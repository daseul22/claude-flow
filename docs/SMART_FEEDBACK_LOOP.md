# 스마트 피드백 루프 가이드

> **설정 없이 범용적으로 작동하는 피드백 루프**

## 📋 목차

1. [개요](#개요)
2. [기존 피드백 루프의 문제점](#기존-피드백-루프의-문제점)
3. [스마트 피드백 루프 특징](#스마트-피드백-루프-특징)
4. [사용 방법](#사용-방법)
5. [TUI 앱 통합](#tui-앱-통합)
6. [API 레퍼런스](#api-레퍼런스)
7. [예시](#예시)

---

## 개요

**스마트 피드백 루프**는 사용자가 평가 조건을 수동으로 입력하지 않아도, **LLM이 자동으로 조건을 추론**하여 피드백 루프를 실행하는 시스템입니다.

### 핵심 기능

- ✅ **자동 조건 생성**: 사용자 요청 분석 → 평가 조건 자동 생성
- ✅ **템플릿 매칭**: 키워드 감지로 빠른 조건 선택 (test, document, refactor 등)
- ✅ **범용 품질 평가**: 키워드가 없어도 완성도/명확성/정확성 기준으로 평가
- ✅ **3가지 모드**: 자동 / 반자동 / 수동
- ✅ **초보자 친화적**: 설정 없이 바로 사용 가능

---

## 기존 피드백 루프의 문제점

### ❌ 문제점

| 문제 | 설명 | 영향 |
|------|------|------|
| **조건 의존성** | `condition_prompt` 필수 입력 | 진입장벽 높음 |
| **설정 복잡도** | 6개 설정 항목 필요 | 사용자 혼란 |
| **UX 문제** | 매번 조건을 새로 입력해야 함 | 번거로움 |
| **범용성 부족** | 특정 유스케이스만 지원 | 일반 대화에 부적합 |

### 기존 방식 예시

```python
# 기존: 사용자가 조건을 수동 작성해야 함
feedback_loop = ImprovedFeedbackLoop(...)
condition_prompt = """
코드 품질 기준:
1. try-except로 에러 처리가 되어 있는지
2. docstring이 있는지
3. 타입 힌팅이 있는지
...
"""  # ← 매번 이렇게 작성해야 함!

async for chunk in feedback_loop.run_with_feedback(
    agent=agent,
    initial_message=user_request,
    condition_prompt=condition_prompt,  # 필수!
):
    print(chunk)
```

---

## 스마트 피드백 루프 특징

### ✨ 핵심 개선사항

#### 1. 자동 조건 생성

사용자 요청을 분석하여 LLM이 평가 조건을 자동 생성:

```python
user_request = "파이썬으로 이진 탐색 함수를 구현해줘"

# 자동 생성되는 조건:
"""
코드 작성 품질 기준:
1. 요구사항이 충족되었는지
2. 에러 처리가 적절한지
3. 타입 힌팅이 있는지
4. docstring/주석이 있는지
5. 코드가 간결하고 명확한지
"""
```

#### 2. 템플릿 매칭 (빠른 경로)

키워드를 감지하여 사전 정의된 템플릿 사용:

| 키워드 | 템플릿 | 평가 기준 |
|--------|--------|----------|
| "테스트" | `test` | 정상/엣지/예외 케이스, 함수명 명확성 |
| "문서화" | `document` | 설명, 설치, 사용법, 섹션 구조 |
| "리팩터링" | `refactor` | 가독성, DRY 원칙, 명명 규칙, 복잡도 |
| "버그 수정" | `bugfix` | 버그 재현, 원인 해결, 테스트 추가 |
| "코드 작성" | `code` | 요구사항, 에러 처리, 타입 힌팅, 주석 |

**장점**: LLM 호출 없이 즉시 조건 선택 → **빠르고 비용 절감**

#### 3. 범용 품질 평가

키워드 매칭이 실패해도 범용 기준으로 평가:

```
평가 기준:
1. 완성도 (40점): 요구사항 충족 여부
2. 명확성 (30점): 이해하기 쉬운지
3. 정확성 (20점): 정보가 정확한지
4. 실용성 (10점): 바로 사용 가능한지

총점 80점 이상 → passed: true
```

**장점**: 어떤 유형의 요청에도 작동 → **범용성 확보**

#### 4. 3가지 모드

| 모드 | 설명 | 사용자 입력 | 사용 사례 |
|------|------|-----------|----------|
| 🤖 **자동** | LLM이 조건 자동 추론 | 없음 | 초보자, 일반 대화 |
| 🎯 **반자동** | 간단한 목표만 입력 | "테스트 커버리지 90%" | 목표가 명확한 경우 |
| ⚙️ **수동** | 상세 조건 프롬프트 입력 | 기존 방식 | 고급 사용자, 세밀한 제어 |

---

## 사용 방법

### 기본 사용 (자동 모드)

```python
from pathlib import Path
from src.presentation.tui.services.agent_client import AgentClient
from src.presentation.tui.services.smart_feedback_loop import create_smart_feedback_loop

# 1. 에이전트 생성
project_path = Path.cwd()
agent = AgentClient(project_path=project_path, model="claude-sonnet-4.5")

# 2. 스마트 피드백 루프 생성 (기본: 자동 모드)
smart_loop = create_smart_feedback_loop(
    project_path=project_path,
    mode="auto",  # 자동 모드 (조건 자동 생성)
)

# 3. 실행 (조건 없이!)
user_request = "파이썬으로 파일을 안전하게 읽는 함수를 작성해줘"

async for chunk in smart_loop.run(
    agent=agent,
    user_request=user_request,
):
    print(chunk, end="", flush=True)
```

### 반자동 모드 (간단한 목표만 입력)

```python
smart_loop = create_smart_feedback_loop(
    project_path=project_path,
    mode="semi-auto",
    simple_goal="테스트 커버리지가 90% 이상이어야 함",  # 목표만 입력
)

user_request = "calculate_discount 함수에 대한 테스트를 작성해줘"

async for chunk in smart_loop.run(agent=agent, user_request=user_request):
    print(chunk, end="", flush=True)
```

### 수동 모드 (기존 방식)

```python
smart_loop = create_smart_feedback_loop(
    project_path=project_path,
    mode="manual",
    detailed_condition="""
코드 품질 기준:
1. try-except로 에러 처리
2. docstring 포함
3. 타입 힌팅 사용
    """,
)

async for chunk in smart_loop.run(agent=agent, user_request=user_request):
    print(chunk, end="", flush=True)
```

### 콜백 사용 (진행 상황 모니터링)

```python
def on_iteration(iteration: int, status: str):
    print(f"\n[반복 {iteration}] {status}")

def on_eval_result(eval_result):
    print(f"  점수: {eval_result.score:.2f}")
    print(f"  통과: {eval_result.passed}")
    print(f"  제안: {eval_result.suggestions}")

def on_condition_generation(chunk: str):
    # 조건 생성 과정 표시
    print(chunk, end="", flush=True)

async for chunk in smart_loop.run(
    agent=agent,
    user_request=user_request,
    on_iteration=on_iteration,
    on_eval_result=on_eval_result,
    on_condition_generation=on_condition_generation,
):
    print(chunk, end="", flush=True)
```

---

## TUI 앱 통합

### 1. `app.py` 수정

```python
# src/presentation/tui/app.py

from .services.smart_feedback_loop import create_smart_feedback_loop

class ClaudeFlowApp(App):
    def __init__(self, project_path: Path, **kwargs):
        super().__init__(**kwargs)
        # ... 기존 코드 ...

        # 스마트 피드백 루프 초기화
        self.smart_feedback_loop = create_smart_feedback_loop(
            project_path=self.project_path,
            mode="auto",  # 기본: 자동 모드
            max_iterations=3,
            quality_threshold=0.8,
        )

    async def on_message_submit(self, message: str):
        """메시지 제출 처리"""
        # 스마트 피드백 루프 활성화 여부 확인
        if self.project_settings.get("smart_feedback_enabled", False):
            # 스마트 피드백 루프 사용
            async for chunk in self.smart_feedback_loop.run(
                agent=self.agent,
                user_request=message,
                on_iteration=self._handle_iteration,
                on_eval_result=self._handle_eval_result,
                on_condition_generation=self._handle_condition_gen,
            ):
                self.chat_view.append_chunk(chunk)
        else:
            # 일반 모드
            async for chunk in self.agent.send_message(message):
                self.chat_view.append_chunk(chunk)

    def _handle_iteration(self, iteration: int, status: str):
        """반복 상황 표시"""
        self.status_bar.update_feedback_iteration(iteration, status)

    def _handle_eval_result(self, eval_result):
        """평가 결과 표시"""
        self.chat_view.append_eval_result(eval_result)

    def _handle_condition_gen(self, chunk: str):
        """조건 생성 과정 표시"""
        self.chat_view.append_chunk(chunk, style="dim")
```

### 2. 설정 모달 추가

```python
# src/presentation/tui/components/modals/settings_modal.py

class SettingsModal(ModalScreen):
    def compose(self):
        yield Container(
            # ... 기존 설정 ...

            # 스마트 피드백 루프 섹션
            Label("🔁 스마트 피드백 루프"),
            Switch(
                id="smart_feedback_enabled",
                value=self.current_settings.get("smart_feedback_enabled", False),
            ),
            Label("모드:"),
            Select(
                id="smart_feedback_mode",
                options=[
                    ("자동 (조건 자동 생성)", "auto"),
                    ("반자동 (목표만 입력)", "semi-auto"),
                    ("수동 (상세 조건)", "manual"),
                ],
                value=self.current_settings.get("smart_feedback_mode", "auto"),
            ),
            Input(
                id="simple_goal",
                placeholder="간단한 목표 입력 (반자동 모드)",
                value=self.current_settings.get("simple_goal", ""),
            ),
            # ...
        )
```

### 3. One-Click 토글 버튼

```python
# app.py

class ClaudeFlowApp(App):
    BINDINGS = [
        # ... 기존 바인딩 ...
        ("f2", "toggle_smart_feedback", "🔁 피드백 루프"),
    ]

    def action_toggle_smart_feedback(self):
        """스마트 피드백 루프 토글"""
        current = self.project_settings.get("smart_feedback_enabled", False)
        self.project_settings["smart_feedback_enabled"] = not current

        status = "활성화" if not current else "비활성화"
        self.notify(f"🔁 스마트 피드백 루프 {status}")
        self.status_bar.update_feedback_loop(not current)
```

---

## API 레퍼런스

### `SmartFeedbackConfig`

```python
@dataclass
class SmartFeedbackConfig:
    mode: Literal["auto", "semi-auto", "manual"] = "auto"
    simple_goal: str = ""  # 반자동 모드: 간단한 목표
    detailed_condition: str = ""  # 수동 모드: 상세 조건
    max_iterations: int = 3  # 최대 반복 횟수
    quality_threshold: float = 0.8  # 품질 임계값 (0.0 ~ 1.0)
```

### `SmartFeedbackLoop`

```python
class SmartFeedbackLoop:
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
    ) -> AsyncIterator[str]:
        """스마트 피드백 루프 실행"""

    def get_best_result(self) -> Optional[IterationHistory]:
        """가장 높은 점수의 결과 반환"""

    def reset(self):
        """상태 리셋"""
```

### `AutoConditionGenerator`

```python
class AutoConditionGenerator:
    def extract_keywords(self, user_request: str) -> list[str]:
        """요청에서 키워드 추출 (test, document, refactor 등)"""

    def get_template_condition(self, user_request: str) -> str:
        """템플릿 기반 조건 생성 (빠른 경로)"""

    async def generate_condition(
        self,
        user_request: str,
        on_generation_output: Optional[Callable[[str], None]] = None,
    ) -> str:
        """LLM을 사용한 조건 자동 생성 (느린 경로)"""
```

### 편의 함수

```python
def create_smart_feedback_loop(
    project_path: Path,
    mode: Literal["auto", "semi-auto", "manual"] = "auto",
    simple_goal: str = "",
    detailed_condition: str = "",
    max_iterations: int = 3,
    quality_threshold: float = 0.8,
) -> SmartFeedbackLoop:
    """스마트 피드백 루프 생성 헬퍼"""
```

---

## 예시

### 예시 1: 자동 모드 (조건 없음)

```python
smart_loop = create_smart_feedback_loop(project_path=Path.cwd(), mode="auto")
user_request = "파이썬으로 이진 탐색 함수를 구현해줘"

async for chunk in smart_loop.run(agent=agent, user_request=user_request):
    print(chunk, end="")
```

**동작**:
1. 키워드 "이진 탐색" 감지 → "code" 템플릿 매칭
2. 조건 자동 생성: "코드 작성 품질 기준 (에러 처리, 타입 힌팅 등)"
3. 최대 3회 반복, 80점 이상이면 조기 종료

### 예시 2: 템플릿 매칭 (빠른 경로)

```python
user_request = "이 코드를 리팩터링해줘"
# → "refactor" 템플릿 자동 선택 (LLM 호출 없음!)
# → 평가 기준: 가독성, DRY 원칙, 명명 규칙, 복잡도
```

### 예시 3: 범용 품질 평가

```python
user_request = "사용자 인증 시스템을 설계해줘"
# → 키워드 매칭 실패
# → 범용 품질 평가 사용 (완성도/명확성/정확성/실용성)
```

### 예시 4: 반자동 모드

```python
smart_loop = create_smart_feedback_loop(
    project_path=Path.cwd(),
    mode="semi-auto",
    simple_goal="테스트 커버리지가 90% 이상",
)
user_request = "테스트를 작성해줘"
# → 목표 기반 조건 생성: "테스트 커버리지가 90% 이상인지 확인"
```

---

## 성능 최적화

### 템플릿 매칭 우선 (빠른 경로)

```python
# 1. 키워드 매칭 시도 (즉시)
keywords = extract_keywords(user_request)
if keywords:
    condition = CONDITION_TEMPLATES[keywords[0]]
    # → LLM 호출 없음!

# 2. 키워드 매칭 실패 → 범용 기준 사용 (빠름)
if not keywords:
    condition = UNIVERSAL_QUALITY_CRITERIA
    # → LLM 호출 없음!

# 3. 범용 기준도 부적절한 경우에만 LLM 호출 (느림)
if need_custom_condition:
    condition = await llm.generate_condition(user_request)
```

**결과**:
- 대부분의 경우 LLM 호출 없이 즉시 조건 선택 → **빠르고 비용 절감**

---

## 마이그레이션 가이드

### 기존 코드 → 스마트 피드백 루프

**Before (기존)**:

```python
from .services.feedback_loop_improved import ImprovedFeedbackLoop

feedback_loop = ImprovedFeedbackLoop(...)
condition_prompt = """사용자가 수동으로 작성"""  # ← 번거로움!

async for chunk in feedback_loop.run_with_feedback(
    agent=agent,
    initial_message=user_request,
    condition_prompt=condition_prompt,
):
    print(chunk)
```

**After (스마트)**:

```python
from .services.smart_feedback_loop import create_smart_feedback_loop

smart_loop = create_smart_feedback_loop(project_path=Path.cwd(), mode="auto")

async for chunk in smart_loop.run(agent=agent, user_request=user_request):
    print(chunk)  # 조건 자동 생성!
```

---

## FAQ

### Q1: 기존 `ImprovedFeedbackLoop`는 제거되나요?

**A**: 아니요. 스마트 피드백 루프는 **내부적으로** `ImprovedFeedbackLoop`를 사용합니다. 고급 사용자는 여전히 `ImprovedFeedbackLoop`를 직접 사용할 수 있습니다.

### Q2: 조건 생성이 느리지 않나요?

**A**: 템플릿 매칭을 우선 사용하므로 대부분의 경우 **LLM 호출 없이** 즉시 조건 선택됩니다. 키워드 매칭 실패 시에만 범용 기준 사용 또는 LLM 호출합니다.

### Q3: 모든 유형의 요청에 작동하나요?

**A**: 예. 범용 품질 평가 기준(완성도/명확성/정확성/실용성)으로 모든 유형의 요청을 처리할 수 있습니다.

### Q4: 토큰 비용이 늘어나지 않나요?

**A**: 템플릿 매칭 사용 시 조건 생성에 LLM 호출이 없으므로 비용이 동일합니다. LLM 조건 생성이 필요한 경우에만 약간의 추가 비용(haiku 모델)이 발생합니다.

---

## 참고 자료

- **구현 파일**: `src/presentation/tui/services/smart_feedback_loop.py`
- **예시 파일**: `examples/smart_feedback_loop_examples.py`
- **기존 피드백 루프**: `src/presentation/tui/services/feedback_loop_improved.py`

---

## 변경 이력

- **2025-11-07**: 초안 작성 (자동 조건 생성, 템플릿 매칭, 범용 평가)
