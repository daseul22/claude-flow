"""
Projects 라우터 패키지

프로젝트 관리, 로그, 세션 관련 엔드포인트를 통합합니다.
"""

from fastapi import APIRouter

from . import core, logs, sessions
from .dependencies import _current_project_path

# 메인 라우터 생성
router = APIRouter(prefix="/api/projects", tags=["projects"])

# 서브 라우터 통합
router.include_router(core.router)
router.include_router(logs.router)
router.include_router(sessions.router)

# 외부에서 import 가능하도록 export
__all__ = ["router", "_current_project_path"]
