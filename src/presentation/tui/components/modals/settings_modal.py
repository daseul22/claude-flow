"""설정 모달"""

from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.containers import Container, Vertical, Horizontal
from textual.widgets import Button, Label, Select, Checkbox, Input, Static
from typing import Dict, Any
from dataclasses import dataclass


@dataclass
class SettingsResult:
    """설정 모달 결과"""
    model: str
    feedback_loop_enabled: bool
    condition_prompt: str
    max_iterations: int
    condition_model: str
    feedback_input: str  # 회귀 시 전달할 입력
    quality_threshold: float  # 품질 임계값 (0.0 ~ 1.0)
    show_statusbar: bool
    show_timestamps: bool
    show_token_counts: bool
    enable_thinking: bool  # Thinking 블록 활성화
    show_thinking_full: bool  # Thinking 전체 표시

    def to_dict(self) -> Dict[str, Any]:
        """Dict로 변환"""
        return {
            "model": self.model,
            "feedback_loop_enabled": self.feedback_loop_enabled,
            "condition_prompt": self.condition_prompt,
            "max_iterations": self.max_iterations,
            "condition_model": self.condition_model,
            "feedback_input": self.feedback_input,
            "quality_threshold": self.quality_threshold,
            "show_statusbar": self.show_statusbar,
            "show_timestamps": self.show_timestamps,
            "show_token_counts": self.show_token_counts,
            "enable_thinking": self.enable_thinking,
            "show_thinking_full": self.show_thinking_full,
        }


class SettingsModal(ModalScreen[SettingsResult]):
    """설정 모달"""

    DEFAULT_CSS = """
    SettingsModal {
        align: center middle;
    }

    SettingsModal > Container {
        width: 90;
        height: auto;
        max-height: 90%;
        border: solid $primary;
        background: $surface;
        padding: 2 3;
        overflow-y: auto;
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
                        ("Claude Opus 4.1", "claude-opus-4.1"),
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

            with Vertical(classes="setting-row"):
                yield Label("  회귀 입력 메시지 (선택):")
                yield Input(
                    value=self.settings.get("feedback_input", ""),
                    placeholder="예: {{output}}을 보고 {{condition}}을 만족하도록 개선해주세요",
                    id="feedback-input"
                )

            with Horizontal(classes="setting-row"):
                yield Label("  최대 반복:")
                yield Input(
                    value=str(self.settings.get("max_iterations", 3)),
                    placeholder="1-30",
                    id="max-iterations"
                )

            with Horizontal(classes="setting-row"):
                yield Label("  품질 임계값:")
                yield Input(
                    value=str(self.settings.get("quality_threshold", 0.8)),
                    placeholder="0.0-1.0 (기본: 0.8)",
                    id="quality-threshold"
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
                yield Label("  상태바:")
                yield Checkbox(
                    "상태바 표시",
                    value=self.settings.get("show_statusbar", True),
                    id="show-statusbar"
                )
            
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

            # Thinking 블록 섹션
            yield Label("Thinking 블록 옵션:", classes="section-label")

            with Horizontal(classes="setting-row"):
                yield Label("  Thinking 활성화:")
                yield Checkbox(
                    "Thinking 블록 표시",
                    value=self.settings.get("enable_thinking", True),
                    id="enable-thinking"
                )

            with Horizontal(classes="setting-row"):
                yield Label("  전체 표시:")
                yield Checkbox(
                    "전체 Thinking 내용 표시 (체크 해제 시 요약만)",
                    value=self.settings.get("show_thinking_full", False),
                    id="show-thinking-full"
                )

            yield Static("", classes="spacer")

            # 버튼
            with Horizontal(classes="buttons"):
                yield Button("저장", variant="primary", id="save")
                yield Button("기본값", variant="warning", id="reset")
                yield Button("취소", variant="default", id="cancel")

    def _collect_settings(self) -> SettingsResult:
        """설정 수집"""
        # 최대 반복 횟수 검증
        try:
            max_iter = int(self.query_one("#max-iterations", Input).value or "3")
            if not (1 <= max_iter <= 30):
                max_iter = 3
        except ValueError:
            max_iter = 3

        # 품질 임계값 검증
        try:
            quality_threshold = float(self.query_one("#quality-threshold", Input).value or "0.8")
            if not (0.0 <= quality_threshold <= 1.0):
                quality_threshold = 0.8
        except ValueError:
            quality_threshold = 0.8

        # Select 값 안전하게 읽기
        model_select = self.query_one("#model-select", Select)
        model_value = model_select.value
        if model_value == Select.BLANK:
            model_value = "claude-sonnet-4.5"

        condition_model_select = self.query_one("#condition-model", Select)
        condition_model_value = condition_model_select.value
        if condition_model_value == Select.BLANK:
            condition_model_value = "claude-haiku-4-5-20251001"

        return SettingsResult(
            model=model_value,
            feedback_loop_enabled=self.query_one("#feedback-enabled", Checkbox).value,
            condition_prompt=self.query_one("#condition-prompt", Input).value.strip(),
            max_iterations=max_iter,
            condition_model=condition_model_value,
            feedback_input=self.query_one("#feedback-input", Input).value.strip(),
            quality_threshold=quality_threshold,
            show_statusbar=self.query_one("#show-statusbar", Checkbox).value,
            show_timestamps=self.query_one("#show-timestamps", Checkbox).value,
            show_token_counts=self.query_one("#show-token-counts", Checkbox).value,
            enable_thinking=self.query_one("#enable-thinking", Checkbox).value,
            show_thinking_full=self.query_one("#show-thinking-full", Checkbox).value,
        )

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """버튼 클릭 처리"""
        if event.button.id == "save":
            settings_result = self._collect_settings()
            self.dismiss(settings_result)
        elif event.button.id == "reset":
            # 기본값으로 리셋
            self.query_one("#model-select", Select).value = "claude-sonnet-4.5"
            self.query_one("#feedback-enabled", Checkbox).value = False
            self.query_one("#condition-prompt", Input).value = ""
            self.query_one("#feedback-input", Input).value = ""
            self.query_one("#max-iterations", Input).value = "3"
            self.query_one("#quality-threshold", Input).value = "0.8"
            self.query_one("#condition-model", Select).value = "claude-haiku-4-5-20251001"
            self.query_one("#show-statusbar", Checkbox).value = True
            self.query_one("#show-timestamps", Checkbox).value = True
            self.query_one("#show-token-counts", Checkbox).value = True
            self.query_one("#enable-thinking", Checkbox).value = True
            self.query_one("#show-thinking-full", Checkbox).value = False
        elif event.button.id == "cancel":
            self.dismiss(None)

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Input에서 엔터 누르면 저장"""
        settings_result = self._collect_settings()
        self.dismiss(settings_result)

