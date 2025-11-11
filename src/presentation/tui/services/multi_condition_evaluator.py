"""다중 조건 평가 시스템"""

from typing import List, Dict, Optional, Callable
from dataclasses import dataclass
from enum import Enum

from .feedback_loop_improved import EvaluationResult
from .agent_client import AgentClient


class ConditionOperator(Enum):
    """조건 연산자"""
    AND = "and"  # 모든 조건 충족
    OR = "or"   # 하나 이상 충족
    MAJORITY = "majority"  # 과반수 충족


@dataclass
class Condition:
    """단일 조건"""
    name: str  # 조건 이름 (예: "에러 처리")
    prompt: str  # 평가 프롬프트
    weight: float = 1.0  # 가중치 (0.0 ~ 1.0)
    required: bool = False  # 필수 조건 여부


@dataclass
class MultiConditionResult:
    """다중 조건 평가 결과"""
    overall_passed: bool  # 전체 통과 여부
    overall_score: float  # 가중 평균 점수
    condition_results: Dict[str, EvaluationResult]  # 조건별 평가
    operator: ConditionOperator
    summary: str  # 요약


class MultiConditionEvaluator:
    """다중 조건 평가기"""

    def __init__(
        self,
        evaluator_client: AgentClient,
    ):
        self.evaluator_client = evaluator_client

    async def evaluate_multi_conditions(
        self,
        output: str,
        conditions: List[Condition],
        operator: ConditionOperator = ConditionOperator.AND,
        on_condition_eval: Optional[Callable[[str, EvaluationResult], None]] = None,
    ) -> MultiConditionResult:
        """다중 조건 평가"""
        condition_results = {}

        # 각 조건 개별 평가
        for condition in conditions:
            eval_prompt = f"""
다음 출력을 검토하고, **JSON 형식으로만** 평가 결과를 반환해주세요.

## 출력
```
{output[:2000]}
```

## 평가 조건: {condition.name}
{condition.prompt}

## 응답 형식 (JSON만 출력)
```json
{{
  "passed": true 또는 false,
  "score": 0.0 ~ 1.0 사이의 품질 점수,
  "reasoning": "평가 이유 (간결하게 1-2문장)",
  "suggestions": ["개선 제안 1", "개선 제안 2"]
}}
```
"""
            # 평가 실행 (기존 evaluate_condition 로직 재사용)
            from .feedback_loop_improved import ImprovedFeedbackLoop
            temp_loop = ImprovedFeedbackLoop(
                project_path=self.evaluator_client.project_path,
                condition_model=self.evaluator_client.model,
            )

            result = await temp_loop.evaluate_condition(
                output=output,
                condition_prompt=condition.prompt,
            )

            condition_results[condition.name] = result

            # 콜백 호출
            if on_condition_eval:
                on_condition_eval(condition.name, result)

        # 전체 평가 계산
        overall_passed, overall_score, summary = self._calculate_overall(
            conditions, condition_results, operator
        )

        return MultiConditionResult(
            overall_passed=overall_passed,
            overall_score=overall_score,
            condition_results=condition_results,
            operator=operator,
            summary=summary,
        )

    def _calculate_overall(
        self,
        conditions: List[Condition],
        results: Dict[str, EvaluationResult],
        operator: ConditionOperator,
    ) -> tuple[bool, float, str]:
        """전체 평가 계산"""
        # 필수 조건 체크
        required_conditions = [c for c in conditions if c.required]
        if required_conditions:
            for cond in required_conditions:
                if not results[cond.name].passed:
                    return (
                        False,
                        0.0,
                        f"필수 조건 '{cond.name}'이 충족되지 않음"
                    )

        # 가중 평균 점수
        total_weight = sum(c.weight for c in conditions)
        weighted_score = sum(
            results[c.name].score * c.weight for c in conditions
        ) / total_weight

        # 연산자별 통과 판단
        passed_count = sum(1 for c in conditions if results[c.name].passed)
        total_count = len(conditions)

        if operator == ConditionOperator.AND:
            overall_passed = passed_count == total_count
            summary = f"모든 조건 충족 필요 ({passed_count}/{total_count} 통과)"

        elif operator == ConditionOperator.OR:
            overall_passed = passed_count > 0
            summary = f"하나 이상 조건 충족 ({passed_count}/{total_count} 통과)"

        elif operator == ConditionOperator.MAJORITY:
            overall_passed = passed_count > total_count / 2
            summary = f"과반수 조건 충족 ({passed_count}/{total_count} 통과)"

        else:
            overall_passed = False
            summary = "알 수 없는 연산자"

        return overall_passed, weighted_score, summary


# 사용 예시
async def example_multi_condition():
    """다중 조건 평가 예시"""
    from pathlib import Path

    project_path = Path.cwd()
    evaluator_client = AgentClient(
        project_path=project_path,
        model="claude-haiku-4-5-20251001"
    )

    multi_evaluator = MultiConditionEvaluator(evaluator_client)

    # 조건 정의
    conditions = [
        Condition(
            name="에러 처리",
            prompt="try-except 블록이 적절히 사용되었는지",
            weight=2.0,  # 중요도 높음
            required=True  # 필수
        ),
        Condition(
            name="타입 힌팅",
            prompt="함수 파라미터와 반환값에 타입 힌팅이 있는지",
            weight=1.0,
            required=False
        ),
        Condition(
            name="문서화",
            prompt="docstring이 있고 명확한지",
            weight=1.5,
            required=False
        ),
        Condition(
            name="테스트",
            prompt="테스트 코드가 포함되어 있는지",
            weight=1.0,
            required=False
        ),
    ]

    # 평가 실행
    output = "..."  # 에이전트 출력

    result = await multi_evaluator.evaluate_multi_conditions(
        output=output,
        conditions=conditions,
        operator=ConditionOperator.AND,  # 모든 조건 충족 필요
        on_condition_eval=lambda name, res: print(
            f"[{name}] 점수: {res.score:.2f} - {res.reasoning}"
        ),
    )

    # 결과 출력
    print(f"\n전체 결과: {'✅ 통과' if result.overall_passed else '❌ 미흡'}")
    print(f"전체 점수: {result.overall_score:.2f}")
    print(f"요약: {result.summary}")

    # 조건별 상세
    for name, eval_result in result.condition_results.items():
        print(f"\n[{name}]")
        print(f"  점수: {eval_result.score:.2f}")
        print(f"  통과: {eval_result.passed}")
        print(f"  이유: {eval_result.reasoning}")
