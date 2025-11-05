"""
보고서 파일 관리 API

프로젝트의 보고서 파일 조회 및 삭제 엔드포인트를 제공합니다.
"""

import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

from fastapi import APIRouter, HTTPException
from src.infrastructure.logging import get_logger
from src.presentation.web.schemas.workflow import (
    ReportFileInfo,
    ReportListResponse,
    ReportContentResponse,
)
from . import dependencies

logger = get_logger(__name__)
router = APIRouter()


@router.delete("/reports")
async def clear_reports() -> Dict[str, Any]:
    """
    현재 프로젝트의 보고서 파일 비우기

    ~/.claude-flow/{project-name}/reports/ 디렉토리의 보고서 파일을 모두 삭제합니다.
    """
    if not dependencies._current_project_path:
        raise HTTPException(status_code=400, detail="프로젝트가 선택되지 않았습니다.")

    project_dir = Path(dependencies._current_project_path)
    project_name = project_dir.name
    home_dir = Path.home()

    reports_dir = home_dir / ".claude-flow" / project_name / "reports"

    if not reports_dir.exists():
        logger.info(f"보고서 디렉토리가 존재하지 않습니다: {reports_dir}")
        return {"message": "삭제할 보고서 파일이 없습니다", "deleted_files": 0, "freed_space_mb": 0.0}

    try:
        total_size = 0
        file_count = 0

        for file_path in reports_dir.rglob("*"):
            if file_path.is_file():
                total_size += file_path.stat().st_size
                file_count += 1

        shutil.rmtree(reports_dir)
        reports_dir.mkdir(parents=True, exist_ok=True)

        freed_space_mb = total_size / (1024 * 1024)

        logger.info(
            f"보고서 파일 삭제 완료: {reports_dir} "
            f"(파일: {file_count}개, 용량: {freed_space_mb:.2f} MB)"
        )

        return {
            "message": "보고서 파일이 삭제되었습니다",
            "deleted_files": file_count,
            "freed_space_mb": round(freed_space_mb, 2),
        }

    except Exception as e:
        logger.error(f"보고서 파일 삭제 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"보고서 파일 삭제 실패: {str(e)}")


@router.get("/reports/list", response_model=ReportListResponse)
async def list_reports() -> ReportListResponse:
    """
    보고서 파일 목록 조회

    현재 프로젝트의 보고서 디렉토리 (~/.claude-flow/{project_name}/reports/)에서
    모든 보고서 파일을 검색하여 반환합니다.
    """
    if not dependencies._current_project_path:
        raise HTTPException(status_code=400, detail="프로젝트가 선택되지 않았습니다.")

    try:
        project_dir = Path(dependencies._current_project_path)
        project_name = project_dir.name
        reports_dir = Path.home() / ".claude-flow" / project_name / "reports"

        if not reports_dir.exists():
            return ReportListResponse(reports=[], total_count=0, total_size=0)

        reports = []
        total_size = 0

        # 보고서 파일 검색 (모든 확장자)
        for report_file in reports_dir.rglob("*"):
            if not report_file.is_file():
                continue

            stat = report_file.stat()
            relative_path = report_file.relative_to(reports_dir)

            # 파일명에서 노드 ID 추출 (예: "planner_report.md" -> "planner")
            node_id = report_file.stem.split("_")[0] if "_" in report_file.stem else report_file.stem
            extension = report_file.suffix.lstrip(".")

            reports.append(
                ReportFileInfo(
                    path=str(relative_path),
                    name=report_file.name,
                    size=stat.st_size,
                    modified=datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    node_id=node_id,
                    extension=extension,
                )
            )

            total_size += stat.st_size

        # 수정 시간 역순 정렬
        reports.sort(key=lambda x: x.modified, reverse=True)

        return ReportListResponse(reports=reports, total_count=len(reports), total_size=total_size)

    except Exception as e:
        logger.error(f"보고서 파일 목록 조회 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"보고서 파일 목록 조회 실패: {str(e)}")


@router.get("/reports/content", response_model=ReportContentResponse)
async def get_report_content(file_path: str) -> ReportContentResponse:
    """
    보고서 파일 내용 조회

    Args:
        file_path: 보고서 파일 상대 경로 (reports/ 기준, 예: "planner_report.md", "coder/output.txt")
    """
    if not dependencies._current_project_path:
        raise HTTPException(status_code=400, detail="프로젝트가 선택되지 않았습니다.")

    try:
        project_dir = Path(dependencies._current_project_path)
        project_name = project_dir.name
        reports_dir = Path.home() / ".claude-flow" / project_name / "reports"

        report_file_path = (reports_dir / file_path).resolve()

        # Path Traversal 방어
        if not str(report_file_path).startswith(str(reports_dir)):
            raise HTTPException(status_code=400, detail="잘못된 파일 경로입니다.")

        if not report_file_path.exists():
            raise HTTPException(
                status_code=404, detail=f"보고서 파일을 찾을 수 없습니다: {file_path}"
            )

        stat = report_file_path.stat()

        # 파일명에서 노드 ID 추출
        node_id = (
            report_file_path.stem.split("_")[0]
            if "_" in report_file_path.stem
            else report_file_path.stem
        )
        extension = report_file_path.suffix.lstrip(".")

        file_info = ReportFileInfo(
            path=file_path,
            name=report_file_path.name,
            size=stat.st_size,
            modified=datetime.fromtimestamp(stat.st_mtime).isoformat(),
            node_id=node_id,
            extension=extension,
        )

        # 파일 내용 읽기
        with open(report_file_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        return ReportContentResponse(content=content, file_info=file_info)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"보고서 파일 내용 조회 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"보고서 파일 내용 조회 실패: {str(e)}")
