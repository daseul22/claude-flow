"""응답 처리 핸들러"""

from typing import Dict, Any
from rich.text import Text

from ..components.chat_view import ChatView
from .response_parser import ResponseParser
from ..config.settings import DisplaySettings
from .feedback_loop_improved import EvaluationResult


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

    def on_todo_update(self, todos: list[Dict[str, Any]]) -> None:
        """TodoWrite 투두 리스트 업데이트 처리"""
        formatted = self.parser.format_todo_list(todos)
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

    def on_eval_result(self, eval_result: EvaluationResult) -> None:
        """평가 결과 (개선된 버전 - 구조화된 평가)"""
        result_text = Text()

        # 품질 점수 표시
        score_emoji = "🟢" if eval_result.score >= 0.8 else "🟡" if eval_result.score >= 0.5 else "🔴"
        result_text.append(f"\n{score_emoji} ", style="")
        result_text.append(f"품질 점수: {eval_result.score:.2f} / 1.0", style="bold cyan")

        # 통과 여부
        result_text.append("\n", style="")
        if eval_result.passed:
            result_text.append("✅ 조건 충족", style="bold green")
        else:
            result_text.append("❌ 조건 미충족 - 재시도 필요", style="bold red")

        # 평가 이유
        result_text.append("\n💭 ", style="yellow")
        result_text.append("평가: ", style="bold yellow")
        result_text.append(eval_result.reasoning, style="white")

        # 개선 제안 (조건 미충족 시)
        if not eval_result.passed and eval_result.suggestions:
            result_text.append("\n\n💡 ", style="cyan")
            result_text.append("개선 제안:", style="bold cyan")
            for i, suggestion in enumerate(eval_result.suggestions, 1):
                result_text.append(f"\n  {i}. {suggestion}", style="white")

        result_text.append("\n", style="")
        result_text.append("━" * 60, style="dim yellow")
        self.chat_view.write(result_text)


class SmartFeedbackLoopCallbackHandler(FeedbackLoopCallbackHandler):
    """스마트 피드백 루프 응답 콜백 핸들러 (조건 생성 콜백 추가)"""

    def on_condition_generation(self, chunk: str) -> None:
        """조건 생성 과정 출력"""
        # 조건 생성 헤더 (처음 호출 시에만)
        if not hasattr(self, "_condition_generation_started"):
            self._condition_generation_started = True
            header = Text("\n", style="")
            header.append("━" * 60, style="dim cyan")
            header.append("\n🧠 ", style="cyan")
            header.append("조건 자동 생성 중...", style="bold cyan")
            header.append("\n", style="")
            self.chat_view.write(header)

        # 조건 생성 출력 (dim 스타일)
        self.chat_view.write(Text(chunk, style="dim white"))
