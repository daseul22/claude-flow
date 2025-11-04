"""
워크플로우 템플릿 관련 스키마 정의

Template: 워크플로우 템플릿 (워크플로우 + 메타데이터)
TemplateMetadata: 템플릿 메타데이터 (목록 조회용)
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from src.presentation.web.schemas.workflow import Workflow


class TemplateMetadata(BaseModel):
    """
    템플릿 메타데이터 (목록 조회용)

    Attributes:
        id: 템플릿 고유 ID
        name: 템플릿 이름
        description: 템플릿 설명
        category: 카테고리 (예: code_review, testing, bug_fix, planning)
        node_count: 노드 개수
        edge_count: 엣지 개수
        thumbnail: 썸네일 URL (옵션)
        tags: 태그 목록 (옵션)
        is_builtin: 내장 템플릿 여부
        created_at: 생성 시간 (ISO 8601)
        updated_at: 수정 시간 (ISO 8601)
    """

    id: str = Field(..., description="템플릿 고유 ID")
    name: str = Field(..., description="템플릿 이름")
    description: Optional[str] = Field(default=None, description="템플릿 설명")
    category: str = Field(..., description="카테고리", example="code_review")
    node_count: int = Field(default=0, description="노드 개수")
    edge_count: int = Field(default=0, description="엣지 개수")
    thumbnail: Optional[str] = Field(default=None, description="썸네일 URL")
    tags: Optional[List[str]] = Field(default_factory=list, description="태그 목록")
    is_builtin: bool = Field(default=False, description="내장 템플릿 여부 (삭제 불가)")
    created_at: Optional[str] = Field(default=None, description="생성 시간 (ISO 8601)")
    updated_at: Optional[str] = Field(default=None, description="수정 시간 (ISO 8601)")


class Template(BaseModel):
    """
    워크플로우 템플릿 (전체)

    Attributes:
        id: 템플릿 고유 ID
        name: 템플릿 이름
        description: 템플릿 설명
        category: 카테고리
        workflow: 워크플로우 정의
        thumbnail: 썸네일 URL (옵션)
        tags: 태그 목록 (옵션)
        is_builtin: 내장 템플릿 여부
        metadata: 추가 메타데이터 (옵션)
        created_at: 생성 시간 (ISO 8601)
        updated_at: 수정 시간 (ISO 8601)
    """

    id: str = Field(..., description="템플릿 고유 ID")
    name: str = Field(..., description="템플릿 이름")
    description: Optional[str] = Field(default=None, description="템플릿 설명")
    category: str = Field(..., description="카테고리", example="code_review")
    workflow: Workflow = Field(..., description="워크플로우 정의")
    thumbnail: Optional[str] = Field(default=None, description="썸네일 URL")
    tags: Optional[List[str]] = Field(default_factory=list, description="태그 목록")
    is_builtin: bool = Field(default=False, description="내장 템플릿 여부 (삭제 불가)")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="추가 메타데이터")
    created_at: Optional[str] = Field(default=None, description="생성 시간 (ISO 8601)")
    updated_at: Optional[str] = Field(default=None, description="수정 시간 (ISO 8601)")

    def to_metadata(self) -> TemplateMetadata:
        """템플릿 메타데이터 추출 (목록 조회용)"""
        return TemplateMetadata(
            id=self.id,
            name=self.name,
            description=self.description,
            category=self.category,
            node_count=len(self.workflow.nodes),
            edge_count=len(self.workflow.edges),
            thumbnail=self.thumbnail,
            tags=self.tags,
            is_builtin=self.is_builtin,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )


class TemplateListResponse(BaseModel):
    """
    템플릿 목록 응답

    Attributes:
        templates: 템플릿 메타데이터 목록
    """

    templates: List[TemplateMetadata] = Field(..., description="템플릿 메타데이터 목록")


class TemplateSaveRequest(BaseModel):
    """
    템플릿 저장 요청

    Attributes:
        name: 템플릿 이름
        description: 템플릿 설명 (옵션)
        category: 카테고리
        workflow: 워크플로우 정의
        tags: 태그 목록 (옵션)
    """

    name: str = Field(..., description="템플릿 이름")
    description: Optional[str] = Field(default=None, description="템플릿 설명")
    category: str = Field(..., description="카테고리", example="custom")
    workflow: Workflow = Field(..., description="워크플로우 정의")
    tags: Optional[List[str]] = Field(default_factory=list, description="태그 목록")


class TemplateSaveResponse(BaseModel):
    """
    템플릿 저장 응답

    Attributes:
        template_id: 저장된 템플릿 ID
        message: 응답 메시지
    """

    template_id: str = Field(..., description="저장된 템플릿 ID")
    message: str = Field(..., description="응답 메시지")
