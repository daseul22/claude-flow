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


@dataclass
class FeedbackLoopDefaults:
    """피드백 루프 기본 설정"""
    enabled: bool = False
    max_iterations: int = 3
    condition_model: str = "claude-haiku-4-5-20251001"


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

