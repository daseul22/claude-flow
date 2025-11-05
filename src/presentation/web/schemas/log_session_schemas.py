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
