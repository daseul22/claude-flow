"""대화 뷰 컴포넌트"""

from typing import Optional, Union
from datetime import datetime
import textwrap

from textual.widgets import RichLog
from rich.text import Text
from rich.markdown import Markdown


class ChatView(RichLog):
    """대화 메시지 표시 영역"""

    DEFAULT_CSS = """
    ChatView {
        border: none;
        height: 1fr;
        width: 100%;
        padding: 1 2;
        overflow-y: auto;
        overflow-x: hidden;
        background: #0d1117;
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

    def write_wrapped(self, content: Union[str, Text]) -> None:
        """텍스트 출력 (자동 줄바꿈 처리)

        Args:
            content: 출력할 텍스트 (str 또는 Text 객체)

        Note:
            Text 객체의 경우 스타일이 보존되지 않고 일반 문자열로 변환됩니다.
            스타일을 보존하려면 write() 메서드를 직접 사용하세요.
        """
        # Text 객체는 일반 문자열로 변환 (스타일 제거)
        # RichLog의 wrap=True 옵션으로 자동 줄바꿈이 되므로
        # Text 객체는 그대로 write()로 전달하는 것이 더 좋습니다
        if isinstance(content, Text):
            # Text 객체는 그대로 write()로 전달
            super().write(content)
            return

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

    def add_user_message(
        self, content: str, timestamp: Optional[str] = None, tokens: Optional[int] = None
    ) -> None:
        """사용자 메시지 추가 (Claude Code 스타일: ❯ 사용)"""
        if timestamp is None:
            timestamp = datetime.now().strftime("%H:%M:%S")

        # 빈 줄
        self.write("")

        # 사용자 메시지: ❯ 로 시작 (Claude Code 스타일 - 큰 화살표)
        message = Text()
        message.append("❯ ", style="bold blue")
        message.append(content, style="")
        self.write(message)

        # 타임스탬프 및 토큰 표시 (선택적, dim 스타일로 작게)
        if self.show_timestamps or tokens:
            meta_text = Text()
            meta_text.append("  ", style="")

            if self.show_timestamps:
                meta_text.append(timestamp, style="dim")

            if tokens and tokens > 0:
                if self.show_timestamps:
                    meta_text.append(" │ ", style="dim")
                if tokens >= 1000:
                    token_str = f"{tokens/1000:.1f}K"
                else:
                    token_str = f"{tokens}"
                meta_text.append(f"{token_str} tokens", style="dim cyan")

            self.write(meta_text)

        self.write("")  # 간격

    def add_assistant_message(
        self, content: str, timestamp: Optional[str] = None, tokens: Optional[int] = None
    ) -> None:
        """어시스턴트 메시지 추가 (Claude Code 스타일: ● 사용)"""
        if timestamp is None:
            timestamp = datetime.now().strftime("%H:%M:%S")

        # 빈 줄
        self.write("")

        # 어시스턴트 메시지: ● 로 시작 (Claude Code 스타일 - 큰 원형 bullet)
        # 첫 줄에만 bullet point 표시
        lines = content.split("\n")

        # 첫 줄
        if lines:
            first_line = Text()
            first_line.append("● ", style="bold green")
            first_line.append(lines[0], style="")
            self.write(first_line)

        # 나머지 줄들 (들여쓰기)
        for line in lines[1:]:
            indented = Text()
            indented.append("  ", style="")  # 2칸 들여쓰기
            indented.append(line, style="")
            self.write(indented)

        # 타임스탬프 및 토큰 표시 (선택적, dim 스타일로 작게)
        if self.show_timestamps or tokens:
            meta_text = Text()
            meta_text.append("  ", style="")

            if self.show_timestamps:
                meta_text.append(timestamp, style="dim")

            if tokens and tokens > 0:
                if self.show_timestamps:
                    meta_text.append(" │ ", style="dim")
                if tokens >= 1000:
                    token_str = f"{tokens/1000:.1f}K"
                else:
                    token_str = f"{tokens}"
                meta_text.append(f"{token_str} tokens", style="dim cyan")

            self.write(meta_text)

        self.write("")  # 간격

    def add_system_message(self, message: str, style: str = "yellow") -> None:
        """시스템 메시지 추가 (Claude Code 스타일)"""
        # 시스템 메시지 박스
        system_text = Text()
        system_text.append("", style=style)
        system_text.append(f"{message}", style=style)
        self.write(system_text)
        self.write("")

    def add_error_message(self, error: str) -> None:
        """에러 메시지 추가 (Claude Code 스타일)"""
        # 에러 박스
        error_text = Text()
        error_text.append("✗ ", style="bold red")
        error_text.append("Error", style="bold red")
        error_text.append(f"\n{error}", style="red")
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

    def add_completion_message(self, tokens_used: Optional[int] = None) -> None:
        """응답 완료 메시지 추가 (간결한 피드백)"""
        completion_text = Text()
        completion_text.append("✓ ", style="green")
        completion_text.append("응답 완료", style="dim green")

        # 토큰 정보 추가 (선택적)
        if tokens_used and tokens_used > 0:
            if tokens_used >= 1000:
                token_str = f"{tokens_used/1000:.1f}K"
            else:
                token_str = f"{tokens_used}"
            completion_text.append(f" ({token_str} tokens)", style="dim cyan")

        self.write(completion_text)
        self.write("")  # 간격

