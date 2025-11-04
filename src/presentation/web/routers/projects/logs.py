"""
로그 파일 관리 API

프로젝트의 로그 파일 조회 및 삭제 엔드포인트를 제공합니다.
"""

import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

from fastapi import APIRouter, HTTPException
from src.infrastructure.logging import get_logger
from src.presentation.web.schemas.workflow import (
    LogFileInfo,
    LogListResponse,
    LogContentResponse,
)
from src.presentation.web.config import ProjectConfig as Config
from . import dependencies

logger = get_logger(__name__)
router = APIRouter()


@router.delete("/logs")
async def clear_logs() -> Dict[str, Any]:
    """
    현재 프로젝트의 로그 파일 비우기

    ~/.claude-flow/{project-name}/logs/ 디렉토리의 로그 파일을 모두 삭제합니다.
    """
    if not dependencies._current_project_path:
        raise HTTPException(status_code=400, detail="프로젝트가 선택되지 않았습니다.")

    project_dir = Path(dependencies._current_project_path)
    project_name = project_dir.name
    home_dir = Path.home()

    log_dirs = [home_dir / ".claude-flow" / project_name / "logs"]

    total_size = 0
    total_file_count = 0
    deleted_dirs = []

    try:
        for logs_dir in log_dirs:
            if not logs_dir.exists():
                logger.debug(f"로그 디렉토리가 존재하지 않습니다: {logs_dir}")
                continue

            dir_size = 0
            dir_file_count = 0

            for file_path in logs_dir.rglob("*"):
                if file_path.is_file():
                    dir_size += file_path.stat().st_size
                    dir_file_count += 1

            shutil.rmtree(logs_dir)
            logs_dir.mkdir(parents=True, exist_ok=True)

            total_size += dir_size
            total_file_count += dir_file_count
            deleted_dirs.append(str(logs_dir))

            logger.info(
                f"로그 파일 삭제: {logs_dir} "
                f"(파일: {dir_file_count}개, 용량: {dir_size / (1024 * 1024):.2f} MB)"
            )

        freed_space_mb = total_size / (1024 * 1024)

        if total_file_count == 0:
            return {"message": "삭제할 로그 파일이 없습니다", "deleted_files": 0, "freed_space_mb": 0.0}

        logger.info(
            f"로그 파일 삭제 완료 (총 {len(deleted_dirs)}개 위치): "
            f"{', '.join(deleted_dirs)} "
            f"(파일: {total_file_count}개, 용량: {freed_space_mb:.2f} MB)"
        )

        return {
            "message": "로그 파일이 삭제되었습니다",
            "deleted_files": total_file_count,
            "freed_space_mb": round(freed_space_mb, 2),
        }

    except Exception as e:
        logger.error(f"로그 파일 삭제 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"로그 파일 삭제 실패: {str(e)}")


@router.get("/logs/list", response_model=LogListResponse)
async def list_logs() -> LogListResponse:
    """
    로그 파일 목록 조회

    현재 프로젝트의 로그 디렉토리 (~/.claude-flow/{project_name}/logs/)에서
    모든 로그 파일을 검색하여 반환합니다.
    """
    if not dependencies._current_project_path:
        raise HTTPException(status_code=400, detail="프로젝트가 선택되지 않았습니다.")

    try:
        project_dir = Path(dependencies._current_project_path)
        project_name = project_dir.name
        logs_dir = Path.home() / ".claude-flow" / project_name / "logs"

        if not logs_dir.exists():
            return LogListResponse(logs=[], total_count=0, total_size=0)

        logs = []
        total_size = 0

        for log_file in logs_dir.rglob("*.log"):
            if not log_file.is_file():
                continue

            stat = log_file.stat()
            relative_path = log_file.relative_to(logs_dir)

            file_type = Config.LOG_TYPES.get(log_file.name, "unknown")

            logs.append(
                LogFileInfo(
                    path=str(relative_path),
                    name=log_file.name,
                    size=stat.st_size,
                    modified=datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    type=file_type,
                )
            )

            total_size += stat.st_size

        logs.sort(key=lambda x: x.modified, reverse=True)

        return LogListResponse(logs=logs, total_count=len(logs), total_size=total_size)

    except Exception as e:
        logger.error(f"로그 파일 목록 조회 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"로그 파일 목록 조회 실패: {str(e)}")


@router.get("/logs/content", response_model=LogContentResponse)
async def get_log_content(file_path: str, max_lines: int = 1000) -> LogContentResponse:
    """
    로그 파일 내용 조회

    Args:
        file_path: 로그 파일 상대 경로 (logs/ 기준, 예: "system.log", "session-123/debug.log")
        max_lines: 최대 라인 수 (기본: 1000, 최대: 10000)
    """
    if not dependencies._current_project_path:
        raise HTTPException(status_code=400, detail="프로젝트가 선택되지 않았습니다.")

    max_lines = min(max_lines, Config.MAX_LOG_LINES)

    try:
        project_dir = Path(dependencies._current_project_path)
        project_name = project_dir.name
        logs_dir = Path.home() / ".claude-flow" / project_name / "logs"

        log_file_path = (logs_dir / file_path).resolve()
        if not str(log_file_path).startswith(str(logs_dir)):
            raise HTTPException(status_code=400, detail="잘못된 파일 경로입니다.")

        if not log_file_path.exists():
            raise HTTPException(status_code=404, detail=f"로그 파일을 찾을 수 없습니다: {file_path}")

        stat = log_file_path.stat()
        file_type = Config.LOG_TYPES.get(log_file_path.name, "unknown")

        file_info = LogFileInfo(
            path=file_path,
            name=log_file_path.name,
            size=stat.st_size,
            modified=datetime.fromtimestamp(stat.st_mtime).isoformat(),
            type=file_type,
        )

        with open(log_file_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
            content = "".join(lines[-max_lines:])

        return LogContentResponse(content=content, file_info=file_info)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"로그 파일 내용 조회 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"로그 파일 내용 조회 실패: {str(e)}")
