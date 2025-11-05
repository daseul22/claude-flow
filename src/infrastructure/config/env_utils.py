"""환경변수 파싱 유틸리티

환경변수를 타입 안전하게 파싱하는 헬퍼 함수들을 제공합니다.
"""

import os
from pathlib import Path
from typing import Optional


def parse_bool_env(var_name: str, default: bool = False) -> bool:
    """
    환경변수를 bool로 파싱

    다양한 형식을 지원합니다:
    - True: "true", "True", "TRUE", "1", "yes", "YES", "on", "ON"
    - False: "false", "False", "FALSE", "0", "no", "NO", "off", "OFF"
    - 기타: default 값 반환

    Args:
        var_name: 환경변수 이름
        default: 기본값 (환경변수가 없거나 파싱 실패 시)

    Returns:
        파싱된 bool 값

    Examples:
        >>> os.environ["MY_FLAG"] = "true"
        >>> parse_bool_env("MY_FLAG")
        True

        >>> os.environ["MY_FLAG"] = "FALSE"
        >>> parse_bool_env("MY_FLAG")
        False

        >>> parse_bool_env("NOT_SET", default=True)
        True
    """
    value = os.getenv(var_name, "").lower().strip()

    if value in ("true", "1", "yes", "on"):
        return True
    elif value in ("false", "0", "no", "off"):
        return False

    return default


def parse_int_env(var_name: str, default: int = 0) -> int:
    """
    환경변수를 int로 파싱

    Args:
        var_name: 환경변수 이름
        default: 기본값 (환경변수가 없거나 파싱 실패 시)

    Returns:
        파싱된 int 값

    Examples:
        >>> os.environ["PORT"] = "8080"
        >>> parse_int_env("PORT")
        8080

        >>> parse_int_env("NOT_SET", default=3000)
        3000
    """
    value = os.getenv(var_name, "").strip()

    if not value:
        return default

    try:
        return int(value)
    except ValueError:
        return default


def parse_float_env(var_name: str, default: float = 0.0) -> float:
    """
    환경변수를 float로 파싱

    Args:
        var_name: 환경변수 이름
        default: 기본값 (환경변수가 없거나 파싱 실패 시)

    Returns:
        파싱된 float 값

    Examples:
        >>> os.environ["TIMEOUT"] = "30.5"
        >>> parse_float_env("TIMEOUT")
        30.5

        >>> parse_float_env("NOT_SET", default=60.0)
        60.0
    """
    value = os.getenv(var_name, "").strip()

    if not value:
        return default

    try:
        return float(value)
    except ValueError:
        return default


def parse_str_env(var_name: str, default: str = "") -> str:
    """
    환경변수를 str로 파싱 (공백 제거)

    Args:
        var_name: 환경변수 이름
        default: 기본값 (환경변수가 없을 때)

    Returns:
        파싱된 str 값

    Examples:
        >>> os.environ["API_KEY"] = "  my-secret-key  "
        >>> parse_str_env("API_KEY")
        'my-secret-key'

        >>> parse_str_env("NOT_SET", default="default-key")
        'default-key'
    """
    return os.getenv(var_name, default).strip()


def validate_required_env_vars(*var_names: str) -> None:
    """
    필수 환경변수가 설정되어 있는지 검증합니다.

    누락된 환경변수가 있으면 ValueError를 발생시킵니다.
    에러 메시지에는 누락된 변수 목록과 설정 방법이 포함됩니다.

    Args:
        *var_names: 검증할 환경변수 이름들

    Raises:
        ValueError: 하나 이상의 필수 환경변수가 설정되지 않은 경우

    Examples:
        >>> os.environ["REQUIRED_VAR"] = "value"
        >>> validate_required_env_vars("REQUIRED_VAR")  # 성공
        >>> validate_required_env_vars("NOT_SET")  # ValueError 발생

        >>> # 여러 변수 동시 검증
        >>> validate_required_env_vars("VAR1", "VAR2", "VAR3")
    """
    missing_vars = [var for var in var_names if not os.getenv(var)]

    if missing_vars:
        error_msg = (
            f"필수 환경변수가 설정되지 않았습니다: {', '.join(missing_vars)}\n\n"
            "다음 방법 중 하나로 설정하세요:\n"
            "  1. .env 파일에 추가:\n"
        )
        for var in missing_vars:
            error_msg += f"     {var}=your-value-here\n"
        error_msg += "\n  2. 환경변수로 직접 설정:\n"
        for var in missing_vars:
            error_msg += f"     export {var}='your-value-here'\n"

        raise ValueError(error_msg)
