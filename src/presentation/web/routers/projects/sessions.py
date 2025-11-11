"""
세션 파일 관리 API

프로젝트의 워크플로우 세션 파일 조회 및 삭제 엔드포인트를 제공합니다.
"""

import json
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List

from fastapi import APIRouter, HTTPException, Query
from src.infrastructure.logging import get_logger
from src.presentation.web.schemas.workflow import (
    SessionFileInfo,
    SessionListResponse,
    SessionContentResponse,
    SessionStats,
    SessionStatsResponse,
)
from . import dependencies

logger = get_logger(__name__)
router = APIRouter()


@router.delete("/sessions")
async def clear_sessions() -> Dict[str, Any]:
    """
    현재 프로젝트의 웹 워크플로우 세션 데이터 비우기

    ~/.claude-flow/{project_name}/web-sessions/ 디렉토리의 모든 세션 파일을 삭제합니다.
    """
    if not dependencies._current_project_path:
        raise HTTPException(status_code=400, detail="프로젝트가 선택되지 않았습니다.")

    project_dir = Path(dependencies._current_project_path)
    project_name = project_dir.name
    web_sessions_dir = Path.home() / ".claude-flow" / project_name / "web-sessions"

    if not web_sessions_dir.exists():
        logger.info(f"웹 세션 디렉토리가 존재하지 않습니다: {web_sessions_dir}")
        return {"message": "삭제할 세션 데이터가 없습니다", "deleted_files": 0, "freed_space_mb": 0.0}

    try:
        total_size = 0
        file_count = 0

        for file_path in web_sessions_dir.rglob("*"):
            if file_path.is_file():
                total_size += file_path.stat().st_size
                file_count += 1

        shutil.rmtree(web_sessions_dir)
        web_sessions_dir.mkdir(parents=True, exist_ok=True)

        freed_space_mb = total_size / (1024 * 1024)

        logger.info(
            f"웹 세션 데이터 삭제 완료: {web_sessions_dir} "
            f"(파일: {file_count}개, 용량: {freed_space_mb:.2f} MB)"
        )

        return {
            "message": "세션 데이터가 삭제되었습니다",
            "deleted_files": file_count,
            "freed_space_mb": round(freed_space_mb, 2),
        }

    except Exception as e:
        logger.error(f"웹 세션 데이터 삭제 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"세션 데이터 삭제 실패: {str(e)}")


@router.get("/sessions/list", response_model=SessionListResponse)
async def list_sessions() -> SessionListResponse:
    """
    세션 파일 목록 조회

    현재 프로젝트의 웹 세션 디렉토리 (~/.claude-flow/{project_name}/web-sessions/)에서
    모든 세션 파일을 검색하여 반환합니다.
    """
    if not dependencies._current_project_path:
        raise HTTPException(status_code=400, detail="프로젝트가 선택되지 않았습니다.")

    try:
        project_dir = Path(dependencies._current_project_path)
        project_name = project_dir.name
        sessions_dir = Path.home() / ".claude-flow" / project_name / "web-sessions"

        if not sessions_dir.exists():
            return SessionListResponse(sessions=[], total_count=0, total_size=0)

        sessions = []
        total_size = 0

        for session_file in sessions_dir.glob("*.json"):
            if not session_file.is_file():
                continue

            stat = session_file.stat()
            session_id = session_file.stem

            status = "unknown"
            try:
                with open(session_file, "r", encoding="utf-8") as f:
                    session_data = json.load(f)
                    status = session_data.get("status", "unknown")
            except Exception:
                pass

            sessions.append(
                SessionFileInfo(
                    session_id=session_id,
                    path=str(session_file),
                    size=stat.st_size,
                    created=datetime.fromtimestamp(stat.st_ctime).isoformat(),
                    modified=datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    status=status,
                )
            )

            total_size += stat.st_size

        sessions.sort(key=lambda x: x.modified, reverse=True)

        return SessionListResponse(
            sessions=sessions, total_count=len(sessions), total_size=total_size
        )

    except Exception as e:
        logger.error(f"세션 파일 목록 조회 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"세션 파일 목록 조회 실패: {str(e)}")


@router.get("/sessions/content", response_model=SessionContentResponse)
async def get_session_content(session_id: str) -> SessionContentResponse:
    """
    세션 파일 내용 조회

    Args:
        session_id: 세션 ID (예: "wf-1234567890")
    """
    if not dependencies._current_project_path:
        raise HTTPException(status_code=400, detail="프로젝트가 선택되지 않았습니다.")

    try:
        project_dir = Path(dependencies._current_project_path)
        project_name = project_dir.name
        sessions_dir = Path.home() / ".claude-flow" / project_name / "web-sessions"

        session_file_path = sessions_dir / f"{session_id}.json"

        if not session_file_path.exists():
            raise HTTPException(status_code=404, detail=f"세션 파일을 찾을 수 없습니다: {session_id}")

        stat = session_file_path.stat()

        with open(session_file_path, "r", encoding="utf-8") as f:
            session_data = json.load(f)

        status = session_data.get("status", "unknown")

        file_info = SessionFileInfo(
            session_id=session_id,
            path=str(session_file_path),
            size=stat.st_size,
            created=datetime.fromtimestamp(stat.st_ctime).isoformat(),
            modified=datetime.fromtimestamp(stat.st_mtime).isoformat(),
            status=status,
        )

        return SessionContentResponse(content=session_data, file_info=file_info)

    except HTTPException:
        raise
    except json.JSONDecodeError as e:
        logger.error(f"세션 JSON 파싱 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"세션 파일 형식이 잘못되었습니다: {str(e)}")
    except Exception as e:
        logger.error(f"세션 파일 내용 조회 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"세션 파일 내용 조회 실패: {str(e)}")


# ============================================================================
# 세션 통계 API (컨텍스트 윈도우 추적)
# ============================================================================


@router.get("/sessions/stats", response_model=List[SessionStatsResponse])
async def get_all_session_stats() -> List[SessionStatsResponse]:
    """
    모든 세션 통계 조회

    Returns:
        List[SessionStatsResponse]: 모든 세션 통계 목록
    """
    try:
        from . import dependencies

        executor = dependencies.get_workflow_executor()
        if not executor:
            raise HTTPException(status_code=500, detail="워크플로우 실행기를 초기화할 수 없습니다")

        all_stats = executor.get_all_session_stats()

        # SessionStats 객체로 변환
        stats_list = []
        for stats_dict in all_stats:
            # 모델별 컨텍스트 한계 설정
            model = stats_dict.get("model", "claude-sonnet-4-5-20250929")
            context_limits = {
                "claude-sonnet-4-5-20250929": 200000,
                "claude-opus-4-5-20250514": 200000,
                "claude-haiku-4-5-20251001": 200000,
                "default": 200000,
            }
            limit = context_limits.get(model, context_limits["default"])

            stats_obj = SessionStats(**stats_dict)
            stats_list.append(SessionStatsResponse(stats=stats_obj, model_context_limit=limit))

        logger.info(f"세션 통계 조회 완료: {len(stats_list)}개 세션")
        return stats_list

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"세션 통계 조회 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"세션 통계 조회 실패: {str(e)}")


@router.get("/sessions/{session_id}/stats", response_model=SessionStatsResponse)
async def get_session_stats(session_id: str) -> SessionStatsResponse:
    """
    특정 세션의 통계 조회

    Args:
        session_id: SDK 세션 ID

    Returns:
        SessionStatsResponse: 세션 통계 정보
    """
    try:
        from . import dependencies

        executor = dependencies.get_workflow_executor()
        if not executor:
            raise HTTPException(status_code=500, detail="워크플로우 실행기를 초기화할 수 없습니다")

        stats_dict = executor.get_session_stats(session_id)

        if not stats_dict:
            raise HTTPException(status_code=404, detail=f"세션 {session_id}의 통계를 찾을 수 없습니다")

        # 모델별 컨텍스트 한계 설정
        model = stats_dict.get("model", "claude-sonnet-4-5-20250929")
        context_limits = {
            "claude-sonnet-4-5-20250929": 200000,
            "claude-opus-4-5-20250514": 200000,
            "claude-haiku-4-5-20251001": 200000,
            "default": 200000,
        }
        limit = context_limits.get(model, context_limits["default"])

        stats_obj = SessionStats(**stats_dict)
        logger.info(f"세션 통계 조회 완료: {session_id[:8]}...")
        return SessionStatsResponse(stats=stats_obj, model_context_limit=limit)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"세션 통계 조회 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"세션 통계 조회 실패: {str(e)}")
