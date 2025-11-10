"""세션 관리 헬퍼 클래스들"""

import json
import shutil
import time
from pathlib import Path
from typing import Dict, Any
from dataclasses import asdict


class AtomicFileWriter:
    """원자적 파일 쓰기 헬퍼 - 재시도 로직 포함"""

    def __init__(self, target_file: Path):
        """
        Args:
            target_file: 저장할 파일 경로
        """
        self.target_file = target_file
        self.temp_file = target_file.with_suffix(".json.tmp")
        self.backup_file = target_file.with_suffix(".json.backup")

    def write_with_retry(self, data: dict, max_retries: int = 3) -> bool:
        """원자적 쓰기 + 재시도

        Args:
            data: JSON 직렬화 가능한 딕셔너리
            max_retries: 최대 재시도 횟수

        Returns:
            저장 성공 여부
        """
        for attempt in range(max_retries):
            try:
                # 1. 기존 파일 백업
                self._backup_existing()

                # 2. 임시 파일에 쓰기
                self._write_temp(data)

                # 3. 검증 (파싱 가능 여부)
                self._validate_temp()

                # 4. 커밋 (임시 → 실제)
                self._commit()

                # 5. 백업 파일 삭제
                self._cleanup_backup()

                return True

            except (IOError, OSError, PermissionError) as e:
                if attempt < max_retries - 1:
                    # 재시도
                    time.sleep(0.1 * (attempt + 1))  # 지수 백오프
                    continue
                else:
                    # 최종 실패
                    self._log_final_error(e)
                    return False

            except Exception as e:
                # 예상치 못한 에러
                self._log_unexpected_error(e)
                return False

        return False

    def _backup_existing(self) -> None:
        """기존 파일 백업"""
        if self.target_file.exists():
            shutil.copy2(self.target_file, self.backup_file)

    def _write_temp(self, data: dict) -> None:
        """임시 파일에 쓰기"""
        with open(self.temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _validate_temp(self) -> None:
        """임시 파일 검증 (파싱 가능 여부)"""
        with open(self.temp_file, "r", encoding="utf-8") as f:
            json.load(f)  # 파싱 테스트

    def _commit(self) -> None:
        """임시 파일을 실제 파일로 이동 (원자적 연산)"""
        self.temp_file.replace(self.target_file)

    def _cleanup_backup(self) -> None:
        """백업 파일 삭제"""
        if self.backup_file.exists():
            self.backup_file.unlink()

    def _log_final_error(self, error: Exception) -> None:
        """최종 실패 로그"""
        import sys

        error_msg = (
            f"[CRITICAL] 세션 저장 실패 (3회 재시도 후):\n"
            f"  파일: {self.target_file}\n"
            f"  에러: {error}\n"
        )

        # 백업 파일이 있으면 알림
        if self.backup_file.exists():
            error_msg += f"  백업: {self.backup_file} (이전 상태 보존됨)\n"

        print(error_msg, file=sys.stderr)

    def _log_unexpected_error(self, error: Exception) -> None:
        """예상치 못한 에러 로그"""
        import sys
        import traceback

        print(
            f"[CRITICAL] 세션 저장 중 예상치 못한 에러:\n"
            f"  파일: {self.target_file}\n"
            f"  에러: {error}\n"
            f"  트레이스:\n{traceback.format_exc()}",
            file=sys.stderr,
        )


class SessionSerializer:
    """세션 직렬화 헬퍼"""

    @staticmethod
    def to_dict(session) -> Dict[str, Any]:
        """세션을 딕셔너리로 변환

        Args:
            session: Session 객체

        Returns:
            JSON 직렬화 가능한 딕셔너리
        """
        return {
            "session_id": session.session_id,
            "project_name": session.project_name,
            "project_path": session.project_path,
            "working_directory": session.working_directory,
            "model": session.model,
            "created_at": session.created_at,
            "updated_at": session.updated_at,
            "claude_md_loaded": session.claude_md_loaded,
            "messages": [
                {
                    "role": msg.role,
                    "content": msg.content,
                    "timestamp": msg.timestamp,
                    "tokens": msg.tokens,
                    "tool_calls": msg.tool_calls,
                }
                for msg in session.messages
            ],
            "feedback_loop": asdict(session.feedback_loop),
            "total_tokens": session.total_tokens,
        }
