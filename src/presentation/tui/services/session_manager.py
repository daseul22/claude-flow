"""세션 관리 시스템"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field

from .session_helpers import AtomicFileWriter, SessionSerializer
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)


@dataclass
class Message:
    """대화 메시지"""

    role: str  # "user" or "assistant"
    content: str
    timestamp: str
    tokens: Dict[str, int] = field(default_factory=lambda: {"input": 0, "output": 0})
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class FeedbackLoopConfig:
    """피드백 루프 설정"""

    enabled: bool = False
    condition_prompt: str = ""
    condition_model: str = "claude-haiku-4-5-20251001"
    max_iterations: int = 3
    current_iteration: int = 0
    feedback_input: str = ""  # 회귀 시 에이전트에게 전달할 입력


@dataclass
class Session:
    """세션 데이터"""

    session_id: str
    project_name: str
    project_path: str
    working_directory: str
    model: str
    created_at: str
    updated_at: str
    claude_md_loaded: bool = False
    messages: List[Message] = field(default_factory=list)
    feedback_loop: FeedbackLoopConfig = field(default_factory=FeedbackLoopConfig)
    total_tokens: Dict[str, int] = field(default_factory=lambda: {"input": 0, "output": 0})


class SessionManager:
    """세션 관리자"""

    def __init__(self, sessions_dir: Path):
        self.sessions_dir = sessions_dir
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.current_session: Optional[Session] = None

        # 세션 통계 추적 (SDK 세션 ID별)
        self._session_stats: Dict[str, Dict[str, Any]] = {}
        # {sdk_session_id: SessionStats dict}

    def create_session(
        self,
        project_name: str,
        project_path: str,
        working_directory: str,
        model: str = "claude-sonnet-4.5",
        claude_md_loaded: bool = False,
        feedback_loop: Optional[FeedbackLoopConfig] = None,
    ) -> Session:
        """새 세션 생성"""
        session_id = str(uuid.uuid4())
        now = datetime.now().isoformat()

        session = Session(
            session_id=session_id,
            project_name=project_name,
            project_path=project_path,
            working_directory=working_directory,
            model=model,
            created_at=now,
            updated_at=now,
            claude_md_loaded=claude_md_loaded,
            feedback_loop=feedback_loop or FeedbackLoopConfig(),
        )

        self.current_session = session
        self.save_session(session)
        return session

    def add_message(
        self,
        role: str,
        content: str,
        tokens: Optional[Dict[str, int]] = None,
        tool_calls: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """메시지 추가"""
        if not self.current_session:
            raise ValueError("활성 세션이 없습니다")

        message = Message(
            role=role,
            content=content,
            timestamp=datetime.now().isoformat(),
            tokens=tokens or {"input": 0, "output": 0},
            tool_calls=tool_calls or [],
        )

        self.current_session.messages.append(message)
        self.current_session.updated_at = datetime.now().isoformat()

        # 총 토큰 업데이트
        self.current_session.total_tokens["input"] += message.tokens["input"]
        self.current_session.total_tokens["output"] += message.tokens["output"]

        # 자동 저장
        self.save_session(self.current_session)

    def save_session(self, session: Session, max_retries: int = 3) -> bool:
        """세션 저장 (재시도 로직 포함)

        Returns:
            bool: 저장 성공 여부
        """
        session_file = self.sessions_dir / f"{session.session_id}.json"

        # 직렬화
        try:
            session_dict = SessionSerializer.to_dict(session)
        except Exception as e:
            import sys

            print(
                f"[CRITICAL] 세션 직렬화 실패: {e}\n" f"세션 ID: {session.session_id}",
                file=sys.stderr,
            )
            return False

        # 원자적 쓰기
        writer = AtomicFileWriter(session_file)
        return writer.write_with_retry(session_dict, max_retries)

    def load_session(self, session_id: str) -> Session:
        """세션 불러오기"""
        session_file = self.sessions_dir / f"{session_id}.json"

        if not session_file.exists():
            raise FileNotFoundError(f"세션을 찾을 수 없습니다: {session_id}")

        with open(session_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        messages = [Message(**msg) for msg in data.get("messages", [])]

        feedback_loop = FeedbackLoopConfig(**data.get("feedback_loop", {}))

        session = Session(
            session_id=data["session_id"],
            project_name=data["project_name"],
            project_path=data["project_path"],
            working_directory=data["working_directory"],
            model=data["model"],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            claude_md_loaded=data.get("claude_md_loaded", False),
            messages=messages,
            feedback_loop=feedback_loop,
            total_tokens=data.get("total_tokens", {"input": 0, "output": 0}),
        )

        self.current_session = session
        return session

    def list_sessions(self) -> List[Dict[str, Any]]:
        """세션 목록 반환 (최근 순)"""
        sessions = []

        for session_file in self.sessions_dir.glob("*.json"):
            try:
                with open(session_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                sessions.append(
                    {
                        "session_id": data["session_id"],
                        "created_at": data["created_at"],
                        "updated_at": data["updated_at"],
                        "message_count": len(data.get("messages", [])),
                        "total_tokens": data.get("total_tokens", {"input": 0, "output": 0}),
                        "first_message": (
                            data["messages"][0]["content"] if data.get("messages") else ""
                        ),
                    }
                )
            except Exception:
                continue

        # 최근 순 정렬
        sessions.sort(key=lambda x: x["updated_at"], reverse=True)
        return sessions

    def delete_session(self, session_id: str) -> None:
        """세션 삭제"""
        try:
            session_file = self.sessions_dir / f"{session_id}.json"
            if session_file.exists():
                session_file.unlink()
        except Exception as e:
            print(f"세션 삭제 실패: {e}")

    def get_session_stats(self) -> Dict[str, Any]:
        """세션 통계 (전체 세션 수, 토큰 등)"""
        sessions = self.list_sessions()
        total_tokens = sum(
            s["total_tokens"]["input"] + s["total_tokens"]["output"] for s in sessions
        )

        return {
            "total_sessions": len(sessions),
            "total_tokens": total_tokens,
            "sessions_today": sum(
                1
                for s in sessions
                if s["created_at"].startswith(datetime.now().strftime("%Y-%m-%d"))
            ),
        }

    # ========================================================================
    # 세션 통계 및 컨텍스트 윈도우 추적
    # ========================================================================

    def update_session_stats(
        self,
        sdk_session_id: str,
        model: str,
        usage_dict: Dict[str, int],
    ) -> Optional[Dict[str, Any]]:
        """SDK 세션 통계 업데이트 (토큰 누적 및 컴팩션 감지)

        Args:
            sdk_session_id: SDK 세션 ID
            model: 모델 이름 (예: "claude-sonnet-4-5-20250929")
            usage_dict: 토큰 사용량 딕셔너리
                {
                    "input_tokens": int,
                    "output_tokens": int,
                    "cache_read_tokens": int,
                    "cache_creation_tokens": int,
                }

        Returns:
            Dict[str, Any]: 컴팩션 이벤트 (발생 시) 또는 None
        """
        timestamp = datetime.now().isoformat()

        # 초기화
        if sdk_session_id not in self._session_stats:
            self._session_stats[sdk_session_id] = {
                "sdk_session_id": sdk_session_id,
                "model": model,
                "token_history": [],
                "compaction_events": [],
                "cumulative_input_tokens": 0,
                "cumulative_output_tokens": 0,
                "cumulative_cache_read_tokens": 0,
                "cumulative_cache_creation_tokens": 0,
                "cumulative_total_tokens": 0,
                "estimated_context_window_usage": 0.0,
                "created_at": timestamp,
                "last_updated_at": timestamp,
            }
            logger.info(f"[SessionStats] 새 세션 통계 초기화: {sdk_session_id[:8]}...")

        stats = self._session_stats[sdk_session_id]

        # 이전 누적 토큰 (컴팩션 감지용)
        prev_cumulative_total = stats["cumulative_total_tokens"]
        prev_cache_read = stats["cumulative_cache_read_tokens"]

        # 토큰 누적
        stats["cumulative_input_tokens"] += usage_dict.get("input_tokens", 0)
        stats["cumulative_output_tokens"] += usage_dict.get("output_tokens", 0)
        stats["cumulative_cache_read_tokens"] += usage_dict.get("cache_read_tokens", 0)
        stats["cumulative_cache_creation_tokens"] += usage_dict.get("cache_creation_tokens", 0)
        stats["cumulative_total_tokens"] = (
            stats["cumulative_input_tokens"]
            + stats["cumulative_output_tokens"]
            + stats["cumulative_cache_read_tokens"]
        )

        # 토큰 스냅샷 생성
        snapshot = {
            "timestamp": timestamp,
            "input_tokens": usage_dict.get("input_tokens", 0),
            "output_tokens": usage_dict.get("output_tokens", 0),
            "cache_read_tokens": usage_dict.get("cache_read_tokens", 0),
            "cache_creation_tokens": usage_dict.get("cache_creation_tokens", 0),
            "cumulative_input": stats["cumulative_input_tokens"],
            "cumulative_output": stats["cumulative_output_tokens"],
            "cumulative_total": stats["cumulative_total_tokens"],
        }
        stats["token_history"].append(snapshot)

        # 컨텍스트 윈도우 사용률 추정
        stats["estimated_context_window_usage"] = self._estimate_context_window_usage(
            stats["cumulative_total_tokens"], model
        )

        # 컴팩션 감지
        compaction_event = self._detect_compaction(
            timestamp=timestamp,
            prev_cumulative=prev_cumulative_total,
            current_cumulative=stats["cumulative_total_tokens"],
            cache_creation_tokens=usage_dict.get("cache_creation_tokens", 0),
            cache_read_tokens=usage_dict.get("cache_read_tokens", 0),
            prev_cache_read=prev_cache_read,
        )

        if compaction_event:
            stats["compaction_events"].append(compaction_event)
            logger.warning(
                f"[SessionStats] 🔄 컴팩션 감지: {sdk_session_id[:8]}... "
                f"trigger={compaction_event['trigger']}, "
                f"reduction={compaction_event['reduction_tokens']} tokens"
            )

        # 마지막 업데이트 시간
        stats["last_updated_at"] = timestamp

        logger.debug(
            f"[SessionStats] 업데이트: {sdk_session_id[:8]}... "
            f"total={stats['cumulative_total_tokens']}, usage={stats['estimated_context_window_usage']:.1%}"
        )

        return compaction_event

    def _detect_compaction(
        self,
        timestamp: str,
        prev_cumulative: int,
        current_cumulative: int,
        cache_creation_tokens: int,
        cache_read_tokens: int,
        prev_cache_read: int,
    ) -> Optional[Dict[str, Any]]:
        """컴팩션 이벤트 감지 (휴리스틱 기반)

        SDK는 컴팩션 이벤트를 직접 노출하지 않으므로, 토큰 패턴을 분석하여 추론합니다.

        컴팩션 감지 조건:
        1. cache_creation_tokens > 0: 새 캐시 생성 (기존 캐시 재구성 신호)
        2. cache_read_tokens == 0 AND prev > 0: 캐시 리셋 (컨텍스트 윈도우 초기화)
        3. cumulative_total < prev_cumulative: 컨텍스트 윈도우 축소 (직접 감소)

        Args:
            timestamp: 현재 타임스탬프
            prev_cumulative: 이전 누적 토큰 수
            current_cumulative: 현재 누적 토큰 수
            cache_creation_tokens: 캐시 생성 토큰 수
            cache_read_tokens: 캐시 읽기 토큰 수
            prev_cache_read: 이전 캐시 읽기 토큰 수

        Returns:
            Dict[str, Any]: 컴팩션 이벤트 딕셔너리 또는 None
        """
        trigger = None

        # 조건 1: 캐시 재생성 (가장 일반적인 컴팩션 신호)
        if cache_creation_tokens > 0:
            trigger = "cache_creation"

        # 조건 2: 캐시 리셋 (cache_read가 0으로 떨어짐)
        elif cache_read_tokens == 0 and prev_cache_read > 0:
            trigger = "cache_reset"

        # 조건 3: 컨텍스트 윈도우 직접 감소
        elif current_cumulative < prev_cumulative:
            trigger = "context_limit"

        if trigger:
            reduction_tokens = max(prev_cumulative - current_cumulative, 0)
            return {
                "timestamp": timestamp,
                "trigger": trigger,
                "before_tokens": prev_cumulative,
                "after_tokens": current_cumulative,
                "reduction_tokens": reduction_tokens,
                "cache_creation_tokens": cache_creation_tokens,
            }

        return None

    def _estimate_context_window_usage(self, cumulative_total: int, model: str) -> float:
        """컨텍스트 윈도우 사용률 추정 (0.0 ~ 1.0)

        Args:
            cumulative_total: 누적 총 토큰 수
            model: 모델 이름

        Returns:
            float: 사용률 (0.0 ~ 1.0)
        """
        # 모델별 컨텍스트 한계 (토큰)
        context_limits = {
            "claude-sonnet-4-5-20250929": 200000,
            "claude-opus-4-5-20250514": 200000,
            "claude-haiku-4-5-20251001": 200000,
            "default": 200000,
        }

        limit = context_limits.get(model, context_limits["default"])
        return min(cumulative_total / limit, 1.0)

    def get_current_sdk_session_stats(self, sdk_session_id: str) -> Optional[Dict[str, Any]]:
        """현재 SDK 세션 통계 조회

        Args:
            sdk_session_id: SDK 세션 ID

        Returns:
            Dict[str, Any]: 세션 통계 딕셔너리 또는 None
        """
        return self._session_stats.get(sdk_session_id)
