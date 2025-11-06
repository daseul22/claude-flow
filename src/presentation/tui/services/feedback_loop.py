"""LLM 피드백 루프"""

from typing import Optional, Callable, AsyncIterator
from pathlib import Path

from .agent_client import AgentClient


class FeedbackLoop:
    """LLM 피드백 루프 관리"""

    def __init__(
        self,
        project_path: Path,
        condition_model: str = "claude-haiku-4-5-20251001",
        max_iterations: int = 3,
    ):
        self.project_path = project_path
        self.condition_model = condition_model
        self.max_iterations = max_iterations
        self.current_iteration = 0

    async def evaluate_condition(
        self,
        output: str,
        condition_prompt: str,
    ) -> bool:
        """조건 평가 (LLM 사용)"""
        # 조건 평가용 에이전트 생성
        evaluator = AgentClient(
            project_path=self.project_path,
            model=self.condition_model,
        )

        # 평가 프롬프트
        eval_prompt = f"""
다음 출력을 검토하고, 조건을 평가해주세요:

<출력>
{output}
</출력>

<조건>
{condition_prompt}
</조건>

조건이 충족되면 "YES"를, 충족되지 않으면 "NO"를 첫 줄에 출력하세요.
그 다음 줄에 간단한 이유를 설명하세요.
"""

        response_text = ""
        async for chunk in evaluator.send_message(eval_prompt):
            response_text += chunk

        # 첫 줄에서 YES/NO 판단
        first_line = response_text.strip().split("\n")[0].upper()

        return "YES" in first_line

    async def run_with_feedback(
        self,
        agent: AgentClient,
        initial_message: str,
        condition_prompt: str,
        on_iteration: Optional[Callable[[int, str], None]] = None,
    ) -> AsyncIterator[str]:
        """피드백 루프 실행"""
        current_message = initial_message
        self.current_iteration = 0

        while self.current_iteration < self.max_iterations:
            self.current_iteration += 1

            if on_iteration:
                on_iteration(self.current_iteration, "시작")

            # 에이전트에게 메시지 전송
            output = ""
            async for chunk in agent.send_message(current_message):
                output += chunk
                yield chunk

            # 조건 평가
            if on_iteration:
                on_iteration(self.current_iteration, "평가 중")

            condition_met = await self.evaluate_condition(output, condition_prompt)

            if condition_met:
                # 조건 충족 - 루프 종료
                if on_iteration:
                    on_iteration(self.current_iteration, "완료")
                break

            # 조건 미충족 - 다음 반복
            if self.current_iteration < self.max_iterations:
                if on_iteration:
                    on_iteration(self.current_iteration, "재시도 준비")

                # 피드백 메시지 생성
                current_message = f"""
이전 출력:
{output}

다음 조건을 충족하도록 개선해주세요:
{condition_prompt}
"""
            else:
                # 최대 반복 도달
                if on_iteration:
                    on_iteration(self.current_iteration, "최대 반복 도달")

    def reset(self):
        """반복 카운터 리셋"""
        self.current_iteration = 0

