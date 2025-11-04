"""
설정 로더 구현

JsonConfigLoader: JSON 파일에서 설정 로드
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Dict, Any

import yaml

from src.domain.models import AgentConfig
from src.infrastructure.logging import get_logger

logger = get_logger(__name__, component="ConfigLoader")


@dataclass
class SystemConfig:
    """
    시스템 설정 구현

    JSON 파일에서 로드된 설정
    딕셔너리 접근도 지원 (하위 호환성)
    """
    # Manager 설정
    manager_model: str = "claude-sonnet-4-5-20250929"
    max_history_messages: int = 20
    max_turns: int = 10

    # Performance 설정
    enable_caching: bool = True
    worker_retry_enabled: bool = True
    worker_retry_max_attempts: int = 3
    worker_retry_base_delay: float = 1.0

    # Security 설정
    max_input_length: int = 5000
    enable_input_validation: bool = True

    # Logging 설정
    log_level: str = "INFO"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    enable_structured_logging: bool = False

    _raw_data: dict = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self):
        """dataclass 초기화 후 처리"""
        # _raw_data는 field로 정의되어 자동 초기화됨
        # 추가 초기화 로직이 필요하면 여기에 작성
        pass

    def get(self, key: str, default=None):
        """
        딕셔너리처럼 get() 메서드 제공

        Args:
            key: 설정 키
            default: 기본값

        Returns:
            설정 값 또는 기본값
        """
        # 먼저 dataclass 필드 확인
        if hasattr(self, key):
            return getattr(self, key)

        # _raw_data에서 확인
        return self._raw_data.get(key, default)

    def __getitem__(self, key: str):
        """
        딕셔너리처럼 [] 접근 제공

        Args:
            key: 설정 키

        Returns:
            설정 값

        Raises:
            KeyError: 키가 없을 경우
        """
        if hasattr(self, key):
            return getattr(self, key)

        if key in self._raw_data:
            return self._raw_data[key]
        raise KeyError(f"설정 키를 찾을 수 없습니다: {key}")


class JsonConfigLoader:
    """
    JSON 설정 로더

    config/agent_config.json, config/system_config.json에서 설정 로드
    prompts/ 디렉토리 자동 스캔 기능 추가
    """

    def __init__(self, project_root: Path):
        """
        Args:
            project_root: 프로젝트 루트 디렉토리
        """
        self.project_root = project_root
        self.agent_config_path = project_root / "config" / "agent_config.json"
        self.system_config_path = project_root / "config" / "system_config.json"
        self.prompts_dir = project_root / "prompts"

    def _parse_prompt_metadata(self, prompt_file: Path) -> Optional[Dict[str, Any]]:
        """
        프롬프트 파일에서 YAML Front Matter 메타데이터 추출

        형식:
        ---
        role: 역할 설명
        allowed_tools:
          - read
          - write
        model: claude-sonnet-4-5-20250929
        thinking: true
        ---

        [프롬프트 내용...]

        Args:
            prompt_file: 프롬프트 파일 경로

        Returns:
            메타데이터 딕셔너리 (없으면 None)
        """
        try:
            content = prompt_file.read_text(encoding='utf-8')

            # YAML Front Matter 정규식 패턴
            pattern = r'^---\s*\n(.*?)\n---\s*\n'
            match = re.match(pattern, content, re.DOTALL)

            if not match:
                return None

            yaml_content = match.group(1)
            metadata = yaml.safe_load(yaml_content)

            return metadata if isinstance(metadata, dict) else None

        except Exception as e:
            logger.warning(
                "Failed to parse prompt metadata",
                prompt_file=str(prompt_file),
                error=str(e)
            )
            return None

    def _scan_prompts_directory(self) -> List[AgentConfig]:
        """
        prompts/ 디렉토리 스캔하여 AgentConfig 자동 생성

        YAML Front Matter가 있는 파일: 메타데이터 사용
        YAML Front Matter가 없는 파일: 기본값 사용

        Returns:
            AgentConfig 리스트
        """
        if not self.prompts_dir.exists():
            logger.warning(f"Prompts directory not found: {self.prompts_dir}")
            return []

        agent_configs = []
        prompt_files = sorted(self.prompts_dir.glob("*.txt"))

        for prompt_file in prompt_files:
            # 파일명에서 이름 추출 (확장자 제외)
            name = prompt_file.stem

            # local.txt는 빈 파일이므로 스킵
            if name == "local":
                continue

            # 메타데이터 파싱
            metadata = self._parse_prompt_metadata(prompt_file)

            # 기본값
            default_role = f"{name} 전문가"
            default_tools = ["read", "write", "edit", "glob", "grep"]
            default_model = "claude-sonnet-4-5-20250929"
            default_thinking = True

            # 메타데이터가 있으면 사용, 없으면 기본값
            if metadata:
                role = metadata.get("role", default_role)
                allowed_tools = metadata.get("allowed_tools", default_tools)
                model = metadata.get("model", default_model)
                thinking = metadata.get("thinking", default_thinking)
            else:
                role = default_role
                allowed_tools = default_tools
                model = default_model
                thinking = default_thinking

            # AgentConfig 생성
            config = AgentConfig(
                name=name,
                role=role,
                system_prompt=f"prompts/{prompt_file.name}",  # 상대 경로
                allowed_tools=allowed_tools,
                model=model,
                thinking=thinking
            )

            agent_configs.append(config)
            logger.debug(
                "Scanned prompt file",
                name=name,
                has_metadata=metadata is not None
            )

        return agent_configs

    def load_agent_configs(self, auto_scan: bool = True) -> List[AgentConfig]:
        """
        에이전트 설정 로드 (하이브리드 방식)

        1. agent_config.json 로드 (있는 경우)
        2. prompts/ 디렉토리 자동 스캔 (auto_scan=True 시)
        3. agent_config.json에 없는 프롬프트만 자동 추가

        Args:
            auto_scan: prompts/ 디렉토리 자동 스캔 여부 (기본값: True)

        Returns:
            AgentConfig 리스트

        Raises:
            ValueError: 설정 파일 형식이 잘못된 경우
        """
        agent_configs = []
        config_names = set()

        # 1. agent_config.json 로드 (선택 사항)
        if self.agent_config_path.exists():
            try:
                with open(self.agent_config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # 유효성 검증
                if "agents" in data and isinstance(data["agents"], list):
                    agents_data = data["agents"]

                    # AgentConfig 객체 생성
                    for agent_data in agents_data:
                        # 필수 필드 검증
                        required_fields = ["name", "role", "system_prompt_file", "allowed_tools", "model"]
                        for field in required_fields:
                            if field not in agent_data:
                                logger.warning(
                                    f"에이전트 설정에 필수 필드 '{field}'가 없습니다. 스킵합니다.",
                                    agent_data=agent_data
                                )
                                continue

                        # system_prompt_file을 system_prompt로 변환
                        agent_data_copy = agent_data.copy()
                        agent_data_copy["system_prompt"] = agent_data_copy.pop("system_prompt_file")

                        config = AgentConfig.from_dict(agent_data_copy)
                        agent_configs.append(config)
                        config_names.add(config.name)

                    logger.info("Agent configs loaded from JSON", count=len(agent_configs))

            except json.JSONDecodeError as e:
                logger.error("JSON parsing failed", config_path=str(self.agent_config_path), error=str(e))
                raise ValueError(f"JSON 파싱 실패: {e}")
            except Exception as e:
                logger.error("Config loading failed", config_path=str(self.agent_config_path), error=str(e))
                # agent_config.json 로드 실패 시 자동 스캔으로 폴백
                logger.warning("agent_config.json 로드 실패. prompts/ 자동 스캔으로 폴백합니다.")

        # 2. prompts/ 디렉토리 자동 스캔
        if auto_scan:
            scanned_configs = self._scan_prompts_directory()

            # agent_config.json에 없는 프롬프트만 추가
            for config in scanned_configs:
                if config.name not in config_names:
                    agent_configs.append(config)
                    config_names.add(config.name)
                    logger.info(
                        "Auto-added agent from prompts directory",
                        name=config.name,
                        role=config.role
                    )

        # 3. 결과 로깅
        total_count = len(agent_configs)
        if total_count == 0:
            logger.warning("No agent configs loaded. Check agent_config.json and prompts/ directory.")
        else:
            logger.info("Total agent configs loaded", total=total_count)

        return agent_configs

    def load_system_config(self) -> SystemConfig:
        """
        시스템 설정 로드

        Returns:
            시스템 설정 객체

        Raises:
            Exception: 로드 실패 시 (기본값 사용)
        """
        if not self.system_config_path.exists():
            logger.warning(f"시스템 설정 파일이 없습니다: {self.system_config_path}. 기본값 사용.")
            return SystemConfig()

        try:
            with open(self.system_config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            manager = data.get("manager", {})
            performance = data.get("performance", {})
            security = data.get("security", {})
            logging_config = data.get("logging", {})

            config = SystemConfig(
                manager_model=manager.get("model", "claude-sonnet-4-5-20250929"),
                max_history_messages=manager.get("max_history_messages", 20),
                max_turns=manager.get("max_turns", 10),
                enable_caching=performance.get("enable_caching", True),
                worker_retry_enabled=performance.get("worker_retry_enabled", True),
                worker_retry_max_attempts=performance.get("worker_retry_max_attempts", 3),
                worker_retry_base_delay=performance.get("worker_retry_base_delay", 1.0),
                max_input_length=security.get("max_input_length", 5000),
                enable_input_validation=security.get("enable_input_validation", True),
                log_level=logging_config.get("level", "INFO"),
                log_format=logging_config.get("format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"),
                enable_structured_logging=logging_config.get("enable_structured_logging", False)
            )

            # 원본 데이터 저장 (딕셔너리 접근용)
            config._raw_data = data

            return config

        except Exception as e:
            logger.error(f"시스템 설정 로드 실패: {e}. 기본값 사용.")
            return SystemConfig()


def load_system_config() -> SystemConfig:
    """
    시스템 설정을 SystemConfig 객체로 로드 (간편 함수)

    Returns:
        SystemConfig: 설정 객체 (파일이 없으면 기본 설정 반환)

    Raises:
        json.JSONDecodeError: JSON 파싱 실패 시
        OSError: 파일 읽기 실패 시 (권한 문제 등)
    """
    from .validator import get_project_root

    config_path = get_project_root() / "config" / "system_config.json"

    if not config_path.exists():
        logger.warning(f"Config file not found: {config_path}. Using default config.")
        return SystemConfig()

    try:
        # JsonConfigLoader를 사용하여 SystemConfig 객체 생성
        loader = JsonConfigLoader(get_project_root())
        return loader.load_system_config()
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse config JSON: {config_path} - {e}")
        raise
    except OSError as e:
        logger.error(f"Failed to read config file: {config_path} - {e}")
        raise
