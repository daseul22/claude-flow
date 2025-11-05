"""
워크플로우 실행 및 세션 관리 API

워크플로우 실행, 세션 조회, 취소, 스트리밍 등을 위한 엔드포인트를 제공합니다.
"""

import asyncio
import json
import uuid
from collections import deque
from pathlib import Path
from typing import Dict, Any

from fastapi import APIRouter, HTTPException, Depends, Body
from sse_starlette.sse import EventSourceResponse

from src.infrastructure.logging import get_logger
from src.presentation.web.schemas.workflow import (
    WorkflowExecuteRequest,
    Workflow,
)
from src.presentation.web.services.workflow_session_store import (
    get_session_store,
    WorkflowSession,
)
from src.presentation.web.services.background_workflow_manager import (
    BackgroundWorkflowManager,
    BackgroundWorkflowTask,
)
from .dependencies import get_background_manager

logger = get_logger(__name__)
router = APIRouter()


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
        raise HTTPException(status_code=400, detail="워크플로우에 노드가 없습니다")

    # 현재 프로젝트 경로 가져오기 (모듈 참조로 변경 - import 시점 복사 문제 해결)
    from src.presentation.web.routers.projects import dependencies as projects_deps

    # 프로젝트가 선택되지 않았으면 에러
    _current_project_path = projects_deps._current_project_path
    logger.info(f"[{session_id}] 프로젝트 경로 확인: {_current_project_path}")
    if _current_project_path is None:
        logger.error(f"[{session_id}] 프로젝트 미선택 상태에서 워크플로우 실행 시도")
        raise HTTPException(
            status_code=400,
            detail="프로젝트를 먼저 선택해주세요. 헤더의 '프로젝트 선택' 버튼을 클릭하세요."
        )

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
        logger.info(f"[{session_id}] 완료된 세션 삭제 후 재생성 " f"(이전 상태: {existing_session.status})")
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
        logger.info(f"[{session_id}] 실행 중인 세션에 재접속 " f"(상태: {existing_session.status})")

    # SSE 스트리밍 함수
    async def event_generator():
        try:
            # 시작 인덱스 결정 (재접속 시 중복 방지)
            start_from_index = 0
            if request.last_event_index is not None:
                start_from_index = request.last_event_index + 1  # 다음 이벤트부터

            logger.info(f"[{session_id}] SSE 스트리밍 시작 " f"(start_from_index={start_from_index})")

            event_count = 0

            # 백그라운드 Task에서 이벤트 스트리밍 (start_from_index 전달)
            async for event in bg_manager.stream_events(
                session_id, start_from_index=start_from_index
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
            logger.info(f"[{session_id}] ⏹️ 클라이언트가 연결을 끊었습니다 " f"(워크플로우는 백그라운드에서 계속 실행 중)")

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
        },
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
        # 먼저 현재 프로젝트 경로로 시도 (모듈 참조로 변경)
        from src.presentation.web.routers.projects import dependencies as projects_deps
        _current_project_path = projects_deps._current_project_path

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
            raise HTTPException(status_code=404, detail=f"세션을 찾을 수 없습니다: {session_id}")

        logger.info(f"세션 조회: {session_id} (상태: {session.status}, 프로젝트: {session.project_path})")

        return session.to_dict()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"세션 조회 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"세션 조회 실패: {str(e)}")


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
            {**session, "is_current": session["session_id"] == current_session_id}
            for session in session_history
        ]

        # 최신 사용 순으로 정렬
        session_history_with_flag.sort(key=lambda s: s["last_used_at"], reverse=True)

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
                await bg_manager.session_store.update_session(
                    new_session_id, status="error", error=str(e)
                )

        # 백그라운드 태스크 시작
        task = asyncio.create_task(run_node_continue())

        # BackgroundWorkflowTask 저장 (SSE로 이벤트 스트리밍 가능하도록)
        bg_manager.tasks[new_session_id] = BackgroundWorkflowTask(
            session_id=new_session_id,
            task=task,
            event_queue=event_queue,
        )

        # 세션 저장소에도 저장 (SSE 스트리밍을 위해 필요)
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
        # 현재 프로젝트 경로 가져오기 (모듈 참조로 변경)
        from src.presentation.web.routers.projects import dependencies as projects_deps
        _current_project_path = projects_deps._current_project_path

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
                raise HTTPException(status_code=404, detail=f"세션을 찾을 수 없습니다: {session_id}")
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
            detail=f"세션 삭제 실패: {str(e)}",
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
        # 현재 프로젝트 경로 가져오기 (모듈 참조로 변경)
        from src.presentation.web.routers.projects import dependencies as projects_deps
        _current_project_path = projects_deps._current_project_path

        if not _current_project_path:
            raise HTTPException(status_code=400, detail="프로젝트가 선택되지 않았습니다")

        # Claude 세션 디렉토리 경로 생성
        # ~/.claude/projects/<project-dir>/
        project_dir_name = str(Path(_current_project_path).resolve()).replace("/", "-")
        if project_dir_name.startswith("-"):
            project_dir_name = project_dir_name[1:]

        claude_sessions_dir = Path.home() / ".claude" / "projects" / f"-{project_dir_name}"

        logger.info(f"Claude 세션 디렉토리: {claude_sessions_dir}")

        if not claude_sessions_dir.exists():
            return {
                "message": "세션 디렉토리가 존재하지 않습니다 (초기화할 세션 없음)",
                "deleted_sessions": 0,
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
            "deleted_sessions": deleted_count,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"노드 세션 초기화 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"노드 세션 초기화 실패: {str(e)}",
        )


@router.post("/sessions/{session_id}/restart")
async def restart_workflow_from_node(
    session_id: str,
    restart_node_id: str = Body(..., embed=True),
    bg_manager: BackgroundWorkflowManager = Depends(get_background_manager),
):
    """
    특정 노드부터 워크플로우 재시작

    워크플로우 실행 중 중단/에러 발생 시, 이미 실행한 노드를 선택하여
    해당 노드부터 워크플로우를 다시 실행합니다.

    재시작 시:
    - 이전 실행의 node_outputs, node_inputs 복원
    - 재시작 노드는 이전에 받았던 입력을 그대로 받아서 실행
    - 새로운 세션 ID로 실행 (이전 세션과 분리)

    Args:
        session_id: 원본 세션 ID (이전 실행)
        restart_node_id: 재시작할 노드 ID
        bg_manager: BackgroundWorkflowManager 의존성 주입

    Returns:
        EventSourceResponse: SSE 스트림 (워크플로우 실행 이벤트)

    Raises:
        HTTPException 404: 원본 세션을 찾을 수 없음
        HTTPException 400: 재시작 노드를 찾을 수 없음
        HTTPException 500: 재시작 실패
    """
    try:
        logger.info(
            f"워크플로우 재시작 요청 - 원본: {session_id}, 재시작 노드: {restart_node_id}"
        )

        # 원본 세션 존재 확인
        session_store = get_session_store()
        original_session = await session_store.get_session(session_id)
        if not original_session:
            raise HTTPException(
                status_code=404,
                detail=f"원본 세션을 찾을 수 없습니다: {session_id}",
            )

        # 새 세션 ID 생성
        new_session_id = str(uuid.uuid4())
        logger.info(f"새 세션 ID 생성: {new_session_id} (원본: {session_id})")

        # 새 세션 생성 (원본 세션 정보 복사)
        new_session = await session_store.create_session(
            session_id=new_session_id,
            workflow=original_session.workflow,
            initial_input=original_session.initial_input,
            project_path=original_session.project_path,
        )

        # 워크플로우 재시작 (백그라운드)
        await bg_manager.restart_workflow_from_node(
            original_session_id=session_id,
            restart_node_id=restart_node_id,
            new_session_id=new_session_id,
        )

        logger.info(
            f"[{new_session_id}] 워크플로우 재시작 시작 (원본: {session_id}, 노드: {restart_node_id})"
        )

        # SSE 이벤트 스트리밍
        async def event_generator():
            """SSE 이벤트 생성기"""
            try:
                async for event in bg_manager.stream_events(new_session_id):
                    event_dict = event.model_dump() if hasattr(event, "model_dump") else event
                    yield {
                        "event": event_dict.get("event_type", "unknown"),
                        "data": json.dumps(event_dict, ensure_ascii=False),
                    }

            except Exception as e:
                logger.error(f"[{new_session_id}] SSE 스트리밍 에러: {e}", exc_info=True)
                # 에러 이벤트 전송
                error_event = {
                    "event": "error",
                    "data": json.dumps(
                        {
                            "event_type": "error",
                            "node_id": "",
                            "data": {"error": str(e)},
                            "timestamp": "",
                        },
                        ensure_ascii=False,
                    ),
                }
                yield error_event

        return EventSourceResponse(event_generator())

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"워크플로우 재시작 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"워크플로우 재시작 실패: {str(e)}",
        )
