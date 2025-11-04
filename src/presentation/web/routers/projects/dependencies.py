"""
프로젝트 라우터 공통 의존성

프로젝트 관련 라우터에서 사용하는 공통 헬퍼 함수를 제공합니다.
"""

import shutil
from pathlib import Path
from typing import Optional

from fastapi import HTTPException

from src.infrastructure.logging import get_logger

logger = get_logger(__name__)

# 현재 선택된 프로젝트 경로 (서버 메모리에 저장)
_current_project_path: Optional[str] = None


def get_config_path(project_path: str) -> Path:
    """
    프로젝트 설정 파일 경로 반환 (레거시, 하위 호환용)

    Args:
        project_path: 프로젝트 디렉토리 경로

    Returns:
        Path: .claude-flow/workflow-config.json 경로
    """
    project_dir = Path(project_path)
    config_dir = project_dir / ".claude-flow"
    return config_dir / "workflow-config.json"


def get_workflows_dir(project_path: str) -> Path:
    """
    워크플로우 디렉토리 경로 반환

    Args:
        project_path: 프로젝트 디렉토리 경로

    Returns:
        Path: .claude-flow/workflows/ 경로
    """
    project_dir = Path(project_path)
    config_dir = project_dir / ".claude-flow"
    return config_dir / "workflows"


def get_workflow_path(project_path: str, workflow_name: str) -> Path:
    """
    특정 워크플로우 파일 경로 반환

    Args:
        project_path: 프로젝트 디렉토리 경로
        workflow_name: 워크플로우 이름

    Returns:
        Path: .claude-flow/workflows/{workflow_name}.json 경로
    """
    workflows_dir = get_workflows_dir(project_path)
    return workflows_dir / f"{workflow_name}.json"


def migrate_legacy_config(project_path: str) -> bool:
    """
    레거시 workflow-config.json을 workflows/default.json로 마이그레이션

    Args:
        project_path: 프로젝트 디렉토리 경로

    Returns:
        bool: 마이그레이션 수행 여부
    """
    legacy_config_path = get_config_path(project_path)

    if not legacy_config_path.exists():
        return False

    # workflows 디렉토리 생성
    workflows_dir = get_workflows_dir(project_path)
    workflows_dir.mkdir(parents=True, exist_ok=True)

    # default.json으로 복사
    default_workflow_path = get_workflow_path(project_path, "default")

    try:
        shutil.copy2(legacy_config_path, default_workflow_path)
        logger.info(f"레거시 설정 파일 마이그레이션: {legacy_config_path} → {default_workflow_path}")

        # 레거시 파일은 백업 후 삭제
        backup_path = legacy_config_path.with_suffix(".json.bak")
        shutil.move(str(legacy_config_path), str(backup_path))
        logger.info(f"레거시 설정 파일 백업: {backup_path}")

        return True
    except Exception as e:
        logger.error(f"레거시 설정 마이그레이션 실패: {e}", exc_info=True)
        return False


def get_display_config_path(project_path: str) -> Path:
    """
    Display 설정 파일 경로 반환

    Args:
        project_path: 프로젝트 디렉토리 경로

    Returns:
        Path: .claude-flow/display-config.json 경로
    """
    project_dir = Path(project_path)
    config_dir = project_dir / ".claude-flow"
    return config_dir / "display-config.json"


def validate_project_path(project_path: str) -> Path:
    """
    프로젝트 경로 검증

    Args:
        project_path: 프로젝트 디렉토리 경로

    Returns:
        Path: 검증된 경로 객체

    Raises:
        HTTPException: 경로가 유효하지 않은 경우
    """
    path = Path(project_path).resolve()

    if not path.exists():
        raise HTTPException(status_code=400, detail=f"프로젝트 디렉토리가 존재하지 않습니다: {project_path}")

    if not path.is_dir():
        raise HTTPException(status_code=400, detail=f"디렉토리가 아닙니다: {project_path}")

    return path
