"""개선된 LLM 피드백 루프"""

import json
import re
from typing import Optional, Callable, AsyncIterator, List, Dict, Any
from pathlib import Path
from dataclasses import dataclass

from .agent_client import AgentClient


@dataclass
class EvaluationResult:
    """평가 결과 구조화"""
    passed: bool  # 조건 충족 여부
    score: float  # 0.0 ~ 1.0 (품질 점수)
    reasoning: str  # 평가 이유
    suggestions: List[str]  # 개선 제안
    raw_response: str  # 원본 LLM 응답


@dataclass
class IterationHistory:
    """반복 이력"""
    iteration: int
    output: str
    evaluation: EvaluationResult
    timestamp: str


class ImprovedFeedbackLoop:
    """개선된 LLM 피드백 루프"""

    def __init__(
        self,
        project_path: Path,
        condition_model: str = "claude-haiku-4-5-20251001",
        max_iterations: int = 3,
        quality_threshold: float = 0.8,  # 조기 종료 임계값
    ):
        self.project_path = project_path
        self.condition_model = condition_model
        self.max_iterations = max_iterations
        self.quality_threshold = quality_threshold
        self.current_iteration = 0
        self.history: List[IterationHistory] = []  # 이력 누적

    async def evaluate_condition(
        self,
        output: str,
        condition_prompt: str,
        previous_attempts: Optional[List[IterationHistory]] = None,
        on_eval_output: Optional[Callable[[str], None]] = None,
    ) -> EvaluationResult:
        """구조화된 조건 평가"""
        evaluator = AgentClient(
            project_path=self.project_path,
            model=self.condition_model,
            enable_thinking=False,  # 평가는 빠르게
        )

        # 이전 시도 컨텍스트 구성
        previous_context = ""
        if previous_attempts:
            previous_context = "\n\n## 이전 시도 기록\n"
            for attempt in previous_attempts:
                previous_context += f"""
### 시도 {attempt.iteration}
- 품질 점수: {attempt.evaluation.score:.2f}
- 평가: {attempt.evaluation.reasoning}
- 제안: {', '.join(attempt.evaluation.suggestions)}
"""

        # 구조화된 평가 프롬프트
        eval_prompt = f"""다음 출력을 검토하고, **JSON 형식으로만** 평가 결과를 반환해주세요.

## 출력
```
{output[:2000]}  # 너무 길면 잘라냄
```

## 평가 조건
{condition_prompt}
{previous_context}

## 응답 형식 (JSON만 출력)
```json
{{
  "passed": true 또는 false,
  "score": 0.0 ~ 1.0 사이의 품질 점수,
  "reasoning": "평가 이유 (간결하게 1-2문장)",
  "suggestions": ["개선 제안 1", "개선 제안 2"]
}}
```

**주의**: JSON 외에는 아무것도 출력하지 마세요.
"""

        response_text = ""
        async for chunk in evaluator.send_message(eval_prompt):
            response_text += chunk
            if on_eval_output:
                on_eval_output(chunk)

        # JSON 파싱 (강건하게)
        try:
            # 코드 블록 제거
            json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # 직접 JSON 찾기
                json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                else:
                    raise ValueError("JSON을 찾을 수 없습니다")

            data = json.loads(json_str)

            return EvaluationResult(
                passed=bool(data.get("passed", False)),
                score=float(data.get("score", 0.0)),
                reasoning=data.get("reasoning", ""),
                suggestions=data.get("suggestions", []),
                raw_response=response_text,
            )

        except Exception as e:
            # 파싱 실패 - 폴백: YES/NO 기반 평가
            first_line = response_text.strip().split("\n")[0].upper()
            passed = "YES" in first_line or "TRUE" in first_line or "통과" in first_line

            return EvaluationResult(
                passed=passed,
                score=1.0 if passed else 0.3,
                reasoning=f"(파싱 실패) {response_text[:200]}",
                suggestions=["평가 응답 파싱 실패"],
                raw_response=response_text,
            )

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
        on_eval_result: Optional[Callable[[EvaluationResult], None]] = None,
        on_todo_update: Optional[Callable[[list], None]] = None,
    ) -> AsyncIterator[str]:
        """개선된 피드백 루프 실행"""
        current_message = initial_message
        self.current_iteration = 0
        self.history = []

        while self.current_iteration < self.max_iterations:
            self.current_iteration += 1

            if on_iteration:
                on_iteration(self.current_iteration, "시작")

            # 에이전트 실행
            output = ""
            async for chunk in agent.send_message(
                current_message,
                on_thinking=on_thinking,
                on_tool_use=on_tool_use,
                on_todo_update=on_todo_update if on_todo_update else None,
            ):
                output += chunk
                yield chunk

            # 평가 시작
            if on_eval_start:
                on_eval_start()

            if on_iteration:
                on_iteration(self.current_iteration, "평가 중")

            # 구조화된 평가 (이전 시도 컨텍스트 포함)
            eval_result = await self.evaluate_condition(
                output,
                condition_prompt,
                previous_attempts=self.history,
                on_eval_output=on_eval_output,
            )

            # 이력 저장
            from datetime import datetime
            self.history.append(
                IterationHistory(
                    iteration=self.current_iteration,
                    output=output,
                    evaluation=eval_result,
                    timestamp=datetime.now().isoformat(),
                )
            )

            # 평가 결과 콜백
            if on_eval_result:
                on_eval_result(eval_result)

            # 조건 충족 또는 품질 임계값 도달
            if eval_result.passed or eval_result.score >= self.quality_threshold:
                if on_iteration:
                    status = "완료" if eval_result.passed else f"품질 충족 (점수: {eval_result.score:.2f})"
                    on_iteration(self.current_iteration, status)
                break

            # 품질 개선도 체크 (정체 상태 감지)
            if len(self.history) >= 2:
                prev_score = self.history[-2].evaluation.score
                current_score = eval_result.score
                improvement = current_score - prev_score

                if improvement < 0.05:  # 개선도가 5% 미만
                    if on_iteration:
                        on_iteration(self.current_iteration, "개선 정체 감지 - 조기 종료")
                    break

            # 다음 반복 준비
            if self.current_iteration < self.max_iterations:
                if on_iteration:
                    on_iteration(self.current_iteration, "재시도 준비")

                # 피드백 메시지 생성 (개선 제안 포함)
                if feedback_input.strip():
                    current_message = feedback_input.replace("{{output}}", output).replace(
                        "{{condition}}", condition_prompt
                    ).replace("{{suggestions}}", "\n".join(eval_result.suggestions))
                else:
                    # 기본 회귀 메시지 (개선 제안 포함)
                    suggestions_text = "\n".join(
                        f"- {s}" for s in eval_result.suggestions
                    )
                    current_message = f"""이전 출력:
```
{output[:1000]}
```

현재 품질 점수: {eval_result.score:.2f} / 1.0
평가: {eval_result.reasoning}

다음 조건을 충족하도록 개선해주세요:
{condition_prompt}

개선 제안:
{suggestions_text}

위 제안을 반영하여 출력을 개선해주세요.
"""
            else:
                if on_iteration:
                    on_iteration(self.current_iteration, "최대 반복 도달")

    def reset(self):
        """상태 리셋"""
        self.current_iteration = 0
        self.history = []

    def get_best_result(self) -> Optional[IterationHistory]:
        """가장 높은 점수의 결과 반환"""
        if not self.history:
            return None
        return max(self.history, key=lambda h: h.evaluation.score)
