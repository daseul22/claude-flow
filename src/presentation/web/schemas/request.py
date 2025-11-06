"""
웹 API 요청/응답 스키마 정의

이 모듈은 FastAPI 엔드포인트에서 사용하는 Pydantic 모델을 정의합니다.
"""

from typing import Optional, List
from pydantic import BaseModel, Field, field_validator


class AgentExecuteRequest(BaseModel):
    """Worker Agent 실행 요청 스키마"""

    agent_name: str = Field(
        ...,
        description="실행할 Worker Agent 이름 (예: planner, coder, reviewer)",
        min_length=1,
        max_length=50,
    )
    task_description: str = Field(
        ...,
        description="Agent에게 전달할 작업 설명",
        min_length=1,
        max_length=5000,  # 프롬프트 인젝션 방어
    )
    session_id: Optional[str] = Field(
        None,
        description="세션 ID (선택적, 미제공 시 자동 생성)",
        min_length=1,
        max_length=100,
    )

    @field_validator("agent_name")
    @classmethod
    def validate_agent_name(cls, v: str) -> str:
        """Agent 이름 검증 (알파벳, 숫자, 언더스코어만 허용)"""
        if not v.replace("_", "").isalnum():
            raise ValueError("Agent 이름은 알파벳, 숫자, 언더스코어만 포함해야 합니다")
        return v.lower()

    @field_validator("task_description")
    @classmethod
    def validate_task_description(cls, v: str) -> str:
        """작업 설명 검증 (공백만 있는 경우 거부)"""
        if not v.strip():
            raise ValueError("작업 설명은 비어있을 수 없습니다")
        return v.strip()


class AgentInfo(BaseModel):
    """Agent 정보 스키마"""

    name: str = Field(..., description="Agent 이름")
    role: str = Field(..., description="Agent 역할")
    description: str = Field(..., description="Agent 설명")
    system_prompt: str = Field(..., description="시스템 프롬프트 원본")
    allowed_tools: List[str] = Field(default_factory=list, description="사용 가능한 도구 목록")
    model: Optional[str] = Field(None, description="사용하는 Claude 모델")
    is_custom: bool = Field(default=False, description="커스텀 워커 여부")


class AgentListResponse(BaseModel):
    """사용 가능한 Agent 목록 응답 스키마"""

    agents: list[AgentInfo] = Field(
        ...,
        description="Agent 목록 (name, role, description, system_prompt 포함)",
    )


class HealthCheckResponse(BaseModel):
    """Health check 응답 스키마"""

    status: str = Field(..., description="서비스 상태 (ok/error)")
    message: str = Field(..., description="상태 메시지")


class ErrorResponse(BaseModel):
    """에러 응답 스키마"""

    error: str = Field(..., description="에러 메시지")
    detail: Optional[str] = Field(None, description="상세 에러 정보")


class CustomWorkerGenerateRequest(BaseModel):
    """커스텀 워커 생성 요청 스키마"""

    worker_requirements: str = Field(
        ...,
        description="원하는 워커의 요구사항 설명",
        min_length=10,
        max_length=2000,
    )
    session_id: Optional[str] = Field(
        None,
        description="세션 ID (선택적, 미제공 시 자동 생성)",
    )

    @field_validator("worker_requirements")
    @classmethod
    def validate_requirements(cls, v: str) -> str:
        """요구사항 검증"""
        if not v.strip():
            raise ValueError("워커 요구사항은 비어있을 수 없습니다")
        return v.strip()


class CustomWorkerSaveRequest(BaseModel):
    """커스텀 워커 저장 요청 스키마"""

    project_path: str = Field(
        ...,
        description="프로젝트 경로",
        min_length=1,
    )
    worker_name: str = Field(
        ...,
        description="워커 이름 (영문, 숫자, _ 만 가능)",
        min_length=1,
        max_length=50,
    )
    role: str = Field(
        ...,
        description="워커 역할 설명",
        min_length=1,
        max_length=100,
    )
    prompt_content: str = Field(
        ...,
        description="시스템 프롬프트 내용",
        min_length=10,
    )
    allowed_tools: List[str] = Field(
        ...,
        description="허용 도구 리스트",
        min_items=1,
    )
    model: str = Field(
        default="claude-sonnet-4-5-20250929",
        description="사용 모델",
    )
    thinking: bool = Field(
        default=False,
        description="Thinking 활성화 여부",
    )

    @field_validator("worker_name")
    @classmethod
    def validate_worker_name(cls, v: str) -> str:
        """워커 이름 검증"""
        if not v.replace("_", "").isalnum():
            raise ValueError("워커 이름은 알파벳, 숫자, 언더스코어만 포함해야 합니다")
        return v.lower()

    @field_validator("allowed_tools")
    @classmethod
    def validate_tools(cls, v: List[str]) -> List[str]:
        """도구 검증"""
        valid_tools = {"read", "write", "edit", "bash", "glob", "grep"}
        for tool in v:
            if tool not in valid_tools:
                raise ValueError(f"유효하지 않은 도구: {tool}")
        return v


class CustomWorkerInfo(BaseModel):
    """커스텀 워커 정보 스키마"""

    name: str = Field(..., description="워커 이름")
    role: str = Field(..., description="워커 역할")
    allowed_tools: List[str] = Field(..., description="허용 도구")
    model: str = Field(..., description="사용 모델")
    thinking: bool = Field(..., description="Thinking 활성화")
    prompt_preview: str = Field(..., description="프롬프트 미리보기 (첫 100자)")


class CustomWorkerListResponse(BaseModel):
    """커스텀 워커 목록 응답 스키마"""

    workers: List[CustomWorkerInfo] = Field(..., description="커스텀 워커 목록")


class WorkflowDesignRequest(BaseModel):
    """워크플로우 설계 요청 스키마"""

    requirements: str = Field(
        ...,
        description="원하는 워크플로우의 요구사항 설명",
        min_length=10,
        max_length=2000,
    )
    session_id: Optional[str] = Field(
        None,
        description="세션 ID (선택적, 미제공 시 자동 생성)",
    )
    current_workflow: Optional[dict] = Field(
        None,
        description="현재 워크플로우 (개선 모드일 때 전달)",
    )
    mode: str = Field(
        default="create",
        description="워크플로우 설계 모드 (create: 새로 만들기, improve: 개선하기)",
    )
    project_path: Optional[str] = Field(
        None,
        description="프로젝트 경로 (워크플로우 설계 시 분석할 프로젝트 디렉토리)",
    )

    @field_validator("requirements")
    @classmethod
    def validate_requirements(cls, v: str) -> str:
        """요구사항 검증"""
        if not v.strip():
            raise ValueError("워크플로우 요구사항은 비어있을 수 없습니다")
        return v.strip()

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: str) -> str:
        """모드 검증"""
        if v not in ("create", "improve"):
            raise ValueError("모드는 'create' 또는 'improve'만 가능합니다")
        return v
