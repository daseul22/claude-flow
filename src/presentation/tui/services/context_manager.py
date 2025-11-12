"""컨텍스트 관리자: 파일/디렉토리를 세션 컨텍스트에 추가하고 관리"""

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Dict, Optional, Set
from datetime import datetime
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class ContextFile:
    """컨텍스트에 포함된 파일 정보"""

    path: str
    label: Optional[str] = None
    added_at: str = field(default_factory=lambda: datetime.now().isoformat())
    is_directory: bool = False
    size_bytes: int = 0
    enabled: bool = True  # 일시적으로 비활성화 가능

    def to_dict(self) -> Dict:
        """딕셔너리로 변환"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> "ContextFile":
        """딕셔너리에서 생성"""
        return cls(**data)


@dataclass
class ContextPreset:
    """컨텍스트 프리셋 (자주 사용하는 파일 조합)"""

    name: str
    description: str
    files: List[ContextFile]
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict:
        """딕셔너리로 변환"""
        return {
            "name": self.name,
            "description": self.description,
            "files": [f.to_dict() for f in self.files],
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "ContextPreset":
        """딕셔너리에서 생성"""
        return cls(
            name=data["name"],
            description=data["description"],
            files=[ContextFile.from_dict(f) for f in data["files"]],
            created_at=data.get("created_at", datetime.now().isoformat()),
        )


class ContextManager:
    """컨텍스트 관리자"""

    def __init__(self, project_path: Path, storage_path: Optional[Path] = None):
        """
        Args:
            project_path: 프로젝트 루트 경로
            storage_path: 컨텍스트 저장 경로 (기본: ~/.claude-flow/{project}/contexts/)
        """
        self.project_path = project_path.absolute()

        if storage_path is None:
            self.storage_path = (
                Path.home()
                / ".claude-flow"
                / self.project_path.name
                / "contexts"
            )
        else:
            self.storage_path = storage_path

        self.storage_path.mkdir(parents=True, exist_ok=True)

        # 현재 세션의 컨텍스트 파일 목록
        self.context_files: List[ContextFile] = []

        # 프리셋 저장 경로
        self.presets_file = self.storage_path / "presets.json"

        # 자동 저장된 마지막 컨텍스트 경로
        self.last_context_file = self.storage_path / "last_context.json"

        logger.info(
            "컨텍스트 관리자 초기화",
            project=str(self.project_path),
            storage=str(self.storage_path),
        )

    def add_file(
        self,
        file_path: Path,
        label: Optional[str] = None,
        enabled: bool = True
    ) -> bool:
        """
        파일을 컨텍스트에 추가

        Args:
            file_path: 추가할 파일 경로
            label: 파일 라벨 (선택, 기본: 상대 경로)
            enabled: 활성화 여부

        Returns:
            성공 여부
        """
        try:
            abs_path = file_path.absolute()

            # 이미 추가된 파일인지 확인
            if any(cf.path == str(abs_path) for cf in self.context_files):
                logger.warning("이미 컨텍스트에 추가된 파일", path=str(abs_path))
                return False

            # 파일 존재 확인
            if not abs_path.exists():
                logger.error("파일이 존재하지 않음", path=str(abs_path))
                return False

            # 프로젝트 내 파일인지 확인 (선택적)
            try:
                rel_path = abs_path.relative_to(self.project_path)
                default_label = str(rel_path)
            except ValueError:
                # 프로젝트 외부 파일
                default_label = abs_path.name

            # 파일 정보 생성
            context_file = ContextFile(
                path=str(abs_path),
                label=label or default_label,
                is_directory=abs_path.is_dir(),
                size_bytes=abs_path.stat().st_size if abs_path.is_file() else 0,
                enabled=enabled,
            )

            self.context_files.append(context_file)
            logger.info("파일이 컨텍스트에 추가됨", file=context_file.to_dict())

            # 자동 저장
            self._save_last_context()

            return True

        except Exception as e:
            logger.error("파일 추가 실패", path=str(file_path), error=str(e))
            return False

    def remove_file(self, file_path: str) -> bool:
        """
        파일을 컨텍스트에서 제거

        Args:
            file_path: 제거할 파일 경로

        Returns:
            성공 여부
        """
        original_count = len(self.context_files)
        self.context_files = [cf for cf in self.context_files if cf.path != file_path]

        removed = len(self.context_files) < original_count
        if removed:
            logger.info("파일이 컨텍스트에서 제거됨", path=file_path)
            self._save_last_context()

        return removed

    def toggle_file(self, file_path: str) -> bool:
        """
        파일 활성화/비활성화 토글

        Args:
            file_path: 토글할 파일 경로

        Returns:
            새로운 enabled 상태 (None이면 파일을 찾지 못함)
        """
        for cf in self.context_files:
            if cf.path == file_path:
                cf.enabled = not cf.enabled
                logger.info(
                    "파일 활성화 상태 변경",
                    path=file_path,
                    enabled=cf.enabled
                )
                self._save_last_context()
                return cf.enabled

        return None

    def clear(self):
        """모든 컨텍스트 파일 제거"""
        self.context_files.clear()
        logger.info("컨텍스트가 비워짐")
        self._save_last_context()

    def get_enabled_files(self) -> List[ContextFile]:
        """활성화된 컨텍스트 파일 목록 반환"""
        return [cf for cf in self.context_files if cf.enabled]

    def get_all_files(self) -> List[ContextFile]:
        """모든 컨텍스트 파일 목록 반환 (비활성화 포함)"""
        return self.context_files.copy()

    def get_total_size(self) -> int:
        """활성화된 파일들의 총 크기 (바이트)"""
        return sum(cf.size_bytes for cf in self.get_enabled_files())

    def build_context_message(self, max_size_bytes: int = 50_000) -> Optional[str]:
        """
        컨텍스트 파일들을 읽어서 하나의 메시지로 조합

        Args:
            max_size_bytes: 최대 크기 (기본: 50KB)

        Returns:
            컨텍스트 메시지 (파일이 없거나 너무 크면 None)
        """
        enabled_files = self.get_enabled_files()

        if not enabled_files:
            return None

        total_size = self.get_total_size()
        if total_size > max_size_bytes:
            logger.warning(
                "컨텍스트 크기가 너무 큼",
                total_size=total_size,
                max_size=max_size_bytes
            )
            return None

        # 메시지 조합
        parts = ["다음 파일들을 참고해주세요:\n"]

        for cf in enabled_files:
            try:
                file_path = Path(cf.path)

                if file_path.is_file():
                    content = file_path.read_text(encoding="utf-8", errors="ignore")
                    parts.append(f"\n--- {cf.label} ({cf.path}) ---")
                    parts.append(content)
                    parts.append(f"--- 끝: {cf.label} ---\n")

                elif file_path.is_dir():
                    # 디렉토리면 파일 목록만 표시
                    files = list(file_path.rglob("*"))
                    file_list = "\n".join(
                        f"  - {f.relative_to(file_path)}"
                        for f in files if f.is_file()
                    )
                    parts.append(f"\n--- 디렉토리: {cf.label} ({cf.path}) ---")
                    parts.append(file_list)
                    parts.append(f"--- 끝: {cf.label} ---\n")

            except Exception as e:
                logger.error("파일 읽기 실패", path=cf.path, error=str(e))
                continue

        return "\n".join(parts)

    def save_preset(self, name: str, description: str = "") -> bool:
        """
        현재 컨텍스트를 프리셋으로 저장

        Args:
            name: 프리셋 이름
            description: 프리셋 설명

        Returns:
            성공 여부
        """
        try:
            preset = ContextPreset(
                name=name,
                description=description,
                files=self.context_files.copy()
            )

            # 기존 프리셋 불러오기
            presets = self._load_presets()

            # 중복 이름 확인
            presets = [p for p in presets if p.name != name]

            # 추가
            presets.append(preset)

            # 저장
            self._save_presets(presets)

            logger.info("프리셋 저장 완료", preset=name, file_count=len(self.context_files))
            return True

        except Exception as e:
            logger.error("프리셋 저장 실패", error=str(e))
            return False

    def load_preset(self, name: str) -> bool:
        """
        프리셋 불러오기

        Args:
            name: 프리셋 이름

        Returns:
            성공 여부
        """
        try:
            presets = self._load_presets()
            preset = next((p for p in presets if p.name == name), None)

            if preset is None:
                logger.warning("프리셋을 찾을 수 없음", preset=name)
                return False

            self.context_files = preset.files.copy()
            logger.info("프리셋 불러오기 완료", preset=name, file_count=len(self.context_files))
            self._save_last_context()
            return True

        except Exception as e:
            logger.error("프리셋 불러오기 실패", error=str(e))
            return False

    def list_presets(self) -> List[ContextPreset]:
        """모든 프리셋 목록 반환"""
        return self._load_presets()

    def delete_preset(self, name: str) -> bool:
        """
        프리셋 삭제

        Args:
            name: 프리셋 이름

        Returns:
            성공 여부
        """
        try:
            presets = self._load_presets()
            original_count = len(presets)

            presets = [p for p in presets if p.name != name]

            if len(presets) == original_count:
                logger.warning("삭제할 프리셋을 찾을 수 없음", preset=name)
                return False

            self._save_presets(presets)
            logger.info("프리셋 삭제 완료", preset=name)
            return True

        except Exception as e:
            logger.error("프리셋 삭제 실패", error=str(e))
            return False

    def restore_last_context(self) -> bool:
        """마지막으로 저장된 컨텍스트 복원"""
        try:
            if not self.last_context_file.exists():
                return False

            with open(self.last_context_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            self.context_files = [ContextFile.from_dict(cf) for cf in data["files"]]
            logger.info("마지막 컨텍스트 복원 완료", file_count=len(self.context_files))
            return True

        except Exception as e:
            logger.error("마지막 컨텍스트 복원 실패", error=str(e))
            return False

    # === 내부 메서드 ===

    def _save_last_context(self):
        """현재 컨텍스트를 자동 저장"""
        try:
            data = {
                "files": [cf.to_dict() for cf in self.context_files],
                "saved_at": datetime.now().isoformat(),
            }

            with open(self.last_context_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

        except Exception as e:
            logger.error("컨텍스트 자동 저장 실패", error=str(e))

    def _load_presets(self) -> List[ContextPreset]:
        """프리셋 파일 로드"""
        try:
            if not self.presets_file.exists():
                return []

            with open(self.presets_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            return [ContextPreset.from_dict(p) for p in data]

        except Exception as e:
            logger.error("프리셋 로드 실패", error=str(e))
            return []

    def _save_presets(self, presets: List[ContextPreset]):
        """프리셋 파일 저장"""
        try:
            data = [p.to_dict() for p in presets]

            with open(self.presets_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

        except Exception as e:
            logger.error("프리셋 저장 실패", error=str(e))
            raise
