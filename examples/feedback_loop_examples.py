"""피드백 루프 실전 예시"""

import asyncio
from pathlib import Path
from src.presentation.tui.services.agent_client import AgentClient
from src.presentation.tui.services.feedback_loop_improved import ImprovedFeedbackLoop, EvaluationResult


async def example_1_code_quality():
    """예시 1: 코드 품질 자동 검증"""
    print("=== 예시 1: 코드 품질 자동 검증 ===\n")

    project_path = Path.cwd()
    agent = AgentClient(project_path=project_path, model="claude-sonnet-4.5")

    feedback_loop = ImprovedFeedbackLoop(
        project_path=project_path,
        condition_model="claude-haiku-4-5-20251001",
        max_iterations=3,
        quality_threshold=0.85,  # 85점 이상이면 통과
    )

    # 사용자 요청
    initial_message = "파이썬으로 파일을 안전하게 읽는 함수를 작성해줘. 함수명은 read_file_safe로 해줘."

    # 평가 조건
    condition_prompt = """
다음 기준으로 코드를 평가하세요:
1. try-except로 에러 처리가 되어 있는지 (필수)
2. 파일이 존재하지 않는 경우를 처리하는지 (필수)
3. docstring이 있는지 (권장)
4. 타입 힌팅이 있는지 (권장)
5. 간단한 사용 예시가 주석에 있는지 (선택)

필수 항목이 모두 충족되고, 권장 항목 중 2개 이상이면 passed: true로 판단하세요.
    """

    # 콜백 정의
    def on_iteration(iteration: int, status: str):
        print(f"\n[반복 {iteration}] {status}")

    def on_eval_result(eval_result: EvaluationResult):
        print(f"\n📊 평가 결과:")
        print(f"  • 점수: {eval_result.score:.2f} / 1.0")
        print(f"  • 통과: {'✅ YES' if eval_result.passed else '❌ NO'}")
        print(f"  • 이유: {eval_result.reasoning}")
        if eval_result.suggestions:
            print(f"  • 개선 제안:")
            for suggestion in eval_result.suggestions:
                print(f"    - {suggestion}")

    # 피드백 루프 실행
    print("실행 중...\n")
    final_output = ""
    async for chunk in feedback_loop.run_with_feedback(
        agent=agent,
        initial_message=initial_message,
        condition_prompt=condition_prompt,
        on_iteration=on_iteration,
        on_eval_result=on_eval_result,
    ):
        print(chunk, end="", flush=True)
        final_output += chunk

    # 최종 결과
    best_result = feedback_loop.get_best_result()
    if best_result:
        print(f"\n\n✨ 최적 결과 (시도 {best_result.iteration}):")
        print(f"   점수: {best_result.evaluation.score:.2f}")
        print(f"   출력: {best_result.output[:200]}...")


async def example_2_documentation():
    """예시 2: 문서 완성도 검증"""
    print("\n\n=== 예시 2: 문서 완성도 검증 ===\n")

    project_path = Path.cwd()
    agent = AgentClient(project_path=project_path)

    feedback_loop = ImprovedFeedbackLoop(
        project_path=project_path,
        max_iterations=4,
        quality_threshold=0.8,
    )

    initial_message = "이 프로젝트의 README.md 파일 초안을 작성해줘."

    condition_prompt = """
다음 섹션들이 포함되어 있는지 확인하세요:
1. 프로젝트 제목 및 간단한 설명
2. 주요 기능 목록
3. 설치 방법
4. 사용 예시
5. 라이선스 정보

각 섹션의 품질도 평가하세요 (너무 짧거나 불명확하면 감점).
    """

    # 사용자 정의 회귀 입력
    feedback_input = """
이전 출력을 보완해주세요:

{{output}}

다음 개선 제안을 반영하세요:
{{suggestions}}

조건: {{condition}}
    """

    async for chunk in feedback_loop.run_with_feedback(
        agent=agent,
        initial_message=initial_message,
        condition_prompt=condition_prompt,
        feedback_input=feedback_input,
    ):
        print(chunk, end="", flush=True)


async def example_3_test_generation():
    """예시 3: 테스트 코드 생성 및 검증"""
    print("\n\n=== 예시 3: 테스트 코드 생성 및 검증 ===\n")

    project_path = Path.cwd()
    agent = AgentClient(project_path=project_path, model="claude-sonnet-4.5")

    feedback_loop = ImprovedFeedbackLoop(
        project_path=project_path,
        max_iterations=3,
        quality_threshold=0.9,  # 테스트는 높은 품질 요구
    )

    initial_message = """
다음 함수에 대한 pytest 테스트를 작성해줘:

def calculate_discount(price: float, discount_percent: float) -> float:
    if discount_percent < 0 or discount_percent > 100:
        raise ValueError("할인율은 0~100 사이여야 합니다")
    return price * (1 - discount_percent / 100)
    """

    condition_prompt = """
테스트 코드가 다음을 모두 포함하는지 확인:
1. 정상 케이스 테스트
2. 경계값 테스트 (0%, 100%)
3. 예외 처리 테스트 (음수, 100 초과)
4. 부동소수점 정밀도 테스트
5. 테스트 함수명이 명확한지

모든 케이스가 포함되어야 passed: true
    """

    def on_eval_result(eval_result: EvaluationResult):
        # 상세한 피드백 표시
        if not eval_result.passed:
            print(f"\n⚠️ 테스트가 불완전합니다 (점수: {eval_result.score:.2f})")
            print(f"   누락된 항목: {', '.join(eval_result.suggestions)}")

    async for chunk in feedback_loop.run_with_feedback(
        agent=agent,
        initial_message=initial_message,
        condition_prompt=condition_prompt,
        on_eval_result=on_eval_result,
    ):
        print(chunk, end="", flush=True)

    # 이력 분석
    print("\n\n📈 품질 개선 추이:")
    for history_item in feedback_loop.history:
        print(
            f"  시도 {history_item.iteration}: "
            f"{history_item.evaluation.score:.2f} "
            f"({'통과' if history_item.evaluation.passed else '미흡'})"
        )


async def example_4_early_termination():
    """예시 4: 조기 종료 메커니즘"""
    print("\n\n=== 예시 4: 조기 종료 메커니즘 ===\n")

    project_path = Path.cwd()
    agent = AgentClient(project_path=project_path)

    feedback_loop = ImprovedFeedbackLoop(
        project_path=project_path,
        max_iterations=10,  # 최대 10회
        quality_threshold=0.85,  # 85점 도달 시 조기 종료
    )

    initial_message = "간단한 TODO 앱 구조를 설계해줘 (클래스 다이어그램)"

    condition_prompt = """
TODO 앱에 필요한 핵심 요소가 포함되어 있는지:
1. Task 모델 (필수 필드: id, title, completed)
2. TaskManager 클래스
3. CRUD 메서드들
4. 간단한 사용 예시
    """

    iteration_count = 0

    def on_iteration(iteration: int, status: str):
        nonlocal iteration_count
        iteration_count = iteration
        print(f"\n[시도 {iteration}] {status}")

    async for chunk in feedback_loop.run_with_feedback(
        agent=agent,
        initial_message=initial_message,
        condition_prompt=condition_prompt,
        on_iteration=on_iteration,
    ):
        print(chunk, end="", flush=True)

    print(f"\n\n📌 총 {iteration_count}회 시도 (최대 10회 중)")
    print(f"   조기 종료 이유: {'품질 임계값 도달' if feedback_loop.get_best_result().evaluation.score >= 0.85 else '개선 정체'}")


async def example_5_comparison():
    """예시 5: 기존 vs 개선 버전 비교"""
    print("\n\n=== 예시 5: 기존 vs 개선 버전 성능 비교 ===\n")

    project_path = Path.cwd()

    # 동일한 조건으로 테스트
    test_message = "파이썬으로 이진 탐색 함수를 구현해줘"
    test_condition = "함수가 정확하고, 시간 복잡도가 O(log n)인지 확인"

    # 기존 버전 (시뮬레이션)
    print("📊 기존 버전 (YES/NO 판단):")
    print("  시도 1: NO → 재시도")
    print("  시도 2: YES → 완료")
    print("  문제점: 왜 NO인지, 어떻게 개선할지 불명확\n")

    # 개선 버전
    print("✨ 개선 버전 (구조화된 평가):")
    agent = AgentClient(project_path=project_path, model="claude-sonnet-4.5")
    feedback_loop = ImprovedFeedbackLoop(
        project_path=project_path,
        max_iterations=3,
        quality_threshold=0.85,
    )

    async for chunk in feedback_loop.run_with_feedback(
        agent=agent,
        initial_message=test_message,
        condition_prompt=test_condition,
        on_iteration=lambda i, s: print(f"  [{i}] {s}"),
        on_eval_result=lambda r: print(
            f"    → 점수: {r.score:.2f}, 제안: {r.suggestions}"
        ),
    ):
        pass

    print("\n  장점:")
    print("  ✅ 점수로 정량 평가")
    print("  ✅ 구체적인 개선 제안")
    print("  ✅ 이력 기반 학습")
    print("  ✅ 조기 종료로 토큰 절약")


async def main():
    """모든 예시 실행"""
    print("🔄 Claude Flow TUI - 개선된 피드백 루프 예시\n")
    print("=" * 60)

    # 예시 선택
    examples = {
        "1": ("코드 품질 검증", example_1_code_quality),
        "2": ("문서 완성도 검증", example_2_documentation),
        "3": ("테스트 코드 생성", example_3_test_generation),
        "4": ("조기 종료", example_4_early_termination),
        "5": ("버전 비교", example_5_comparison),
    }

    print("\n실행할 예시를 선택하세요:")
    for key, (name, _) in examples.items():
        print(f"  {key}. {name}")
    print("  0. 모두 실행")

    choice = input("\n선택 (0-5): ").strip()

    if choice == "0":
        for name, func in examples.values():
            await func()
            await asyncio.sleep(2)  # 예시 간 간격
    elif choice in examples:
        _, func = examples[choice]
        await func()
    else:
        print("잘못된 선택입니다.")


if __name__ == "__main__":
    asyncio.run(main())
