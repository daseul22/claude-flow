"""상태바 컴포넌트"""

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static
from textual.containers import Horizontal


class StatusBar(Widget):
    """하단 상태바"""

    DEFAULT_CSS = """
    StatusBar {
        dock: bottom;
        height: 1;
        background: $panel;
        color: $text;
    }

    StatusBar Horizontal {
        width: 100%;
        height: 1;
    }

    StatusBar .project-info {
        width: 30%;
    }

    StatusBar .session-info {
        width: 40%;
        text-align: center;
    }

    StatusBar .token-info {
        width: 30%;
        text-align: right;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.project_name = ""
        self.session_id = ""
        self.git_branch = ""
        self.input_tokens = 0
        self.output_tokens = 0
        self.estimated_cost = 0.0
        self.feedback_loop_enabled = False

    def compose(self) -> ComposeResult:
        """컴포넌트 구성"""
        with Horizontal():
            yield Static("", classes="project-info", id="project-info")
            yield Static("", classes="session-info", id="session-info")
            yield Static("", classes="token-info", id="token-info")

    def update_project(self, name: str, git_branch: str = "") -> None:
        """프로젝트 정보 업데이트"""
        self.project_name = name
        self.git_branch = git_branch
        self._refresh_display()

    def update_session(self, session_id: str) -> None:
        """세션 정보 업데이트"""
        self.session_id = session_id[:8]  # 앞 8자만 표시
        self._refresh_display()

    def update_tokens(self, input_tokens: int, output_tokens: int, cost: float = 0.0) -> None:
        """토큰 사용량 업데이트"""
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.estimated_cost = cost
        self._refresh_display()

    def update_feedback_loop(self, enabled: bool) -> None:
        """피드백 루프 상태 업데이트"""
        self.feedback_loop_enabled = enabled
        self._refresh_display()

    def _refresh_display(self) -> None:
        """화면 갱신"""
        # 프로젝트 정보
        project_text = f"📁 {self.project_name}"
        if self.git_branch:
            project_text += f" [{self.git_branch}]"

        project_widget = self.query_one("#project-info", Static)
        project_widget.update(project_text)

        # 세션 정보
        session_text = f"Session: {self.session_id}" if self.session_id else "No session"
        if self.feedback_loop_enabled:
            session_text += " | 🔁 Feedback"
        session_widget = self.query_one("#session-info", Static)
        session_widget.update(session_text)

        # 토큰 정보
        total_tokens = self.input_tokens + self.output_tokens
        token_text = f"🪙 {total_tokens:,} tokens"
        if self.estimated_cost > 0:
            token_text += f" (${self.estimated_cost:.4f})"

        token_widget = self.query_one("#token-info", Static)
        token_widget.update(token_text)

