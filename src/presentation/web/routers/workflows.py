"""
워크플로우 API 라우터

워크플로우 저장, 조회, 실행을 위한 엔드포인트를 제공합니다.
"""

import asyncio
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Any
from functools import lru_cache

from fastapi import APIRouter, HTTPException, Depends, Body
from sse_starlette.sse import EventSourceResponse

from src.infrastructure.config import JsonConfigLoader, get_project_root
from src.infrastructure.logging import get_logger
from src.presentation.web.schemas.workflow import (
    Workflow,
    WorkflowExecuteRequest,
    WorkflowSaveRequest,
    WorkflowSaveResponse,
    WorkflowListResponse,
    WorkflowValidateResponse,
    WorkflowValidationError,
)
from src.presentation.web.schemas.request import WorkflowDesignRequest
from src.infrastructure.claude.worker_client import WorkerAgent
from src.domain.models import AgentConfig
from typing import AsyncIterator
from src.presentation.web.services.workflow_executor import WorkflowExecutor
from src.presentation.web.services.workflow_validator import WorkflowValidator
from src.presentation.web.services.workflow_session_store import get_session_store
from src.presentation.web.services.background_workflow_manager import (
    get_background_workflow_manager,
    BackgroundWorkflowManager,
)
from src.presentation.web.config import ProjectConfig, WorkflowConfig

logger = get_logger(__name__)
router = APIRouter(prefix="/api/workflows", tags=["workflows"])


# 워크플로우 저장 디렉토리
WORKFLOWS_DIR = ProjectConfig.WORKFLOWS_DIR
WORKFLOWS_DIR.mkdir(parents=True, exist_ok=True)


@lru_cache()
def get_config_loader() -> JsonConfigLoader:
    """
    JsonConfigLoader 싱글톤 인스턴스 반환 (FastAPI Depends + lru_cache)

    Returns:
        JsonConfigLoader: 스레드 안전한 싱글톤 인스턴스
    """
    project_root = get_project_root()
    return JsonConfigLoader(project_root)


# 프로젝트별 WorkflowExecutor 캐시
_executors: Dict[str, WorkflowExecutor] = {}


def get_workflow_executor(
    config_loader: JsonConfigLoader = Depends(get_config_loader)
) -> WorkflowExecutor:
    """
    WorkflowExecutor 인스턴스 반환 (프로젝트별 캐싱)

    Args:
        config_loader: ConfigLoader 의존성 주입

    Returns:
        WorkflowExecutor: 워크플로우 실행 엔진
    """
    # projects 라우터에서 현재 프로젝트 경로 가져오기
    from src.presentation.web.routers.projects import _current_project_path

    # 캐시 키 생성
    cache_key = _current_project_path or "~default"

    # 캐시에서 인스턴스 확인
    if cache_key not in _executors:
        logger.info(f"새 WorkflowExecutor 생성 (프로젝트: {cache_key})")
        _executors[cache_key] = WorkflowExecutor(config_loader, _current_project_path)

    return _executors[cache_key]


def get_background_manager(
    executor: WorkflowExecutor = Depends(get_workflow_executor)
) -> BackgroundWorkflowManager:
    """
    BackgroundWorkflowManager 인스턴스 반환 (프로젝트별 캐싱)

    Args:
        executor: WorkflowExecutor 의존성 주입

    Returns:
        BackgroundWorkflowManager: 백그라운드 워크플로우 관리자
    """
    # projects 라우터에서 현재 프로젝트 경로 가져오기
    from src.presentation.web.routers.projects import _current_project_path
    return get_background_workflow_manager(executor, project_path=_current_project_path)


@router.post("/execute")
async def execute_workflow(
    request: WorkflowExecuteRequest,
    bg_manager: BackgroundWorkflowManager = Depends(get_background_manager),
):
    """
    워크플로우 실행 (Server-Sent Events + 백그라운드 실행)

    워크플로우를 백그라운드 Task로 실행하므로, SSE 연결이 끊어져도 계속 실행됩니다.
    새로고침 후 동일한 session_id로 재접속하면 진행 상황을 이어받을 수 있습니다.

    Args:
        request: 워크플로우 실행 요청
        bg_manager: BackgroundWorkflowManager 의존성 주입

    Returns:
        EventSourceResponse: SSE 스트리밍 응답

    Example:
        POST /api/workflows/execute
        Body: {
            "workflow": {
                "name": "코드 리뷰 워크플로우",
                "nodes": [...],
                "edges": [...]
            },
            "initial_input": "main.py 파일 리뷰",
            "session_id": "optional-session-id"
        }

    SSE Response:
        data: {"event_type": "node_start", "node_id": "1", "data": {...}}
        data: {"event_type": "node_output", "node_id": "1", "data": {"chunk": "..."}}
        data: {"event_type": "node_complete", "node_id": "1", "data": {...}}
        ...
        data: {"event_type": "workflow_complete", "node_id": "", "data": {...}}
        data: [DONE]
    """
    # 세션 ID 생성 (미제공 시)
    session_id = request.session_id or str(uuid.uuid4())

    logger.info(
        f"[{session_id}] 워크플로우 실행 요청: {request.workflow.name} "
        f"(노드: {len(request.workflow.nodes)})"
    )

    # 워크플로우 검증
    if not request.workflow.nodes:
        raise HTTPException(
            status_code=400,
            detail="워크플로우에 노드가 없습니다"
        )

    # 현재 프로젝트 경로 가져오기
    from src.presentation.web.routers.projects import _current_project_path

    # 세션 저장소 가져오기 (현재 프로젝트 경로 기반)
    session_store = get_session_store(project_path=_current_project_path)

    # 기존 세션 확인 (재접속인 경우)
    existing_session = await session_store.get_session(session_id)

    if existing_session is None:
        # 새 세션 생성 (프로젝트 경로 포함)
        await session_store.create_session(
            session_id=session_id,
            workflow=request.workflow,
            initial_input=request.initial_input,
            project_path=_current_project_path,
        )

        # 백그라운드 워크플로우 시작 (프로젝트 경로, start_node_id 전달)
        try:
            logger.info(
                f"[{session_id}] [DEBUG] 워크플로우 실행 시작:\n"
                f"  - executor 인스턴스: {id(bg_manager.executor)}\n"
                f"  - 프로젝트 경로: {_current_project_path}"
            )
            await bg_manager.start_workflow(
                session_id=session_id,
                workflow=request.workflow,
                initial_input=request.initial_input,
                project_path=_current_project_path,
                start_node_id=request.start_node_id,
            )
            logger.info(f"[{session_id}] 백그라운드 워크플로우 시작 완료")
        except ValueError as e:
            # 이미 실행 중인 경우 (정상적인 재접속)
            logger.info(f"[{session_id}] 기존 워크플로우에 재접속: {e}")
    elif existing_session.status in ["completed", "error", "cancelled"]:
        # 완료된 세션은 삭제하고 새 세션 생성
        logger.info(
            f"[{session_id}] 완료된 세션 삭제 후 재생성 "
            f"(이전 상태: {existing_session.status})"
        )
        await session_store.delete_session(session_id)

        # 새 세션 생성
        await session_store.create_session(
            session_id=session_id,
            workflow=request.workflow,
            initial_input=request.initial_input,
            project_path=_current_project_path,
        )

        # 백그라운드 워크플로우 시작 (프로젝트 경로, start_node_id 전달)
        await bg_manager.start_workflow(
            session_id=session_id,
            workflow=request.workflow,
            initial_input=request.initial_input,
            project_path=_current_project_path,
            start_node_id=request.start_node_id,
        )
        logger.info(f"[{session_id}] 새 워크플로우 시작 완료")
    else:
        # 실행 중인 세션에 재접속
        logger.info(
            f"[{session_id}] 실행 중인 세션에 재접속 "
            f"(상태: {existing_session.status})"
        )

    # SSE 스트리밍 함수
    async def event_generator():
        try:
            # 시작 인덱스 결정 (재접속 시 중복 방지)
            start_from_index = 0
            if request.last_event_index is not None:
                start_from_index = request.last_event_index + 1  # 다음 이벤트부터

            logger.info(
                f"[{session_id}] SSE 스트리밍 시작 "
                f"(start_from_index={start_from_index})"
            )

            event_count = 0

            # 백그라운드 Task에서 이벤트 스트리밍 (start_from_index 전달)
            async for event in bg_manager.stream_events(
                session_id,
                start_from_index=start_from_index
            ):
                event_count += 1

                # 이벤트를 JSON으로 직렬화
                event_data = event.model_dump()

                logger.info(
                    f"[{session_id}] 📤 SSE Event #{start_from_index + event_count}: "
                    f"{event.event_type} (node: {event.node_id})"
                )
                logger.debug(f"[{session_id}] Event data: {event_data}")

                # JSON 문자열 생성
                json_str = json.dumps(event_data, ensure_ascii=False)
                logger.debug(f"[{session_id}] JSON 직렬화 완료: {json_str[:100]}...")

                # SSE 형식으로 전송
                sse_message = {"data": json_str}
                logger.debug(f"[{session_id}] SSE 메시지 전송: {sse_message}")
                yield sse_message

            # 완료 시그널
            logger.info(
                f"[{session_id}] ✅ SSE 스트림 완료 "
                f"(전송: {event_count}개, 총 누적: {start_from_index + event_count}개)"
            )
            logger.info(f"[{session_id}] 📤 [DONE] 시그널 전송")
            yield {"data": "[DONE]"}

        except asyncio.CancelledError:
            # 클라이언트가 연결을 끊은 경우 (정상적인 중단)
            # 백그라운드 Task는 계속 실행됨!
            logger.info(
                f"[{session_id}] ⏹️ 클라이언트가 연결을 끊었습니다 "
                f"(워크플로우는 백그라운드에서 계속 실행 중)"
            )

            # [DONE] 시그널을 보내지 않음 (이미 연결이 끊어짐)
            raise  # CancelledError는 재발생시켜 정리 작업이 이루어지도록 함

        except Exception as e:
            error_msg = f"ERROR: {str(e)}"
            logger.error(f"[{session_id}] {error_msg}", exc_info=True)

            # 에러 메시지 전송
            yield {"data": error_msg}
            yield {"data": "[DONE]"}

    # EventSourceResponse로 SSE 스트리밍 반환
    return EventSourceResponse(
        event_generator(),
        headers={
            "X-Accel-Buffering": "no",
            "Cache-Control": "no-cache",
            "X-Session-ID": session_id,  # 세션 ID를 헤더로 전달
        }
    )


@router.post("", response_model=WorkflowSaveResponse)
async def save_workflow(request: WorkflowSaveRequest) -> WorkflowSaveResponse:
    """
    워크플로우 저장

    Args:
        request: 워크플로우 저장 요청

    Returns:
        WorkflowSaveResponse: 저장된 워크플로우 ID

    Example:
        POST /api/workflows
        Body: {
            "workflow": {
                "name": "코드 리뷰 워크플로우",
                "description": "코드 작성 → 리뷰 → 커밋",
                "nodes": [...],
                "edges": [...]
            }
        }

        Response: {
            "workflow_id": "uuid-v4",
            "message": "워크플로우가 저장되었습니다"
        }
    """
    try:
        workflow = request.workflow

        # 워크플로우 ID 생성 (미제공 시)
        workflow_id = workflow.id or str(uuid.uuid4())
        workflow.id = workflow_id

        # 파일로 저장
        workflow_path = WORKFLOWS_DIR / f"{workflow_id}.json"
        with open(workflow_path, "w", encoding="utf-8") as f:
            json.dump(
                workflow.model_dump(),
                f,
                ensure_ascii=False,
                indent=2
            )

        logger.info(f"워크플로우 저장: {workflow.name} (ID: {workflow_id})")

        return WorkflowSaveResponse(
            workflow_id=workflow_id,
            message="워크플로우가 저장되었습니다"
        )

    except Exception as e:
        logger.error(f"워크플로우 저장 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"워크플로우 저장 실패: {str(e)}"
        )


@router.get("", response_model=WorkflowListResponse)
async def list_workflows() -> WorkflowListResponse:
    """
    워크플로우 목록 조회

    Returns:
        WorkflowListResponse: 워크플로우 목록 (메타데이터만)

    Example:
        GET /api/workflows
        Response: {
            "workflows": [
                {
                    "id": "uuid-v4",
                    "name": "코드 리뷰 워크플로우",
                    "description": "코드 작성 → 리뷰 → 커밋",
                    "node_count": 3,
                    "edge_count": 2
                },
                ...
            ]
        }
    """
    try:
        workflows = []

        for workflow_path in WORKFLOWS_DIR.glob("*.json"):
            try:
                with open(workflow_path, "r", encoding="utf-8") as f:
                    workflow_data = json.load(f)

                # 메타데이터만 추출
                workflows.append({
                    "id": workflow_data.get("id"),
                    "name": workflow_data.get("name"),
                    "description": workflow_data.get("description"),
                    "node_count": len(workflow_data.get("nodes", [])),
                    "edge_count": len(workflow_data.get("edges", [])),
                })

            except Exception as e:
                logger.warning(f"워크플로우 로드 실패: {workflow_path} - {e}")
                continue

        logger.info(f"워크플로우 목록 조회: {len(workflows)}개")

        return WorkflowListResponse(workflows=workflows)

    except Exception as e:
        logger.error(f"워크플로우 목록 조회 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"워크플로우 목록 조회 실패: {str(e)}"
        )


@router.get("/{workflow_id}", response_model=Workflow)
async def get_workflow(workflow_id: str) -> Workflow:
    """
    워크플로우 조회 (단일)

    Args:
        workflow_id: 워크플로우 ID

    Returns:
        Workflow: 워크플로우 전체 데이터

    Example:
        GET /api/workflows/{workflow_id}
        Response: {
            "id": "uuid-v4",
            "name": "코드 리뷰 워크플로우",
            "description": "...",
            "nodes": [...],
            "edges": [...]
        }
    """
    try:
        workflow_path = WORKFLOWS_DIR / f"{workflow_id}.json"

        if not workflow_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"워크플로우를 찾을 수 없습니다: {workflow_id}"
            )

        with open(workflow_path, "r", encoding="utf-8") as f:
            workflow_data = json.load(f)

        logger.info(f"워크플로우 조회: {workflow_data.get('name')} (ID: {workflow_id})")

        return Workflow(**workflow_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"워크플로우 조회 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"워크플로우 조회 실패: {str(e)}"
        )


@router.delete("/{workflow_id}")
async def delete_workflow(workflow_id: str) -> Dict[str, str]:
    """
    워크플로우 삭제

    Args:
        workflow_id: 워크플로우 ID

    Returns:
        Dict[str, str]: 응답 메시지

    Example:
        DELETE /api/workflows/{workflow_id}
        Response: {
            "message": "워크플로우가 삭제되었습니다"
        }
    """
    try:
        workflow_path = WORKFLOWS_DIR / f"{workflow_id}.json"

        if not workflow_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"워크플로우를 찾을 수 없습니다: {workflow_id}"
            )

        workflow_path.unlink()

        logger.info(f"워크플로우 삭제: {workflow_id}")

        return {"message": "워크플로우가 삭제되었습니다"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"워크플로우 삭제 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"워크플로우 삭제 실패: {str(e)}"
        )


@router.post("/validate", response_model=WorkflowValidateResponse)
async def validate_workflow(
    workflow: Workflow,
    config_loader: JsonConfigLoader = Depends(get_config_loader),
):
    """
    워크플로우 검증

    실행 전 워크플로우의 유효성을 검사합니다:
    - 순환 참조 검사
    - 고아 노드 검사
    - 템플릿 변수 유효성 검사
    - Worker별 도구 권한 검사
    - Input 노드 존재 여부 검사
    - Manager 노드 검증

    Args:
        workflow: 검증할 워크플로우
        config_loader: ConfigLoader 의존성 주입

    Returns:
        WorkflowValidateResponse: 검증 결과
            - valid: 검증 통과 여부 (error가 없으면 True)
            - errors: 검증 에러 목록 (severity, node_id, message, suggestion)

    Example:
        POST /api/workflows/validate
        {
            "name": "test",
            "nodes": [...],
            "edges": [...]
        }

        Response:
        {
            "valid": false,
            "errors": [
                {
                    "severity": "error",
                    "node_id": "node1",
                    "message": "순환 참조가 감지되었습니다",
                    "suggestion": "노드 간 연결을 확인하여 순환 참조를 제거하세요"
                }
            ]
        }
    """
    try:
        # WorkflowValidator 생성 (config_loader 전달하여 Worker 도구 목록 동적 로드)
        validator = WorkflowValidator(config_loader=config_loader)

        # 워크플로우 검증
        validation_errors = validator.validate(workflow)

        # ValidationError → WorkflowValidationError 변환
        errors = [
            WorkflowValidationError(
                severity=error.severity,
                node_id=error.node_id,
                message=error.message,
                suggestion=error.suggestion,
            )
            for error in validation_errors
        ]

        # error severity가 있으면 invalid
        has_errors = any(e.severity == "error" for e in errors)

        return WorkflowValidateResponse(
            valid=not has_errors,
            errors=errors,
        )

    except Exception as e:
        logger.error(f"워크플로우 검증 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"워크플로우 검증 실패: {str(e)}"
        )


@router.get("/sessions/{session_id}")
async def get_session(session_id: str) -> Dict[str, Any]:
    """
    워크플로우 실행 세션 조회

    새로고침 후 세션 복원을 위해 사용합니다.

    Args:
        session_id: 세션 ID

    Returns:
        Dict[str, Any]: 세션 정보
            - session_id: 세션 ID
            - workflow: 워크플로우 정의
            - initial_input: 초기 입력
            - status: 실행 상태 (running, completed, error, cancelled)
            - current_node_id: 현재 실행 중인 노드 ID
            - node_outputs: 노드별 출력
            - logs: 실행 로그 (이벤트 목록)
            - start_time: 시작 시각
            - end_time: 종료 시각 (완료/에러 시)
            - error: 에러 메시지 (에러 발생 시)

    Example:
        GET /api/workflows/sessions/abc-123

        Response:
        {
            "session_id": "abc-123",
            "workflow": { "name": "...", "nodes": [...], "edges": [...] },
            "initial_input": "작업 설명",
            "status": "running",
            "current_node_id": "node-2",
            "node_outputs": {
                "node-1": "첫 번째 노드 출력..."
            },
            "logs": [
                {"event_type": "node_start", "node_id": "node-1", ...},
                {"event_type": "node_complete", "node_id": "node-1", ...},
                {"event_type": "node_start", "node_id": "node-2", ...}
            ],
            "start_time": "2025-01-27T12:00:00",
            "end_time": null,
            "error": null
        }
    """
    try:
        # 먼저 현재 프로젝트 경로로 시도
        from src.presentation.web.routers.projects import _current_project_path

        session_store = get_session_store(project_path=_current_project_path)
        session = await session_store.get_session(session_id)

        # 현재 프로젝트에서 세션을 찾지 못하면, fallback 경로에서 시도
        if not session:
            logger.info(f"현재 프로젝트에서 세션 {session_id}를 찾을 수 없음. Fallback 경로에서 시도...")
            fallback_store = get_session_store(project_path=None)
            session = await fallback_store.get_session(session_id)

            if session:
                # Fallback 경로에서 찾은 경우, 세션에 저장된 project_path 사용
                logger.info(f"Fallback 경로에서 세션 발견. project_path: {session.project_path}")

        if not session:
            raise HTTPException(
                status_code=404,
                detail=f"세션을 찾을 수 없습니다: {session_id}"
            )

        logger.info(f"세션 조회: {session_id} (상태: {session.status}, 프로젝트: {session.project_path})")

        return session.to_dict()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"세션 조회 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"세션 조회 실패: {str(e)}"
        )


@router.post("/sessions/{session_id}/cancel")
async def cancel_workflow_session(
    session_id: str,
    bg_manager: BackgroundWorkflowManager = Depends(get_background_manager),
) -> Dict[str, str]:
    """
    워크플로우 실행 취소

    실행 중인 워크플로우를 중단합니다.

    Args:
        session_id: 세션 ID
        bg_manager: 백그라운드 워크플로우 관리자

    Returns:
        Dict[str, str]: 응답 메시지

    Example:
        POST /api/workflows/sessions/abc-123/cancel

        Response:
        {
            "message": "워크플로우가 취소되었습니다",
            "session_id": "abc-123"
        }
    """
    try:
        logger.info(f"워크플로우 취소 요청: {session_id}")

        # BackgroundWorkflowManager를 통해 워크플로우 취소
        await bg_manager.cancel_workflow(session_id)

        return {
            "message": "워크플로우가 취소되었습니다",
            "session_id": session_id,
        }

    except ValueError as e:
        logger.warning(f"워크플로우 취소 실패: {e}")
        raise HTTPException(
            status_code=404,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"워크플로우 취소 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"워크플로우 취소 실패: {str(e)}",
        )


@router.get("/nodes/{node_id}/sessions")
async def get_node_sessions(
    node_id: str,
    bg_manager: BackgroundWorkflowManager = Depends(get_background_manager),
) -> Dict[str, Any]:
    """
    노드의 세션 목록 조회

    사용자가 이전 세션을 확인하고 선택하여 대화를 계속할 수 있도록 합니다.

    Args:
        node_id: 노드 ID
        bg_manager: 백그라운드 워크플로우 관리자

    Returns:
        Dict[str, Any]: 세션 목록 및 현재 활성 세션 정보

    Example:
        GET /api/workflows/nodes/node-123/sessions

        Response:
        {
            "node_id": "node-123",
            "agent_name": "Backend Coder",
            "current_session_id": "uuid-456",
            "session_history": [
                {
                    "session_id": "uuid-456",
                    "agent_name": "Backend Coder",
                    "created_at": "2025-10-30T18:00:00",
                    "last_used_at": "2025-10-30T18:05:00",
                    "is_current": true
                }
            ]
        }
    """
    try:
        executor = bg_manager.executor

        # 현재 활성 세션 ID
        current_session_id = executor._node_sessions.get(node_id)

        # 세션 이력
        session_history = executor._node_session_history.get(node_id, [])

        # 세션 이력에 is_current 플래그 추가
        session_history_with_flag = [
            {
                **session,
                "is_current": session["session_id"] == current_session_id
            }
            for session in session_history
        ]

        # 최신 사용 순으로 정렬
        session_history_with_flag.sort(
            key=lambda s: s["last_used_at"],
            reverse=True
        )

        # 에이전트 이름
        agent_name = executor._node_agent_names.get(node_id, "Unknown")

        return {
            "node_id": node_id,
            "agent_name": agent_name,
            "current_session_id": current_session_id,
            "session_history": session_history_with_flag,
        }

    except Exception as e:
        logger.error(f"노드 세션 목록 조회 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"노드 세션 목록 조회 실패: {str(e)}",
        )


@router.post("/nodes/{node_id}/continue")
async def continue_node_conversation(
    node_id: str,
    prompt: str = Body(..., embed=True),
    bg_manager: BackgroundWorkflowManager = Depends(get_background_manager),
) -> Dict[str, str]:
    """
    노드에 추가 프롬프트를 전송하여 대화 계속 (주도적 대화)

    사용자가 로그 상세 모달에서 추가 질문/지시를 입력할 때 사용합니다.
    해당 노드의 이전 세션을 이어서 실행합니다.

    Args:
        node_id: 노드 ID
        prompt: 추가 프롬프트
        bg_manager: 백그라운드 워크플로우 관리자

    Returns:
        Dict[str, str]: 응답 메시지 및 새 실행 세션 ID

    Example:
        POST /api/workflows/nodes/node-123/continue
        {
            "prompt": "테스트 코드도 작성해줘"
        }

        Response:
        {
            "message": "노드 실행이 시작되었습니다",
            "node_id": "node-123",
            "session_id": "new-session-456"
        }
    """
    try:
        logger.info(f"노드 추가 대화 요청: {node_id}, 프롬프트: {prompt[:50]}...")

        # 새 세션 ID 생성
        import uuid
        new_session_id = str(uuid.uuid4())

        # Executor를 통해 노드 재실행
        executor = bg_manager.executor

        # 디버깅: executor 인스턴스 및 저장된 세션 확인
        logger.info(
            f"[DEBUG] 추가 대화 API 호출:\n"
            f"  - node_id: {node_id}\n"
            f"  - prompt: {prompt[:50]}...\n"
            f"  - executor 인스턴스: {id(executor)}\n"
            f"  - executor._node_sessions 크기: {len(executor._node_sessions)}\n"
            f"  - executor._node_sessions 키: {list(executor._node_sessions.keys())}"
        )

        # 노드의 이전 세션 ID 확인
        previous_session_id = executor._node_sessions.get(node_id)
        if not previous_session_id:
            # 저장된 세션 목록 확인
            available_sessions = list(executor._node_sessions.keys())
            agent_name = executor._node_agent_names.get(node_id, "알 수 없음")

            # 상세한 에러 메시지
            error_msg = (
                f"❌ 노드 '{node_id}' ({agent_name})의 세션을 찾을 수 없습니다.\n\n"
                "💡 가능한 원인:\n"
                "1. 워크플로우를 아직 실행하지 않았습니다\n"
                "2. 서버를 재시작하여 세션이 초기화되었습니다\n"
                "3. 노드 실행 중 에러가 발생하여 세션이 저장되지 않았습니다\n\n"
                f"📝 현재 저장된 세션: {len(available_sessions)}개\n"
            )

            if available_sessions:
                error_msg += f"   - 사용 가능한 노드: {', '.join(available_sessions[:5])}"
                if len(available_sessions) > 5:
                    error_msg += f" 외 {len(available_sessions) - 5}개"
            else:
                error_msg += "   - 저장된 세션이 없습니다. 먼저 워크플로우를 실행해주세요."

            raise ValueError(error_msg)

        logger.info(f"노드 {node_id} 재실행 (이전 세션: {previous_session_id[:8]}...)")

        # 백그라운드 태스크 생성 및 이벤트 저장
        from src.presentation.web.services.background_workflow_manager import BackgroundWorkflowTask
        from collections import deque

        # BackgroundWorkflowTask 생성
        event_queue = deque()

        async def run_node_continue():
            try:
                logger.info(f"노드 {node_id} 추가 대화 실행 시작")
                async for event in executor.execute_single_node_continue(
                    node_id=node_id,
                    additional_prompt=prompt,
                    project_path=executor.project_path,
                ):
                    # 이벤트를 큐에 저장 (SSE로 전송 가능하도록)
                    event_queue.append(event)

                    # 세션 저장소에도 저장
                    await bg_manager.session_store.append_log(new_session_id, event)

                    logger.debug(
                        f"노드 {node_id} 추가 대화 이벤트: {event.event_type} "
                        f"({event.data.get('chunk_type', 'N/A')})"
                    )

                # 완료 시 task 상태 및 세션 업데이트
                if new_session_id in bg_manager.tasks:
                    bg_manager.tasks[new_session_id].completed = True
                await bg_manager.session_store.update_session(new_session_id, status="completed")
                logger.info(f"노드 {node_id} 추가 대화 완료")

            except Exception as e:
                logger.error(f"노드 {node_id} 추가 대화 실패: {e}", exc_info=True)
                # 에러 시 task 상태 및 세션 업데이트
                if new_session_id in bg_manager.tasks:
                    bg_manager.tasks[new_session_id].error = str(e)
                    bg_manager.tasks[new_session_id].completed = True
                await bg_manager.session_store.update_session(new_session_id, status="error", error=str(e))

        # 백그라운드 태스크 시작
        import asyncio
        task = asyncio.create_task(run_node_continue())

        # BackgroundWorkflowTask 저장 (SSE로 이벤트 스트리밍 가능하도록)
        bg_manager.tasks[new_session_id] = BackgroundWorkflowTask(
            session_id=new_session_id,
            task=task,
            event_queue=event_queue,
        )

        # 세션 저장소에도 저장 (SSE 스트리밍을 위해 필요)
        from src.presentation.web.services.workflow_session_store import WorkflowSession
        from src.presentation.web.schemas.workflow import Workflow
        
        workflow_session = WorkflowSession(
            session_id=new_session_id,
            workflow=Workflow(
                name=f"추가 프롬프트 - {node_id}",
                nodes=[],  # 단일 노드 실행이므로 빈 배열
                edges=[],
            ),
            initial_input=prompt,
            project_path=executor.project_path,
            status="running",
            logs=[],
        )
        await bg_manager.session_store.save_session(workflow_session)
        logger.info(f"세션 {new_session_id} 저장소에 저장 완료")

        return {
            "message": "노드 추가 대화가 시작되었습니다",
            "node_id": node_id,
            "session_id": new_session_id,
        }

    except ValueError as e:
        logger.warning(f"노드 추가 대화 실패: {e}")
        raise HTTPException(
            status_code=404,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"노드 추가 대화 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"노드 추가 대화 실패: {str(e)}",
        )


@router.get("/sessions/{session_id}/stream")
async def stream_session_events(
    session_id: str,
    bg_manager: BackgroundWorkflowManager = Depends(get_background_manager),
):
    """
    세션의 이벤트를 SSE로 스트리밍 (추가 프롬프트 실행 결과 수신용)

    로그 상세 모달에서 추가 프롬프트를 전송한 후,
    이 엔드포인트로 SSE 연결하여 실행 결과를 실시간으로 받습니다.

    Args:
        session_id: 세션 ID (continue_node_conversation에서 받은 새 세션 ID)
        bg_manager: 백그라운드 워크플로우 관리자

    Returns:
        EventSourceResponse: SSE 스트리밍 응답

    Example:
        GET /api/workflows/sessions/abc-123/stream
    """
    logger.info(f"SSE 스트리밍 시작: session_id={session_id}")

    async def event_generator():
        """SSE 이벤트 생성기"""
        try:
            # 세션이 존재하는지 확인
            if session_id not in bg_manager.tasks:
                error_msg = f"세션을 찾을 수 없습니다: {session_id}"
                logger.warning(error_msg)
                yield {"data": json.dumps({"error": error_msg})}
                return

            # 이벤트 스트리밍
            async for event in bg_manager.stream_events(session_id, start_from_index=0):
                # 이벤트를 JSON 문자열로 변환
                event_dict = {
                    "event_type": event.event_type,
                    "node_id": event.node_id,
                    "data": event.data,
                    "timestamp": event.timestamp,
                }
                yield {"data": json.dumps(event_dict)}

                # 워크플로우 완료 또는 에러 시 종료
                if event.event_type in ["workflow_complete", "workflow_error"]:
                    logger.info(f"SSE 스트리밍 종료: session_id={session_id}, event={event.event_type}")
                    break

            # 종료 신호
            yield {"data": "[DONE]"}

        except Exception as e:
            error_msg = f"SSE 스트리밍 에러: {str(e)}"
            logger.error(error_msg, exc_info=True)
            yield {"data": json.dumps({"error": error_msg})}
            yield {"data": "[DONE]"}

    # EventSourceResponse로 SSE 스트리밍 반환
    return EventSourceResponse(
        event_generator(),
        headers={
            "X-Accel-Buffering": "no",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.post("/sessions/{session_id}/user-input")
async def send_user_input(
    session_id: str,
    answer: str = Body(..., embed=True),
    bg_manager: BackgroundWorkflowManager = Depends(get_background_manager),
) -> Dict[str, str]:
    """
    사용자 입력을 Worker에게 전달 (Human-in-the-Loop)

    Worker가 "@ASK_USER:" 패턴으로 질문을 했을 때,
    웹 UI에서 사용자 답변을 이 엔드포인트로 전송합니다.

    Args:
        session_id: 세션 ID
        answer: 사용자 답변
        bg_manager: 백그라운드 워크플로우 관리자

    Returns:
        Dict[str, str]: 응답 메시지

    Example:
        POST /api/workflows/sessions/abc-123/user-input
        {
            "answer": "네, 진행해주세요"
        }

        Response:
        {
            "message": "사용자 입력이 전달되었습니다",
            "session_id": "abc-123"
        }
    """
    try:
        logger.info(f"사용자 입력 전달: {session_id}, 답변: {answer[:50]}...")

        # Executor를 통해 Queue에 답변 전달
        executor = bg_manager.executor
        if session_id not in executor.user_input_queues:
            raise ValueError(f"세션 {session_id}의 입력 Queue를 찾을 수 없습니다")

        queue = executor.user_input_queues[session_id]
        await queue.put(answer)

        logger.info(f"사용자 입력 Queue에 답변 전달 완료: {session_id}")

        return {
            "message": "사용자 입력이 전달되었습니다",
            "session_id": session_id,
        }

    except ValueError as e:
        logger.warning(f"사용자 입력 전달 실패: {e}")
        raise HTTPException(
            status_code=404,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"사용자 입력 전달 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"사용자 입력 전달 실패: {str(e)}",
        )


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str) -> Dict[str, str]:
    """
    워크플로우 실행 세션 삭제

    완료된 세션을 정리할 때 사용합니다.

    Args:
        session_id: 세션 ID

    Returns:
        Dict[str, str]: 응답 메시지

    Example:
        DELETE /api/workflows/sessions/abc-123

        Response:
        {
            "message": "세션이 삭제되었습니다"
        }
    """
    try:
        # 현재 프로젝트 경로 가져오기 (get_session과 동일)
        from src.presentation.web.routers.projects import _current_project_path

        # 프로젝트별 세션 저장소 사용
        session_store = get_session_store(project_path=_current_project_path)

        # 세션 존재 여부 확인
        session = await session_store.get_session(session_id)
        if not session:
            # Fallback 경로에서 시도
            logger.info(f"현재 프로젝트에서 세션 {session_id}를 찾을 수 없음. Fallback 경로에서 시도...")
            fallback_store = get_session_store(project_path=None)
            session = await fallback_store.get_session(session_id)

            if session:
                await fallback_store.delete_session(session_id)
                logger.info(f"Fallback 경로에서 세션 삭제: {session_id}")
            else:
                raise HTTPException(
                    status_code=404,
                    detail=f"세션을 찾을 수 없습니다: {session_id}"
                )
        else:
            await session_store.delete_session(session_id)
            logger.info(f"세션 삭제: {session_id}")

        return {"message": "세션이 삭제되었습니다"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"세션 삭제 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"세션 삭제 실패: {str(e)}"
        )


@router.post("/clear-node-sessions")
async def clear_node_sessions() -> Dict[str, Any]:
    """
    모든 노드의 SDK 세션 초기화

    Claude Code SDK가 저장한 모든 세션 파일(.jsonl)을 삭제하여
    각 노드의 대화 컨텍스트를 초기화합니다.

    Returns:
        Dict[str, Any]: 삭제된 세션 수와 메시지

    Example:
        POST /api/workflows/clear-node-sessions

        Response:
        {
            "message": "모든 노드 세션이 초기화되었습니다",
            "deleted_sessions": 824
        }
    """
    try:
        # 현재 프로젝트 경로 가져오기
        from src.presentation.web.routers.projects import _current_project_path

        if not _current_project_path:
            raise HTTPException(
                status_code=400,
                detail="프로젝트가 선택되지 않았습니다"
            )

        # Claude 세션 디렉토리 경로 생성
        # ~/.claude/projects/<project-dir>/
        project_dir_name = str(Path(_current_project_path).resolve()).replace('/', '-')
        if project_dir_name.startswith('-'):
            project_dir_name = project_dir_name[1:]

        claude_sessions_dir = Path.home() / ".claude" / "projects" / f"-{project_dir_name}"

        logger.info(f"Claude 세션 디렉토리: {claude_sessions_dir}")

        if not claude_sessions_dir.exists():
            return {
                "message": "세션 디렉토리가 존재하지 않습니다 (초기화할 세션 없음)",
                "deleted_sessions": 0
            }

        # .jsonl 파일 찾기
        session_files = list(claude_sessions_dir.glob("*.jsonl"))
        deleted_count = 0

        for session_file in session_files:
            try:
                session_file.unlink()
                deleted_count += 1
                logger.debug(f"세션 파일 삭제: {session_file.name}")
            except Exception as e:
                logger.warning(f"세션 파일 삭제 실패: {session_file.name} - {e}")

        logger.info(f"노드 세션 초기화 완료: {deleted_count}개 파일 삭제")

        return {
            "message": "모든 노드 세션이 초기화되었습니다",
            "deleted_sessions": deleted_count
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"노드 세션 초기화 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"노드 세션 초기화 실패: {str(e)}"
        )


# ==================== 워크플로우 설계 (workflow_designer) ====================

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
    with open(state_file, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def load_design_session_state(session_id: str) -> dict | None:
    """설계 세션 상태를 파일에서 로드"""
    session_dir = get_design_session_dir(session_id)
    state_file = session_dir / "state.json"
    if state_file.exists():
        with open(state_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None


def append_design_session_output(session_id: str, chunk: str):
    """설계 세션 출력을 파일에 추가"""
    session_dir = get_design_session_dir(session_id)
    output_file = session_dir / "output.txt"
    with open(output_file, 'a', encoding='utf-8') as f:
        f.write(chunk)


def read_design_session_output(session_id: str) -> str:
    """설계 세션 출력을 파일에서 읽기"""
    session_dir = get_design_session_dir(session_id)
    output_file = session_dir / "output.txt"
    if output_file.exists():
        with open(output_file, 'r', encoding='utf-8') as f:
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
    requirements: str, session_id: str
) -> AsyncIterator[str]:
    """
    workflow_designer 실행 (스트리밍)

    Args:
        requirements: 워크플로우 요구사항
        session_id: 세션 ID

    Yields:
        str: Worker 출력 청크
    """
    try:
        config = get_workflow_designer_config()

        # claude-flow 프로젝트를 working directory로 설정
        # 기존 워커 정보 및 프롬프트를 참고하기 위함
        claude_flow_project_dir = str(get_project_root())

        worker = WorkerAgent(
            config=config,
            project_dir=claude_flow_project_dir
        )

        logger.info(
            f"[{session_id}] workflow_designer 실행 시작 "
            f"(working_dir: {claude_flow_project_dir})"
        )

        async for chunk in worker.execute_task(requirements):
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
    is_reconnect = existing_state is not None and existing_state.get("status") in ["generating", "completed"]

    if is_reconnect:
        logger.info(f"[{session_id}] 설계 세션 재접속 (상태: {existing_state.get('status')})")
    else:
        logger.info(
            f"[{session_id}] 워크플로우 설계 요청 "
            f"(요구사항 길이: {len(request.requirements)})"
        )
        # 새 세션 상태 저장
        save_design_session_state(session_id, {
            "session_id": session_id,
            "status": "generating",
            "requirements": request.requirements,
            "created_at": datetime.now().isoformat(),
        })

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
                request.requirements, session_id
            ):
                chunk_count += 1
                accumulated_output += chunk
                append_design_session_output(session_id, chunk)  # 파일에 저장
                logger.debug(f"[{session_id}] SSE Chunk #{chunk_count}: len={len(chunk)}")
                yield {"data": chunk}

            logger.info(f"[{session_id}] SSE 스트림 완료 (총 {chunk_count}개 청크)")
            logger.info(f"[{session_id}] 📊 전체 출력 길이: {len(accumulated_output)} characters")

            # 세션 완료 상태 저장
            save_design_session_state(session_id, {
                "session_id": session_id,
                "status": "completed",
                "requirements": request.requirements,
                "created_at": existing_state.get("created_at") if existing_state else datetime.now().isoformat(),
                "completed_at": datetime.now().isoformat(),
            })

            yield {"data": "[DONE]"}

        except Exception as e:
            error_msg = f"ERROR: {str(e)}"
            logger.error(f"[{session_id}] {error_msg}", exc_info=True)

            # 에러 상태 저장
            save_design_session_state(session_id, {
                "session_id": session_id,
                "status": "error",
                "error": str(e),
                "created_at": existing_state.get("created_at") if existing_state else datetime.now().isoformat(),
            })

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
        }
    )
