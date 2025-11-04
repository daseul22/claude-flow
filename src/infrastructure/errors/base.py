"""
베이스 에러 클래스

모든 커스텀 에러의 추상 베이스 클래스입니다.
"""

from enum import Enum
from typing import Any


class ErrorCategory(str, Enum):
    """에러 카테고리"""

    DOMAIN = "domain"  # 비즈니스 로직 에러
    INFRASTRUCTURE = "infrastructure"  # 인프라 레이어 에러
    PRESENTATION = "presentation"  # API/UI 레이어 에러


class BaseError(Exception):
    """
    모든 커스텀 에러의 베이스 클래스

    Attributes:
        message: 에러 메시지
        code: 에러 코드 (예: WORKFLOW_VALIDATION_FAILED)
        category: 에러 카테고리 (domain, infrastructure, presentation)
        status_code: HTTP 상태 코드 (API 에러 시)
        details: 추가 에러 정보
        original_exception: 원본 예외 (래핑하는 경우)
    """

    def __init__(
        self,
        message: str,
        code: str,
        category: ErrorCategory,
        status_code: int = 500,
        details: dict[str, Any] | None = None,
        original_exception: Exception | None = None,
    ) -> None:
        """
        BaseError 초기화

        Args:
            message: 에러 메시지
            code: 에러 코드
            category: 에러 카테고리
            status_code: HTTP 상태 코드
            details: 추가 에러 정보
            original_exception: 원본 예외
        """
        super().__init__(message)
        self.message = message
        self.code = code
        self.category = category
        self.status_code = status_code
        self.details = details or {}
        self.original_exception = original_exception

    def to_dict(self) -> dict[str, Any]:
        """에러를 딕셔너리로 변환 (API 응답용)"""
        result = {
            "error": True,
            "code": self.code,
            "message": self.message,
            "category": self.category.value,
        }

        if self.details:
            result["details"] = self.details

        return result

    def __str__(self) -> str:
        """문자열 표현"""
        return f"[{self.code}] {self.message}"

    def __repr__(self) -> str:
        """개발자용 표현"""
        return (
            f"{self.__class__.__name__}("
            f"code={self.code!r}, "
            f"message={self.message!r}, "
            f"category={self.category.value!r})"
        )
