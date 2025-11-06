"""Claude Agent SDK 클라이언트"""

import os
from typing import Optional, Callable, AsyncIterator
from pathlib import Path

from src.domain.models import AgentConfig
from src.infrastructure.claude.worker_client import WorkerAgent


class AgentClient:
    """Claude Agent SDK 클라이언트 래퍼 (기존 WorkerAgent 재사용)"""

    def __init__(
        self,
        project_path: Path,
        model: str = "claude-sonnet-4.5",
        claude_md_content: Optional[str] = None,
    ):
        self.project_path = project_path
        self.model = model
        self.claude_md_content = claude_md_content

        # Claude OAuth Token 확인
        self.oauth_token = os.getenv("CLAUDE_CODE_OAUTH_TOKEN")
        if not self.oauth_token:
            raise ValueError(
                "CLAUDE_CODE_OAUTH_TOKEN 환경변수가 설정되지 않았습니다.\n"
                "Claude Code에서 OAuth 토큰을 발급받아 설정해주세요."
            )

        # 시스템 프롬프트 구성
        system_prompt = self._build_system_prompt()

        # AgentConfig 생성 (기존 도메인 모델 사용)
        agent_config = AgentConfig(
            name="claude-tui",
            role="TUI 대화형 AI 에이전트",
            system_prompt=system_prompt,
            model=self._normalize_model_name(model),
            allowed_tools=["Read", "Write", "Edit", "Bash"],
            thinking=False,  # TUI에서는 thinking 비활성화
        )

        # WorkerAgent 생성
        self.worker = WorkerAgent(
            config=agent_config,
            project_dir=str(project_path)
        )

    def _normalize_model_name(self, model: str) -> str:
        """모델명을 SDK 형식으로 변환"""
        model_mapping = {
            "claude-sonnet-4.5": "claude-sonnet-4-5-20250929",
            "claude-haiku-4.5": "claude-haiku-4-5-20251001",  # 수정됨
        }
        return model_mapping.get(model, "claude-sonnet-4-5-20250929")

    async def send_message(
        self,
        message: str,
        on_token: Optional[Callable[[str], None]] = None,
        on_tool_use: Optional[Callable[[str, dict], None]] = None,
        on_thinking: Optional[Callable[[str], None]] = None,
    ) -> AsyncIterator[str]:
        """메시지 전송 및 스트리밍 응답"""

        try:
            # WorkerAgent의 execute_task는 깔끔한 텍스트를 반환
            # 특별한 파싱 없이 그대로 전달
            async for chunk in self.worker.execute_task(
                task_description=message,
                resume_session_id=None,  # TUI에서는 세션 재사용 안 함 (일단)
            ):
                # 일반 텍스트 그대로 yield
                if on_token:
                    on_token(chunk)
                yield chunk

        except Exception as e:
            error_msg = f"에러 발생: {str(e)}"
            if on_token:
                on_token(error_msg)
            yield error_msg

    def _build_system_prompt(self) -> str:
        """시스템 프롬프트 구성"""
        prompts = []

        # CLAUDE.md 내용 추가
        if self.claude_md_content:
            prompts.append("# 프로젝트 컨텍스트 (CLAUDE.md)")
            prompts.append(self.claude_md_content)
            prompts.append("")

        # 기본 시스템 프롬프트
        prompts.append(
            "당신은 소프트웨어 개발을 돕는 AI 에이전트입니다.\n"
            "사용자의 요청을 정확히 이해하고, 필요한 작업을 수행하세요.\n"
            "파일을 읽고 쓸 수 있으며, 터미널 명령어를 실행할 수 있습니다."
        )

        return "\n".join(prompts)

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """비용 추정 (USD)"""
        # Claude 4.5 Sonnet 기준 (예시 단가)
        prices = {
            "claude-sonnet-4.5": {"input": 3.0, "output": 15.0},  # per 1M tokens
            "claude-opus-4.1": {"input": 15.0, "output": 75.0},
            "claude-haiku-4.5": {"input": 0.8, "output": 4.0},
        }

        price = prices.get(self.model, prices["claude-sonnet-4.5"])

        input_cost = (input_tokens / 1_000_000) * price["input"]
        output_cost = (output_tokens / 1_000_000) * price["output"]

        return input_cost + output_cost
