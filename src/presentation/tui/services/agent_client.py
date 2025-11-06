"""Claude Agent SDK 클라이언트"""

import os
from typing import Optional, Callable, AsyncIterator
from pathlib import Path

try:
    from claude_agent_sdk import ClaudeSDKClient
    from claude_agent_sdk.agent_options import ClaudeAgentOptions
    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False
    ClaudeSDKClient = None
    ClaudeAgentOptions = None
    print("Warning: claude-agent-sdk not available. Running in mock mode.")


class AgentClient:
    """Claude Agent SDK 클라이언트 래퍼"""

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

    async def send_message(
        self,
        message: str,
        on_token: Optional[Callable[[str], None]] = None,
    ) -> AsyncIterator[str]:
        """메시지 전송 및 스트리밍 응답"""

        if not SDK_AVAILABLE:
            # Mock 응답 (SDK 없을 때)
            mock_response = f"[Mock] 응답: {message[:50]}...\n\n파일을 읽고 분석하겠습니다."
            if on_token:
                on_token(mock_response)
            yield mock_response
            return

        # 시스템 프롬프트 구성
        system_prompt = self._build_system_prompt()

        try:
            # 에이전트 옵션 설정
            options = ClaudeAgentOptions(
                model=self.model,
                system_prompt=system_prompt,
                working_directory=str(self.project_path),
                permission_mode="acceptEdits",
            )

            # ClaudeSDKClient를 context manager로 사용
            async with ClaudeSDKClient(options=options) as client:
                # query로 메시지 전송
                await client.query(prompt=message)

                # receive_response로 응답 수신
                async for response in client.receive_response():
                    # AssistantMessage에서 텍스트 추출
                    if hasattr(response, 'blocks'):
                        for block in response.blocks:
                            # TextBlock 처리
                            if hasattr(block, 'text'):
                                text = block.text
                                if on_token:
                                    on_token(text)
                                yield text
                            # ThinkingBlock 처리
                            elif hasattr(block, 'thinking'):
                                thinking = f"[Thinking] {block.thinking}\n"
                                if on_token:
                                    on_token(thinking)
                                yield thinking

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

