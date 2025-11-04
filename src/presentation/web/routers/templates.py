"""
워크플로우 템플릿 API 라우터

템플릿 조회, 저장, 삭제를 위한 엔드포인트를 제공합니다.
"""

from typing import Dict, Any
from functools import lru_cache

from fastapi import APIRouter, HTTPException, Depends

from src.infrastructure.logging import get_logger
from src.presentation.web.schemas.template import (
    Template,
    TemplateListResponse,
    TemplateSaveRequest,
    TemplateSaveResponse,
)
from src.presentation.web.services.template_manager import TemplateManager

logger = get_logger(__name__)
router = APIRouter(prefix="/api/templates", tags=["templates"])


@lru_cache()
def get_template_manager() -> TemplateManager:
    """
    TemplateManager 싱글톤 인스턴스 반환 (FastAPI Depends + lru_cache)

    Returns:
        TemplateManager: 스레드 안전한 싱글톤 인스턴스
    """
    return TemplateManager()


@router.get("", response_model=TemplateListResponse)
async def list_templates(manager: TemplateManager = Depends(get_template_manager)):
    """
    템플릿 목록 조회 (메타데이터만)

    내장 템플릿과 사용자 템플릿을 모두 반환합니다.

    Args:
        manager: TemplateManager 의존성 주입

    Returns:
        TemplateListResponse: 템플릿 메타데이터 목록

    Example:
        GET /api/templates

    Response:
        {
            "templates": [
                {
                    "id": "code_review",
                    "name": "코드 리뷰 워크플로우",
                    "description": "계획 수립 → 코드 작성 → 코드 리뷰",
                    "category": "code_review",
                    "node_count": 4,
                    "edge_count": 3,
                    "tags": ["code-review", "planner", "coder", "reviewer"],
                    "is_builtin": true,
                    "created_at": "2025-10-28T00:00:00Z",
                    "updated_at": "2025-10-28T00:00:00Z"
                },
                ...
            ]
        }
    """
    try:
        templates = manager.list_templates()
        logger.info(f"템플릿 목록 조회 성공: {len(templates)}개")
        return TemplateListResponse(templates=templates)
    except Exception as e:
        logger.error(f"템플릿 목록 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"템플릿 목록 조회 실패: {str(e)}")


@router.get("/{template_id}", response_model=Template)
async def get_template(template_id: str, manager: TemplateManager = Depends(get_template_manager)):
    """
    템플릿 상세 조회 (전체 데이터)

    Args:
        template_id: 템플릿 ID
        manager: TemplateManager 의존성 주입

    Returns:
        Template: 템플릿 객체 (워크플로우 포함)

    Raises:
        HTTPException: 템플릿을 찾을 수 없는 경우 (404)

    Example:
        GET /api/templates/code_review

    Response:
        {
            "id": "code_review",
            "name": "코드 리뷰 워크플로우",
            "description": "계획 수립 → 코드 작성 → 코드 리뷰",
            "category": "code_review",
            "workflow": {
                "id": "code_review_workflow",
                "name": "코드 리뷰 워크플로우",
                "nodes": [...],
                "edges": [...]
            },
            "tags": ["code-review", "planner", "coder", "reviewer"],
            "is_builtin": true,
            "created_at": "2025-10-28T00:00:00Z",
            "updated_at": "2025-10-28T00:00:00Z"
        }
    """
    try:
        template = manager.get_template(template_id)
        if template is None:
            logger.warning(f"템플릿을 찾을 수 없습니다: {template_id}")
            raise HTTPException(status_code=404, detail=f"템플릿을 찾을 수 없습니다: {template_id}")

        logger.info(f"템플릿 조회 성공: {template_id}")
        return template
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"템플릿 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"템플릿 조회 실패: {str(e)}")


@router.post("", response_model=TemplateSaveResponse)
async def save_template(
    request: TemplateSaveRequest, manager: TemplateManager = Depends(get_template_manager)
):
    """
    사용자 정의 템플릿 저장

    Args:
        request: 템플릿 저장 요청
        manager: TemplateManager 의존성 주입

    Returns:
        TemplateSaveResponse: 저장된 템플릿 ID 및 메시지

    Raises:
        HTTPException: 템플릿 검증 실패 또는 저장 실패 (400, 500)

    Example:
        POST /api/templates
        Body: {
            "name": "내 워크플로우",
            "description": "사용자 정의 워크플로우",
            "category": "custom",
            "workflow": {
                "name": "내 워크플로우",
                "nodes": [...],
                "edges": [...]
            },
            "tags": ["custom"]
        }

    Response:
        {
            "template_id": "abc123",
            "message": "템플릿 저장 완료"
        }
    """
    try:
        # 템플릿 검증
        workflow_dict = request.workflow.dict()
        errors = manager.validate_template(workflow_dict)
        if errors:
            logger.warning(f"템플릿 검증 실패: {errors}")
            raise HTTPException(status_code=400, detail=f"템플릿 검증 실패: {', '.join(errors)}")

        # 템플릿 저장
        template_id = manager.save_template(
            name=request.name,
            description=request.description,
            category=request.category,
            workflow=workflow_dict,
            tags=request.tags,
        )

        logger.info(f"템플릿 저장 성공: {template_id} ({request.name})")
        return TemplateSaveResponse(template_id=template_id, message="템플릿 저장 완료")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"템플릿 저장 실패: {e}")
        raise HTTPException(status_code=500, detail=f"템플릿 저장 실패: {str(e)}")


@router.delete("/{template_id}")
async def delete_template(
    template_id: str, manager: TemplateManager = Depends(get_template_manager)
):
    """
    템플릿 삭제 (내장 템플릿은 삭제 불가)

    Args:
        template_id: 템플릿 ID
        manager: TemplateManager 의존성 주입

    Returns:
        dict: 삭제 결과 메시지

    Raises:
        HTTPException: 내장 템플릿 삭제 시도 또는 템플릿 미존재 (400, 404)

    Example:
        DELETE /api/templates/abc123

    Response:
        {
            "message": "템플릿 삭제 완료",
            "template_id": "abc123"
        }
    """
    try:
        success = manager.delete_template(template_id)
        if not success:
            logger.warning(f"템플릿을 찾을 수 없습니다: {template_id}")
            raise HTTPException(status_code=404, detail=f"템플릿을 찾을 수 없습니다: {template_id}")

        logger.info(f"템플릿 삭제 성공: {template_id}")
        return {"message": "템플릿 삭제 완료", "template_id": template_id}
    except HTTPException:
        raise
    except ValueError as e:
        # 내장 템플릿 삭제 시도
        logger.warning(f"템플릿 삭제 실패: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"템플릿 삭제 실패: {e}")
        raise HTTPException(status_code=500, detail=f"템플릿 삭제 실패: {str(e)}")


@router.post("/validate")
async def validate_template(
    workflow: Dict[str, Any], manager: TemplateManager = Depends(get_template_manager)
):
    """
    템플릿 검증 (워크플로우 유효성 검사)

    Args:
        workflow: 워크플로우 데이터
        manager: TemplateManager 의존성 주입

    Returns:
        dict: 검증 결과

    Example:
        POST /api/templates/validate
        Body: {
            "nodes": [...],
            "edges": [...]
        }

    Response:
        {
            "valid": true,
            "errors": []
        }

        또는

        {
            "valid": false,
            "errors": [
                "엣지의 source 노드가 존재하지 않습니다: unknown-node"
            ]
        }
    """
    try:
        errors = manager.validate_template(workflow)
        logger.info(f"템플릿 검증 완료: valid={len(errors) == 0}")
        return {"valid": len(errors) == 0, "errors": errors}
    except Exception as e:
        logger.error(f"템플릿 검증 실패: {e}")
        raise HTTPException(status_code=500, detail=f"템플릿 검증 실패: {str(e)}")
