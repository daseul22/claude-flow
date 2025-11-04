"""
웹 API 라우터

FastAPI 라우터를 정의합니다.
"""

from src.presentation.web.routers.agents import router as agents_router
from src.presentation.web.routers.health import router as health_router
from src.presentation.web.routers.workflows import router as workflows_router
from src.presentation.web.routers.projects import router as projects_router
from src.presentation.web.routers.filesystem import router as filesystem_router
from src.presentation.web.routers.templates import router as templates_router
from src.presentation.web.routers.custom_workers import router as custom_workers_router

__all__ = [
    "agents_router",
    "health_router",
    "workflows_router",
    "projects_router",
    "filesystem_router",
    "templates_router",
    "custom_workers_router",
]
