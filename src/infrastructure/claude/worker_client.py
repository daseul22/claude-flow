"""
워커 에이전트 - Claude Agent SDK로 실제 작업 수행

WorkerAgent: Claude Code의 agentic harness를 사용하여 파일 읽기/쓰기, 코드 실행 등 수행
"""

from typing import AsyncIterator, Optional, Callable, Dict, Any, Awaitable
from pathlib import Path
import os

from src.domain.models import AgentConfig
from src.infrastructure.config import get_claude_cli_path, get_project_root
from src.infrastructure.logging import get_logger
from .sdk_executor import (
    SDKExecutionConfig,
    WorkerResponseHandler,
    WorkerSDKExecutor
)

logger = get_logger(__name__)


class WorkerAgent:
    """
    실제 작업을 수행하는 워커 에이전트

    Claude Agent SDK를 사용하여 Claude Code의 모든 기능(파일 읽기/쓰기,
    bash 실행, grep, edit 등)을 프로그래밍 방식으로 실행합니다.

    Attributes:
        config: 에이전트 설정
        system_prompt: 시스템 프롬프트
    """

    def __init__(
        self,
        config: AgentConfig,
        project_dir: Optional[str] = None
    ):
        """
        Args:
            config: 에이전트 설정
            project_dir: 프로젝트 디렉토리 경로 (CLAUDE.md 로드용, 선택)
        """
        self.config = config
        self.project_dir = project_dir
        self.system_prompt = self._load_system_prompt()
        self.last_session_id: Optional[str] = None  # 마지막 실행의 세션 ID 저장

    def _load_system_prompt(self) -> str:
        """
        시스템 프롬프트 로드 (프로젝트 루트 기준)

        config.system_prompt가 파일 경로면 파일에서 로드하고,
        그렇지 않으면 문자열 그대로 사용합니다.
        프로젝트 컨텍스트가 있으면 프롬프트에 추가합니다.

        Returns:
            시스템 프롬프트 문자열
        """
        prompt_text = self.config.system_prompt

        # .txt 확장자가 있거나 경로처럼 보이면 파일에서 로드 시도
        if prompt_text.endswith('.txt') or '/' in prompt_text:
            try:
                prompt_path = Path(prompt_text)
                if not prompt_path.is_absolute():
                    # 프로젝트 루트 기준으로 경로 해석
                    prompt_path = get_project_root() / prompt_text

                if prompt_path.exists():
                    with open(prompt_path, 'r', encoding='utf-8') as f:
                        loaded_prompt = f.read().strip()
                        logger.info(f"✅ 시스템 프롬프트 로드: {prompt_path}")
                        prompt_text = loaded_prompt
                else:
                    logger.warning(f"⚠️  프롬프트 파일 없음: {prompt_path}, 기본값 사용")
            except Exception as e:
                logger.error(f"❌ 프롬프트 로드 실패: {e}, 기본값 사용")

        # 프로젝트 CLAUDE.md 추가 (사용자가 선택한 프로젝트의 가이드라인)
        if self.project_dir:
            claude_md_path = Path(self.project_dir) / "CLAUDE.md"
            if claude_md_path.exists():
                try:
                    with open(claude_md_path, 'r', encoding='utf-8') as f:
                        claude_md_text = f.read().strip()
                        if claude_md_text:
                            prompt_text = f"{prompt_text}\n\n# Project Guidelines (from CLAUDE.md)\n\n{claude_md_text}"
                            logger.info(f"✅ 프로젝트 CLAUDE.md 로드: {claude_md_path}")
                except Exception as e:
                    logger.warning(f"⚠️  CLAUDE.md 로드 실패: {e}")

        # Thinking 모드 활성화 시 ultrathink 프롬프트 추가
        if self.config.thinking:
            ultrathink_text = """

# ULTRATHINK MODE

Before responding, engage in deep analysis and reasoning:

1. **Problem Analysis**: Break down the task into core components
2. **Solution Exploration**: Consider multiple approaches and their trade-offs
3. **Implementation Planning**: Think through step-by-step execution
4. **Quality Verification**: Anticipate edge cases and potential issues

Use your thinking process liberally throughout your response to show your reasoning.
"""
            prompt_text = f"{prompt_text}\n{ultrathink_text}"
            logger.info(f"✅ Thinking 모드 활성화: ultrathink 프롬프트 추가")

        return prompt_text

    def _generate_debug_info(self, task_description: str) -> str:
        """
        Worker 실행 시 디버그 정보 생성 (시스템 프롬프트, 맥락 포함)

        Args:
            task_description: 작업 설명

        Returns:
            포맷팅된 디버그 정보
        """
        lines = []
        lines.append("\n" + "="*70)
        lines.append(f"🔍 [{self.config.name.upper()}] Worker 실행 정보")
        lines.append("="*70)

        # 1. 기본 정보
        lines.append(f"\n📋 Worker: {self.config.name} ({self.config.role})")
        lines.append(f"🤖 Model: {self.config.model}")
        lines.append(f"🛠️  Tools: {', '.join(self.config.allowed_tools) if self.config.allowed_tools else 'None'}")

        # 2. 시스템 프롬프트 정보 (전체 내용 표시)
        lines.append(f"\n📄 System Prompt:")
        lines.append(f"   Source: {self.config.system_prompt}")
        lines.append(f"   Length: {len(self.system_prompt)} characters")
        lines.append("\n" + "-"*70)
        # 시스템 프롬프트 전체 표시 (indented)
        for line in self.system_prompt.split('\n'):
            lines.append(f"   {line}")
        lines.append("-"*70)


        # 4. 작업 설명 (전체 표시)
        lines.append(f"\n📝 Task Description:")
        lines.append("-"*70)
        for line in task_description.split('\n'):
            lines.append(f"   {line}")
        lines.append("-"*70)

        lines.append("\n" + "="*70)
        lines.append("⚡ Starting Worker execution...")
        lines.append("="*70 + "\n")

        return "\n".join(lines)

    async def execute_task(
        self,
        task_description: str,
        usage_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        resume_session_id: Optional[str] = None,
        user_input_callback: Optional[Callable[[str], Awaitable[str]]] = None,
        session_id_callback: Optional[Callable[[str], None]] = None
    ) -> AsyncIterator[str]:
        """
        Claude Agent SDK를 사용하여 작업 실행 (Human-in-the-Loop 지원)

        Args:
            task_description: 작업 설명
            usage_callback: 토큰 사용량 정보를 받을 콜백 함수 (선택)
            resume_session_id: 재개할 SDK 세션 ID (선택, 이전 실행의 컨텍스트 유지)
            user_input_callback: 사용자 입력이 필요할 때 호출되는 async 함수 (선택)
                                 질문(str)을 받아서 답변(str)을 반환해야 함
            session_id_callback: SDK 세션 ID가 추출되면 즉시 호출되는 콜백 함수 (선택)
                                session_id(str)를 받아서 즉시 저장할 수 있음

        Yields:
            스트리밍 응답 청크

        Raises:
            Exception: 작업 실행 실패 시
        """
        # Working directory 변경 (project_dir이 지정된 경우)
        original_cwd = os.getcwd()
        if self.project_dir:
            try:
                os.chdir(self.project_dir)
                logger.info(f"[{self.config.name}] Working Directory 변경: {original_cwd} → {self.project_dir}")
            except Exception as e:
                logger.warning(f"[{self.config.name}] Working Directory 변경 실패: {e}")
                # 변경 실패 시 원래 디렉토리에서 계속 진행

        try:
            # 디버그 정보 출력 (기본 비활성화 - 컨텍스트 절약)
            # WORKER_DEBUG_INFO=true로 설정하면 활성화
            show_debug_info = os.getenv("WORKER_DEBUG_INFO", "false").lower() in (
                "true", "1", "yes"
            )
            if show_debug_info:
                debug_info = self._generate_debug_info(task_description)
                yield debug_info

            # 시스템 프롬프트와 작업 설명 결합
            full_prompt = f"{self.system_prompt}\n\n{task_description}"

            logger.info(f"[{self.config.name}] Claude Agent SDK 실행 시작")
            logger.info(f"[{self.config.name}] Working Directory: {os.getcwd()}")
            logger.info(f"[{self.config.name}] Prompt 길이: {len(full_prompt)} characters")
            logger.info(f"[{self.config.name}] Model: {self.config.model}")
            logger.info(f"[{self.config.name}] Tools: {self.config.allowed_tools}")
            logger.info(f"[{self.config.name}] Thinking Mode: {self.config.thinking}")
            logger.info(f"[{self.config.name}] CLI Path: {get_claude_cli_path()}")

            # SDK 실행 설정
            config = SDKExecutionConfig(
                model=self.config.model,
                cli_path=get_claude_cli_path(),
                permission_mode="bypassPermissions"
            )

            # 응답 핸들러 생성 (usage_callback 전달)
            response_handler = WorkerResponseHandler(usage_callback=usage_callback)

            # Executor 생성
            executor = WorkerSDKExecutor(
                config=config,
                allowed_tools=self.config.allowed_tools if self.config.allowed_tools else [],
                response_handler=response_handler,
                worker_name=self.config.name
            )

            # 스트림 실행 (resume_session_id, user_input_callback, session_id_callback 전달)
            async for text in executor.execute_stream(
                prompt=full_prompt,
                resume_session_id=resume_session_id,
                user_input_callback=user_input_callback,
                session_id_callback=session_id_callback
            ):
                yield text

            # 실제 SDK 세션 ID 저장 (다음 실행에서 재활용)
            self.last_session_id = executor.last_session_id
            if self.last_session_id:
                logger.info(
                    f"[{self.config.name}] ✓ Worker 세션 ID 저장 완료: {self.last_session_id[:8]}... "
                    "(다음 실행에서 resume으로 재활용)"
                )
            else:
                logger.warning(
                    f"[{self.config.name}] ⚠️ SDK 세션 ID를 가져올 수 없습니다. "
                    "추가 프롬프트 기능이 동작하지 않을 수 있습니다."
                )

            # Worker 실행 완료 표시
            yield f"\n└─ ✅ [{self.config.name}] 완료\n"

        finally:
            # Working directory 복원
            if self.project_dir and os.getcwd() != original_cwd:
                try:
                    os.chdir(original_cwd)
                    logger.info(f"[{self.config.name}] Working Directory 복원: {os.getcwd()}")
                except Exception as e:
                    logger.error(f"[{self.config.name}] Working Directory 복원 실패: {e}")

    def __repr__(self) -> str:
        return f"WorkerAgent(name={self.config.name}, role={self.config.role})"
