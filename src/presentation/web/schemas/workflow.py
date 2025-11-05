"""
워크플로우 스키마 (호환성 레이어)

⚠️ 이 파일은 하위 호환성을 위한 재export 레이어입니다.
실제 스키마 정의는 다음 파일들에 있습니다:
- workflow_nodes.py: 노드 데이터 스키마
- workflow_core.py: 워크플로우 핵심 스키마
- workflow_api.py: API 요청/응답 및 이벤트
- project_schemas.py: 프로젝트 관련
- validation_schemas.py: 검증 관련
- display_schemas.py: Display 설정
- log_session_schemas.py: 로그 및 세션

기존 코드에서:
    from src.presentation.web.schemas.workflow import WorkflowNode, Workflow
이렇게 import하는 경로를 유지하기 위한 파일입니다.
"""

# 노드 데이터 스키마
from .workflow_nodes import (
    WorkerNodeData,
    InputNodeData,
    ConditionNodeData,
    MergeNodeData,
    WorkflowNodeData,
)

# 워크플로우 핵심 스키마
from .workflow_core import (
    WorkflowNode,
    WorkflowEdge,
    Workflow,
)

# API 요청/응답 및 이벤트
from .workflow_api import (
    WorkflowExecuteRequest,
    WorkflowExecuteResponse,
    WorkflowSaveRequest,
    WorkflowSaveResponse,
    WorkflowListResponse,
    TokenUsage,
    WorkflowNodeExecutionEvent,
)

# 프로젝트 스키마
from .project_schemas import (
    ProjectConfig,
    ProjectSelectRequest,
    ProjectSelectResponse,
    ProjectWorkflowSaveRequest,
    ProjectWorkflowLoadResponse,
)

# 검증 스키마
from .validation_schemas import (
    WorkflowValidationError,
    WorkflowValidateResponse,
)

# Display 설정
from .display_schemas import (
    DisplayConfig,
    DisplayConfigLoadResponse,
    DisplayConfigSaveRequest,
)

# 로그, 세션 및 보고서
from .log_session_schemas import (
    LogFileInfo,
    SessionFileInfo,
    LogListResponse,
    SessionListResponse,
    LogContentResponse,
    SessionContentResponse,
    ReportFileInfo,
    ReportListResponse,
    ReportContentResponse,
)

__all__ = [
    # 노드 데이터
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
    # 로그/세션/보고서
    "LogFileInfo",
    "SessionFileInfo",
    "LogListResponse",
    "SessionListResponse",
    "LogContentResponse",
    "SessionContentResponse",
    "ReportFileInfo",
    "ReportListResponse",
    "ReportContentResponse",
]
