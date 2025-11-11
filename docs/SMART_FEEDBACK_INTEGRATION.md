# 스마트 피드백 루프 통합 가이드

> TUI 앱에 스마트 피드백 루프가 성공적으로 통합되었습니다!

## 📋 통합 완료 내역

### 1. 핵심 모듈 추가 ✅

- ✅ `src/presentation/tui/services/smart_feedback_loop.py`: 스마트 피드백 루프 구현
- ✅ `src/presentation/tui/services/response_strategy.py`: `SmartFeedbackLoopResponseStrategy` 추가
- ✅ `src/presentation/tui/services/response_handler.py`: `SmartFeedbackLoopCallbackHandler` 추가

### 2. app.py 통합 ✅

- ✅ Import 추가
- ✅ `__init__`에 `self.smart_feedback_loop` 추가
- ✅ `create_new_session`에 스마트 피드백 루프 초기화
- ✅ `_select_response_strategy`에 우선순위 추가 (스마트 > 기존 > 일반)
- ✅ `_create_response_handler`에 SmartFeedbackLoopCallbackHandler 추가

---

## 🚀 사용 방법

### 설정 활성화

설정 파일(`~/.claude-flow/config.json`)에 다음 설정 추가:

```json
{
  "feedback_loop_defaults": {
    "enabled": false
  },
  "smart_feedback_defaults": {
    "enabled": true,
    "mode": "auto",
    "max_iterations": 3,
    "quality_threshold": 0.8
  }
}
```

또는 프로젝트별 설정(`~/.claude-flow/{project}/settings.json`):

```json
{
  "smart_feedback_enabled": true,
  "smart_feedback_mode": "auto",
  "smart_feedback_max_iterations": 3,
  "smart_feedback_quality_threshold": 0.8,
  "smart_feedback_simple_goal": "",
  "smart_feedback_detailed_condition": ""
}
```

### 모드 선택

| 설정 키 | 값 | 설명 |
|---------|---|------|
| `smart_feedback_mode` | `"auto"` | 조건 자동 생성 (기본, 권장) |
| `smart_feedback_mode` | `"semi-auto"` | 간단한 목표만 입력 |
| `smart_feedback_mode` | `"manual"` | 상세 조건 프롬프트 입력 |

---

## 🎯 통합 우선순위

```
스마트 피드백 루프 (우선순위 1)
        ↓
기존 피드백 루프 (우선순위 2)
        ↓
일반 응답 (우선순위 3)
```

**동작**:
1. `smart_feedback_enabled: true` → **스마트 피드백 루프 사용** (조건 자동 생성!)
2. `smart_feedback_enabled: false` + `feedback_loop_enabled: true` → 기존 피드백 루프 (조건 수동 입력 필요)
3. 둘 다 비활성화 → 일반 응답

---

## 📊 실행 예시

### 예시 1: 자동 모드 (기본)

**설정**:
```json
{
  "smart_feedback_enabled": true,
  "smart_feedback_mode": "auto"
}
```

**사용자 입력**:
```
파이썬으로 파일을 안전하게 읽는 함수를 작성해줘
```

**동작**:
1. 🧠 조건 자동 생성 중...
   - "코드 작성 품질 기준: 에러 처리, 타입 힌팅, docstring, 간결성"
2. 🔄 반복 1: 시작 → 코드 작성
3. 🔍 조건 평가 중...
4. 🟢 품질 점수: 0.85 / 1.0
5. ✅ 조건 충족 → 완료!

### 예시 2: 반자동 모드

**설정**:
```json
{
  "smart_feedback_enabled": true,
  "smart_feedback_mode": "semi-auto",
  "smart_feedback_simple_goal": "테스트 커버리지가 90% 이상"
}
```

**사용자 입력**:
```
calculate_discount 함수에 대한 테스트를 작성해줘
```

**동작**:
1. 목표 기반 조건: "테스트 커버리지가 90% 이상인지 확인"
2. 반복 실행 → 평가 → 필요 시 재시도

---

## 🔧 설정 모달 UI (추가 필요)

> **TODO**: `settings_modal.py`에 다음 UI 추가

```python
# 스마트 피드백 루프 섹션
Label("✨ 스마트 피드백 루프 (조건 자동 생성)", classes="settings-section-label"),
Switch(
    id="smart_feedback_enabled",
    value=settings.get("smart_feedback_enabled", False),
),
Label("모드:"),
Select(
    id="smart_feedback_mode",
    options=[
        ("자동 (조건 자동 생성) - 권장", "auto"),
        ("반자동 (간단한 목표만)", "semi-auto"),
        ("수동 (상세 조건)", "manual"),
    ],
    value=settings.get("smart_feedback_mode", "auto"),
),
Input(
    id="smart_feedback_simple_goal",
    placeholder="간단한 목표 (반자동 모드)",
    value=settings.get("smart_feedback_simple_goal", ""),
),
TextArea(
    id="smart_feedback_detailed_condition",
    placeholder="상세 조건 프롬프트 (수동 모드)",
),
```

---

## 📝 추가 작업 (Optional)

### 1. One-Click 토글 단축키 추가

`app.py`의 `BINDINGS`에 추가:

```python
BINDINGS = [
    # ... 기존 바인딩 ...
    ("f2", "toggle_smart_feedback", "✨ 스마트 피드백"),
]

def action_toggle_smart_feedback(self):
    """스마트 피드백 루프 토글"""
    current = self.project_settings.get("smart_feedback_enabled", False)
    self.project_settings["smart_feedback_enabled"] = not current

    # 재초기화
    if not current:
        self.smart_feedback_loop = create_smart_feedback_loop(
            project_path=self.project_path,
            mode=self.project_settings.get("smart_feedback_mode", "auto"),
        )
    else:
        self.smart_feedback_loop = None

    status = "활성화" if not current else "비활성화"
    self.notify(f"✨ 스마트 피드백 루프 {status}")
```

### 2. 상태바 표시 추가

`status_bar.py`에 스마트 피드백 루프 상태 표시:

```python
def update_smart_feedback(self, enabled: bool, mode: str):
    """스마트 피드백 루프 상태 업데이트"""
    if enabled:
        mode_emoji = {"auto": "🤖", "semi-auto": "🎯", "manual": "⚙️"}
        self.feedback_status = f"{mode_emoji[mode]} Smart"
    else:
        self.feedback_status = ""
```

---

## 🎓 개발자 가이드

### 아키텍처

```
사용자 메시지 입력
        ↓
app.on_input_box_submitted()
        ↓
_select_response_strategy()
        ↓
┌────────────────────────────────────────┐
│ SmartFeedbackLoopResponseStrategy?     │
└────────────────────────────────────────┘
        ↓ YES
SmartFeedbackLoop.run()
        ↓
1. 조건 자동 생성 (AutoConditionGenerator)
   - 템플릿 매칭 (빠른 경로)
   - LLM 생성 (느린 경로)
        ↓
2. ImprovedFeedbackLoop.run_with_feedback()
   - 반복 실행
   - 조건 평가
   - 필요 시 재시도
        ↓
SmartFeedbackLoopCallbackHandler
   - on_condition_generation()
   - on_iteration()
   - on_eval_start()
   - on_eval_result()
        ↓
ChatView에 결과 표시
```

### 핵심 클래스

| 클래스 | 역할 | 위치 |
|--------|------|------|
| `SmartFeedbackLoop` | 스마트 피드백 루프 엔진 | `smart_feedback_loop.py` |
| `AutoConditionGenerator` | 조건 자동 생성 | `smart_feedback_loop.py` |
| `SmartFeedbackLoopResponseStrategy` | 응답 전략 | `response_strategy.py` |
| `SmartFeedbackLoopCallbackHandler` | UI 콜백 핸들러 | `response_handler.py` |

---

## 🐛 문제 해결

### Q1: 스마트 피드백 루프가 활성화되지 않음

**A**: 설정 확인:
```python
# app.py에서 디버깅
if self.smart_feedback_loop is not None:
    print("✅ 스마트 피드백 루프 활성화")
else:
    print("❌ 스마트 피드백 루프 비활성화")
    print(f"설정: {self.project_settings.get('smart_feedback_enabled')}")
```

### Q2: 조건 생성이 표시되지 않음

**A**: `SmartFeedbackLoopCallbackHandler.on_condition_generation` 콜백 확인:
```python
def on_condition_generation(self, chunk: str) -> None:
    print(f"[디버그] 조건 생성: {chunk}")
    # ... 기존 코드 ...
```

### Q3: 기존 피드백 루프와 충돌

**A**: 우선순위 확인 (`_select_response_strategy`):
- 스마트 피드백 루프 (우선순위 1)
- 기존 피드백 루프 (우선순위 2)
- 스마트가 활성화되면 기존 피드백 루프는 무시됨

---

## 📚 참고 문서

- **스마트 피드백 루프 가이드**: `docs/SMART_FEEDBACK_LOOP.md`
- **사용 예시**: `examples/smart_feedback_loop_examples.py`
- **구현 파일**: `src/presentation/tui/services/smart_feedback_loop.py`

---

## ✅ 체크리스트

### 통합 완료 ✅
- [x] `smart_feedback_loop.py` 구현
- [x] `ResponseStrategy` 추가
- [x] `ResponseHandler` 추가
- [x] `app.py` 통합
- [x] 우선순위 설정
- [x] 예시 및 문서 작성

### 추가 작업 (Optional) ⏸️
- [ ] `settings_modal.py` UI 추가
- [ ] `config/settings.py` 기본값 추가
- [ ] One-Click 토글 단축키 (F2)
- [ ] 상태바 표시
- [ ] 테스트 작성

---

## 🎉 완료!

스마트 피드백 루프가 성공적으로 통합되었습니다!

**다음 단계**:
1. 설정 파일에 `smart_feedback_enabled: true` 추가
2. TUI 앱 실행
3. 일반 메시지 입력 (예: "파이썬 함수를 작성해줘")
4. 조건이 자동 생성되고 피드백 루프가 실행되는 것을 확인!

**테스트 명령어**:
```bash
python -m src.presentation.tui.cli
```

---

## 변경 이력

- **2025-11-07**: 초안 작성 (스마트 피드백 루프 통합 완료)
