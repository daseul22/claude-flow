"""
워크플로우 API 요청/응답 스키마

API 엔드포인트의 요청 및 응답 구조를 정의합니다.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from .workflow_core import Workflow


class WorkflowExecuteRequest(BaseModel):
    """
    워크플로우 실행 요청

    Attributes:
        workflow: 실행할 워크플로우
        initial_input: 초기 입력 데이터
        start_node_id: 시작 노드 ID (옵션, Input 노드 선택)
        session_id: 세션 ID (옵션)
        last_event_index: 마지막 수신 이벤트 인덱스 (재접속 시 중복 방지용, 옵션)
    """

    workflow: Workflow = Field(..., description="실행할 워크플로우")
    initial_input: str = Field(..., description="초기 입력 데이터 (첫 번째 노드에 전달)")
    start_node_id: Optional[str] = Field(
        default=None, description="시작 노드 ID (옵션, 지정 시 해당 Input 노드에서만 시작)"
    )
    session_id: Optional[str] = Field(default=None, description="세션 ID (비워두면 자동 생성)")
    last_event_index: Optional[int] = Field(
        default=None, description="마지막 수신 이벤트 인덱스 (재접속 시 중복 방지용, 0부터 시작)"
    )


class WorkflowExecuteResponse(BaseModel):
    """
    워크플로우 실행 응답

    Attributes:
        session_id: 세션 ID
        status: 실행 상태 (running, completed, failed)
        message: 상태 메시지
    """

    session_id: str = Field(..., description="세션 ID")
    status: str = Field(..., description="실행 상태")
    message: str = Field(..., description="상태 메시지")


class WorkflowSaveRequest(BaseModel):
    """
    워크플로우 저장 요청

    Attributes:
        workflow: 저장할 워크플로우
    """

    workflow: Workflow = Field(..., description="저장할 워크플로우")


class WorkflowSaveResponse(BaseModel):
    """
    워크플로우 저장 응답

    Attributes:
        workflow_id: 저장된 워크플로우 ID
        message: 응답 메시지
    """

    workflow_id: str = Field(..., description="저장된 워크플로우 ID")
    message: str = Field(..., description="응답 메시지")


class WorkflowListResponse(BaseModel):
    """
    워크플로우 목록 응답

    Attributes:
        workflows: 워크플로우 목록 (메타데이터만)
    """

    workflows: List[Dict[str, Any]] = Field(..., description="워크플로우 목록 (id, name, description)")


class TokenUsage(BaseModel):
    """
    토큰 사용량 정보

    Attributes:
        input_tokens: 입력 토큰 수
        output_tokens: 출력 토큰 수
        total_tokens: 전체 토큰 수
    """

    input_tokens: int = Field(default=0, description="입력 토큰 수")
    output_tokens: int = Field(default=0, description="출력 토큰 수")
    total_tokens: int = Field(default=0, description="전체 토큰 수")


class WorkflowNodeExecutionEvent(BaseModel):
    """
    워크플로우 노드 실행 이벤트 (SSE)

    Attributes:
        event_type: 이벤트 타입 (node_start, node_output, node_complete, node_error)
        node_id: 노드 ID
        data: 이벤트 데이터
        timestamp: 이벤트 발생 시각 (ISO 8601)
        elapsed_time: 노드 실행 경과 시간 (초)
        token_usage: 토큰 사용량 정보
    """

    event_type: str = Field(..., description="이벤트 타입", example="node_start")
    node_id: str = Field(..., description="노드 ID")
    data: Dict[str, Any] = Field(..., description="이벤트 데이터")
    timestamp: Optional[str] = Field(default=None, description="이벤트 발생 시각 (ISO 8601 형식)")
    elapsed_time: Optional[float] = Field(default=None, description="노드 실행 경과 시간 (초)")
    token_usage: Optional[TokenUsage] = Field(default=None, description="토큰 사용량 정보")
