"""
인프라 에러 클래스

인프라 레이어 (SDK, CLI, Storage 등)의 에러를 정의합니다.
"""

from typing import Any

from .base import BaseError, ErrorCategory


class InfrastructureError(BaseError):
    """인프라 레이어 에러 베이스 클래스"""

    def __init__(
        self,
        message: str,
        code: str,
        status_code: int = 500,
        details: dict[str, Any] | None = None,
        original_exception: Exception | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code=code,
            category=ErrorCategory.INFRASTRUCTURE,
            status_code=status_code,
            details=details,
            original_exception=original_exception,
        )


class SDKError(InfrastructureError):
    """Claude Agent SDK 에러"""

    def __init__(
        self,
        message: str,
        sdk_error_type: str | None = None,
        details: dict[str, Any] | None = None,
        original_exception: Exception | None = None,
    ) -> None:
        error_details = details or {}
        if sdk_error_type:
            error_details["sdk_error_type"] = sdk_error_type

        super().__init__(
            message=message,
            code="SDK_ERROR",
            status_code=500,
            details=error_details,
            original_exception=original_exception,
        )


class CLIError(InfrastructureError):
    """Claude CLI 실행 에러"""

    def __init__(
        self,
        message: str,
        command: str | None = None,
        exit_code: int | None = None,
        details: dict[str, Any] | None = None,
        original_exception: Exception | None = None,
    ) -> None:
        error_details = details or {}
        if command:
            error_details["command"] = command
        if exit_code is not None:
            error_details["exit_code"] = exit_code

        super().__init__(
            message=message,
            code="CLI_ERROR",
            status_code=500,
            details=error_details,
            original_exception=original_exception,
        )


class StorageError(InfrastructureError):
    """스토리지 (파일, DB 등) 에러"""

    def __init__(
        self,
        message: str,
        path: str | None = None,
        operation: str | None = None,
        details: dict[str, Any] | None = None,
        original_exception: Exception | None = None,
    ) -> None:
        error_details = details or {}
        if path:
            error_details["path"] = path
        if operation:
            error_details["operation"] = operation

        super().__init__(
            message=message,
            code="STORAGE_ERROR",
            status_code=500,
            details=error_details,
            original_exception=original_exception,
        )


class NetworkError(InfrastructureError):
    """네트워크 에러 (API 호출, 외부 서비스 등)"""

    def __init__(
        self,
        message: str,
        url: str | None = None,
        status_code: int | None = None,
        details: dict[str, Any] | None = None,
        original_exception: Exception | None = None,
    ) -> None:
        error_details = details or {}
        if url:
            error_details["url"] = url

        super().__init__(
            message=message,
            code="NETWORK_ERROR",
            status_code=status_code or 503,
            details=error_details,
            original_exception=original_exception,
        )
