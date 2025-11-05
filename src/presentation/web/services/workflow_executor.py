"""
워크플로우 실행 엔진

워크플로우의 노드를 순차적으로 실행하고, 노드 간 데이터 전달을 관리합니다.
"""

import asyncio
from datetime import datetime
from typing import Dict, Any, AsyncIterator, List, Optional, Set
from pathlib import Path

from src.domain.models import AgentConfig
from src.infrastructure.config import JsonConfigLoader
from src.infrastructure.storage.custom_worker_repository import CustomWorkerRepository
from src.infrastructure.logging import (
    get_logger,
    add_session_file_handlers,
    remove_session_file_handlers,
)
from src.presentation.web.schemas.workflow import (
    Workflow,
    WorkflowEdge,
    WorkflowNodeExecutionEvent,
)
from src.presentation.web.services.workflow_graph_manager import WorkflowGraphManager
from src.presentation.web.services.workflow_template_renderer import WorkflowTemplateRenderer
from src.presentation.web.services.workflow_condition_evaluator import WorkflowConditionEvaluator
from src.presentation.web.services.workflow_node_executor import WorkflowNodeExecutor

logger = get_logger(__name__)


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
                logger.info(f"커스텀 워커 로드 완료: {len(custom_workers)}개 " f"(프로젝트: {project_path})")
            except Exception as e:
                logger.warning(f"커스텀 워커 로드 실패 (프로젝트: {project_path}): {e}", exc_info=True)

        self.agent_config_map = {config.name: config for config in self.agent_configs}

        # 컴포넌트 초기화
        self.template_renderer = WorkflowTemplateRenderer()
        self.condition_evaluator = WorkflowConditionEvaluator(self._condition_iterations)
        self.node_executor = WorkflowNodeExecutor(
            config_loader=self.config_loader,
            agent_config_map=self.agent_config_map,
            custom_worker_names=self.custom_worker_names,
            project_path=self.project_path,
            node_sessions=self._node_sessions,
            node_session_history=self._node_session_history,
            node_agent_names=self._node_agent_names,
            user_input_queues=self.user_input_queues,
            cancelled_sessions=self.cancelled_sessions,
        )

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
                f"Agent '{agent_name}'를 찾을 수 없습니다.\n" f"사용 가능한 Agent: {', '.join(available_agents)}"
            )

            # 커스텀 워커인 경우 추가 안내
            if agent_name not in self.custom_worker_names:
                error_msg += "\n\n힌트: 기본 제공 Worker가 아닙니다. " "커스텀 워커인 경우 프로젝트 경로를 확인하세요."
            else:
                error_msg += (
                    f"\n\n힌트: 커스텀 워커 '{agent_name}'가 로드되지 않았습니다. " f"프로젝트 경로: {self.project_path}"
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

    @staticmethod
    def _get_parent_nodes(node_id: str, edges: List[WorkflowEdge]) -> List[str]:
        """
        노드의 부모 노드 ID 목록 조회 (헬퍼 메서드)

        Args:
            node_id: 노드 ID
            edges: 엣지 목록

        Returns:
            List[str]: 부모 노드 ID 목록
        """
        return [edge.source for edge in edges if edge.target == node_id]

    def _find_start_node(
        self,
        workflow: Workflow,
        start_node_id: Optional[str] = None,
        allow_non_input: bool = False,
    ) -> str:
        """
        워크플로우의 시작 노드 찾기

        Args:
            workflow: 워크플로우 객체
            start_node_id: 지정된 시작 노드 ID (옵션)
            allow_non_input: Input 노드가 아닌 노드도 허용 (재시작 시 True)

        Returns:
            str: 시작 노드 ID

        Raises:
            ValueError: 시작 노드를 찾을 수 없는 경우
        """
        if start_node_id:
            # 지정된 시작 노드 확인
            start_node = next((n for n in workflow.nodes if n.id == start_node_id), None)
            if not start_node:
                raise ValueError(f"지정된 시작 노드를 찾을 수 없습니다: {start_node_id}")

            # 재시작 모드가 아니면 Input 노드만 허용
            if not allow_non_input and start_node.type != "input":
                raise ValueError(
                    f"시작 노드는 Input 노드여야 합니다: {start_node_id} (타입: {start_node.type})"
                )
            return start_node_id

        # Input 노드 찾기
        input_nodes = [node for node in workflow.nodes if node.type == "input"]
        if not input_nodes:
            raise ValueError("워크플로우에 Input 노드가 없습니다. Input 노드에서 시작해야 합니다.")

        # 첫 번째 Input 노드 사용
        return input_nodes[0].id

    def _can_execute_merge_node(
        self,
        node_id: str,
        executed_nodes: Set[str],
        graph_manager: WorkflowGraphManager,
    ) -> bool:
        """
        Merge 노드 실행 가능 여부 확인 (모든 부모 노드 완료 확인)

        Args:
            node_id: Merge 노드 ID
            executed_nodes: 이미 실행된 노드 ID 집합
            graph_manager: 그래프 관리자

        Returns:
            bool: 실행 가능 여부 (모든 부모 노드가 완료되었으면 True)
        """
        parent_nodes = graph_manager.get_parent_nodes(node_id)
        return all(parent_id in executed_nodes for parent_id in parent_nodes)

    async def _execute_nodes_in_parallel(
        self,
        node_ids: List[str],
        node_map: Dict[str, Any],
        node_outputs: Dict[str, str],
        node_inputs: Dict[str, str],
        initial_input: str,
        session_id: str,
        edges: List[WorkflowEdge],
        all_nodes: List[Any],
        project_path: Optional[str],
    ) -> AsyncIterator[WorkflowNodeExecutionEvent]:
        """
        여러 노드를 병렬로 실행하고 이벤트를 스트리밍

        Args:
            node_ids: 병렬 실행할 노드 ID 목록
            node_map: 노드 ID -> 노드 객체 매핑
            node_outputs: 노드 출력 저장소
            node_inputs: 노드 입력 저장소
            initial_input: 초기 입력
            session_id: 세션 ID
            edges: 워크플로우 엣지 목록
            all_nodes: 모든 노드 목록
            project_path: 프로젝트 경로

        Yields:
            WorkflowNodeExecutionEvent: 각 노드의 실행 이벤트
        """
        event_queue = asyncio.Queue()
        completed_nodes = set()

        async def execute_node_task(node_id: str):
            """단일 노드 실행 태스크"""
            try:
                node = node_map.get(node_id)
                if not node:
                    logger.error(f"[{session_id}] 병렬 실행: 노드를 찾을 수 없음: {node_id}")
                    return

                async for event in self.node_executor.execute_single_node(
                    node=node,
                    node_outputs=node_outputs,
                    node_inputs=node_inputs,
                    initial_input=initial_input,
                    session_id=session_id,
                    edges=edges,
                    all_nodes=all_nodes,
                    condition_evaluator=self.condition_evaluator,
                    template_renderer=self.template_renderer,
                    project_path=project_path,
                ):
                    await event_queue.put(event)

                completed_nodes.add(node_id)
                logger.info(f"[{session_id}] ✓ 병렬 노드 완료: {node_id}")

            except Exception as e:
                logger.error(
                    f"[{session_id}] ✗ 병렬 노드 실행 실패: {node_id} - {e}",
                    exc_info=True,
                )
                # 에러 이벤트 전송
                error_event = WorkflowNodeExecutionEvent(
                    event_type="node_error",
                    node_id=node_id,
                    data={"error": str(e)},
                    timestamp=datetime.now().isoformat(),
                )
                await event_queue.put(error_event)
                completed_nodes.add(node_id)  # 에러여도 완료로 표시

        # 모든 노드 병렬 실행
        logger.info(f"[{session_id}] 🔀 병렬 실행 시작: {node_ids} ({len(node_ids)}개 노드)")
        tasks = [asyncio.create_task(execute_node_task(nid)) for nid in node_ids]

        # 이벤트 스트리밍 (모든 노드가 완료될 때까지)
        while len(completed_nodes) < len(node_ids):
            try:
                # 0.1초 타임아웃으로 이벤트 대기
                event = await asyncio.wait_for(event_queue.get(), timeout=0.1)
                yield event
            except asyncio.TimeoutError:
                # 취소 확인
                self._check_cancellation(session_id)
                continue

        # 남은 이벤트 모두 처리
        while not event_queue.empty():
            event = await event_queue.get()
            yield event

        # 모든 태스크 완료 대기 (예외 발생 시 전파)
        await asyncio.gather(*tasks)

        logger.info(
            f"[{session_id}] ✅ 병렬 실행 완료: {node_ids} "
            f"({len(completed_nodes)}/{len(node_ids)} 성공)"
        )

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
        # WorkflowNodeExecutor에 위임
        async for event in self.node_executor.execute_single_node_continue(
            node_id=node_id,
            additional_prompt=additional_prompt,
            project_path=project_path,
        ):
            yield event

    async def execute_workflow(
        self,
        workflow: Workflow,
        initial_input: str,
        session_id: str,
        project_path: Optional[str] = None,
        start_node_id: Optional[str] = None,
        restore_node_outputs: Optional[Dict[str, str]] = None,
        restore_node_inputs: Optional[Dict[str, str]] = None,
        restore_executed_nodes: Optional[Set[str]] = None,
    ) -> AsyncIterator[WorkflowNodeExecutionEvent]:
        """
        워크플로우 실행 (동적 노드 선택, Condition 분기 지원)

        **v4.1.0 변경사항**: 위상 정렬 대신 동적 노드 선택 방식으로 전환
        - Condition 노드의 next_node_id를 정확히 반영
        - Merge 노드의 대기 로직 개선
        - 중복 실행 방지 (executed_nodes Set)

        **v4.2.0 변경사항**: 워크플로우 재시작 지원
        - restore_node_outputs, restore_node_inputs로 이전 실행 상태 복원
        - start_node_id와 함께 사용하여 특정 노드부터 재시작

        Args:
            workflow: 실행할 워크플로우
            initial_input: 초기 입력 데이터
            session_id: 세션 ID
            project_path: 프로젝트 디렉토리 경로 (세션별 로그 저장용)
            start_node_id: 시작 노드 ID (옵션, 지정 시 해당 노드에서 시작)
            restore_node_outputs: 복원할 노드 출력 (재시작 시)
            restore_node_inputs: 복원할 노드 입력 (재시작 시)
            restore_executed_nodes: 복원할 실행 완료 노드 목록 (재시작 시)

        Yields:
            WorkflowNodeExecutionEvent: 노드 실행 이벤트

        Raises:
            ValueError: 워크플로우 설정 오류
            Exception: 노드 실행 실패
        """
        # 세션별 파일 핸들러 추가
        # project_path가 None이면 self.project_path 사용
        add_session_file_handlers(session_id, project_path or self.project_path)

        # 세션별 Condition 노드 반복 횟수 초기화
        self._condition_iterations[session_id] = {}

        # 세션별 사용자 입력 Queue 생성 (Human-in-the-Loop)
        user_input_queue = asyncio.Queue()
        self.user_input_queues[session_id] = user_input_queue
        logger.info(f"[{session_id}] 사용자 입력 Queue 생성 (Human-in-the-Loop 지원)")

        try:
            # 재시작 모드 확인
            is_restart = restore_node_outputs is not None or restore_node_inputs is not None
            restart_info = f" (재시작: {start_node_id})" if is_restart else ""

            logger.info(
                f"[{session_id}] 워크플로우 실행 시작 (동적 실행): {workflow.name}{restart_info} "
                f"(노드: {len(workflow.nodes)}, 엣지: {len(workflow.edges)})"
            )

            # WorkflowGraphManager 생성
            graph_manager = WorkflowGraphManager(workflow.nodes, workflow.edges)

            # 노드 맵 생성 (빠른 조회)
            node_map = {node.id: node for node in workflow.nodes}

            # 시작 노드 찾기 (재시작 시 allow_non_input=True)
            current_node_id = self._find_start_node(
                workflow, start_node_id, allow_non_input=is_restart
            )
            logger.info(f"[{session_id}] 시작 노드: {current_node_id}")

            # 실행 추적 (재시작 시 이전 상태 복원)
            executed_nodes: Set[str] = restore_executed_nodes.copy() if restore_executed_nodes else set()
            pending_merge_nodes: Set[str] = set()
            node_outputs: Dict[str, str] = restore_node_outputs.copy() if restore_node_outputs else {}
            node_inputs: Dict[str, str] = restore_node_inputs.copy() if restore_node_inputs else {}

            # 재시작 시 복원 정보 로깅
            if is_restart:
                logger.info(
                    f"[{session_id}] 이전 상태 복원 완료 - "
                    f"실행 완료 노드: {len(executed_nodes)}개, "
                    f"노드 출력: {len(node_outputs)}개, "
                    f"노드 입력: {len(node_inputs)}개"
                )
                # 재시작 노드를 executed_nodes에서 제거 (다시 실행하기 위해)
                if start_node_id and start_node_id in executed_nodes:
                    executed_nodes.remove(start_node_id)
                    logger.info(f"[{session_id}] 재시작 노드를 실행 목록에서 제거: {start_node_id}")

            max_iterations = len(workflow.nodes) * 10  # 무한 루프 방지
            iteration_count = 0

            # === 동적 노드 실행 루프 ===
            while current_node_id or pending_merge_nodes:
                iteration_count += 1
                if iteration_count > max_iterations:
                    raise ValueError(
                        f"워크플로우 실행 중 무한 루프 감지 (반복: {iteration_count}회). "
                        f"현재 노드: {current_node_id}, Pending: {pending_merge_nodes}"
                    )

                # 취소 확인
                self._check_cancellation(session_id)

                # === 현재 노드 실행 ===
                if current_node_id:
                    # 노드 조회
                    node = node_map.get(current_node_id)
                    if not node:
                        raise ValueError(f"노드를 찾을 수 없습니다: {current_node_id}")

                    # 중복 실행 방지 (Condition 노드는 피드백 루프를 위해 재실행 허용)
                    if current_node_id in executed_nodes:
                        if node.type == "condition":
                            logger.info(
                                f"[{session_id}] Condition 노드 재실행 허용: {current_node_id} "
                                f"(피드백 루프)"
                            )
                            executed_nodes.remove(current_node_id)
                        else:
                            logger.warning(
                                f"[{session_id}] 노드 중복 실행 방지: {current_node_id}"
                            )
                            current_node_id = None
                            continue

                    logger.info(
                        f"[{session_id}] 노드 실행: {current_node_id} "
                        f"(타입: {node.type}, 반복: {iteration_count})"
                    )

                    # 노드 실행 및 next_node_id 추출
                    next_node_id = None
                    async for event in self.node_executor.execute_single_node(
                        node=node,
                        node_outputs=node_outputs,
                        node_inputs=node_inputs,
                        initial_input=initial_input,
                        session_id=session_id,
                        edges=workflow.edges,
                        all_nodes=workflow.nodes,
                        condition_evaluator=self.condition_evaluator,
                        template_renderer=self.template_renderer,
                        project_path=project_path,
                    ):
                        yield event

                        # Condition 노드의 경우 next_node_id 추출
                        if (
                            event.event_type == "node_complete"
                            and node.type == "condition"
                        ):
                            next_node_id = event.data.get("next_node")
                            logger.info(
                                f"[{session_id}] Condition 분기: {current_node_id} → {next_node_id}"
                            )

                    # 실행 완료 표시
                    executed_nodes.add(current_node_id)

                    # === 다음 노드 결정 ===
                    if next_node_id:
                        # Case 1: Condition 노드가 지정한 경로 (피드백 루프 허용)
                        # Condition 분기는 이전에 실행된 노드로도 돌아갈 수 있음

                        # Condition의 출력(= 부모 출력)을 다음 노드의 입력으로 설정
                        condition_output = node_outputs.get(current_node_id, "")
                        node_inputs[next_node_id] = condition_output
                        logger.info(
                            f"[{session_id}] Condition 출력을 다음 노드 입력으로 설정: "
                            f"{next_node_id} ← {len(condition_output)}자"
                        )

                        if next_node_id in executed_nodes:
                            logger.info(
                                f"[{session_id}] 피드백 루프: {current_node_id} → {next_node_id} "
                                f"(이미 실행된 노드로 재진입)"
                            )
                            # executed_nodes에서 제거하여 재실행 가능하게 함
                            executed_nodes.remove(next_node_id)
                        current_node_id = next_node_id
                        logger.info(f"[{session_id}] 다음 노드 (Condition): {next_node_id}")

                    else:
                        # Case 2: 일반 노드 → 자식 노드로
                        children = graph_manager.get_child_nodes(current_node_id)

                        if len(children) == 0:
                            # 자식 없음: 종료
                            current_node_id = None
                            logger.info(f"[{session_id}] 자식 노드 없음, 종료 대기")

                        elif len(children) == 1:
                            # 단일 자식
                            child_id = children[0]
                            child_node = node_map.get(child_id)

                            if child_node and child_node.type == "merge":
                                # Merge 노드: 모든 부모 완료 확인
                                if self._can_execute_merge_node(
                                    child_id, executed_nodes, graph_manager
                                ):
                                    # 모든 부모 완료: 즉시 실행
                                    # Merge 노드는 여러 부모의 출력을 병합하므로 node_inputs 설정 안 함
                                    current_node_id = child_id
                                    logger.info(
                                        f"[{session_id}] Merge 노드 준비 완료: {child_id}"
                                    )
                                else:
                                    # 아직 미완료 부모가 있으면 대기
                                    pending_merge_nodes.add(child_id)
                                    current_node_id = None
                                    logger.info(
                                        f"[{session_id}] Merge 노드 대기 등록: {child_id}"
                                    )
                            else:
                                # 일반 노드: 즉시 실행
                                # 현재 노드의 출력을 자식 노드의 입력으로 설정
                                parent_output = node_outputs.get(current_node_id, "")
                                node_inputs[child_id] = parent_output
                                current_node_id = child_id
                                logger.info(f"[{session_id}] 다음 노드 (단일): {child_id}")

                        else:
                            # 여러 자식: 병렬 실행
                            logger.info(
                                f"[{session_id}] 여러 자식 노드 발견, 병렬 실행: {children}"
                            )

                            # 모든 자식에 부모 출력 전달
                            parent_output = node_outputs.get(current_node_id, "")
                            for child_id in children:
                                node_inputs[child_id] = parent_output

                            # 병렬 실행
                            async for event in self._execute_nodes_in_parallel(
                                node_ids=children,
                                node_map=node_map,
                                node_outputs=node_outputs,
                                node_inputs=node_inputs,
                                initial_input=initial_input,
                                session_id=session_id,
                                edges=workflow.edges,
                                all_nodes=workflow.nodes,
                                project_path=project_path,
                            ):
                                yield event

                            # 모든 자식 완료 표시
                            executed_nodes.update(children)

                            # 다음 노드 결정: 자식들의 자식 노드들 수집
                            next_candidates = set()
                            for child_id in children:
                                child_children = graph_manager.get_child_nodes(child_id)
                                next_candidates.update(child_children)

                            if not next_candidates:
                                # 더 이상 진행할 노드 없음
                                current_node_id = None
                                logger.info(
                                    f"[{session_id}] 병렬 실행 후 자식 노드 없음, 종료 대기"
                                )
                            else:
                                # Merge 노드와 일반 노드 분류
                                merge_nodes = [
                                    nid
                                    for nid in next_candidates
                                    if node_map.get(nid) and node_map.get(nid).type == "merge"
                                ]
                                regular_nodes = [
                                    nid for nid in next_candidates if nid not in merge_nodes
                                ]

                                if merge_nodes:
                                    # Merge 노드가 있으면 실행 가능 여부 확인
                                    merge_ready = False
                                    for merge_id in merge_nodes:
                                        if self._can_execute_merge_node(
                                            merge_id, executed_nodes, graph_manager
                                        ):
                                            # Merge 노드 실행 가능
                                            # Merge 노드는 여러 부모의 출력을 병합하므로
                                            # node_inputs 설정하지 않음
                                            current_node_id = merge_id
                                            merge_ready = True
                                            logger.info(
                                                f"[{session_id}] 병렬 실행 후 Merge 노드 "
                                                f"준비 완료: {merge_id}"
                                            )
                                            break
                                        else:
                                            # 아직 미완료 부모가 있으면 대기
                                            pending_merge_nodes.add(merge_id)
                                            logger.info(
                                                f"[{session_id}] 병렬 실행 후 Merge 노드 "
                                                f"대기 등록: {merge_id}"
                                            )

                                    if not merge_ready:
                                        # Merge 노드가 준비되지 않았으면 일반 노드로 진행
                                        if regular_nodes:
                                            next_node = regular_nodes[0]
                                            # 병렬 실행된 자식 중 하나의 출력을 전달
                                            # (일반적으로 병렬 후 Merge로 가야 하지만,
                                            # 예외적인 경우 처리)
                                            current_node_id = next_node
                                            logger.info(
                                                f"[{session_id}] 병렬 실행 후 일반 노드로 "
                                                f"진행: {next_node}"
                                            )
                                        else:
                                            current_node_id = None

                                elif regular_nodes:
                                    # Merge 노드 없이 일반 노드만 있으면 첫 번째 선택
                                    next_node = regular_nodes[0]
                                    # 병렬 실행된 자식 중 하나의 출력을 전달
                                    # (병렬 후 단일 노드로 진행하는 것은 비정상적이지만 처리)
                                    current_node_id = next_node
                                    if len(regular_nodes) > 1:
                                        logger.warning(
                                            f"[{session_id}] 병렬 실행 후 여러 일반 노드 발견, "
                                            f"첫 번째 선택: {next_node} (전체: {regular_nodes})"
                                        )
                                    else:
                                        logger.info(
                                            f"[{session_id}] 병렬 실행 후 단일 노드로 "
                                            f"진행: {next_node}"
                                        )
                                else:
                                    current_node_id = None

                # === Pending Merge 노드 확인 ===
                if not current_node_id and pending_merge_nodes:
                    for pending_id in list(pending_merge_nodes):
                        if self._can_execute_merge_node(
                            pending_id, executed_nodes, graph_manager
                        ):
                            # 모든 부모 완료: 실행
                            current_node_id = pending_id
                            pending_merge_nodes.remove(pending_id)
                            logger.info(
                                f"[{session_id}] Pending Merge 노드 실행: {pending_id}"
                            )
                            break

                # === 종료 조건 ===
                if not current_node_id and not pending_merge_nodes:
                    logger.info(f"[{session_id}] 모든 노드 실행 완료")
                    break

            logger.info(
                f"[{session_id}] 워크플로우 실행 완료: {workflow.name} "
                f"(실행 노드: {len(executed_nodes)}/{len(workflow.nodes)})"
            )

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
            logger.warning(f"[{session_id}] 워크플로우 취소 요청 받음")

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
