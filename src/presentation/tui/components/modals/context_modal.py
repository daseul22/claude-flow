"""컨텍스트 관리 모달들"""

from pathlib import Path
from typing import Optional

from textual.app import ComposeResult
from textual.containers import Grid, Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static, TextArea, ListView, ListItem
from rich.text import Text

from ...services.context_manager import ContextManager, ContextPreset


class AddContextFileModal(ModalScreen):
    """파일 추가 모달"""

    DEFAULT_CSS = """
    AddContextFileModal {
        align: center middle;
    }

    AddContextFileModal > Grid {
        width: 80;
        height: auto;
        border: solid #8b5cf6;
        background: #0d1117;
        padding: 1;
    }

    AddContextFileModal Label {
        margin-bottom: 1;
    }

    AddContextFileModal Input {
        margin-bottom: 1;
    }

    AddContextFileModal Button {
        margin: 1 1 0 1;
    }
    """

    def __init__(
        self,
        context_manager: ContextManager,
        project_path: Path,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.context_manager = context_manager
        self.project_path = project_path

    def compose(self) -> ComposeResult:
        """컴포넌트 구성"""
        with Grid():
            yield Label("📁 컨텍스트에 파일 추가", id="modal-title")

            yield Label("파일 경로 (절대 경로 또는 프로젝트 상대 경로):")
            yield Input(
                placeholder=str(self.project_path / "src/main.py"),
                id="file-path-input"
            )

            yield Label("라벨 (선택 사항, 기본: 상대 경로):")
            yield Input(
                placeholder="예: main.py",
                id="file-label-input"
            )

            with Horizontal():
                yield Button("추가", id="add-btn", variant="primary")
                yield Button("취소", id="cancel-btn", variant="default")

    def on_mount(self) -> None:
        """마운트 시 포커스 설정"""
        self.query_one("#file-path-input", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """버튼 클릭 이벤트"""
        if event.button.id == "cancel-btn":
            self.dismiss(None)

        elif event.button.id == "add-btn":
            # 입력값 가져오기
            path_input = self.query_one("#file-path-input", Input)
            label_input = self.query_one("#file-label-input", Input)

            file_path_str = path_input.value.strip()
            label = label_input.value.strip() or None

            if not file_path_str:
                # TODO: 에러 메시지 표시
                return

            # 경로 변환
            file_path = Path(file_path_str)

            if not file_path.is_absolute():
                # 상대 경로면 프로젝트 루트 기준
                file_path = self.project_path / file_path

            # 추가
            success = self.context_manager.add_file(file_path, label=label)

            if success:
                self.dismiss(file_path)
            else:
                # TODO: 에러 메시지 표시
                pass


class ManagePresetsModal(ModalScreen):
    """프리셋 관리 모달"""

    DEFAULT_CSS = """
    ManagePresetsModal {
        align: center middle;
    }

    ManagePresetsModal > Grid {
        width: 80;
        height: 30;
        border: solid #8b5cf6;
        background: #0d1117;
        padding: 1;
    }

    ManagePresetsModal Label {
        margin-bottom: 1;
    }

    ManagePresetsModal ListView {
        height: 15;
        border: solid #30363d;
        background: #161b22;
        margin-bottom: 1;
    }

    ManagePresetsModal Button {
        margin: 1 1 0 1;
    }
    """

    def __init__(self, context_manager: ContextManager, **kwargs):
        super().__init__(**kwargs)
        self.context_manager = context_manager

    def compose(self) -> ComposeResult:
        """컴포넌트 구성"""
        with Grid():
            yield Label("📦 프리셋 관리", id="modal-title")

            yield ListView(id="presets-list")

            with Horizontal():
                yield Button("새 프리셋 저장", id="save-btn", variant="primary")
                yield Button("불러오기", id="load-btn", variant="success")
                yield Button("삭제", id="delete-btn", variant="error")
                yield Button("닫기", id="close-btn", variant="default")

    def on_mount(self) -> None:
        """마운트 시 프리셋 목록 로드"""
        self.refresh_presets()

    def refresh_presets(self) -> None:
        """프리셋 목록 갱신"""
        list_view = self.query_one("#presets-list", ListView)
        list_view.clear()

        presets = self.context_manager.list_presets()

        if not presets:
            # Text 객체를 사용하여 스타일 적용
            empty_text = Text("저장된 프리셋이 없습니다", style="dim italic")
            list_view.append(ListItem(Static(empty_text)))
        else:
            for preset in presets:
                text = Text()
                text.append(preset.name, style="bold cyan")
                text.append(f" ({len(preset.files)}개 파일)", style="dim")
                if preset.description:
                    text.append(f"\n  {preset.description}", style="dim italic")

                list_view.append(ListItem(Static(text)))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """버튼 클릭 이벤트"""
        if event.button.id == "close-btn":
            self.dismiss(None)

        elif event.button.id == "save-btn":
            # 새 프리셋 저장 모달 열기
            self.app.push_screen(SavePresetModal(self.context_manager), self.on_preset_saved)

        elif event.button.id == "load-btn":
            # 선택된 프리셋 불러오기
            list_view = self.query_one("#presets-list", ListView)
            if list_view.index is None:
                return

            presets = self.context_manager.list_presets()
            if 0 <= list_view.index < len(presets):
                preset = presets[list_view.index]
                self.context_manager.load_preset(preset.name)
                self.dismiss(preset.name)

        elif event.button.id == "delete-btn":
            # 선택된 프리셋 삭제
            list_view = self.query_one("#presets-list", ListView)
            if list_view.index is None:
                return

            presets = self.context_manager.list_presets()
            if 0 <= list_view.index < len(presets):
                preset = presets[list_view.index]
                self.context_manager.delete_preset(preset.name)
                self.refresh_presets()

    def on_preset_saved(self, result: Optional[str]) -> None:
        """프리셋 저장 후 콜백"""
        if result:
            self.refresh_presets()


class SavePresetModal(ModalScreen):
    """프리셋 저장 모달"""

    DEFAULT_CSS = """
    SavePresetModal {
        align: center middle;
    }

    SavePresetModal > Grid {
        width: 60;
        height: auto;
        border: solid #8b5cf6;
        background: #0d1117;
        padding: 1;
    }

    SavePresetModal Label {
        margin-bottom: 1;
    }

    SavePresetModal Input {
        margin-bottom: 1;
    }

    SavePresetModal TextArea {
        height: 5;
        margin-bottom: 1;
    }

    SavePresetModal Button {
        margin: 1 1 0 1;
    }
    """

    def __init__(self, context_manager: ContextManager, **kwargs):
        super().__init__(**kwargs)
        self.context_manager = context_manager

    def compose(self) -> ComposeResult:
        """컴포넌트 구성"""
        with Grid():
            yield Label("💾 현재 컨텍스트를 프리셋으로 저장", id="modal-title")

            file_count = len(self.context_manager.get_all_files())
            yield Label(f"현재 {file_count}개의 파일이 포함됩니다.")

            yield Label("프리셋 이름:")
            yield Input(placeholder="예: backend-dev", id="preset-name-input")

            yield Label("설명 (선택 사항):")
            yield TextArea(id="preset-description-input")

            with Horizontal():
                yield Button("저장", id="save-btn", variant="primary")
                yield Button("취소", id="cancel-btn", variant="default")

    def on_mount(self) -> None:
        """마운트 시 포커스 설정"""
        self.query_one("#preset-name-input", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """버튼 클릭 이벤트"""
        if event.button.id == "cancel-btn":
            self.dismiss(None)

        elif event.button.id == "save-btn":
            name_input = self.query_one("#preset-name-input", Input)
            desc_input = self.query_one("#preset-description-input", TextArea)

            name = name_input.value.strip()
            description = desc_input.text.strip()

            if not name:
                # TODO: 에러 메시지 표시
                return

            success = self.context_manager.save_preset(name, description)

            if success:
                self.dismiss(name)
            else:
                # TODO: 에러 메시지 표시
                pass
