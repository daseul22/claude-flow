"""응답 처리 핸들러"""

from typing import Dict, Any
from rich.text import Text

from ..components.chat_view import ChatView
from .response_parser import ResponseParser
from ..config.settings import DisplaySettings


class ResponseCallbackHandler:
    """응답 콜백 핸들러 - 에이전트 응답의 각종 블록을 처리"""

    def __init__(
        self, chat_view: ChatView, parser: ResponseParser, display_config: DisplaySettings
    ):
        """
        Args:
            chat_view: 채팅 뷰 위젯
            parser: 응답 파서
            display_config: 디스플레이 설정
        """
        self.chat_view = chat_view
        self.parser = parser
        self.display_config = display_config

    def on_thinking(self, thinking: str) -> None:
        """ThinkingBlock 처리"""
        show_full = self.display_config.show_thinking_full
        formatted = self.parser.format_thinking_block(thinking, show_full=show_full)
        self.chat_view.write(formatted)
        self.chat_view.write("")  # 블록 간 간격

    def on_tool_use(self, tool_name: str, tool_input: Dict[str, Any]) -> None:
        """ToolUseBlock 처리"""
        formatted = self.parser.format_tool_use(tool_name, tool_input)
        self.chat_view.write(formatted)
        self.chat_view.write("")  # 블록 간 간격

    def on_tool_result(self, result: str) -> None:
        """ToolResultBlock 처리"""
        formatted = self.parser.format_tool_result("", result)
        self.chat_view.write(formatted)
        self.chat_view.write("")  # 블록 간 간격


class FeedbackLoopCallbackHandler(ResponseCallbackHandler):
    """피드백 루프 응답 콜백 핸들러 (평가 콜백 추가)"""

    def on_eval_start(self) -> None:
        """평가 시작"""
        eval_header = Text("\n", style="")
        eval_header.append("━" * 60, style="dim yellow")
        eval_header.append("\n🔍 ", style="yellow")
        eval_header.append("조건 평가 중...", style="bold yellow")
        self.chat_view.write(eval_header)

    def on_eval_output(self, chunk: str) -> None:
        """평가 LLM 출력"""
        self.chat_view.write_wrapped(chunk)

    def on_eval_result(self, condition_met: bool, eval_response: str) -> None:
        """평가 결과"""
        result_text = Text()
        if condition_met:
            result_text.append("✅ 조건 충족", style="bold green")
        else:
            result_text.append("❌ 조건 미충족 - 재시도 필요", style="bold red")
        result_text.append("\n", style="")
        result_text.append("━" * 60, style="dim yellow")
        self.chat_view.write(result_text)
