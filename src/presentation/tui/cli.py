"""Claude Flow TUI CLI 진입점"""

import sys
import os
from pathlib import Path
import click
from dotenv import load_dotenv

from .app import ClaudeFlowApp


@click.command()
@click.argument(
    "project_path",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    required=False,
    default=None,
)
@click.option(
    "--version",
    is_flag=True,
    help="버전 정보 표시",
)
def main(project_path: Path = None, version: bool = False):
    """
    Claude Flow TUI - LLM 피드백 루프 기반 대화형 AI 에이전트

    \b
    사용법:
        claude-flow              # 현재 디렉토리에서 실행
        claude-flow /path/to/project  # 특정 디렉토리에서 실행

    \b
    키보드 단축키:
        Ctrl+N    새 세션
        Ctrl+O    세션 불러오기
        Ctrl+I    프로젝트 정보
        Ctrl+L    화면 지우기
        Ctrl+C    중단/취소/종료
        Ctrl+Q    종료

    \b
    환경변수:
        CLAUDE_CODE_OAUTH_TOKEN    Claude Code OAuth 토큰 (필수)
    """

    if version:
        from . import __version__
        click.echo(f"Claude Flow TUI v{__version__}")
        return

    # 프로젝트 경로 결정
    if project_path is None:
        project_path = Path.cwd()

    # 프로젝트 경로 검증
    if not project_path.exists():
        click.echo(f"❌ 경로를 찾을 수 없습니다: {project_path}", err=True)
        sys.exit(1)

    if not project_path.is_dir():
        click.echo(f"❌ 디렉토리가 아닙니다: {project_path}", err=True)
        sys.exit(1)

    # 환경변수 로드 (.env 파일)
    env_file = project_path / ".env"
    if env_file.exists():
        load_dotenv(env_file)
    else:
        # 전역 .env 시도
        load_dotenv()

    # 환경변수 확인
    if not os.getenv("CLAUDE_CODE_OAUTH_TOKEN"):
        click.echo(
            "❌ CLAUDE_CODE_OAUTH_TOKEN 환경변수가 설정되지 않았습니다.\n"
            "\n"
            "Claude Code에서 OAuth 토큰을 발급받아 설정해주세요:\n"
            "  export CLAUDE_CODE_OAUTH_TOKEN='your-token-here'\n"
            "\n"
            "또는 .env 파일에 추가하세요.",
            err=True,
        )
        sys.exit(1)

    # TUI 앱 실행
    try:
        app = ClaudeFlowApp(project_path=project_path)
        app.run()
    except KeyboardInterrupt:
        click.echo("\n\n👋 Claude Flow를 종료합니다.")
    except Exception as e:
        click.echo(f"\n❌ 오류 발생: {e}", err=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

