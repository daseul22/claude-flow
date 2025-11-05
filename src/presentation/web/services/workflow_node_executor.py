"""
워크플로우 노드 실행기 (오케스트레이터)

개별 노드를 실행하고, 노드 출력을 관리합니다.
Strategy Pattern으로 각 노드 타입별 실행 로직을 분리했습니다.
"""

import asyncio
from typing import Dict, Any, AsyncIterator, List, Optional, Set

from src.domain.models import AgentConfig
from src.infrastructure.config import JsonConfigLoader
from src.infrastructure.logging import get_logger
from src.presentation.web.schemas.workflow import (
    WorkflowNode,
    WorkflowEdge,
    WorkflowNodeExecutionEvent,
)
from src.presentation.web.services.node_executors import (
    InputNodeExecutor,
    WorkerNodeExecutor,
    ConditionNodeExecutor,
    MergeNodeExecutor,
)

logger = get_logger(__name__)


class WorkflowNodeExecutor:
    """
    워크플로우 노드 실행 오케스트레이터

    노드 타입에 따라 적절한 NodeExecutor에 실행을 위임합니다 (Strategy Pattern).

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
        input_executor: Input 노드 실행기
        worker_executor: Worker 노드 실행기
        condition_executor: Condition 노드 실행기
        merge_executor: Merge 노드 실행기
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

        # 노드 타입별 Executor 생성 (Strategy Pattern)
        executor_args = {
            "config_loader": config_loader,
            "agent_config_map": agent_config_map,
            "custom_worker_names": custom_worker_names,
            "project_path": project_path,
            "node_sessions": node_sessions,
            "node_session_history": node_session_history,
            "node_agent_names": node_agent_names,
            "user_input_queues": user_input_queues,
            "cancelled_sessions": cancelled_sessions,
        }

        self.input_executor = InputNodeExecutor(**executor_args)
        self.worker_executor = WorkerNodeExecutor(**executor_args)
        self.condition_executor = ConditionNodeExecutor(**executor_args)
        self.merge_executor = MergeNodeExecutor(**executor_args)

    async def execute_single_node(
        self,
        node: WorkflowNode,
        node_outputs: Dict[str, str],
        node_inputs: Dict[str, str],
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

        노드 타입에 따라 적절한 Executor에 위임합니다.

        Args:
            node: 실행할 노드
            node_outputs: 이전 노드 출력들
            node_inputs: 각 노드가 실제로 받을 입력 (피드백 루프 지원)
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
        if session_id in self.cancelled_sessions:
            logger.info(f"[{session_id}] 취소 플래그 감지 - CancelledError 발생")
            raise asyncio.CancelledError(f"Session {session_id} was cancelled")

        # 노드 타입에 따라 적절한 Executor 선택 (Strategy Pattern)
        if node.type == "input":
            executor = self.input_executor
        elif node.type == "condition":
            executor = self.condition_executor
        elif node.type == "merge":
            executor = self.merge_executor
        else:  # worker 노드
            executor = self.worker_executor

        # Executor에 실행 위임
        async for event in executor.execute(
            node=node,
            node_outputs=node_outputs,
            node_inputs=node_inputs,
            initial_input=initial_input,
            session_id=session_id,
            edges=edges,
            all_nodes=all_nodes,
            condition_evaluator=condition_evaluator,
            template_renderer=template_renderer,
        ):
            yield event

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

        Worker 노드에만 적용되며, WorkerNodeExecutor에 위임합니다.

        Args:
            node_id: 실행할 노드 ID
            additional_prompt: 추가 프롬프트
            project_path: 프로젝트 디렉토리 경로

        Yields:
            WorkflowNodeExecutionEvent: 노드 실행 이벤트

        Raises:
            ValueError: 노드를 찾을 수 없거나 이전 세션이 없는 경우
        """
        # WorkerNodeExecutor에 위임
        async for event in self.worker_executor.execute_continue(
            node_id=node_id,
            additional_prompt=additional_prompt,
        ):
            yield event
