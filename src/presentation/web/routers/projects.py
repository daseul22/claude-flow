"""
프로젝트 API 라우터

프로젝트 디렉토리 선택 및 워크플로우 설정 저장/로드를 위한 엔드포인트를 제공합니다.
"""

import json
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any

from fastapi import APIRouter, HTTPException
from src.infrastructure.logging import get_logger
from src.presentation.web.schemas.workflow import (
    ProjectSelectRequest,
    ProjectSelectResponse,
    ProjectWorkflowSaveRequest,
    ProjectWorkflowLoadResponse,
    Workflow,
    ProjectConfig,
    DisplayConfig,
    DisplayConfigLoadResponse,
    DisplayConfigSaveRequest,
    LogFileInfo,
    LogListResponse,
    SessionFileInfo,
    SessionListResponse,
    LogContentResponse,
    SessionContentResponse,
)
from src.presentation.web.config import ProjectConfig as Config, ErrorMessages

logger = get_logger(__name__)
router = APIRouter(prefix="/api/projects", tags=["projects"])

# 현재 선택된 프로젝트 경로 (서버 메모리에 저장)
_current_project_path: Optional[str] = None


def get_config_path(project_path: str) -> Path:
    """
    프로젝트 설정 파일 경로 반환 (레거시, 하위 호환용)

    Args:
        project_path: 프로젝트 디렉토리 경로

    Returns:
        Path: .claude-flow/workflow-config.json 경로
    """
    project_dir = Path(project_path)
    config_dir = project_dir / ".claude-flow"
    return config_dir / "workflow-config.json"


def get_workflows_dir(project_path: str) -> Path:
    """
    워크플로우 디렉토리 경로 반환

    Args:
        project_path: 프로젝트 디렉토리 경로

    Returns:
        Path: .claude-flow/workflows/ 경로
    """
    project_dir = Path(project_path)
    config_dir = project_dir / ".claude-flow"
    return config_dir / "workflows"


def get_workflow_path(project_path: str, workflow_name: str) -> Path:
    """
    특정 워크플로우 파일 경로 반환

    Args:
        project_path: 프로젝트 디렉토리 경로
        workflow_name: 워크플로우 이름

    Returns:
        Path: .claude-flow/workflows/{workflow_name}.json 경로
    """
    workflows_dir = get_workflows_dir(project_path)
    return workflows_dir / f"{workflow_name}.json"


def migrate_legacy_config(project_path: str) -> bool:
    """
    레거시 workflow-config.json을 workflows/default.json로 마이그레이션

    Args:
        project_path: 프로젝트 디렉토리 경로

    Returns:
        bool: 마이그레이션 수행 여부
    """
    legacy_config_path = get_config_path(project_path)

    if not legacy_config_path.exists():
        return False

    # workflows 디렉토리 생성
    workflows_dir = get_workflows_dir(project_path)
    workflows_dir.mkdir(parents=True, exist_ok=True)

    # default.json으로 복사
    default_workflow_path = get_workflow_path(project_path, "default")

    try:
        shutil.copy2(legacy_config_path, default_workflow_path)
        logger.info(f"레거시 설정 파일 마이그레이션: {legacy_config_path} → {default_workflow_path}")

        # 레거시 파일은 백업 후 삭제
        backup_path = legacy_config_path.with_suffix(".json.bak")
        shutil.move(str(legacy_config_path), str(backup_path))
        logger.info(f"레거시 설정 파일 백업: {backup_path}")

        return True
    except Exception as e:
        logger.error(f"레거시 설정 마이그레이션 실패: {e}", exc_info=True)
        return False


def get_display_config_path(project_path: str) -> Path:
    """
    Display 설정 파일 경로 반환

    Args:
        project_path: 프로젝트 디렉토리 경로

    Returns:
        Path: .claude-flow/display-config.json 경로
    """
    project_dir = Path(project_path)
    config_dir = project_dir / ".claude-flow"
    return config_dir / "display-config.json"


def validate_project_path(project_path: str) -> Path:
    """
    프로젝트 경로 검증

    Args:
        project_path: 프로젝트 디렉토리 경로

    Returns:
        Path: 검증된 경로 객체

    Raises:
        HTTPException: 경로가 유효하지 않은 경우
    """
    path = Path(project_path).resolve()

    if not path.exists():
        raise HTTPException(
            status_code=400,
            detail=f"프로젝트 디렉토리가 존재하지 않습니다: {project_path}"
        )

    if not path.is_dir():
        raise HTTPException(
            status_code=400,
            detail=f"디렉토리가 아닙니다: {project_path}"
        )

    return path


@router.post("/select", response_model=ProjectSelectResponse)
async def select_project(request: ProjectSelectRequest) -> ProjectSelectResponse:
    """
    프로젝트 디렉토리 선택

    Args:
        request: 프로젝트 선택 요청 (프로젝트 경로 포함)

    Returns:
        ProjectSelectResponse: 선택 결과 및 기존 설정 존재 여부

    Example:
        POST /api/projects/select
        Body: {
            "project_path": "/Users/username/my-project"
        }

        Response: {
            "project_path": "/Users/username/my-project",
            "message": "프로젝트가 선택되었습니다",
            "has_existing_config": true
        }
    """
    global _current_project_path

    # 경로 검증
    project_path = validate_project_path(request.project_path)
    _current_project_path = str(project_path)

    # 기존 설정 확인
    config_path = get_config_path(str(project_path))
    has_existing = config_path.exists()

    logger.info(
        f"프로젝트 선택: {project_path} "
        f"(기존 설정: {'있음' if has_existing else '없음'})"
    )

    return ProjectSelectResponse(
        project_path=str(project_path),
        message="프로젝트가 선택되었습니다",
        has_existing_config=has_existing,
    )


@router.get("/current")
async def get_current_project() -> Dict[str, Any]:
    """
    현재 선택된 프로젝트 정보 조회

    Returns:
        Dict[str, Any]: 프로젝트 정보 (경로, 설정 존재 여부)

    Example:
        GET /api/projects/current

        Response: {
            "project_path": "/Users/username/my-project",
            "has_existing_config": true
        }
    """
    if not _current_project_path:
        return {
            "project_path": None,
            "has_existing_config": False,
        }

    config_path = get_config_path(_current_project_path)
    has_existing = config_path.exists()

    return {
        "project_path": _current_project_path,
        "has_existing_config": has_existing,
    }


@router.post("/workflow")
async def save_project_workflow(
    request: ProjectWorkflowSaveRequest
) -> Dict[str, str]:
    """
    프로젝트에 워크플로우 저장

    Args:
        request: 워크플로우 저장 요청

    Returns:
        Dict[str, str]: 응답 메시지

    Example:
        POST /api/projects/workflow
        Body: {
            "project_path": "/Users/username/my-project",  # 옵션
            "workflow": {
                "name": "코드 리뷰 워크플로우",
                "nodes": [...],
                "edges": [...]
            }
        }

        Response: {
            "message": "워크플로우가 저장되었습니다",
            "config_path": "/Users/username/my-project/.claude-flow/workflow-config.json"
        }
    """
    # 프로젝트 경로 결정 (요청에 포함되지 않으면 현재 프로젝트 사용)
    project_path = request.project_path or _current_project_path

    # 명시적 검증: project_path가 None이거나 빈 문자열이면 에러
    if not project_path or project_path.strip() == "":
        logger.error(
            f"워크플로우 저장 실패: 프로젝트 경로 없음 "
            f"(request.project_path={request.project_path}, _current_project_path={_current_project_path})"
        )
        raise HTTPException(
            status_code=400,
            detail=(
                "프로젝트가 선택되지 않았습니다. "
                "먼저 '프로젝트 선택' 버튼을 클릭하여 프로젝트 디렉토리를 선택하세요."
            )
        )

    # 경로 검증
    validate_project_path(project_path)

    # 설정 디렉토리 생성
    config_path = get_config_path(project_path)
    config_path.parent.mkdir(parents=True, exist_ok=True)

    # ProjectConfig 생성
    project_config = ProjectConfig(
        project_path=project_path,
        workflow=request.workflow,
        metadata={
            "last_modified": datetime.now().isoformat(),
            "version": "1.0",
        },
    )

    # JSON 저장
    try:
        workflow_dict = project_config.model_dump(mode='json', exclude_none=False)

        # 디버그: parallel_execution 필드 확인
        for node in request.workflow.nodes:
            node_data = node.data if hasattr(node, 'data') else node.get('data', {})
            if isinstance(node_data, dict):
                parallel_exec = node_data.get('parallel_execution')
                logger.info(
                    f"[저장] 노드 {node.id}: parallel_execution = {parallel_exec}"
                )

        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(
                workflow_dict,
                f,
                ensure_ascii=False,
                indent=2,
            )

        logger.info(
            f"워크플로우 저장: {request.workflow.name} → {config_path}"
        )

        return {
            "message": "워크플로우가 저장되었습니다",
            "config_path": str(config_path),
        }

    except Exception as e:
        logger.error(f"워크플로우 저장 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"워크플로우 저장 실패: {str(e)}"
        )


@router.get("/workflow", response_model=ProjectWorkflowLoadResponse)
async def load_project_workflow(
    project_path: Optional[str] = None
) -> ProjectWorkflowLoadResponse:
    """
    프로젝트에서 워크플로우 로드

    Args:
        project_path: 프로젝트 디렉토리 경로 (옵션, 미제공 시 현재 프로젝트)

    Returns:
        ProjectWorkflowLoadResponse: 로드된 워크플로우 및 메타데이터

    Example:
        GET /api/projects/workflow?project_path=/Users/username/my-project

        Response: {
            "project_path": "/Users/username/my-project",
            "workflow": {
                "name": "코드 리뷰 워크플로우",
                "nodes": [...],
                "edges": [...]
            },
            "last_modified": "2025-10-27T12:34:56.789Z"
        }
    """
    # 프로젝트 경로 결정
    target_path = project_path or _current_project_path

    if not target_path:
        raise HTTPException(
            status_code=400,
            detail="프로젝트가 선택되지 않았습니다. 먼저 /api/projects/select를 호출하세요."
        )

    # 경로 검증
    validate_project_path(target_path)

    # 설정 파일 확인
    config_path = get_config_path(target_path)

    if not config_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"워크플로우 설정 파일을 찾을 수 없습니다: {config_path}"
        )

    # JSON 로드
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config_data = json.load(f)

        project_config = ProjectConfig(**config_data)

        logger.info(
            f"워크플로우 로드: {project_config.workflow.name} ← {config_path}"
        )

        # 디버그: parallel_execution 필드 확인
        for node in project_config.workflow.nodes:
            node_data = node.data if hasattr(node, 'data') else {}
            if isinstance(node_data, dict):
                parallel_exec = node_data.get('parallel_execution')
            else:
                parallel_exec = getattr(node_data, 'parallel_execution', None)
            logger.info(
                f"[로드] 노드 {node.id}: parallel_execution = {parallel_exec}"
            )

        return ProjectWorkflowLoadResponse(
            project_path=target_path,
            workflow=project_config.workflow,
            last_modified=project_config.metadata.get("last_modified"),
        )

    except Exception as e:
        logger.error(f"워크플로우 로드 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"워크플로우 로드 실패: {str(e)}"
        )


@router.delete("/sessions")
async def clear_sessions() -> Dict[str, Any]:
    """
    현재 프로젝트의 웹 워크플로우 세션 데이터 비우기

    ~/.claude-flow/{project_name}/web-sessions/ 디렉토리의 모든 세션 파일을 삭제합니다.

    Returns:
        Dict[str, Any]: 삭제 결과 (삭제된 파일 수, 확보된 용량)

    Example:
        DELETE /api/projects/sessions

        Response: {
            "message": "세션 데이터가 삭제되었습니다",
            "deleted_files": 5,
            "freed_space_mb": 12.3
        }
    """
    if not _current_project_path:
        raise HTTPException(
            status_code=400,
            detail="프로젝트가 선택되지 않았습니다."
        )

    # 웹 세션 디렉토리 경로: ~/.claude-flow/{project_name}/web-sessions/
    project_dir = Path(_current_project_path)
    project_name = project_dir.name
    web_sessions_dir = Path.home() / ".claude-flow" / project_name / "web-sessions"

    if not web_sessions_dir.exists():
        logger.info(f"웹 세션 디렉토리가 존재하지 않습니다: {web_sessions_dir}")
        return {
            "message": "삭제할 세션 데이터가 없습니다",
            "deleted_files": 0,
            "freed_space_mb": 0.0
        }

    try:
        # 디렉토리 크기 및 파일 개수 계산
        total_size = 0
        file_count = 0

        for file_path in web_sessions_dir.rglob("*"):
            if file_path.is_file():
                total_size += file_path.stat().st_size
                file_count += 1

        # 디렉토리 삭제 및 재생성 (빈 디렉토리 유지)
        shutil.rmtree(web_sessions_dir)
        web_sessions_dir.mkdir(parents=True, exist_ok=True)

        freed_space_mb = total_size / (1024 * 1024)

        logger.info(
            f"웹 세션 데이터 삭제 완료: {web_sessions_dir} "
            f"(파일: {file_count}개, 용량: {freed_space_mb:.2f} MB)"
        )

        return {
            "message": "세션 데이터가 삭제되었습니다",
            "deleted_files": file_count,
            "freed_space_mb": round(freed_space_mb, 2)
        }

    except Exception as e:
        logger.error(f"웹 세션 데이터 삭제 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"세션 데이터 삭제 실패: {str(e)}"
        )


@router.delete("/logs")
async def clear_logs() -> Dict[str, Any]:
    """
    현재 프로젝트의 로그 파일 비우기

    ~/.claude-flow/{project-name}/logs/ 디렉토리의 로그 파일을 모두 삭제합니다.

    Returns:
        Dict[str, Any]: 삭제 결과 (삭제된 파일 수, 확보된 용량)

    Example:
        DELETE /api/projects/logs

        Response: {
            "message": "로그 파일이 삭제되었습니다",
            "deleted_files": 8,
            "freed_space_mb": 45.6
        }
    """
    if not _current_project_path:
        raise HTTPException(
            status_code=400,
            detail="프로젝트가 선택되지 않았습니다."
        )

    project_dir = Path(_current_project_path)
    project_name = project_dir.name
    home_dir = Path.home()

    # 로그 디렉토리: ~/.claude-flow/{project_name}/logs/
    log_dirs = [
        home_dir / ".claude-flow" / project_name / "logs",
    ]

    total_size = 0
    total_file_count = 0
    deleted_dirs = []

    try:
        for logs_dir in log_dirs:
            if not logs_dir.exists():
                logger.debug(f"로그 디렉토리가 존재하지 않습니다: {logs_dir}")
                continue

            # 디렉토리 크기 및 파일 개수 계산
            dir_size = 0
            dir_file_count = 0

            for file_path in logs_dir.rglob("*"):
                if file_path.is_file():
                    dir_size += file_path.stat().st_size
                    dir_file_count += 1

            # 디렉토리 삭제 및 재생성 (빈 디렉토리 유지)
            shutil.rmtree(logs_dir)
            logs_dir.mkdir(parents=True, exist_ok=True)

            total_size += dir_size
            total_file_count += dir_file_count
            deleted_dirs.append(str(logs_dir))

            logger.info(
                f"로그 파일 삭제: {logs_dir} "
                f"(파일: {dir_file_count}개, 용량: {dir_size / (1024 * 1024):.2f} MB)"
            )

        freed_space_mb = total_size / (1024 * 1024)

        if total_file_count == 0:
            return {
                "message": "삭제할 로그 파일이 없습니다",
                "deleted_files": 0,
                "freed_space_mb": 0.0
            }

        logger.info(
            f"로그 파일 삭제 완료 (총 {len(deleted_dirs)}개 위치): "
            f"{', '.join(deleted_dirs)} "
            f"(파일: {total_file_count}개, 용량: {freed_space_mb:.2f} MB)"
        )

        return {
            "message": "로그 파일이 삭제되었습니다",
            "deleted_files": total_file_count,
            "freed_space_mb": round(freed_space_mb, 2)
        }

    except Exception as e:
        logger.error(f"로그 파일 삭제 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"로그 파일 삭제 실패: {str(e)}"
        )


@router.get("/display-config", response_model=DisplayConfigLoadResponse)
async def load_display_config(
    project_path: Optional[str] = None
) -> DisplayConfigLoadResponse:
    """
    Display 설정 로드

    Args:
        project_path: 프로젝트 디렉토리 경로 (옵션, 미제공 시 현재 프로젝트)

    Returns:
        DisplayConfigLoadResponse: 로드된 Display 설정

    Example:
        GET /api/projects/display-config

        Response: {
            "config": {
                "left_sidebar_open": true,
                "right_sidebar_open": true,
                "expanded_sections": ["input", "manager", "general"]
            }
        }
    """
    # 프로젝트 경로 결정
    target_path = project_path or _current_project_path

    if not target_path:
        # 프로젝트 선택되지 않은 경우 기본값 반환
        logger.info("프로젝트 미선택 - Display 설정 기본값 반환")
        return DisplayConfigLoadResponse(
            config=DisplayConfig()
        )

    # 경로 검증
    try:
        validate_project_path(target_path)
    except HTTPException:
        # 경로 검증 실패 시 기본값 반환
        logger.warning(f"프로젝트 경로 검증 실패 - Display 설정 기본값 반환: {target_path}")
        return DisplayConfigLoadResponse(
            config=DisplayConfig()
        )

    # 설정 파일 확인
    config_path = get_display_config_path(target_path)

    if not config_path.exists():
        # 설정 파일 없으면 기본값 반환
        logger.info(f"Display 설정 파일 없음 - 기본값 반환: {config_path}")
        return DisplayConfigLoadResponse(
            config=DisplayConfig()
        )

    # JSON 로드
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config_data = json.load(f)

        display_config = DisplayConfig(**config_data)

        logger.info(f"Display 설정 로드 완료: {config_path}")

        return DisplayConfigLoadResponse(
            config=display_config
        )

    except Exception as e:
        logger.error(f"Display 설정 로드 실패: {e}", exc_info=True)
        # 로드 실패 시 기본값 반환
        return DisplayConfigLoadResponse(
            config=DisplayConfig()
        )


@router.post("/display-config")
async def save_display_config(
    request: DisplayConfigSaveRequest
) -> Dict[str, str]:
    """
    Display 설정 저장

    Args:
        request: Display 설정 저장 요청

    Returns:
        Dict[str, str]: 응답 메시지

    Example:
        POST /api/projects/display-config
        Body: {
            "config": {
                "left_sidebar_open": false,
                "right_sidebar_open": true,
                "expanded_sections": ["input", "manager"]
            }
        }

        Response: {
            "message": "Display 설정이 저장되었습니다",
            "config_path": "/project/.claude-flow/display-config.json"
        }
    """
    if not _current_project_path:
        raise HTTPException(
            status_code=400,
            detail="프로젝트가 선택되지 않았습니다. 먼저 프로젝트를 선택하세요."
        )

    # 경로 검증
    validate_project_path(_current_project_path)

    # 설정 디렉토리 생성
    config_path = get_display_config_path(_current_project_path)
    config_path.parent.mkdir(parents=True, exist_ok=True)

    # JSON 저장
    try:
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(
                request.config.model_dump(),
                f,
                ensure_ascii=False,
                indent=2,
            )

        logger.info(f"Display 설정 저장: {config_path}")

        return {
            "message": "Display 설정이 저장되었습니다",
            "config_path": str(config_path),
        }

    except Exception as e:
        logger.error(f"Display 설정 저장 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Display 설정 저장 실패: {str(e)}"
        )


# ============================================================================
# 로그 및 세션 뷰어 API
# ============================================================================

@router.get("/logs/list", response_model=LogListResponse)
async def list_logs() -> LogListResponse:
    """
    로그 파일 목록 조회

    현재 프로젝트의 로그 디렉토리 (~/.claude-flow/{project_name}/logs/)에서
    모든 로그 파일을 검색하여 반환합니다.

    Returns:
        LogListResponse: 로그 파일 목록 및 통계

    Example:
        GET /api/projects/logs/list

        Response: {
            "logs": [
                {
                    "path": "system.log",
                    "name": "system.log",
                    "size": 1024000,
                    "modified": "2025-10-29T17:30:00",
                    "type": "system"
                },
                {
                    "path": "session-123/debug.log",
                    "name": "debug.log",
                    "size": 512000,
                    "modified": "2025-10-29T17:25:00",
                    "type": "debug"
                }
            ],
            "total_count": 2,
            "total_size": 1536000
        }
    """
    if not _current_project_path:
        raise HTTPException(
            status_code=400,
            detail="프로젝트가 선택되지 않았습니다."
        )

    try:
        project_dir = Path(_current_project_path)
        project_name = project_dir.name
        logs_dir = Path.home() / ".claude-flow" / project_name / "logs"

        if not logs_dir.exists():
            return LogListResponse(logs=[], total_count=0, total_size=0)

        logs = []
        total_size = 0

        # 모든 로그 파일 수집
        for log_file in logs_dir.rglob("*.log"):
            if not log_file.is_file():
                continue

            stat = log_file.stat()
            relative_path = log_file.relative_to(logs_dir)

            # 파일 타입 결정
            file_type = Config.LOG_TYPES.get(log_file.name, "unknown")

            logs.append(LogFileInfo(
                path=str(relative_path),
                name=log_file.name,
                size=stat.st_size,
                modified=datetime.fromtimestamp(stat.st_mtime).isoformat(),
                type=file_type
            ))

            total_size += stat.st_size

        # 최근 수정 순으로 정렬
        logs.sort(key=lambda x: x.modified, reverse=True)

        return LogListResponse(
            logs=logs,
            total_count=len(logs),
            total_size=total_size
        )

    except Exception as e:
        logger.error(f"로그 파일 목록 조회 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"로그 파일 목록 조회 실패: {str(e)}"
        )


@router.get("/logs/content", response_model=LogContentResponse)
async def get_log_content(file_path: str, max_lines: int = 1000) -> LogContentResponse:
    """
    로그 파일 내용 조회

    Args:
        file_path: 로그 파일 상대 경로 (logs/ 기준, 예: "system.log", "session-123/debug.log")
        max_lines: 최대 라인 수 (기본: 1000, 최대: 10000)

    Returns:
        LogContentResponse: 로그 파일 내용 및 정보

    Example:
        GET /api/projects/logs/content?file_path=system.log&max_lines=500
    """
    if not _current_project_path:
        raise HTTPException(
            status_code=400,
            detail="프로젝트가 선택되지 않았습니다."
        )

    # max_lines 제한
    max_lines = min(max_lines, Config.MAX_LOG_LINES)

    try:
        project_dir = Path(_current_project_path)
        project_name = project_dir.name
        logs_dir = Path.home() / ".claude-flow" / project_name / "logs"

        # 경로 검증 (디렉토리 탐색 방지)
        log_file_path = (logs_dir / file_path).resolve()
        if not str(log_file_path).startswith(str(logs_dir)):
            raise HTTPException(
                status_code=400,
                detail="잘못된 파일 경로입니다."
            )

        if not log_file_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"로그 파일을 찾을 수 없습니다: {file_path}"
            )

        # 파일 정보
        stat = log_file_path.stat()
        file_type = "unknown"
        if log_file_path.name == "system.log":
            file_type = "system"
        elif log_file_path.name == "debug.log":
            file_type = "debug"
        elif log_file_path.name == "info.log":
            file_type = "info"
        elif log_file_path.name == "error.log":
            file_type = "error"

        file_info = LogFileInfo(
            path=file_path,
            name=log_file_path.name,
            size=stat.st_size,
            modified=datetime.fromtimestamp(stat.st_mtime).isoformat(),
            type=file_type
        )

        # 파일 내용 읽기 (마지막 max_lines 라인)
        with open(log_file_path, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
            content = ''.join(lines[-max_lines:])

        return LogContentResponse(
            content=content,
            file_info=file_info
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"로그 파일 내용 조회 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"로그 파일 내용 조회 실패: {str(e)}"
        )


@router.get("/sessions/list", response_model=SessionListResponse)
async def list_sessions() -> SessionListResponse:
    """
    세션 파일 목록 조회

    현재 프로젝트의 웹 세션 디렉토리 (~/.claude-flow/{project_name}/web-sessions/)에서
    모든 세션 파일을 검색하여 반환합니다.

    Returns:
        SessionListResponse: 세션 파일 목록 및 통계

    Example:
        GET /api/projects/sessions/list

        Response: {
            "sessions": [
                {
                    "session_id": "wf-1234567890",
                    "path": "~/.claude-flow/better-llm/web-sessions/wf-1234567890.json",
                    "size": 5120,
                    "created": "2025-10-29T17:00:00",
                    "modified": "2025-10-29T17:30:00",
                    "status": "completed"
                }
            ],
            "total_count": 1,
            "total_size": 5120
        }
    """
    if not _current_project_path:
        raise HTTPException(
            status_code=400,
            detail="프로젝트가 선택되지 않았습니다."
        )

    try:
        project_dir = Path(_current_project_path)
        project_name = project_dir.name
        sessions_dir = Path.home() / ".claude-flow" / project_name / "web-sessions"

        if not sessions_dir.exists():
            return SessionListResponse(sessions=[], total_count=0, total_size=0)

        sessions = []
        total_size = 0

        # 모든 세션 파일 수집
        for session_file in sessions_dir.glob("*.json"):
            if not session_file.is_file():
                continue

            stat = session_file.stat()
            session_id = session_file.stem

            # 세션 상태 파악 (JSON 파일 읽기)
            status = "unknown"
            try:
                with open(session_file, 'r', encoding='utf-8') as f:
                    session_data = json.load(f)
                    status = session_data.get("status", "unknown")
            except Exception:
                pass

            sessions.append(SessionFileInfo(
                session_id=session_id,
                path=str(session_file),
                size=stat.st_size,
                created=datetime.fromtimestamp(stat.st_ctime).isoformat(),
                modified=datetime.fromtimestamp(stat.st_mtime).isoformat(),
                status=status
            ))

            total_size += stat.st_size

        # 최근 수정 순으로 정렬
        sessions.sort(key=lambda x: x.modified, reverse=True)

        return SessionListResponse(
            sessions=sessions,
            total_count=len(sessions),
            total_size=total_size
        )

    except Exception as e:
        logger.error(f"세션 파일 목록 조회 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"세션 파일 목록 조회 실패: {str(e)}"
        )


@router.get("/sessions/content", response_model=SessionContentResponse)
async def get_session_content(session_id: str) -> SessionContentResponse:
    """
    세션 파일 내용 조회

    Args:
        session_id: 세션 ID (예: "wf-1234567890")

    Returns:
        SessionContentResponse: 세션 파일 내용 (JSON) 및 정보

    Example:
        GET /api/projects/sessions/content?session_id=wf-1234567890
    """
    if not _current_project_path:
        raise HTTPException(
            status_code=400,
            detail="프로젝트가 선택되지 않았습니다."
        )

    try:
        project_dir = Path(_current_project_path)
        project_name = project_dir.name
        sessions_dir = Path.home() / ".claude-flow" / project_name / "web-sessions"

        session_file_path = sessions_dir / f"{session_id}.json"

        if not session_file_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"세션 파일을 찾을 수 없습니다: {session_id}"
            )

        # 파일 정보
        stat = session_file_path.stat()

        # 세션 JSON 읽기
        with open(session_file_path, 'r', encoding='utf-8') as f:
            session_data = json.load(f)

        status = session_data.get("status", "unknown")

        file_info = SessionFileInfo(
            session_id=session_id,
            path=str(session_file_path),
            size=stat.st_size,
            created=datetime.fromtimestamp(stat.st_ctime).isoformat(),
            modified=datetime.fromtimestamp(stat.st_mtime).isoformat(),
            status=status
        )

        return SessionContentResponse(
            content=session_data,
            file_info=file_info
        )

    except HTTPException:
        raise
    except json.JSONDecodeError as e:
        logger.error(f"세션 JSON 파싱 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"세션 파일 형식이 잘못되었습니다: {str(e)}"
        )
    except Exception as e:
        logger.error(f"세션 파일 내용 조회 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"세션 파일 내용 조회 실패: {str(e)}"
        )


# ============================================================================
# 워크플로우 관리 API (다중 워크플로우 지원)
# ============================================================================


@router.get("/workflows/list")
async def list_workflows() -> Dict[str, Any]:
    """
    프로젝트의 모든 워크플로우 목록 조회

    Returns:
        Dict[str, Any]: 워크플로우 목록 및 통계

    Example:
        GET /api/projects/workflows/list

        Response: {
            "workflows": [
                {
                    "name": "default",
                    "display_name": "Default Workflow",
                    "description": "기본 워크플로우",
                    "last_modified": "2025-10-30T10:00:00",
                    "size": 1024
                },
                {
                    "name": "code-review",
                    "display_name": "Code Review Workflow",
                    "description": "코드 리뷰 워크플로우",
                    "last_modified": "2025-10-30T09:00:00",
                    "size": 2048
                }
            ],
            "total_count": 2,
            "current_workflow": "default"
        }
    """
    if not _current_project_path:
        raise HTTPException(
            status_code=400,
            detail="프로젝트가 선택되지 않았습니다."
        )

    # 레거시 설정 마이그레이션 시도
    migrate_legacy_config(_current_project_path)

    workflows_dir = get_workflows_dir(_current_project_path)

    if not workflows_dir.exists():
        return {
            "workflows": [],
            "total_count": 0,
            "current_workflow": None
        }

    try:
        workflows = []

        for workflow_file in workflows_dir.glob("*.json"):
            if not workflow_file.is_file():
                continue

            try:
                stat = workflow_file.stat()
                workflow_name = workflow_file.stem

                # 워크플로우 파일에서 메타데이터 읽기
                with open(workflow_file, 'r', encoding='utf-8') as f:
                    workflow_data = json.load(f)

                workflow_info = workflow_data.get("workflow", {})
                display_name = workflow_info.get("name", workflow_name)
                description = workflow_info.get("description", "")

                workflows.append({
                    "name": workflow_name,
                    "display_name": display_name,
                    "description": description,
                    "last_modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "size": stat.st_size
                })
            except Exception as e:
                logger.warning(f"워크플로우 파일 읽기 실패: {workflow_file} - {e}")
                continue

        # 최근 수정 순으로 정렬
        workflows.sort(key=lambda x: x["last_modified"], reverse=True)

        # 현재 워크플로우 (기본값: 첫 번째)
        current_workflow = workflows[0]["name"] if workflows else None

        return {
            "workflows": workflows,
            "total_count": len(workflows),
            "current_workflow": current_workflow
        }

    except Exception as e:
        logger.error(f"워크플로우 목록 조회 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"워크플로우 목록 조회 실패: {str(e)}"
        )


@router.get("/workflows/{workflow_name}", response_model=ProjectWorkflowLoadResponse)
async def load_workflow_by_name(workflow_name: str) -> ProjectWorkflowLoadResponse:
    """
    특정 워크플로우 로드

    Args:
        workflow_name: 워크플로우 이름

    Returns:
        ProjectWorkflowLoadResponse: 로드된 워크플로우 및 메타데이터

    Example:
        GET /api/projects/workflows/default
    """
    if not _current_project_path:
        raise HTTPException(
            status_code=400,
            detail="프로젝트가 선택되지 않았습니다."
        )

    # 레거시 설정 마이그레이션 시도
    migrate_legacy_config(_current_project_path)

    workflow_path = get_workflow_path(_current_project_path, workflow_name)

    if not workflow_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"워크플로우를 찾을 수 없습니다: {workflow_name}"
        )

    try:
        with open(workflow_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)

        project_config = ProjectConfig(**config_data)

        logger.info(f"워크플로우 로드: {workflow_name} ← {workflow_path}")

        return ProjectWorkflowLoadResponse(
            project_path=_current_project_path,
            workflow=project_config.workflow,
            last_modified=project_config.metadata.get("last_modified")
        )

    except Exception as e:
        logger.error(f"워크플로우 로드 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"워크플로우 로드 실패: {str(e)}"
        )


@router.post("/workflows/{workflow_name}")
async def save_workflow_by_name(
    workflow_name: str,
    request: ProjectWorkflowSaveRequest
) -> Dict[str, str]:
    """
    워크플로우 저장 (이름 지정)

    Args:
        workflow_name: 워크플로우 이름
        request: 워크플로우 저장 요청

    Returns:
        Dict[str, str]: 응답 메시지

    Example:
        POST /api/projects/workflows/code-review
        Body: {
            "workflow": {
                "name": "Code Review Workflow",
                "nodes": [...],
                "edges": [...]
            }
        }
    """
    if not _current_project_path:
        raise HTTPException(
            status_code=400,
            detail="프로젝트가 선택되지 않았습니다."
        )

    # 워크플로우 이름 검증
    if not workflow_name or not workflow_name.strip():
        raise HTTPException(
            status_code=400,
            detail="워크플로우 이름이 비어있습니다."
        )

    # 파일명으로 사용할 수 없는 문자 검증
    if any(char in workflow_name for char in Config.INVALID_FILENAME_CHARS):
        raise HTTPException(
            status_code=400,
            detail=ErrorMessages.INVALID_FILENAME.format(chars=', '.join(Config.INVALID_FILENAME_CHARS))
        )

    # workflows 디렉토리 생성
    workflows_dir = get_workflows_dir(_current_project_path)
    workflows_dir.mkdir(parents=True, exist_ok=True)

    workflow_path = get_workflow_path(_current_project_path, workflow_name)

    # ProjectConfig 생성
    project_config = ProjectConfig(
        project_path=_current_project_path,
        workflow=request.workflow,
        metadata={
            "last_modified": datetime.now().isoformat(),
            "version": "1.0",
        }
    )

    try:
        workflow_dict = project_config.model_dump(mode='json', exclude_none=False)

        with open(workflow_path, 'w', encoding='utf-8') as f:
            json.dump(
                workflow_dict,
                f,
                ensure_ascii=False,
                indent=2
            )

        logger.info(f"워크플로우 저장: {workflow_name} → {workflow_path}")

        return {
            "message": "워크플로우가 저장되었습니다",
            "workflow_name": workflow_name,
            "config_path": str(workflow_path)
        }

    except Exception as e:
        logger.error(f"워크플로우 저장 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"워크플로우 저장 실패: {str(e)}"
        )


@router.delete("/workflows/{workflow_name}")
async def delete_workflow_by_name(workflow_name: str) -> Dict[str, str]:
    """
    워크플로우 삭제

    Args:
        workflow_name: 워크플로우 이름

    Returns:
        Dict[str, str]: 응답 메시지

    Example:
        DELETE /api/projects/workflows/code-review
    """
    if not _current_project_path:
        raise HTTPException(
            status_code=400,
            detail="프로젝트가 선택되지 않았습니다."
        )

    workflow_path = get_workflow_path(_current_project_path, workflow_name)

    if not workflow_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"워크플로우를 찾을 수 없습니다: {workflow_name}"
        )

    try:
        workflow_path.unlink()
        logger.info(f"워크플로우 삭제: {workflow_name} ({workflow_path})")

        return {
            "message": "워크플로우가 삭제되었습니다",
            "workflow_name": workflow_name
        }

    except Exception as e:
        logger.error(f"워크플로우 삭제 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"워크플로우 삭제 실패: {str(e)}"
        )


@router.put("/workflows/{old_name}/rename")
async def rename_workflow(old_name: str, new_name: str) -> Dict[str, str]:
    """
    워크플로우 이름 변경

    Args:
        old_name: 기존 워크플로우 이름
        new_name: 새 워크플로우 이름 (쿼리 파라미터)

    Returns:
        Dict[str, str]: 응답 메시지

    Example:
        PUT /api/projects/workflows/old-name/rename?new_name=new-name
    """
    if not _current_project_path:
        raise HTTPException(
            status_code=400,
            detail="프로젝트가 선택되지 않았습니다."
        )

    if not new_name or not new_name.strip():
        raise HTTPException(
            status_code=400,
            detail="새 워크플로우 이름이 비어있습니다."
        )

    # 파일명으로 사용할 수 없는 문자 검증
    if any(char in new_name for char in Config.INVALID_FILENAME_CHARS):
        raise HTTPException(
            status_code=400,
            detail=ErrorMessages.INVALID_FILENAME.format(chars=', '.join(Config.INVALID_FILENAME_CHARS))
        )

    old_path = get_workflow_path(_current_project_path, old_name)
    new_path = get_workflow_path(_current_project_path, new_name)

    if not old_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"워크플로우를 찾을 수 없습니다: {old_name}"
        )

    if new_path.exists():
        raise HTTPException(
            status_code=400,
            detail=f"이미 존재하는 워크플로우 이름입니다: {new_name}"
        )

    try:
        shutil.move(str(old_path), str(new_path))
        logger.info(f"워크플로우 이름 변경: {old_name} → {new_name}")

        return {
            "message": "워크플로우 이름이 변경되었습니다",
            "old_name": old_name,
            "new_name": new_name
        }

    except Exception as e:
        logger.error(f"워크플로우 이름 변경 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"워크플로우 이름 변경 실패: {str(e)}"
        )
