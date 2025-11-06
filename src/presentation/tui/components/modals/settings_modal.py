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
        width: 80;
        height: 35;
        border: solid $primary;
        background: $surface;
        padding: 1 2;
    }

    SettingsModal .setting-row {
        height: 3;
        margin: 1 0;
    }

    SettingsModal Label {
        width: 30;
    }

    SettingsModal Select {
        width: 40;
    }

    SettingsModal Input {
        width: 40;
    }

    SettingsModal .buttons {
        height: 3;
        align: center middle;
        margin-top: 2;
    }
    """

    def __init__(self, current_settings: Dict[str, Any], **kwargs):
        super().__init__(**kwargs)
        self.settings = current_settings.copy()

    def compose(self) -> ComposeResult:
        """컴포넌트 구성"""
        with Container():
            yield Label("⚙️  설정", id="title")
            yield Static("")

            # 모델 선택
            with Horizontal(classes="setting-row"):
                yield Label("모델:")
                yield Select(
                    options=[
                        ("Claude 4.5 Sonnet (기본)", "claude-sonnet-4.5"),
                        ("Claude 4.1 Opus", "claude-opus-4.1"),
                        ("Claude 4.5 Haiku", "claude-haiku-4.5"),
                    ],
                    value=self.settings.get("model", "claude-sonnet-4.5"),
                    id="model-select"
                )

            # 피드백 루프 활성화
            with Horizontal(classes="setting-row"):
                yield Label("피드백 루프:")
                yield Checkbox(
                    "활성화",
                    value=self.settings.get("feedback_loop_enabled", False),
                    id="feedback-enabled"
                )

            # 피드백 루프 최대 반복
            with Horizontal(classes="setting-row"):
                yield Label("최대 반복 횟수:")
                yield Input(
                    value=str(self.settings.get("max_iterations", 3)),
                    placeholder="1-30",
                    id="max-iterations"
                )

            # 피드백 루프 조건 모델
            with Horizontal(classes="setting-row"):
                yield Label("조건 평가 모델:")
                yield Select(
                    options=[
                        ("Haiku (빠름, 저렴)", "claude-haiku-4-5-20251001"),
                        ("Sonnet (균형)", "claude-sonnet-4-5-20250929"),
                    ],
                    value=self.settings.get("condition_model", "claude-haiku-4-5-20251001"),
                    id="condition-model"
                )

            # 타임스탬프 표시
            with Horizontal(classes="setting-row"):
                yield Label("타임스탬프 표시:")
                yield Checkbox(
                    "표시",
                    value=self.settings.get("show_timestamps", True),
                    id="show-timestamps"
                )

            # 토큰 카운트 표시
            with Horizontal(classes="setting-row"):
                yield Label("토큰 카운트 표시:")
                yield Checkbox(
                    "표시",
                    value=self.settings.get("show_token_counts", True),
                    id="show-token-counts"
                )

            yield Static("")

            # 버튼
            with Horizontal(classes="buttons"):
                yield Button("저장", variant="primary", id="save")
                yield Button("취소", variant="default", id="cancel")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """버튼 클릭 처리"""
        if event.button.id == "save":
            # 설정 수집
            settings = {
                "model": self.query_one("#model-select", Select).value,
                "feedback_loop_enabled": self.query_one("#feedback-enabled", Checkbox).value,
                "max_iterations": int(self.query_one("#max-iterations", Input).value or "3"),
                "condition_model": self.query_one("#condition-model", Select).value,
                "show_timestamps": self.query_one("#show-timestamps", Checkbox).value,
                "show_token_counts": self.query_one("#show-token-counts", Checkbox).value,
            }
            self.dismiss(settings)

        elif event.button.id == "cancel":
            self.dismiss(None)

