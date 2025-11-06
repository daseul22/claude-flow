"""대화 뷰 컴포넌트"""

from typing import Optional
from datetime import datetime
import textwrap

from textual.widgets import RichLog
from rich.text import Text
from rich.markdown import Markdown


class ChatView(RichLog):
    """대화 메시지 표시 영역"""

    DEFAULT_CSS = """
    ChatView {
        border: solid $primary;
        height: 1fr;
        width: 100%;
        padding: 1;
        overflow-y: auto;
        overflow-x: hidden;
    }
    """

    def __init__(self, show_timestamps: bool = True, **kwargs):
        super().__init__(
            highlight=True,
            markup=True,
            auto_scroll=True,
            wrap=True,  # 자동 줄바꿈 활성화
            **kwargs
        )
        self.show_timestamps = show_timestamps

    def write_wrapped(self, content: str) -> None:
        """텍스트 출력 (자동 줄바꿈 처리)"""
        # 터미널 너비 가져오기 (패딩 고려)
        max_width = max(self.size.width - 4, 40)  # 최소 40자
        
        # 긴 줄을 줄바꿈
        lines = content.split('\n')
        wrapped_lines = []
        for line in lines:
            if len(line) > max_width:
                # textwrap으로 줄바꿈
                wrapped = textwrap.fill(
                    line,
                    width=max_width,
                    break_long_words=False,
                    break_on_hyphens=False,
                )
                wrapped_lines.append(wrapped)
            else:
                wrapped_lines.append(line)
        
        content = '\n'.join(wrapped_lines)
        
        # 부모 클래스의 write 호출
        super().write(content)

    def add_user_message(self, content: str, timestamp: Optional[str] = None) -> None:
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

    def add_assistant_message(self, content: str, timestamp: Optional[str] = None) -> None:
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

    def add_system_message(self, message: str, style: str = "yellow") -> None:
        """시스템 메시지 추가"""
        system_text = Text(f"ℹ️  {message}", style=style)
        self.write(system_text)
        self.write("")

    def add_error_message(self, error: str) -> None:
        """에러 메시지 추가"""
        error_text = Text(f"❌ Error: {error}", style="bold red")
        self.write(error_text)
        self.write("")

    def add_tool_call(self, tool_name: str, args: dict) -> None:
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

    def clear_messages(self) -> None:
        """모든 메시지 삭제"""
        self.clear()

    def toggle_timestamps(self) -> None:
        """타임스탬프 표시 토글"""
        self.show_timestamps = not self.show_timestamps

