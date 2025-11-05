"""
환경 검증 유틸리티

validate_environment: 환경변수 검증
get_claude_cli_path: Claude CLI 경로 반환
"""

import os
import logging
import platform
from pathlib import Path
from typing import Optional

# Optional dotenv support
try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv():
        """Fallback when python-dotenv is not installed"""
        pass

logger = logging.getLogger(__name__)


def validate_environment() -> None:
    """
    환경 변수 검증 (CLAUDE_CODE_OAUTH_TOKEN)

    .env 파일이 있으면 자동으로 로드합니다.
    우선순위: 1. 현재 작업 디렉토리 2. 프로젝트 루트

    OAuth 토큰 기반 인증만 사용합니다 (Claude 구독 사용자).

    Raises:
        ValueError: OAuth 토큰이 설정되지 않은 경우
    """
    # .env 파일 로드 (우선순위: 작업 디렉토리 → 프로젝트 루트)
    cwd_dotenv = Path.cwd() / ".env"
    if cwd_dotenv.exists():
        load_dotenv(dotenv_path=cwd_dotenv)
        logger.debug(f"Loaded .env from current directory: {cwd_dotenv}")
    else:
        project_root = get_project_root()
        project_dotenv = project_root / ".env"
        if project_dotenv.exists():
            load_dotenv(dotenv_path=project_dotenv)
            logger.debug(f"Loaded .env from project root: {project_dotenv}")
        else:
            logger.debug("No .env file found")

    oauth_token = os.getenv("CLAUDE_CODE_OAUTH_TOKEN")

    if not oauth_token:
        project_root = get_project_root()
        project_dotenv = project_root / ".env"
        project_env_example = project_root / ".env.example"

        error_msg = "CLAUDE_CODE_OAUTH_TOKEN이 설정되지 않았습니다.\n\n"
        error_msg += "다음 방법 중 하나로 설정하세요:\n\n"

        # 방법 1: 환경변수
        error_msg += "1. 환경변수로 직접 설정:\n"
        error_msg += "   export CLAUDE_CODE_OAUTH_TOKEN='your-oauth-token'\n\n"

        # 방법 2: .env 파일 (현재 디렉토리)
        error_msg += "2. 현재 디렉토리에 .env 파일 생성:\n"
        error_msg += f"   현재 디렉토리: {Path.cwd()}\n"
        error_msg += "   echo \"CLAUDE_CODE_OAUTH_TOKEN='your-token'\" > .env\n\n"

        # 방법 3: .env 파일 (프로젝트 루트)
        error_msg += "3. 프로젝트 루트에 .env 파일 생성:\n"
        error_msg += f"   프로젝트 루트: {project_root}\n"

        if project_env_example.exists():
            error_msg += f"   .env.example 파일을 복사:\n"
            error_msg += f"   cp {project_env_example} {project_dotenv}\n\n"
        else:
            error_msg += f"   cd {project_root}\n"
            error_msg += "   echo \"CLAUDE_CODE_OAUTH_TOKEN='your-token'\" > .env\n\n"

        # 방법 4: pipx 설치 시 BETTER_LLM_ROOT 설정
        if "site-packages" in str(Path(__file__)):
            # pipx 설치 감지
            error_msg += "4. [pipx 설치 사용자] 소스 코드 위치 지정:\n"
            error_msg += "   # better-llm 소스 코드를 클론한 위치로 설정\n"
            error_msg += "   export BETTER_LLM_ROOT='/path/to/better-llm'\n"
            error_msg += "   # 예: export BETTER_LLM_ROOT='/Users/daniel/dallem-repo/better-llm'\n"

        raise ValueError(error_msg)


def get_claude_cli_path() -> str:
    """
    Claude CLI 실행 파일 경로를 반환합니다.

    우선순위:
    1. 환경변수 CLAUDE_CLI_PATH (명시적 오버라이드)
    2. 자동 탐지 (~/.claude/local/claude)

    Returns:
        Claude CLI 실행 파일 경로

    Raises:
        FileNotFoundError: CLI를 찾을 수 없을 경우
    """
    # .env 파일 로드 (우선순위: 작업 디렉토리 → 프로젝트 루트)
    cwd_dotenv = Path.cwd() / ".env"
    if cwd_dotenv.exists():
        load_dotenv(dotenv_path=cwd_dotenv)
    else:
        project_root = get_project_root()
        project_dotenv = project_root / ".env"
        if project_dotenv.exists():
            load_dotenv(dotenv_path=project_dotenv)

    # 1. 환경변수 확인
    env_path = os.getenv("CLAUDE_CLI_PATH")
    if env_path:
        cli_path = Path(env_path).expanduser()
        if cli_path.exists():
            return str(cli_path)
        else:
            logger.warning(f"환경변수 CLAUDE_CLI_PATH가 유효하지 않습니다: {env_path}")

    # 2. 자동 탐지
    home_dir = Path.home()
    system = platform.system()

    if system == "Windows":
        default_path = home_dir / ".claude" / "local" / "claude.exe"
    else:  # macOS, Linux
        default_path = home_dir / ".claude" / "local" / "claude"

    if default_path.exists():
        return str(default_path)

    # 찾을 수 없음
    raise FileNotFoundError(
        f"Claude CLI를 찾을 수 없습니다.\n"
        f"다음 중 하나의 방법으로 설정하세요:\n\n"
        f"방법 1 - 환경변수 설정:\n"
        f"  export CLAUDE_CLI_PATH='/path/to/claude'\n\n"
        f"방법 2 - 기본 경로에 설치:\n"
        f"  {default_path}\n\n"
        f"Claude CLI 설치 방법: https://docs.anthropic.com/en/docs/claude-code"
    )


def get_project_root() -> Path:
    """
    프로젝트 루트 디렉토리 반환

    우선순위:
    1. 환경변수 BETTER_LLM_ROOT
    2. 현재 작업 디렉토리에 config/ 존재 시
    3. __file__ 기반 경로 (개발 모드)

    Returns:
        프로젝트 루트 디렉토리 (절대 경로)
    """
    import os

    # 1. 환경변수 확인
    env_root = os.getenv("BETTER_LLM_ROOT")
    if env_root:
        root = Path(env_root).resolve()
        if (root / "config").exists():
            return root

    # 2. 현재 작업 디렉토리 확인
    cwd = Path.cwd()
    if (cwd / "config").exists():
        return cwd

    # 3. __file__ 기반 경로 (개발 모드)
    # better-llm/src/infrastructure/config/validator.py -> better-llm
    file_based_root = Path(__file__).parent.parent.parent.parent.resolve()
    if (file_based_root / "config").exists():
        return file_based_root

    # 4. 찾지 못한 경우 현재 작업 디렉토리 반환 (경고 로그)
    logger = logging.getLogger(__name__)
    logger.warning(
        f"프로젝트 루트를 찾을 수 없습니다. 현재 작업 디렉토리를 사용합니다: {cwd}\n"
        f"환경변수 BETTER_LLM_ROOT를 설정하거나, better-llm 프로젝트 디렉토리에서 실행하세요."
    )
    return cwd


def get_project_name() -> str:
    """
    프로젝트 이름 감지

    우선순위:
    1. Git remote URL에서 프로젝트 이름 추출
    2. Git root directory 이름
    3. 현재 작업 디렉토리 이름

    Returns:
        프로젝트 이름 (디렉토리명)

    Example:
        >>> get_project_name()
        'better-llm'

    Notes:
        - Git URL 파싱 지원 형식:
          * HTTPS: https://github.com/user/repo.git
          * SSH: git@github.com:user/repo.git
          * SSH with port: ssh://git@github.com:22/user/repo.git
          * With query params: https://github.com/user/repo.git?ref=main
    """
    import subprocess
    import re

    try:
        # 1. Git remote URL에서 프로젝트 이름 추출 시도
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False
        )

        if result.returncode == 0:
            remote_url = result.stdout.strip()
            if remote_url:
                # Query params 제거 (예: ?ref=main)
                remote_url = remote_url.split("?")[0]
                # Fragment 제거 (예: #branch)
                remote_url = remote_url.split("#")[0]
                # .git 확장자 제거
                if remote_url.endswith(".git"):
                    remote_url = remote_url[:-4]

                # URL에서 프로젝트 이름 추출
                # SSH URL with port: ssh://git@github.com:22/user/repo -> repo
                # SSH URL: git@github.com:user/repo -> repo
                # HTTPS URL: https://github.com/user/repo -> repo

                # SSH with port 형식 처리
                if remote_url.startswith("ssh://"):
                    # ssh://git@github.com:22/user/repo
                    match = re.search(r"ssh://[^/]+/(.+)", remote_url)
                    if match:
                        path = match.group(1)
                        project_name = path.split("/")[-1]
                        if project_name:
                            return project_name

                # 일반 SSH 형식 (git@github.com:user/repo)
                if "@" in remote_url and ":" in remote_url:
                    # git@github.com:user/repo -> user/repo
                    parts = remote_url.split(":")
                    if len(parts) >= 2:
                        project_name = parts[-1].split("/")[-1]
                        if project_name:
                            return project_name

                # HTTPS 형식 또는 기타 형식
                project_name = remote_url.split("/")[-1]
                if project_name:
                    return project_name
        else:
            # Git 명령 실패 시 debug 레벨로 기록
            logger.debug(
                f"Git remote command failed (code {result.returncode}): "
                f"{result.stderr.strip()}"
            )
    except subprocess.TimeoutExpired:
        logger.debug("Git remote command timed out")
    except FileNotFoundError:
        logger.debug("Git command not found")
    except Exception as e:
        logger.debug(f"Unexpected error while getting git remote: {e}")

    try:
        # 2. Git root 디렉토리 확인 시도
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False
        )

        if result.returncode == 0:
            git_root = Path(result.stdout.strip())
            return git_root.name
        else:
            logger.debug(
                f"Git rev-parse command failed (code {result.returncode}): "
                f"{result.stderr.strip()}"
            )
    except subprocess.TimeoutExpired:
        logger.debug("Git rev-parse command timed out")
    except FileNotFoundError:
        logger.debug("Git command not found")
    except Exception as e:
        logger.debug(f"Unexpected error while getting git root: {e}")

    # 3. Git 저장소가 아니면 현재 작업 디렉토리 이름 사용
    return Path.cwd().name


def get_data_dir(subdir: Optional[str] = None, project_path: Optional[str] = None) -> Path:
    """
    데이터 디렉토리 경로 반환 (~/.claude-flow/{project-name}/)

    프로젝트별 세션, 로그 등을 저장하는 디렉토리를 반환합니다.
    디렉토리가 없으면 자동으로 생성합니다.

    Args:
        subdir: 하위 디렉토리 이름 (예: "sessions", "logs")
        project_path: 프로젝트 디렉토리 경로 (None이면 자동 감지 시도)

    Returns:
        데이터 디렉토리 경로 (절대 경로)

    Raises:
        OSError: 디렉토리 생성에 실패한 경우

    Example:
        >>> get_data_dir()
        Path('/Users/daniel/.claude-flow/claude-flow')
        >>> get_data_dir("sessions", "/path/to/my-project")
        Path('/Users/daniel/.claude-flow/my-project/sessions')

    Notes:
        - project_path가 제공되면 해당 프로젝트 이름 사용
        - project_path가 None이면 get_project_name()으로 자동 감지
        - 디렉토리가 없으면 자동으로 생성됩니다 (parents=True, exist_ok=True).
        - 멀티 프로젝트 환경에서도 각 프로젝트의 데이터가 격리됩니다.
    """
    home_dir = Path.home()

    if project_path:
        # 명시적으로 전달된 프로젝트 경로 사용
        project_name = Path(project_path).name
    else:
        # 자동 감지 시도
        project_name = get_project_name()

    if subdir:
        data_path = home_dir / ".claude-flow" / project_name / subdir
    else:
        data_path = home_dir / ".claude-flow" / project_name

    # 디렉토리 생성 (없으면)
    try:
        data_path.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Data directory ensured: {data_path}")
    except OSError as e:
        current_dir = Path.cwd()
        error_msg = (
            f"Failed to create data directory: {data_path}\n"
            f"Current working directory: {current_dir}\n"
            f"Project name: {project_name}\n"
            f"Error: {e}"
        )
        logger.error(error_msg)
        raise OSError(error_msg) from e

    return data_path
