"""FastAPI 앱 - Claude Flow 워크플로우 캔버스"""
# 표준 라이브러리
import os
from contextlib import asynccontextmanager
from pathlib import Path

# 서드파티
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# 로컬
from src.infrastructure.logging import configure_structlog, get_logger
from src.presentation.web.routers import (
    agents_router,
    health_router,
    workflows_router,
    projects_router,
    filesystem_router,
    templates_router,
    custom_workers_router,
)

# .env 파일 로드 (여러 경로 시도)
# 1. 현재 작업 디렉토리 (사용자가 실행한 위치)
# 2. 홈 디렉토리의 .claude-flow/.env
# 3. 프로젝트 루트 (개발 모드)
env_paths = [
    Path.cwd() / ".env",  # 현재 디렉토리
    Path.home() / ".claude-flow" / ".env",  # 홈 디렉토리
    Path(__file__).parent.parent.parent.parent / ".env",  # 프로젝트 루트 (개발)
]

env_loaded = False
for env_path in env_paths:
    if env_path.exists():
        load_dotenv(env_path)
        env_loaded = True
        break

if not env_loaded:
    # .env 파일이 없으면 시스템 환경변수만 사용
    load_dotenv()

# 로그 시스템 초기화 (웹 앱 시작 시 필수)
configure_structlog(
    log_dir=None,  # 기본 디렉토리 사용
    log_level=os.getenv("LOG_LEVEL", "INFO"),
    enable_json=False  # 콘솔 로그는 읽기 쉬운 형식 사용
)

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI Lifespan Context Manager (권장 방식)

    startup 및 shutdown 이벤트를 처리합니다.
    """
    # Startup
    logger.info(f"🚀 Claude Flow 시작 (React: {(Path(__file__).parent / 'static-react').exists()})")

    # 환경변수 확인 (경고만 표시, 앱은 시작)
    if not os.getenv("CLAUDE_CODE_OAUTH_TOKEN"):
        logger.warning("⚠️  CLAUDE_CODE_OAUTH_TOKEN 환경변수가 설정되지 않았습니다")
        logger.warning("   Worker Agent 실행 시 오류가 발생할 수 있습니다")
    else:
        logger.info("✓ CLAUDE_CODE_OAUTH_TOKEN 확인됨")

    yield  # 애플리케이션 실행 중

    # Shutdown
    logger.info("🛑 Claude Flow 종료 중...")
    # 필요한 경우 리소스 정리 작업 추가 (DB 연결 종료, 캐시 정리 등)
    logger.info("✅ Claude Flow 종료 완료")


app = FastAPI(title="Claude Flow", version="4.0.0", lifespan=lifespan)

origins = os.getenv("WEB_ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

app.include_router(health_router)
app.include_router(agents_router)
app.include_router(workflows_router)
app.include_router(projects_router)
app.include_router(filesystem_router)
app.include_router(templates_router)
app.include_router(custom_workers_router)

REACT_BUILD_DIR = Path(__file__).parent / "static-react"

if REACT_BUILD_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(REACT_BUILD_DIR / "assets")), name="assets")
    @app.get("/")
    async def root():
        return FileResponse(str(REACT_BUILD_DIR / "index.html"))
else:
    @app.get("/")
    async def root():
        return {"error": "React 빌드 필요", "solution": "cd src/presentation/web/frontend && npm run build"}


def main():
    import uvicorn

    # .env 파일 다시 로드 (main 함수에서도)
    # 여러 경로 시도
    env_paths = [
        Path.cwd() / ".env",  # 현재 디렉토리
        Path.home() / ".claude-flow" / ".env",  # 홈 디렉토리
        Path(__file__).parent.parent.parent.parent / ".env",  # 프로젝트 루트 (개발)
    ]

    for env_path in env_paths:
        if env_path.exists():
            load_dotenv(env_path)
            break
    else:
        load_dotenv()

    host = os.getenv("WEB_HOST", "127.0.0.1")
    port = int(os.getenv("WEB_PORT", "8000"))

    print("╔════════════════════════════════════════════╗")
    print("║   Claude Flow Workflow Canvas              ║")
    print("╚════════════════════════════════════════════╝")
    print()
    print(f"🚀 웹 서버: http://{host}:{port}")

    # 환경변수 확인
    if not os.getenv("CLAUDE_CODE_OAUTH_TOKEN"):
        print()
        print("⚠️  경고: CLAUDE_CODE_OAUTH_TOKEN 환경변수가 설정되지 않았습니다")
        print("   .env 파일을 확인하거나 다음과 같이 설정하세요:")
        print("   export CLAUDE_CODE_OAUTH_TOKEN='your-token'")
    else:
        print("✓ CLAUDE_CODE_OAUTH_TOKEN 확인됨")

    print()
    print("   Ctrl+C로 종료")
    print()

    uvicorn.run("src.presentation.web.app:app", host=host, port=port, log_level="info")

if __name__ == "__main__":
    main()
