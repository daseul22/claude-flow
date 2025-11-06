"""
워크플로우 세션 저장소

워크플로우 실행 상태를 파일로 저장하여 새로고침 후에도 복구 가능하도록 합니다.

저장 경로:
- 프로젝트 선택 시: ~/.claude-flow/{project_name}/web-sessions/{session_id}.json
- 프로젝트 미선택 시: ~/.claude-flow/web-sessions/{session_id}.json (fallback)
"""

import json
import asyncio
import aiofiles
from pathlib import Path
from typing import Dict, List, Optional, Any, Literal
from datetime import datetime
from dataclasses import dataclass, field

from src.infrastructure.logging import get_logger
from src.presentation.web.schemas.workflow import Workflow, WorkflowNodeExecutionEvent

logger = get_logger(__name__)


@dataclass
class WorkflowSession:
    """
    워크플로우 실행 세션

    Attributes:
        session_id: 세션 ID
        workflow: 워크플로우 정의
        initial_input: 초기 입력
        project_path: 프로젝트 디렉토리 경로 (세션 복원용)
        status: 실행 상태 (running, completed, error, cancelled)
        current_node_id: 현재 실행 중인 노드 ID
        node_outputs: 노드별 출력 (node_id → output)
        logs: 실행 로그 (이벤트 목록)
        start_time: 시작 시각
        end_time: 종료 시각
        error: 에러 메시지 (에러 발생 시)
    """

    session_id: str
    workflow: Workflow
    initial_input: str
    project_path: Optional[str] = None  # 프로젝트 경로 (세션 복원용)
    status: Literal["running", "completed", "error", "cancelled"] = "running"
    current_node_id: Optional[str] = None
    node_outputs: Dict[str, str] = field(default_factory=dict)
    node_inputs: Dict[str, str] = field(default_factory=dict)  # 노드별 입력 (디버깅용)
    logs: List[Dict[str, Any]] = field(default_factory=list)
    start_time: str = field(default_factory=lambda: datetime.now().isoformat())
    end_time: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환 (JSON 직렬화용)"""
        return {
            "session_id": self.session_id,
            "workflow": self.workflow.model_dump()
            if hasattr(self.workflow, "model_dump")
            else self.workflow,
            "initial_input": self.initial_input,
            "project_path": self.project_path,
            "status": self.status,
            "current_node_id": self.current_node_id,
            "node_outputs": self.node_outputs,
            "node_inputs": self.node_inputs,
            "logs": self.logs,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkflowSession":
        """딕셔너리에서 복원"""
        workflow_data = data["workflow"]
        workflow = Workflow(**workflow_data) if isinstance(workflow_data, dict) else workflow_data

        return cls(
            session_id=data["session_id"],
            workflow=workflow,
            initial_input=data["initial_input"],
            project_path=data.get("project_path"),  # 프로젝트 경로 복원
            status=data["status"],
            current_node_id=data.get("current_node_id"),
            node_outputs=data.get("node_outputs", {}),
            node_inputs=data.get("node_inputs", {}),  # 노드별 입력 복원
            logs=data.get("logs", []),
            start_time=data["start_time"],
            end_time=data.get("end_time"),
            error=data.get("error"),
        )


class WorkflowSessionStore:
    """
    워크플로우 세션 저장소 (파일 기반 + 메모리 캐싱)

    세션 데이터를 JSON 파일로 저장하고, 메모리에 캐싱하여 빠른 접근을 제공합니다.

    Attributes:
        sessions_dir: 세션 저장 디렉토리
        _cache: 메모리 캐시 (session_id → WorkflowSession)
        _locks: 세션별 파일 쓰기 락 (동시성 제어)
    """

    def __init__(self, sessions_dir: Optional[Path] = None):
        """
        WorkflowSessionStore 초기화

        Args:
            sessions_dir: 세션 저장 디렉토리 (기본값: ~/.claude-flow/web-sessions/)
        """
        if sessions_dir is None:
            sessions_dir = Path.home() / ".claude-flow" / "web-sessions"

        self.sessions_dir = sessions_dir
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

        # 메모리 캐시 (session_id → WorkflowSession)
        self._cache: Dict[str, WorkflowSession] = {}

        # 파일 쓰기 락 (session_id → asyncio.Lock)
        self._locks: Dict[str, asyncio.Lock] = {}

        logger.info(f"워크플로우 세션 저장소 초기화: {self.sessions_dir}")

    def _get_session_path(self, session_id: str) -> Path:
        """세션 파일 경로 반환"""
        return self.sessions_dir / f"{session_id}.json"

    def _get_lock(self, session_id: str) -> asyncio.Lock:
        """세션별 파일 쓰기 락 반환 (동시성 제어)"""
        if session_id not in self._locks:
            self._locks[session_id] = asyncio.Lock()
        return self._locks[session_id]

    async def create_session(
        self,
        session_id: str,
        workflow: Workflow,
        initial_input: str,
        project_path: Optional[str] = None,
    ) -> WorkflowSession:
        """
        새 세션 생성 및 저장

        Args:
            session_id: 세션 ID
            workflow: 워크플로우 정의
            initial_input: 초기 입력
            project_path: 프로젝트 디렉토리 경로 (세션 복원용)

        Returns:
            WorkflowSession: 생성된 세션
        """
        session = WorkflowSession(
            session_id=session_id,
            workflow=workflow,
            initial_input=initial_input,
            project_path=project_path,
            status="running",
        )

        # 메모리 캐시에 저장
        self._cache[session_id] = session

        # 파일로 저장
        await self._save_to_file(session)

        logger.info(f"세션 생성: {session_id} (워크플로우: {workflow.name})")
        return session

    async def get_session(self, session_id: str) -> Optional[WorkflowSession]:
        """
        세션 조회 (캐시 우선, 없으면 파일에서 로드)

        Args:
            session_id: 세션 ID

        Returns:
            WorkflowSession: 세션 (없으면 None)
        """
        # 1. 메모리 캐시 확인
        if session_id in self._cache:
            return self._cache[session_id]

        # 2. 파일에서 로드
        session_path = self._get_session_path(session_id)
        if not session_path.exists():
            return None

        try:
            # 비동기 파일 읽기 (이벤트 루프 블로킹 방지)
            async with aiofiles.open(session_path, "r", encoding="utf-8") as f:
                content = await f.read()
                data = json.loads(content)

            session = WorkflowSession.from_dict(data)

            # 캐시에 저장
            self._cache[session_id] = session

            logger.info(f"세션 로드: {session_id} (상태: {session.status})")
            return session

        except Exception as e:
            logger.error(f"세션 로드 실패: {session_id} - {e}", exc_info=True)
            return None

    async def update_session(
        self,
        session_id: str,
        **updates: Any,
    ) -> None:
        """
        세션 업데이트 (부분 업데이트 지원)

        Args:
            session_id: 세션 ID
            **updates: 업데이트할 필드 (status, current_node_id, error 등)

        Raises:
            ValueError: 세션을 찾을 수 없는 경우
        """
        session = await self.get_session(session_id)
        if not session:
            raise ValueError(f"세션을 찾을 수 없습니다: {session_id}")

        # 필드 업데이트
        for key, value in updates.items():
            if hasattr(session, key):
                setattr(session, key, value)

        # 파일로 저장
        await self._save_to_file(session)

        logger.debug(f"세션 업데이트: {session_id} - {updates}")

    async def append_log(
        self,
        session_id: str,
        event: WorkflowNodeExecutionEvent,
    ) -> None:
        """
        세션에 로그 추가 (이벤트 기록)

        Args:
            session_id: 세션 ID
            event: 워크플로우 노드 실행 이벤트

        Raises:
            ValueError: 세션을 찾을 수 없는 경우
        """
        session = await self.get_session(session_id)
        if not session:
            raise ValueError(f"세션을 찾을 수 없습니다: {session_id}")

        # 이벤트를 딕셔너리로 변환하여 로그에 추가
        log_entry = event.model_dump()
        session.logs.append(log_entry)

        # 이벤트 타입별 처리
        if event.event_type == "node_start":
            session.current_node_id = event.node_id

            # 노드 입력 저장 (디버깅용)
            if "input" in event.data:
                session.node_inputs[event.node_id] = event.data["input"]

        elif event.event_type == "node_output":
            # 노드 출력 누적 (청크 단위 추가)
            chunk = event.data.get("chunk", "")
            if event.node_id not in session.node_outputs:
                session.node_outputs[event.node_id] = ""
            session.node_outputs[event.node_id] += chunk

        elif event.event_type == "node_complete":
            # 노드 완료 시 전체 출력 저장 (이벤트에 포함된 경우)
            if "output" in event.data:
                session.node_outputs[event.node_id] = event.data["output"]

        elif event.event_type == "node_error":
            session.status = "error"
            session.error = event.data.get("error", "Unknown error")
            session.end_time = datetime.now().isoformat()

        elif event.event_type == "workflow_complete":
            session.status = "completed"
            session.current_node_id = None
            session.end_time = datetime.now().isoformat()

        # 파일로 저장 (비동기 + 락)
        await self._save_to_file(session)

    async def save_session(self, session: WorkflowSession) -> None:
        """
        기존 세션 객체를 저장 (캐시 + 파일)

        Args:
            session: 저장할 세션 객체
        """
        # 메모리 캐시에 저장
        self._cache[session.session_id] = session

        # 파일로 저장
        await self._save_to_file(session)

        logger.info(f"세션 저장: {session.session_id}")

    async def delete_session(self, session_id: str) -> None:
        """
        세션 삭제 (캐시 + 파일 + Lock)

        Args:
            session_id: 세션 ID
        """
        # 캐시에서 제거
        self._cache.pop(session_id, None)

        # Lock 제거 (메모리 누수 방지)
        if session_id in self._locks:
            del self._locks[session_id]

        # 파일 삭제
        session_path = self._get_session_path(session_id)
        if session_path.exists():
            session_path.unlink()
            logger.info(f"세션 삭제: {session_id}")

    async def list_sessions(
        self,
        status: Optional[Literal["running", "completed", "error", "cancelled"]] = None,
    ) -> List[WorkflowSession]:
        """
        세션 목록 조회

        Args:
            status: 상태 필터 (None이면 모두 조회)

        Returns:
            List[WorkflowSession]: 세션 목록
        """
        sessions = []

        for session_path in self.sessions_dir.glob("*.json"):
            session_id = session_path.stem
            session = await self.get_session(session_id)

            if session:
                if status is None or session.status == status:
                    sessions.append(session)

        return sessions

    async def _save_to_file(self, session: WorkflowSession) -> None:
        """
        세션을 파일로 저장 (비동기 + 락)

        Args:
            session: 저장할 세션
        """
        session_path = self._get_session_path(session.session_id)

        # 세션별 락 획득 (동시 쓰기 방지)
        lock = self._get_lock(session.session_id)
        async with lock:
            try:
                # 디렉토리 확인 및 생성
                session_path.parent.mkdir(parents=True, exist_ok=True)

                # JSON 직렬화
                data = session.to_dict()
                json_str = json.dumps(data, ensure_ascii=False, indent=2)

                # 비동기 파일 쓰기 (이벤트 루프 블로킹 방지)
                async with aiofiles.open(session_path, "w", encoding="utf-8") as f:
                    await f.write(json_str)

                logger.info(f"세션 저장 완료: {session.session_id} → {session_path}")

            except Exception as e:
                logger.error(f"세션 저장 실패: {session.session_id} → {session_path} - {e}", exc_info=True)


# 싱글톤 인스턴스 캐시 (프로젝트 경로별로 별도 인스턴스)
_session_stores: Dict[str, WorkflowSessionStore] = {}


def get_session_store(project_path: Optional[str] = None) -> WorkflowSessionStore:
    """
    WorkflowSessionStore 인스턴스 반환 (프로젝트별 캐싱)

    Args:
        project_path: 프로젝트 디렉토리 경로 (None이면 전역 projects 모듈에서 가져옴)

    Returns:
        WorkflowSessionStore: 프로젝트별 세션 저장소 인스턴스

    Note:
        - 프로젝트 선택 시: ~/.claude-flow/{project_name}/web-sessions/
        - 프로젝트 미선택 시: ~/.claude-flow/web-sessions/ (fallback)
    """
    # project_path가 명시되지 않으면 전역 _current_project_path 사용
    if project_path is None:
        # 순환 import 방지를 위해 함수 내부에서 import
        try:
            from src.presentation.web.routers.projects import _current_project_path

            project_path = _current_project_path
        except ImportError:
            logger.warning("projects 모듈을 불러올 수 없습니다. Fallback 경로 사용")
            project_path = None

    # 세션 디렉토리 결정
    if project_path:
        # 프로젝트별 세션 디렉토리: ~/.claude-flow/{project_name}/web-sessions/
        project_name = Path(project_path).name
        sessions_dir = Path.home() / ".claude-flow" / project_name / "web-sessions"
        cache_key = str(sessions_dir)
    else:
        # Fallback: 홈 디렉토리 세션 디렉토리
        sessions_dir = Path.home() / ".claude-flow" / "web-sessions"
        cache_key = "~default"

    # 캐시에서 인스턴스 반환 (없으면 새로 생성)
    if cache_key not in _session_stores:
        logger.info(f"새 세션 저장소 생성: {sessions_dir}")
        _session_stores[cache_key] = WorkflowSessionStore(sessions_dir)

    return _session_stores[cache_key]
