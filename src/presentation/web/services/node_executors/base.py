"""
노드 실행기 베이스 클래스

모든 노드 타입별 Executor의 추상 베이스 클래스입니다.
"""

import asyncio
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from src.domain.models import AgentConfig
from src.infrastructure.config import JsonConfigLoader
from src.infrastructure.logging import get_logger
from src.presentation.web.schemas.workflow import (
    WorkflowNode,
    WorkflowEdge,
    WorkflowNodeExecutionEvent,
)

if TYPE_CHECKING:
    from src.presentation.web.services.workflow_condition_evaluator import (
        WorkflowConditionEvaluator,
    )
    from src.presentation.web.services.workflow_template_renderer import (
        WorkflowTemplateRenderer,
    )

logger = get_logger(__name__)


@runtime_checkable
class ConditionEvaluatorProtocol(Protocol):
    """조건 평가기 프로토콜 (순환 import 방지)"""

    async def execute_condition_node(
        self, node: WorkflowNode, node_outputs: dict[str, str], edges: list[WorkflowEdge], session_id: str
    ) -> tuple[str, str]:
        ...

    async def execute_merge_node(
        self, node: WorkflowNode, node_outputs: dict[str, str], edges: list[WorkflowEdge], session_id: str
    ) -> str:
        ...


@runtime_checkable
class TemplateRendererProtocol(Protocol):
    """템플릿 렌더러 프로토콜 (순환 import 방지)"""

    def render_task_template(
        self, template: str, node_id: str, node_outputs: dict[str, str], initial_input: str
    ) -> str:
        ...


class BaseNodeExecutor(ABC):
    """
    노드 실행기 베이스 클래스

    모든 노드 타입별 Executor는 이 클래스를 상속받아 execute() 메서드를 구현합니다.

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
        agent_config_map: dict[str, AgentConfig],
        custom_worker_names: set[str],
        project_path: str | None,
        node_sessions: dict[str, str],
        node_session_history: dict[str, list[dict[str, str]]],
        node_agent_names: dict[str, str],
        user_input_queues: dict[str, asyncio.Queue[str]],
        cancelled_sessions: set[str],
        on_node_session_update: callable | None = None,
    ) -> None:
        """
        BaseNodeExecutor 초기화

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
            on_node_session_update: 노드 세션 업데이트 콜백 (node_id, session_id)
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
        self.on_node_session_update = on_node_session_update

    @abstractmethod
    async def execute(
        self,
        node: WorkflowNode,
        node_outputs: dict[str, str],
        node_inputs: dict[str, str],
        initial_input: str,
        session_id: str,
        edges: list[WorkflowEdge],
        all_nodes: list[WorkflowNode],
        condition_evaluator: ConditionEvaluatorProtocol,
        template_renderer: TemplateRendererProtocol,
        executed_nodes: set[str] | None = None,
    ) -> AsyncIterator[WorkflowNodeExecutionEvent]:
        """
        노드 실행 (추상 메서드)

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
            executed_nodes: 실행 완료된 노드 집합 (회귀 판단용, 옵션)

        Yields:
            WorkflowNodeExecutionEvent: 노드 실행 이벤트
        """
        pass

    # ========================================================================
    # 공통 헬퍼 메서드
    # ========================================================================

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
                f"Agent '{agent_name}'를 찾을 수 없습니다.\n"
                f"사용 가능한 Agent: {', '.join(available_agents)}"
            )

            if agent_name not in self.custom_worker_names:
                error_msg += (
                    "\n\n힌트: 기본 제공 Worker가 아닙니다. "
                    "커스텀 워커인 경우 프로젝트 경로를 확인하세요."
                )
            else:
                error_msg += (
                    f"\n\n힌트: 커스텀 워커 '{agent_name}'가 로드되지 않았습니다. "
                    f"프로젝트 경로: {self.project_path}"
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
    def _get_parent_nodes(node_id: str, edges: list[WorkflowEdge]) -> list[str]:
        """
        노드의 부모 노드 ID 목록 조회

        Args:
            node_id: 노드 ID
            edges: 엣지 목록

        Returns:
            List[str]: 부모 노드 ID 목록
        """
        return [edge.source for edge in edges if edge.target == node_id]
