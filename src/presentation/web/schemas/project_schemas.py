"""
프로젝트 관련 스키마

프로젝트 선택 및 워크플로우 설정 관련 스키마를 정의합니다.
"""

from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

from .workflow_core import Workflow


class ProjectConfig(BaseModel):
    """
    프로젝트 워크플로우 설정

    프로젝트 디렉토리의 .claude-flow/workflow-config.json에 저장됩니다.

    Attributes:
        project_path: 프로젝트 디렉토리 절대 경로
        workflow: 워크플로우 정의
        metadata: 메타데이터 (마지막 수정 시간 등)
    """

    project_path: str = Field(..., description="프로젝트 디렉토리 절대 경로")
    workflow: Workflow = Field(..., description="워크플로우 정의")
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="메타데이터 (last_modified, version 등)"
    )


class ProjectSelectRequest(BaseModel):
    """
    프로젝트 선택 요청

    Attributes:
        project_path: 프로젝트 디렉토리 절대 경로
    """

    project_path: str = Field(
        ..., description="프로젝트 디렉토리 절대 경로", example="/Users/username/my-project"
    )


class ProjectSelectResponse(BaseModel):
    """
    프로젝트 선택 응답

    Attributes:
        project_path: 선택된 프로젝트 경로
        message: 응답 메시지
        has_existing_config: 기존 설정 존재 여부
    """

    project_path: str = Field(..., description="선택된 프로젝트 경로")
    message: str = Field(..., description="응답 메시지")
    has_existing_config: bool = Field(..., description="기존 설정 존재 여부 (자동 로드 가능)")


class ProjectWorkflowSaveRequest(BaseModel):
    """
    프로젝트에 워크플로우 저장 요청

    Attributes:
        project_path: 프로젝트 디렉토리 경로 (옵션, 미제공 시 현재 프로젝트 사용)
        workflow: 저장할 워크플로우
    """

    project_path: Optional[str] = Field(default=None, description="프로젝트 디렉토리 경로 (미제공 시 현재 프로젝트)")
    workflow: Workflow = Field(..., description="저장할 워크플로우")


class ProjectWorkflowLoadResponse(BaseModel):
    """
    프로젝트에서 워크플로우 로드 응답

    Attributes:
        project_path: 프로젝트 경로
        workflow: 로드된 워크플로우
        last_modified: 마지막 수정 시간
    """

    project_path: str = Field(..., description="프로젝트 경로")
    workflow: Workflow = Field(..., description="로드된 워크플로우")
    last_modified: Optional[str] = Field(default=None, description="마지막 수정 시간 (ISO 8601)")
