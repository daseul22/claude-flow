"""입력창 컴포넌트"""

from textual.widgets import TextArea
from textual.message import Message

from ..utils.keymap import normalize_shortcut_key


class InputBox(TextArea):
    """메시지 입력창"""

    DEFAULT_CSS = """
    InputBox {
        height: 3;
        width: 100%;
        border: solid #8b5cf6;
        background: #0d1117;
        margin: 0;
        padding: 0;
    }

    InputBox:focus {
        border: solid #8b5cf6;
        background: #0d1117;
    }

    InputBox:disabled {
        border: solid #4a4a4a;
        background: #1a1a1a;
        opacity: 0.6;
    }
    """

    class Submitted(Message):
        """메시지 전송 이벤트"""

        def __init__(self, text: str):
            super().__init__()
            self.text = text

    def __init__(self, **kwargs):
        super().__init__(
            show_line_numbers=False,
            **kwargs
        )
        self.input_history: list[str] = []
        self.history_index = -1
        self.temp_input = ""  # 이력 탐색 전 원래 입력 임시 저장

    async def on_key(self, event) -> None:
        """키 이벤트 처리"""
        key = normalize_shortcut_key(event.key)

        # Shift+Enter는 줄바꿈 (기본 동작)
        if key == "shift+enter":
            # TextArea 기본 동작으로 줄바꿈
            return
        
        # Enter로 전송
        elif key == "enter":
            await self.submit_message()
            event.prevent_default()
            event.stop()
        
        # Ctrl+Enter도 전송 (대안)
        elif key == "ctrl+enter":
            await self.submit_message()
            event.prevent_default()
            event.stop()

        # 위/아래 화살표로 히스토리 탐색 (항상 가능)
        elif key == "up":
            if self.input_history:
                # 첫 탐색이면 현재 입력 저장
                if self.history_index == -1:
                    self.temp_input = self.text

                # 이력을 위로 탐색
                if self.history_index < len(self.input_history) - 1:
                    self.history_index += 1
                    self.text = self.input_history[-(self.history_index + 1)]
            event.prevent_default()

        elif key == "down":
            # 이력 탐색 중일 때만 작동
            if self.history_index > 0:
                self.history_index -= 1
                self.text = self.input_history[-(self.history_index + 1)]
                event.prevent_default()
            elif self.history_index == 0:
                # 원래 입력으로 복원
                self.history_index = -1
                self.text = self.temp_input
                self.temp_input = ""
                event.prevent_default()

    async def submit_message(self) -> None:
        """메시지 전송"""
        text = self.text.strip()

        if text:
            # 히스토리에 추가
            self.input_history.append(text)
            self.history_index = -1
            self.temp_input = ""  # 임시 입력 초기화

            # 이벤트 발생
            self.post_message(self.Submitted(text))

            # 입력창 초기화
            self.text = ""

    def clear_input(self) -> None:
        """입력창 초기화"""
        self.text = ""
        self.history_index = -1
        self.temp_input = ""  # 임시 입력 초기화

