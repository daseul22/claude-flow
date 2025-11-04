"""
워크플로우 실행 엔진

워크플로우의 노드를 순차적으로 실행하고, 노드 간 데이터 전달을 관리합니다.
"""

import asyncio
import time
from datetime import datetime
from typing import Dict, Any, AsyncIterator, List, Optional, Tuple, Set
from collections import deque
from dataclasses import replace
from pathlib import Path

from src.domain.models import AgentConfig
from src.infrastructure.config import JsonConfigLoader
from src.infrastructure.claude.worker_client import WorkerAgent
from src.infrastructure.storage.custom_worker_repository import CustomWorkerRepository
from src.infrastructure.logging import get_logger, add_session_file_handlers, remove_session_file_handlers
from src.presentation.web.schemas.workflow import (
    Workflow,
    WorkflowNode,
    WorkflowEdge,
    WorkflowNodeExecutionEvent,
    WorkerNodeData,
    InputNodeData,
    ConditionNodeData,
    MergeNodeData,
    TokenUsage,
)
from src.presentation.web.config import WorkflowConfig, NodeConfig, EventConfig, ErrorMessages

logger = get_logger(__name__)


def extract_text_from_worker_output(output: str) -> str:
    """
    Worker 출력에서 최종 텍스트만 추출

    Worker 출력은 thinking, tool_use, tool_result, text 블록을 포함할 수 있습니다.
    이 함수는 type="text"인 블록만 추출하여 반환합니다.

    Args:
        output: Worker의 전체 출력

    Returns:
        str: 최종 텍스트만 추출된 결과
    """
    import json

    text_parts = []

    # {"role": "assistant"로 시작하는 JSON 객체 찾기 (중괄호 카운팅)
    start_pattern = '{"role":'
    idx = 0

    while idx < len(output):
        # {"role": 패턴 찾기
        start_idx = output.find(start_pattern, idx)
        if start_idx == -1:
            break

        # 중괄호 카운팅으로 완전한 JSON 객체 추출
        brace_count = 0
        in_string = False
        escape_next = False
        end_idx = start_idx

        for i in range(start_idx, len(output)):
            char = output[i]

            if escape_next:
                escape_next = False
                continue

            if char == '\\':
                escape_next = True
                continue

            if char == '"' and not escape_next:
                in_string = not in_string
                continue

            if not in_string:
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        end_idx = i + 1
                        break

        # 완전한 JSON 객체 추출 시도
        if end_idx > start_idx:
            try:
                json_str = output[start_idx:end_idx]
                data = json.loads(json_str)

                # content 배열에서 type="text"인 블록만 추출
                if isinstance(data.get("content"), list):
                    for block in data["content"]:
                        if isinstance(block, dict) and block.get("type") == "text":
                            text_parts.append(block.get("text", ""))

            except json.JSONDecodeError as e:
                logger.debug(f"JSON 파싱 실패 (위치: {start_idx}-{end_idx}): {e}")

            idx = end_idx
        else:
            idx = start_idx + len(start_pattern)

    # 텍스트 블록을 찾았으면 조합하여 반환
    if text_parts:
        result = "\n".join(text_parts).strip()
        logger.debug(f"텍스트 추출 성공: {len(text_parts)}개 블록, {len(result)}자")
        return result

    # JSON 파싱 실패 시 전체 출력 반환 (안전장치)
    logger.warning("텍스트 블록을 찾을 수 없어 전체 출력 반환")
    return output


def classify_chunk_type(chunk: str) -> str:
    """
    Worker 출력 청크의 타입을 분류합니다.

    Args:
        chunk: 출력 청크

    Returns:
        str: "thinking", "tool", "text" 중 하나
    """
    import json

    # JSON 블록인지 확인
    if chunk.strip().startswith('{"role":'):
        try:
            data = json.loads(chunk)
            if isinstance(data.get("content"), list):
                for block in data["content"]:
                    if isinstance(block, dict):
                        block_type = block.get("type", "")
                        if block_type in ("thinking", "tool_use", "tool_result"):
                            return "thinking" if block_type == "thinking" else "tool"
                        elif block_type == "text":
                            return "text"
        except json.JSONDecodeError:
            pass

    # 기본적으로 text로 간주
    return "text"


class WorkflowExecutor:
    """
    워크플로우 실행 엔진

    워크플로우의 노드를 위상 정렬하여 순차적으로 실행하고,
    각 노드의 출력을 다음 노드의 입력으로 전달합니다.

    Attributes:
        config_loader: Agent 설정 로더
        agent_configs: Agent 설정 목록 (캐시)
    """

    def __init__(self, config_loader: JsonConfigLoader, project_path: Optional[str] = None):
        """
        WorkflowExecutor 초기화

        Args:
            config_loader: Agent 설정 로더
            project_path: 프로젝트 경로 (커스텀 워커 로드용, 옵션)
        """
        self.config_loader = config_loader
        self.project_path = project_path
        self.agent_configs = config_loader.load_agent_configs()

        # Condition 노드 반복 횟수 추적 (세션별, 노드별)
        # {session_id: {node_id: iteration_count}}
        self._condition_iterations: Dict[str, Dict[str, int]] = {}

        # 노드 세션 관리 (노드별 현재 활성 SDK 세션 ID 저장)
        # {node_id: session_id}
        # 메모리 기반: 서버 재시작 시 초기화
        # 여러 워크플로우 실행에 걸쳐 유지되어 컨텍스트 재활용
        self._node_sessions: Dict[str, str] = {}

        # 노드 세션 이력 (노드별 모든 세션 목록)
        # {node_id: [SessionInfo, ...]}
        # 사용자가 세션 목록을 보고 선택할 수 있도록 지원
        self._node_session_history: Dict[str, List[Dict[str, Any]]] = {}

        # 노드 에이전트 이름 매핑 (노드별 agent_name 저장)
        # {node_id: agent_name}
        # execute_single_node_continue에서 사용
        self._node_agent_names: Dict[str, str] = {}

        # 사용자 입력 Queue 관리 (세션별)
        # {session_id: asyncio.Queue}
        # Human-in-the-Loop 지원: Worker가 사용자 입력을 요청할 때 사용
        self.user_input_queues: Dict[str, asyncio.Queue] = {}

        # 취소 요청 플래그 (세션별)
        # {session_id}
        # 워크플로우 실행 중 취소 요청이 들어오면 즉시 중단
        self.cancelled_sessions: Set[str] = set()

        # 커스텀 워커 로드 (프로젝트 경로가 주어진 경우)
        self.custom_worker_names = set()
        if project_path:
            try:
                custom_repo = CustomWorkerRepository(Path(project_path))
                custom_workers = custom_repo.load_custom_workers()
                self.agent_configs.extend(custom_workers)
                self.custom_worker_names = {w.name for w in custom_workers}
                logger.info(
                    f"커스텀 워커 로드 완료: {len(custom_workers)}개 "
                    f"(프로젝트: {project_path})"
                )
            except Exception as e:
                logger.warning(
                    f"커스텀 워커 로드 실패 (프로젝트: {project_path}): {e}",
                    exc_info=True
                )

        self.agent_config_map = {
            config.name: config for config in self.agent_configs
        }

    def _get_agent_config(self, agent_name: str) -> AgentConfig:
        """
        Agent 설정 조회

        Args:
            agent_name: Agent 이름

        Returns:
            AgentConfig: Agent 설정

        Raises:
            ValueError: Agent를 찾을 수 없는 경우
        """
        config = self.agent_config_map.get(agent_name)
        if not config:
            # 더 명확한 에러 메시지 제공
            available_agents = list(self.agent_config_map.keys())
            error_msg = (
                f"Agent '{agent_name}'를 찾을 수 없습니다.\n"
                f"사용 가능한 Agent: {', '.join(available_agents)}"
            )

            # 커스텀 워커인 경우 추가 안내
            if agent_name not in self.custom_worker_names:
                error_msg += (
                    f"\n\n힌트: 기본 제공 Worker가 아닙니다. "
                    f"커스텀 워커인 경우 프로젝트 경로를 확인하세요."
                )
            else:
                error_msg += (
                    f"\n\n힌트: 커스텀 워커 '{agent_name}'가 로드되지 않았습니다. "
                    f"프로젝트 경로: {self.project_path}"
                )

            logger.error(error_msg)
            raise ValueError(error_msg)
        return config

    def cancel_session(self, session_id: str) -> None:
        """
        세션 취소 요청

        Args:
            session_id: 취소할 세션 ID
        """
        self.cancelled_sessions.add(session_id)
        logger.info(f"[{session_id}] 세션 취소 요청 등록")

    def _check_cancellation(self, session_id: str) -> None:
        """
        취소 플래그 체크

        Args:
            session_id: 세션 ID

        Raises:
            asyncio.CancelledError: 취소 요청이 있는 경우
        """
        if session_id in self.cancelled_sessions:
            logger.info(f"[{session_id}] 취소 플래그 감지 - CancelledError 발생")
            raise asyncio.CancelledError(f"Session {session_id} was cancelled")

    def _topological_sort(
        self, nodes: List[WorkflowNode], edges: List[WorkflowEdge], start_node_id: Optional[str] = None
    ) -> List[WorkflowNode]:
        """
        워크플로우 노드 위상 정렬 (Topological Sort)

        Args:
            nodes: 노드 목록
            edges: 엣지 목록
            start_node_id: 시작 노드 ID (옵션, 지정 시 해당 Input 노드만 시작점으로 사용)

        Returns:
            List[WorkflowNode]: 실행 순서대로 정렬된 노드 목록

        Raises:
            ValueError: 순환 참조가 있는 경우
        """
        # 노드 ID → 노드 매핑
        node_map = {node.id: node for node in nodes}

        # 유효하지 않은 엣지 필터링 (존재하지 않는 노드를 참조하는 엣지 제거)
        valid_edges = []
        for edge in edges:
            if edge.source not in node_map:
                logger.warning(
                    f"엣지 {edge.id}: source 노드 '{edge.source}'가 존재하지 않습니다. 엣지를 무시합니다."
                )
                continue
            if edge.target not in node_map:
                logger.warning(
                    f"엣지 {edge.id}: target 노드 '{edge.target}'가 존재하지 않습니다. 엣지를 무시합니다."
                )
                continue
            valid_edges.append(edge)

        # Input 노드 찾기 (시작점)
        input_nodes = [node for node in nodes if node.type == "input"]
        if not input_nodes:
            raise ValueError("워크플로우에 Input 노드가 없습니다. Input 노드에서 시작해야 합니다.")

        # start_node_id가 지정된 경우 해당 노드만 시작점으로 사용
        if start_node_id:
            # 지정된 노드가 Input 노드인지 확인
            start_node = node_map.get(start_node_id)
            if not start_node:
                raise ValueError(f"지정된 시작 노드를 찾을 수 없습니다: {start_node_id}")
            if start_node.type != "input":
                raise ValueError(f"시작 노드는 Input 노드여야 합니다: {start_node_id} (타입: {start_node.type})")
            input_node_ids = [start_node_id]
            logger.info(f"특정 Input 노드에서 시작: {start_node_id}")
        else:
            # start_node_id가 없으면 모든 Input 노드를 시작점으로 사용 (기존 동작)
            input_node_ids = [node.id for node in input_nodes]
            logger.info(f"모든 Input 노드에서 시작: {input_node_ids}")

        # Condition 노드의 max_iterations가 설정된 경우 피드백 루프 허용
        # 백엣지(back-edge) 식별: Condition 노드에서 나가는 엣지가 이미 방문한 노드로 가는 경우
        condition_nodes_with_iterations = set()
        for node in nodes:
            if node.type == "condition":
                max_iterations = None
                if hasattr(node.data, "max_iterations"):
                    max_iterations = node.data.max_iterations
                elif isinstance(node.data, dict):
                    max_iterations = node.data.get("max_iterations")

                if max_iterations is not None:
                    condition_nodes_with_iterations.add(node.id)
                    logger.info(f"Condition 노드 발견 (max_iterations={max_iterations}): {node.id}")
                else:
                    logger.debug(f"Condition 노드 발견 (max_iterations 없음): {node.id}")

        logger.info(f"피드백 루프 제어 노드 총 {len(condition_nodes_with_iterations)}개: {condition_nodes_with_iterations}")

        # 백엣지 식별 (DFS로 순환 경로 파악)
        back_edges = set()
        visited_dfs = set()
        rec_stack = set()

        def identify_back_edges(node_id: str, path: List[str]):
            """DFS로 백엣지 식별 (순환 경로에 Condition + max_iterations 포함 여부 확인)"""
            visited_dfs.add(node_id)
            rec_stack.add(node_id)
            path.append(node_id)

            for edge in valid_edges:
                if edge.source == node_id:
                    target = edge.target

                    # 이미 방문 스택에 있으면 백엣지 (순환)
                    if target in rec_stack:
                        logger.debug(f"🔄 백엣지 발견: {node_id} → {target}")

                        # 순환 경로 추출 (target부터 현재 노드까지)
                        try:
                            cycle_start_idx = path.index(target)
                            cycle_path = path[cycle_start_idx:] + [target]
                            logger.debug(f"   순환 경로: {' → '.join(cycle_path)}")
                        except ValueError:
                            logger.error(f"   ❌ 순환 경로 추출 실패: target={target}, path={path}")
                            continue

                        # 순환 경로에 max_iterations가 설정된 Condition 노드가 있는지 확인
                        has_condition_with_iterations = any(
                            node_id in condition_nodes_with_iterations
                            for node_id in cycle_path
                        )
                        logger.debug(f"   Condition 노드 포함 여부: {has_condition_with_iterations}")

                        if has_condition_with_iterations:
                            # 피드백 루프 허용: 백엣지로 표시
                            back_edges.add((edge.source, edge.target))
                            logger.info(
                                f"✅ 피드백 루프 감지 (허용): {edge.source} → {edge.target} "
                                f"(순환 경로: {' → '.join(cycle_path)})"
                            )
                        else:
                            # max_iterations 없는 순환: 검증 단계에서 에러 발생
                            logger.warning(
                                f"⚠️ 무제한 순환 감지: {edge.source} → {edge.target} "
                                f"(순환 경로: {' → '.join(cycle_path)}). "
                                f"Condition 노드에 max_iterations를 설정하세요."
                            )
                    elif target not in visited_dfs:
                        identify_back_edges(target, path.copy())

            rec_stack.remove(node_id)

        # 모든 Input 노드에서 DFS 시작하여 백엣지 식별
        for input_id in input_node_ids:
            if input_id not in visited_dfs:
                identify_back_edges(input_id, [])

        logger.info(f"백엣지 식별 완료: 총 {len(back_edges)}개 발견")
        if back_edges:
            for source, target in back_edges:
                logger.info(f"  - {source} → {target}")
        else:
            logger.info("  (백엣지 없음)")

        # 인접 리스트 (노드 ID → 자식 노드 ID 목록)
        adjacency: Dict[str, List[str]] = {node.id: [] for node in nodes}
        in_degree: Dict[str, int] = {node.id: 0 for node in nodes}

        for edge in valid_edges:
            # 백엣지는 위상 정렬에서 제외 (피드백 루프)
            if (edge.source, edge.target) not in back_edges:
                adjacency[edge.source].append(edge.target)
                in_degree[edge.target] += 1
            else:
                logger.debug(f"백엣지 제외 (위상 정렬): {edge.source} → {edge.target}")

        # 디버깅: 인접 리스트 출력
        logger.debug("위상 정렬용 인접 리스트:")
        for node_id, children in adjacency.items():
            if children:
                logger.debug(f"  {node_id} → {children}")

        # Input 노드에서 도달 가능한 노드만 필터링 (BFS)
        reachable_nodes = set(input_node_ids)
        bfs_queue = deque(input_node_ids)

        while bfs_queue:
            current_id = bfs_queue.popleft()
            for child_id in adjacency[current_id]:
                if child_id not in reachable_nodes:
                    reachable_nodes.add(child_id)
                    bfs_queue.append(child_id)

        # 도달 불가능한 노드 경고
        unreachable_nodes = [node.id for node in nodes if node.id not in reachable_nodes]
        if unreachable_nodes:
            logger.warning(
                f"Input 노드에서 도달할 수 없는 노드가 있습니다: {unreachable_nodes}. "
                "이 노드들은 실행되지 않습니다."
            )

        # 도달 가능한 노드만으로 위상 정렬 수행
        # Input 노드만 시작점으로 설정
        queue = deque(input_node_ids)
        sorted_nodes = []
        visited = set()

        # 무한 루프 방지: 최대 반복 횟수 (노드 수 * 노드 수)
        max_iterations = len(reachable_nodes) * len(reachable_nodes)
        iteration_count = 0
        stuck_counter: Dict[str, int] = {}  # 각 노드가 큐에 추가된 횟수

        while queue:
            iteration_count += 1
            if iteration_count > max_iterations:
                stuck_nodes = [nid for nid, count in stuck_counter.items() if count > 5]
                raise ValueError(
                    f"위상 정렬 중 무한 루프 감지. 교착 상태 노드: {stuck_nodes}. "
                    f"Condition 노드 + max_iterations를 통한 피드백 루프가 아닌 실제 순환 참조가 있을 수 있습니다."
                )

            node_id = queue.popleft()

            if node_id in visited:
                continue

            # 도달 불가능한 노드는 건너뜀
            if node_id not in reachable_nodes:
                continue

            # 모든 부모 노드가 처리되었는지 확인 (백엣지 제외)
            parents_ready = True
            for edge in valid_edges:
                # 백엣지는 부모 의존성 체크에서 제외 (피드백 루프)
                if (edge.source, edge.target) in back_edges:
                    continue

                if edge.target == node_id and edge.source in reachable_nodes:
                    if edge.source not in visited:
                        parents_ready = False
                        break

            if not parents_ready:
                # 부모 노드가 아직 처리되지 않았으면 큐 뒤로
                stuck_counter[node_id] = stuck_counter.get(node_id, 0) + 1
                queue.append(node_id)
                continue

            visited.add(node_id)
            sorted_nodes.append(node_map[node_id])

            # 자식 노드를 큐에 추가
            for child_id in adjacency[node_id]:
                if child_id not in visited and child_id in reachable_nodes:
                    queue.append(child_id)

        # 순환 참조 검사 (도달 가능한 노드 기준)
        if len(sorted_nodes) != len(reachable_nodes):
            unvisited = [nid for nid in reachable_nodes if nid not in visited]
            raise ValueError(
                f"워크플로우에 순환 참조가 있습니다. 방문하지 못한 노드: {unvisited}"
            )

        return sorted_nodes

    def _get_parent_nodes(
        self, node_id: str, edges: List[WorkflowEdge]
    ) -> List[str]:
        """
        노드의 부모 노드 ID 목록 조회

        Args:
            node_id: 노드 ID
            edges: 엣지 목록

        Returns:
            List[str]: 부모 노드 ID 목록
        """
        return [edge.source for edge in edges if edge.target == node_id]

    def _get_child_nodes(
        self, node_id: str, edges: List[WorkflowEdge]
    ) -> List[str]:
        """
        노드의 자식 노드 ID 목록 조회

        Args:
            node_id: 노드 ID
            edges: 엣지 목록

        Returns:
            List[str]: 자식 노드 ID 목록
        """
        return [edge.target for edge in edges if edge.source == node_id]

    def _extract_final_output(self, full_output: str) -> str:
        """
        전체 출력에서 최종 표준 출력 추출 (TextBlock만)

        SDK 출력은 JSON 형식으로 직렬화되어 있습니다:
        - {"role": "assistant", "content": [{"type": "text", "text": "..."}]}
        - {"role": "assistant", "content": [{"type": "thinking", "thinking": "..."}]}
        - {"role": "assistant", "content": [{"type": "tool_use", ...}]}
        - {"role": "user", "content": [{"type": "tool_result", ...}]}

        이 메서드는 type="text"인 블록만 추출합니다.

        Args:
            full_output: 전체 출력 (모든 chunk 결합)

        Returns:
            str: 최종 표준 출력 (TextBlock만)
        """
        import json
        import re

        text_parts = []

        # JSON 블록 추출 ({"role": ... } 패턴)
        json_pattern = r'\{"role":\s*"[^"]+",\s*"content":\s*\[.*?\]\}'

        for match in re.finditer(json_pattern, full_output, re.DOTALL):
            try:
                json_str = match.group(0)
                data = json.loads(json_str)

                if isinstance(data, dict) and "content" in data:
                    for block in data["content"]:
                        if isinstance(block, dict) and block.get("type") == "text":
                            text_parts.append(block.get("text", ""))

            except json.JSONDecodeError:
                continue

        # JSON이 아닌 일반 텍스트도 포함 (디버그 정보 등 제외)
        # JSON 블록을 제거한 나머지 텍스트
        cleaned_output = re.sub(json_pattern, '', full_output, flags=re.DOTALL)

        # Worker 완료 메시지 제거
        cleaned_output = re.sub(
            r'\n={50,}\n✅\s*\[.*?\]\s*Worker execution completed\n={50,}\n',
            '',
            cleaned_output
        )

        # 디버그 정보 제거 (🔍으로 시작하는 블록)
        cleaned_output = re.sub(
            r'\n={50,}\n🔍.*?={50,}\n',
            '',
            cleaned_output,
            flags=re.DOTALL
        )

        # 빈 줄만 있는 경우 제거
        cleaned_output = cleaned_output.strip()

        if cleaned_output:
            text_parts.append(cleaned_output)

        return "".join(text_parts)

    def _check_parallel_execution(self, node: WorkflowNode) -> bool:
        """
        노드의 parallel_execution 플래그 확인

        Args:
            node: 워크플로우 노드

        Returns:
            bool: 병렬 실행 여부
        """
        if isinstance(node.data, dict):
            return node.data.get("parallel_execution", False)
        else:
            return getattr(node.data, "parallel_execution", False)

    def _compute_execution_groups(
        self, nodes: List[WorkflowNode], edges: List[WorkflowEdge]
    ) -> List[List[WorkflowNode]]:
        """
        병렬 실행 그룹 계산

        parallel_execution=True인 노드의 자식 노드들을 병렬 그룹으로 묶습니다.

        Args:
            nodes: 위상 정렬된 노드 목록
            edges: 엣지 목록

        Returns:
            List[List[WorkflowNode]]: 실행 그룹 목록 (각 그룹은 병렬 실행)
        """
        node_map = {node.id: node for node in nodes}
        processed = set()
        execution_groups = []

        for node in nodes:
            if node.id in processed:
                continue

            # parallel_execution 플래그 확인
            if self._check_parallel_execution(node):
                # 자식 노드들을 병렬 그룹으로 묶음
                child_ids = self._get_child_nodes(node.id, edges)
                parallel_group = []

                for child_id in child_ids:
                    if child_id in node_map and child_id not in processed:
                        parallel_group.append(node_map[child_id])
                        processed.add(child_id)

                # 현재 노드는 단독 실행
                execution_groups.append([node])
                processed.add(node.id)

                # 자식 노드들은 병렬 실행
                if parallel_group:
                    execution_groups.append(parallel_group)
            else:
                # 단독 실행
                execution_groups.append([node])
                processed.add(node.id)

        return execution_groups

    def _render_task_template(
        self,
        template: str,
        node_id: str,
        node_outputs: Dict[str, str],
        initial_input: str,
    ) -> str:
        """
        작업 설명 템플릿 렌더링

        변수:
        - {{input}}: 초기 입력 (첫 번째 노드)
        - {{node_<id>}}: 특정 노드의 출력
        - {{parent}}: 부모 노드의 출력 (부모가 1개인 경우)

        Args:
            template: 템플릿 문자열
            node_id: 현재 노드 ID
            node_outputs: 노드 ID → 출력 매핑
            initial_input: 초기 입력

        Returns:
            str: 렌더링된 작업 설명
        """
        result = template

        # {{input}} 치환
        result = result.replace("{{input}}", initial_input)

        # {{node_<id>}} 치환
        for nid, output in node_outputs.items():
            result = result.replace(f"{{{{node_{nid}}}}}", output)

        # {{parent}} 치환 (부모가 1개인 경우만 지원)
        if "{{parent}}" in result:
            parent_node_ids = list(node_outputs.keys())
            if len(parent_node_ids) == 1:
                # 부모가 1개인 경우, 해당 노드의 출력 사용
                result = result.replace("{{parent}}", node_outputs[parent_node_ids[0]])
            elif len(parent_node_ids) == 0:
                # 부모가 없으면 빈 문자열로 치환
                result = result.replace("{{parent}}", "")
            else:
                # 부모가 여러 개인 경우, 경고 로그 및 첫 번째 부모 출력 사용
                logger.warning(
                    f"노드에 부모가 {len(parent_node_ids)}개 있습니다. "
                    f"{{{{parent}}}} 변수는 부모가 1개인 경우만 지원합니다. "
                    f"첫 번째 부모의 출력을 사용합니다: {parent_node_ids[0]}"
                )
                result = result.replace("{{parent}}", node_outputs[parent_node_ids[0]])

        return result

    async def _evaluate_llm_condition(
        self,
        condition_prompt: str,
        input_text: str,
        session_id: str,
    ) -> Tuple[bool, str]:
        """
        LLM을 사용하여 조건 평가 (Haiku 모델 사용)

        Args:
            condition_prompt: LLM에게 전달할 조건 프롬프트
            input_text: 평가할 텍스트
            session_id: 세션 ID

        Returns:
            Tuple[bool, str]: (조건 결과, LLM 응답 이유)
        """
        from claude_agent_sdk import query
        from claude_agent_sdk.types import ClaudeAgentOptions

        logger.info(f"[{session_id}] LLM 조건 평가 시작 (Haiku 모델)")

        # Haiku 모델로 빠른 판단
        options = ClaudeAgentOptions(
            model=WorkflowConfig.HAIKU_MODEL,
            allowed_tools=[],  # 도구 사용 안함
            permission_mode="bypassPermissions",  # 자동 실행을 위해 승인 우회
        )

        # LLM에게 전달할 전체 프롬프트
        full_prompt = f"""다음 출력을 분석하여 조건을 평가해주세요.

<조건>
{condition_prompt}
</조건>

<평가 대상 출력>
{input_text[:WorkflowConfig.LLM_INPUT_LIMIT]}
</평가 대상 출력>

위 출력이 조건을 만족하는지 판단하여, 다음 형식으로 응답해주세요:

판단: [YES 또는 NO]
이유: [한 줄 설명]

예시:
판단: YES
이유: 테스트가 모두 통과했으며 에러가 없습니다.
"""

        try:
            # LLM 호출
            response_text = ""
            async for response in query(prompt=full_prompt, options=options):
                if hasattr(response, 'content') and isinstance(response.content, list):
                    for block in response.content:
                        if hasattr(block, 'type') and block.type == 'text':
                            response_text += block.text

            logger.debug(f"[{session_id}] LLM 응답: {response_text[:WorkflowConfig.CONDITION_OUTPUT_LIMIT]}")

            # 응답 파싱
            lines = response_text.strip().split('\n')
            result = False
            reason = ""

            for line in lines:
                if line.startswith('판단:'):
                    decision = line.replace('판단:', '').strip().upper()
                    result = decision in ['YES', 'Y', 'TRUE', '예']
                elif line.startswith('이유:'):
                    reason = line.replace('이유:', '').strip()

            if not reason:
                reason = response_text[:WorkflowConfig.CONDITION_OUTPUT_LIMIT]  # 파싱 실패 시 전체 응답 사용

            logger.info(
                f"[{session_id}] LLM 조건 평가 완료: {result} (이유: {reason[:100]})"
            )

            return result, reason

        except Exception as e:
            logger.error(f"[{session_id}] LLM 조건 평가 실패: {e}", exc_info=True)
            # 에러 발생 시 안전하게 False 반환
            return False, f"LLM 평가 실패: {str(e)}"

    def _evaluate_condition(
        self,
        condition_type: str,
        condition_value: str,
        input_text: str
    ) -> bool:
        """
        조건 평가

        Args:
            condition_type: 조건 타입 ('contains', 'regex', 'length', 'custom', 'llm')
            condition_value: 조건 값
            input_text: 평가할 텍스트

        Returns:
            bool: 조건이 True인지 여부
        """
        import re

        if condition_type == "contains":
            # 텍스트 포함 검사
            return condition_value in input_text

        elif condition_type == "regex":
            # 정규표현식 매칭
            try:
                pattern = re.compile(condition_value)
                return bool(pattern.search(input_text))
            except re.error as e:
                logger.error(f"정규표현식 오류: {e}")
                return False

        elif condition_type == "length":
            # 길이 비교 (예: ">100", "<=500", "==0")
            try:
                text_length = len(input_text)
                # condition_value를 파싱하여 비교
                if condition_value.startswith(">="):
                    threshold = int(condition_value[2:].strip())
                    return text_length >= threshold
                elif condition_value.startswith("<="):
                    threshold = int(condition_value[2:].strip())
                    return text_length <= threshold
                elif condition_value.startswith(">"):
                    threshold = int(condition_value[1:].strip())
                    return text_length > threshold
                elif condition_value.startswith("<"):
                    threshold = int(condition_value[1:].strip())
                    return text_length < threshold
                elif condition_value.startswith("=="):
                    threshold = int(condition_value[2:].strip())
                    return text_length == threshold
                else:
                    # 숫자만 있는 경우 == 로 간주
                    threshold = int(condition_value.strip())
                    return text_length == threshold
            except (ValueError, IndexError) as e:
                logger.error(f"길이 조건 파싱 오류: {e}")
                return False

        elif condition_type == "custom":
            # 커스텀 Python 표현식 평가
            try:
                # 안전한 평가를 위해 제한된 네임스페이스 사용
                namespace = {
                    "output": input_text,
                    "len": len,
                    "str": str,
                    "int": int,
                    "float": float,
                }
                result = eval(condition_value, {"__builtins__": {}}, namespace)
                return bool(result)
            except Exception as e:
                logger.error(f"커스텀 조건 평가 오류: {e}")
                return False

        else:
            logger.warning(f"알 수 없는 조건 타입: {condition_type}")
            return False

    async def _execute_condition_node(
        self,
        node: WorkflowNode,
        node_outputs: Dict[str, str],
        edges: List[WorkflowEdge],
        session_id: str,
    ) -> tuple[str, str]:
        """
        조건 분기 노드 실행 (반복 제한 포함)

        Args:
            node: 조건 노드
            node_outputs: 이전 노드 출력들
            edges: 엣지 목록 (분기 경로 확인용)
            session_id: 세션 ID

        Returns:
            tuple[str, str]: (다음 실행할 노드 ID, 조건 평가 결과 텍스트)

        Raises:
            ValueError: 부모 노드가 없거나 분기 경로가 없는 경우
        """
        node_id = node.id
        node_data: ConditionNodeData = node.data  # type: ignore

        # 반복 횟수 증가
        if session_id not in self._condition_iterations:
            self._condition_iterations[session_id] = {}

        current_iteration = self._condition_iterations[session_id].get(node_id, 0) + 1
        self._condition_iterations[session_id][node_id] = current_iteration

        logger.info(
            f"[{session_id}] 조건 노드 실행: {node_id} "
            f"(타입: {node_data.condition_type}, 반복: {current_iteration}회)"
        )

        # 부모 노드 출력 가져오기
        parent_nodes = self._get_parent_nodes(node_id, edges)
        if not parent_nodes:
            raise ValueError(f"조건 노드 {node_id}에 부모 노드가 없습니다")

        # 첫 번째 부모 노드의 출력 사용
        parent_id = parent_nodes[0]
        parent_output = node_outputs.get(parent_id, "")

        # LLM 조건인 경우 비동기 평가
        llm_reason = ""
        if node_data.condition_type == "llm":
            condition_result, llm_reason = await self._evaluate_llm_condition(
                node_data.condition_value,
                parent_output,
                session_id
            )
        else:
            # 일반 조건 평가
            condition_result = self._evaluate_condition(
                node_data.condition_type,
                node_data.condition_value,
                parent_output
            )

        logger.info(
            f"[{session_id}] 조건 평가 결과: {condition_result} "
            f"(입력 길이: {len(parent_output)})"
        )

        # max_iterations 체크 (반복 제한)
        # max_iterations가 None인 경우 기본값 10 사용
        max_iterations = node_data.max_iterations if node_data.max_iterations is not None else 10

        if current_iteration >= max_iterations:
            logger.warning(
                f"[{session_id}] 조건 노드 {node_id}: "
                f"최대 반복 횟수 도달 ({current_iteration}/{max_iterations}). "
                f"강제로 true 경로로 이동합니다."
            )
            # 최대 반복 횟수 도달 시 강제로 true 경로로 이동
            condition_result = True
            llm_reason = f"최대 반복 횟수 도달 ({max_iterations}회)"

        # 분기 경로 결정 (엣지의 sourceHandle을 사용)
        # sourceHandle이 "true"인 엣지 → True 경로
        # sourceHandle이 "false"인 엣지 → False 경로
        next_node_id = None
        for edge in edges:
            if edge.source == node_id:
                if condition_result and edge.sourceHandle == "true":
                    next_node_id = edge.target
                    break
                elif not condition_result and edge.sourceHandle == "false":
                    next_node_id = edge.target
                    break

        if next_node_id is None:
            branch_type = "true" if condition_result else "false"
            raise ValueError(
                f"조건 노드 {node_id}의 {branch_type} 분기 경로가 없습니다. "
                f"sourceHandle이 '{branch_type}'인 엣지를 추가해주세요."
            )

        # 조건 결과를 텍스트로 변환
        result_text = f"조건 평가 결과: {condition_result}\n"
        result_text += f"반복 횟수: {current_iteration}/{max_iterations}"
        result_text += f"\n분기: {next_node_id}"

        if llm_reason:
            result_text += f"\nLLM 판단 이유: {llm_reason}"

        return next_node_id, result_text

    async def _execute_merge_node(
        self,
        node: WorkflowNode,
        node_outputs: Dict[str, str],
        edges: List[WorkflowEdge],
        session_id: str,
    ) -> str:
        """
        병합 노드 실행

        Args:
            node: 병합 노드
            node_outputs: 이전 노드 출력들
            edges: 엣지 목록
            session_id: 세션 ID

        Returns:
            str: 병합된 출력
        """
        node_id = node.id
        node_data: MergeNodeData = node.data  # type: ignore

        logger.info(
            f"[{session_id}] 병합 노드 실행: {node_id} "
            f"(전략: {node_data.merge_strategy})"
        )

        # 부모 노드 출력들 수집
        parent_nodes = self._get_parent_nodes(node_id, edges)
        if not parent_nodes:
            raise ValueError(f"병합 노드 {node_id}에 부모 노드가 없습니다")

        parent_outputs = []
        for pid in parent_nodes:
            if pid not in node_outputs:
                logger.warning(
                    f"[{session_id}] 병합 노드 {node_id}: "
                    f"부모 노드 '{pid}'의 출력이 없습니다. 빈 문자열을 사용합니다."
                )
            parent_outputs.append(node_outputs.get(pid, ""))

        # 병합 전략에 따라 출력 생성
        if node_data.merge_strategy == "concatenate":
            # 모든 출력을 구분자로 결합
            merged_output = node_data.separator.join(parent_outputs)

        elif node_data.merge_strategy == "first":
            # 첫 번째 출력만 사용
            merged_output = parent_outputs[0] if parent_outputs else ""

        elif node_data.merge_strategy == "last":
            # 마지막 출력만 사용
            merged_output = parent_outputs[-1] if parent_outputs else ""

        elif node_data.merge_strategy == "custom":
            # 커스텀 템플릿 사용
            if node_data.custom_template:
                merged_output = node_data.custom_template
                for i, output in enumerate(parent_outputs):
                    merged_output = merged_output.replace(f"{{{{branch_{i+1}}}}}", output)
            else:
                # 템플릿이 없으면 concatenate로 폴백
                merged_output = node_data.separator.join(parent_outputs)

        else:
            logger.warning(
                f"알 수 없는 병합 전략: {node_data.merge_strategy}, "
                "concatenate로 폴백합니다"
            )
            merged_output = node_data.separator.join(parent_outputs)

        logger.info(
            f"[{session_id}] 병합 노드 완료: {node_id} "
            f"(입력: {len(parent_outputs)}개, 출력 길이: {len(merged_output)})"
        )

        return merged_output

    async def _execute_single_node(
        self,
        node: WorkflowNode,
        node_outputs: Dict[str, str],
        initial_input: str,
        session_id: str,
        edges: List[WorkflowEdge],
        all_nodes: List[WorkflowNode],
        project_path: Optional[str] = None,
    ) -> AsyncIterator[WorkflowNodeExecutionEvent]:
        """
        단일 노드 실행 (모든 노드 타입 지원)

        Args:
            node: 실행할 노드
            node_outputs: 이전 노드 출력들
            initial_input: 초기 입력
            session_id: 세션 ID
            edges: 엣지 목록
            all_nodes: 모든 노드 목록
            project_path: 프로젝트 디렉토리 경로

        Yields:
            WorkflowNodeExecutionEvent: 노드 실행 이벤트
        """
        node_id = node.id

        # 취소 플래그 체크 (각 노드 실행 전)
        self._check_cancellation(session_id)

        # Input 노드 처리
        if node.type == "input":
            if isinstance(node.data, InputNodeData):
                input_value = node.data.initial_input
            elif isinstance(node.data, dict):
                input_value = node.data.get("initial_input", initial_input)
            else:
                input_value = initial_input
            node_outputs[node_id] = input_value

            yield WorkflowNodeExecutionEvent(
                event_type="node_start",
                node_id=node_id,
                data={
                    "agent_name": "Input",
                },
                timestamp=datetime.now().isoformat(),
            )

            # 입력 로그 이벤트
            yield WorkflowNodeExecutionEvent(
                event_type="node_output",
                node_id=node_id,
                data={
                    "chunk": input_value,
                    "log_type": "input"  # 노드 입력
                },
            )

            # 최종 출력 이벤트 (Input 노드는 입력=출력)
            yield WorkflowNodeExecutionEvent(
                event_type="node_output",
                node_id=node_id,
                data={
                    "chunk": input_value,
                    "log_type": "output"  # 최종 출력
                },
            )

            yield WorkflowNodeExecutionEvent(
                event_type="node_complete",
                node_id=node_id,
                data={
                    "node_type": "input",
                    "agent_name": "Input",
                    "output_length": len(input_value),
                },
                timestamp=datetime.now().isoformat(),
                elapsed_time=0.0,
            )

            logger.info(
                f"[{session_id}] Input 노드 완료: {node_id} "
                f"(출력 길이: {len(input_value)})"
            )
            return

        # Condition 노드
        elif node.type == "condition":
            start_time = time.time()

            # 부모 노드 출력 가져오기 (입력으로 사용)
            parent_nodes = self._get_parent_nodes(node_id, edges)
            parent_output = ""
            if parent_nodes:
                parent_id = parent_nodes[0]
                parent_output = node_outputs.get(parent_id, "")

            node_data: ConditionNodeData = node.data  # type: ignore

            yield WorkflowNodeExecutionEvent(
                event_type="node_start",
                node_id=node_id,
                data={
                    "node_type": "condition",
                    "input": parent_output,
                    "condition_type": node_data.condition_type,
                    "condition_value": node_data.condition_value,
                },
                timestamp=datetime.now().isoformat(),
            )

            try:
                next_node_id, result_text = await self._execute_condition_node(
                    node, node_outputs, edges, session_id
                )

                node_outputs[node_id] = result_text
                elapsed_time = time.time() - start_time

                yield WorkflowNodeExecutionEvent(
                    event_type="node_complete",
                    node_id=node_id,
                    data={
                        "node_type": "condition",
                        "next_node": next_node_id,
                        "output": result_text,
                    },
                    timestamp=datetime.now().isoformat(),
                    elapsed_time=elapsed_time,
                )

                logger.info(
                    f"[{session_id}] 조건 노드 완료: {node_id} → {next_node_id}"
                )

            except Exception as e:
                error_msg = f"조건 노드 실행 실패: {str(e)}"
                logger.error(f"[{session_id}] {node_id}: {error_msg}", exc_info=True)

                elapsed_time = time.time() - start_time

                yield WorkflowNodeExecutionEvent(
                    event_type="node_error",
                    node_id=node_id,
                    data={"error": error_msg},
                    timestamp=datetime.now().isoformat(),
                    elapsed_time=elapsed_time,
                )

                raise

        # Merge 노드
        elif node.type == "merge":
            start_time = time.time()

            # 부모 노드 출력들 가져오기 (입력으로 사용)
            parent_nodes = self._get_parent_nodes(node_id, edges)
            parent_outputs_list = []
            for pid in parent_nodes:
                parent_outputs_list.append(node_outputs.get(pid, ""))

            node_data: MergeNodeData = node.data  # type: ignore

            # 입력 요약 (각 부모 노드의 출력 길이)
            input_summary = {
                f"parent_{i+1}": len(output) for i, output in enumerate(parent_outputs_list)
            }

            yield WorkflowNodeExecutionEvent(
                event_type="node_start",
                node_id=node_id,
                data={
                    "node_type": "merge",
                    "input": "\n\n---\n\n".join(parent_outputs_list),
                    "input_summary": input_summary,
                    "merge_strategy": node_data.merge_strategy,
                },
                timestamp=datetime.now().isoformat(),
            )

            try:
                merged_output = await self._execute_merge_node(
                    node, node_outputs, edges, session_id
                )

                node_outputs[node_id] = merged_output
                elapsed_time = time.time() - start_time

                yield WorkflowNodeExecutionEvent(
                    event_type="node_complete",
                    node_id=node_id,
                    data={
                        "node_type": "merge",
                        "output_length": len(merged_output),
                        "output": merged_output,
                    },
                    timestamp=datetime.now().isoformat(),
                    elapsed_time=elapsed_time,
                )

                logger.info(
                    f"[{session_id}] 병합 노드 완료: {node_id} "
                    f"(출력 길이: {len(merged_output)})"
                )

            except Exception as e:
                error_msg = f"병합 노드 실행 실패: {str(e)}"
                logger.error(f"[{session_id}] {node_id}: {error_msg}", exc_info=True)

                elapsed_time = time.time() - start_time

                yield WorkflowNodeExecutionEvent(
                    event_type="node_error",
                    node_id=node_id,
                    data={"error": error_msg},
                    timestamp=datetime.now().isoformat(),
                    elapsed_time=elapsed_time,
                )

                raise

        # Worker 노드
        else:
            if isinstance(node.data, dict):
                agent_name = node.data.get("agent_name")
                task_template = node.data.get("task_template")
                allowed_tools_override = node.data.get("allowed_tools")
                thinking_override = node.data.get("thinking")

                if not agent_name:
                    raise ValueError(f"노드 {node_id}: agent_name이 지정되지 않았습니다")
                if not task_template:
                    raise ValueError(f"노드 {node_id}: task_template이 지정되지 않았습니다")
            else:
                node_data: WorkerNodeData = node.data  # type: ignore
                agent_name = node_data.agent_name
                task_template = node_data.task_template
                allowed_tools_override = node_data.allowed_tools
                thinking_override = node_data.thinking

            start_time = time.time()

            # 먼저 task_description 생성 (입력 저장용)
            agent_config = self._get_agent_config(agent_name)

            if allowed_tools_override is not None:
                agent_config = replace(agent_config, allowed_tools=allowed_tools_override)
                logger.info(
                    f"[{session_id}] 노드 {node_id}: allowed_tools 오버라이드 "
                    f"({len(allowed_tools_override)}개 도구)"
                )

            if thinking_override is not None:
                agent_config = replace(agent_config, thinking=thinking_override)
                logger.info(
                    f"[{session_id}] 노드 {node_id}: thinking 모드 오버라이드 "
                    f"(thinking={thinking_override})"
                )

            parent_nodes = self._get_parent_nodes(node_id, edges)
            parent_outputs = {
                pid: node_outputs[pid] for pid in parent_nodes
                if pid in node_outputs
            }

            task_description = self._render_task_template(
                template=task_template,
                node_id=node_id,
                node_outputs=parent_outputs,
                initial_input=initial_input,
            )

            # node_start 이벤트
            start_event = WorkflowNodeExecutionEvent(
                event_type="node_start",
                node_id=node_id,
                data={
                    "agent_name": agent_name,
                },
                timestamp=datetime.now().isoformat(),
            )
            logger.info(f"[{session_id}] 🟢 이벤트 생성: node_start (node: {node_id}, agent: {agent_name})")
            yield start_event

            # 입력 이벤트 (별도 이벤트로 전송)
            input_event = WorkflowNodeExecutionEvent(
                event_type="node_output",
                node_id=node_id,
                data={
                    "chunk": task_description,
                    "chunk_type": "input",  # 입력임을 명시
                },
            )
            logger.debug(f"[{session_id}] 📥 이벤트 생성: node_input (node: {node_id})")
            yield input_event

            try:
                logger.info(
                    f"[{session_id}] 노드 실행: {node_id} ({agent_name}) "
                    f"- 작업 길이: {len(task_description)}"
                )

                # 노드별 세션 관리: 이전 세션 ID가 있으면 재사용
                previous_session_id = self._node_sessions.get(node_id)
                if previous_session_id:
                    logger.info(
                        f"[{session_id}] 노드 {node_id}: 이전 세션 재개 "
                        f"(세션: {previous_session_id[:8]}...)"
                    )
                else:
                    logger.info(
                        f"[{session_id}] 노드 {node_id}: 새 세션 시작"
                    )

                worker = WorkerAgent(config=agent_config, project_dir=project_path)
                node_output_chunks = []
                node_token_usage: Optional[TokenUsage] = None

                def usage_callback(usage_info: Dict[str, Any]):
                    nonlocal node_token_usage
                    node_token_usage = TokenUsage(
                        input_tokens=usage_info.get("input_tokens", 0),
                        output_tokens=usage_info.get("output_tokens", 0),
                        total_tokens=usage_info.get("total_tokens", 0),
                    )
                    logger.debug(
                        f"[{session_id}] 💰 토큰 사용량: {node_token_usage.total_tokens} "
                        f"(입력: {node_token_usage.input_tokens}, 출력: {node_token_usage.output_tokens})"
                    )

                # 사용자 입력 콜백 정의 (Human-in-the-Loop)
                # user_input_queue는 execute_workflow에서 생성되어 self.user_input_queues에 저장됨
                async def user_input_callback_impl(question: str) -> str:
                    """사용자 입력을 Queue에서 대기"""
                    logger.info(f"[{session_id}] 💬 사용자 입력 대기: {question[:100]}...")
                    user_queue = self.user_input_queues.get(session_id)
                    if not user_queue:
                        logger.error(f"[{session_id}] 사용자 입력 Queue를 찾을 수 없음")
                        raise ValueError(f"세션 {session_id}의 사용자 입력 Queue를 찾을 수 없습니다")
                    answer = await user_queue.get()
                    logger.info(f"[{session_id}] ✅ 사용자 답변 수신: {answer[:100]}...")
                    return answer

                # Worker 실행 (이전 세션 ID 및 user_input_callback 전달)
                async for chunk in worker.execute_task(
                    task_description,
                    usage_callback=usage_callback,
                    resume_session_id=previous_session_id,
                    user_input_callback=user_input_callback_impl
                ):
                    # 🔴 취소 플래그 체크 (SDK 스트리밍 중에도 즉시 중단)
                    self._check_cancellation(session_id)

                    # 특수 이벤트 마커 감지 (Human-in-the-Loop)
                    if chunk.startswith("@EVENT:user_input_request:"):
                        import json
                        # 마커 제거 및 JSON 파싱
                        json_str = chunk[len("@EVENT:user_input_request:"):]
                        event_data = json.loads(json_str)
                        question = event_data.get("question", "")

                        # user_input_request 이벤트 전송
                        user_input_event = WorkflowNodeExecutionEvent(
                            event_type="user_input_request",
                            node_id=node_id,
                            data={
                                "question": question,
                                "session_id": session_id,
                            },
                        )
                        logger.info(f"[{session_id}] 💬 이벤트 생성: user_input_request (node: {node_id})")
                        yield user_input_event

                        # 이 청크는 출력에 포함하지 않음 (내부 제어용)
                        continue

                    node_output_chunks.append(chunk)

                    # 청크 타입 분류
                    chunk_type = classify_chunk_type(chunk)

                    output_event = WorkflowNodeExecutionEvent(
                        event_type="node_output",
                        node_id=node_id,
                        data={
                            "chunk": chunk,
                            "chunk_type": chunk_type,  # "thinking", "tool", "text"
                        },
                    )
                    logger.debug(f"[{session_id}] 📝 이벤트 생성: node_output (node: {node_id}, type: {chunk_type}, chunk: {len(chunk)}자)")
                    yield output_event

                # 전체 출력에서 최종 텍스트만 추출하여 저장
                full_output = "".join(node_output_chunks)
                final_text = extract_text_from_worker_output(full_output)
                node_outputs[node_id] = final_text  # 다음 노드에는 최종 텍스트만 전달

                logger.info(
                    f"[{session_id}] 노드 출력 처리 완료: {node_id} "
                    f"(전체: {len(full_output)}자, 최종 텍스트: {len(final_text)}자)"
                )

                # Worker에서 반환된 실제 SDK 세션 ID 저장
                # SDK 세션 ID가 있을 때만 저장 (UUID 형식이어야 함)
                if worker.last_session_id:
                    self._node_sessions[node_id] = worker.last_session_id
                    self._node_agent_names[node_id] = agent_name  # agent_name도 함께 저장

                    # 세션 이력에 추가 (새 세션이거나 기존 세션 업데이트)
                    if node_id not in self._node_session_history:
                        self._node_session_history[node_id] = []

                    # 이미 존재하는 세션인지 확인
                    existing_session = next(
                        (s for s in self._node_session_history[node_id]
                         if s["session_id"] == worker.last_session_id),
                        None
                    )

                    if existing_session:
                        # 기존 세션 업데이트 (last_used_at)
                        existing_session["last_used_at"] = datetime.now().isoformat()
                    else:
                        # 새 세션 추가
                        self._node_session_history[node_id].append({
                            "session_id": worker.last_session_id,
                            "agent_name": agent_name,
                            "created_at": datetime.now().isoformat(),
                            "last_used_at": datetime.now().isoformat(),
                        })

                    logger.info(
                        f"[{session_id}] ✓ 노드 세션 저장 완료: {node_id} ({agent_name}) → "
                        f"SDK 세션 {worker.last_session_id[:8]}... "
                        f"(총 {len(self._node_sessions)}개 노드, 이력: {len(self._node_session_history.get(node_id, []))}개)"
                    )
                else:
                    logger.warning(
                        f"[{session_id}] ⚠️  노드 {node_id}: SDK 세션 ID를 받지 못함. "
                        f"추가 프롬프트 기능을 사용할 수 없습니다. "
                        f"(Response에 session_id 필드가 없거나 None)"
                    )


                elapsed_time = time.time() - start_time

                complete_event = WorkflowNodeExecutionEvent(
                    event_type="node_complete",
                    node_id=node_id,
                    data={
                        "agent_name": agent_name,
                        "output_length": len(final_text),
                    },
                    timestamp=datetime.now().isoformat(),
                    elapsed_time=elapsed_time,
                    token_usage=node_token_usage,
                )
                logger.info(f"[{session_id}] ✅ 이벤트 생성: node_complete (node: {node_id}, agent: {agent_name})")
                yield complete_event

                logger.info(
                    f"[{session_id}] 노드 완료: {node_id} ({agent_name}) "
                    f"- 출력 길이: {len(final_text)}"
                )

            except Exception as e:
                error_msg = f"노드 실행 실패: {str(e)}"
                logger.error(f"[{session_id}] {node_id}: {error_msg}", exc_info=True)

                elapsed_time = time.time() - start_time

                error_event = WorkflowNodeExecutionEvent(
                    event_type="node_error",
                    node_id=node_id,
                    data={"error": error_msg},
                    timestamp=datetime.now().isoformat(),
                    elapsed_time=elapsed_time,
                )
                logger.error(f"[{session_id}] 🔴 이벤트 생성: node_error (node: {node_id})")
                yield error_event

                raise

    async def _execute_node_and_queue_events(
        self,
        node: WorkflowNode,
        node_outputs: Dict[str, str],
        initial_input: str,
        session_id: str,
        edges: List[WorkflowEdge],
        all_nodes: List[WorkflowNode],
        event_queue: asyncio.Queue,
        project_path: Optional[str] = None,
    ) -> None:
        """
        단일 노드를 실행하고 모든 이벤트를 큐에 전송

        Args:
            node: 실행할 노드
            node_outputs: 노드 출력 딕셔너리 (공유)
            initial_input: 초기 입력
            session_id: 세션 ID
            edges: 엣지 목록
            all_nodes: 모든 노드 목록
            event_queue: 이벤트를 전송할 큐
            project_path: 프로젝트 경로
        """
        try:
            async for event in self._execute_single_node(
                node, node_outputs, initial_input, session_id,
                edges, all_nodes, project_path
            ):
                await event_queue.put(event)
        except Exception as e:
            # 에러 발생 시 에러를 큐에 전달
            logger.error(
                f"[{session_id}] 노드 {node.id} 실행 중 에러: {str(e)}",
                exc_info=True
            )
            await event_queue.put(e)  # 예외를 큐에 넣음

    async def execute_single_node_continue(
        self,
        node_id: str,
        additional_prompt: str,
        project_path: Optional[str] = None,
    ) -> AsyncIterator[WorkflowNodeExecutionEvent]:
        """
        단일 노드에 추가 프롬프트를 전송하여 대화 계속 (주도적 대화)

        Args:
            node_id: 실행할 노드 ID
            additional_prompt: 추가 프롬프트
            project_path: 프로젝트 디렉토리 경로

        Yields:
            WorkflowNodeExecutionEvent: 노드 실행 이벤트

        Raises:
            ValueError: 노드를 찾을 수 없거나 이전 세션이 없는 경우
        """
        # 디버깅: 현재 저장된 노드 세션 확인
        logger.info(
            f"[DEBUG] 추가 대화 요청: node_id={node_id}\n"
            f"[DEBUG] 저장된 노드 세션 목록: {list(self._node_sessions.keys())}\n"
            f"[DEBUG] 저장된 agent_name 목록: {list(self._node_agent_names.keys())}"
        )

        # 노드의 이전 세션 ID 확인
        previous_session_id = self._node_sessions.get(node_id)
        if not previous_session_id:
            available_nodes = ", ".join(self._node_sessions.keys()) if self._node_sessions else "(없음)"
            raise ValueError(
                f"노드 {node_id}의 이전 세션을 찾을 수 없습니다.\n"
                f"사용 가능한 노드: {available_nodes}\n"
                f"먼저 워크플로우를 실행해주세요."
            )

        # 노드의 agent_name 확인
        agent_name = self._node_agent_names.get(node_id)
        if not agent_name:
            available_agents = ", ".join(self._node_agent_names.keys()) if self._node_agent_names else "(없음)"
            raise ValueError(
                f"노드 {node_id}의 Agent 정보를 찾을 수 없습니다.\n"
                f"사용 가능한 노드: {available_agents}"
            )

        logger.info(
            f"노드 {node_id} 추가 대화 시작: {agent_name} "
            f"(이전 세션: {previous_session_id[:8]}...)"
        )

        # Agent 설정 조회
        agent_config = self._get_agent_config(agent_name)

        # node_start 이벤트
        yield WorkflowNodeExecutionEvent(
            event_type="node_start",
            node_id=node_id,
            data={
                "additional_prompt": True,
                "agent_name": agent_name,
            },
            timestamp=datetime.now().isoformat(),
        )

        # Worker 실행 (이전 세션 재개)
        try:
            worker = WorkerAgent(config=agent_config, project_dir=project_path)
            node_output_chunks = []
            node_token_usage: Optional[TokenUsage] = None

            def usage_callback(usage_info: Dict[str, Any]):
                nonlocal node_token_usage
                node_token_usage = TokenUsage(
                    input_tokens=usage_info.get("input_tokens", 0),
                    output_tokens=usage_info.get("output_tokens", 0),
                    total_tokens=usage_info.get("total_tokens", 0),
                )
                logger.debug(
                    f"💰 토큰 사용량: {node_token_usage.total_tokens} "
                    f"(입력: {node_token_usage.input_tokens}, 출력: {node_token_usage.output_tokens})"
                )

            # Worker 실행 (이전 세션 ID로 재개, user_input_callback은 None)
            async for chunk in worker.execute_task(
                additional_prompt,
                usage_callback=usage_callback,
                resume_session_id=previous_session_id,
                user_input_callback=None,  # 주도적 대화에서는 사용자 입력 요청 없음
            ):
                node_output_chunks.append(chunk)

                # 청크 타입 분류
                chunk_type = classify_chunk_type(chunk)

                output_event = WorkflowNodeExecutionEvent(
                    event_type="node_output",
                    node_id=node_id,
                    data={
                        "chunk": chunk,
                        "chunk_type": chunk_type,
                    },
                )
                logger.debug(f"📝 이벤트 생성: node_output (node: {node_id}, type: {chunk_type})")
                yield output_event

            # 전체 출력에서 최종 텍스트만 추출
            full_output = "".join(node_output_chunks)
            final_text = extract_text_from_worker_output(full_output)

            logger.info(
                f"노드 출력 처리 완료: {node_id} "
                f"(전체: {len(full_output)}자, 최종 텍스트: {len(final_text)}자)"
            )

            # Worker에서 반환된 실제 SDK 세션 ID 업데이트 (동일해야 하지만 갱신)
            if worker.last_session_id:
                self._node_sessions[node_id] = worker.last_session_id

                # 세션 이력 업데이트 (last_used_at)
                if node_id in self._node_session_history:
                    existing_session = next(
                        (s for s in self._node_session_history[node_id]
                         if s["session_id"] == worker.last_session_id),
                        None
                    )
                    if existing_session:
                        existing_session["last_used_at"] = datetime.now().isoformat()

                logger.info(
                    f"노드 세션 업데이트: {node_id} → "
                    f"SDK 세션 {worker.last_session_id[:8]}..."
                )

            # node_complete 이벤트
            complete_event = WorkflowNodeExecutionEvent(
                event_type="node_complete",
                node_id=node_id,
                data={
                    "agent_name": agent_name,
                    "output_length": len(final_text),
                },
                timestamp=datetime.now().isoformat(),
                token_usage=node_token_usage,
            )
            logger.info(f"✅ 이벤트 생성: node_complete (node: {node_id}, agent: {agent_name})")
            yield complete_event

            logger.info(
                f"노드 추가 대화 완료: {node_id} ({agent_name}) "
                f"- 출력 길이: {len(final_text)}"
            )

        except Exception as e:
            logger.error(f"노드 {node_id} 추가 대화 실패: {e}", exc_info=True)
            yield WorkflowNodeExecutionEvent(
                event_type="node_error",
                node_id=node_id,
                data={"error": str(e)},
                timestamp=datetime.now().isoformat(),
            )

    async def execute_workflow(
        self,
        workflow: Workflow,
        initial_input: str,
        session_id: str,
        project_path: Optional[str] = None,
        start_node_id: Optional[str] = None,
    ) -> AsyncIterator[WorkflowNodeExecutionEvent]:
        """
        워크플로우 실행 (스트리밍, 병렬 실행 지원)

        Args:
            workflow: 실행할 워크플로우
            initial_input: 초기 입력 데이터
            session_id: 세션 ID
            project_path: 프로젝트 디렉토리 경로 (세션별 로그 저장용)
            start_node_id: 시작 노드 ID (옵션, 지정 시 해당 Input 노드에서만 시작)

        Yields:
            WorkflowNodeExecutionEvent: 노드 실행 이벤트

        Raises:
            ValueError: 워크플로우 설정 오류
            Exception: 노드 실행 실패
        """
        # 세션별 파일 핸들러 추가
        add_session_file_handlers(session_id, project_path)

        # 세션별 Condition 노드 반복 횟수 초기화
        self._condition_iterations[session_id] = {}

        # 세션별 사용자 입력 Queue 생성 (Human-in-the-Loop)
        user_input_queue = asyncio.Queue()
        self.user_input_queues[session_id] = user_input_queue
        logger.info(f"[{session_id}] 사용자 입력 Queue 생성 (Human-in-the-Loop 지원)")

        # 실행 중인 병렬 태스크 추적 (취소 시 정리용)
        running_tasks: List[asyncio.Task] = []

        try:
            logger.info(
                f"[{session_id}] 워크플로우 실행 시작: {workflow.name} "
                f"(노드: {len(workflow.nodes)}, 엣지: {len(workflow.edges)})"
            )

            # 위상 정렬
            try:
                sorted_nodes = self._topological_sort(workflow.nodes, workflow.edges, start_node_id)
            except ValueError as e:
                logger.error(f"[{session_id}] 워크플로우 정렬 실패: {e}")
                raise

            logger.info(
                f"[{session_id}] 실행 순서: "
                f"{[node.id for node in sorted_nodes]}"
            )

            # 실행 그룹 계산 (병렬 실행 그룹 포함)
            execution_groups = self._compute_execution_groups(sorted_nodes, workflow.edges)

            logger.info(
                f"[{session_id}] 실행 그룹: {len(execution_groups)}개 "
                f"(병렬 그룹: {sum(1 for g in execution_groups if len(g) > 1)}개)"
            )

            # 노드 출력 저장 (노드 ID → 출력)
            node_outputs: Dict[str, str] = {}

            # 실행 그룹별로 처리 (병렬 실행 지원)
            for group_idx, group in enumerate(execution_groups):
                group_node_ids = [node.id for node in group]

                if len(group) == 1:
                    # 단독 실행
                    node = group[0]
                    logger.info(
                        f"[{session_id}] 그룹 {group_idx + 1}/{len(execution_groups)}: "
                        f"노드 {node.id} 단독 실행"
                    )

                    async for event in self._execute_single_node(
                        node, node_outputs, initial_input, session_id,
                        workflow.edges, workflow.nodes, project_path
                    ):
                        yield event

                else:
                    # 병렬 실행 (실시간 이벤트 스트리밍)
                    logger.info(
                        f"[{session_id}] 그룹 {group_idx + 1}/{len(execution_groups)}: "
                        f"{len(group)}개 노드 병렬 실행 ({group_node_ids})"
                    )

                    # 이벤트 큐 생성
                    event_queue: asyncio.Queue = asyncio.Queue()

                    # 병렬 실행 태스크 생성
                    tasks = [
                        asyncio.create_task(
                            self._execute_node_and_queue_events(
                                node, node_outputs, initial_input, session_id,
                                workflow.edges, workflow.nodes, event_queue, project_path
                            )
                        )
                        for node in group
                    ]

                    # 실행 중인 태스크 추적에 추가
                    running_tasks.extend(tasks)

                    # 완료된 노드 수 추적
                    completed_nodes = 0
                    total_nodes = len(group)

                    # 실시간으로 이벤트를 스트리밍
                    while completed_nodes < total_nodes:
                        # 큐에서 이벤트 가져오기 (타임아웃 1초)
                        try:
                            event_or_exception = await asyncio.wait_for(
                                event_queue.get(), timeout=1.0
                            )

                            # 예외인 경우
                            if isinstance(event_or_exception, Exception):
                                error_msg = f"병렬 실행 중 노드 실패: {str(event_or_exception)}"
                                logger.error(f"[{session_id}] {error_msg}", exc_info=event_or_exception)

                                # 에러 이벤트 생성
                                yield WorkflowNodeExecutionEvent(
                                    event_type="node_error",
                                    node_id="unknown",
                                    data={"error": error_msg},
                                    timestamp=datetime.now().isoformat(),
                                )

                                # 모든 태스크 취소
                                for task in tasks:
                                    task.cancel()

                                raise event_or_exception

                            # 정상 이벤트인 경우
                            event = event_or_exception
                            yield event

                            # 노드 완료/에러 이벤트 카운팅
                            if event.event_type in ["node_complete", "node_error"]:
                                completed_nodes += 1
                                logger.info(
                                    f"[{session_id}] 병렬 노드 완료: {event.node_id} "
                                    f"({completed_nodes}/{total_nodes})"
                                )

                        except asyncio.TimeoutError:
                            # 타임아웃 시 태스크 상태 확인
                            done_tasks = [t for t in tasks if t.done()]
                            if done_tasks:
                                # 완료된 태스크가 있으면 다시 시도
                                continue
                            else:
                                # 모든 태스크가 아직 실행 중
                                continue

                    # 모든 태스크 완료 대기 (정리 작업)
                    await asyncio.gather(*tasks, return_exceptions=True)

                    logger.info(
                        f"[{session_id}] 병렬 그룹 완료: {group_node_ids}"
                    )

            logger.info(f"[{session_id}] 워크플로우 실행 완료: {workflow.name}")

            # 워크플로우 완료 이벤트
            workflow_complete_event = WorkflowNodeExecutionEvent(
                event_type="workflow_complete",
                node_id="",
                data={"message": "워크플로우 실행 완료"},
                timestamp=datetime.now().isoformat(),
            )
            logger.info(f"[{session_id}] 🎉 이벤트 생성: workflow_complete")
            yield workflow_complete_event

        except asyncio.CancelledError:
            # 워크플로우 취소 요청 시
            logger.warning(
                f"[{session_id}] 워크플로우 취소 요청 받음. "
                f"실행 중인 태스크 {len(running_tasks)}개 정리 중..."
            )

            # 모든 실행 중인 병렬 태스크 취소
            for task in running_tasks:
                if not task.done():
                    task.cancel()

            # 취소된 태스크 대기 (정리)
            if running_tasks:
                await asyncio.gather(*running_tasks, return_exceptions=True)

            logger.info(f"[{session_id}] 모든 태스크 정리 완료")

            # 취소 이벤트 생성
            cancel_event = WorkflowNodeExecutionEvent(
                event_type="workflow_cancelled",
                node_id="",
                data={"message": "워크플로우가 취소되었습니다"},
                timestamp=datetime.now().isoformat(),
            )
            yield cancel_event

            # CancelledError 재발생 (상위 호출자에게 전파)
            raise

        finally:
            # 취소 플래그 제거 (메모리 누수 방지)
            self.cancelled_sessions.discard(session_id)

            # 세션별 파일 핸들러 제거 (메모리 누수 방지)
            remove_session_file_handlers(session_id)

            # 사용자 입력 Queue 정리
            if session_id in self.user_input_queues:
                del self.user_input_queues[session_id]
                logger.info(f"[{session_id}] 사용자 입력 Queue 정리 완료")
