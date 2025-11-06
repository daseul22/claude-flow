"""프로젝트 유틸리티"""

import subprocess
from pathlib import Path
from typing import Optional, Dict, Any


def get_project_name(project_path: Path) -> str:
    """프로젝트명 감지 (Git 저장소명 또는 디렉토리명)"""
    try:
        # Git 저장소명 시도
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=project_path,
            capture_output=True,
            text=True,
            timeout=5,
        )

        if result.returncode == 0:
            repo_path = Path(result.stdout.strip())
            return repo_path.name
    except Exception:
        pass

    # Git 실패시 디렉토리명 사용
    return project_path.name


def get_git_info(project_path: Path) -> Optional[Dict[str, str]]:
    """Git 저장소 정보"""
    try:
        # 현재 브랜치
        branch_result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=project_path,
            capture_output=True,
            text=True,
            timeout=5,
        )

        if branch_result.returncode != 0:
            return None

        branch = branch_result.stdout.strip()

        # 저장소 URL (origin)
        url_result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=project_path,
            capture_output=True,
            text=True,
            timeout=5,
        )

        url = url_result.stdout.strip() if url_result.returncode == 0 else None

        return {
            "branch": branch,
            "remote_url": url,
        }
    except Exception:
        return None


def load_claude_md(project_path: Path) -> Optional[str]:
    """CLAUDE.md 파일 로드"""
    claude_md_file = project_path / "CLAUDE.md"

    if not claude_md_file.exists():
        return None

    try:
        with open(claude_md_file, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        print(f"CLAUDE.md 로드 실패: {e}")
        return None


def get_project_info(project_path: Path) -> Dict[str, Any]:
    """프로젝트 전체 정보"""
    project_name = get_project_name(project_path)
    git_info = get_git_info(project_path)
    claude_md_content = load_claude_md(project_path)

    return {
        "name": project_name,
        "path": str(project_path.absolute()),
        "git": git_info,
        "claude_md_loaded": claude_md_content is not None,
        "claude_md_content": claude_md_content,
    }

