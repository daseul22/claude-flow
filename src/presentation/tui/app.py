"""Claude Flow TUI 메인 앱"""

import asyncio
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.worker import Worker, WorkerState
from rich.text import Text

from .components.status_bar import StatusBar
from .components.chat_view import ChatView
from .components.input_box import InputBox
from .components.modals.session_list import SessionListModal
from .components.modals.settings_modal import SettingsModal
from .components.modals.help_modal import HelpModal
from .config.settings import ConfigManager
from .services.session_manager import SessionManager
from .services.agent_client import AgentClient
from .services.logger import SessionLogger, LogManager
from .services.project_utils import get_project_info
from .services.feedback_loop import FeedbackLoop
from .services.response_parser import ResponseParser


class ClaudeFlowApp(App):
    """Claude Flow TUI 메인 애플리케이션"""

    CSS = """
    Screen {
        background: $background;
        layout: vertical;
    }

    #main-container {
        width: 100%;
        height: 100%;
        layout: vertical;
    }
    
    Container {
        width: 100%;
        height: 100%;
    }
    
    ChatView {
        height: 1fr;
    }
    
    InputBox {
        height: 5;
        margin-bottom: 1;
    }
    """

    BINDINGS = [
        Binding("ctrl+n", "new_session", "새 세션"),
        Binding("ctrl+o", "open_session", "세션 불러오기"),
        Binding("ctrl+i", "project_info", "프로젝트 정보"),
        Binding("ctrl+s", "settings", "설정"),
        Binding("ctrl+slash", "help", "도움말"),
        Binding("f1", "help", "도움말"),
        Binding("ctrl+l", "clear_screen", "화면 지우기"),
        Binding("ctrl+c", "interrupt", "중단"),
        Binding("ctrl+q", "quit", "종료"),
    ]

    def __init__(self, project_path: Path, **kwargs):
        super().__init__(**kwargs)
        self.project_path = project_path.absolute()
        self.initial_project_path = self.project_path  # 초기 프로젝트 경로 저장

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
        self.current_worker: Optional[Worker] = None  # 현재 실행 중인 Worker
        self.is_processing: bool = False  # 응답 처리 중 플래그
        self.should_stop: bool = False  # 중단 요청 플래그

        # 디렉토리 히스토리 (cd - 용)
        self.directory_history: list[Path] = []

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
        # 터미널 크기 확인
        size = self.size
        if size.width < 80 or size.height < 24:
            chat_view = self.query_one(ChatView)
            chat_view.add_system_message(
                f"⚠️  터미널 크기가 작습니다 (현재: {size.width}x{size.height})\n"
                f"권장 최소 크기: 80x24\n"
                f"터미널 크기를 조정해주세요.",
                style="yellow"
            )

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

    async def on_resize(self, event) -> None:
        """터미널 크기 변경 시"""
        # 자동으로 레이아웃 조정됨 (Textual이 처리)
        pass
    
    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        """Worker 상태 변경 감지"""
        worker = event.worker
        
        # Worker가 시작되면 처리 중 플래그 설정
        if worker.state == WorkerState.RUNNING:
            if worker.name == "agent_response":
                self.is_processing = True
        
        # Worker가 완료/취소되면 플래그 초기화
        elif worker.state in (WorkerState.SUCCESS, WorkerState.CANCELLED, WorkerState.ERROR):
            if worker.name == "agent_response":
                self.is_processing = False
                self.should_stop = False
                
                # 취소된 경우
                if worker.state == WorkerState.CANCELLED:
                    chat_view = self.query_one(ChatView)
                    chat_view.add_system_message("✓ 응답이 중단되었습니다.", style="yellow")
                
                # 에러 발생
                elif worker.state == WorkerState.ERROR and worker.error:
                    chat_view = self.query_one(ChatView)
                    chat_view.add_error_message(f"Worker 에러: {worker.error}")

    async def create_new_session(self):
        """새 세션 생성"""
        # 피드백 루프 설정 준비
        from .services.session_manager import FeedbackLoopConfig
        feedback_loop_config = FeedbackLoopConfig(
            enabled=self.config.config.feedback_loop_defaults.enabled,
            condition_prompt="",
            condition_model=self.config.config.feedback_loop_defaults.condition_model,
            max_iterations=self.config.config.feedback_loop_defaults.max_iterations,
            current_iteration=0,
            feedback_input="",
        )
        
        # 세션 생성
        session = self.session_manager.create_session(
            project_name=self.project_name,
            project_path=str(self.project_path),
            working_directory=str(self.project_path),
            model=self.config.config.default_model,
            claude_md_loaded=self.claude_md_content is not None,
            feedback_loop=feedback_loop_config,
        )

        # 로거 생성
        logs_dir = self.config.get_project_logs_dir(self.project_name)
        self.logger = SessionLogger(
            logs_dir=logs_dir,
            session_id=session.session_id,
            log_level=self.config.config.logging.log_level,
            max_file_size_mb=self.config.config.logging.max_file_size_mb,
        )

        # 에이전트 클라이언트 생성 (또는 재사용)
        if self.agent is None:
            self.agent = AgentClient(
                project_path=self.project_path,
                model=session.model,
                claude_md_content=self.claude_md_content,
                enable_thinking=self.config.config.display.enable_thinking,
            )
        else:
            # 기존 에이전트 세션 초기화 (새 세션이므로 맥락 리셋)
            self.agent.reset_session()

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
        status_bar.update_feedback_loop(session.feedback_loop.enabled)

        if self.logger:
            self.logger.log_event("new_session", {
                "session_id": session.session_id,
                "project": self.project_name,
            })

    async def on_input_box_submitted(self, message: InputBox.Submitted) -> None:
        """메시지 전송 처리"""
        user_message = message.text
        chat_view = self.query_one(ChatView)

        # cd 명령어 처리
        if user_message.strip().startswith("cd "):
            await self.handle_cd_command(user_message.strip())
            return

        # 사용자 메시지 표시
        chat_view.add_user_message(user_message)

        # 세션에 저장
        self.session_manager.add_message(
            role="user",
            content=user_message,
            tokens={"input": len(user_message.split()), "output": 0},  # 간단한 추정
        )

        # 로그
        if self.logger:
            self.logger.log_message("user", user_message)

        # 에이전트 응답 (Worker로 실행)
        self.current_worker = self.run_worker(
            self.get_agent_response(user_message),
            name="agent_response",
            group="agent",
            exclusive=True,  # 같은 그룹의 다른 워커 취소
        )

    async def handle_cd_command(self, command: str):
        """cd 명령어 처리"""
        chat_view = self.query_one(ChatView)
        
        # 경로 추출
        path_str = command[3:].strip()
        
        if not path_str:
            # 현재 디렉토리 표시
            chat_view.add_system_message(f"현재 디렉토리: {self.project_path}", style="cyan")
            return

        try:
            # cd - (이전 디렉토리)
            if path_str == "-":
                if not self.directory_history:
                    chat_view.add_system_message("이전 디렉토리가 없습니다.", style="yellow")
                    return
                
                new_path = self.directory_history.pop()
                
            # 경로 해석
            elif path_str == "~":
                new_path = Path.home()
            elif path_str == "..":
                new_path = self.project_path.parent
            elif path_str.startswith("~"):
                new_path = Path.home() / path_str[2:]
            elif path_str.startswith("/"):
                new_path = Path(path_str)
            else:
                new_path = self.project_path / path_str

            # 경로 검증
            if not new_path.exists():
                chat_view.add_error_message(f"디렉토리를 찾을 수 없습니다: {new_path}")
                return

            if not new_path.is_dir():
                chat_view.add_error_message(f"디렉토리가 아닙니다: {new_path}")
                return
            
            # 권한 검증 (읽기/쓰기 가능 여부)
            if not os.access(new_path, os.R_OK):
                chat_view.add_system_message(
                    f"⚠️  읽기 권한이 없습니다: {new_path}",
                    style="yellow"
                )
            
            if not os.access(new_path, os.W_OK):
                chat_view.add_system_message(
                    f"⚠️  쓰기 권한이 없습니다: {new_path}",
                    style="yellow"
                )

            # 작업 디렉토리 변경
            old_path = self.project_path
            
            # cd - 가 아닌 경우에만 히스토리에 추가
            if path_str != "-":
                self.directory_history.append(old_path)
                # 히스토리는 최대 10개만 유지
                if len(self.directory_history) > 10:
                    self.directory_history.pop(0)
            
            self.project_path = new_path.absolute()

            # 프로젝트 루트 외부 이동 경고
            try:
                new_path.relative_to(self.initial_project_path)
            except ValueError:
                # 프로젝트 루트 외부
                chat_view.add_system_message(
                    "⚠️  프로젝트 루트 외부로 이동했습니다.\n"
                    f"초기 프로젝트: {self.initial_project_path}",
                    style="yellow"
                )

            # 세션 업데이트
            if self.session_manager.current_session:
                self.session_manager.current_session.working_directory = str(self.project_path)
                self.session_manager.save_session(self.session_manager.current_session)

            # 알림
            chat_view.add_system_message(
                f"작업 디렉토리 변경:\n  {old_path}\n  → {self.project_path}",
                style="green"
            )

            # 로그
            if self.logger:
                self.logger.log_event("cd", {"from": str(old_path), "to": str(self.project_path)})

        except Exception as e:
            chat_view.add_error_message(f"디렉토리 변경 실패: {str(e)}")

    async def get_agent_response(self, user_message: str) -> None:
        """에이전트 응답 받기 (실시간 스트리밍) - Worker에서 실행"""
        from textual.worker import get_current_worker
        
        chat_view = self.query_one(ChatView)
        worker = get_current_worker()
        
        # 처리 중 플래그 설정
        self.is_processing = True
        self.should_stop = False

        try:
            # 응답 헤더 추가
            self._add_response_header(chat_view)

            # 피드백 루프 활성화 확인
            session = self.session_manager.current_session
            use_feedback_loop = (
                self.feedback_loop is not None 
                and session 
                and session.feedback_loop.enabled
            )

            # 피드백 루프 활성화했지만 조건 프롬프트 없음
            if use_feedback_loop and not session.feedback_loop.condition_prompt.strip():
                chat_view.add_error_message(
                    "⚠️  피드백 루프가 활성화되었지만 조건 프롬프트가 없습니다.\n"
                    "Ctrl+,로 설정에서 '조건 프롬프트'를 입력하세요."
                )
                use_feedback_loop = False

            # 실시간 스트리밍 응답
            response_text = ""

            # 블록 처리용 파서
            parser = ResponseParser()

            # 콜백 함수들
            def on_thinking_callback(thinking: str):
                show_full = self.config.config.display.show_thinking_full
                formatted = parser.format_thinking_block(thinking, show_full=show_full)
                chat_view.write(formatted)  # Rich Text 객체는 그대로
                chat_view.write("")  # 블록 간 간격

            def on_tool_use_callback(tool_name: str, tool_input: dict):
                formatted = parser.format_tool_use(tool_name, tool_input)
                chat_view.write(formatted)  # Rich Text 객체는 그대로
                chat_view.write("")  # 블록 간 간격

            def on_tool_result_callback(result: str):
                formatted = parser.format_tool_result("", result)
                chat_view.write(formatted)  # Rich Text 객체는 그대로
                chat_view.write("")  # 블록 간 간격

            if use_feedback_loop:
                # 피드백 루프 사용
                chat_view.add_system_message(
                    f"🔁 피드백 루프 활성화 (최대 {session.feedback_loop.max_iterations}회)",
                    style="yellow"
                )

                # 평가 LLM 출력 콜백
                def on_eval_start():
                    """평가 시작"""
                    from rich.text import Text
                    eval_header = Text("\n", style="")
                    eval_header.append("━" * 60, style="dim yellow")
                    eval_header.append("\n🔍 ", style="yellow")
                    eval_header.append("조건 평가 중...", style="bold yellow")
                    chat_view.write(eval_header)
                
                def on_eval_output(chunk: str):
                    """평가 LLM 출력"""
                    chat_view.write_wrapped(chunk)
                
                def on_eval_result(condition_met: bool, eval_response: str):
                    """평가 결과"""
                    from rich.text import Text
                    result_text = Text()
                    if condition_met:
                        result_text.append("✅ 조건 충족", style="bold green")
                    else:
                        result_text.append("❌ 조건 미충족 - 재시도 필요", style="bold red")
                    result_text.append("\n", style="")
                    result_text.append("━" * 60, style="dim yellow")
                    chat_view.write(result_text)

                iteration = 0
                async for chunk in self.feedback_loop.run_with_feedback(
                    agent=self.agent,
                    initial_message=user_message,
                    condition_prompt=session.feedback_loop.condition_prompt,
                    feedback_input=session.feedback_loop.feedback_input,
                    on_iteration=lambda iter_num, status: chat_view.add_system_message(
                        f"🔄 반복 {iter_num}: {status}",
                        style="dim"
                    ),
                    on_thinking=on_thinking_callback,
                    on_tool_use=on_tool_use_callback,
                    on_eval_start=on_eval_start,
                    on_eval_output=on_eval_output,
                    on_eval_result=on_eval_result,
                ):
                    # Worker 취소 체크 (Ctrl+C 즉시 반응)
                    if worker.is_cancelled or self.should_stop:
                        return
                    
                    response_text += chunk
                    chat_view.write_wrapped(chunk)  # 문자열은 줄바꿈 처리
            else:
                # 일반 응답
                async for chunk in self.agent.send_message(
                    user_message,
                    on_thinking=on_thinking_callback,
                    on_tool_use=on_tool_use_callback,
                    on_tool_result=on_tool_result_callback,
                ):
                    # Worker 취소 체크 (Ctrl+C 즉시 반응)
                    if worker.is_cancelled or self.should_stop:
                        return
                    
                    response_text += chunk
                    chat_view.write_wrapped(chunk)  # 문자열은 줄바꿈 처리

            # 세션에 저장
            self.session_manager.add_message(
                role="assistant",
                content=response_text,
                tokens={"input": 0, "output": len(response_text.split())},
            )

            # 로그
            if self.logger:
                self.logger.log_message("assistant", response_text)

            # 상태바 업데이트 (토큰)
            self._update_token_display(len(response_text))

        except Exception as e:
            chat_view.add_error_message(str(e))
            if self.logger:
                self.logger.log_error(e)
        finally:
            # 처리 완료
            self.is_processing = False
            self.should_stop = False

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

        # 세션 목록 모달 표시 (callback 방식)
        def on_session_selected(result):
            """세션 선택 콜백"""
            if result is None:
                return
            
            # 삭제 액션 처리
            if isinstance(result, str) and result.startswith("DELETE:"):
                session_id = result[7:]  # "DELETE:" 제거
                self._delete_session_sync(session_id)
            # 세션 선택
            else:
                self.load_selected_session(result)

        modal = SessionListModal(sessions)
        self.push_screen(modal, callback=on_session_selected)

    def _delete_session_sync(self, session_id: str) -> None:
        """세션 삭제 (동기 버전, callback에서 호출)"""
        chat_view = self.query_one(ChatView)
        
        try:
            # 세션 삭제
            self.session_manager.delete_session(session_id)
            
            # 알림
            chat_view.add_system_message(
                f"✅ 세션 {session_id[:8]}이(가) 삭제되었습니다.",
                style="green"
            )
            
            # 로그
            if self.logger:
                self.logger.log_event("session_deleted", {"session_id": session_id})
                
        except Exception as e:
            chat_view.add_error_message(f"세션 삭제 실패: {str(e)}")

    def load_selected_session(self, session_id: str) -> None:
        """선택된 세션 불러오기"""
        chat_view = self.query_one(ChatView)
        
        try:
            # 세션 로드
            session = self.session_manager.load_session(session_id)
            
            # SDK 세션 초기화 (다른 세션이므로 맥락 리셋)
            if self.agent:
                self.agent.reset_session()

            # 대화 기록 복원
            chat_view.clear_messages()
            chat_view.add_system_message(f"세션 {session_id[:8]} 불러옴", style="green")

            # 메시지 복원
            for msg in session.messages:
                timestamp = self._format_timestamp(msg.timestamp)
                
                if msg.role == "user":
                    chat_view.add_user_message(msg.content, timestamp)
                elif msg.role == "assistant":
                    chat_view.add_assistant_message(msg.content, timestamp)

            # 상태바 업데이트
            if self.agent:
                status_bar = self.query_one(StatusBar)
                status_bar.update_session(session.session_id)
                cost = self.agent.estimate_cost(
                    session.total_tokens["input"],
                    session.total_tokens["output"]
                )
                status_bar.update_tokens(
                    session.total_tokens["input"],
                    session.total_tokens["output"],
                    cost
                )

        except Exception as e:
            chat_view.add_error_message(f"세션 불러오기 실패: {str(e)}")

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

    async def action_settings(self) -> None:
        """설정 열기"""
        chat_view = self.query_one(ChatView)
        
        # 현재 설정 수집 - 항상 config 파일의 값 사용 (세션 값이 아님!)
        session = self.session_manager.current_session
        current_settings = {
            "model": self.config.config.default_model,
            "feedback_loop_enabled": self.config.config.feedback_loop_defaults.enabled,
            "condition_prompt": session.feedback_loop.condition_prompt if session else "",
            "max_iterations": self.config.config.feedback_loop_defaults.max_iterations,
            "condition_model": self.config.config.feedback_loop_defaults.condition_model,
            "feedback_input": session.feedback_loop.feedback_input if session else "",
            "show_statusbar": self.config.config.display.show_statusbar,
            "show_timestamps": self.config.config.display.show_timestamps,
            "show_token_counts": self.config.config.display.show_token_counts,
            "enable_thinking": self.config.config.display.enable_thinking,
            "show_thinking_full": self.config.config.display.show_thinking_full,
        }

        # 설정 모달 표시 (callback 방식)
        def on_settings_saved(settings_result):
            """설정 저장 콜백"""
            if settings_result is None:
                chat_view.add_system_message("설정 변경이 취소되었습니다.", style="yellow")
                return
            
            self._apply_settings(settings_result)
        
        modal = SettingsModal(current_settings)
        self.push_screen(modal, callback=on_settings_saved)
    
    def _apply_settings(self, settings_result) -> None:
        """설정 적용 (콜백에서 호출)"""
        chat_view = self.query_one(ChatView)
        
        try:
            # SettingsResult를 dict로 변환
            result = settings_result.to_dict()
            
            # 설정 변경 전 값 기록 (비교용)
            old_settings = {
                "model": self.config.config.default_model,
                "feedback_loop_enabled": self.config.config.feedback_loop_defaults.enabled,
                "max_iterations": self.config.config.feedback_loop_defaults.max_iterations,
            }
            
            # 설정 적용
            self.config.config.default_model = result["model"]
            self.config.config.feedback_loop_defaults.enabled = result["feedback_loop_enabled"]
            self.config.config.feedback_loop_defaults.max_iterations = result["max_iterations"]
            self.config.config.feedback_loop_defaults.condition_model = result["condition_model"]
            self.config.config.display.show_statusbar = result["show_statusbar"]
            self.config.config.display.show_timestamps = result["show_timestamps"]
            self.config.config.display.show_token_counts = result["show_token_counts"]
            self.config.config.display.enable_thinking = result["enable_thinking"]
            self.config.config.display.show_thinking_full = result["show_thinking_full"]

            # 설정 저장 (with 에러 처리)
            try:
                self.config.save()
                # 저장 성공 확인
                if not self.config.config_path.exists():
                    raise FileNotFoundError(f"설정 파일이 생성되지 않았습니다: {self.config.config_path}")
                
                # 세션 로그에 설정 변경 이벤트 기록
                if self.logger:
                    changes = []
                    if old_settings["model"] != result["model"]:
                        changes.append(f"모델: {old_settings['model']} → {result['model']}")
                    if old_settings["feedback_loop_enabled"] != result["feedback_loop_enabled"]:
                        changes.append(f"피드백 루프: {old_settings['feedback_loop_enabled']} → {result['feedback_loop_enabled']}")
                    if old_settings["max_iterations"] != result["max_iterations"]:
                        changes.append(f"최대 반복: {old_settings['max_iterations']} → {result['max_iterations']}")
                    
                    self.logger.log_event("settings_changed", {
                        "config_file": str(self.config.config_path),
                        "changes": changes,
                        "new_settings": {
                            "model": result["model"],
                            "feedback_loop_enabled": result["feedback_loop_enabled"],
                            "max_iterations": result["max_iterations"],
                            "condition_model": result["condition_model"],
                        }
                    })
                    
            except Exception as save_error:
                chat_view.add_error_message(f"❌ 설정 파일 저장 실패: {save_error}")
                if self.logger:
                    self.logger.log_error(save_error)
                return

            # 세션에도 피드백 루프 설정 저장
            if self.session_manager.current_session:
                self.session_manager.current_session.feedback_loop.enabled = result["feedback_loop_enabled"]
                self.session_manager.current_session.feedback_loop.condition_prompt = result.get("condition_prompt", "")
                self.session_manager.current_session.feedback_loop.max_iterations = result["max_iterations"]
                self.session_manager.current_session.feedback_loop.condition_model = result["condition_model"]
                self.session_manager.current_session.feedback_loop.feedback_input = result.get("feedback_input", "")
                self.session_manager.save_session(self.session_manager.current_session)

            # 피드백 루프 재생성 (설정 변경 시)
            if result["feedback_loop_enabled"]:
                self.feedback_loop = FeedbackLoop(
                    project_path=self.project_path,
                    condition_model=result["condition_model"],
                    max_iterations=result["max_iterations"],
                )
            else:
                self.feedback_loop = None

            # 알림 (상세)
            feedback_status = "활성화" if result['feedback_loop_enabled'] else "비활성화"
            condition_info = ""
            if result['feedback_loop_enabled'] and result.get('condition_prompt'):
                condition_info = f"\n  조건: {result['condition_prompt'][:40]}..."
            
            chat_view.add_system_message(
                f"✅ 설정이 저장되었습니다.\n"
                f"  파일: {self.config.config_path}\n"
                f"  모델: {result['model']}\n"
                f"  피드백 루프: {feedback_status}{condition_info}\n"
                f"  최대 반복: {result['max_iterations']}회",
                style="green"
            )

            # 타임스탬프 표시 토글 적용
            chat_view.show_timestamps = result["show_timestamps"]
            
            # 상태바 표시/숨김
            status_bar = self.query_one(StatusBar)
            if self.config.config.display.show_statusbar:
                status_bar.styles.display = "block"
            else:
                status_bar.styles.display = "none"
            
            # 상태바 업데이트 (피드백 루프 상태)
            status_bar.update_feedback_loop(result["feedback_loop_enabled"])
            
        except Exception as e:
            chat_view.add_error_message(f"설정 처리 실패: {str(e)}")
            if self.logger:
                self.logger.log_error(e)

    async def action_help(self) -> None:
        """도움말 표시"""
        modal = HelpModal()
        await self.push_screen(modal)

    async def action_clear_screen(self) -> None:
        """화면 지우기"""
        chat_view = self.query_one(ChatView)
        chat_view.clear_messages()
        chat_view.add_system_message("화면이 지워졌습니다. (대화 기록은 유지됨)", style="dim")

    async def action_interrupt(self) -> None:
        """현재 작업 중단"""
        input_box = self.query_one(InputBox)
        chat_view = self.query_one(ChatView)

        # Worker 실행 중이면 취소
        if self.current_worker and self.current_worker.is_running:
            self.current_worker.cancel()
            self.should_stop = True
            chat_view.add_system_message("⏹️  응답 중단 중...", style="yellow")
            return

        # 응답 스트리밍 중이면 중단 플래그 설정 (fallback)
        if self.is_processing:
            self.should_stop = True
            chat_view.add_system_message("⏹️  응답 중단 중...", style="yellow")
            return

        # 입력 중이면 입력창 초기화
        if input_box.text:
            input_box.clear_input()
            chat_view.add_system_message("입력이 취소되었습니다.", style="yellow")
            return

        # 아무것도 없으면 종료
        self.action_quit()

    def action_quit(self) -> None:
        """앱 종료"""
        # 종료 전 세션 통계 표시
        if self.session_manager.current_session:
            session = self.session_manager.current_session
            total_input = session.total_tokens["input"]
            total_output = session.total_tokens["output"]
            total_tokens = total_input + total_output
            
            if self.agent:
                cost = self.agent.estimate_cost(total_input, total_output)
                
                # 로그에 기록
                if self.logger:
                    self.logger.log_event("session_end", {
                        "total_tokens": total_tokens,
                        "input_tokens": total_input,
                        "output_tokens": total_output,
                        "estimated_cost": cost,
                        "message_count": len(session.messages),
                    })
        
        self.exit()

    # ========== Helper Methods ==========

    def _add_response_header(self, chat_view: ChatView) -> None:
        """응답 헤더 추가 (타임스탬프 + 레이블)"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        if self.config.config.display.show_timestamps:
            header = Text(f"[{timestamp}] ", style="dim")
            header.append("Claude", style="bold green")
            chat_view.write(header)
        else:
            assistant_label = Text("Claude", style="bold green")
            chat_view.write(assistant_label)

    def _update_token_display(self, response_length: int) -> None:
        """토큰 사용량 표시 업데이트"""
        session = self.session_manager.current_session
        if not session or not self.agent:
            return

        total_input = session.total_tokens["input"]
        total_output = session.total_tokens["output"]
        cost = self.agent.estimate_cost(total_input, total_output)

        status_bar = self.query_one(StatusBar)
        status_bar.update_tokens(total_input, total_output, cost)

    @staticmethod
    def _format_timestamp(timestamp: str) -> str:
        """ISO 타임스탬프를 HH:MM:SS로 변환"""
        # 2024-01-01T12:34:56.789 → 12:34:56
        if "T" in timestamp:
            return timestamp.split("T")[1][:8]
        # 이미 HH:MM:SS 형식이면 그대로
        return timestamp[:8]

