"""
도메인 에러 클래스

비즈니스 로직 레이어의 에러를 정의합니다.
"""

from typing import Any

from .base import BaseError, ErrorCategory


class DomainError(BaseError):
    """도메인 레이어 에러 베이스 클래스"""

    def __init__(
        self,
        message: str,
        code: str,
        status_code: int = 400,
        details: dict[str, Any] | None = None,
        original_exception: Exception | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code=code,
            category=ErrorCategory.DOMAIN,
            status_code=status_code,
            details=details,
            original_exception=original_exception,
        )


class ValidationError(DomainError):
    """검증 에러 (입력 데이터, 워크플로우 등)"""

    def __init__(
        self,
        message: str,
        field: str | None = None,
        details: dict[str, Any] | None = None,
        original_exception: Exception | None = None,
    ) -> None:
        error_details = details or {}
        if field:
            error_details["field"] = field

        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            status_code=400,
            details=error_details,
            original_exception=original_exception,
        )


class ConfigurationError(DomainError):
    """설정 에러 (Agent 설정, 프로젝트 설정 등)"""

    def __init__(
        self,
        message: str,
        config_key: str | None = None,
        details: dict[str, Any] | None = None,
        original_exception: Exception | None = None,
    ) -> None:
        error_details = details or {}
        if config_key:
            error_details["config_key"] = config_key

        super().__init__(
            message=message,
            code="CONFIGURATION_ERROR",
            status_code=400,
            details=error_details,
            original_exception=original_exception,
        )


class WorkflowValidationError(DomainError):
    """워크플로우 검증 에러"""

    def __init__(
        self,
        message: str,
        node_id: str | None = None,
        edge_id: str | None = None,
        details: dict[str, Any] | None = None,
        original_exception: Exception | None = None,
    ) -> None:
        error_details = details or {}
        if node_id:
            error_details["node_id"] = node_id
        if edge_id:
            error_details["edge_id"] = edge_id

        super().__init__(
            message=message,
            code="WORKFLOW_VALIDATION_ERROR",
            status_code=400,
            details=error_details,
            original_exception=original_exception,
        )


class NodeExecutionError(DomainError):
    """노드 실행 에러"""

    def __init__(
        self,
        message: str,
        node_id: str,
        agent_name: str | None = None,
        details: dict[str, Any] | None = None,
        original_exception: Exception | None = None,
    ) -> None:
        error_details = details or {}
        error_details["node_id"] = node_id
        if agent_name:
            error_details["agent_name"] = agent_name

        super().__init__(
            message=message,
            code="NODE_EXECUTION_ERROR",
            status_code=500,
            details=error_details,
            original_exception=original_exception,
        )
