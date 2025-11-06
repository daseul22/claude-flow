"""세션 목록 모달"""

from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.containers import Container, Vertical
from textual.widgets import Button, Label, ListView, ListItem


class SessionListModal(ModalScreen[str]):
    """세션 목록 선택 모달"""

    DEFAULT_CSS = """
    SessionListModal {
        align: center middle;
    }

    SessionListModal > Container {
        width: 80;
        height: 30;
        border: solid $primary;
        background: $surface;
        padding: 1;
    }

    SessionListModal ListView {
        height: 20;
        border: solid $accent;
    }

    SessionListModal .buttons {
        height: 3;
        align: center middle;
    }
    """

    def __init__(self, sessions: list, **kwargs):
        super().__init__(**kwargs)
        self.sessions = sessions

    def compose(self) -> ComposeResult:
        """컴포넌트 구성"""
        with Container():
            yield Label("📋 세션 목록", id="title")

            # 세션 목록
            with ListView():
                for session in self.sessions:
                    session_id = session["session_id"][:8]
                    created = session["created_at"][:10]
                    msg_count = session["message_count"]
                    first_msg = session.get("first_message", "")[:50]

                    item_text = f"{session_id} | {created} | {msg_count}개 메시지\n  {first_msg}..."

                    yield ListItem(
                        Label(item_text),
                        id=f"session-{session['session_id']}"
                    )

            # 버튼
            with Vertical(classes="buttons"):
                yield Button("선택", variant="primary", id="select")
                yield Button("취소", variant="default", id="cancel")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """버튼 클릭 처리"""
        if event.button.id == "select":
            # 선택된 세션 찾기
            list_view = self.query_one(ListView)
            if list_view.index is not None and list_view.index < len(self.sessions):
                selected_session = self.sessions[list_view.index]
                self.dismiss(selected_session["session_id"])
            else:
                self.dismiss()

        elif event.button.id == "cancel":
            self.dismiss()

    async def on_list_view_selected(self, event: ListView.Selected) -> None:
        """리스트 아이템 더블클릭으로 선택"""
        if event.item:
            try:
                list_items = list(self.query(ListItem))
                session_index = list_items.index(event.item)
                if session_index < len(self.sessions):
                    selected_session = self.sessions[session_index]
                    self.dismiss(selected_session["session_id"])
            except (ValueError, IndexError):
                pass

