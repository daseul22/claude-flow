"""입력창 컴포넌트"""

from textual.widgets import TextArea
from textual.message import Message


class InputBox(TextArea):
    """메시지 입력창"""

    DEFAULT_CSS = """
    InputBox {
        dock: bottom;
        height: 5;
        border: solid $accent;
    }
    """

    class Submitted(Message):
        """메시지 전송 이벤트"""

        def __init__(self, text: str):
            super().__init__()
            self.text = text

    def __init__(self, **kwargs):
        super().__init__(
            language="markdown",
            theme="monokai",
            show_line_numbers=False,
            **kwargs
        )
        self.input_history: list[str] = []
        self.history_index = -1

    async def on_key(self, event) -> None:
        """키 이벤트 처리"""
        # Enter로 전송 (Shift+Enter는 줄바꿈)
        # Textual에서는 Shift가 눌린 경우 event에 shift 속성이 없으므로
        # 기본 동작을 그대로 사용 (TextArea가 줄바꿈 처리)
        if event.key == "enter":
            # Shift가 눌리지 않았을 때만 전송
            # Textual의 Key 이벤트는 shift 수식자를 별도로 체크해야 함
            # 간단하게 처리: enter만 누르면 전송
            await self.submit_message()
            event.prevent_default()

        # Ctrl+Enter도 전송으로 처리 (대안)
        elif event.key == "ctrl+enter":
            await self.submit_message()
            event.prevent_default()

        # 위/아래 화살표로 히스토리 탐색 (입력창이 비어있을 때만)
        elif event.key == "up" and not self.text:
            if self.input_history:
                if self.history_index < len(self.input_history) - 1:
                    self.history_index += 1
                    self.text = self.input_history[-(self.history_index + 1)]
            event.prevent_default()

        elif event.key == "down" and not self.text:
            if self.history_index > 0:
                self.history_index -= 1
                self.text = self.input_history[-(self.history_index + 1)]
            elif self.history_index == 0:
                self.history_index = -1
                self.text = ""
            event.prevent_default()

    async def submit_message(self):
        """메시지 전송"""
        text = self.text.strip()

        if text:
            # 히스토리에 추가
            self.input_history.append(text)
            self.history_index = -1

            # 이벤트 발생
            self.post_message(self.Submitted(text))

            # 입력창 초기화
            self.text = ""

    def clear_input(self):
        """입력창 초기화"""
        self.text = ""
        self.history_index = -1

    def set_placeholder(self, text: str):
        """플레이스홀더 설정"""
        # Textual TextArea는 플레이스홀더를 직접 지원하지 않으므로
        # 비어있을 때만 임시로 표시
        if not self.text:
            self.text = text

