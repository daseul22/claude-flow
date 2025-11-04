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

            # WorkflowGraphManager 생성
            graph_manager = WorkflowGraphManager(workflow.nodes, workflow.edges)

            # 위상 정렬
            try:
                sorted_nodes = graph_manager.topological_sort(start_node_id)
            except ValueError as e:
                logger.error(f"[{session_id}] 워크플로우 정렬 실패: {e}")
                raise

            logger.info(f"[{session_id}] 실행 순서: " f"{[node.id for node in sorted_nodes]}")

            # 실행 그룹 계산 (병렬 실행 그룹 포함)
            execution_groups = graph_manager.compute_execution_groups(sorted_nodes)

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

                    async for event in self.node_executor.execute_single_node(
                        node=node,
                        node_outputs=node_outputs,
                        initial_input=initial_input,
                        session_id=session_id,
                        edges=workflow.edges,
                        all_nodes=workflow.nodes,
                        condition_evaluator=self.condition_evaluator,
                        template_renderer=self.template_renderer,
                        project_path=project_path,
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
                            self.node_executor.execute_node_and_queue_events(
                                node=node,
                                node_outputs=node_outputs,
                                initial_input=initial_input,
                                session_id=session_id,
                                edges=workflow.edges,
                                all_nodes=workflow.nodes,
                                event_queue=event_queue,
                                condition_evaluator=self.condition_evaluator,
                                template_renderer=self.template_renderer,
                                project_path=project_path,
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
                                logger.error(
                                    f"[{session_id}] {error_msg}", exc_info=event_or_exception
                                )

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

                    logger.info(f"[{session_id}] 병렬 그룹 완료: {group_node_ids}")

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
                f"[{session_id}] 워크플로우 취소 요청 받음. " f"실행 중인 태스크 {len(running_tasks)}개 정리 중..."
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
