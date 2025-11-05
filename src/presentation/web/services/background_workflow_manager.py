"""
백그라운드 워크플로우 실행 관리자

워크플로우를 백그라운드 Task로 실행하고, SSE 연결이 끊어져도 계속 실행되도록 합니다.
새로고침 후 재접속 시 진행 중인 워크플로우의 이벤트를 복구할 수 있습니다.
"""

import asyncio
from typing import Dict, Optional, AsyncIterator, Any
from dataclasses import dataclass, field
from collections import deque
from datetime import datetime

from src.infrastructure.logging import get_logger
from src.presentation.web.schemas.workflow import (
    Workflow,
    WorkflowNodeExecutionEvent,
)
from src.presentation.web.services.workflow_executor import WorkflowExecutor
from src.presentation.web.services.workflow_session_store import (
    get_session_store,
    WorkflowSessionStore,
)

logger = get_logger(__name__)


@dataclass
class BackgroundWorkflowTask:
    """
    백그라운드 워크플로우 Task

    Attributes:
        session_id: 세션 ID
        task: asyncio Task 객체
        event_queue: 이벤트 큐 (무제한, 메모리 관리는 cleanup_completed_tasks로 처리)
        completed: 완료 여부
        error: 에러 메시지 (에러 발생 시)
    """

    session_id: str
    task: asyncio.Task
    event_queue: deque = field(default_factory=deque)
    completed: bool = False
    error: Optional[str] = None
    start_time: str = field(default_factory=lambda: datetime.now().isoformat())


class BackgroundWorkflowManager:
    """
    백그라운드 워크플로우 실행 관리자 (싱글톤)

    워크플로우를 백그라운드 Task로 실행하고, 이벤트를 메모리 큐에 저장합니다.
    SSE 연결이 끊어져도 워크플로우는 계속 실행되며, 재접속 시 이벤트를 복구할 수 있습니다.

    Attributes:
        executor: WorkflowExecutor 인스턴스
        session_store: WorkflowSessionStore 인스턴스
        tasks: 세션 ID → BackgroundWorkflowTask 매핑
    """

    def __init__(
        self,
        executor: WorkflowExecutor,
        session_store: Optional[WorkflowSessionStore] = None,
        project_path: Optional[str] = None,
    ):
        """
        BackgroundWorkflowManager 초기화

        Args:
            executor: WorkflowExecutor 인스턴스
            session_store: WorkflowSessionStore 인스턴스 (기본값: 싱글톤)
            project_path: 프로젝트 디렉토리 경로 (세션 저장 위치 결정)
        """
        self.executor = executor
        self.project_path = project_path
        self.session_store = session_store or get_session_store(project_path)
        self.tasks: Dict[str, BackgroundWorkflowTask] = {}
        # 세션별 project_path 매핑 (올바른 session_store 사용을 위해)
        self.session_project_paths: Dict[str, Optional[str]] = {}

        logger.info(f"백그라운드 워크플로우 관리자 초기화 (프로젝트: {project_path or '기본'})")

    def _get_session_store(self, session_id: str) -> WorkflowSessionStore:
        """
        세션별 올바른 session_store 반환

        Args:
            session_id: 세션 ID

        Returns:
            WorkflowSessionStore: 세션에 맞는 session_store 인스턴스
        """
        project_path = self.session_project_paths.get(session_id)
        if project_path is not None:
            return get_session_store(project_path)
        return self.session_store

    async def start_workflow(
        self,
        session_id: str,
        workflow: Workflow,
        initial_input: str,
        project_path: Optional[str] = None,
        start_node_id: Optional[str] = None,
    ) -> None:
        """
        워크플로우를 백그라운드 Task로 시작

        Args:
            session_id: 세션 ID
            workflow: 실행할 워크플로우
            initial_input: 초기 입력
            project_path: 프로젝트 디렉토리 경로 (세션별 로그 저장용)
            start_node_id: 시작 노드 ID (옵션, 지정 시 해당 Input 노드에서만 시작)

        Raises:
            ValueError: 이미 실행 중인 세션인 경우
        """
        # 이미 실행 중인 세션 확인
        if session_id in self.tasks:
            existing_task = self.tasks[session_id]
            if not existing_task.completed:
                raise ValueError(f"세션 {session_id}는 이미 실행 중입니다")

        # 세션의 project_path 저장 (올바른 session_store 사용을 위해)
        self.session_project_paths[session_id] = project_path

        logger.info(f"[{session_id}] 백그라운드 워크플로우 시작: {workflow.name}")

        # 백그라운드 Task 생성 (project_path, start_node_id 전달)
        task = asyncio.create_task(
            self._run_workflow(session_id, workflow, initial_input, project_path, start_node_id)
        )

        # Task 등록
        self.tasks[session_id] = BackgroundWorkflowTask(
            session_id=session_id,
            task=task,
        )

    async def _run_workflow(
        self,
        session_id: str,
        workflow: Workflow,
        initial_input: str,
        project_path: Optional[str] = None,
        start_node_id: Optional[str] = None,
    ) -> None:
        """
        워크플로우 실행 (백그라운드 Task 내부)

        Args:
            session_id: 세션 ID
            workflow: 실행할 워크플로우
            initial_input: 초기 입력
            project_path: 프로젝트 디렉토리 경로 (세션별 로그 저장용)
            start_node_id: 시작 노드 ID (옵션, 지정 시 해당 Input 노드에서만 시작)
        """
        bg_task = self.tasks[session_id]

        # 세션에 맞는 session_store 사용
        session_store = self._get_session_store(session_id)

        try:
            logger.info(f"[{session_id}] 워크플로우 실행 시작 (백그라운드, 세션 경로: {project_path or '기본'})")

            # WorkflowExecutor 실행 (project_path, start_node_id 전달)
            async for event in self.executor.execute_workflow(
                workflow=workflow,
                initial_input=initial_input,
                session_id=session_id,
                project_path=project_path,
                start_node_id=start_node_id,
            ):
                # 이벤트를 큐에 저장
                bg_task.event_queue.append(event)

                # 세션 저장소에도 기록 (올바른 session_store 사용)
                await session_store.append_log(session_id, event)

                logger.debug(
                    f"[{session_id}] 이벤트 큐에 추가: {event.event_type} "
                    f"(큐 크기: {len(bg_task.event_queue)})"
                )

            # 완료 처리
            bg_task.completed = True
            logger.info(f"[{session_id}] 워크플로우 실행 완료 (백그라운드)")

        except Exception as e:
            error_msg = str(e)
            bg_task.error = error_msg

            logger.error(
                f"[{session_id}] 워크플로우 실행 실패 (백그라운드): {error_msg}",
                exc_info=True,
            )

            # 에러 이벤트를 큐에 추가 (SSE 클라이언트가 에러를 받을 수 있도록)
            error_event = WorkflowNodeExecutionEvent(
                event_type="workflow_error",
                node_id="",
                data={"error": error_msg},
                timestamp=datetime.now().isoformat(),
            )
            bg_task.event_queue.append(error_event)

            # 완료 처리
            bg_task.completed = True

            # 세션 상태 업데이트 (올바른 session_store 사용)
            await session_store.update_session(
                session_id,
                status="error",
                error=error_msg,
                end_time=datetime.now().isoformat(),
            )

    async def stream_events(
        self,
        session_id: str,
        start_from_index: int = 0,
    ) -> AsyncIterator[WorkflowNodeExecutionEvent]:
        """
        세션의 이벤트 스트리밍 (세션 저장소 기반 + 실시간 폴링)

        새로고침 후 재접속 시에도 중복 없이 이벤트를 이어받을 수 있습니다.

        Args:
            session_id: 세션 ID
            start_from_index: 시작 이벤트 인덱스 (0부터 시작, 기본값 0)

        Yields:
            WorkflowNodeExecutionEvent: 노드 실행 이벤트

        Raises:
            ValueError: 세션을 찾을 수 없는 경우
        """
        # 세션에 맞는 session_store 사용
        session_store = self._get_session_store(session_id)

        # 세션 저장소에서 세션 가져오기
        session = await session_store.get_session(session_id)
        if not session:
            raise ValueError(f"세션을 찾을 수 없습니다: {session_id}")

        # 백그라운드 Task 확인 (실시간 폴링 여부 결정)
        bg_task = self.tasks.get(session_id)
        is_task_running = bg_task is not None and not bg_task.completed

        logger.info(
            f"[{session_id}] 이벤트 스트리밍 시작 "
            f"(start_from_index={start_from_index}, "
            f"저장된 로그={len(session.logs)}, "
            f"실시간 폴링={is_task_running})"
        )

        # 1. 세션 저장소에서 기존 이벤트 전송 (start_from_index 이후)
        existing_logs = session.logs[start_from_index:]
        for log_entry in existing_logs:
            # Dict → WorkflowNodeExecutionEvent 변환
            event = WorkflowNodeExecutionEvent(**log_entry)
            yield event

        sent_count = start_from_index + len(existing_logs)
        logger.info(f"[{session_id}] 기존 이벤트 전송 완료: {len(existing_logs)}개 " f"(총 누적: {sent_count}개)")

        # 2. 실시간 이벤트 스트리밍 (백그라운드 Task가 실행 중인 경우)
        if is_task_running:
            logger.info(f"[{session_id}] 실시간 폴링 시작")

            while not bg_task.completed:
                # 세션 저장소 다시 로드 (새 이벤트 확인)
                session = await session_store.get_session(session_id)
                if not session:
                    logger.warning(f"[{session_id}] 세션이 삭제되었습니다. 스트리밍 중단")
                    break

                current_log_count = len(session.logs)

                # 새 이벤트가 있으면 전송
                if current_log_count > sent_count:
                    new_logs = session.logs[sent_count:]
                    for log_entry in new_logs:
                        event = WorkflowNodeExecutionEvent(**log_entry)
                        yield event
                        sent_count += 1

                # 짧은 대기 (CPU 사용률 최소화)
                await asyncio.sleep(0.1)

            # 3. 완료 후 남은 이벤트 전송 (race condition 방지)
            session = await session_store.get_session(session_id)
            if session:
                final_logs = session.logs[sent_count:]
                for log_entry in final_logs:
                    event = WorkflowNodeExecutionEvent(**log_entry)
                    yield event

                logger.info(f"[{session_id}] 실시간 폴링 완료 " f"(총 {len(session.logs)}개 이벤트)")
        else:
            logger.info(f"[{session_id}] 백그라운드 Task 없음. 저장된 이벤트만 전송 완료 " f"(상태: {session.status})")

    def get_task_status(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Task 상태 조회

        Args:
            session_id: 세션 ID

        Returns:
            Dict[str, any]: Task 상태 (None이면 세션을 찾을 수 없음)
                - session_id: 세션 ID
                - completed: 완료 여부
                - error: 에러 메시지 (에러 발생 시)
                - event_count: 이벤트 개수
                - start_time: 시작 시각
        """
        if session_id not in self.tasks:
            return None

        bg_task = self.tasks[session_id]
        return {
            "session_id": session_id,
            "completed": bg_task.completed,
            "error": bg_task.error,
            "event_count": len(bg_task.event_queue),
            "start_time": bg_task.start_time,
        }

    async def cancel_workflow(self, session_id: str) -> None:
        """
        워크플로우 취소

        Args:
            session_id: 세션 ID

        Raises:
            ValueError: 세션을 찾을 수 없는 경우
        """
        if session_id not in self.tasks:
            raise ValueError(f"세션을 찾을 수 없습니다: {session_id}")

        bg_task = self.tasks[session_id]

        # WorkflowExecutor에 취소 플래그 등록 (각 노드 실행 전 체크)
        self.executor.cancel_session(session_id)

        # Task 취소 (asyncio.CancelledError 발생)
        bg_task.task.cancel()

        try:
            # Task가 완전히 종료될 때까지 대기 (정리 작업 완료)
            await bg_task.task
        except asyncio.CancelledError:
            logger.info(f"[{session_id}] 워크플로우 취소 완료")

        # 완료 처리
        bg_task.completed = True

        # 세션 상태 업데이트 (올바른 session_store 사용)
        session_store = self._get_session_store(session_id)
        await session_store.update_session(
            session_id,
            status="cancelled",
            end_time=datetime.now().isoformat(),
        )

    async def cleanup_completed_tasks(self, max_age_seconds: int = 3600) -> int:
        """
        완료된 Task 정리 (메모리 절약)

        Args:
            max_age_seconds: 최대 보존 시간 (초)

        Returns:
            int: 정리된 Task 개수
        """
        now = datetime.now()
        removed_count = 0

        session_ids_to_remove = []
        for session_id, bg_task in self.tasks.items():
            if not bg_task.completed:
                continue

            # 시작 시간 파싱
            start_time = datetime.fromisoformat(bg_task.start_time)
            age_seconds = (now - start_time).total_seconds()

            if age_seconds > max_age_seconds:
                session_ids_to_remove.append(session_id)

        # Task 제거
        for session_id in session_ids_to_remove:
            del self.tasks[session_id]
            removed_count += 1
            logger.info(f"[{session_id}] 완료된 Task 정리 (메모리 절약)")

        return removed_count

    async def restart_workflow_from_node(
        self,
        original_session_id: str,
        restart_node_id: str,
        new_session_id: str,
    ) -> None:
        """
        특정 노드부터 워크플로우 재시작

        이전 실행의 상태(node_outputs, node_inputs)를 복원하여
        지정된 노드부터 워크플로우를 다시 실행합니다.

        Args:
            original_session_id: 원본 세션 ID (이전 실행)
            restart_node_id: 재시작할 노드 ID
            new_session_id: 새 세션 ID (재시작 실행)

        Raises:
            ValueError: 원본 세션을 찾을 수 없는 경우
        """
        # 원본 세션 조회 (올바른 session_store 사용)
        session_store = self._get_session_store(original_session_id)
        original_session = await session_store.get_session(original_session_id)
        if not original_session:
            raise ValueError(f"원본 세션을 찾을 수 없습니다: {original_session_id}")

        logger.info(
            f"[{new_session_id}] 워크플로우 재시작 요청 - "
            f"원본: {original_session_id}, 재시작 노드: {restart_node_id}"
        )

        # 재시작 노드 확인
        restart_node = next(
            (n for n in original_session.workflow.nodes if n.id == restart_node_id), None
        )
        if not restart_node:
            raise ValueError(
                f"재시작 노드를 찾을 수 없습니다: {restart_node_id} "
                f"(워크플로우: {original_session.workflow.name})"
            )

        # 재시작 노드 이전에 실행된 노드들 수집
        all_node_ids = {n.id for n in original_session.workflow.nodes}
        executed_before_restart = set()

        # node_outputs에 저장된 노드들 = 이미 실행 완료된 노드들
        for node_id in original_session.node_outputs.keys():
            if node_id in all_node_ids and node_id != restart_node_id:
                executed_before_restart.add(node_id)

        logger.info(
            f"[{new_session_id}] 이전 실행 상태 복원 - "
            f"실행 완료 노드: {len(executed_before_restart)}개, "
            f"노드 출력: {len(original_session.node_outputs)}개, "
            f"노드 입력: {len(original_session.node_inputs)}개"
        )

        # 백그라운드 Task 생성 (restore 파라미터 전달)
        task = asyncio.create_task(
            self._run_workflow_with_restore(
                session_id=new_session_id,
                workflow=original_session.workflow,
                initial_input=original_session.initial_input,
                project_path=original_session.project_path,
                start_node_id=restart_node_id,
                restore_node_outputs=original_session.node_outputs,
                restore_node_inputs=original_session.node_inputs,
                restore_executed_nodes=executed_before_restart,
            )
        )

        # Task 등록
        self.tasks[new_session_id] = BackgroundWorkflowTask(
            session_id=new_session_id,
            task=task,
        )

    async def _run_workflow_with_restore(
        self,
        session_id: str,
        workflow: Workflow,
        initial_input: str,
        project_path: Optional[str] = None,
        start_node_id: Optional[str] = None,
        restore_node_outputs: Optional[Dict[str, str]] = None,
        restore_node_inputs: Optional[Dict[str, str]] = None,
        restore_executed_nodes: Optional[set] = None,
    ) -> None:
        """
        워크플로우 실행 (복원 파라미터 포함)

        Args:
            session_id: 세션 ID
            workflow: 실행할 워크플로우
            initial_input: 초기 입력
            project_path: 프로젝트 디렉토리 경로
            start_node_id: 시작 노드 ID
            restore_node_outputs: 복원할 노드 출력
            restore_node_inputs: 복원할 노드 입력
            restore_executed_nodes: 복원할 실행 완료 노드 목록
        """
        bg_task = self.tasks[session_id]

        # 세션에 맞는 session_store 사용
        session_store = self._get_session_store(session_id)

        try:
            logger.info(f"[{session_id}] 워크플로우 재시작 실행 시작 (백그라운드)")

            # WorkflowExecutor 실행 (restore 파라미터 전달)
            async for event in self.executor.execute_workflow(
                workflow=workflow,
                initial_input=initial_input,
                session_id=session_id,
                project_path=project_path,
                start_node_id=start_node_id,
                restore_node_outputs=restore_node_outputs,
                restore_node_inputs=restore_node_inputs,
                restore_executed_nodes=restore_executed_nodes,
            ):
                # 이벤트를 큐에 저장
                bg_task.event_queue.append(event)

                # 세션 저장소에도 기록 (올바른 session_store 사용)
                await session_store.append_log(session_id, event)

                logger.debug(
                    f"[{session_id}] 이벤트 큐에 추가: {event.event_type} "
                    f"(큐 크기: {len(bg_task.event_queue)})"
                )

            # 완료 처리
            bg_task.completed = True
            logger.info(f"[{session_id}] 워크플로우 재시작 실행 완료 (백그라운드)")

        except Exception as e:
            error_msg = str(e)
            bg_task.error = error_msg

            logger.error(
                f"[{session_id}] 워크플로우 재시작 실행 실패 (백그라운드): {error_msg}",
                exc_info=True,
            )

            # 에러 이벤트를 큐에 추가
            error_event = WorkflowNodeExecutionEvent(
                event_type="workflow_error",
                node_id="",
                data={"error": error_msg},
                timestamp=datetime.now().isoformat(),
            )
            bg_task.event_queue.append(error_event)

            # 완료 처리
            bg_task.completed = True

            # 세션 상태 업데이트 (올바른 session_store 사용)
            await session_store.update_session(
                session_id,
                status="error",
                error=error_msg,
                end_time=datetime.now().isoformat(),
            )


# 프로젝트별 인스턴스 캐시 (프로젝트 경로 → BackgroundWorkflowManager)
_managers: Dict[str, BackgroundWorkflowManager] = {}


def get_background_workflow_manager(
    executor: Optional[WorkflowExecutor] = None,
    project_path: Optional[str] = None,
) -> BackgroundWorkflowManager:
    """
    BackgroundWorkflowManager 인스턴스 반환 (프로젝트별 캐싱)

    프로젝트 경로별로 별도의 BackgroundWorkflowManager 인스턴스를 유지합니다.
    이를 통해 프로젝트 전환 시에도 각 프로젝트의 커스텀 워커를 올바르게 로드할 수 있습니다.

    Args:
        executor: WorkflowExecutor 인스턴스 (첫 호출 시 필수)
        project_path: 프로젝트 경로 (None이면 기본 인스턴스)

    Returns:
        BackgroundWorkflowManager: 프로젝트별 인스턴스

    Raises:
        ValueError: 첫 호출 시 executor가 None인 경우
    """
    global _managers

    # 캐시 키 생성
    cache_key = project_path or "~default"

    # 캐시에서 인스턴스 확인
    if cache_key not in _managers:
        if executor is None:
            raise ValueError("첫 호출 시 executor를 제공해야 합니다")
        logger.info(f"새 BackgroundWorkflowManager 생성 (프로젝트: {cache_key})")
        _managers[cache_key] = BackgroundWorkflowManager(
            executor,
            project_path=project_path
        )
    else:
        # 기존 인스턴스가 있지만 executor가 다르면 업데이트
        if executor is not None:
            existing_manager = _managers[cache_key]
            if existing_manager.executor != executor:
                logger.info(f"BackgroundWorkflowManager executor 업데이트 (프로젝트: {cache_key})")
                existing_manager.executor = executor

    return _managers[cache_key]
