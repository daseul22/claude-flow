"""
워크플로우 자동 설계 API

workflow_designer Worker를 사용하여 요구사항으로부터 워크플로우를 자동 설계합니다.
"""

import asyncio
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, AsyncIterator

from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse

from src.infrastructure.config import JsonConfigLoader, get_project_root
from src.infrastructure.logging import get_logger
from src.infrastructure.claude.worker_client import WorkerAgent
from src.domain.models import AgentConfig
from src.presentation.web.schemas.request import WorkflowDesignRequest

logger = get_logger(__name__)
router = APIRouter()

# 활성 설계 세션 관리 (메모리)
_active_design_sessions: Dict[str, dict] = {}


def get_design_session_dir(session_id: str) -> Path:
    """설계 세션 디렉토리 경로 반환"""
    from src.infrastructure.config import get_data_dir

    data_dir = get_data_dir()
    session_dir = data_dir / "workflow_design_sessions" / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    return session_dir


def save_design_session_state(session_id: str, state: dict):
    """설계 세션 상태를 파일에 저장"""
    session_dir = get_design_session_dir(session_id)
    state_file = session_dir / "state.json"
    with open(state_file, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def load_design_session_state(session_id: str) -> dict | None:
    """설계 세션 상태를 파일에서 로드"""
    session_dir = get_design_session_dir(session_id)
    state_file = session_dir / "state.json"
    if state_file.exists():
        with open(state_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def append_design_session_output(session_id: str, chunk: str):
    """설계 세션 출력을 파일에 추가"""
    session_dir = get_design_session_dir(session_id)
    output_file = session_dir / "output.txt"
    with open(output_file, "a", encoding="utf-8") as f:
        f.write(chunk)


def read_design_session_output(session_id: str) -> str:
    """설계 세션 출력을 파일에서 읽기"""
    session_dir = get_design_session_dir(session_id)
    output_file = session_dir / "output.txt"
    if output_file.exists():
        with open(output_file, "r", encoding="utf-8") as f:
            return f.read()
    return ""


def get_workflow_designer_config() -> AgentConfig:
    """
    workflow_designer 설정 로드

    Returns:
        AgentConfig: workflow_designer 설정

    Raises:
        HTTPException: 설정 로드 실패 시
    """
    try:
        config_loader = JsonConfigLoader(get_project_root())
        agent_configs = config_loader.load_agent_configs()

        config = next(
            (cfg for cfg in agent_configs if cfg.name == "workflow_designer"),
            None,
        )

        if not config:
            raise HTTPException(
                status_code=500,
                detail="workflow_designer 설정을 찾을 수 없습니다",
            )

        return config

    except Exception as e:
        logger.error(f"workflow_designer 설정 로드 실패: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"워크플로우 디자이너 설정 로드 실패: {str(e)}",
        )


async def _execute_workflow_designer(
    requirements: str,
    session_id: str,
    current_workflow: Dict | None = None,
    mode: str = "create",
    project_path: str | None = None,
) -> AsyncIterator[str]:
    """
    workflow_designer 실행 (스트리밍)

    Args:
        requirements: 워크플로우 요구사항
        session_id: 세션 ID
        current_workflow: 현재 워크플로우 (개선 모드일 때)
        mode: 워크플로우 설계 모드 (create | improve)
        project_path: 프로젝트 경로 (워크플로우 설계 시 분석할 프로젝트 디렉토리)

    Yields:
        str: Worker 출력 청크
    """
    try:
        config = get_workflow_designer_config()

        # 프로젝트 디렉토리 결정
        # 1. 사용자가 지정한 프로젝트 경로 (우선)
        # 2. claude-flow 프로젝트 루트 (폴백)
        if project_path:
            working_dir = project_path
            logger.info(f"[{session_id}] 사용자 프로젝트 디렉토리 사용: {working_dir}")
        else:
            working_dir = str(get_project_root())
            logger.warning(
                f"[{session_id}] project_path가 없어 claude-flow 프로젝트 디렉토리 사용: {working_dir}"
            )

        worker = WorkerAgent(config=config, project_dir=working_dir)

        # 개선 모드일 때 프롬프트에 현재 워크플로우 포함
        if mode == "improve" and current_workflow:
            task_prompt = f"""---CURRENT_WORKFLOW_START---
{json.dumps(current_workflow, ensure_ascii=False, indent=2)}
---CURRENT_WORKFLOW_END---

수정 요구사항:
{requirements}"""
            logger.info(
                f"[{session_id}] workflow_designer 실행 시작 (모드: improve, "
                f"현재 노드 수: {len(current_workflow.get('nodes', []))}, "
                f"working_dir: {working_dir})"
            )
        else:
            task_prompt = requirements
            logger.info(
                f"[{session_id}] workflow_designer 실행 시작 (모드: create, "
                f"working_dir: {working_dir})"
            )

        async for chunk in worker.execute_task(task_prompt):
            yield chunk

        logger.info(f"[{session_id}] workflow_designer 실행 완료")

    except Exception as e:
        error_msg = f"워크플로우 디자이너 실행 실패: {str(e)}"
        logger.error(f"[{session_id}] {error_msg}", exc_info=True)
        raise


@router.post("/design")
async def design_workflow(request: WorkflowDesignRequest):
    """
    워크플로우 설계 (SSE 스트리밍)

    workflow_designer를 실행하여 요구사항으로부터 워크플로우를 자동 설계합니다.
    세션 ID로 재접속하면 이전 출력부터 이어서 볼 수 있습니다.

    Args:
        request: 워크플로우 설계 요청 (requirements, session_id)

    Returns:
        EventSourceResponse: SSE 스트리밍 응답

    Example:
        POST /api/workflows/design
        Body: {
            "requirements": "코드 리뷰 후 테스트 실행하는 워크플로우",
            "session_id": "optional-session-id"
        }

    SSE Response:
        data: 생성된 워크플로우 JSON 청크 1
        data: 생성된 워크플로우 JSON 청크 2
        ...
        data: [DONE]
    """
    session_id = request.session_id or str(uuid.uuid4())

    # 기존 세션 확인
    existing_state = load_design_session_state(session_id)
    is_reconnect = existing_state is not None and existing_state.get("status") in [
        "generating",
        "completed",
    ]

    if is_reconnect:
        logger.info(f"[{session_id}] 설계 세션 재접속 (상태: {existing_state.get('status')})")
    else:
        logger.info(f"[{session_id}] 워크플로우 설계 요청 " f"(요구사항 길이: {len(request.requirements)})")
        # 새 세션 상태 저장
        save_design_session_state(
            session_id,
            {
                "session_id": session_id,
                "status": "generating",
                "requirements": request.requirements,
                "created_at": datetime.now().isoformat(),
            },
        )

    async def event_generator():
        try:
            # 재접속: 이전 출력 먼저 스트리밍
            if is_reconnect:
                previous_output = read_design_session_output(session_id)
                if previous_output:
                    logger.info(f"[{session_id}] 이전 출력 복원 (길이: {len(previous_output)})")
                    yield {"data": previous_output}

                # 이미 완료된 세션이면 [DONE] 전송
                if existing_state.get("status") == "completed":
                    logger.info(f"[{session_id}] 세션 이미 완료됨")
                    yield {"data": "[DONE]"}
                    return

            # 이미 실행 중인 세션이면 대기만 (중복 실행 방지)
            if session_id in _active_design_sessions:
                logger.info(f"[{session_id}] 이미 실행 중인 세션 - 출력 대기")
                # 실행 중인 세션의 새 출력을 기다림 (최대 5분)
                timeout = 300  # 5분
                start_time = asyncio.get_event_loop().time()
                while session_id in _active_design_sessions:
                    # 타임아웃 체크 (무한 대기 방지)
                    if asyncio.get_event_loop().time() - start_time > timeout:
                        error_msg = f"세션 대기 타임아웃 ({timeout}초)"
                        logger.error(f"[{session_id}] {error_msg}")
                        yield {"data": json.dumps({"error": error_msg})}
                        yield {"data": "[DONE]"}
                        return
                    await asyncio.sleep(0.5)
                # 완료 후 남은 출력 전송
                yield {"data": "[DONE]"}
                return

            # 새로운 실행: 워커 실행
            _active_design_sessions[session_id] = {"started_at": datetime.now().isoformat()}

            chunk_count = 0
            accumulated_output = ""

            async for chunk in _execute_workflow_designer(
                request.requirements,
                session_id,
                request.current_workflow,
                request.mode,
                request.project_path,
            ):
                chunk_count += 1
                accumulated_output += chunk
                append_design_session_output(session_id, chunk)  # 파일에 저장
                logger.debug(f"[{session_id}] SSE Chunk #{chunk_count}: len={len(chunk)}")
                yield {"data": chunk}

            logger.info(f"[{session_id}] SSE 스트림 완료 (총 {chunk_count}개 청크)")
            logger.info(f"[{session_id}] 📊 전체 출력 길이: {len(accumulated_output)} characters")

            # 세션 완료 상태 저장
            save_design_session_state(
                session_id,
                {
                    "session_id": session_id,
                    "status": "completed",
                    "requirements": request.requirements,
                    "created_at": (
                        existing_state.get("created_at")
                        if existing_state
                        else datetime.now().isoformat()
                    ),
                    "completed_at": datetime.now().isoformat(),
                },
            )

            yield {"data": "[DONE]"}

        except Exception as e:
            error_msg = f"ERROR: {str(e)}"
            logger.error(f"[{session_id}] {error_msg}", exc_info=True)

            # 에러 상태 저장
            save_design_session_state(
                session_id,
                {
                    "session_id": session_id,
                    "status": "error",
                    "error": str(e),
                    "created_at": (
                        existing_state.get("created_at")
                        if existing_state
                        else datetime.now().isoformat()
                    ),
                },
            )

            yield {"data": error_msg}
            yield {"data": "[DONE]"}

        finally:
            # 활성 세션에서 제거
            if session_id in _active_design_sessions:
                del _active_design_sessions[session_id]

    return EventSourceResponse(
        event_generator(),
        headers={
            "X-Accel-Buffering": "no",
            "Cache-Control": "no-cache",
            "X-Session-Id": session_id,  # 세션 ID 헤더로 반환
        },
    )
