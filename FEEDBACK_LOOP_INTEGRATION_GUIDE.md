# 🔄 개선된 피드백 루프 통합 가이드

## 변경 사항 요약

### 1. 평가 정확도 개선 ⭐⭐⭐
- **구조화된 평가**: JSON 응답으로 파싱 정확도 향상
- **품질 점수**: 0.0 ~ 1.0 스케일로 정량 평가
- **개선 제안**: LLM이 구체적인 개선 방안 제시

### 2. 컨텍스트 누적 ⭐⭐⭐
- **이력 관리**: 모든 시도 기록 저장
- **누적 학습**: 이전 평가 결과를 다음 평가에 전달
- **개선도 측정**: 반복마다 품질 향상도 추적

### 3. 조기 종료 메커니즘 ⭐⭐
- **품질 임계값**: 설정한 점수 도달 시 자동 종료
- **정체 감지**: 개선도가 5% 미만이면 조기 종료
- **최적 결과 선택**: 여러 시도 중 가장 좋은 결과 반환

---

## 통합 방법

### Step 1: 기존 FeedbackLoop 교체

**파일**: `src/presentation/tui/app.py`

```python
# 변경 전
from .services.feedback_loop import FeedbackLoop

# 변경 후
from .services.feedback_loop_improved import ImprovedFeedbackLoop, EvaluationResult
```

### Step 2: 초기화 시 quality_threshold 설정

```python
# app.py의 __init__ 또는 설정 로드 부분
self.feedback_loop = ImprovedFeedbackLoop(
    project_path=self.project_path,
    condition_model=self.config.get("feedback_loop.condition_model", "claude-haiku-4-5-20251001"),
    max_iterations=self.config.get("feedback_loop.max_iterations", 3),
    quality_threshold=0.8,  # 새로운 옵션: 80점 이상이면 조기 종료
)
```

### Step 3: 평가 결과 콜백 수정

**파일**: `src/presentation/tui/services/response_handler.py` (또는 관련 핸들러)

```python
# 변경 전 (bool, str)
def on_eval_result(self, condition_met: bool, eval_response: str):
    if condition_met:
        self.chat_view.append_message("system", "✅ 조건 충족")
    else:
        self.chat_view.append_message("system", "❌ 조건 미충족")
    self.chat_view.append_message("system", eval_response)

# 변경 후 (EvaluationResult)
def on_eval_result(self, eval_result: EvaluationResult):
    # 품질 점수 표시
    score_emoji = "🟢" if eval_result.score >= 0.8 else "🟡" if eval_result.score >= 0.5 else "🔴"

    self.chat_view.append_message(
        "system",
        f"{score_emoji} 품질 점수: {eval_result.score:.2f} / 1.0"
    )

    # 평가 이유
    self.chat_view.append_message("system", f"평가: {eval_result.reasoning}")

    # 개선 제안 (조건 미충족 시)
    if not eval_result.passed and eval_result.suggestions:
        suggestions = "\n".join(f"  • {s}" for s in eval_result.suggestions)
        self.chat_view.append_message("system", f"개선 제안:\n{suggestions}")
```

### Step 4: 설정 UI 업데이트

**파일**: `src/presentation/tui/components/modals/settings_modal.py`

```python
# 피드백 루프 설정 섹션에 추가
class SettingsModal(ModalScreen):
    def compose(self) -> ComposeResult:
        # ... 기존 설정들 ...

        # 새로운 설정 추가
        yield Label("품질 임계값 (조기 종료)")
        yield Input(
            value=str(self.config.get("feedback_loop.quality_threshold", 0.8)),
            id="quality_threshold",
            placeholder="0.0 ~ 1.0 (예: 0.8)"
        )
        yield Static("점수가 이 값 이상이면 자동으로 루프를 종료합니다.")
```

### Step 5: 세션 파일 구조 업데이트

**파일**: `~/.claude-flow/{project-name}/sessions/{session-id}.json`

```json
{
  "feedback_loop": {
    "enabled": true,
    "condition_prompt": "출력에 에러가 있는지 확인",
    "condition_model": "claude-haiku-4-5-20251001",
    "max_iterations": 3,
    "quality_threshold": 0.8,
    "current_iteration": 0,
    "history": [
      {
        "iteration": 1,
        "output": "...",
        "evaluation": {
          "passed": false,
          "score": 0.6,
          "reasoning": "일부 개선 필요",
          "suggestions": ["에러 처리 추가", "테스트 작성"]
        },
        "timestamp": "2025-01-01T00:00:00Z"
      }
    ]
  }
}
```

---

## 사용 예시

### 예시 1: 코드 품질 검증

```python
# 사용자 입력
"파일 읽기 기능을 구현해줘"

# 피드백 루프 조건
condition_prompt = """
1. 에러 처리가 적절히 구현되어 있는지
2. 파일이 존재하지 않는 경우를 처리하는지
3. 코드에 주석이 있는지
"""

# 실행 결과
# 시도 1: 점수 0.5 → 재시도
# 시도 2: 점수 0.85 → 조기 종료 (임계값 0.8 초과)
```

### 예시 2: 문서 완성도 평가

```python
# 사용자 입력
"README 파일을 작성해줘"

# 피드백 루프 조건
condition_prompt = """
1. 프로젝트 설명이 명확한지
2. 설치 방법이 포함되어 있는지
3. 사용 예시가 있는지
4. 라이선스 정보가 있는지
"""

# 실행 결과
# 시도 1: 점수 0.4 → 제안: "설치 방법 추가"
# 시도 2: 점수 0.6 → 제안: "라이선스 정보 추가"
# 시도 3: 점수 0.9 → 완료
```

---

## 성능 최적화 팁

### 1. 평가 모델 선택
- **빠른 평가**: `claude-haiku-4-5-20251001` (기본값)
- **정확한 평가**: `claude-sonnet-4-5-20250929`

### 2. 출력 길이 제한
```python
# 평가 시 출력을 잘라서 전달 (토큰 절약)
output_preview = output[:2000]  # 처음 2000자만
```

### 3. 캐싱 활용
```python
# 동일한 조건 프롬프트를 여러 번 사용하는 경우
# Prompt Caching 활성화 (SDK가 지원하면)
```

### 4. 병렬 평가 (향후)
```python
# 여러 조건을 병렬로 평가
conditions = ["에러 처리", "테스트", "문서화"]
results = await asyncio.gather(*[
    evaluate_condition(output, cond) for cond in conditions
])
```

---

## 디버깅 가이드

### 평가 파싱 실패 시

**증상**: `(파싱 실패)` 메시지 표시

**해결 방법**:
1. `eval_result.raw_response` 확인
2. LLM이 JSON 외에 다른 텍스트를 출력했는지 확인
3. 필요 시 평가 프롬프트 수정

### 개선도가 정체될 때

**증상**: 점수가 계속 비슷한 값 (예: 0.55 → 0.56 → 0.57)

**해결 방법**:
1. `feedback_input`을 더 구체적으로 작성
2. `condition_prompt`를 명확하게 수정
3. 최대 반복 횟수 증가

### 평가가 너무 엄격할 때

**증상**: 점수가 항상 낮음 (< 0.5)

**해결 방법**:
1. `quality_threshold` 낮추기 (예: 0.7)
2. `condition_prompt`를 더 관대하게 수정
3. 평가 모델 변경 (Haiku → Sonnet)

---

## 추가 개선 아이디어

### 1. 다중 조건 평가 (AND/OR)
```python
conditions = [
    {"type": "and", "prompts": ["에러 처리", "테스트"]},
    {"type": "or", "prompts": ["주석", "문서"]}
]
```

### 2. 사용자 피드백 통합
```python
# 사용자가 평가에 개입
if eval_result.score < 0.5:
    user_feedback = await ask_user("개선이 필요한 부분이 있나요?")
    current_message += f"\n사용자 피드백: {user_feedback}"
```

### 3. 평가 히스토리 시각화
```python
# 점수 추이 그래프
scores = [h.evaluation.score for h in self.history]
# 0.5 → 0.7 → 0.85 (개선 추세 표시)
```

### 4. 자동 조건 생성
```python
# 사용자 요청에서 자동으로 평가 조건 생성
user_message = "파일 읽기 기능을 구현해줘"
auto_conditions = generate_conditions(user_message)
# → ["에러 처리", "파일 존재 확인", "테스트"]
```

---

## 마이그레이션 체크리스트

- [ ] `feedback_loop_improved.py` 추가
- [ ] `app.py`에서 import 변경
- [ ] `response_handler.py` 콜백 수정
- [ ] `settings_modal.py`에 quality_threshold 추가
- [ ] 세션 파일 구조 업데이트 (하위 호환)
- [ ] 기존 세션 파일 마이그레이션 스크립트 작성
- [ ] 테스트 실행 및 검증
- [ ] 문서 업데이트 (TUI_기능명세서.md)

---

## 참고 자료

- **기존 구현**: `src/presentation/tui/services/feedback_loop.py`
- **개선 구현**: `src/presentation/tui/services/feedback_loop_improved.py`
- **데이터 플로우**: `docs/data-flow.md` (참고용)
- **TUI 기능명세서**: `docs/TUI_기능명세서.md`
