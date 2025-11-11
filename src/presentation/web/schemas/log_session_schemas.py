"""
로그, 세션 및 보고서 스키마

로그 파일, 세션 및 보고서 뷰어 관련 스키마를 정의합니다.
"""

from typing import List, Dict, Any
from pydantic import BaseModel, Field


class LogFileInfo(BaseModel):
    """
    로그 파일 정보

    Attributes:
        path: 파일 상대 경로 (logs/ 기준)
        name: 파일명
        size: 파일 크기 (bytes)
        modified: 수정 시간 (ISO 8601)
        type: 파일 타입 (system, debug, info, error)
    """

    path: str = Field(..., description="파일 상대 경로")
    name: str = Field(..., description="파일명")
    size: int = Field(..., description="파일 크기 (bytes)")
    modified: str = Field(..., description="수정 시간 (ISO 8601)")
    type: str = Field(..., description="파일 타입 (system, debug, info, error)")


class SessionFileInfo(BaseModel):
    """
    세션 파일 정보

    Attributes:
        session_id: 세션 ID
        path: 파일 경로
        size: 파일 크기 (bytes)
        created: 생성 시간 (ISO 8601)
        modified: 수정 시간 (ISO 8601)
        status: 세션 상태 (running, completed, error, cancelled)
    """

    session_id: str = Field(..., description="세션 ID")
    path: str = Field(..., description="파일 경로")
    size: int = Field(..., description="파일 크기 (bytes)")
    created: str = Field(..., description="생성 시간 (ISO 8601)")
    modified: str = Field(..., description="수정 시간 (ISO 8601)")
    status: str = Field(..., description="세션 상태")


class LogListResponse(BaseModel):
    """
    로그 파일 목록 응답

    Attributes:
        logs: 로그 파일 목록
        total_count: 전체 파일 개수
        total_size: 전체 파일 크기 (bytes)
    """

    logs: List[LogFileInfo] = Field(..., description="로그 파일 목록")
    total_count: int = Field(..., description="전체 파일 개수")
    total_size: int = Field(..., description="전체 파일 크기 (bytes)")


class SessionListResponse(BaseModel):
    """
    세션 파일 목록 응답

    Attributes:
        sessions: 세션 파일 목록
        total_count: 전체 세션 개수
        total_size: 전체 파일 크기 (bytes)
    """

    sessions: List[SessionFileInfo] = Field(..., description="세션 파일 목록")
    total_count: int = Field(..., description="전체 세션 개수")
    total_size: int = Field(..., description="전체 파일 크기 (bytes)")


class LogContentResponse(BaseModel):
    """
    로그 파일 내용 응답

    Attributes:
        content: 로그 파일 내용
        file_info: 파일 정보
    """

    content: str = Field(..., description="로그 파일 내용")
    file_info: LogFileInfo = Field(..., description="파일 정보")


class SessionContentResponse(BaseModel):
    """
    세션 파일 내용 응답

    Attributes:
        content: 세션 파일 내용 (JSON)
        file_info: 파일 정보
    """

    content: Dict[str, Any] = Field(..., description="세션 파일 내용 (JSON)")
    file_info: SessionFileInfo = Field(..., description="파일 정보")


class ReportFileInfo(BaseModel):
    """
    보고서 파일 정보

    Attributes:
        path: 파일 상대 경로 (reports/ 기준)
        name: 파일명
        size: 파일 크기 (bytes)
        modified: 수정 시간 (ISO 8601)
        node_id: 노드 ID (파일명에서 추출)
        extension: 파일 확장자 (md, txt, json, etc)
    """

    path: str = Field(..., description="파일 상대 경로")
    name: str = Field(..., description="파일명")
    size: int = Field(..., description="파일 크기 (bytes)")
    modified: str = Field(..., description="수정 시간 (ISO 8601)")
    node_id: str = Field(..., description="노드 ID")
    extension: str = Field(..., description="파일 확장자")


class ReportListResponse(BaseModel):
    """
    보고서 파일 목록 응답

    Attributes:
        reports: 보고서 파일 목록
        total_count: 전체 파일 개수
        total_size: 전체 파일 크기 (bytes)
    """

    reports: List[ReportFileInfo] = Field(..., description="보고서 파일 목록")
    total_count: int = Field(..., description="전체 파일 개수")
    total_size: int = Field(..., description="전체 파일 크기 (bytes)")


class ReportContentResponse(BaseModel):
    """
    보고서 파일 내용 응답

    Attributes:
        content: 보고서 파일 내용
        file_info: 파일 정보
    """

    content: str = Field(..., description="보고서 파일 내용")
    file_info: ReportFileInfo = Field(..., description="파일 정보")


# ============================================================================
# 세션 통계 및 컨텍스트 윈도우 추적
# ============================================================================


class TokenSnapshot(BaseModel):
    """
    특정 시점의 토큰 사용량 스냅샷

    Attributes:
        timestamp: 스냅샷 생성 시간 (ISO 8601)
        input_tokens: 입력 토큰 수 (이번 실행)
        output_tokens: 출력 토큰 수 (이번 실행)
        cache_read_tokens: 캐시 읽기 토큰 수
        cache_creation_tokens: 캐시 생성 토큰 수
        cumulative_input: 누적 입력 토큰 (세션 시작부터)
        cumulative_output: 누적 출력 토큰 (세션 시작부터)
        cumulative_total: 누적 총 토큰 (세션 시작부터)
    """

    timestamp: str = Field(..., description="스냅샷 생성 시간 (ISO 8601)")
    input_tokens: int = Field(default=0, description="입력 토큰 수 (이번 실행)")
    output_tokens: int = Field(default=0, description="출력 토큰 수 (이번 실행)")
    cache_read_tokens: int = Field(default=0, description="캐시 읽기 토큰 수")
    cache_creation_tokens: int = Field(default=0, description="캐시 생성 토큰 수")
    cumulative_input: int = Field(default=0, description="누적 입력 토큰")
    cumulative_output: int = Field(default=0, description="누적 출력 토큰")
    cumulative_total: int = Field(default=0, description="누적 총 토큰")


class CompactionEvent(BaseModel):
    """
    컨텍스트 윈도우 컴팩션 이벤트

    Attributes:
        timestamp: 컴팩션 발생 시간 (ISO 8601)
        trigger: 컴팩션 트리거 원인 (cache_creation, cache_reset, context_limit)
        before_tokens: 컴팩션 전 누적 토큰 수
        after_tokens: 컴팩션 후 누적 토큰 수
        reduction_tokens: 감소한 토큰 수
        cache_creation_tokens: 새로 생성된 캐시 토큰 수
    """

    timestamp: str = Field(..., description="컴팩션 발생 시간 (ISO 8601)")
    trigger: str = Field(..., description="컴팩션 트리거 원인")
    before_tokens: int = Field(..., description="컴팩션 전 누적 토큰 수")
    after_tokens: int = Field(..., description="컴팩션 후 누적 토큰 수")
    reduction_tokens: int = Field(..., description="감소한 토큰 수")
    cache_creation_tokens: int = Field(default=0, description="새로 생성된 캐시 토큰 수")


class SessionStats(BaseModel):
    """
    세션별 토큰 사용량 통계

    Attributes:
        session_id: SDK 세션 ID
        node_id: 노드 ID
        agent_name: 에이전트 이름
        model: 사용된 모델 (예: claude-sonnet-4-5-20250929)
        token_history: 토큰 사용량 이력 (시계열)
        compaction_events: 컴팩션 이벤트 목록
        cumulative_input_tokens: 누적 입력 토큰
        cumulative_output_tokens: 누적 출력 토큰
        cumulative_cache_read_tokens: 누적 캐시 읽기 토큰
        cumulative_cache_creation_tokens: 누적 캐시 생성 토큰
        cumulative_total_tokens: 누적 총 토큰
        estimated_context_window_usage: 컨텍스트 윈도우 사용률 (0.0 ~ 1.0)
        created_at: 세션 생성 시간 (ISO 8601)
        last_updated_at: 마지막 업데이트 시간 (ISO 8601)
    """

    session_id: str = Field(..., description="SDK 세션 ID")
    node_id: str = Field(..., description="노드 ID")
    agent_name: str = Field(..., description="에이전트 이름")
    model: str = Field(default="claude-sonnet-4-5-20250929", description="사용된 모델")
    token_history: List[TokenSnapshot] = Field(default_factory=list, description="토큰 사용량 이력")
    compaction_events: List[CompactionEvent] = Field(
        default_factory=list, description="컴팩션 이벤트 목록"
    )
    cumulative_input_tokens: int = Field(default=0, description="누적 입력 토큰")
    cumulative_output_tokens: int = Field(default=0, description="누적 출력 토큰")
    cumulative_cache_read_tokens: int = Field(default=0, description="누적 캐시 읽기 토큰")
    cumulative_cache_creation_tokens: int = Field(default=0, description="누적 캐시 생성 토큰")
    cumulative_total_tokens: int = Field(default=0, description="누적 총 토큰")
    estimated_context_window_usage: float = Field(
        default=0.0, ge=0.0, le=1.0, description="컨텍스트 윈도우 사용률 (0.0 ~ 1.0)"
    )
    created_at: str = Field(..., description="세션 생성 시간 (ISO 8601)")
    last_updated_at: str = Field(..., description="마지막 업데이트 시간 (ISO 8601)")


class SessionStatsResponse(BaseModel):
    """
    세션 통계 조회 응답

    Attributes:
        stats: 세션 통계 정보
        model_context_limit: 모델의 컨텍스트 윈도우 한계 (토큰 수)
    """

    stats: SessionStats = Field(..., description="세션 통계 정보")
    model_context_limit: int = Field(default=200000, description="모델의 컨텍스트 윈도우 한계")
