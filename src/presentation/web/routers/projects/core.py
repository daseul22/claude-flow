"""
프로젝트 CRUD 및 워크플로우 관리 API

프로젝트 선택, 워크플로우 저장/로드를 위한 엔드포인트를 제공합니다.
(간소화 버전 - 핵심 기능만 포함)
"""

import json
import shutil
from datetime import datetime
from typing import Dict, Any, Optional

from fastapi import APIRouter, HTTPException
from src.infrastructure.logging import get_logger
from src.presentation.web.schemas.workflow import (
    ProjectSelectRequest,
    ProjectSelectResponse,
    ProjectWorkflowSaveRequest,
    ProjectWorkflowLoadResponse,
    ProjectConfig,
    DisplayConfig,
    DisplayConfigLoadResponse,
    DisplayConfigSaveRequest,
)
from src.presentation.web.config import ProjectConfig as Config, ErrorMessages
from . import dependencies
from .dependencies import (
    get_config_path,
    get_workflows_dir,
    get_workflow_path,
    migrate_legacy_config,
    get_display_config_path,
    validate_project_path,
)

logger = get_logger(__name__)
router = APIRouter()


@router.post("/select", response_model=ProjectSelectResponse)
async def select_project(request: ProjectSelectRequest) -> ProjectSelectResponse:
    """프로젝트 디렉토리 선택"""
    # 경로 검증
    project_path = validate_project_path(request.project_path)
    dependencies._current_project_path = str(project_path)

    # 기존 설정 확인
    config_path = get_config_path(str(project_path))
    has_existing = config_path.exists()

    logger.info(f"프로젝트 선택: {project_path} " f"(기존 설정: {'있음' if has_existing else '없음'})")

    return ProjectSelectResponse(
        project_path=str(project_path),
        message="프로젝트가 선택되었습니다",
        has_existing_config=has_existing,
    )


@router.get("/current")
async def get_current_project() -> Dict[str, Any]:
    """현재 선택된 프로젝트 정보 조회"""
    if not dependencies._current_project_path:
        return {
            "project_path": None,
            "has_existing_config": False,
        }

    config_path = get_config_path(dependencies._current_project_path)
    has_existing = config_path.exists()

    return {
        "project_path": dependencies._current_project_path,
        "has_existing_config": has_existing,
    }


@router.get("/workflows/list")
async def list_workflows() -> Dict[str, Any]:
    """워크플로우 목록 조회"""
    if not dependencies._current_project_path:
        raise HTTPException(status_code=400, detail="프로젝트가 선택되지 않았습니다")

    workflows_dir = get_workflows_dir(dependencies._current_project_path)

    if not workflows_dir.exists():
        return {"workflows": []}

    workflow_files = list(workflows_dir.glob("*.json"))
    workflows = []

    for workflow_file in workflow_files:
        try:
            # 파일 정보 가져오기
            stat = workflow_file.stat()
            file_size = stat.st_size
            modified_time = datetime.fromtimestamp(stat.st_mtime).isoformat()

            with open(workflow_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                workflow_data = data.get("workflow", {})
                workflows.append(
                    {
                        "name": workflow_file.stem,
                        "display_name": workflow_data.get("name", workflow_file.stem),
                        "description": workflow_data.get("description", ""),
                        "last_modified": modified_time,
                        "size": file_size,
                    }
                )
        except Exception as e:
            logger.warning(f"워크플로우 로드 실패: {workflow_file} - {e}")

    return {"workflows": workflows}


@router.get("/display-config", response_model=DisplayConfigLoadResponse)
async def load_display_config() -> DisplayConfigLoadResponse:
    """Display 설정 로드"""
    if not dependencies._current_project_path:
        raise HTTPException(status_code=400, detail="프로젝트가 선택되지 않았습니다")

    config_path = get_display_config_path(dependencies._current_project_path)

    if not config_path.exists():
        return DisplayConfigLoadResponse(
            has_config=False,
            config=DisplayConfig(layout_config={}, canvas_state={}),
        )

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return DisplayConfigLoadResponse(
            has_config=True,
            config=DisplayConfig(**data),
        )
    except Exception as e:
        logger.error(f"Display 설정 로드 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"설정 로드 실패: {str(e)}")


@router.post("/display-config")
async def save_display_config(request: DisplayConfigSaveRequest) -> Dict[str, str]:
    """Display 설정 저장"""
    if not dependencies._current_project_path:
        raise HTTPException(status_code=400, detail="프로젝트가 선택되지 않았습니다")

    config_path = get_display_config_path(dependencies._current_project_path)
    config_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(request.config.model_dump(), f, ensure_ascii=False, indent=2)

        logger.info(f"Display 설정 저장: {config_path}")
        return {"message": "Display 설정이 저장되었습니다"}
    except Exception as e:
        logger.error(f"Display 설정 저장 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"설정 저장 실패: {str(e)}")


# ============================================================================
# 워크플로우 저장/로드 API (레거시)
# ============================================================================


@router.post("/workflow")
async def save_project_workflow(request: ProjectWorkflowSaveRequest) -> Dict[str, str]:
    """프로젝트에 워크플로우 저장 (레거시 엔드포인트)"""
    project_path = request.project_path or dependencies._current_project_path

    if not project_path or project_path.strip() == "":
        raise HTTPException(
            status_code=400,
            detail="프로젝트가 선택되지 않았습니다. 먼저 프로젝트를 선택하세요.",
        )

    validate_project_path(project_path)

    config_path = get_config_path(project_path)
    config_path.parent.mkdir(parents=True, exist_ok=True)

    project_config = ProjectConfig(
        project_path=project_path,
        workflow=request.workflow,
        metadata={"last_modified": datetime.now().isoformat(), "version": "1.0"},
    )

    try:
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(
                project_config.model_dump(mode="json", exclude_none=False),
                f,
                ensure_ascii=False,
                indent=2,
            )
        logger.info(f"워크플로우 저장: {request.workflow.name} → {config_path}")
        return {"message": "워크플로우가 저장되었습니다", "config_path": str(config_path)}
    except Exception as e:
        logger.error(f"워크플로우 저장 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"워크플로우 저장 실패: {str(e)}")


@router.get("/workflow", response_model=ProjectWorkflowLoadResponse)
async def load_project_workflow(
    project_path: Optional[str] = None,
) -> ProjectWorkflowLoadResponse:
    """프로젝트에서 워크플로우 로드 (레거시 엔드포인트)"""
    target_path = project_path or dependencies._current_project_path

    if not target_path:
        raise HTTPException(status_code=400, detail="프로젝트가 선택되지 않았습니다.")

    validate_project_path(target_path)
    config_path = get_config_path(target_path)

    if not config_path.exists():
        raise HTTPException(status_code=404, detail=f"워크플로우 설정 파일을 찾을 수 없습니다: {config_path}")

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config_data = json.load(f)

        project_config = ProjectConfig(**config_data)
        logger.info(f"워크플로우 로드: {project_config.workflow.name} ← {config_path}")

        return ProjectWorkflowLoadResponse(
            project_path=target_path,
            workflow=project_config.workflow,
            last_modified=project_config.metadata.get("last_modified"),
        )
    except Exception as e:
        logger.error(f"워크플로우 로드 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"워크플로우 로드 실패: {str(e)}")


# ============================================================================
# 워크플로우 관리 API (다중 워크플로우 지원)
# ============================================================================


@router.get("/workflows/{workflow_name}", response_model=ProjectWorkflowLoadResponse)
async def load_workflow_by_name(workflow_name: str) -> ProjectWorkflowLoadResponse:
    """특정 워크플로우 로드"""
    if not dependencies._current_project_path:
        raise HTTPException(status_code=400, detail="프로젝트가 선택되지 않았습니다.")

    migrate_legacy_config(dependencies._current_project_path)
    workflow_path = get_workflow_path(dependencies._current_project_path, workflow_name)

    if not workflow_path.exists():
        raise HTTPException(status_code=404, detail=f"워크플로우를 찾을 수 없습니다: {workflow_name}")

    try:
        with open(workflow_path, "r", encoding="utf-8") as f:
            config_data = json.load(f)

        project_config = ProjectConfig(**config_data)
        logger.info(f"워크플로우 로드: {workflow_name} ← {workflow_path}")

        return ProjectWorkflowLoadResponse(
            project_path=dependencies._current_project_path,
            workflow=project_config.workflow,
            last_modified=project_config.metadata.get("last_modified"),
        )
    except Exception as e:
        logger.error(f"워크플로우 로드 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"워크플로우 로드 실패: {str(e)}")


@router.post("/workflows/{workflow_name}")
async def save_workflow_by_name(
    workflow_name: str, request: ProjectWorkflowSaveRequest
) -> Dict[str, str]:
    """워크플로우 저장 (이름 지정)"""
    if not dependencies._current_project_path:
        raise HTTPException(status_code=400, detail="프로젝트가 선택되지 않았습니다.")

    if not workflow_name or not workflow_name.strip():
        raise HTTPException(status_code=400, detail="워크플로우 이름이 비어있습니다.")

    if any(char in workflow_name for char in Config.INVALID_FILENAME_CHARS):
        raise HTTPException(
            status_code=400,
            detail=ErrorMessages.INVALID_FILENAME.format(
                chars=", ".join(Config.INVALID_FILENAME_CHARS)
            ),
        )

    workflows_dir = get_workflows_dir(dependencies._current_project_path)
    workflows_dir.mkdir(parents=True, exist_ok=True)

    workflow_path = get_workflow_path(dependencies._current_project_path, workflow_name)

    project_config = ProjectConfig(
        project_path=dependencies._current_project_path,
        workflow=request.workflow,
        metadata={"last_modified": datetime.now().isoformat(), "version": "1.0"},
    )

    try:
        with open(workflow_path, "w", encoding="utf-8") as f:
            json.dump(
                project_config.model_dump(mode="json", exclude_none=False),
                f,
                ensure_ascii=False,
                indent=2,
            )

        logger.info(f"워크플로우 저장: {workflow_name} → {workflow_path}")
        return {
            "message": "워크플로우가 저장되었습니다",
            "workflow_name": workflow_name,
            "config_path": str(workflow_path),
        }
    except Exception as e:
        logger.error(f"워크플로우 저장 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"워크플로우 저장 실패: {str(e)}")


@router.delete("/workflows/{workflow_name}")
async def delete_workflow_by_name(workflow_name: str) -> Dict[str, str]:
    """워크플로우 삭제"""
    if not dependencies._current_project_path:
        raise HTTPException(status_code=400, detail="프로젝트가 선택되지 않았습니다.")

    workflow_path = get_workflow_path(dependencies._current_project_path, workflow_name)

    if not workflow_path.exists():
        raise HTTPException(status_code=404, detail=f"워크플로우를 찾을 수 없습니다: {workflow_name}")

    try:
        workflow_path.unlink()
        logger.info(f"워크플로우 삭제: {workflow_name} ({workflow_path})")
        return {"message": "워크플로우가 삭제되었습니다", "workflow_name": workflow_name}
    except Exception as e:
        logger.error(f"워크플로우 삭제 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"워크플로우 삭제 실패: {str(e)}")


@router.put("/workflows/{old_name}/rename")
async def rename_workflow(old_name: str, new_name: str) -> Dict[str, str]:
    """워크플로우 이름 변경"""
    if not dependencies._current_project_path:
        raise HTTPException(status_code=400, detail="프로젝트가 선택되지 않았습니다.")

    if not new_name or not new_name.strip():
        raise HTTPException(status_code=400, detail="새 워크플로우 이름이 비어있습니다.")

    if any(char in new_name for char in Config.INVALID_FILENAME_CHARS):
        raise HTTPException(
            status_code=400,
            detail=ErrorMessages.INVALID_FILENAME.format(
                chars=", ".join(Config.INVALID_FILENAME_CHARS)
            ),
        )

    old_path = get_workflow_path(dependencies._current_project_path, old_name)
    new_path = get_workflow_path(dependencies._current_project_path, new_name)

    if not old_path.exists():
        raise HTTPException(status_code=404, detail=f"워크플로우를 찾을 수 없습니다: {old_name}")

    if new_path.exists():
        raise HTTPException(status_code=400, detail=f"이미 존재하는 워크플로우 이름입니다: {new_name}")

    try:
        shutil.move(str(old_path), str(new_path))
        logger.info(f"워크플로우 이름 변경: {old_name} → {new_name}")
        return {"message": "워크플로우 이름이 변경되었습니다", "old_name": old_name, "new_name": new_name}
    except Exception as e:
        logger.error(f"워크플로우 이름 변경 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"워크플로우 이름 변경 실패: {str(e)}")
