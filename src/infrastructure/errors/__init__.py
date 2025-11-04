"""
표준화된 에러 클래스 계층 구조

모든 커스텀 에러는 BaseError를 상속받아 일관된 에러 처리를 구현합니다.
"""

from .base import BaseError, ErrorCategory
from .domain_errors import (
    DomainError,
    ValidationError,
    ConfigurationError,
    WorkflowValidationError,
    NodeExecutionError,
)
from .infrastructure_errors import (
    InfrastructureError,
    SDKError,
    CLIError,
    StorageError,
    NetworkError,
)
from .presentation_errors import (
    PresentationError,
    APIError,
    AuthenticationError,
    AuthorizationError,
    ResourceNotFoundError,
    ConflictError,
)

__all__ = [
    # 베이스
    "BaseError",
    "ErrorCategory",
    # 도메인 에러
    "DomainError",
    "ValidationError",
    "ConfigurationError",
    "WorkflowValidationError",
    "NodeExecutionError",
    # 인프라 에러
    "InfrastructureError",
    "SDKError",
    "CLIError",
    "StorageError",
    "NetworkError",
    # Presentation 에러
    "PresentationError",
    "APIError",
    "AuthenticationError",
    "AuthorizationError",
    "ResourceNotFoundError",
    "ConflictError",
]
