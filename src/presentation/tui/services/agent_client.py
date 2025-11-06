"""Claude Agent SDK 클라이언트"""

import os
import json
from typing import Optional, Callable, AsyncIterator, Dict, Any
from pathlib import Path

from src.domain.models import AgentConfig
from src.infrastructure.claude.worker_client import WorkerAgent
from .response_parser import ResponseParser


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
        # 이미 SDK 형식이면 그대로 반환
        if model.startswith("claude-") and "-20" in model:
            return model
        
        # 사용자 친화적 이름을 SDK 형식으로 변환
        model_mapping = {
            "claude-sonnet-4.5": "claude-sonnet-4-5-20250929",
            "claude-haiku-4.5": "claude-haiku-4-5-20251001",
            "claude-opus-4.1": "claude-opus-4-20241022",
        }
        return model_mapping.get(model, "claude-sonnet-4-5-20250929")

    async def send_message(
        self,
        message: str,
        on_token: Optional[Callable[[str], None]] = None,
        on_thinking: Optional[Callable[[str], None]] = None,
        on_tool_use: Optional[Callable[[str, Dict], None]] = None,
        on_tool_result: Optional[Callable[[str], None]] = None,
    ) -> AsyncIterator[str]:
        """메시지 전송 및 스트리밍 응답 (블록 파싱)"""
        parser = ResponseParser()
        
        try:
            async for chunk in self.worker.execute_task(
                task_description=message,
                resume_session_id=None,
            ):
                # 청크 파싱
                parsed = parser.parse_chunk(chunk)

                if parsed["type"] == "json":
                    # JSON 형식 응답 (ThinkingBlock, ToolUse 등)
                    data = parsed["data"]
                    
                    if "content" in data and isinstance(data["content"], list):
                        for block in data["content"]:
                            block_type = block.get("type")
                            
                            # ThinkingBlock 처리
                            if block_type == "thinking":
                                thinking_text = block.get("thinking", "")
                                if on_thinking:
                                    on_thinking(thinking_text)
                                # JSON은 yield하지 않음
                                continue
                            
                            # ToolUse 처리
                            elif block_type == "tool_use":
                                tool_name = block.get("name", "unknown")
                                tool_input = block.get("input", {})
                                if on_tool_use:
                                    on_tool_use(tool_name, tool_input)
                                # JSON은 yield하지 않음
                                continue

                    # JSON이지만 특수 블록이 아니면 그대로 표시
                    # (하지만 대부분 특수 블록이므로 skip)
                    continue

                # 일반 텍스트는 그대로 yield
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
