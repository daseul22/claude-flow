"""컨텍스트 사이드바: 컨텍스트 파일 목록 표시 및 관리"""

from pathlib import Path
from typing import Optional

from textual.app import ComposeResult
from textual.containers import VerticalScroll, Horizontal
from textual.widgets import Static, Button, ListView, ListItem
from textual.message import Message
from rich.text import Text

from ..services.context_manager import ContextManager, ContextFile


class ContextFileItem(ListItem):
    """컨텍스트 파일 아이템"""

    def __init__(self, context_file: ContextFile, **kwargs):
        super().__init__(**kwargs)
        self.context_file = context_file

    def compose(self) -> ComposeResult:
        """컴포넌트 구성"""
        # 파일 상태 아이콘
        icon = "✓" if self.context_file.enabled else "○"
        icon_color = "green" if self.context_file.enabled else "dim"

        # 파일 타입 아이콘
        if self.context_file.is_directory:
            type_icon = "📁"
        else:
            type_icon = "📄"

        # 파일 크기 포맷팅
        size_kb = self.context_file.size_bytes / 1024
        if size_kb < 1:
            size_str = f"{self.context_file.size_bytes}B"
        elif size_kb < 1024:
            size_str = f"{size_kb:.1f}KB"
        else:
            size_str = f"{size_kb / 1024:.1f}MB"

        # 텍스트 구성
        text = Text()
        text.append(f"{icon} ", style=icon_color)
        text.append(f"{type_icon} ")
        text.append(self.context_file.label or "Unknown", style="bold")
        text.append(f" ({size_str})", style="dim")

        yield Static(text)


class ContextSidebar(VerticalScroll):
    """컨텍스트 사이드바"""

    DEFAULT_CSS = """
    ContextSidebar {
        width: 40;
        border-left: solid #8b5cf6;
        background: #161b22;
        padding: 1;
    }

    ContextSidebar #sidebar-title {
        margin-bottom: 1;
        color: #8b949e;
        text-style: bold;
    }

    ContextSidebar Button {
        margin-bottom: 1;
        width: 100%;
    }

    ContextSidebar ListView {
        height: auto;
        border: solid #30363d;
        background: #0d1117;
        margin-bottom: 1;
    }

    ContextSidebar .stats {
        margin-top: 1;
        padding: 1;
        border: solid #30363d;
        background: #0d1117;
        color: #8b949e;
    }
    """

    class FileToggled(Message):
        """파일 토글 메시지"""

        def __init__(self, file_path: str) -> None:
            super().__init__()
            self.file_path = file_path

    class FileRemoved(Message):
        """파일 제거 메시지"""

        def __init__(self, file_path: str) -> None:
            super().__init__()
            self.file_path = file_path

    class AddFileRequested(Message):
        """파일 추가 요청 메시지"""
        pass

    class ManagePresetsRequested(Message):
        """프리셋 관리 요청 메시지"""
        pass

    def __init__(
        self,
        context_manager: ContextManager,
        show: bool = True,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.context_manager = context_manager
        self.display = show

    def compose(self) -> ComposeResult:
        """컴포넌트 구성"""
        yield Static("📋 컨텍스트 관리", id="sidebar-title")

        # 컨트롤 버튼
        with Horizontal():
            yield Button("➕ 추가", id="add-file-btn", variant="primary")
            yield Button("📦 프리셋", id="manage-presets-btn", variant="default")

        # 파일 목록
        yield ListView(id="context-file-list")

        # 통계 정보
        yield Static("", id="context-stats", classes="stats")

    def on_mount(self) -> None:
        """마운트 시 파일 목록 로드"""
        self.refresh_file_list()

    def refresh_file_list(self) -> None:
        """파일 목록 갱신"""
        list_view = self.query_one("#context-file-list", ListView)
        list_view.clear()

        files = self.context_manager.get_all_files()

        if not files:
            # Text 객체를 사용하여 스타일 적용
            empty_text = Text("파일이 없습니다", style="dim italic")
            list_view.append(ListItem(Static(empty_text)))
        else:
            for cf in files:
                list_view.append(ContextFileItem(cf))

        # 통계 업데이트
        self.update_stats()

    def update_stats(self) -> None:
        """통계 정보 업데이트"""
        all_files = self.context_manager.get_all_files()
        enabled_files = self.context_manager.get_enabled_files()
        total_size = self.context_manager.get_total_size()

        size_kb = total_size / 1024
        if size_kb < 1024:
            size_str = f"{size_kb:.1f} KB"
        else:
            size_str = f"{size_kb / 1024:.1f} MB"

        stats_text = Text()
        stats_text.append(f"총 파일: ", style="dim")
        stats_text.append(f"{len(all_files)}", style="bold")
        stats_text.append(f" (활성: ", style="dim")
        stats_text.append(f"{len(enabled_files)}", style="bold green")
        stats_text.append(f")\n", style="dim")
        stats_text.append(f"총 크기: ", style="dim")
        stats_text.append(size_str, style="bold cyan")

        stats_widget = self.query_one("#context-stats", Static)
        stats_widget.update(stats_text)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """버튼 클릭 이벤트"""
        if event.button.id == "add-file-btn":
            self.post_message(self.AddFileRequested())
        elif event.button.id == "manage-presets-btn":
            self.post_message(self.ManagePresetsRequested())

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """리스트 아이템 선택 이벤트"""
        if isinstance(event.item, ContextFileItem):
            # 토글 처리
            self.context_manager.toggle_file(event.item.context_file.path)
            self.refresh_file_list()
            self.post_message(self.FileToggled(event.item.context_file.path))

    def toggle_visibility(self) -> None:
        """사이드바 표시/숨김 토글"""
        self.display = not self.display
