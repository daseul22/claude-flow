"""
워크플로우 검증 스키마

워크플로우 검증 관련 스키마를 정의합니다.
"""

from typing import List
from pydantic import BaseModel, Field


class WorkflowValidationError(BaseModel):
    """
    워크플로우 검증 에러

    Attributes:
        severity: 심각도 ('error', 'warning', 'info')
        node_id: 에러가 발생한 노드 ID
        message: 에러 메시지
        suggestion: 해결 방법 제안
    """

    severity: str = Field(..., description="심각도 (error, warning, info)")
    node_id: str = Field(..., description="에러가 발생한 노드 ID")
    message: str = Field(..., description="에러 메시지")
    suggestion: str = Field(..., description="해결 방법 제안")


class WorkflowValidateResponse(BaseModel):
    """
    워크플로우 검증 응답

    Attributes:
        valid: 검증 통과 여부 (에러가 없으면 True)
        errors: 검증 에러 목록
    """

    valid: bool = Field(..., description="검증 통과 여부")
    errors: List[WorkflowValidationError] = Field(..., description="검증 에러 목록 (비어있으면 검증 통과)")
