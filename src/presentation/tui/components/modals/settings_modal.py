"""설정 모달"""

from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.containers import Container, Vertical, Horizontal
from textual.widgets import Button, Label, Select, Checkbox, Input, Static
from typing import Dict, Any


class SettingsModal(ModalScreen[Dict[str, Any]]):
    """설정 모달"""

    DEFAULT_CSS = """
    SettingsModal {
        align: center middle;
    }

    SettingsModal > Container {
        width: 90;
        height: auto;
        max-height: 40;
        border: solid $primary;
        background: $surface;
        padding: 2 3;
    }

    SettingsModal .setting-row {
        height: auto;
        margin: 2 0;
        padding: 1 0;
    }

    SettingsModal Label {
        width: 35;
        padding: 0 1;
    }

    SettingsModal Select {
        width: 45;
    }

    SettingsModal Input {
        width: 45;
    }

    SettingsModal .buttons {
        height: auto;
        align: center middle;
        margin-top: 3;
        padding: 1 0;
    }
    
    SettingsModal Button {
        margin: 0 1;
        min-width: 12;
    }
    
    SettingsModal #title {
        text-align: center;
        text-style: bold;
        margin-bottom: 2;
    }
    
    SettingsModal .section-label {
        text-style: bold;
        color: $accent;
        margin-top: 1;
        margin-bottom: 1;
    }
    
    SettingsModal .spacer {
        height: 1;
    }
    """

    def __init__(self, current_settings: Dict[str, Any], **kwargs):
        super().__init__(**kwargs)
        self.settings = current_settings.copy()

    def compose(self) -> ComposeResult:
        """컴포넌트 구성"""
        with Container():
            yield Label("⚙️  설정", id="title")
            yield Static("", classes="spacer")

            # 모델 선택
            yield Label("모델 선택:", classes="section-label")
            with Horizontal(classes="setting-row"):
                yield Label("  모델:")
                yield Select(
                    options=[
                        ("Claude 4.5 Sonnet (기본)", "claude-sonnet-4.5"),
                        ("Claude 4.1 Opus", "claude-opus-4.1"),
                        ("Claude 4.5 Haiku", "claude-haiku-4.5"),
                    ],
                    value=self.settings.get("model", "claude-sonnet-4.5"),
                    id="model-select"
                )

            yield Static("", classes="spacer")

            # 피드백 루프 섹션
            yield Label("피드백 루프 설정:", classes="section-label")
            
            with Horizontal(classes="setting-row"):
                yield Label("  활성화:")
                yield Checkbox(
                    "피드백 루프 사용",
                    value=self.settings.get("feedback_loop_enabled", False),
                    id="feedback-enabled"
                )

            with Vertical(classes="setting-row"):
                yield Label("  조건 프롬프트:")
                yield Input(
                    value=self.settings.get("condition_prompt", "출력에 에러가 있는지 확인해주세요"),
                    placeholder="예: 출력에 에러가 없고 완성도가 높은지 확인",
                    id="condition-prompt"
                )

            with Horizontal(classes="setting-row"):
                yield Label("  최대 반복:")
                yield Input(
                    value=str(self.settings.get("max_iterations", 3)),
                    placeholder="1-30",
                    id="max-iterations"
                )

            with Horizontal(classes="setting-row"):
                yield Label("  평가 모델:")
                yield Select(
                    options=[
                        ("Haiku (빠름, 저렴)", "claude-haiku-4-5-20251001"),
                        ("Sonnet (균형)", "claude-sonnet-4-5-20250929"),
                    ],
                    value=self.settings.get("condition_model", "claude-haiku-4-5-20251001"),
                    id="condition-model"
                )

            yield Static("", classes="spacer")

            # 표시 옵션 섹션
            yield Label("표시 옵션:", classes="section-label")
            
            with Horizontal(classes="setting-row"):
                yield Label("  타임스탬프:")
                yield Checkbox(
                    "메시지에 시간 표시",
                    value=self.settings.get("show_timestamps", True),
                    id="show-timestamps"
                )

            with Horizontal(classes="setting-row"):
                yield Label("  토큰 카운트:")
                yield Checkbox(
                    "토큰 사용량 표시",
                    value=self.settings.get("show_token_counts", True),
                    id="show-token-counts"
                )

            yield Static("", classes="spacer")

            # 버튼
            with Horizontal(classes="buttons"):
                yield Button("저장", variant="primary", id="save")
                yield Button("취소", variant="default", id="cancel")

    def _collect_settings(self) -> Dict[str, Any]:
        """설정 수집"""
        # 최대 반복 횟수 검증
        try:
            max_iter = int(self.query_one("#max-iterations", Input).value or "3")
            if not (1 <= max_iter <= 30):
                max_iter = 3
        except ValueError:
            max_iter = 3

        return {
            "model": self.query_one("#model-select", Select).value,
            "feedback_loop_enabled": self.query_one("#feedback-enabled", Checkbox).value,
            "condition_prompt": self.query_one("#condition-prompt", Input).value.strip(),
            "max_iterations": max_iter,
            "condition_model": self.query_one("#condition-model", Select).value,
            "show_timestamps": self.query_one("#show-timestamps", Checkbox).value,
            "show_token_counts": self.query_one("#show-token-counts", Checkbox).value,
        }

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """버튼 클릭 처리"""
        if event.button.id == "save":
            settings = self._collect_settings()
            self.dismiss(settings)
        elif event.button.id == "cancel":
            self.dismiss(None)

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Input에서 엔터 누르면 저장"""
        settings = self._collect_settings()
        self.dismiss(settings)

