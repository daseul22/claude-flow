"""
워크플로우 노드 실행기

개별 노드를 실행하고, 노드 출력을 관리합니다.
"""

import asyncio
import time
from datetime import datetime
from typing import Dict, Any, AsyncIterator, List, Optional, Set

from src.domain.models import AgentConfig
from src.infrastructure.config import JsonConfigLoader
from src.infrastructure.claude.worker_client import WorkerAgent
from src.infrastructure.logging import get_logger
from src.presentation.web.schemas.workflow import (
    WorkflowNode,
    WorkflowEdge,
    WorkflowNodeExecutionEvent,
    WorkerNodeData,
    InputNodeData,
    TokenUsage,
)
from src.presentation.web.services.workflow_utils import (
    extract_text_from_worker_output,
    classify_chunk_type,
)

logger = get_logger(__name__)


class WorkflowNodeExecutor:
    """
    워크플로우 노드 실행기

    개별 노드의 실행 로직을 담당하며, 모든 노드 타입(Input, Worker, Condition, Merge)을
    실행할 수 있습니다.

    Attributes:
        config_loader: Agent 설정 로더
        agent_config_map: Agent 설정 매핑 (이름 → 설정)
        custom_worker_names: 커스텀 워커 이름 집합
        project_path: 프로젝트 경로
        node_sessions: 노드 세션 매핑 (참조)
        node_session_history: 노드 세션 이력 (참조)
        node_agent_names: 노드 에이전트 이름 매핑 (참조)
        user_input_queues: 사용자 입력 Queue (참조)
        cancelled_sessions: 취소된 세션 집합 (참조)
    """

    def __init__(
        self,
        config_loader: JsonConfigLoader,
        agent_config_map: Dict[str, AgentConfig],
        custom_worker_names: Set[str],
        project_path: Optional[str],
        node_sessions: Dict[str, str],
        node_session_history: Dict[str, List[Dict[str, Any]]],
        node_agent_names: Dict[str, str],
        user_input_queues: Dict[str, asyncio.Queue],
        cancelled_sessions: Set[str],
    ):
        """
        WorkflowNodeExecutor 초기화

        Args:
            config_loader: Agent 설정 로더
            agent_config_map: Agent 설정 매핑
            custom_worker_names: 커스텀 워커 이름 집합
            project_path: 프로젝트 경로
            node_sessions: 노드 세션 매핑 (참조)
            node_session_history: 노드 세션 이력 (참조)
            node_agent_names: 노드 에이전트 이름 매핑 (참조)
            user_input_queues: 사용자 입력 Queue (참조)
            cancelled_sessions: 취소된 세션 집합 (참조)
        """
        self.config_loader = config_loader
        self.agent_config_map = agent_config_map
        self.custom_worker_names = custom_worker_names
        self.project_path = project_path

        # 참조로 받은 상태 (WorkflowExecutor가 소유)
        self.node_sessions = node_sessions
        self.node_session_history = node_session_history
        self.node_agent_names = node_agent_names
        self.user_input_queues = user_input_queues
        self.cancelled_sessions = cancelled_sessions

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
            available_agents = list(self.agent_config_map.keys())
            error_msg = (
                f"Agent '{agent_name}'를 찾을 수 없습니다.\n" f"사용 가능한 Agent: {', '.join(available_agents)}"
            )

            if agent_name not in self.custom_worker_names:
                error_msg += "\n\n힌트: 기본 제공 Worker가 아닙니다. " "커스텀 워커인 경우 프로젝트 경로를 확인하세요."
            else:
                error_msg += (
                    f"\n\n힌트: 커스텀 워커 '{agent_name}'가 로드되지 않았습니다. " f"프로젝트 경로: {self.project_path}"
                )

            logger.error(error_msg)
            raise ValueError(error_msg)
        return config

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

    def _extract_final_output(self, full_output: str) -> str:
        """
        전체 출력에서 최종 표준 출력 추출 (TextBlock만)

        이 메서드는 extract_text_from_worker_output을 래핑합니다.

        Args:
            full_output: 전체 출력 (모든 chunk 결합)

        Returns:
            str: 최종 표준 출력 (TextBlock만)
        """
        return extract_text_from_worker_output(full_output)

    def _parse_worker_node_data(
        self, node: WorkflowNode, session_id: str
    ) -> tuple[str, str, Optional[List[str]], Optional[str]]:
        """
        Worker 노드 데이터 파싱

        Args:
            node: 워크플로우 노드
            session_id: 세션 ID

        Returns:
            tuple: (agent_name, task_template, allowed_tools_override, thinking_override)

        Raises:
            ValueError: 필수 필드가 누락된 경우
        """
        node_id = node.id

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
            node_data: WorkerNodeData = node.data
            agent_name = node_data.agent_name
            task_template = node_data.task_template
            allowed_tools_override = node_data.allowed_tools
            thinking_override = node_data.thinking

        return agent_name, task_template, allowed_tools_override, thinking_override

    def _prepare_worker_agent_config(
        self,
        agent_name: str,
        allowed_tools_override: Optional[List[str]],
        thinking_override: Optional[str],
        node_id: str,
        session_id: str,
    ) -> AgentConfig:
        """
        Worker Agent 설정 준비

        Args:
            agent_name: Agent 이름
            allowed_tools_override: 도구 오버라이드
            thinking_override: Thinking 모드 오버라이드
            node_id: 노드 ID
            session_id: 세션 ID

        Returns:
            AgentConfig: 준비된 Agent 설정
        """
        from dataclasses import replace

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
                f"[{session_id}] 노드 {node_id}: thinking 모드 오버라이드 (thinking={thinking_override})"
            )

        return agent_config

    def _render_worker_task(
        self,
        task_template: str,
        node_id: str,
        node_outputs: Dict[str, str],
        initial_input: str,
        edges: List[WorkflowEdge],
        template_renderer: Any,
    ) -> str:
        """
        Worker 작업 템플릿 렌더링

        Args:
            task_template: 작업 템플릿
            node_id: 노드 ID
            node_outputs: 노드 출력 매핑
            initial_input: 초기 입력
            edges: 엣지 목록
            template_renderer: 템플릿 렌더러

        Returns:
            str: 렌더링된 작업 설명
        """
        parent_nodes = self._get_parent_nodes(node_id, edges)
        parent_outputs = {pid: node_outputs[pid] for pid in parent_nodes if pid in node_outputs}

        return template_renderer.render_task_template(
            template=task_template,
            node_id=node_id,
            node_outputs=parent_outputs,
            initial_input=initial_input,
        )

    def _save_worker_node_session(
        self, node_id: str, agent_name: str, worker_session_id: str, session_id: str
    ) -> None:
        """
        Worker 노드의 SDK 세션 저장

        Args:
            node_id: 노드 ID
            agent_name: Agent 이름
            worker_session_id: Worker SDK 세션 ID
            session_id: 워크플로우 세션 ID
        """
        self.node_sessions[node_id] = worker_session_id
        self.node_agent_names[node_id] = agent_name

        if node_id not in self.node_session_history:
            self.node_session_history[node_id] = []

        existing_session = next(
            (s for s in self.node_session_history[node_id] if s["session_id"] == worker_session_id),
            None,
        )

        if existing_session:
            existing_session["last_used_at"] = datetime.now().isoformat()
        else:
            self.node_session_history[node_id].append(
                {
                    "session_id": worker_session_id,
                    "agent_name": agent_name,
                    "created_at": datetime.now().isoformat(),
                    "last_used_at": datetime.now().isoformat(),
                }
            )

        logger.info(
            f"[{session_id}] ✓ 노드 세션 저장 완료: {node_id} ({agent_name}) → "
            f"SDK 세션 {worker_session_id[:8]}... "
            f"(총 {len(self.node_sessions)}개 노드, "
            f"이력: {len(self.node_session_history.get(node_id, []))}개)"
        )

    async def execute_single_node(
        self,
        node: WorkflowNode,
        node_outputs: Dict[str, str],
        initial_input: str,
        session_id: str,
        edges: List[WorkflowEdge],
        all_nodes: List[WorkflowNode],
        condition_evaluator: Any,  # WorkflowConditionEvaluator (circular import 방지)
        template_renderer: Any,  # WorkflowTemplateRenderer (circular import 방지)
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
            condition_evaluator: 조건 평가기 인스턴스
            template_renderer: 템플릿 렌더러 인스턴스
            project_path: 프로젝트 디렉토리 경로

        Yields:
            WorkflowNodeExecutionEvent: 노드 실행 이벤트
        """

        # 취소 플래그 체크 (각 노드 실행 전)
        self._check_cancellation(session_id)

        # Input 노드 처리
        if node.type == "input":
            async for event in self._execute_input_node(
                node, node_outputs, initial_input, session_id
            ):
                yield event
            return

        # Condition 노드
        elif node.type == "condition":
            async for event in self._execute_condition_node_wrapper(
                node, node_outputs, edges, session_id, condition_evaluator
            ):
                yield event
            return

        # Merge 노드
        elif node.type == "merge":
            async for event in self._execute_merge_node_wrapper(
                node, node_outputs, edges, session_id, condition_evaluator
            ):
                yield event
            return

        # Worker 노드
        else:
            async for event in self._execute_worker_node(
                node,
                node_outputs,
                initial_input,
                session_id,
                edges,
                template_renderer,
                project_path,
            ):
                yield event

    async def _execute_input_node(
        self,
        node: WorkflowNode,
        node_outputs: Dict[str, str],
        initial_input: str,
        session_id: str,
    ) -> AsyncIterator[WorkflowNodeExecutionEvent]:
        """Input 노드 실행"""
        node_id = node.id

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
            data={"agent_name": "Input"},
            timestamp=datetime.now().isoformat(),
        )

        # 입력 로그 이벤트
        yield WorkflowNodeExecutionEvent(
            event_type="node_output",
            node_id=node_id,
            data={"chunk": input_value, "log_type": "input"},
        )

        # 최종 출력 이벤트
        yield WorkflowNodeExecutionEvent(
            event_type="node_output",
            node_id=node_id,
            data={"chunk": input_value, "log_type": "output"},
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

        logger.info(f"[{session_id}] Input 노드 완료: {node_id} (출력 길이: {len(input_value)})")

    async def _execute_condition_node_wrapper(
        self,
        node: WorkflowNode,
        node_outputs: Dict[str, str],
        edges: List[WorkflowEdge],
        session_id: str,
        condition_evaluator: Any,
    ) -> AsyncIterator[WorkflowNodeExecutionEvent]:
        """Condition 노드 실행 (래퍼)"""
        start_time = time.time()
        node_id = node.id

        # 부모 노드 출력 가져오기
        parent_nodes = self._get_parent_nodes(node_id, edges)
        parent_output = ""
        if parent_nodes:
            parent_id = parent_nodes[0]
            parent_output = node_outputs.get(parent_id, "")

        node_data = node.data

        yield WorkflowNodeExecutionEvent(
            event_type="node_start",
            node_id=node_id,
            data={
                "node_type": "condition",
                "input": parent_output,
                "condition_type": (
                    node_data.condition_type
                    if hasattr(node_data, "condition_type")
                    else node_data.get("condition_type")
                ),
                "condition_value": (
                    node_data.condition_value
                    if hasattr(node_data, "condition_value")
                    else node_data.get("condition_value")
                ),
            },
            timestamp=datetime.now().isoformat(),
        )

        try:
            # WorkflowConditionEvaluator의 execute_condition_node 호출
            next_node_id, result_text = await condition_evaluator.execute_condition_node(
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

            logger.info(f"[{session_id}] 조건 노드 완료: {node_id} → {next_node_id}")

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

    async def _execute_merge_node_wrapper(
        self,
        node: WorkflowNode,
        node_outputs: Dict[str, str],
        edges: List[WorkflowEdge],
        session_id: str,
        condition_evaluator: Any,
    ) -> AsyncIterator[WorkflowNodeExecutionEvent]:
        """Merge 노드 실행 (래퍼)"""
        start_time = time.time()
        node_id = node.id

        # 부모 노드 출력들 가져오기
        parent_nodes = self._get_parent_nodes(node_id, edges)
        parent_outputs_list = []
        for pid in parent_nodes:
            parent_outputs_list.append(node_outputs.get(pid, ""))

        node_data = node.data

        # 입력 요약
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
                "merge_strategy": (
                    node_data.merge_strategy
                    if hasattr(node_data, "merge_strategy")
                    else node_data.get("merge_strategy")
                ),
            },
            timestamp=datetime.now().isoformat(),
        )

        try:
            # WorkflowConditionEvaluator의 execute_merge_node 호출
            merged_output = await condition_evaluator.execute_merge_node(
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

            logger.info(f"[{session_id}] 병합 노드 완료: {node_id} (출력 길이: {len(merged_output)})")

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

    async def _execute_worker_node(
        self,
        node: WorkflowNode,
        node_outputs: Dict[str, str],
        initial_input: str,
        session_id: str,
        edges: List[WorkflowEdge],
        template_renderer: Any,
        project_path: Optional[str],
    ) -> AsyncIterator[WorkflowNodeExecutionEvent]:
        """Worker 노드 실행 (리팩토링됨: 헬퍼 메서드 사용)"""
        node_id = node.id
        start_time = time.time()

        # 1. 노드 데이터 파싱
        (
            agent_name,
            task_template,
            allowed_tools_override,
            thinking_override,
        ) = self._parse_worker_node_data(node, session_id)

        # 2. Agent 설정 준비 (오버라이드 적용)
        agent_config = self._prepare_worker_agent_config(
            agent_name, allowed_tools_override, thinking_override, node_id, session_id
        )

        # 3. 작업 템플릿 렌더링
        task_description = self._render_worker_task(
            task_template, node_id, node_outputs, initial_input, edges, template_renderer
        )

        # node_start 이벤트
        start_event = WorkflowNodeExecutionEvent(
            event_type="node_start",
            node_id=node_id,
            data={"agent_name": agent_name},
            timestamp=datetime.now().isoformat(),
        )
        logger.info(f"[{session_id}] 🟢 이벤트 생성: node_start (node: {node_id}, agent: {agent_name})")
        yield start_event

        # 입력 이벤트
        input_event = WorkflowNodeExecutionEvent(
            event_type="node_output",
            node_id=node_id,
            data={"chunk": task_description, "chunk_type": "input"},
        )
        logger.debug(f"[{session_id}] 📥 이벤트 생성: node_input (node: {node_id})")
        yield input_event

        try:
            logger.info(
                f"[{session_id}] 노드 실행: {node_id} ({agent_name}) "
                f"- 작업 길이: {len(task_description)}"
            )

            # 노드별 세션 관리
            previous_session_id = self.node_sessions.get(node_id)
            if previous_session_id:
                logger.info(
                    f"[{session_id}] 노드 {node_id}: 이전 세션 재개 " f"(세션: {previous_session_id[:8]}...)"
                )
            else:
                logger.info(f"[{session_id}] 노드 {node_id}: 새 세션 시작")

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

            # 사용자 입력 콜백
            async def user_input_callback_impl(question: str) -> str:
                logger.info(f"[{session_id}] 💬 사용자 입력 대기: {question[:100]}...")
                user_queue = self.user_input_queues.get(session_id)
                if not user_queue:
                    logger.error(f"[{session_id}] 사용자 입력 Queue를 찾을 수 없음")
                    raise ValueError(f"세션 {session_id}의 사용자 입력 Queue를 찾을 수 없습니다")
                answer = await user_queue.get()
                logger.info(f"[{session_id}] ✅ 사용자 답변 수신: {answer[:100]}...")
                return answer

            # SDK 세션 ID 콜백 (ResultMessage에서 추출 시 호출됨)
            session_event_sent = [False]  # 이벤트 전송 플래그 (중복 방지)

            def session_id_callback_impl(sdk_session_id: str) -> None:
                """SDK 세션 ID 저장 및 이벤트 전송 (ResultMessage 수신 시)"""
                logger.info(
                    f"[{session_id}] ⚡ SDK 세션 ID 획득: {sdk_session_id[:8]}... "
                    f"(노드 {node_id}, ResultMessage에서 추출)"
                )
                # 세션 저장
                self._save_worker_node_session(node_id, agent_name, sdk_session_id, session_id)
                # 이벤트 전송 플래그 설정 (다음 청크에서 전송)
                session_event_sent[0] = False

            # Worker 실행
            async for chunk in worker.execute_task(
                task_description,
                usage_callback=usage_callback,
                resume_session_id=previous_session_id,
                user_input_callback=user_input_callback_impl,
                session_id_callback=session_id_callback_impl,
            ):
                # 취소 플래그 체크
                self._check_cancellation(session_id)

                # 새 세션 생성 시 프론트엔드로 이벤트 전송 (최초 1회)
                if not session_event_sent[0] and not previous_session_id:
                    current_sdk_session = self.node_sessions.get(node_id)
                    if current_sdk_session:
                        session_event = WorkflowNodeExecutionEvent(
                            event_type="node_session_created",
                            node_id=node_id,
                            data={
                                "session_id": current_sdk_session,
                                "agent_name": agent_name,
                                "created_at": datetime.now().isoformat(),
                            },
                        )
                        logger.info(
                            f"[{session_id}] 📡 이벤트 전송: node_session_created "
                            f"(node: {node_id}, sdk_session: {current_sdk_session[:8]}...)"
                        )
                        yield session_event
                        session_event_sent[0] = True

                # 특수 이벤트 마커 감지
                if chunk.startswith("@EVENT:user_input_request:"):
                    import json

                    json_str = chunk[len("@EVENT:user_input_request:") :]
                    event_data = json.loads(json_str)
                    question = event_data.get("question", "")

                    user_input_event = WorkflowNodeExecutionEvent(
                        event_type="user_input_request",
                        node_id=node_id,
                        data={"question": question, "session_id": session_id},
                    )
                    logger.info(f"[{session_id}] 💬 이벤트 생성: user_input_request (node: {node_id})")
                    yield user_input_event
                    continue

                node_output_chunks.append(chunk)

                # 청크 타입 분류
                chunk_type = classify_chunk_type(chunk)

                output_event = WorkflowNodeExecutionEvent(
                    event_type="node_output",
                    node_id=node_id,
                    data={"chunk": chunk, "chunk_type": chunk_type},
                )
                logger.debug(
                    f"[{session_id}] 📝 이벤트 생성: node_output (node: {node_id}, "
                    f"type: {chunk_type}, chunk: {len(chunk)}자)"
                )
                yield output_event

            # 최종 텍스트 추출
            full_output = "".join(node_output_chunks)
            final_text = self._extract_final_output(full_output)
            node_outputs[node_id] = final_text

            logger.info(
                f"[{session_id}] 노드 출력 처리 완료: {node_id} "
                f"(전체: {len(full_output)}자, 최종 텍스트: {len(final_text)}자)"
            )

            # SDK 세션 ID 저장
            if worker.last_session_id:
                self._save_worker_node_session(
                    node_id, agent_name, worker.last_session_id, session_id
                )
            else:
                logger.warning(
                    f"[{session_id}] ⚠️  노드 {node_id}: SDK 세션 ID를 받지 못함. "
                    f"추가 프롬프트 기능을 사용할 수 없습니다."
                )

            elapsed_time = time.time() - start_time

            complete_event = WorkflowNodeExecutionEvent(
                event_type="node_complete",
                node_id=node_id,
                data={"agent_name": agent_name, "output_length": len(final_text)},
                timestamp=datetime.now().isoformat(),
                elapsed_time=elapsed_time,
                token_usage=node_token_usage,
            )
            logger.info(
                f"[{session_id}] ✅ 이벤트 생성: node_complete (node: {node_id}, agent: {agent_name})"
            )
            yield complete_event

            logger.info(
                f"[{session_id}] 노드 완료: {node_id} ({agent_name}) - 출력 길이: {len(final_text)}"
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

    async def execute_node_and_queue_events(
        self,
        node: WorkflowNode,
        node_outputs: Dict[str, str],
        initial_input: str,
        session_id: str,
        edges: List[WorkflowEdge],
        all_nodes: List[WorkflowNode],
        event_queue: asyncio.Queue,
        condition_evaluator: Any,
        template_renderer: Any,
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
            condition_evaluator: 조건 평가기
            template_renderer: 템플릿 렌더러
            project_path: 프로젝트 경로
        """
        try:
            async for event in self.execute_single_node(
                node,
                node_outputs,
                initial_input,
                session_id,
                edges,
                all_nodes,
                condition_evaluator,
                template_renderer,
                project_path,
            ):
                await event_queue.put(event)
        except Exception as e:
            logger.error(f"[{session_id}] 노드 {node.id} 실행 중 에러: {str(e)}", exc_info=True)
            await event_queue.put(e)

    async def execute_single_node_continue(
        self,
        node_id: str,
        additional_prompt: str,
        project_path: Optional[str] = None,
    ) -> AsyncIterator[WorkflowNodeExecutionEvent]:
        """
        단일 노드에 추가 프롬프트를 전송하여 대화 계속

        Args:
            node_id: 실행할 노드 ID
            additional_prompt: 추가 프롬프트
            project_path: 프로젝트 디렉토리 경로

        Yields:
            WorkflowNodeExecutionEvent: 노드 실행 이벤트

        Raises:
            ValueError: 노드를 찾을 수 없거나 이전 세션이 없는 경우
        """
        logger.info(
            f"[DEBUG] 추가 대화 요청: node_id={node_id}\n"
            f"[DEBUG] 저장된 노드 세션 목록: {list(self.node_sessions.keys())}\n"
            f"[DEBUG] 저장된 agent_name 목록: {list(self.node_agent_names.keys())}"
        )

        # 노드의 이전 세션 ID 확인
        previous_session_id = self.node_sessions.get(node_id)
        if not previous_session_id:
            available_nodes = ", ".join(self.node_sessions.keys()) if self.node_sessions else "(없음)"
            raise ValueError(
                f"노드 {node_id}의 이전 세션을 찾을 수 없습니다.\n"
                f"사용 가능한 노드: {available_nodes}\n"
                f"먼저 워크플로우를 실행해주세요."
            )

        # 노드의 agent_name 확인
        agent_name = self.node_agent_names.get(node_id)
        if not agent_name:
            available_agents = (
                ", ".join(self.node_agent_names.keys()) if self.node_agent_names else "(없음)"
            )
            raise ValueError(
                f"노드 {node_id}의 Agent 정보를 찾을 수 없습니다.\n" f"사용 가능한 노드: {available_agents}"
            )

        logger.info(f"노드 {node_id} 추가 대화 시작: {agent_name} (이전 세션: {previous_session_id[:8]}...)")

        # Agent 설정 조회
        agent_config = self._get_agent_config(agent_name)

        # node_start 이벤트
        yield WorkflowNodeExecutionEvent(
            event_type="node_start",
            node_id=node_id,
            data={"additional_prompt": True, "agent_name": agent_name},
            timestamp=datetime.now().isoformat(),
        )

        # Worker 실행
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

            # SDK 세션 ID 콜백 (추가 프롬프트 실행 시에도 즉시 저장)
            def session_id_callback_impl(sdk_session_id: str) -> None:
                logger.info(
                    f"⚡ SDK 세션 ID 조기 획득 (추가 프롬프트): {sdk_session_id[:8]}... "
                    f"(노드 {node_id})"
                )
                # 즉시 업데이트
                self.node_sessions[node_id] = sdk_session_id
                if node_id in self.node_session_history:
                    existing_session = next(
                        (s for s in self.node_session_history[node_id] if s["session_id"] == sdk_session_id),
                        None,
                    )
                    if existing_session:
                        existing_session["last_used_at"] = datetime.now().isoformat()

            async for chunk in worker.execute_task(
                additional_prompt,
                usage_callback=usage_callback,
                resume_session_id=previous_session_id,
                user_input_callback=None,
                session_id_callback=session_id_callback_impl,
            ):
                node_output_chunks.append(chunk)

                chunk_type = classify_chunk_type(chunk)

                output_event = WorkflowNodeExecutionEvent(
                    event_type="node_output",
                    node_id=node_id,
                    data={"chunk": chunk, "chunk_type": chunk_type},
                )
                logger.debug(f"📝 이벤트 생성: node_output (node: {node_id}, type: {chunk_type})")
                yield output_event

            # 최종 텍스트 추출
            full_output = "".join(node_output_chunks)
            final_text = self._extract_final_output(full_output)

            logger.info(
                f"노드 출력 처리 완료: {node_id} " f"(전체: {len(full_output)}자, 최종 텍스트: {len(final_text)}자)"
            )

            # SDK 세션 ID 업데이트
            if worker.last_session_id:
                self.node_sessions[node_id] = worker.last_session_id

                if node_id in self.node_session_history:
                    existing_session = next(
                        (
                            s
                            for s in self.node_session_history[node_id]
                            if s["session_id"] == worker.last_session_id
                        ),
                        None,
                    )
                    if existing_session:
                        existing_session["last_used_at"] = datetime.now().isoformat()

                logger.info(f"노드 세션 업데이트: {node_id} → SDK 세션 {worker.last_session_id[:8]}...")

            # node_complete 이벤트
            complete_event = WorkflowNodeExecutionEvent(
                event_type="node_complete",
                node_id=node_id,
                data={"agent_name": agent_name, "output_length": len(final_text)},
                timestamp=datetime.now().isoformat(),
                token_usage=node_token_usage,
            )
            logger.info(f"✅ 이벤트 생성: node_complete (node: {node_id}, agent: {agent_name})")
            yield complete_event

            logger.info(f"노드 추가 대화 완료: {node_id} ({agent_name}) - 출력 길이: {len(final_text)}")

        except Exception as e:
            logger.error(f"노드 {node_id} 추가 대화 실패: {e}", exc_info=True)
            yield WorkflowNodeExecutionEvent(
                event_type="node_error",
                node_id=node_id,
                data={"error": str(e)},
                timestamp=datetime.now().isoformat(),
            )
