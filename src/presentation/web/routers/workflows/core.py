"""
워크플로우 CRUD API

워크플로우 저장, 조회, 삭제, 검증을 위한 엔드포인트를 제공합니다.
"""

import json
import uuid
from typing import Dict

from fastapi import APIRouter, HTTPException, Depends

from src.infrastructure.config import JsonConfigLoader
from src.infrastructure.logging import get_logger
from src.presentation.web.schemas.workflow import (
    Workflow,
    WorkflowSaveRequest,
    WorkflowSaveResponse,
    WorkflowListResponse,
    WorkflowValidateResponse,
    WorkflowValidationError,
)
from src.presentation.web.services.workflow_validator import WorkflowValidator
from .dependencies import WORKFLOWS_DIR, get_config_loader

logger = get_logger(__name__)
router = APIRouter()


@router.post("", response_model=WorkflowSaveResponse)
async def save_workflow(request: WorkflowSaveRequest) -> WorkflowSaveResponse:
    """
    워크플로우 저장

    Args:
        request: 워크플로우 저장 요청

    Returns:
        WorkflowSaveResponse: 저장된 워크플로우 ID

    Example:
        POST /api/workflows
        Body: {
            "workflow": {
                "name": "코드 리뷰 워크플로우",
                "description": "코드 작성 → 리뷰 → 커밋",
                "nodes": [...],
                "edges": [...]
            }
        }

        Response: {
            "workflow_id": "uuid-v4",
            "message": "워크플로우가 저장되었습니다"
        }
    """
    try:
        workflow = request.workflow

        # 워크플로우 ID 생성 (미제공 시)
        workflow_id = workflow.id or str(uuid.uuid4())
        workflow.id = workflow_id

        # 파일로 저장
        workflow_path = WORKFLOWS_DIR / f"{workflow_id}.json"
        with open(workflow_path, "w", encoding="utf-8") as f:
            json.dump(workflow.model_dump(), f, ensure_ascii=False, indent=2)

        logger.info(f"워크플로우 저장: {workflow.name} (ID: {workflow_id})")

        return WorkflowSaveResponse(workflow_id=workflow_id, message="워크플로우가 저장되었습니다")

    except Exception as e:
        logger.error(f"워크플로우 저장 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"워크플로우 저장 실패: {str(e)}")


@router.get("", response_model=WorkflowListResponse)
async def list_workflows() -> WorkflowListResponse:
    """
    워크플로우 목록 조회

    Returns:
        WorkflowListResponse: 워크플로우 목록 (메타데이터만)

    Example:
        GET /api/workflows
        Response: {
            "workflows": [
                {
                    "id": "uuid-v4",
                    "name": "코드 리뷰 워크플로우",
                    "description": "코드 작성 → 리뷰 → 커밋",
                    "node_count": 3,
                    "edge_count": 2
                },
                ...
            ]
        }
    """
    try:
        workflows = []

        for workflow_path in WORKFLOWS_DIR.glob("*.json"):
            try:
                with open(workflow_path, "r", encoding="utf-8") as f:
                    workflow_data = json.load(f)

                # 메타데이터만 추출
                workflows.append(
                    {
                        "id": workflow_data.get("id"),
                        "name": workflow_data.get("name"),
                        "description": workflow_data.get("description"),
                        "node_count": len(workflow_data.get("nodes", [])),
                        "edge_count": len(workflow_data.get("edges", [])),
                    }
                )

            except Exception as e:
                logger.warning(f"워크플로우 로드 실패: {workflow_path} - {e}")
                continue

        logger.info(f"워크플로우 목록 조회: {len(workflows)}개")

        return WorkflowListResponse(workflows=workflows)

    except Exception as e:
        logger.error(f"워크플로우 목록 조회 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"워크플로우 목록 조회 실패: {str(e)}")


@router.get("/{workflow_id}", response_model=Workflow)
async def get_workflow(workflow_id: str) -> Workflow:
    """
    워크플로우 조회 (단일)

    Args:
        workflow_id: 워크플로우 ID

    Returns:
        Workflow: 워크플로우 전체 데이터

    Example:
        GET /api/workflows/{workflow_id}
        Response: {
            "id": "uuid-v4",
            "name": "코드 리뷰 워크플로우",
            "description": "...",
            "nodes": [...],
            "edges": [...]
        }
    """
    try:
        workflow_path = WORKFLOWS_DIR / f"{workflow_id}.json"

        if not workflow_path.exists():
            raise HTTPException(status_code=404, detail=f"워크플로우를 찾을 수 없습니다: {workflow_id}")

        with open(workflow_path, "r", encoding="utf-8") as f:
            workflow_data = json.load(f)

        logger.info(f"워크플로우 조회: {workflow_data.get('name')} (ID: {workflow_id})")

        return Workflow(**workflow_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"워크플로우 조회 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"워크플로우 조회 실패: {str(e)}")


@router.delete("/{workflow_id}")
async def delete_workflow(workflow_id: str) -> Dict[str, str]:
    """
    워크플로우 삭제

    Args:
        workflow_id: 워크플로우 ID

    Returns:
        Dict[str, str]: 응답 메시지

    Example:
        DELETE /api/workflows/{workflow_id}
        Response: {
            "message": "워크플로우가 삭제되었습니다"
        }
    """
    try:
        workflow_path = WORKFLOWS_DIR / f"{workflow_id}.json"

        if not workflow_path.exists():
            raise HTTPException(status_code=404, detail=f"워크플로우를 찾을 수 없습니다: {workflow_id}")

        workflow_path.unlink()

        logger.info(f"워크플로우 삭제: {workflow_id}")

        return {"message": "워크플로우가 삭제되었습니다"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"워크플로우 삭제 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"워크플로우 삭제 실패: {str(e)}")


@router.post("/validate", response_model=WorkflowValidateResponse)
async def validate_workflow(
    workflow: Workflow,
    config_loader: JsonConfigLoader = Depends(get_config_loader),
):
    """
    워크플로우 검증

    실행 전 워크플로우의 유효성을 검사합니다:
    - 순환 참조 검사
    - 고아 노드 검사
    - 템플릿 변수 유효성 검사
    - Worker별 도구 권한 검사
    - Input 노드 존재 여부 검사
    - Manager 노드 검증

    Args:
        workflow: 검증할 워크플로우
        config_loader: ConfigLoader 의존성 주입

    Returns:
        WorkflowValidateResponse: 검증 결과
            - valid: 검증 통과 여부 (error가 없으면 True)
            - errors: 검증 에러 목록 (severity, node_id, message, suggestion)

    Example:
        POST /api/workflows/validate
        {
            "name": "test",
            "nodes": [...],
            "edges": [...]
        }

        Response:
        {
            "valid": false,
            "errors": [
                {
                    "severity": "error",
                    "node_id": "node1",
                    "message": "순환 참조가 감지되었습니다",
                    "suggestion": "노드 간 연결을 확인하여 순환 참조를 제거하세요"
                }
            ]
        }
    """
    try:
        # WorkflowValidator 생성 (config_loader 전달하여 Worker 도구 목록 동적 로드)
        validator = WorkflowValidator(config_loader=config_loader)

        # 워크플로우 검증
        validation_errors = validator.validate(workflow)

        # ValidationError → WorkflowValidationError 변환
        errors = [
            WorkflowValidationError(
                severity=error.severity,
                node_id=error.node_id,
                message=error.message,
                suggestion=error.suggestion,
            )
            for error in validation_errors
        ]

        # error severity가 있으면 invalid
        has_errors = any(e.severity == "error" for e in errors)

        return WorkflowValidateResponse(
            valid=not has_errors,
            errors=errors,
        )

    except Exception as e:
        logger.error(f"워크플로우 검증 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"워크플로우 검증 실패: {str(e)}")
