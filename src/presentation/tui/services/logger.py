"""로깅 시스템"""

import logging
from pathlib import Path
from datetime import datetime
from typing import Optional


class SessionLogger:
    """세션별 로거"""

    def __init__(
        self,
        logs_dir: Path,
        session_id: str,
        log_level: str = "INFO",
        max_file_size_mb: int = 10,
    ):
        self.logs_dir = logs_dir
        self.logs_dir.mkdir(parents=True, exist_ok=True)

        self.session_id = session_id
        self.log_file = logs_dir / f"{session_id}.log"

        # 로거 설정
        self.logger = logging.getLogger(f"session_{session_id}")
        self.logger.setLevel(getattr(logging, log_level.upper()))

        # 파일 핸들러
        handler = logging.FileHandler(self.log_file, encoding="utf-8")
        handler.setLevel(getattr(logging, log_level.upper()))

        # 포맷터
        formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)

        self.logger.addHandler(handler)
        self.max_file_size = max_file_size_mb * 1024 * 1024  # bytes

    def log_message(self, role: str, content: str, tokens: Optional[dict] = None):
        """메시지 로그"""
        log_entry = f"[{role.upper()}] {content[:100]}..."
        if tokens:
            log_entry += f" | Tokens: {tokens}"
        self.logger.info(log_entry)

    def log_tool_call(self, tool_name: str, args: dict):
        """도구 호출 로그"""
        self.logger.info(f"[TOOL] {tool_name} - {args}")

    def log_error(self, error: Exception):
        """에러 로그"""
        self.logger.error(f"[ERROR] {str(error)}", exc_info=True)

    def log_event(self, event: str, data: Optional[dict] = None):
        """이벤트 로그"""
        log_entry = f"[EVENT] {event}"
        if data:
            log_entry += f" - {data}"
        self.logger.info(log_entry)

    def check_rotation(self):
        """로그 파일 크기 확인 및 로테이션"""
        if self.log_file.exists() and self.log_file.stat().st_size > self.max_file_size:
            # 백업 파일명
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = self.logs_dir / f"{self.session_id}_{timestamp}.log.gz"

            # 압축 (간단히 rename만 수행, 실제로는 gzip 사용)
            import shutil
            shutil.move(str(self.log_file), str(backup_file))

            # 새 로그 파일 시작
            self.logger.info(f"로그 로테이션: {backup_file}")


class LogManager:
    """로그 파일 관리"""

    def __init__(self, logs_dir: Path):
        self.logs_dir = logs_dir

    def list_logs(self):
        """로그 파일 목록"""
        if not self.logs_dir.exists():
            return []

        logs = []
        for log_file in self.logs_dir.glob("*.log*"):
            logs.append({
                "filename": log_file.name,
                "path": str(log_file),
                "size": log_file.stat().st_size,
                "modified": datetime.fromtimestamp(
                    log_file.stat().st_mtime
                ).isoformat(),
            })

        # 최근 순 정렬
        logs.sort(key=lambda x: x["modified"], reverse=True)
        return logs

    def delete_log(self, filename: str):
        """로그 파일 삭제"""
        log_file = self.logs_dir / filename
        if log_file.exists():
            log_file.unlink()

    def delete_old_logs(self, days: int):
        """오래된 로그 삭제"""
        from datetime import timedelta

        cutoff = datetime.now() - timedelta(days=days)

        for log_file in self.logs_dir.glob("*.log*"):
            modified = datetime.fromtimestamp(log_file.stat().st_mtime)
            if modified < cutoff:
                log_file.unlink()

    def get_total_size(self) -> int:
        """총 로그 파일 크기 (bytes)"""
        total = 0
        for log_file in self.logs_dir.glob("*.log*"):
            total += log_file.stat().st_size
        return total

