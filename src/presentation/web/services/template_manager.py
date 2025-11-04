"""
워크플로우 템플릿 관리자

TemplateManager: 템플릿 CRUD 및 검증 로직
"""

import json
import uuid
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime
from src.presentation.web.schemas.template import Template, TemplateMetadata
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)


class TemplateManager:
    """
    워크플로우 템플릿 관리자

    내장 템플릿(builtin)과 사용자 정의 템플릿(user)을 분리 관리합니다.
    - 내장 템플릿: templates/ 디렉토리 (읽기 전용, 삭제 불가)
    - 사용자 템플릿: ~/.claude-flow/templates/ 디렉토리 (읽기/쓰기/삭제 가능)

    Attributes:
        builtin_templates_dir: 내장 템플릿 디렉토리
        user_templates_dir: 사용자 템플릿 디렉토리
    """

    def __init__(
        self,
        builtin_templates_dir: Optional[Path] = None,
        user_templates_dir: Optional[Path] = None,
    ):
        """
        템플릿 매니저 초기화

        Args:
            builtin_templates_dir: 내장 템플릿 디렉토리 (기본: 프로젝트 루트/templates)
            user_templates_dir: 사용자 템플릿 디렉토리 (기본: ~/.claude-flow/templates)
        """
        # 내장 템플릿 디렉토리 (프로젝트 루트/templates)
        if builtin_templates_dir is None:
            project_root = Path(__file__).parent.parent.parent.parent.parent
            self.builtin_templates_dir = project_root / "templates"
        else:
            self.builtin_templates_dir = builtin_templates_dir

        # 사용자 템플릿 디렉토리 (~/.claude-flow/templates)
        if user_templates_dir is None:
            self.user_templates_dir = Path.home() / ".claude-flow" / "templates"
        else:
            self.user_templates_dir = user_templates_dir

        # 사용자 템플릿 디렉토리 생성 (존재하지 않으면)
        self.user_templates_dir.mkdir(parents=True, exist_ok=True)

        logger.info(
            f"TemplateManager 초기화 완료: builtin={self.builtin_templates_dir}, user={self.user_templates_dir}"
        )

    def list_templates(self) -> List[TemplateMetadata]:
        """
        템플릿 목록 조회 (메타데이터만)

        내장 템플릿과 사용자 템플릿을 모두 반환합니다.

        Returns:
            템플릿 메타데이터 목록
        """
        templates = []

        # 내장 템플릿 로드
        if self.builtin_templates_dir.exists():
            for template_file in self.builtin_templates_dir.glob("*.json"):
                try:
                    template = self._load_template_from_file(template_file, is_builtin=True)
                    if template:
                        templates.append(template.to_metadata())
                except Exception as e:
                    logger.error(f"내장 템플릿 로드 실패: {template_file.name} - {e}")

        # 사용자 템플릿 로드
        for template_file in self.user_templates_dir.glob("*.json"):
            try:
                template = self._load_template_from_file(template_file, is_builtin=False)
                if template:
                    templates.append(template.to_metadata())
            except Exception as e:
                logger.error(f"사용자 템플릿 로드 실패: {template_file.name} - {e}")

        logger.info(f"템플릿 목록 조회 완료: {len(templates)}개")
        return templates

    def get_template(self, template_id: str) -> Optional[Template]:
        """
        템플릿 상세 조회 (전체 데이터)

        Args:
            template_id: 템플릿 ID

        Returns:
            템플릿 객체 (없으면 None)
        """
        # 내장 템플릿 검색
        builtin_file = self.builtin_templates_dir / f"{template_id}.json"
        if builtin_file.exists():
            template = self._load_template_from_file(builtin_file, is_builtin=True)
            if template:
                logger.info(f"내장 템플릿 조회 완료: {template_id}")
                return template

        # 사용자 템플릿 검색
        user_file = self.user_templates_dir / f"{template_id}.json"
        if user_file.exists():
            template = self._load_template_from_file(user_file, is_builtin=False)
            if template:
                logger.info(f"사용자 템플릿 조회 완료: {template_id}")
                return template

        logger.warning(f"템플릿을 찾을 수 없습니다: {template_id}")
        return None

    def save_template(
        self,
        name: str,
        description: Optional[str],
        category: str,
        workflow: Dict[str, Any],
        tags: Optional[List[str]] = None,
        template_id: Optional[str] = None,
    ) -> str:
        """
        사용자 정의 템플릿 저장

        Args:
            name: 템플릿 이름
            description: 템플릿 설명
            category: 카테고리
            workflow: 워크플로우 데이터 (dict)
            tags: 태그 목록
            template_id: 템플릿 ID (수정 시 제공, 없으면 새로 생성)

        Returns:
            저장된 템플릿 ID
        """
        # 템플릿 ID 생성 또는 재사용
        if template_id is None:
            template_id = str(uuid.uuid4())[:8]
            logger.info(f"새 템플릿 ID 생성: {template_id}")
        else:
            # 기존 템플릿 수정 시 내장 템플릿은 수정 불가
            existing_template = self.get_template(template_id)
            if existing_template and existing_template.is_builtin:
                raise ValueError(f"내장 템플릿은 수정할 수 없습니다: {template_id}")

        now = datetime.utcnow().isoformat() + "Z"

        # 템플릿 객체 생성
        template_data = {
            "id": template_id,
            "name": name,
            "description": description,
            "category": category,
            "workflow": workflow,
            "tags": tags or [],
            "is_builtin": False,
            "metadata": {},
            "created_at": now,
            "updated_at": now,
        }

        # 파일로 저장
        template_file = self.user_templates_dir / f"{template_id}.json"
        with open(template_file, "w", encoding="utf-8") as f:
            json.dump(template_data, f, indent=2, ensure_ascii=False)

        logger.info(f"사용자 템플릿 저장 완료: {template_id} ({name})")
        return template_id

    def delete_template(self, template_id: str) -> bool:
        """
        템플릿 삭제 (내장 템플릿은 삭제 불가)

        Args:
            template_id: 템플릿 ID

        Returns:
            삭제 성공 여부
        """
        # 내장 템플릿인지 확인
        builtin_file = self.builtin_templates_dir / f"{template_id}.json"
        if builtin_file.exists():
            raise ValueError(f"내장 템플릿은 삭제할 수 없습니다: {template_id}")

        # 사용자 템플릿 삭제
        user_file = self.user_templates_dir / f"{template_id}.json"
        if user_file.exists():
            user_file.unlink()
            logger.info(f"사용자 템플릿 삭제 완료: {template_id}")
            return True

        logger.warning(f"템플릿을 찾을 수 없습니다: {template_id}")
        return False

    def validate_template(self, workflow: Dict[str, Any]) -> List[str]:
        """
        템플릿 검증 (워크플로우 유효성 검사)

        검증 항목:
        1. 필수 필드 존재 (nodes, edges)
        2. 노드 ID 중복 검사
        3. 엣지 연결 유효성 (source/target 노드 존재 확인)

        Args:
            workflow: 워크플로우 데이터

        Returns:
            에러 메시지 목록 (빈 리스트면 검증 통과)
        """
        errors = []

        # 1. 필수 필드 존재
        if "nodes" not in workflow:
            errors.append("필수 필드 'nodes'가 없습니다")
        if "edges" not in workflow:
            errors.append("필수 필드 'edges'가 없습니다")

        if errors:
            return errors

        nodes = workflow["nodes"]
        edges = workflow["edges"]

        # 2. 노드 ID 중복 검사
        node_ids = [node["id"] for node in nodes]
        if len(node_ids) != len(set(node_ids)):
            errors.append("중복된 노드 ID가 있습니다")

        # 3. 엣지 연결 유효성
        node_id_set = set(node_ids)
        for edge in edges:
            source = edge.get("source")
            target = edge.get("target")

            if source not in node_id_set:
                errors.append(f"엣지의 source 노드가 존재하지 않습니다: {source}")
            if target not in node_id_set:
                errors.append(f"엣지의 target 노드가 존재하지 않습니다: {target}")

        if not errors:
            logger.info("템플릿 검증 통과")
        else:
            logger.warning(f"템플릿 검증 실패: {errors}")

        return errors

    def _load_template_from_file(self, template_file: Path, is_builtin: bool) -> Optional[Template]:
        """
        JSON 파일에서 템플릿 로드

        Args:
            template_file: 템플릿 파일 경로
            is_builtin: 내장 템플릿 여부

        Returns:
            템플릿 객체 (로드 실패 시 None)
        """
        try:
            with open(template_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            # is_builtin 플래그 강제 설정
            data["is_builtin"] = is_builtin

            # Template 객체로 변환 (Pydantic 검증)
            template = Template(**data)
            return template
        except Exception as e:
            logger.error(f"템플릿 파일 로드 실패: {template_file} - {e}")
            return None
