# 스마트 피드백 루프 빠른 시작 가이드

> 5분 안에 스마트 피드백 루프를 설정하고 사용하는 방법

## 📋 필수 조건

- TUI 앱이 설치되어 있어야 함
- Python 3.10 이상

---

## ⚡ 빠른 설정 (3단계)

### 1단계: 설정 파일 생성

**프로젝트별 설정** (권장):

```bash
# 프로젝트명 확인
# TUI 실행 시 표시되는 프로젝트명을 사용하세요
# 예: "claude-flow-web" → ~/.claude-flow/claude-flow-web/settings.json

# 설정 파일 생성
mkdir -p ~/.claude-flow/claude-flow-web
cat > ~/.claude-flow/claude-flow-web/settings.json << 'EOF'
{
  "smart_feedback_enabled": true,
  "smart_feedback_mode": "auto",
  "smart_feedback_max_iterations": 3,
  "smart_feedback_quality_threshold": 0.8
}
EOF
```

**또는 전역 기본값 설정**:

```bash
# 전역 설정 파일 수정
cat > ~/.claude-flow/config.json << 'EOF'
{
  "theme": "dark",
  "display": {
    "show_statusbar": true,
    "show_timestamps": true,
    "show_token_counts": true,
    "sidebar_visible": false,
    "enable_thinking": true,
    "show_thinking_full": false
  },
  "default_model": "claude-sonnet-4.5",
  "feedback_loop_defaults": {
    "enabled": false,
    "max_iterations": 3,
    "condition_model": "claude-haiku-4-5-20251001",
    "quality_threshold": 0.8
  },
  "logging": {
    "auto_save": true,
    "log_level": "INFO",
    "max_file_size_mb": 10,
    "retention_days": 30
  },
  "shortcuts": {
    "new_session": "ctrl+n",
    "open_session": "ctrl+o",
    "change_directory": "ctrl+d",
    "project_info": "ctrl+i",
    "clear_screen": "ctrl+l"
  }
}
EOF
```

### 2단계: TUI 실행

```bash
python -m src.presentation.tui.cli
```

### 3단계: 메시지 입력하고 확인

```
파이썬으로 파일을 안전하게 읽는 함수를 작성해줘
```

**기대 결과**:

```
✨ 스마트 피드백 루프 활성화 (자동 모드, 최대 3회)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🧠 조건 자동 생성 중...

[템플릿 매칭] "code" 템플릿 선택

📋 생성된 평가 조건:
코드 작성 품질 기준:
1. 요구사항이 충족되었는지
2. 에러 처리가 적절한지
3. 타입 힌팅이 있는지
4. docstring/주석이 있는지
5. 코드가 간결하고 명확한지

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔄 반복 1: 시작
...
```

---

## 🎨 설정 옵션

### 기본 설정 (자동 모드)

```json
{
  "smart_feedback_enabled": true,
  "smart_feedback_mode": "auto",
  "smart_feedback_max_iterations": 3,
  "smart_feedback_quality_threshold": 0.8
}
```

**동작**:
- 조건 자동 생성 (템플릿 매칭 또는 LLM 생성)
- 최대 3회 반복
- 품질 80점 이상이면 조기 종료

### 반자동 모드 (목표만 입력)

```json
{
  "smart_feedback_enabled": true,
  "smart_feedback_mode": "semi-auto",
  "smart_feedback_simple_goal": "테스트 커버리지가 90% 이상",
  "smart_feedback_max_iterations": 3,
  "smart_feedback_quality_threshold": 0.85
}
```

**동작**:
- 간단한 목표를 조건으로 확장
- 목표: "테스트 커버리지가 90% 이상인지 확인"

### 수동 모드 (상세 조건)

```json
{
  "smart_feedback_enabled": true,
  "smart_feedback_mode": "manual",
  "smart_feedback_detailed_condition": "코드가 PEP 8을 준수하고, 타입 힌팅이 있으며, docstring이 명확한지 확인",
  "smart_feedback_max_iterations": 5,
  "smart_feedback_quality_threshold": 0.9
}
```

**동작**:
- 사용자 정의 상세 조건 사용
- 기존 피드백 루프와 유사하지만 자동 평가 지원

---

## 🔧 고급 설정

### 품질 임계값 조정

```json
{
  "smart_feedback_quality_threshold": 0.7  // 70점 이상 (관대)
}
```

**권장값**:
- **0.7**: 관대한 평가 (빠른 완료)
- **0.8**: 기본값 (균형)
- **0.9**: 엄격한 평가 (높은 품질)

### 최대 반복 횟수

```json
{
  "smart_feedback_max_iterations": 5  // 최대 5회 반복
}
```

**권장값**:
- **3회**: 기본값 (적당)
- **5회**: 복잡한 작업 (품질 중시)
- **1회**: 빠른 작업 (피드백 루프 비활성화와 유사)

---

## 📊 동작 예시

### 예시 1: 코드 작성 (자동 모드)

**입력**:
```
파이썬으로 이진 탐색 함수를 작성해줘
```

**동작**:
1. 키워드 "이진 탐색" 감지
2. "code" 템플릿 매칭 (즉시)
3. 평가 조건: "에러 처리, 타입 힌팅, docstring, 간결성"
4. 반복 1: 코드 작성 → 평가 (점수 0.85) → ✅ 통과

### 예시 2: 테스트 작성 (반자동 모드)

**설정**:
```json
{
  "smart_feedback_mode": "semi-auto",
  "smart_feedback_simple_goal": "엣지 케이스 커버리지 100%"
}
```

**입력**:
```
calculate_discount 함수에 대한 테스트를 작성해줘
```

**동작**:
1. 목표 기반 조건: "엣지 케이스 커버리지 100%인지 확인"
2. 반복 1: 테스트 작성 → 평가 (점수 0.65) → ❌ 미흡
3. 개선 제안: "경계값 테스트 추가, 예외 처리 테스트 필요"
4. 반복 2: 테스트 보완 → 평가 (점수 0.90) → ✅ 통과

---

## 🐛 문제 해결

### Q1: 스마트 피드백 루프가 활성화되지 않음

**원인**: 설정 파일이 로드되지 않음

**해결**:
```bash
# 설정 파일 경로 확인
ls -la ~/.claude-flow/claude-flow-web/settings.json

# 파일 내용 확인
cat ~/.claude-flow/claude-flow-web/settings.json

# 프로젝트명 확인 (TUI 실행 시 표시)
# "프로젝트: {프로젝트명}" 메시지 확인
```

### Q2: 조건 생성이 표시되지 않음

**원인**: `on_condition_generation` 콜백이 호출되지 않음

**해결**:
```bash
# 로그 확인
tail -f ~/.claude-flow/{프로젝트명}/logs/session_*.log

# 디버그 모드 활성화 (config.json)
{
  "logging": {
    "log_level": "DEBUG"
  }
}
```

### Q3: 평가가 너무 엄격함

**원인**: `quality_threshold`가 너무 높음

**해결**:
```json
{
  "smart_feedback_quality_threshold": 0.7  // 0.8 → 0.7로 낮춤
}
```

### Q4: 반복이 너무 많음

**원인**: `max_iterations`가 너무 높거나, 조건이 달성 불가능

**해결**:
```json
{
  "smart_feedback_max_iterations": 2,  // 3 → 2로 감소
  "smart_feedback_quality_threshold": 0.75  // 임계값도 낮춤
}
```

---

## 🎯 모드 선택 가이드

| 사용 사례 | 권장 모드 | 설정 |
|-----------|----------|------|
| **일반 코딩** | 자동 | `"mode": "auto"` |
| **특정 목표 있음** | 반자동 | `"mode": "semi-auto"` + `simple_goal` |
| **엄격한 품질 기준** | 수동 | `"mode": "manual"` + `detailed_condition` |
| **빠른 프로토타입** | 자동 (낮은 임계값) | `"mode": "auto"` + `"quality_threshold": 0.7` |
| **프로덕션 코드** | 수동 (높은 임계값) | `"mode": "manual"` + `"quality_threshold": 0.9` |

---

## 📚 다음 단계

1. ✅ 기본 설정으로 시작
2. 🎨 필요에 따라 모드 변경
3. 🔧 품질 임계값 조정
4. 📖 [상세 가이드](SMART_FEEDBACK_LOOP.md) 읽기

---

## 💡 팁

### 팁 1: 템플릿 매칭 활용

키워드를 명확히 사용하면 템플릿 매칭으로 **빠르게** 조건 생성:
- "테스트 작성해줘" → `test` 템플릿
- "문서화해줘" → `document` 템플릿
- "리팩터링해줘" → `refactor` 템플릿
- "버그 수정해줘" → `bugfix` 템플릿

### 팁 2: 조기 종료 활용

품질 임계값을 적절히 설정하면 불필요한 반복 방지:
```json
{
  "smart_feedback_quality_threshold": 0.8  // 80점 도달 시 즉시 종료
}
```

### 팁 3: 로그 활용

실행 과정을 로그로 확인:
```bash
tail -f ~/.claude-flow/{프로젝트명}/logs/session_*.log
```

---

## 🎉 완료!

이제 스마트 피드백 루프를 사용할 준비가 되었습니다!

**테스트 명령어**:
```bash
python -m src.presentation.tui.cli
```

**첫 메시지**:
```
파이썬으로 파일 읽기 함수를 작성해줘
```

---

## 변경 이력

- **2025-11-07**: 초안 작성 (빠른 시작 가이드)
