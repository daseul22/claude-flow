"""
워크플로우 라우터 공통 의존성

워크플로우 관련 라우터에서 사용하는 공통 의존성을 제공합니다.

의존성 주입 패턴:
    - lru_cache: 싱글톤 패턴 (ConfigLoader 등)
    - 프로젝트별 캐싱: WorkflowExecutor는 프로젝트별로 인스턴스 유지
    - Depends(): FastAPI 의존성 주입

Example:
    @router.post("/execute")
    async def execute_workflow(
        executor: WorkflowExecutor = Depends(get_workflow_executor)
    ):
        ...
"""

from functools import lru_cache
from pathlib import Path

from fastapi import Depends

from src.infrastructure.config import JsonConfigLoader, get_project_root
from src.infrastructure.logging import get_logger
from src.presentation.web.config import ProjectConfig
from src.presentation.web.services.workflow_executor import WorkflowExecutor
from src.presentation.web.services.background_workflow_manager import (
    get_background_workflow_manager,
    BackgroundWorkflowManager,
)

logger = get_logger(__name__)

# 워크플로우 저장 디렉토리
WORKFLOWS_DIR: Path = ProjectConfig.WORKFLOWS_DIR
WORKFLOWS_DIR.mkdir(parents=True, exist_ok=True)

# 프로젝트별 WorkflowExecutor 캐시
_executors: dict[str, WorkflowExecutor] = {}


def clear_executor_cache(project_path: str | None = None) -> None:
    """
    WorkflowExecutor 캐시 무효화

    커스텀 워커 저장/삭제 후 호출하여 최신 상태를 반영합니다.

    Args:
        project_path: 특정 프로젝트의 캐시만 무효화 (None이면 전체 무효화)
    """
    if project_path is None:
        # 전체 캐시 무효화
        _executors.clear()
        logger.info("전체 WorkflowExecutor 캐시 무효화")
    else:
        # 특정 프로젝트 캐시만 무효화
        cache_key = project_path or "~default"
        if cache_key in _executors:
            del _executors[cache_key]
            logger.info(f"WorkflowExecutor 캐시 무효화: {cache_key}")


@lru_cache()
def get_config_loader() -> JsonConfigLoader:
    """
    JsonConfigLoader 싱글톤 인스턴스 반환 (FastAPI Depends + lru_cache)

    Returns:
        JsonConfigLoader: 스레드 안전한 싱글톤 인스턴스
    """
    project_root = get_project_root()
    return JsonConfigLoader(project_root)


def get_workflow_executor(
    config_loader: JsonConfigLoader = Depends(get_config_loader),
) -> WorkflowExecutor:
    """
    WorkflowExecutor 인스턴스 반환 (프로젝트별 캐싱)

    Args:
        config_loader: ConfigLoader 의존성 주입

    Returns:
        WorkflowExecutor: 워크플로우 실행 엔진
    """
    # projects 라우터에서 현재 프로젝트 경로 가져오기 (모듈 참조로 변경)
    from src.presentation.web.routers.projects import dependencies as projects_deps
    _current_project_path = projects_deps._current_project_path

    # 캐시 키 생성
    cache_key = _current_project_path or "~default"

    # 캐시에서 인스턴스 확인
    if cache_key not in _executors:
        logger.info(f"새 WorkflowExecutor 생성 (프로젝트: {cache_key})")
        _executors[cache_key] = WorkflowExecutor(config_loader, _current_project_path)

    return _executors[cache_key]


def get_background_manager(
    executor: WorkflowExecutor = Depends(get_workflow_executor),
) -> BackgroundWorkflowManager:
    """
    BackgroundWorkflowManager 인스턴스 반환 (프로젝트별 캐싱)

    Args:
        executor: WorkflowExecutor 의존성 주입

    Returns:
        BackgroundWorkflowManager: 백그라운드 워크플로우 관리자
    """
    # projects 라우터에서 현재 프로젝트 경로 가져오기 (모듈 참조로 변경)
    from src.presentation.web.routers.projects import dependencies as projects_deps
    _current_project_path = projects_deps._current_project_path

    return get_background_workflow_manager(executor, project_path=_current_project_path)
