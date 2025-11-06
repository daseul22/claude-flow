"""Claude Flow TUI 메인 앱"""

import asyncio
from pathlib import Path
from typing import Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container

from .components.status_bar import StatusBar
from .components.chat_view import ChatView
from .components.input_box import InputBox
from .components.modals.session_list import SessionListModal
from .config.settings import ConfigManager
from .services.session_manager import SessionManager
from .services.agent_client import AgentClient
from .services.logger import SessionLogger, LogManager
from .services.project_utils import get_project_info
from .services.feedback_loop import FeedbackLoop


class ClaudeFlowApp(App):
    """Claude Flow TUI 메인 애플리케이션"""

    CSS = """
    Screen {
        background: $background;
    }

    #main-container {
        width: 100%;
        height: 100%;
    }
    """

    BINDINGS = [
        Binding("ctrl+n", "new_session", "새 세션"),
        Binding("ctrl+o", "open_session", "세션 불러오기"),
        Binding("ctrl+i", "project_info", "프로젝트 정보"),
        Binding("ctrl+l", "clear_screen", "화면 지우기"),
        Binding("ctrl+c", "interrupt", "중단"),
        Binding("ctrl+q", "quit", "종료"),
    ]

    def __init__(self, project_path: Path, **kwargs):
        super().__init__(**kwargs)
        self.project_path = project_path.absolute()

        # 설정
        self.config = ConfigManager()

        # 프로젝트 정보 가져오기
        project_info = get_project_info(self.project_path)
        self.project_name = project_info["name"]
        self.git_info = project_info["git"]
        self.claude_md_content = project_info["claude_md_content"]

        # 세션 관리자
        sessions_dir = self.config.get_project_sessions_dir(self.project_name)
        self.session_manager = SessionManager(sessions_dir)

        # 로그 관리자
        logs_dir = self.config.get_project_logs_dir(self.project_name)
        self.log_manager = LogManager(logs_dir)
        self.logger: Optional[SessionLogger] = None

        # 에이전트 클라이언트
        self.agent: Optional[AgentClient] = None

        # 피드백 루프
        self.feedback_loop: Optional[FeedbackLoop] = None

        # 현재 작업
        self.current_task: Optional[asyncio.Task] = None

    def compose(self) -> ComposeResult:
        """UI 구성"""
        with Container(id="main-container"):
            yield ChatView(
                show_timestamps=self.config.config.display.show_timestamps
            )
            yield InputBox()
            yield StatusBar()

    async def on_mount(self) -> None:
        """앱 마운트 시"""
        # 새 세션 생성
        await self.create_new_session()

        # 환영 메시지
        chat_view = self.query_one(ChatView)
        chat_view.add_system_message(
            f"Claude Flow TUI v1.0 시작됨\n"
            f"프로젝트: {self.project_name}\n"
            f"경로: {self.project_path}",
            style="cyan"
        )

        if self.git_info:
            chat_view.add_system_message(
                f"Git 브랜치: {self.git_info['branch']}",
                style="dim"
            )

        if self.claude_md_content:
            chat_view.add_system_message(
                "✓ CLAUDE.md 로드됨",
                style="green"
            )

        # 입력창 포커스
        self.query_one(InputBox).focus()

    async def create_new_session(self):
        """새 세션 생성"""
        # 세션 생성
        session = self.session_manager.create_session(
            project_name=self.project_name,
            project_path=str(self.project_path),
            working_directory=str(self.project_path),
            model=self.config.config.default_model,
            claude_md_loaded=self.claude_md_content is not None,
        )

        # 로거 생성
        logs_dir = self.config.get_project_logs_dir(self.project_name)
        self.logger = SessionLogger(
            logs_dir=logs_dir,
            session_id=session.session_id,
            log_level=self.config.config.logging.log_level,
            max_file_size_mb=self.config.config.logging.max_file_size_mb,
        )

        # 에이전트 클라이언트 생성
        self.agent = AgentClient(
            project_path=self.project_path,
            model=session.model,
            claude_md_content=self.claude_md_content,
        )

        # 피드백 루프 생성
        if self.config.config.feedback_loop_defaults.enabled:
            self.feedback_loop = FeedbackLoop(
                project_path=self.project_path,
                condition_model=self.config.config.feedback_loop_defaults.condition_model,
                max_iterations=self.config.config.feedback_loop_defaults.max_iterations,
            )

        # 상태바 업데이트
        status_bar = self.query_one(StatusBar)
        git_branch = self.git_info["branch"] if self.git_info else ""
        status_bar.update_project(self.project_name, git_branch)
        status_bar.update_session(session.session_id)

        self.logger.log_event("new_session", {
            "session_id": session.session_id,
            "project": self.project_name,
        })

    async def on_input_box_submitted(self, message: InputBox.Submitted) -> None:
        """메시지 전송 처리"""
        user_message = message.text
        chat_view = self.query_one(ChatView)

        # 사용자 메시지 표시
        chat_view.add_user_message(user_message)

        # 세션에 저장
        self.session_manager.add_message(
            role="user",
            content=user_message,
            tokens={"input": len(user_message.split()), "output": 0},  # 간단한 추정
        )

        # 로그
        self.logger.log_message("user", user_message)

        # 에이전트 응답
        await self.get_agent_response(user_message)

    async def get_agent_response(self, user_message: str):
        """에이전트 응답 받기"""
        chat_view = self.query_one(ChatView)

        try:
            # 응답 수집
            response_text = ""

            # 스트리밍 응답
            async for chunk in self.agent.send_message(
                user_message,
                on_token=lambda token: None,  # 실시간 표시는 나중에
            ):
                response_text += chunk

            # 어시스턴트 메시지 표시
            chat_view.add_assistant_message(response_text)

            # 세션에 저장
            self.session_manager.add_message(
                role="assistant",
                content=response_text,
                tokens={"input": 0, "output": len(response_text.split())},
            )

            # 로그
            self.logger.log_message("assistant", response_text)

            # 상태바 업데이트 (토큰)
            session = self.session_manager.current_session
            if session:
                total_input = session.total_tokens["input"]
                total_output = session.total_tokens["output"]
                cost = self.agent.estimate_cost(total_input, total_output)

                status_bar = self.query_one(StatusBar)
                status_bar.update_tokens(total_input, total_output, cost)

        except Exception as e:
            chat_view.add_error_message(str(e))
            self.logger.log_error(e)

    async def action_new_session(self) -> None:
        """새 세션 생성"""
        chat_view = self.query_one(ChatView)
        chat_view.add_system_message("새 세션을 시작합니다...")
        await self.create_new_session()

    async def action_open_session(self) -> None:
        """세션 불러오기"""
        sessions = self.session_manager.list_sessions()

        if not sessions:
            chat_view = self.query_one(ChatView)
            chat_view.add_system_message("저장된 세션이 없습니다.", style="yellow")
            return

        # 세션 목록 모달 표시
        modal = SessionListModal(sessions)
        await self.push_screen(modal)

    async def action_project_info(self) -> None:
        """프로젝트 정보 표시"""
        chat_view = self.query_one(ChatView)

        stats = self.session_manager.get_session_stats()

        info = f"""
📁 프로젝트: {self.project_name}
📂 경로: {self.project_path}
📊 총 세션 수: {stats['total_sessions']}
🪙 총 토큰: {stats['total_tokens']:,}
📅 오늘 세션: {stats['sessions_today']}
"""

        if self.git_info:
            info += f"🔀 Git 브랜치: {self.git_info['branch']}\n"

        chat_view.add_system_message(info.strip(), style="cyan")

    async def action_clear_screen(self) -> None:
        """화면 지우기"""
        chat_view = self.query_one(ChatView)
        chat_view.clear_messages()
        chat_view.add_system_message("화면이 지워졌습니다. (대화 기록은 유지됨)", style="dim")

    async def action_interrupt(self) -> None:
        """현재 작업 중단"""
        input_box = self.query_one(InputBox)

        # 입력 중이면 입력창 초기화
        if input_box.text:
            input_box.clear_input()
            chat_view = self.query_one(ChatView)
            chat_view.add_system_message("입력이 취소되었습니다.", style="yellow")
            return

        # 실행 중인 작업 중단
        if self.current_task and not self.current_task.done():
            self.current_task.cancel()
            chat_view = self.query_one(ChatView)
            chat_view.add_system_message("작업이 중단되었습니다.", style="yellow")
            return

        # 아무것도 없으면 종료 확인
        await self.action_quit()

    async def action_quit(self) -> None:
        """앱 종료"""
        chat_view = self.query_one(ChatView)
        chat_view.add_system_message("Claude Flow를 종료합니다...", style="yellow")
        await asyncio.sleep(0.5)
        self.exit()

