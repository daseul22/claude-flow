"""TUI 설정 관리"""

import json
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict


@dataclass
class DisplaySettings:
    """화면 표시 설정"""
    show_statusbar: bool = True
    show_timestamps: bool = True
    show_token_counts: bool = True
    sidebar_visible: bool = False
    # Thinking 블록 관련
    enable_thinking: bool = True  # Thinking 활성화 여부
    show_thinking_full: bool = False  # False: 요약만, True: 전체 표시


@dataclass
class FeedbackLoopDefaults:
    """피드백 루프 기본 설정"""
    enabled: bool = False
    max_iterations: int = 3
    condition_model: str = "claude-haiku-4-5-20251001"
    quality_threshold: float = 0.8  # 품질 임계값 (0.0 ~ 1.0, 기본: 80점)


@dataclass
class LoggingSettings:
    """로깅 설정"""
    auto_save: bool = True
    log_level: str = "INFO"
    max_file_size_mb: int = 10
    retention_days: int = 30


@dataclass
class ShortcutSettings:
    """키보드 단축키 설정"""
    new_session: str = "ctrl+n"
    open_session: str = "ctrl+o"
    change_directory: str = "ctrl+d"
    project_info: str = "ctrl+i"
    clear_screen: str = "ctrl+l"


@dataclass
class AppConfig:
    """TUI 앱 전체 설정"""
    theme: str = "dark"
    display: DisplaySettings = None
    default_model: str = "claude-sonnet-4.5"
    feedback_loop_defaults: FeedbackLoopDefaults = None
    logging: LoggingSettings = None
    shortcuts: ShortcutSettings = None

    def __post_init__(self):
        if self.display is None:
            self.display = DisplaySettings()
        if self.feedback_loop_defaults is None:
            self.feedback_loop_defaults = FeedbackLoopDefaults()
        if self.logging is None:
            self.logging = LoggingSettings()
        if self.shortcuts is None:
            self.shortcuts = ShortcutSettings()


class ConfigManager:
    """설정 파일 관리자"""

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or Path.home() / ".claude-flow" / "config.json"
        self.config: AppConfig = self.load()

    def load(self) -> AppConfig:
        """설정 파일 로드"""
        if not self.config_path.exists():
            # 기본 설정 반환 및 즉시 저장
            config = AppConfig()
            try:
                self.config = config
                self.save()  # 기본 설정 파일 생성
            except Exception as e:
                print(f"⚠️  기본 설정 파일 생성 실패: {e}")
            return config

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            return AppConfig(
                theme=data.get("theme", "dark"),
                display=DisplaySettings(**data.get("display", {})),
                default_model=data.get("default_model", "claude-sonnet-4.5"),
                feedback_loop_defaults=FeedbackLoopDefaults(
                    **data.get("feedback_loop_defaults", {})
                ),
                logging=LoggingSettings(**data.get("logging", {})),
                shortcuts=ShortcutSettings(**data.get("shortcuts", {})),
            )
        except Exception as e:
            print(f"⚠️  설정 파일 로드 실패: {e}. 기본 설정 사용")
            import traceback
            traceback.print_exc()
            return AppConfig()

    def save(self):
        """설정 파일 저장"""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        config_dict = {
            "theme": self.config.theme,
            "display": asdict(self.config.display),
            "default_model": self.config.default_model,
            "feedback_loop_defaults": asdict(self.config.feedback_loop_defaults),
            "logging": asdict(self.config.logging),
            "shortcuts": asdict(self.config.shortcuts),
        }

        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(config_dict, f, indent=2, ensure_ascii=False)

    def get_claude_flow_dir(self) -> Path:
        """Claude Flow 루트 디렉토리 반환"""
        return Path.home() / ".claude-flow"

    def get_project_sessions_dir(self, project_name: str) -> Path:
        """프로젝트 세션 디렉토리 반환"""
        return self.get_claude_flow_dir() / project_name / "sessions"

    def get_project_logs_dir(self, project_name: str) -> Path:
        """프로젝트 로그 디렉토리 반환"""
        return self.get_claude_flow_dir() / project_name / "logs"

    def get_project_settings_path(self, project_name: str) -> Path:
        """프로젝트 설정 파일 경로 반환"""
        return self.get_claude_flow_dir() / project_name / "settings.json"

    def load_project_settings(self, project_name: str) -> dict:
        """프로젝트별 설정 로드 (없으면 전역 기본값 반환)"""
        settings_path = self.get_project_settings_path(project_name)

        # 기본값 딕셔너리 (기존 피드백 루프 설정)
        defaults = {
            "feedback_loop_enabled": self.config.feedback_loop_defaults.enabled,
            "feedback_loop_max_iterations": self.config.feedback_loop_defaults.max_iterations,
            "feedback_loop_condition_model": self.config.feedback_loop_defaults.condition_model,
            "feedback_loop_quality_threshold": self.config.feedback_loop_defaults.quality_threshold,
        }

        if not settings_path.exists():
            # 프로젝트 설정이 없으면 전역 기본값 반환
            return defaults

        try:
            with open(settings_path, "r", encoding="utf-8") as f:
                project_settings = json.load(f)

            # 기본값으로 시작한 후, 프로젝트 설정으로 업데이트
            # 이렇게 하면 새로운 키(예: smart_feedback_*)도 자동으로 로드됨
            result = defaults.copy()

            # 기존 키는 기본값 적용
            for key in defaults.keys():
                if key in project_settings:
                    result[key] = project_settings[key]

            # 새로운 키는 그대로 추가 (예: smart_feedback_enabled)
            for key, value in project_settings.items():
                if key not in result:
                    result[key] = value

            return result

        except Exception as e:
            print(f"⚠️  프로젝트 설정 로드 실패: {e}. 기본 설정 사용")
            return defaults

    def save_project_settings(self, project_name: str, settings: dict):
        """프로젝트별 설정 저장"""
        settings_path = self.get_project_settings_path(project_name)
        settings_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(settings_path, "w", encoding="utf-8") as f:
                json.dump(settings, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"⚠️  프로젝트 설정 저장 실패: {e}")

