"""설정 관리 헬퍼 클래스들"""

from typing import Dict, List, Any
from pathlib import Path

from ..config.settings import ConfigManager
from .session_manager import SessionManager
from .feedback_loop_improved import ImprovedFeedbackLoop


class SettingsChangeDetector:
    """설정 변경 감지기"""

    def __init__(self, old_settings: Dict[str, Any], new_settings: Dict[str, Any]):
        """
        Args:
            old_settings: 기존 설정 딕셔너리
            new_settings: 새 설정 딕셔너리
        """
        self.old = old_settings
        self.new = new_settings

    def get_changes(self) -> List[str]:
        """변경된 설정 목록 반환 (사람이 읽을 수 있는 형식)"""
        changes = []

        # 모델 변경
        if self.old.get("model") != self.new.get("model"):
            changes.append(f"모델: {self.old.get('model')} → {self.new.get('model')}")

        # 피드백 루프 활성화 변경
        if self.old.get("feedback_loop_enabled") != self.new.get("feedback_loop_enabled"):
            changes.append(
                f"피드백 루프: {self.old.get('feedback_loop_enabled')} → {self.new.get('feedback_loop_enabled')}"
            )

        # 최대 반복 횟수 변경
        if self.old.get("max_iterations") != self.new.get("max_iterations"):
            changes.append(
                f"최대 반복: {self.old.get('max_iterations')} → {self.new.get('max_iterations')}"
            )

        # 조건 모델 변경
        if self.old.get("condition_model") != self.new.get("condition_model"):
            changes.append(
                f"조건 모델: {self.old.get('condition_model')} → {self.new.get('condition_model')}"
            )

        return changes

    def has_changes(self) -> bool:
        """변경사항 존재 여부"""
        return len(self.get_changes()) > 0


class SettingsApplicator:
    """설정 적용기"""

    def __init__(self, config_manager: ConfigManager, session_manager: SessionManager, project_name: str):
        """
        Args:
            config_manager: 설정 관리자
            session_manager: 세션 관리자
            project_name: 프로젝트 이름 (프로젝트별 설정 저장에 사용)
        """
        self.config = config_manager
        self.session = session_manager
        self.project_name = project_name

    def apply_global_settings(self, settings: Dict[str, Any]) -> None:
        """전역 설정 적용 (config 파일)"""
        self.config.config.default_model = settings["model"]
        self.config.config.feedback_loop_defaults.enabled = settings["feedback_loop_enabled"]
        self.config.config.feedback_loop_defaults.max_iterations = settings["max_iterations"]
        self.config.config.feedback_loop_defaults.condition_model = settings["condition_model"]
        self.config.config.feedback_loop_defaults.quality_threshold = settings.get("quality_threshold", 0.8)
        self.config.config.display.show_statusbar = settings["show_statusbar"]
        self.config.config.display.show_timestamps = settings["show_timestamps"]
        self.config.config.display.show_token_counts = settings["show_token_counts"]
        self.config.config.display.enable_thinking = settings["enable_thinking"]
        self.config.config.display.show_thinking_full = settings["show_thinking_full"]

    def apply_session_settings(self, settings: Dict[str, Any]) -> bool:
        """세션 설정 적용 (현재 세션)

        Returns:
            세션 저장 성공 여부
        """
        if not self.session.current_session:
            return True  # 세션이 없으면 성공으로 처리

        session = self.session.current_session
        session.feedback_loop.enabled = settings["feedback_loop_enabled"]
        session.feedback_loop.condition_prompt = settings.get("condition_prompt", "")
        session.feedback_loop.max_iterations = settings["max_iterations"]
        session.feedback_loop.condition_model = settings["condition_model"]
        session.feedback_loop.feedback_input = settings.get("feedback_input", "")

        # 프로젝트별 설정 저장 (피드백 루프 설정)
        self.save_project_settings(settings)

        # 세션 저장
        return self.session.save_session(session)

    def save_project_settings(self, settings: Dict[str, Any]) -> None:
        """프로젝트별 설정 저장 (피드백 루프 설정만)"""
        project_settings = {
            "feedback_loop_enabled": settings["feedback_loop_enabled"],
            "feedback_loop_max_iterations": settings["max_iterations"],
            "feedback_loop_condition_model": settings["condition_model"],
            "feedback_loop_quality_threshold": settings.get("quality_threshold", 0.8),
        }
        self.config.save_project_settings(self.project_name, project_settings)

    def create_feedback_loop(self, settings: Dict[str, Any], project_path: Path) -> ImprovedFeedbackLoop:
        """피드백 루프 인스턴스 생성 (개선된 버전)"""
        return ImprovedFeedbackLoop(
            project_path=project_path,
            condition_model=settings["condition_model"],
            max_iterations=settings["max_iterations"],
            quality_threshold=settings.get("quality_threshold", 0.8),  # 기본값: 80점
        )

    def save_config(self) -> None:
        """설정 파일 저장"""
        self.config.save()

        # 저장 성공 확인
        if not self.config.config_path.exists():
            raise FileNotFoundError(f"설정 파일이 생성되지 않았습니다: {self.config.config_path}")
