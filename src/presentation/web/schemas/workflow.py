"""
워크플로우 관련 스키마 정의

WorkflowNode: 워크플로우 캔버스의 노드 (Worker Agent)
WorkflowEdge: 노드 간 연결 (데이터 흐름)
Workflow: 전체 워크플로우 정의
"""

from typing import List, Dict, Any, Optional, Union
from pydantic import BaseModel, Field


class WorkerNodeData(BaseModel):
    """
    Worker 노드의 데이터 (개별 Worker Agent)

    Attributes:
        agent_name: Worker Agent 이름 (planner, coder, reviewer 등)
        task_template: 작업 설명 템플릿 ({{input}} 등의 변수 지원)
        allowed_tools: 사용 가능한 도구 목록 (옵션, 미지정 시 기본 설정 사용)
        thinking: Thinking 모드 활성화 여부 (ultrathink 프롬프트 추가, 옵션)
        parallel_execution: 자식 노드를 병렬로 실행할지 여부 (기본: false)
        config: 추가 설정 (옵션)
    """

    agent_name: str = Field(..., description="Worker Agent 이름")
    task_template: str = Field(..., description="작업 설명 템플릿 ({{input}}, {{node_id}} 등 변수 지원)")
    allowed_tools: Optional[List[str]] = Field(
        default=None, description="사용 가능한 도구 목록 (옵션, 미지정 시 agent_config.json의 기본값 사용)"
    )
    thinking: Optional[bool] = Field(
        default=None, description="Thinking 모드 활성화 여부 (ultrathink 프롬프트 추가, 옵션)"
    )
    parallel_execution: Optional[bool] = Field(
        default=False, description="자식 노드를 병렬로 실행할지 여부 (기본: false)"
    )
    config: Optional[Dict[str, Any]] = Field(default=None, description="추가 설정 (옵션)")


class InputNodeData(BaseModel):
    """
    Input 노드의 데이터 (워크플로우 시작점)

    Input 노드는 워크플로우의 시작점으로, 초기 입력을 저장하고
    연결된 노드로 전달합니다.

    Attributes:
        initial_input: 초기 입력 텍스트
        parallel_execution: 자식 노드를 병렬로 실행할지 여부 (기본: false)
    """

    initial_input: str = Field(..., description="워크플로우 초기 입력 텍스트")
    parallel_execution: Optional[bool] = Field(
        default=False, description="자식 노드를 병렬로 실행할지 여부 (기본: false)"
    )


class ConditionNodeData(BaseModel):
    """
    조건 분기 노드의 데이터

    조건 분기 노드는 이전 노드의 출력을 평가하여 True/False 경로로 분기합니다.
    반복 기능을 활성화하면 false 경로가 순환을 만들 때 최대 반복 횟수를 제한합니다.

    Attributes:
        condition_type: 조건 타입 ('contains', 'regex', 'length', 'custom', 'llm')
        condition_value: 조건 값 (예: 'success', '\\d{3}', '100', 'len(output) > 0')
        true_branch_id: True 경로 노드 ID
        false_branch_id: False 경로 노드 ID (옵션)
        max_iterations: 최대 반복 횟수 (옵션, 피드백 루프 제한용)
        parallel_execution: 자식 노드를 병렬로 실행할지 여부 (기본: false)
    """

    condition_type: str = Field(..., description="조건 타입 (contains, regex, length, custom, llm)")
    condition_value: str = Field(..., description="조건 값 (타입에 따라 다름)")
    true_branch_id: Optional[str] = Field(
        default=None, description="True 경로 노드 ID (동적으로 엣지로 관리될 수 있음)"
    )
    false_branch_id: Optional[str] = Field(
        default=None, description="False 경로 노드 ID (동적으로 엣지로 관리될 수 있음)"
    )
    max_iterations: Optional[int] = Field(
        default=None, description="최대 반복 횟수 (None이면 반복 안함, 피드백 루프에서 무한 반복 방지)"
    )
    parallel_execution: Optional[bool] = Field(
        default=False, description="자식 노드를 병렬로 실행할지 여부 (기본: false)"
    )


class MergeNodeData(BaseModel):
    """
    병합 노드의 데이터

    병합 노드는 여러 분기의 출력을 하나로 통합합니다.

    Attributes:
        merge_strategy: 병합 전략 ('concatenate', 'first', 'last', 'custom')
        separator: 결합 시 사용할 구분자 (concatenate 전략 시)
        custom_template: 커스텀 병합 템플릿 (옵션)
        parallel_execution: 자식 노드를 병렬로 실행할지 여부 (기본: false)
    """

    merge_strategy: str = Field(
        default="concatenate", description="병합 전략 (concatenate, first, last, custom)"
    )
    separator: str = Field(default="\n\n---\n\n", description="결합 시 사용할 구분자 (concatenate 전략 시)")
    custom_template: Optional[str] = Field(
        default=None, description="커스텀 병합 템플릿 ({{branch_1}}, {{branch_2}} 등)"
    )
    parallel_execution: Optional[bool] = Field(
        default=False, description="자식 노드를 병렬로 실행할지 여부 (기본: false)"
    )


# Union 타입으로 모든 노드 타입 포함
WorkflowNodeData = Union[WorkerNodeData, InputNodeData, ConditionNodeData, MergeNodeData]


class WorkflowNode(BaseModel):
    """
    워크플로우 노드 (React Flow 호환 형식)

    Attributes:
        id: 노드 고유 ID
        type: 노드 타입 (worker, input, condition, merge)
        position: 캔버스 상의 위치 {x, y}
        data: 노드 데이터 (WorkerNodeData, InputNodeData, ConditionNodeData, MergeNodeData)
    """

    id: str = Field(..., description="노드 고유 ID")
    type: str = Field(default="worker", description="노드 타입 (worker, input, condition, merge)")
    position: Dict[str, float] = Field(..., description="캔버스 상의 위치", example={"x": 100, "y": 100})
    data: Union[
        WorkerNodeData, InputNodeData, ConditionNodeData, MergeNodeData, Dict[str, Any]
    ] = Field(..., description="노드 데이터 (타입에 따라 다름)")


class WorkflowEdge(BaseModel):
    """
    워크플로우 엣지 (노드 간 연결)

    Attributes:
        id: 엣지 고유 ID
        source: 시작 노드 ID
        target: 종료 노드 ID
        sourceHandle: 시작 핸들 ID (옵션)
        targetHandle: 종료 핸들 ID (옵션)
    """

    id: str = Field(..., description="엣지 고유 ID")
    source: str = Field(..., description="시작 노드 ID")
    target: str = Field(..., description="종료 노드 ID")
    sourceHandle: Optional[str] = Field(default=None, description="시작 핸들 ID")
    targetHandle: Optional[str] = Field(default=None, description="종료 핸들 ID")


class Workflow(BaseModel):
    """
    워크플로우 정의 (전체)

    Attributes:
        id: 워크플로우 고유 ID
        name: 워크플로우 이름
        description: 워크플로우 설명
        nodes: 노드 목록
        edges: 엣지 목록
        metadata: 추가 메타데이터 (옵션)
    """

    id: Optional[str] = Field(default=None, description="워크플로우 고유 ID")
    name: str = Field(..., description="워크플로우 이름")
    description: Optional[str] = Field(default=None, description="워크플로우 설명")
    nodes: List[WorkflowNode] = Field(..., description="노드 목록")
    edges: List[WorkflowEdge] = Field(..., description="엣지 목록")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="추가 메타데이터")


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


# ==================== 프로젝트 설정 스키마 ====================


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


# ==================== 워크플로우 검증 스키마 ====================


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


# ==================== Display 설정 스키마 ====================


class DisplayConfig(BaseModel):
    """
    웹 UI Display 설정

    프로젝트 디렉토리의 .claude-flow/display-config.json에 저장됩니다.

    Attributes:
        left_sidebar_open: 왼쪽 사이드바 열림 상태
        right_sidebar_open: 오른쪽 사이드바 열림 상태
        expanded_sections: 확장된 섹션 목록 (NodePanel)
    """

    left_sidebar_open: bool = Field(default=True, description="왼쪽 사이드바 열림 상태")
    right_sidebar_open: bool = Field(default=True, description="오른쪽 사이드바 열림 상태")
    expanded_sections: List[str] = Field(
        default_factory=lambda: [
            "input",
            "manager",
            "advanced",
            "general",
            "specialized",
            "custom",
        ],
        description="확장된 섹션 목록 (NodePanel)",
    )


class DisplayConfigLoadResponse(BaseModel):
    """
    Display 설정 로드 응답

    Attributes:
        config: Display 설정
    """

    config: DisplayConfig = Field(..., description="Display 설정")


class DisplayConfigSaveRequest(BaseModel):
    """
    Display 설정 저장 요청

    Attributes:
        config: 저장할 Display 설정
    """

    config: DisplayConfig = Field(..., description="저장할 Display 설정")


# ============================================================================
# 로그 및 세션 뷰어 스키마
# ============================================================================


class LogFileInfo(BaseModel):
    """
    로그 파일 정보

    Attributes:
        path: 파일 상대 경로 (logs/ 기준)
        name: 파일명
        size: 파일 크기 (bytes)
        modified: 수정 시간 (ISO 8601)
        type: 파일 타입 (system, debug, info, error)
    """

    path: str = Field(..., description="파일 상대 경로")
    name: str = Field(..., description="파일명")
    size: int = Field(..., description="파일 크기 (bytes)")
    modified: str = Field(..., description="수정 시간 (ISO 8601)")
    type: str = Field(..., description="파일 타입 (system, debug, info, error)")


class SessionFileInfo(BaseModel):
    """
    세션 파일 정보

    Attributes:
        session_id: 세션 ID
        path: 파일 경로
        size: 파일 크기 (bytes)
        created: 생성 시간 (ISO 8601)
        modified: 수정 시간 (ISO 8601)
        status: 세션 상태 (running, completed, error, cancelled)
    """

    session_id: str = Field(..., description="세션 ID")
    path: str = Field(..., description="파일 경로")
    size: int = Field(..., description="파일 크기 (bytes)")
    created: str = Field(..., description="생성 시간 (ISO 8601)")
    modified: str = Field(..., description="수정 시간 (ISO 8601)")
    status: str = Field(..., description="세션 상태")


class LogListResponse(BaseModel):
    """
    로그 파일 목록 응답

    Attributes:
        logs: 로그 파일 목록
        total_count: 전체 파일 개수
        total_size: 전체 파일 크기 (bytes)
    """

    logs: List[LogFileInfo] = Field(..., description="로그 파일 목록")
    total_count: int = Field(..., description="전체 파일 개수")
    total_size: int = Field(..., description="전체 파일 크기 (bytes)")


class SessionListResponse(BaseModel):
    """
    세션 파일 목록 응답

    Attributes:
        sessions: 세션 파일 목록
        total_count: 전체 세션 개수
        total_size: 전체 파일 크기 (bytes)
    """

    sessions: List[SessionFileInfo] = Field(..., description="세션 파일 목록")
    total_count: int = Field(..., description="전체 세션 개수")
    total_size: int = Field(..., description="전체 파일 크기 (bytes)")


class LogContentResponse(BaseModel):
    """
    로그 파일 내용 응답

    Attributes:
        content: 로그 파일 내용
        file_info: 파일 정보
    """

    content: str = Field(..., description="로그 파일 내용")
    file_info: LogFileInfo = Field(..., description="파일 정보")


class SessionContentResponse(BaseModel):
    """
    세션 파일 내용 응답

    Attributes:
        content: 세션 파일 내용 (JSON)
        file_info: 파일 정보
    """

    content: Dict[str, Any] = Field(..., description="세션 파일 내용 (JSON)")
    file_info: SessionFileInfo = Field(..., description="파일 정보")
