"""
파일 시스템 브라우저 API 라우터

디렉토리 탐색을 위한 엔드포인트를 제공합니다.
"""

import os
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/filesystem", tags=["filesystem"])


class DirectoryEntry(BaseModel):
    """
    디렉토리 엔트리 (파일 또는 디렉토리)

    Attributes:
        name: 파일/디렉토리 이름
        path: 절대 경로
        is_directory: 디렉토리 여부
        is_readable: 읽기 권한 여부
    """

    name: str = Field(..., description="파일/디렉토리 이름")
    path: str = Field(..., description="절대 경로")
    is_directory: bool = Field(..., description="디렉토리 여부")
    is_readable: bool = Field(default=True, description="읽기 권한 여부")


class DirectoryBrowseResponse(BaseModel):
    """
    디렉토리 브라우징 응답

    Attributes:
        current_path: 현재 경로
        parent_path: 부모 경로 (없으면 None)
        entries: 디렉토리 엔트리 목록 (디렉토리 먼저, 이름순 정렬)
    """

    current_path: str = Field(..., description="현재 경로")
    parent_path: Optional[str] = Field(default=None, description="부모 경로")
    entries: List[DirectoryEntry] = Field(..., description="디렉토리 엔트리 목록")


# 무시할 디렉토리/파일 패턴
IGNORE_PATTERNS = {
    ".git",
    ".svn",
    ".hg",  # 버전 관리
    "node_modules",
    "venv",
    ".venv",
    "__pycache__",  # 의존성
    ".DS_Store",
    "Thumbs.db",  # 시스템 파일
    ".Trash",
    ".Spotlight-V100",
    ".fseventsd",  # macOS 시스템
}


def is_hidden_or_ignored(name: str) -> bool:
    """
    숨김 파일 또는 무시할 파일인지 확인

    Args:
        name: 파일/디렉토리 이름

    Returns:
        bool: 숨김/무시 여부
    """
    # 숨김 파일 (점으로 시작)
    if name.startswith(".") and name not in {".", ".."}:
        # .claude-flow은 허용
        if name == ".claude-flow":
            return False
        return True

    # 무시 패턴
    if name in IGNORE_PATTERNS:
        return True

    return False


def is_safe_path(base_path: Path, requested_path: Path) -> bool:
    """
    경로 탐색 공격 방지 (Path Traversal)

    BUG-002 FIX: High priority security fix

    요청 경로가 기본 경로(홈 디렉토리) 하위인지 확인합니다.
    ../../../../../etc 같은 공격으로부터 보호합니다.

    Args:
        base_path: 허용된 기본 경로 (예: 홈 디렉토리)
        requested_path: 사용자가 요청한 경로

    Returns:
        bool: 안전한 경로 여부
    """
    try:
        # 경로 정규화 (심볼릭 링크 해석)
        resolved_base = base_path.resolve()
        resolved_requested = requested_path.resolve()

        # 요청 경로가 기본 경로 하위인지 확인
        # Python 3.9+: is_relative_to 사용
        try:
            # is_relative_to()는 boolean을 반환 (예외를 발생시키지 않음)
            return resolved_requested.is_relative_to(resolved_base)
        except AttributeError:
            # Python 3.8 이하 호환성
            try:
                resolved_requested.relative_to(resolved_base)
                return True
            except ValueError:
                return False
    except (ValueError, RuntimeError):
        logger.warning(f"경로 검증 실패: {requested_path}")
        return False


@router.get("/home")
async def get_home_directory() -> dict[str, str]:
    """
    사용자 홈 디렉토리 경로 반환

    Returns:
        Dict[str, str]: 홈 디렉토리 경로

    Example:
        GET /api/filesystem/home

        Response: {
            "home_path": "/Users/username"
        }
    """
    home_path = str(Path.home())
    logger.info(f"홈 디렉토리 조회: {home_path}")
    return {"home_path": home_path}


@router.get("/browse", response_model=DirectoryBrowseResponse)
async def browse_directory(
    path: Optional[str] = Query(None, description="탐색할 디렉토리 경로 (미제공 시 홈 디렉토리)")
) -> DirectoryBrowseResponse:
    """
    디렉토리 브라우징

    Args:
        path: 탐색할 디렉토리 경로 (옵션)

    Returns:
        DirectoryBrowseResponse: 디렉토리 엔트리 목록

    Example:
        GET /api/filesystem/browse?path=/Users/username/projects

        Response: {
            "current_path": "/Users/username/projects",
            "parent_path": "/Users/username",
            "entries": [
                {
                    "name": "my-project",
                    "path": "/Users/username/projects/my-project",
                    "is_directory": true,
                    "is_readable": true
                },
                ...
            ]
        }
    """
    # 경로 결정 (미제공 시 홈 디렉토리)
    if path is None:
        target_path = Path.home()
    else:
        target_path = Path(path).resolve()

        # BUG-002 FIX: Path Traversal 방어
        # 사용자가 홈 디렉토리 밖의 경로에 접근하려는 시도를 차단
        if not is_safe_path(Path.home(), target_path):
            logger.warning(f"Path Traversal 시도 감지: {target_path}")
            raise HTTPException(status_code=403, detail="접근 권한이 없는 경로입니다")

    # 경로 존재 확인
    if not target_path.exists():
        raise HTTPException(status_code=404, detail=f"디렉토리를 찾을 수 없습니다: {target_path}")

    # 디렉토리 확인
    if not target_path.is_dir():
        raise HTTPException(status_code=400, detail=f"디렉토리가 아닙니다: {target_path}")

    # 읽기 권한 확인
    if not os.access(target_path, os.R_OK):
        raise HTTPException(status_code=403, detail=f"읽기 권한이 없습니다: {target_path}")

    # 부모 경로 계산
    parent_path = str(target_path.parent) if target_path.parent != target_path else None

    # 디렉토리 엔트리 수집
    entries: List[DirectoryEntry] = []

    try:
        for entry in target_path.iterdir():
            # 숨김/무시 파일 건너뛰기
            if is_hidden_or_ignored(entry.name):
                continue

            # 권한 확인
            is_readable = os.access(entry, os.R_OK)

            entries.append(
                DirectoryEntry(
                    name=entry.name,
                    path=str(entry.resolve()),
                    is_directory=entry.is_dir(),
                    is_readable=is_readable,
                )
            )

    except PermissionError as e:
        logger.warning(f"디렉토리 읽기 실패: {target_path} - {e}")
        raise HTTPException(status_code=403, detail=f"디렉토리 읽기 권한이 없습니다: {target_path}")
    except Exception as e:
        logger.error(f"디렉토리 탐색 실패: {target_path} - {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"디렉토리 탐색 실패: {str(e)}")

    # 정렬: 디렉토리 먼저, 이름순
    entries.sort(key=lambda e: (not e.is_directory, e.name.lower()))

    logger.info(f"디렉토리 브라우징: {target_path} " f"(엔트리: {len(entries)}개)")

    return DirectoryBrowseResponse(
        current_path=str(target_path),
        parent_path=parent_path,
        entries=entries,
    )
