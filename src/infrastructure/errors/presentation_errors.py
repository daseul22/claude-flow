"""
Presentation 에러 클래스

API/UI 레이어의 에러를 정의합니다.
"""

from typing import Any

from .base import BaseError, ErrorCategory


class PresentationError(BaseError):
    """Presentation 레이어 에러 베이스 클래스"""

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
            category=ErrorCategory.PRESENTATION,
            status_code=status_code,
            details=details,
            original_exception=original_exception,
        )


class APIError(PresentationError):
    """일반 API 에러"""

    def __init__(
        self,
        message: str,
        status_code: int = 400,
        details: dict[str, Any] | None = None,
        original_exception: Exception | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="API_ERROR",
            status_code=status_code,
            details=details,
            original_exception=original_exception,
        )


class AuthenticationError(PresentationError):
    """인증 에러 (401)"""

    def __init__(
        self,
        message: str = "인증이 필요합니다",
        details: dict[str, Any] | None = None,
        original_exception: Exception | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="AUTHENTICATION_ERROR",
            status_code=401,
            details=details,
            original_exception=original_exception,
        )


class AuthorizationError(PresentationError):
    """권한 에러 (403)"""

    def __init__(
        self,
        message: str = "권한이 없습니다",
        resource: str | None = None,
        details: dict[str, Any] | None = None,
        original_exception: Exception | None = None,
    ) -> None:
        error_details = details or {}
        if resource:
            error_details["resource"] = resource

        super().__init__(
            message=message,
            code="AUTHORIZATION_ERROR",
            status_code=403,
            details=error_details,
            original_exception=original_exception,
        )


class ResourceNotFoundError(PresentationError):
    """리소스를 찾을 수 없음 (404)"""

    def __init__(
        self,
        message: str,
        resource_type: str | None = None,
        resource_id: str | None = None,
        details: dict[str, Any] | None = None,
        original_exception: Exception | None = None,
    ) -> None:
        error_details = details or {}
        if resource_type:
            error_details["resource_type"] = resource_type
        if resource_id:
            error_details["resource_id"] = resource_id

        super().__init__(
            message=message,
            code="RESOURCE_NOT_FOUND",
            status_code=404,
            details=error_details,
            original_exception=original_exception,
        )


class ConflictError(PresentationError):
    """리소스 충돌 (409)"""

    def __init__(
        self,
        message: str,
        conflicting_resource: str | None = None,
        details: dict[str, Any] | None = None,
        original_exception: Exception | None = None,
    ) -> None:
        error_details = details or {}
        if conflicting_resource:
            error_details["conflicting_resource"] = conflicting_resource

        super().__init__(
            message=message,
            code="CONFLICT_ERROR",
            status_code=409,
            details=error_details,
            original_exception=original_exception,
        )
