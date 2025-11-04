"""
웹 프레젠테이션 레이어

FastAPI 기반 웹 UI를 제공합니다.
"""

# FastAPI는 선택적 의존성 (웹 서버 실행 시 필요)
try:
    from src.presentation.web.app import app

    __all__ = ["app"]
except ImportError:
    # FastAPI가 설치되지 않은 경우 (테스트 환경 등)
    __all__ = []
