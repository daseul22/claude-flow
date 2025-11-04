"""
워크플로우 시스템 상수 정의

매직 넘버와 하드코딩된 문자열을 중앙 집중화하여 관리합니다.
"""

from pathlib import Path
from typing import Dict, Set


class WorkflowConfig:
    """워크플로우 실행 관련 상수"""

    # 모델 설정
    HAIKU_MODEL = "claude-haiku-4-5-20251001"

    # 입력 제한
    LLM_INPUT_LIMIT = 5000
    CONDITION_OUTPUT_LIMIT = 200

    # 타임아웃 (초)
    NODE_SESSION_TIMEOUT = 300  # 5분
    DESIGN_SESSION_TIMEOUT = 300  # 5분

    # 재시도 설정
    MAX_CONDITION_ITERATIONS = 10

    # SSE 설정
    SSE_CHUNK_SIZE = 4096


class ProjectConfig:
    """프로젝트 관리 관련 상수"""

    # 디렉토리 경로
    BASE_DIR = Path.home() / ".claude-flow"
    WORKFLOWS_DIR = BASE_DIR / "workflows"
    SESSIONS_DIR_NAME = "web-sessions"
    LOGS_DIR_NAME = "logs"

    # Claude CLI 세션 디렉토리
    CLAUDE_SESSION_DIR = Path.home() / ".claude" / "projects"

    # 로그 파일 타입 매핑
    LOG_TYPES: Dict[str, str] = {
        "system.log": "system",
        "debug.log": "debug",
        "info.log": "info",
        "error.log": "error",
        "claude-flow.log": "workflow",
        "claude-flow-error.log": "error",
    }

    # 파일명 유효성 검사
    INVALID_FILENAME_CHARS: Set[str] = frozenset(["/", "\\", ":", "*", "?", '"', "<", ">", "|"])

    # 제한
    MAX_LOG_LINES = 10000
    MAX_WORKFLOW_NAME_LENGTH = 255


class NodeConfig:
    """노드 실행 관련 상수"""

    # 노드 타입
    NODE_TYPE_INPUT = "input"
    NODE_TYPE_WORKER = "worker"
    NODE_TYPE_CONDITION = "condition"
    NODE_TYPE_MERGE = "merge"

    # Condition 노드 타입
    CONDITION_TYPE_CONTAINS = "contains"
    CONDITION_TYPE_REGEX = "regex"
    CONDITION_TYPE_LENGTH = "length"
    CONDITION_TYPE_LLM = "llm"
    CONDITION_TYPE_CUSTOM = "custom"

    # Merge 노드 전략
    MERGE_STRATEGY_CONCATENATE = "concatenate"
    MERGE_STRATEGY_FIRST = "first"
    MERGE_STRATEGY_LAST = "last"
    MERGE_STRATEGY_CUSTOM = "custom"


class EventConfig:
    """이벤트 타입 상수"""

    # 워크플로우 이벤트
    WORKFLOW_START = "workflow_start"
    WORKFLOW_COMPLETE = "workflow_complete"
    WORKFLOW_ERROR = "workflow_error"

    # 노드 이벤트
    NODE_START = "node_start"
    NODE_PROGRESS = "node_progress"
    NODE_OUTPUT = "node_output"
    NODE_COMPLETE = "node_complete"
    NODE_ERROR = "node_error"

    # 특수 이벤트
    ASK_USER = "ask_user"
    TOKEN_USAGE = "token_usage"


class ErrorMessages:
    """에러 메시지 상수"""

    # 프로젝트 관련
    PROJECT_NOT_SELECTED = "프로젝트가 선택되지 않았습니다"
    PROJECT_NOT_EXIST = "디렉토리가 존재하지 않습니다: {path}"
    PROJECT_NOT_DIR = "디렉토리가 아닙니다: {path}"

    # 워크플로우 관련
    WORKFLOW_EMPTY = "워크플로우가 비어있습니다"
    WORKFLOW_NO_INPUT = "Input 노드가 없습니다"
    WORKFLOW_CIRCULAR = "순환 참조가 감지되었습니다"
    WORKFLOW_NOT_FOUND = "워크플로우를 찾을 수 없습니다: {name}"

    # 파일명 관련
    INVALID_FILENAME = "잘못된 파일명입니다: {chars}"
    FILENAME_TOO_LONG = f"파일명이 너무 깁니다 (최대 {ProjectConfig.MAX_WORKFLOW_NAME_LENGTH}자)"

    # 세션 관련
    SESSION_NOT_FOUND = "세션을 찾을 수 없습니다: {session_id}"
    SESSION_ALREADY_RUNNING = "세션이 이미 실행 중입니다: {session_id}"

    # 노드 관련
    NODE_NOT_FOUND = "노드를 찾을 수 없습니다: {node_id}"
    AGENT_NOT_FOUND = "Agent를 찾을 수 없습니다: {agent_name}"
