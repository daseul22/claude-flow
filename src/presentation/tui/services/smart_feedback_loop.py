"""스마트 피드백 루프 - 설정 없이 범용적으로 작동"""

import re
from typing import Optional, Callable, AsyncIterator, Literal
from pathlib import Path
from dataclasses import dataclass

from .agent_client import AgentClient
from .feedback_loop_improved import ImprovedFeedbackLoop, EvaluationResult


# 범용 품질 평가 기준 (Fallback용)
UNIVERSAL_QUALITY_CRITERIA = """
다음 기준으로 출력을 평가하세요:

1. **완성도** (40점): 사용자 요청이 충족되었는가?
   - 모든 요구사항이 포함되었는지
   - 누락된 항목이 없는지

2. **명확성** (30점): 출력이 명확하고 이해하기 쉬운가?
   - 설명이 명확한지
   - 구조가 논리적인지

3. **정확성** (20점): 정보가 정확하고 검증 가능한가?
   - 잘못된 정보가 없는지
   - 실행 가능한지 (코드의 경우)

4. **실용성** (10점): 실제 사용 가능한 수준인가?
   - 바로 적용 가능한지
   - 추가 수정이 최소한인지

**총점 80점 이상이면 passed: true로 판단하세요.**
"""


@dataclass
class SmartFeedbackConfig:
    """스마트 피드백 루프 설정"""

    mode: Literal["auto", "semi-auto", "manual"] = "auto"
    simple_goal: str = ""  # 반자동 모드: 간단한 목표 ("테스트 커버리지 90%")
    detailed_condition: str = ""  # 수동 모드: 상세 조건 프롬프트
    max_iterations: int = 3
    quality_threshold: float = 0.8


class AutoConditionGenerator:
    """사용자 요청에서 평가 조건을 자동 생성 (LLM 기반)"""

    def __init__(self, project_path: Path, model: str = "claude-haiku-4-5-20251001"):
        self.project_path = project_path
        self.model = model

    async def generate_condition(
        self,
        user_request: str,
        on_generation_output: Optional[Callable[[str], None]] = None,
    ) -> str:
        """LLM을 사용한 조건 자동 생성 (항상 LLM 기반)"""
        generator = AgentClient(
            project_path=self.project_path,
            model=self.model,
            enable_thinking=False,
        )

        # 개선된 프롬프트: 예시 템플릿을 참고하여 더 나은 조건 생성
        generation_prompt = f"""
다음 사용자 요청을 분석하고, **출력 품질을 평가할 구체적이고 실용적인 조건**을 생성해주세요.

## 사용자 요청
{user_request}

## 작업 분석
1. 사용자가 요청한 작업의 **유형**을 파악하세요 (예: 코드 작성, 테스트 작성, 문서화, 리팩터링, 버그 수정 등).
2. 해당 작업의 **핵심 목표**를 식별하세요.
3. 출력 품질을 평가할 **구체적인 기준** 5개를 생성하세요.

## 예시 템플릿 (참고용)

**테스트 코드 작성 시:**
1. 정상 케이스 테스트가 포함되었는지
2. 엣지 케이스와 경계값 테스트가 포함되었는지
3. 예외 처리 테스트가 포함되었는지
4. 테스트 함수명이 명확한지
5. assert 메시지가 명확한지

**문서 작성 시:**
1. 프로젝트 설명이 명확한지
2. 설치 방법이 포함되었는지
3. 사용 예시가 포함되었는지
4. 주요 기능 목록이 있는지
5. 섹션 구조가 명확한지

**코드 작성 시:**
1. 요구사항이 충족되었는지
2. 에러 처리가 적절한지
3. 타입 힌팅이 있는지 (Python/TypeScript)
4. 주석/docstring이 있는지
5. 코드가 간결하고 명확한지

**리팩터링 시:**
1. 코드 가독성이 개선되었는지
2. DRY 원칙을 준수하는지 (중복 제거)
3. 함수/변수명이 명확한지
4. 복잡도가 낮아졌는지
5. 주석이 적절히 추가되었는지

**버그 수정 시:**
1. 버그가 재현되지 않는지
2. 원인이 명확히 해결되었는지
3. 관련 테스트가 추가되었는지
4. 유사한 버그 예방 코드가 있는지
5. 변경 사항이 최소화되었는지

## 응답 형식
다음 형식으로 평가 조건을 작성하세요:

품질 평가 기준:
1. [구체적인 기준 1]
2. [구체적인 기준 2]
3. [구체적인 기준 3]
4. [구체적인 기준 4]
5. [구체적인 기준 5]

**총점 80점 이상이면 passed: true로 판단하세요.**

**주의사항:**
- 조건만 출력하세요. 다른 설명은 불필요합니다.
- 사용자 요청의 맥락에 맞는 구체적이고 실용적인 기준을 작성하세요.
- 위 예시를 참고하되, 사용자 요청에 최적화된 기준을 만드세요.
"""

        condition = ""
        async for chunk in generator.send_message(generation_prompt):
            condition += chunk
            if on_generation_output:
                on_generation_output(chunk)

        # 생성 실패 시 범용 기준 사용
        if not condition.strip():
            return UNIVERSAL_QUALITY_CRITERIA

        return condition.strip()


class SmartFeedbackLoop:
    """설정 없이 범용적으로 작동하는 스마트 피드백 루프"""

    def __init__(
        self,
        project_path: Path,
        config: SmartFeedbackConfig = None,
    ):
        self.project_path = project_path
        self.config = config or SmartFeedbackConfig()

        # 조건 생성기
        self.condition_generator = AutoConditionGenerator(
            project_path=project_path,
            model="claude-haiku-4-5-20251001",  # 조건 생성은 빠른 모델 사용
        )

        # 피드백 루프 (개선 버전 사용)
        self.feedback_loop: Optional[ImprovedFeedbackLoop] = None

    async def prepare_condition(
        self,
        user_request: str,
        on_generation_output: Optional[Callable[[str], None]] = None,
    ) -> str:
        """모드에 따라 조건 준비 (항상 LLM 기반)"""
        if self.config.mode == "manual":
            # 수동 모드: 사용자 지정 조건 사용
            return self.config.detailed_condition

        elif self.config.mode == "semi-auto":
            # 반자동 모드: 간단한 목표를 LLM이 구체적인 조건으로 확장
            if self.config.simple_goal.strip():
                # LLM을 사용하여 간단한 목표를 구체적인 평가 조건으로 확장
                expanded_request = f"{user_request}\n\n목표: {self.config.simple_goal}"
                return await self.condition_generator.generate_condition(
                    expanded_request, on_generation_output
                )
            else:
                # 목표가 없으면 자동 모드로 전환
                return await self.condition_generator.generate_condition(
                    user_request, on_generation_output
                )

        else:
            # 자동 모드 (기본): LLM이 조건 자동 생성
            return await self.condition_generator.generate_condition(
                user_request, on_generation_output
            )

    async def run(
        self,
        agent: AgentClient,
        user_request: str,
        on_iteration: Optional[Callable[[int, str], None]] = None,
        on_thinking: Optional[Callable[[str], None]] = None,
        on_tool_use: Optional[Callable[[str, dict], None]] = None,
        on_eval_start: Optional[Callable[[], None]] = None,
        on_eval_output: Optional[Callable[[str], None]] = None,
        on_eval_result: Optional[Callable[[EvaluationResult], None]] = None,
        on_condition_generation: Optional[Callable[[str], None]] = None,
        on_todo_update: Optional[Callable[[list], None]] = None,
    ) -> AsyncIterator[str]:
        """스마트 피드백 루프 실행"""
        # 1. 조건 준비 (자동 생성 포함)
        if on_condition_generation:
            on_condition_generation("[조건 생성 중...]\n")

        condition_prompt = await self.prepare_condition(
            user_request, on_generation_output=on_condition_generation
        )

        if on_condition_generation:
            on_condition_generation(f"\n\n📋 생성된 평가 조건:\n{condition_prompt}\n\n")

        # 2. 피드백 루프 초기화
        self.feedback_loop = ImprovedFeedbackLoop(
            project_path=self.project_path,
            condition_model="claude-haiku-4-5-20251001",
            max_iterations=self.config.max_iterations,
            quality_threshold=self.config.quality_threshold,
        )

        # 3. 피드백 루프 실행
        async for chunk in self.feedback_loop.run_with_feedback(
            agent=agent,
            initial_message=user_request,
            condition_prompt=condition_prompt,
            on_iteration=on_iteration,
            on_thinking=on_thinking,
            on_tool_use=on_tool_use,
            on_eval_start=on_eval_start,
            on_eval_output=on_eval_output,
            on_eval_result=on_eval_result,
            on_todo_update=on_todo_update,
        ):
            yield chunk

    def get_best_result(self):
        """최적 결과 반환 (ImprovedFeedbackLoop에 위임)"""
        if self.feedback_loop:
            return self.feedback_loop.get_best_result()
        return None

    def reset(self):
        """상태 리셋"""
        if self.feedback_loop:
            self.feedback_loop.reset()


# 편의 함수
def create_smart_feedback_loop(
    project_path: Path,
    mode: Literal["auto", "semi-auto", "manual"] = "auto",
    simple_goal: str = "",
    detailed_condition: str = "",
    max_iterations: int = 3,
    quality_threshold: float = 0.8,
) -> SmartFeedbackLoop:
    """스마트 피드백 루프 생성 헬퍼"""
    config = SmartFeedbackConfig(
        mode=mode,
        simple_goal=simple_goal,
        detailed_condition=detailed_condition,
        max_iterations=max_iterations,
        quality_threshold=quality_threshold,
    )
    return SmartFeedbackLoop(project_path=project_path, config=config)
