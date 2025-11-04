"""
웹 API 스키마

Pydantic 모델을 정의합니다.
"""

from src.presentation.web.schemas.request import (
    AgentExecuteRequest,
    AgentListResponse,
    HealthCheckResponse,
    ErrorResponse,
)

# 워크플로우 스키마 재export (하위 호환성 유지)
from src.presentation.web.schemas.workflow_nodes import (
    WorkerNodeData,
    InputNodeData,
    ConditionNodeData,
    MergeNodeData,
    WorkflowNodeData,
)
from src.presentation.web.schemas.workflow_core import (
    WorkflowNode,
    WorkflowEdge,
    Workflow,
)
from src.presentation.web.schemas.workflow_api import (
    WorkflowExecuteRequest,
    WorkflowExecuteResponse,
    WorkflowSaveRequest,
    WorkflowSaveResponse,
    WorkflowListResponse,
    TokenUsage,
    WorkflowNodeExecutionEvent,
)
from src.presentation.web.schemas.project_schemas import (
    ProjectConfig,
    ProjectSelectRequest,
    ProjectSelectResponse,
    ProjectWorkflowSaveRequest,
    ProjectWorkflowLoadResponse,
)
from src.presentation.web.schemas.validation_schemas import (
    WorkflowValidationError,
    WorkflowValidateResponse,
)
from src.presentation.web.schemas.display_schemas import (
    DisplayConfig,
    DisplayConfigLoadResponse,
    DisplayConfigSaveRequest,
)
from src.presentation.web.schemas.log_session_schemas import (
    LogFileInfo,
    SessionFileInfo,
    LogListResponse,
    SessionListResponse,
    LogContentResponse,
    SessionContentResponse,
)

__all__ = [
    # 기존 스키마
    "AgentExecuteRequest",
    "AgentListResponse",
    "HealthCheckResponse",
    "ErrorResponse",
    # 워크플로우 노드 데이터
    "WorkerNodeData",
    "InputNodeData",
    "ConditionNodeData",
    "MergeNodeData",
    "WorkflowNodeData",
    # 워크플로우 핵심
    "WorkflowNode",
    "WorkflowEdge",
    "Workflow",
    # API 요청/응답
    "WorkflowExecuteRequest",
    "WorkflowExecuteResponse",
    "WorkflowSaveRequest",
    "WorkflowSaveResponse",
    "WorkflowListResponse",
    "TokenUsage",
    "WorkflowNodeExecutionEvent",
    # 프로젝트
    "ProjectConfig",
    "ProjectSelectRequest",
    "ProjectSelectResponse",
    "ProjectWorkflowSaveRequest",
    "ProjectWorkflowLoadResponse",
    # 검증
    "WorkflowValidationError",
    "WorkflowValidateResponse",
    # Display
    "DisplayConfig",
    "DisplayConfigLoadResponse",
    "DisplayConfigSaveRequest",
    # 로그/세션
    "LogFileInfo",
    "SessionFileInfo",
    "LogListResponse",
    "SessionListResponse",
    "LogContentResponse",
    "SessionContentResponse",
]
