"""세션 관리 시스템"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict, field


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
        backup_file = self.sessions_dir / f"{session.session_id}.json.backup"

        # 세션 데이터 직렬화
        try:
            session_dict = {
                "session_id": session.session_id,
                "project_name": session.project_name,
                "project_path": session.project_path,
                "working_directory": session.working_directory,
                "model": session.model,
                "created_at": session.created_at,
                "updated_at": session.updated_at,
                "claude_md_loaded": session.claude_md_loaded,
                "messages": [
                    {
                        "role": msg.role,
                        "content": msg.content,
                        "timestamp": msg.timestamp,
                        "tokens": msg.tokens,
                        "tool_calls": msg.tool_calls,
                    }
                    for msg in session.messages
                ],
                "feedback_loop": asdict(session.feedback_loop),
                "total_tokens": session.total_tokens,
            }
        except Exception as e:
            import sys
            print(
                f"[CRITICAL] 세션 데이터 직렬화 실패: {e}\n"
                f"세션 ID: {session.session_id}",
                file=sys.stderr
            )
            return False

        # 재시도 로직
        for attempt in range(max_retries):
            try:
                # 기존 파일이 있으면 백업 생성
                if session_file.exists():
                    import shutil
                    shutil.copy2(session_file, backup_file)

                # 임시 파일에 먼저 저장 (원자적 쓰기)
                temp_file = session_file.with_suffix('.json.tmp')
                with open(temp_file, "w", encoding="utf-8") as f:
                    json.dump(session_dict, f, indent=2, ensure_ascii=False)

                # 검증: 저장된 파일 읽기 테스트
                with open(temp_file, "r", encoding="utf-8") as f:
                    json.load(f)  # 파싱 가능한지 확인

                # 임시 파일을 실제 파일로 이동 (원자적 연산)
                temp_file.replace(session_file)

                # 백업 파일 삭제 (성공 시)
                if backup_file.exists():
                    backup_file.unlink()

                return True

            except (IOError, OSError, PermissionError) as e:
                # 파일 시스템 에러 (디스크 가득 참, 권한 부족 등)
                if attempt < max_retries - 1:
                    # 재시도
                    import time
                    time.sleep(0.1 * (attempt + 1))  # 지수 백오프
                    continue
                else:
                    # 최종 실패
                    import sys
                    error_msg = (
                        f"[CRITICAL] 세션 저장 실패 ({max_retries}회 재시도 후):\n"
                        f"  세션 ID: {session.session_id}\n"
                        f"  파일: {session_file}\n"
                        f"  에러: {e}\n"
                    )

                    # 백업 파일이 있으면 알림
                    if backup_file.exists():
                        error_msg += f"  백업: {backup_file} (이전 상태 보존됨)\n"

                    print(error_msg, file=sys.stderr)
                    return False

            except Exception as e:
                # 예상치 못한 에러
                import sys
                import traceback
                print(
                    f"[CRITICAL] 세션 저장 중 예상치 못한 에러:\n"
                    f"  세션 ID: {session.session_id}\n"
                    f"  에러: {e}\n"
                    f"  트레이스:\n{traceback.format_exc()}",
                    file=sys.stderr
                )
                return False

        return False

    def load_session(self, session_id: str) -> Session:
        """세션 불러오기"""
        session_file = self.sessions_dir / f"{session_id}.json"

        if not session_file.exists():
            raise FileNotFoundError(f"세션을 찾을 수 없습니다: {session_id}")

        with open(session_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        messages = [
            Message(**msg)
            for msg in data.get("messages", [])
        ]

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

                sessions.append({
                    "session_id": data["session_id"],
                    "created_at": data["created_at"],
                    "updated_at": data["updated_at"],
                    "message_count": len(data.get("messages", [])),
                    "total_tokens": data.get("total_tokens", {"input": 0, "output": 0}),
                    "first_message": data["messages"][0]["content"] if data.get("messages") else "",
                })
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
        """세션 통계"""
        sessions = self.list_sessions()
        total_tokens = sum(
            s["total_tokens"]["input"] + s["total_tokens"]["output"]
            for s in sessions
        )

        return {
            "total_sessions": len(sessions),
            "total_tokens": total_tokens,
            "sessions_today": sum(
                1 for s in sessions
                if s["created_at"].startswith(datetime.now().strftime("%Y-%m-%d"))
            ),
        }

