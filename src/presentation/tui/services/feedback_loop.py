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
        on_eval_output: Optional[Callable[[str], None]] = None,
    ) -> tuple[bool, str]:
        """조건 평가 (LLM 사용)
        
        Returns:
            (조건 충족 여부, 평가 응답)
        """
        # 조건 평가용 에이전트 생성
        model_name = self.condition_model
        
        # SDK 형식이 아니면 변환 (안전장치)
        if not model_name.startswith("claude-"):
            model_name = "claude-haiku-4-5-20251001"
        
        evaluator = AgentClient(
            project_path=self.project_path,
            model=model_name,
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
            # 평가 과정을 UI에 표시
            if on_eval_output:
                on_eval_output(chunk)

        # 첫 줄에서 YES/NO 판단
        first_line = response_text.strip().split("\n")[0].upper()

        return ("YES" in first_line, response_text)

    async def run_with_feedback(
        self,
        agent: AgentClient,
        initial_message: str,
        condition_prompt: str,
        feedback_input: str = "",
        on_iteration: Optional[Callable[[int, str], None]] = None,
        on_thinking: Optional[Callable[[str], None]] = None,
        on_tool_use: Optional[Callable[[str, dict], None]] = None,
        on_eval_start: Optional[Callable[[], None]] = None,
        on_eval_output: Optional[Callable[[str], None]] = None,
        on_eval_result: Optional[Callable[[bool, str], None]] = None,
        on_todo_update: Optional[Callable[[list], None]] = None,
    ) -> AsyncIterator[str]:
        """피드백 루프 실행
        
        Args:
            feedback_input: 회귀 시 에이전트에게 전달할 입력 메시지 (비어있으면 기본 메시지 사용)
        """
        current_message = initial_message
        self.current_iteration = 0

        while self.current_iteration < self.max_iterations:
            self.current_iteration += 1

            if on_iteration:
                on_iteration(self.current_iteration, "시작")

            # 에이전트에게 메시지 전송 (콜백 전달)
            output = ""
            async for chunk in agent.send_message(
                current_message,
                on_thinking=on_thinking,
                on_tool_use=on_tool_use,
                on_todo_update=on_todo_update if on_todo_update else None,
            ):
                output += chunk
                yield chunk

            # 조건 평가 시작 알림
            if on_eval_start:
                on_eval_start()
            
            if on_iteration:
                on_iteration(self.current_iteration, "평가 중")

            # 조건 평가 (평가 출력도 UI에 표시)
            condition_met, eval_response = await self.evaluate_condition(
                output, 
                condition_prompt,
                on_eval_output=on_eval_output
            )
            
            # 평가 결과 콜백
            if on_eval_result:
                on_eval_result(condition_met, eval_response)

            if condition_met:
                # 조건 충족 - 루프 종료
                if on_iteration:
                    on_iteration(self.current_iteration, "완료")
                break

            # 조건 미충족 - 다음 반복
            if self.current_iteration < self.max_iterations:
                if on_iteration:
                    on_iteration(self.current_iteration, "재시도 준비")

                # 피드백 메시지 생성 (사용자 정의 메시지 또는 기본 메시지)
                if feedback_input.strip():
                    # 사용자가 정의한 회귀 입력 사용
                    # {{output}}, {{condition}} 치환 지원
                    current_message = feedback_input.replace("{{output}}", output).replace("{{condition}}", condition_prompt)
                else:
                    # 기본 회귀 메시지
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

