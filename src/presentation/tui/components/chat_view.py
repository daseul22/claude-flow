"""대화 뷰 컴포넌트"""

from textual.widgets import RichLog
from textual.widget import Widget
from rich.text import Text
from rich.panel import Panel
from rich.markdown import Markdown
from datetime import datetime


class ChatView(RichLog):
    """대화 메시지 표시 영역"""

    DEFAULT_CSS = """
    ChatView {
        border: solid $primary;
        height: 1fr;
        padding: 1;
    }
    """

    def __init__(self, show_timestamps: bool = True, **kwargs):
        super().__init__(
            highlight=True,
            markup=True,
            auto_scroll=True,
            **kwargs
        )
        self.show_timestamps = show_timestamps

    def add_user_message(self, content: str, timestamp: str = None):
        """사용자 메시지 추가"""
        if timestamp is None:
            timestamp = datetime.now().strftime("%H:%M:%S")

        # 타임스탬프와 사용자 레이블을 한 줄로
        if self.show_timestamps:
            header = Text(f"[{timestamp}] ", style="dim")
            header.append("You", style="bold cyan")
            self.write(header)
        else:
            user_label = Text("You", style="bold cyan")
            self.write(user_label)

        # 메시지 내용
        self.write(f"  {content}")
        self.write("")  # 구분선

    def add_assistant_message(self, content: str, timestamp: str = None):
        """어시스턴트 메시지 추가"""
        if timestamp is None:
            timestamp = datetime.now().strftime("%H:%M:%S")

        # 타임스탬프와 어시스턴트 레이블을 한 줄로
        if self.show_timestamps:
            header = Text(f"[{timestamp}] ", style="dim")
            header.append("Claude", style="bold green")
            self.write(header)
        else:
            assistant_label = Text("Claude", style="bold green")
            self.write(assistant_label)

        # 메시지 내용 (마크다운 렌더링)
        try:
            md = Markdown(content)
            self.write(md)
        except Exception:
            # 마크다운 파싱 실패시 일반 텍스트로
            self.write(f"  {content}")

        self.write("")  # 구분선

    def add_system_message(self, message: str, style: str = "yellow"):
        """시스템 메시지 추가"""
        system_text = Text(f"ℹ️  {message}", style=style)
        self.write(system_text)
        self.write("")

    def add_error_message(self, error: str):
        """에러 메시지 추가"""
        error_text = Text(f"❌ Error: {error}", style="bold red")
        self.write(error_text)
        self.write("")

    def add_tool_call(self, tool_name: str, args: dict):
        """도구 호출 표시"""
        tool_text = Text(f"🔧 Tool: {tool_name}", style="magenta")
        self.write(tool_text)

        # 인자 표시 (간단히)
        if args:
            args_str = ", ".join(f"{k}={v}" for k, v in list(args.items())[:3])
            if len(args) > 3:
                args_str += ", ..."
            self.write(f"  Args: {args_str}")

        self.write("")

    def clear_messages(self):
        """모든 메시지 삭제"""
        self.clear()

    def toggle_timestamps(self):
        """타임스탬프 표시 토글"""
        self.show_timestamps = not self.show_timestamps

