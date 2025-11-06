"""단축키 도움말 모달"""

from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.containers import Container, Vertical
from textual.widgets import Button, Label, Static
from rich.table import Table


class HelpModal(ModalScreen):
    """단축키 도움말 모달"""

    DEFAULT_CSS = """
    HelpModal {
        align: center middle;
    }

    HelpModal > Container {
        width: 70;
        height: 30;
        border: solid $primary;
        background: $surface;
        padding: 1 2;
    }

    HelpModal .buttons {
        height: 3;
        align: center middle;
        margin-top: 1;
    }
    """

    def compose(self) -> ComposeResult:
        """컴포넌트 구성"""
        with Container():
            yield Label("⌨️  키보드 단축키", id="title")
            yield Static("")

            # 단축키 테이블 생성
            table = Table(title="", show_header=True, box=None)
            table.add_column("단축키", style="cyan", width=20)
            table.add_column("기능", style="white", width=35)

            # 세션 관리
            table.add_row("Ctrl+N", "새 세션")
            table.add_row("Ctrl+O", "세션 불러오기")
            
            # 프로젝트
            table.add_row("Ctrl+I", "프로젝트 정보")
            table.add_row("cd [경로]", "작업 디렉토리 변경")
            table.add_row("cd -", "이전 디렉토리로 돌아가기")
            
            # 설정
            table.add_row("Ctrl+,", "설정 열기")
            
            # 화면 제어
            table.add_row("Ctrl+L", "화면 지우기 (대화 기록 유지)")
            
            # 입력
            table.add_row("Enter", "메시지 전송")
            table.add_row("Ctrl+Enter", "메시지 전송 (대안)")
            table.add_row("↑ / ↓", "이전 입력 탐색")
            
            # 중단/종료
            table.add_row("Ctrl+C", "중단 / 입력 취소 / 종료")
            table.add_row("Ctrl+Q", "앱 종료")
            table.add_row("Esc", "모달 닫기")
            
            # 도움말
            table.add_row("Ctrl+/ 또는 F1", "이 도움말 표시")

            yield Static(table)
            yield Static("")

            # 버튼
            with Vertical(classes="buttons"):
                yield Button("닫기", variant="primary", id="close")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """버튼 클릭 처리"""
        self.dismiss()

