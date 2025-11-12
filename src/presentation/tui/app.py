"""Claude Flow TUI 메인 앱"""

import os
from pathlib import Path
from typing import Optional, Dict, Any

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal
from textual.worker import Worker, WorkerState
from rich.text import Text

from .components.status_bar import StatusBar
from .components.chat_view import ChatView
from .components.input_box import InputBox
from .components.context_sidebar import ContextSidebar
from .components.modals.session_list import SessionListModal
from .components.modals.settings_modal import SettingsModal
from .components.modals.help_modal import HelpModal
from .components.modals.context_modal import (
    AddContextFileModal,
    ManagePresetsModal,
)
from .config.settings import ConfigManager
from .services.session_manager import SessionManager
from .services.agent_client import AgentClient
from .services.logger import SessionLogger, LogManager
from .services.project_utils import get_project_info
from .services.context_manager import ContextManager
from .services.feedback_loop_improved import ImprovedFeedbackLoop, EvaluationResult
from .services.smart_feedback_loop import SmartFeedbackLoop, create_smart_feedback_loop
from .services.response_parser import ResponseParser
from .services.response_handler import (
    ResponseCallbackHandler,
    FeedbackLoopCallbackHandler,
    SmartFeedbackLoopCallbackHandler,
)
from .services.response_strategy import (
    ResponseStrategy,
    NormalResponseStrategy,
    FeedbackLoopResponseStrategy,
    SmartFeedbackLoopResponseStrategy,
)
from .services.settings_helpers import SettingsChangeDetector, SettingsApplicator
from .utils.keymap import ShortcutDefinition, expand_shortcut


class ClaudeFlowApp(App):
    """Claude Flow TUI 메인 애플리케이션"""

    CSS = """
    Screen {
        background: #0d1117;
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

    Horizontal {
        width: 100%;
        height: 1fr;
    }

    ChatView {
        width: 1fr;
        height: 100%;
        border: none;
        padding: 0 1;
        background: #0d1117;
    }

    InputBox {
        height: 3;
        margin: 1 0 1 0;
        border: solid #8b5cf6;
        background: #0d1117;
    }

    StatusBar {
        background: #161b22;
        color: #8b949e;
    }
    """

    _BINDING_DEFINITIONS = [
        ShortcutDefinition("ctrl+n", "new_session", "새 세션"),
        ShortcutDefinition("ctrl+o", "open_session", "세션 불러오기"),
        ShortcutDefinition("ctrl+i", "project_info", "프로젝트 정보"),
        ShortcutDefinition("ctrl+k", "toggle_context", "컨텍스트"),
        ShortcutDefinition("ctrl+s", "settings", "설정"),
        ShortcutDefinition("ctrl+slash", "help", "도움말"),
        ShortcutDefinition("f1", "help", "도움말"),
        ShortcutDefinition("ctrl+l", "clear_screen", "화면 지우기"),
        ShortcutDefinition("ctrl+c", "interrupt", "중단"),
        ShortcutDefinition("ctrl+q", "quit", "종료"),
    ]

    BINDINGS = [
        binding for definition in _BINDING_DEFINITIONS for binding in expand_shortcut(definition)
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
        self.claude_md_exists = project_info["claude_md_loaded"]  # CLAUDE.md 파일 존재 여부만 저장

        # 프로젝트별 설정 로드
        self.project_settings = self.config.load_project_settings(self.project_name)

        # 세션 관리자
        sessions_dir = self.config.get_project_sessions_dir(self.project_name)
        self.session_manager = SessionManager(sessions_dir)

        # 로그 관리자
        logs_dir = self.config.get_project_logs_dir(self.project_name)
        self.log_manager = LogManager(logs_dir)
        self.logger: Optional[SessionLogger] = None

        # 에이전트 클라이언트
        self.agent: Optional[AgentClient] = None

        # 피드백 루프 (개선된 버전)
        self.feedback_loop: Optional[ImprovedFeedbackLoop] = None

        # 스마트 피드백 루프 (조건 자동 생성)
        self.smart_feedback_loop: Optional[SmartFeedbackLoop] = None

        # 현재 작업
        self.current_worker: Optional[Worker] = None  # 현재 실행 중인 Worker
        self.is_processing: bool = False  # 응답 처리 중 플래그
        self.should_stop: bool = False  # 중단 요청 플래그

        # 디렉토리 히스토리 (cd - 용)
        self.directory_history: list[Path] = []

        # 컴팩션 이벤트 중복 알림 방지 (최근 5초 내 동일 트리거 무시)
        self._last_compaction_event: Optional[Dict[str, Any]] = None
        self._compaction_debounce_seconds: float = 5.0

        # 컨텍스트 윈도우 경고 플래그 (80% 경고는 한 번만)
        self._context_window_80_warned: bool = False

        # 컨텍스트 관리자
        self.context_manager = ContextManager(self.project_path)
        # 마지막 컨텍스트 복원
        self.context_manager.restore_last_context()

    def compose(self) -> ComposeResult:
        """UI 구성"""
        with Container(id="main-container"):
            with Horizontal():
                yield ChatView(show_timestamps=self.config.config.display.show_timestamps)
                yield ContextSidebar(
                    self.context_manager,
                    show=False  # 기본적으로 숨김
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
                style="yellow",
            )

        # 새 세션 생성
        await self.create_new_session()

        # 환영 메시지
        chat_view = self.query_one(ChatView)
        chat_view.add_system_message(
            f"Claude Flow TUI v1.0 시작됨\n"
            f"프로젝트: {self.project_name}\n"
            f"경로: {self.project_path}",
            style="cyan",
        )

        if self.git_info:
            chat_view.add_system_message(f"Git 브랜치: {self.git_info['branch']}", style="dim")

        if self.claude_md_exists:
            chat_view.add_system_message("✓ CLAUDE.md 감지됨 (자동 로드)", style="green")

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
                # 상태바 업데이트 (처리 중 표시)
                status_bar = self.query_one(StatusBar)
                status_bar.update_processing(True)
                # 입력창 비활성화
                input_box = self.query_one(InputBox)
                input_box.disabled = True

        # Worker가 완료/취소되면 플래그 초기화
        elif worker.state in (WorkerState.SUCCESS, WorkerState.CANCELLED, WorkerState.ERROR):
            if worker.name == "agent_response":
                self.is_processing = False
                self.should_stop = False
                # 상태바 업데이트 (처리 완료)
                status_bar = self.query_one(StatusBar)
                status_bar.update_processing(False)
                # 입력창 활성화
                input_box = self.query_one(InputBox)
                input_box.disabled = False

                chat_view = self.query_one(ChatView)

                # 정상 완료
                if worker.state == WorkerState.SUCCESS:
                    # 마지막 메시지의 토큰 수 가져오기 (있으면)
                    tokens_used = None
                    if (
                        self.session_manager.current_session
                        and self.session_manager.current_session.messages
                    ):
                        last_message = self.session_manager.current_session.messages[-1]
                        if last_message.role == "assistant":
                            tokens_used = (
                                last_message.tokens.get("input", 0)
                                + last_message.tokens.get("output", 0)
                            )

                    chat_view.add_completion_message(tokens_used)

                # 취소된 경우
                elif worker.state == WorkerState.CANCELLED:
                    chat_view.add_system_message("✓ 응답이 중단되었습니다.", style="yellow")

                # 에러 발생
                elif worker.state == WorkerState.ERROR and worker.error:
                    chat_view.add_error_message(f"Worker 에러: {worker.error}")

    async def create_new_session(self):
        """새 세션 생성"""
        # 컨텍스트 윈도우 경고 플래그 리셋
        self._context_window_80_warned = False

        # 피드백 루프 설정 준비 (프로젝트별 설정 사용)
        from .services.session_manager import FeedbackLoopConfig

        feedback_loop_config = FeedbackLoopConfig(
            enabled=self.project_settings["feedback_loop_enabled"],
            condition_prompt="",
            condition_model=self.project_settings["feedback_loop_condition_model"],
            max_iterations=self.project_settings["feedback_loop_max_iterations"],
            current_iteration=0,
            feedback_input="",
        )

        # 세션 생성
        session = self.session_manager.create_session(
            project_name=self.project_name,
            project_path=str(self.project_path),
            working_directory=str(self.project_path),
            model=self.config.config.default_model,
            claude_md_loaded=self.claude_md_exists,
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
                # claude_md_content 파라미터 제거 (WorkerAgent가 자동 로드)
                enable_thinking=self.config.config.display.enable_thinking,
            )
        else:
            # 기존 에이전트 세션 초기화 (새 세션이므로 맥락 리셋)
            self.agent.reset_session()

        # 피드백 루프 생성 (개선된 버전, 프로젝트별 설정 사용)
        if self.project_settings["feedback_loop_enabled"]:
            self.feedback_loop = ImprovedFeedbackLoop(
                project_path=self.project_path,
                condition_model=self.project_settings["feedback_loop_condition_model"],
                max_iterations=self.project_settings["feedback_loop_max_iterations"],
                quality_threshold=self.project_settings["feedback_loop_quality_threshold"],
            )

        # 스마트 피드백 루프 생성 (조건 자동 생성)
        if self.project_settings.get("smart_feedback_enabled", False):
            self.smart_feedback_loop = create_smart_feedback_loop(
                project_path=self.project_path,
                mode=self.project_settings.get("smart_feedback_mode", "auto"),
                simple_goal=self.project_settings.get("smart_feedback_simple_goal", ""),
                detailed_condition=self.project_settings.get(
                    "smart_feedback_detailed_condition", ""
                ),
                max_iterations=self.project_settings.get(
                    "smart_feedback_max_iterations",
                    self.project_settings["feedback_loop_max_iterations"],
                ),
                quality_threshold=self.project_settings.get(
                    "smart_feedback_quality_threshold",
                    self.project_settings["feedback_loop_quality_threshold"],
                ),
            )

        # 상태바 업데이트
        status_bar = self.query_one(StatusBar)
        git_branch = self.git_info["branch"] if self.git_info else ""
        status_bar.update_project(self.project_name, git_branch)
        status_bar.update_session(session.session_id)
        status_bar.update_feedback_loop(session.feedback_loop.enabled)

        if self.logger:
            self.logger.log_event(
                "new_session",
                {
                    "session_id": session.session_id,
                    "project": self.project_name,
                },
            )

    async def on_input_box_submitted(self, message: InputBox.Submitted) -> None:
        """메시지 전송 처리"""
        user_message = message.text
        chat_view = self.query_one(ChatView)

        # cd 명령어 처리
        if user_message.strip().startswith("cd "):
            await self.handle_cd_command(user_message.strip())
            return

        # 컨텍스트 주입
        final_message = self._inject_context(user_message)

        # 사용자 메시지 표시 (원본 메시지만 표시)
        estimated_tokens = int(len(final_message.split()) * 1.3)
        chat_view.add_user_message(user_message, tokens=estimated_tokens)

        # 컨텍스트가 추가되었으면 알림 표시
        enabled_files = self.context_manager.get_enabled_files()
        if enabled_files:
            chat_view.add_system_message(
                f"📎 컨텍스트: {len(enabled_files)}개 파일 포함됨",
                style="dim cyan"
            )

        # 세션에 저장 (컨텍스트 포함된 메시지 저장)
        self.session_manager.add_message(
            role="user",
            content=final_message,
            tokens={"input": estimated_tokens, "output": 0},  # 간단한 추정
        )

        # 로그
        if self.logger:
            self.logger.log_message("user", final_message)

        # 에이전트 응답 (Worker로 실행) - 컨텍스트 포함된 메시지 전달
        self.current_worker = self.run_worker(
            self.get_agent_response(final_message),
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
                chat_view.add_system_message(f"⚠️  읽기 권한이 없습니다: {new_path}", style="yellow")

            if not os.access(new_path, os.W_OK):
                chat_view.add_system_message(f"⚠️  쓰기 권한이 없습니다: {new_path}", style="yellow")

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
                    style="yellow",
                )

            # 세션 업데이트
            if self.session_manager.current_session:
                self.session_manager.current_session.working_directory = str(self.project_path)
                save_success = self.session_manager.save_session(
                    self.session_manager.current_session
                )
                if not save_success:
                    chat_view.add_system_message(
                        "⚠️  세션 저장 실패 (작업 디렉토리 변경은 적용되었으나 저장되지 않음)",
                        style="yellow",
                    )

            # 알림
            chat_view.add_system_message(
                f"작업 디렉토리 변경:\n  {old_path}\n  → {self.project_path}", style="green"
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

        # 초기화
        self._initialize_response_state()
        self._add_response_header(chat_view)

        try:
            # 응답 전략 선택
            strategy = self._select_response_strategy()
            if strategy is None:
                # 피드백 루프 설정 오류
                return

            # 콜백 핸들러 생성
            handler = self._create_response_handler(strategy)

            # 토큰 사용량 콜백 생성 (세션 통계 추적용)
            usage_callback = self._create_usage_callback(chat_view)

            # 응답 실행
            response_text = await strategy.execute(
                agent=self.agent,
                message=user_message,
                handler=handler,
                worker=worker,
                should_stop_flag=lambda: self.should_stop,
                usage_callback=usage_callback,
            )

            # 세션 저장 및 상태 업데이트
            self._save_response(response_text)

        except Exception as e:
            self._handle_response_error(e, chat_view)
        finally:
            self._cleanup_response_state()

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
                f"✅ 세션 {session_id[:8]}이(가) 삭제되었습니다.", style="green"
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
                # 메시지별 토큰 수 계산
                msg_tokens = msg.tokens.get("input", 0) + msg.tokens.get("output", 0)

                if msg.role == "user":
                    chat_view.add_user_message(msg.content, timestamp, tokens=msg_tokens)
                elif msg.role == "assistant":
                    chat_view.add_assistant_message(msg.content, timestamp, tokens=msg_tokens)

            # 상태바 업데이트
            if self.agent:
                status_bar = self.query_one(StatusBar)
                status_bar.update_session(session.session_id)
                cost = self.agent.estimate_cost(
                    session.total_tokens["input"], session.total_tokens["output"]
                )
                status_bar.update_tokens(
                    session.total_tokens["input"], session.total_tokens["output"], cost
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
            settings = settings_result.to_dict()

            # 변경 감지
            old_settings = self._get_current_settings_dict()
            detector = SettingsChangeDetector(old_settings, settings)

            # 설정 적용
            applicator = SettingsApplicator(self.config, self.session_manager, self.project_name)
            applicator.apply_global_settings(settings)

            # 설정 저장
            try:
                applicator.save_config()
            except Exception as save_error:
                chat_view.add_error_message(f"❌ 설정 파일 저장 실패: {save_error}")
                if self.logger:
                    self.logger.log_error(save_error)
                return

            # 세션 설정 적용
            session_save_success = applicator.apply_session_settings(settings)
            if not session_save_success:
                chat_view.add_system_message(
                    "⚠️  세션 저장 실패 (설정은 적용되었으나 세션에 저장되지 않음)",
                    style="yellow",
                )

            # 프로젝트 설정 메모리 업데이트
            self.project_settings["feedback_loop_enabled"] = settings["feedback_loop_enabled"]
            self.project_settings["feedback_loop_max_iterations"] = settings["max_iterations"]
            self.project_settings["feedback_loop_condition_model"] = settings["condition_model"]
            self.project_settings["feedback_loop_quality_threshold"] = settings.get("quality_threshold", 0.8)

            # 피드백 루프 재생성
            if settings["feedback_loop_enabled"]:
                self.feedback_loop = applicator.create_feedback_loop(settings, self.project_path)
            else:
                self.feedback_loop = None

            # UI 설정 적용
            self._apply_ui_settings(settings, chat_view)

            # 로깅 및 알림
            self._log_settings_changes(detector, settings)
            self._show_settings_success_message(settings, chat_view)

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
        await self.action_quit()

    async def action_quit(self) -> None:
        """앱 종료 (비동기 정리 작업 포함)"""
        chat_view = self.query_one(ChatView)

        try:
            # 실행 중인 Worker 취소
            if self.current_worker and self.current_worker.is_running:
                self.should_stop = True
                self.current_worker.cancel()

                # Worker 종료 대기 (최대 2초)
                import asyncio

                try:
                    await asyncio.wait_for(asyncio.to_thread(self.current_worker.wait), timeout=2.0)
                except asyncio.TimeoutError:
                    chat_view.add_system_message(
                        "⚠️  Worker 종료 timeout (강제 종료됨)", style="yellow"
                    )

            # 세션 저장 (최종)
            if self.session_manager.current_session:
                session = self.session_manager.current_session
                total_input = session.total_tokens["input"]
                total_output = session.total_tokens["output"]
                total_tokens = total_input + total_output

                # 세션 통계 계산
                cost = (
                    self.agent.estimate_cost(total_input, total_output) if self.agent else 0.0
                )
                message_count = len(session.messages)

                # 종료 이벤트 로그
                if self.logger:
                    self.logger.log_event(
                        "session_end",
                        {
                            "total_tokens": total_tokens,
                            "input_tokens": total_input,
                            "output_tokens": total_output,
                            "estimated_cost": cost,
                            "message_count": message_count,
                        },
                    )

                # 세션 통계 표시 (사용자에게)
                from rich.text import Text

                stats_message = Text()
                stats_message.append("\n━━━ 세션 종료 통계 ━━━\n", style="bold cyan")
                stats_message.append(f"📊 메시지 수: {message_count}\n", style="white")
                stats_message.append(
                    f"🎯 토큰 사용량: {total_tokens:,} "
                    f"(입력: {total_input:,}, 출력: {total_output:,})\n",
                    style="white",
                )
                if cost > 0:
                    stats_message.append(f"💰 예상 비용: ${cost:.4f}\n", style="yellow")
                stats_message.append("━━━━━━━━━━━━━━━━━━━━\n", style="bold cyan")

                chat_view.write(stats_message)

                # 최종 세션 저장
                save_success = self.session_manager.save_session(session)
                if not save_success:
                    chat_view.add_system_message(
                        "⚠️  세션 저장 실패 (백업 파일 확인 필요)", style="red"
                    )
                    # 사용자가 메시지를 볼 시간 제공
                    await asyncio.sleep(1.0)

        except Exception as e:
            # 종료 중 에러가 발생해도 앱은 종료해야 함
            chat_view.add_error_message(f"종료 중 에러 발생: {e}")
            if self.logger:
                self.logger.log_error(e)
            await asyncio.sleep(0.5)

        finally:
            # 항상 종료
            self.exit()

    # ========== Helper Methods ==========

    def _initialize_response_state(self) -> None:
        """응답 처리 상태 초기화"""
        self.is_processing = True
        self.should_stop = False

    def _select_response_strategy(self) -> Optional[ResponseStrategy]:
        """응답 전략 선택 (스마트 피드백 루프 > 피드백 루프 > 일반)"""
        session = self.session_manager.current_session
        chat_view = self.query_one(ChatView)

        # 1. 스마트 피드백 루프 (우선순위 1)
        if self.smart_feedback_loop is not None:
            return SmartFeedbackLoopResponseStrategy(
                smart_feedback_loop=self.smart_feedback_loop,
            )

        # 2. 기존 피드백 루프 (우선순위 2)
        use_feedback_loop = (
            self.feedback_loop is not None and session and session.feedback_loop.enabled
        )

        # 피드백 루프 활성화했지만 조건 프롬프트 없음 → 스마트 피드백 루프 자동 사용
        if use_feedback_loop and not session.feedback_loop.condition_prompt.strip():
            # 스마트 피드백 루프 즉석 생성
            if self.smart_feedback_loop is None:
                self.smart_feedback_loop = create_smart_feedback_loop(
                    project_path=self.project_path,
                    mode="auto",  # 자동 모드 (조건 자동 생성)
                    max_iterations=self.project_settings["feedback_loop_max_iterations"],
                    quality_threshold=self.project_settings["feedback_loop_quality_threshold"],
                )

            # 스마트 피드백 루프 전략 반환
            chat_view.add_system_message(
                "💡 조건 프롬프트가 없어 스마트 피드백 루프를 자동 활성화했습니다.\n"
                "요청을 분석하여 평가 기준을 자동 생성합니다."
            )
            return SmartFeedbackLoopResponseStrategy(
                smart_feedback_loop=self.smart_feedback_loop,
            )

        if use_feedback_loop:
            # 피드백 루프 전략
            return FeedbackLoopResponseStrategy(
                feedback_loop=self.feedback_loop,
                condition_prompt=session.feedback_loop.condition_prompt,
                feedback_input=session.feedback_loop.feedback_input,
                max_iterations=session.feedback_loop.max_iterations,
            )

        # 3. 일반 응답 전략 (우선순위 3)
        return NormalResponseStrategy()

    def _create_response_handler(self, strategy: ResponseStrategy) -> ResponseCallbackHandler:
        """응답 핸들러 생성"""
        chat_view = self.query_one(ChatView)
        parser = ResponseParser()
        display_config = self.config.config.display

        if isinstance(strategy, SmartFeedbackLoopResponseStrategy):
            # 스마트 피드백 루프 핸들러 (조건 생성 + 평가 콜백)
            return SmartFeedbackLoopCallbackHandler(chat_view, parser, display_config)
        elif isinstance(strategy, FeedbackLoopResponseStrategy):
            # 피드백 루프 핸들러 (평가 콜백 포함)
            return FeedbackLoopCallbackHandler(chat_view, parser, display_config)
        else:
            # 일반 핸들러
            return ResponseCallbackHandler(chat_view, parser, display_config)

    def _save_response(self, response_text: str) -> None:
        """응답 저장 및 상태 업데이트"""
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

    def _handle_response_error(self, error: Exception, chat_view: ChatView) -> None:
        """응답 에러 처리"""
        chat_view.add_error_message(str(error))
        if self.logger:
            self.logger.log_error(error)

    def _cleanup_response_state(self) -> None:
        """응답 처리 상태 정리"""
        self.is_processing = False
        self.should_stop = False

    def _get_current_settings_dict(self) -> Dict[str, Any]:
        """현재 설정을 딕셔너리로 반환 (프로젝트별 설정 사용)"""
        return {
            "model": self.config.config.default_model,
            "feedback_loop_enabled": self.project_settings["feedback_loop_enabled"],
            "max_iterations": self.project_settings["feedback_loop_max_iterations"],
            "condition_model": self.project_settings["feedback_loop_condition_model"],
        }

    def _apply_ui_settings(self, settings: Dict[str, Any], chat_view: ChatView) -> None:
        """UI 설정 적용 (타임스탬프, 상태바 등)"""
        # 타임스탬프 표시 토글
        chat_view.show_timestamps = settings["show_timestamps"]

        # 상태바 표시/숨김
        status_bar = self.query_one(StatusBar)
        if self.config.config.display.show_statusbar:
            status_bar.styles.display = "block"
        else:
            status_bar.styles.display = "none"

        # 상태바 업데이트 (피드백 루프 상태)
        status_bar.update_feedback_loop(settings["feedback_loop_enabled"])

    def _log_settings_changes(
        self, detector: SettingsChangeDetector, settings: Dict[str, Any]
    ) -> None:
        """설정 변경 이력 로깅"""
        if not self.logger:
            return

        changes = detector.get_changes()
        if not changes:
            return

        self.logger.log_event(
            "settings_changed",
            {
                "config_file": str(self.config.config_path),
                "changes": changes,
                "new_settings": {
                    "model": settings["model"],
                    "feedback_loop_enabled": settings["feedback_loop_enabled"],
                    "max_iterations": settings["max_iterations"],
                    "condition_model": settings["condition_model"],
                },
            },
        )

    def _show_settings_success_message(self, settings: Dict[str, Any], chat_view: ChatView) -> None:
        """설정 저장 성공 메시지 표시"""
        feedback_status = "활성화" if settings["feedback_loop_enabled"] else "비활성화"
        condition_info = ""
        if settings["feedback_loop_enabled"] and settings.get("condition_prompt"):
            condition_info = f"\n  조건: {settings['condition_prompt'][:40]}..."

        chat_view.add_system_message(
            f"✅ 설정이 저장되었습니다.\n"
            f"  파일: {self.config.config_path}\n"
            f"  모델: {settings['model']}\n"
            f"  피드백 루프: {feedback_status}{condition_info}\n"
            f"  최대 반복: {settings['max_iterations']}회",
            style="green",
        )

    def _create_usage_callback(self, chat_view: ChatView) -> callable:
        """토큰 사용량 콜백 생성 (세션 통계 추적용)

        Returns:
            Callable[[Dict[str, Any]], None]: 토큰 사용량 콜백 함수
        """

        def on_usage(usage_dict: Dict[str, Any]) -> None:
            """토큰 사용량 정보 수신 시 호출 (ResultMessage에서만 호출됨)"""
            # Agent 및 세션 ID 확인
            if not self.agent or not self.agent.current_session_id:
                return  # 세션 ID 없으면 스킵

            model = self.agent.model
            normalized_model = self.agent._normalize_model_name(model)
            sdk_session_id = self.agent.current_session_id

            # 세션 통계 업데이트
            compaction_event = self.session_manager.update_session_stats(
                sdk_session_id=sdk_session_id,
                model=normalized_model,
                usage_dict=usage_dict,
            )

            # 컴팩션 이벤트 감지 시 알림 (감소 토큰 > 0 + 중복 방지)
            if compaction_event:
                reduction = compaction_event["reduction_tokens"]

                # 감소 토큰이 0이면 무시 (의미 없는 이벤트)
                if reduction <= 0:
                    return

                # 중복 알림 방지 (최근 N초 내 동일 트리거 무시)
                from datetime import datetime
                now = datetime.now()
                trigger = compaction_event["trigger"]

                if self._last_compaction_event:
                    last_trigger = self._last_compaction_event.get("trigger")
                    last_time_str = self._last_compaction_event.get("timestamp")

                    if last_time_str and last_trigger == trigger:
                        try:
                            last_time = datetime.fromisoformat(last_time_str)
                            time_diff = (now - last_time).total_seconds()

                            # N초 내 동일 트리거는 중복으로 간주
                            if time_diff < self._compaction_debounce_seconds:
                                return
                        except Exception:
                            pass  # 파싱 실패 시 무시하고 알림 표시

                # 알림 표시
                trigger_text = {
                    "cache_creation": "캐시 재생성",
                    "cache_reset": "캐시 리셋",
                    "context_limit": "컨텍스트 윈도우 축소",
                }.get(trigger, trigger)

                chat_view.add_system_message(
                    f"🔄 컨텍스트 컴팩션 발생: {trigger_text} (감소: {reduction:,} tokens)",
                    style="yellow",
                )

                # 마지막 이벤트 저장 (중복 방지용)
                self._last_compaction_event = compaction_event

            # 세션 통계 조회 및 StatusBar 업데이트
            stats = self.session_manager.get_current_sdk_session_stats(sdk_session_id)
            if stats:
                cumulative_tokens = stats["cumulative_total_tokens"]
                usage_pct = stats["estimated_context_window_usage"]
                # 모델별 컨텍스트 한계 동적 조회
                limit = self.session_manager.get_context_limit(normalized_model)

                status_bar = self.query_one(StatusBar)
                status_bar.update_context_window(cumulative_tokens, usage_pct, limit)

                # 컨텍스트 윈도우 80% 경고 (한 번만)
                if usage_pct >= 0.8 and not self._context_window_80_warned:
                    self._context_window_80_warned = True
                    chat_view = self.query_one(ChatView)
                    from rich.text import Text

                    warning_msg = Text()
                    warning_msg.append("\n⚠️  ", style="bold yellow")
                    warning_msg.append("컨텍스트 윈도우 경고", style="bold yellow")
                    warning_msg.append(
                        f"\n현재 사용량: {int(usage_pct * 100)}% "
                        f"({cumulative_tokens:,} / {limit:,} tokens)\n",
                        style="yellow",
                    )
                    warning_msg.append(
                        "\n권장 조치:\n"
                        "  • 새 세션 시작 (Ctrl+N)\n"
                        "  • 불필요한 대화 내용 정리\n"
                        "  • 컨텍스트 윈도우가 가득 차면 자동으로 컴팩션됩니다\n",
                        style="dim yellow",
                    )

                    chat_view.write(warning_msg)

        return on_usage

    def _add_response_header(self, chat_view: ChatView) -> None:
        """응답 헤더 추가 (Claude Code 스타일: ● 사용)"""
        # 빈 줄
        chat_view.write("")

        # 큰 bullet point로 시작 (Claude Code 스타일)
        header = Text()
        header.append("● ", style="bold green")
        chat_view.write(header)

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

    # === 컨텍스트 관리 ===

    def _inject_context(self, user_message: str) -> str:
        """
        사용자 메시지에 컨텍스트 파일 내용을 자동으로 주입

        Args:
            user_message: 원본 사용자 메시지

        Returns:
            컨텍스트가 주입된 메시지 (컨텍스트가 없으면 원본 그대로)
        """
        context_message = self.context_manager.build_context_message(
            max_size_bytes=100_000  # 최대 100KB
        )

        if context_message:
            # 컨텍스트 + 사용자 메시지 조합
            return f"{context_message}\n\n---\n\n사용자 요청: {user_message}"
        else:
            # 컨텍스트가 없으면 원본 그대로
            return user_message

    # === 컨텍스트 관리 액션 ===

    def action_toggle_context(self) -> None:
        """컨텍스트 사이드바 표시/숨김 토글"""
        sidebar = self.query_one(ContextSidebar)
        sidebar.toggle_visibility()

    def on_context_sidebar_add_file_requested(
        self, message: ContextSidebar.AddFileRequested
    ) -> None:
        """파일 추가 요청 처리"""
        self.push_screen(
            AddContextFileModal(self.context_manager, self.project_path),
            self.on_file_added
        )

    def on_context_sidebar_manage_presets_requested(
        self, message: ContextSidebar.ManagePresetsRequested
    ) -> None:
        """프리셋 관리 요청 처리"""
        self.push_screen(
            ManagePresetsModal(self.context_manager),
            self.on_preset_action
        )

    def on_context_sidebar_file_toggled(
        self, message: ContextSidebar.FileToggled
    ) -> None:
        """파일 토글 처리 (활성화/비활성화)"""
        chat_view = self.query_one(ChatView)
        chat_view.add_system_message(
            f"컨텍스트 파일 토글: {message.file_path}",
            style="dim"
        )

    def on_file_added(self, result: Optional[Path]) -> None:
        """파일 추가 완료 콜백"""
        if result:
            sidebar = self.query_one(ContextSidebar)
            sidebar.refresh_file_list()

            chat_view = self.query_one(ChatView)
            chat_view.add_system_message(
                f"✓ 컨텍스트에 파일 추가됨: {result.name}",
                style="green"
            )

    def on_preset_action(self, result: Optional[str]) -> None:
        """프리셋 액션 완료 콜백"""
        if result:
            sidebar = self.query_one(ContextSidebar)
            sidebar.refresh_file_list()

            chat_view = self.query_one(ChatView)
            chat_view.add_system_message(
                f"✓ 프리셋 '{result}' 불러오기 완료",
                style="green"
            )
