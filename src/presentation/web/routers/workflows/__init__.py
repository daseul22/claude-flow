"""
워크플로우 라우터 통합 모듈

workflows 패키지의 모든 하위 라우터를 통합하여 단일 APIRouter로 제공합니다.
"""

from fastapi import APIRouter

from . import core, execution, design

# 통합 라우터 생성
router = APIRouter(prefix="/api/workflows", tags=["workflows"])

# 하위 라우터 포함
router.include_router(core.router)
router.include_router(execution.router)
router.include_router(design.router)

# 외부에서 import 가능하도록 export
__all__ = ["router"]
