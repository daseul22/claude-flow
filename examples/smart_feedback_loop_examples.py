"""스마트 피드백 루프 사용 예시"""

import asyncio
from pathlib import Path
from src.presentation.tui.services.agent_client import AgentClient
from src.presentation.tui.services.smart_feedback_loop import (
    SmartFeedbackLoop,
    SmartFeedbackConfig,
    create_smart_feedback_loop,
)
from src.presentation.tui.services.feedback_loop_improved import EvaluationResult


async def example_1_auto_mode():
    """예시 1: 자동 모드 - 설정 없이 바로 사용"""
    print("=" * 60)
    print("예시 1: 자동 모드 (설정 없음, 조건 자동 생성)")
    print("=" * 60)

    project_path = Path.cwd()
    agent = AgentClient(project_path=project_path, model="claude-sonnet-4.5")

    # 스마트 피드백 루프 생성 (기본 설정)
    smart_loop = create_smart_feedback_loop(
        project_path=project_path,
        mode="auto",  # 자동 모드
    )

    # 사용자 요청 (조건 없음!)
    user_request = "파이썬으로 이진 탐색 함수를 구현해줘"

    # 콜백 정의
    def on_condition_gen(chunk: str):
        print(chunk, end="", flush=True)

    def on_iteration(iteration: int, status: str):
        print(f"\n\n{'='*50}")
        print(f"🔄 반복 {iteration}/{smart_loop.config.max_iterations}: {status}")
        print(f"{'='*50}\n")

    def on_eval_result(eval_result: EvaluationResult):
        print(f"\n📊 평가 결과:")
        print(f"  • 점수: {eval_result.score:.2f} / 1.0")
        print(f"  • 통과: {'✅ YES' if eval_result.passed else '❌ NO'}")
        print(f"  • 이유: {eval_result.reasoning}")
        if eval_result.suggestions:
            print(f"  • 개선 제안:")
            for suggestion in eval_result.suggestions:
                print(f"    - {suggestion}")

    # 실행
    print("\n📝 요청:", user_request)
    print("\n" + "=" * 60)

    async for chunk in smart_loop.run(
        agent=agent,
        user_request=user_request,
        on_condition_generation=on_condition_gen,
        on_iteration=on_iteration,
        on_eval_result=on_eval_result,
    ):
        print(chunk, end="", flush=True)

    # 최종 결과
    best = smart_loop.get_best_result()
    if best:
        print(f"\n\n✨ 최적 결과 (시도 {best.iteration}):")
        print(f"   점수: {best.evaluation.score:.2f}")


async def example_2_semi_auto_mode():
    """예시 2: 반자동 모드 - 간단한 목표만 입력"""
    print("\n\n" + "=" * 60)
    print("예시 2: 반자동 모드 (간단한 목표만 입력)")
    print("=" * 60)

    project_path = Path.cwd()
    agent = AgentClient(project_path=project_path)

    # 간단한 목표만 지정
    smart_loop = create_smart_feedback_loop(
        project_path=project_path,
        mode="semi-auto",
        simple_goal="테스트 커버리지가 90% 이상이어야 함",  # 목표만 입력
    )

    user_request = "calculate_discount 함수에 대한 pytest 테스트를 작성해줘"

    print(f"\n📝 요청: {user_request}")
    print(f"🎯 목표: {smart_loop.config.simple_goal}")
    print("\n" + "=" * 60)

    async for chunk in smart_loop.run(
        agent=agent,
        user_request=user_request,
        on_iteration=lambda i, s: print(f"\n[{i}] {s}"),
        on_eval_result=lambda r: print(
            f"  → 점수: {r.score:.2f}, 통과: {r.passed}"
        ),
    ):
        print(chunk, end="", flush=True)


async def example_3_template_matching():
    """예시 3: 템플릿 매칭 - 빠른 경로"""
    print("\n\n" + "=" * 60)
    print("예시 3: 템플릿 매칭 (키워드 기반 빠른 경로)")
    print("=" * 60)

    project_path = Path.cwd()
    agent = AgentClient(project_path=project_path)

    smart_loop = create_smart_feedback_loop(project_path=project_path)

    # 키워드가 명확한 요청들
    test_cases = [
        "이 코드를 리팩터링해줘",  # → refactor 템플릿
        "README 파일을 작성해줘",  # → document 템플릿
        "버그를 수정해줘",  # → bugfix 템플릿
    ]

    for user_request in test_cases:
        print(f"\n📝 요청: {user_request}")

        # 조건 생성 (템플릿 매칭)
        condition = smart_loop.condition_generator.get_template_condition(user_request)
        print(f"\n🎯 매칭된 템플릿:\n{condition[:150]}...")


async def example_4_universal_quality():
    """예시 4: 범용 품질 평가 - 어떤 요청에도 작동"""
    print("\n\n" + "=" * 60)
    print("예시 4: 범용 품질 평가 (키워드 없는 요청)")
    print("=" * 60)

    project_path = Path.cwd()
    agent = AgentClient(project_path=project_path)

    smart_loop = create_smart_feedback_loop(
        project_path=project_path,
        quality_threshold=0.85,  # 높은 품질 요구
    )

    # 키워드가 애매한 일반 요청
    user_request = "사용자 인증 시스템을 설계해줘"

    print(f"\n📝 요청: {user_request}")
    print("(키워드 매칭 실패 → 범용 품질 평가 사용)")
    print("\n" + "=" * 60)

    async for chunk in smart_loop.run(
        agent=agent,
        user_request=user_request,
        on_iteration=lambda i, s: print(f"\n[{i}] {s}"),
        on_eval_result=lambda r: print(
            f"  완성도: {r.score*0.4:.1f}/40, "
            f"명확성: {r.score*0.3:.1f}/30, "
            f"정확성: {r.score*0.2:.1f}/20, "
            f"실용성: {r.score*0.1:.1f}/10"
        ),
    ):
        print(chunk, end="", flush=True)


async def example_5_comparison():
    """예시 5: 기존 vs 스마트 피드백 루프 비교"""
    print("\n\n" + "=" * 60)
    print("예시 5: 기존 vs 스마트 피드백 루프 비교")
    print("=" * 60)

    print("\n📊 기존 피드백 루프 (feedback_loop_improved.py):")
    print("  ❌ 문제점:")
    print("     - condition_prompt를 수동으로 입력해야 함")
    print("     - 조건 작성법을 알아야 함")
    print("     - 설정이 복잡함")
    print("  ✅ 장점:")
    print("     - 세밀한 제어 가능")
    print("     - 고급 사용자에게 유용")

    print("\n✨ 스마트 피드백 루프 (smart_feedback_loop.py):")
    print("  ✅ 장점:")
    print("     - 조건 자동 생성 (LLM 활용)")
    print("     - 템플릿 매칭으로 빠른 실행")
    print("     - 범용 품질 평가로 모든 요청 지원")
    print("     - 3가지 모드 (자동/반자동/수동)")
    print("     - 초보자도 쉽게 사용")
    print("  ⚠️ 단점:")
    print("     - 조건 생성 시 약간의 지연 (템플릿 매칭으로 완화)")


async def example_6_tui_integration():
    """예시 6: TUI 앱 통합 방법"""
    print("\n\n" + "=" * 60)
    print("예시 6: TUI 앱 통합 방법")
    print("=" * 60)

    print("""
# app.py 통합 예시

from .services.smart_feedback_loop import create_smart_feedback_loop

class ClaudeFlowApp(App):
    def __init__(self, project_path: Path, **kwargs):
        # ... 기존 코드 ...

        # 스마트 피드백 루프 (자동 모드)
        self.smart_feedback_loop = create_smart_feedback_loop(
            project_path=self.project_path,
            mode="auto",  # 기본: 자동 모드
            max_iterations=3,
            quality_threshold=0.8,
        )

    async def on_message_submit(self, message: str):
        # 피드백 루프 활성화 여부 확인
        if self.project_settings.get("smart_feedback_enabled", False):
            # 스마트 피드백 루프 사용
            async for chunk in self.smart_feedback_loop.run(
                agent=self.agent,
                user_request=message,
                on_iteration=self.handle_iteration,
                on_eval_result=self.handle_eval_result,
            ):
                self.chat_view.append_chunk(chunk)
        else:
            # 일반 모드
            async for chunk in self.agent.send_message(message):
                self.chat_view.append_chunk(chunk)

# 설정 모달에 토글 추가
"smart_feedback_enabled": True/False  # 기본: False
    """)


async def example_7_one_click_toggle():
    """예시 7: One-Click 토글 시뮬레이션"""
    print("\n\n" + "=" * 60)
    print("예시 7: One-Click 피드백 루프 토글")
    print("=" * 60)

    project_path = Path.cwd()
    agent = AgentClient(project_path=project_path)

    # 토글 상태
    feedback_enabled = False

    print("\n[일반 모드]")
    print("  사용자: 파이썬으로 파일 읽기 함수를 작성해줘")
    print("  → 1회 실행 → 완료")

    print("\n(사용자가 '🔁 피드백 루프' 버튼 클릭)")
    feedback_enabled = True

    print("\n[🔁 피드백 루프 모드]")
    print("  사용자: 파이썬으로 파일 읽기 함수를 작성해줘")
    print("  → 조건 자동 생성 → 3회 반복 → 품질 80점 이상 → 완료")

    if feedback_enabled:
        smart_loop = create_smart_feedback_loop(project_path=project_path)
        user_request = "파이썬으로 파일 읽기 함수를 작성해줘"

        print(f"\n📝 요청: {user_request}")
        print("\n" + "=" * 60)

        async for chunk in smart_loop.run(
            agent=agent,
            user_request=user_request,
            on_iteration=lambda i, s: print(f"\n[{i}/3] {s}"),
            on_eval_result=lambda r: print(f"  점수: {r.score:.2f}"),
        ):
            print(chunk, end="", flush=True)


async def main():
    """모든 예시 실행"""
    print("🚀 스마트 피드백 루프 - 사용 예시\n")
    print("=" * 60)

    examples = {
        "1": ("자동 모드 (설정 없음)", example_1_auto_mode),
        "2": ("반자동 모드 (목표만 입력)", example_2_semi_auto_mode),
        "3": ("템플릿 매칭 (빠른 경로)", example_3_template_matching),
        "4": ("범용 품질 평가", example_4_universal_quality),
        "5": ("기존 vs 스마트 비교", example_5_comparison),
        "6": ("TUI 통합 방법", example_6_tui_integration),
        "7": ("One-Click 토글", example_7_one_click_toggle),
    }

    print("\n실행할 예시를 선택하세요:")
    for key, (name, _) in examples.items():
        print(f"  {key}. {name}")
    print("  0. 모두 실행")

    choice = input("\n선택 (0-7): ").strip()

    if choice == "0":
        for name, func in examples.values():
            await func()
            await asyncio.sleep(1)
    elif choice in examples:
        _, func = examples[choice]
        await func()
    else:
        print("잘못된 선택입니다.")


if __name__ == "__main__":
    asyncio.run(main())
