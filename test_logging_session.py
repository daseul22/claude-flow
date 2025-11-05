#!/usr/bin/env python3
"""
로그 및 세션 저장 테스트

워크플로우 실행 없이 로그/세션 디렉토리 생성 및 저장을 테스트합니다.
"""

import asyncio
import json
from pathlib import Path
from src.infrastructure.logging import configure_structlog, add_session_file_handlers, get_logger
from src.presentation.web.services.workflow_session_store import WorkflowSessionStore, WorkflowSession
from src.presentation.web.schemas.workflow import Workflow

# 로깅 초기화
configure_structlog(log_level="INFO", enable_json=False)
logger = get_logger(__name__)


async def test_logging_and_session():
    """로그 및 세션 저장 테스트"""

    project_path = "/Users/simdaseul/dallem-repo/claude-flow-web"
    project_name = Path(project_path).name
    session_id = "test-session-12345"

    print(f"프로젝트: {project_path}")
    print(f"프로젝트 이름: {project_name}")
    print(f"테스트 세션 ID: {session_id}\n")

    # 1. 로그 디렉토리 확인
    print("=" * 60)
    print("1. 로그 디렉토리 테스트")
    print("=" * 60)

    logs_dir = Path.home() / ".claude-flow" / project_name / "logs"
    print(f"예상 로그 경로: {logs_dir}")

    # 로그 핸들러 추가
    add_session_file_handlers(session_id, project_path)

    # 로그 작성
    logger.info("테스트 로그 메시지 #1")
    logger.warning("테스트 경고 메시지 #2")
    logger.error("테스트 에러 메시지 #3")

    # 디렉토리 확인
    if logs_dir.exists():
        print(f"✅ 로그 디렉토리 생성 확인: {logs_dir}")

        # 로그 파일 목록
        log_files = list(logs_dir.rglob("*.log"))
        print(f"\n생성된 로그 파일 ({len(log_files)}개):")
        for log_file in log_files:
            rel_path = log_file.relative_to(logs_dir)
            size = log_file.stat().st_size
            print(f"  - {rel_path} ({size} bytes)")
    else:
        print(f"❌ 로그 디렉토리 미생성: {logs_dir}")

    # 2. 세션 디렉토리 확인
    print("\n" + "=" * 60)
    print("2. 세션 디렉토리 테스트")
    print("=" * 60)

    sessions_dir = Path.home() / ".claude-flow" / project_name / "web-sessions"
    print(f"예상 세션 경로: {sessions_dir}")

    # 세션 저장소 생성
    session_store = WorkflowSessionStore(sessions_dir)

    # 테스트 워크플로우 생성
    test_workflow = Workflow(
        id=None,
        name="테스트 워크플로우",
        description="로그/세션 저장 테스트용",
        nodes=[],
        edges=[],
        metadata=None
    )

    # 세션 생성
    session = await session_store.create_session(
        session_id=session_id,
        workflow=test_workflow,
        initial_input="테스트 입력",
        project_path=project_path
    )

    # 세션에 로그 추가
    from src.presentation.web.schemas.workflow import WorkflowNodeExecutionEvent

    test_event = WorkflowNodeExecutionEvent(
        event_type="node_start",
        node_id="test-node-1",
        timestamp="2025-11-05T22:00:00Z",
        data={"input": "테스트 입력"}
    )

    await session_store.append_log(session_id, test_event)

    # 디렉토리 확인
    if sessions_dir.exists():
        print(f"✅ 세션 디렉토리 생성 확인: {sessions_dir}")

        # 세션 파일 목록
        session_files = list(sessions_dir.glob("*.json"))
        print(f"\n생성된 세션 파일 ({len(session_files)}개):")
        for session_file in session_files:
            size = session_file.stat().st_size
            print(f"  - {session_file.name} ({size} bytes)")

            # 내용 확인
            with open(session_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                print(f"    → 상태: {data.get('status')}")
                print(f"    → 로그 수: {len(data.get('logs', []))}")
    else:
        print(f"❌ 세션 디렉토리 미생성: {sessions_dir}")

    # 3. 최종 요약
    print("\n" + "=" * 60)
    print("3. 테스트 결과 요약")
    print("=" * 60)

    logs_ok = logs_dir.exists()
    sessions_ok = sessions_dir.exists()

    print(f"로그 저장: {'✅ 성공' if logs_ok else '❌ 실패'}")
    print(f"세션 저장: {'✅ 성공' if sessions_ok else '❌ 실패'}")

    if logs_ok and sessions_ok:
        print("\n🎉 모든 테스트 통과!")
        print("\n워크플로우 실행 시 다음 경로에 저장됩니다:")
        print(f"  - 로그: {logs_dir}")
        print(f"  - 세션: {sessions_dir}")
    else:
        print("\n⚠️  일부 테스트 실패. 코드를 확인하세요.")

    # 정리
    print(f"\n정리 명령어:")
    print(f"  rm -rf ~/.claude-flow/{project_name}")


if __name__ == "__main__":
    asyncio.run(test_logging_and_session())
