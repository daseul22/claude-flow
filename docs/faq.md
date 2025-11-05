# FAQ - Frequently Asked Questions

Claude Flow 사용 중 자주 묻는 질문과 답변입니다.

---

## 📚 관련 문서

- **[문서 INDEX](INDEX.md)** - 모든 문서의 전체 목록
- **[프로젝트 README](../README.md)** - 프로젝트 개요 및 빠른 시작
- **[설치 가이드](installation.md)** - 설치 및 환경 설정
- **[튜토리얼](tutorial.md)** - 첫 번째 워크플로우 작성
- **[프로젝트 문서](../CLAUDE.md)** - 상세 가이드

---

## 목차

- [설치 및 환경 설정](#설치-및-환경-설정)
- [기본 개념](#기본-개념)
- [워크플로우 설계](#워크플로우-설계)
- [워크플로우 실행](#워크플로우-실행)
- [Worker 에이전트](#worker-에이전트)
- [트러블슈팅](#트러블슈팅)
- [성능 최적화](#성능-최적화)
- [고급 기능](#고급-기능)

---

## 설치 및 환경 설정

### Q1: Python 버전 요구사항은 무엇인가요?

**A**: Claude Flow는 **Python 3.10 이상**을 요구합니다.

```bash
# 버전 확인
python3 --version  # 3.10.0 이상이어야 함

# Python 설치 방법
# macOS
brew install python@3.11

# Ubuntu/Debian
sudo apt install python3.11

# Windows
# https://www.python.org/downloads/ 에서 다운로드
```

---

### Q2: 설치 후 "claude-flow-web 명령어를 찾을 수 없습니다" 에러가 발생합니다

**A**: 셸 설정을 다시 로드해야 합니다.

```bash
# zsh 사용자 (macOS 기본)
source ~/.zshrc

# bash 사용자
source ~/.bashrc

# 또는 새 터미널 탭 열기
```

**여전히 안 되면**:

```bash
# pipx 설치 경로 확인
pipx list | grep claude-flow

# 직접 실행
python -m src.presentation.web.app
```

---

### Q3: 여러 Python 버전이 설치되어 있습니다. 특정 버전을 사용할 수 있나요?

**A**: 네, pipx에 Python 버전을 지정할 수 있습니다.

```bash
# Python 3.11로 설치
pipx install --python /usr/bin/python3.11 .

# 또는 개발 모드로 설치
pipx install --python /usr/bin/python3.11 -e .

# 설치된 경로 확인
which python3.11
```

---

### Q4: CLAUDE_CODE_OAUTH_TOKEN은 어디서 발급받나요?

**A**: Claude Code 설정에서 발급받을 수 있습니다.

1. [Claude Code](https://claude.ai/code) 접속
2. 우측 상단 **프로필 아이콘** 클릭
3. **Settings** 선택
4. **OAuth Tokens** 섹션
5. **Generate Token** 클릭
6. 토큰 복사

```bash
# 토큰 설정 방법 (3가지)

# 1. 임시 설정 (현재 세션만)
export CLAUDE_CODE_OAUTH_TOKEN='sk-proj-xxx...'

# 2. .env 파일에 설정 (권장)
echo "CLAUDE_CODE_OAUTH_TOKEN=sk-proj-xxx..." > .env

# 3. 영구 설정 (모든 세션)
echo "export CLAUDE_CODE_OAUTH_TOKEN='sk-proj-xxx...'" >> ~/.zshrc
source ~/.zshrc
```

---

### Q5: Node.js 없이 Claude Flow를 사용할 수 있나요?

**A**: 부분적으로 가능합니다.

```bash
# Node.js가 없으면:
# - CLI로 사용: 가능 ✓ (python -m src.presentation.web.app)
# - 웹 UI 사용: 불가능 ✗ (빌드 필요)

# Node.js 설치
# macOS
brew install node

# Ubuntu
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install nodejs

# Windows
# https://nodejs.org/ 에서 다운로드
```

---

## 기본 개념

### Q6: "워크플로우"란 무엇인가요?

**A**: 워크플로우는 AI 에이전트들을 연결하여 자동으로 작업을 처리하는 파이프라인입니다.

```
예시: 코드 리뷰 워크플로우

[사용자 입력] → [코드 분석] → [리뷰] → [리포트 생성] → [결과]
     (Input)   (Worker)   (Worker)   (Worker)      (Output)
```

**특징**:
- 비주얼 편집 (드래그 앤 드롭)
- 조건 분기 (if-else)
- 병렬 실행
- 세션 재활용 (컨텍스트 유지)
- 실시간 모니터링

---

### Q7: "Worker 에이전트"와 "노드"의 차이는 무엇인가요?

**A**: 워크플로우 관점에서의 구분입니다.

| 구분 | 설명 | 예시 |
|------|------|------|
| **Worker** | AI 에이전트 (프롬프트) | `code_reviewer` |
| **노드** | 워크플로우의 실행 단위 | Worker 노드 (code_reviewer 사용) |

```
워크플로우:
[Input 노드] → [Worker 노드 (code_reviewer)] → [Worker 노드 (bug_fixer)] → [Output 노드]
```

---

### Q8: 어떤 종류의 워크플로우를 만들 수 있나요?

**A**: 소프트웨어 개발 관련 거의 모든 작업을 자동화할 수 있습니다.

**예제**:

1. **코드 작성 및 리뷰**
   ```
   [요구사항] → [설계] → [코딩] → [테스트] → [리뷰] → [수정] → [완료]
   ```

2. **문서화 자동화**
   ```
   [코드] → [분석] → [API 문서] → [사용자 가이드] → [완료]
   ```

3. **버그 수정**
   ```
   [버그 보고] → [원인 분석] → [수정 안 제안] → [테스트] → [완료]
   ```

4. **병렬 처리**
   ```
   [요구사항]
     ├→ [Coder] → [Output]
     ├→ [Tester] → |
     └→ [Reviewer] → [Merger] → [최종 결과]
   ```

---

### Q9: 세션이란 무엇인가요?

**A**: 한 번의 워크플로우 실행 전체를 나타냅니다.

```
세션 = 워크플로우 실행 1회

세션의 정보:
- 시작 시간 및 종료 시간
- 각 노드의 입력/출력
- 토큰 사용량
- 실행 상태 (성공/실패/진행 중)
```

**세션 조회**:

```
UI: [프로젝트] → [세션 이력] → [세션 선택]
파일: ~/.claude-flow/[프로젝트]/sessions/[session-id].json
```

---

## 워크플로우 설계

### Q10: Input 노드에 입력값을 어떻게 설정하나요?

**A**: Input 노드에서 직접 입력하거나, 실행 시 입력받을 수 있습니다.

**방법 1: 고정 입력값**

```
Input 노드 설정:
- 입력값: "다음 코드를 분석해주세요: [코드 내용]"
```

**방법 2: 실행 시 입력**

```
Input 노드 설정:
- 입력값: (비워 두면 실행 시 묻음)

실행 시:
1. "워크플로우 실행" 클릭
2. 팝업에 입력값 입력
3. "실행" 버튼 클릭
```

**방법 3: 다른 노드의 출력값 사용**

```
Worker 노드 템플릿: {{input}}
Input의 값이 {{input}} 자리에 대체됨
```

---

### Q11: Worker 노드 템플릿에서 변수를 어떻게 사용하나요?

**A**: 이중 중괄호 `{{}}` 구문으로 변수를 참조합니다.

**사용 가능한 변수**:

```
{{input}}            # Input 노드의 입력값
{{node_1.output}}    # node_1의 출력값
{{node_2.output}}    # node_2의 출력값
{{node_3.output}}    # node_3의 출력값
```

**실제 예시**:

```
템플릿:
"다음 코드를 분석하시고, {{node_1.output}} 보고서를 바탕으로 개선안을 제시해주세요:

{{input}}"

렌더링 결과:
"다음 코드를 분석하시고, [node_1의 분석 결과] 보고서를 바탕으로 개선안을 제시해주세요:

[Input의 코드]"
```

---

### Q12: 조건 노드는 어떻게 사용하나요?

**A**: 조건에 따라 다른 경로로 분기합니다.

**조건 타입**:

| 타입 | 설명 | 예시 |
|------|------|------|
| **contains** | 텍스트 포함 여부 | "ERROR" 포함 → True |
| **regex** | 정규식 패턴 매칭 | `^[A-Z]` 로 시작 → True |
| **length** | 텍스트 길이 | 길이 > 100 → True |
| **custom** | Python 표현식 | `len(value) > 50` → True |
| **llm** | AI가 판단 | "버그가 있는가?" → True |

**실제 예시**:

```
조건 설정:
- 조건 타입: "contains" (포함)
- 값: {{node_1.output}} (분석 결과)
- 패턴: "ERROR|FAIL|BUG"

결과:
- [True] → [Bug Fixer] (버그 수정)
- [False] → [Output] (완료)
```

---

### Q13: 병렬 실행은 어떻게 설정하나요?

**A**: 위상 정렬 알고리즘으로 자동 감지합니다. 의존성이 없는 노드는 동시 실행됩니다.

**예시**:

```
[Input]
  ├→ [Coder]      (의존성 없음)
  ├→ [Tester]     (의존성 없음)
  └→ [Reviewer]   (의존성 없음)
       ↓
  [Merger] → [Output]
```

**동작**:
1. Coder, Tester, Reviewer 동시 실행 (3개)
2. 모두 완료 후 Merger 실행
3. 최종 결과 출력

**성능 효과**:
- 순차 실행: 3 + 1 = 4번 라운드 필요
- 병렬 실행: 2번 라운드 (약 50% 시간 단축)

---

### Q14: Merge 노드의 병합 전략은 무엇인가요?

**A**: 여러 입력을 하나로 통합하는 방식을 선택합니다.

| 전략 | 설명 | 예시 |
|------|------|------|
| **concatenate** | 모든 입력을 순서대로 연결 | `input1 + input2 + input3` |
| **first** | 첫 번째 입력만 사용 | `input1` |
| **last** | 마지막 입력만 사용 | `input3` |
| **custom** | 사용자 정의 함수 | (개발자용) |

**실제 예시**:

```
여러 테스트 결과 병합:

전략: concatenate (연결)

입력 1: [Unit Test 결과]
입력 2: [Integration Test 결과]
입력 3: [E2E Test 결과]

출력:
"[Unit Test 결과]
[Integration Test 결과]
[E2E Test 결과]"
```

---

## 워크플로우 실행

### Q15: 워크플로우를 실행하려면 어떻게 해야 하나요?

**A**: 3가지 방법이 있습니다.

**방법 1: 웹 UI (권장)**

```
1. 브라우저에서 http://localhost:5173 접속
2. 워크플로우 선택
3. 우측 상단 "실행" 버튼 클릭
4. 입력값 입력 (필요시)
5. "실행" 버튼 클릭
```

**방법 2: REST API**

```bash
# 워크플로우 실행 (SSE 스트리밍)
curl -N http://localhost:5173/api/workflows/execute \
  -H "Content-Type: application/json" \
  -d '{
    "workflow": {...},
    "input": "사용자 입력값"
  }'
```

**방법 3: Python 코드 (개발자용)**

```python
from src.presentation.web.services.workflow_executor import WorkflowExecutor

executor = WorkflowExecutor(project_path="/path/to/project")
result = executor.execute(workflow=..., input_value="...")
```

---

### Q16: 실행 중 워크플로우를 중단할 수 있나요?

**A**: 네, **중단** 버튼으로 언제든지 중단할 수 있습니다.

```
UI: 실행 로그 패널 → "중단" 버튼 클릭

주의:
- 현재 진행 중인 노드가 완료될 때까지 대기
- 이미 완료된 노드의 결과는 유지됨
```

---

### Q17: 실행 로그는 어디에 저장되나요?

**A**: 파일 시스템에 저장됩니다.

**로그 위치**:

```
~/.claude-flow/[프로젝트명]/
  └── logs/
      ├── session-[session-id].log         # 전체 세션 로그
      ├── node-[node-id]-[timestamp].log   # 노드별 상세 로그
      └── error-[timestamp].log            # 에러 로그
```

**UI에서 확인**:

```
[프로젝트] → [세션 이력] → [세션 선택] → [상세 로그]
```

**명령어로 확인**:

```bash
# 최근 로그 확인
tail -f ~/.claude-flow/claude-flow-web/logs/session-*.log

# 특정 노드의 로그
grep "node_1" ~/.claude-flow/claude-flow-web/logs/*.log
```

---

### Q18: 이전 실행 결과를 다시 확인할 수 있나요?

**A**: 네, 세션 이력에서 조회 및 복원할 수 있습니다.

```
UI: [프로젝트] → [세션 이력]
    → [세션 선택]
    → [상세 보기]

파일: ~/.claude-flow/[프로젝트]/sessions/[session-id].json
```

**세션 정보**:

```json
{
  "session_id": "...",
  "timestamp": "2024-01-01T12:00:00",
  "workflow_id": "...",
  "status": "completed",
  "node_results": {
    "node_1": {
      "input": "...",
      "output": "...",
      "tokens_used": 1500
    }
  },
  "total_tokens": 5000
}
```

---

### Q19: 실행 시간을 측정할 수 있나요?

**A**: 네, 실행 로그에서 확인할 수 있습니다.

```
UI: 실행 로그 → [노드 선택]

표시 정보:
- 노드 시작 시간
- 노드 종료 시간
- 소요 시간 (자동 계산)
- 토큰 사용량
```

**명령어로 측정**:

```bash
# 시간 측정
time claude-flow-web

# 또는 API 호출 시간
curl -w "@curl-format.txt" -o /dev/null -s http://localhost:5173/api/...
```

---

## Worker 에이전트

### Q20: 사용 가능한 Worker 목록은 어디서 확인하나요?

**A**: 3가지 방법으로 확인할 수 있습니다.

**방법 1: 웹 UI (권장)**

```
Worker 노드 선택 → 우측 패널 → "에이전트" 드롭다운
(모든 사용 가능한 Worker 목록 표시)
```

**방법 2: REST API**

```bash
curl http://localhost:5173/api/agents

응답:
[
  {
    "name": "code_reviewer",
    "role": "코드 리뷰 전문가",
    "model": "claude-sonnet-4-5-20250929",
    "thinking": true
  },
  ...
]
```

**방법 3: 파일 확인**

```bash
# 빌트인 Worker
ls -la prompts/

# 커스텀 Worker
ls -la ~/.claude-flow/custom_workers/
```

---

### Q21: Worker의 기본 설정(모델, Thinking 등)을 변경할 수 있나요?

**A**: 예제 1) 파일로 변경 가능합니다 (자동 스캔).

```bash
# prompts/code_reviewer.txt 파일 상단에 추가:

---
role: 코드 리뷰 전문가
model: claude-haiku-4-5-20251001  # 다른 모델로 변경
thinking: false  # Thinking 비활성화
allowed_tools:
  - read
  - grep
---

[기존 프롬프트...]
```

**예제 2) 노드에서 변경 가능합니다 (일회성).

```
Worker 노드 설정:
- 에이전트: code_reviewer (선택)
- 모델 오버라이드: claude-haiku-4-5-20251001 (선택)
- Thinking 오버라이드: false (선택)
```

---

### Q22: 커스텀 Worker를 만드는 방법은?

**A**: 프롬프트 파일을 만들면 자동으로 Worker로 등록됩니다.

**Step 1: 프롬프트 파일 생성**

```bash
touch ~/.claude-flow/custom_workers/my_worker.txt
```

**Step 2: 프롬프트 작성**

```txt
---
role: 커스텀 작업 담당
allowed_tools:
  - read
  - write
  - bash
model: claude-sonnet-4-5-20250929
thinking: true
---

# My Custom Worker

당신은 [역할] 전문가입니다.

## 책임

- [책임 1]
- [책임 2]
- [책임 3]

## 작업 완료 시 필수 조치

1. 상세한 작업 보고서 작성
2. 결과를 마커로 감싸기:

---NEXT_WORKER_OUTPUT_START---
[요약]
---NEXT_WORKER_OUTPUT_END---
```

**Step 3: 워크플로우 재시작**

```bash
# 서버 재시작 (새 Worker 감지)
# 또는 UI에서 새로고침
```

**Step 4: Worker 노드에서 선택**

```
Worker 노드 설정:
- 에이전트: my_worker (새로운 Worker!)
```

---

### Q23: Worker가 도구(tools)를 사용하려면?

**A**: 프롬프트에서 `allowed_tools`로 지정합니다.

```txt
---
allowed_tools:
  - read      # 파일 읽기
  - write     # 파일 작성
  - edit      # 파일 수정
  - bash      # 셸 명령어 실행
  - glob      # 파일 검색
  - grep      # 텍스트 검색
---
```

**도구 사용 예**:

```
프롬프트 내용:

당신은 다음 도구를 사용할 수 있습니다:
1. read: 파일의 내용을 읽어주세요
2. bash: 필요한 명령어를 실행해주세요
3. write: 결과를 파일에 저장해주세요
```

---

### Q24: Worker의 출력을 편집할 수 있나요?

**A**: 아니요, Worker의 출력은 자동으로 처리됩니다.

하지만 다음 방법으로 출력을 제어할 수 있습니다:

**방법 1: 작업 템플릿으로 조정**

```
템플릿: "{{input}}을 분석하되, 핵심 내용만 250자 이내로 요약해주세요"
(Worker가 요청을 따를 가능성 높음)
```

**방법 2: 출력 추출 설정**

```
Worker 노드 설정 → [⚙️ 고급 설정]
→ [📤 출력 추출 전략] → [마커 사이 텍스트]
→ 시작 마커: <!-- RESULT -->
→ 종료 마커: <!-- /RESULT -->

템플릿에 마커 포함:
"결과를 <!-- RESULT -->와 <!-- /RESULT --> 사이에 작성해주세요"
```

---

## 트러블슈팅

### Q25: "Worker를 찾을 수 없습니다" 에러가 발생합니다

**A**: Worker 파일이 없거나 서버가 새로고침되지 않았을 가능성이 있습니다.

**해결책**:

```bash
# 1. 프롬프트 파일 확인
ls -la prompts/[worker_name].txt      # 빌트인 Worker
ls -la ~/.claude-flow/custom_workers/ # 커스텀 Worker

# 2. 파일 이름 확인 (대소문자 구분!)
# 예: code_reviewer.txt (O), CodeReviewer.txt (X)

# 3. 서버 재시작
# UI: 새로고침 (Cmd/Ctrl + R)
# 또는 서버 프로세스 재시작

# 4. API 확인
curl http://localhost:5173/api/agents | grep "code_reviewer"
```

---

### Q26: Worker 실행 중 "토큰 부족" 에러가 발생합니다

**A**: Claude API의 토큰 한도에 도달했을 가능성이 있습니다.

**해결책**:

```bash
# 1. 토큰 사용량 확인
# UI: 실행 로그 → [노드 선택] → "토큰 사용량" 확인

# 2. 입력값 축소
# 불필요한 텍스트 제거, 파일 크기 감소

# 3. Thinking 비활성화 (간단한 작업)
Worker 노드 설정 → Thinking: false

# 4. 더 작은 모델 사용
allowed_tools 설정: model: claude-haiku-4-5-20251001
```

---

### Q27: Worker가 응답을 주지 않습니다 (무한 대기)

**A**: API 지연, 네트워크 문제, 또는 스트림 문제일 수 있습니다.

**해결책**:

```bash
# 1. 워크플로우 중단
UI: 실행 로그 → [중단] 버튼

# 2. 로그 확인
tail -f ~/.claude-flow/claude-flow-web/logs/session-*.log

# 3. 서버 상태 확인
curl http://localhost:5173/api/health

# 4. 네트워크 연결 확인
ping api.anthropic.com

# 5. 토큰 유효성 확인
echo $CLAUDE_CODE_OAUTH_TOKEN
```

---

### Q28: 특정 노드만 자꾸 실패합니다

**A**: 해당 Worker의 설정이나 프롬프트에 문제가 있을 수 있습니다.

**해결책**:

```bash
# 1. 노드 입력값 확인
UI: 실행 로그 → [노드 선택] → [입력값 보기]

# 2. Worker 프롬프트 확인
cat prompts/[worker_name].txt
cat ~/.claude-flow/custom_workers/[worker_name].txt

# 3. 프롬프트 수정
# 명확한 지침 추가, 예제 포함

# 4. 허용 도구 확인
# 필요한 도구가 all_tools에 포함되어 있는지

# 5. 모델 변경 시도
Worker 노드 설정 → 모델 오버라이드: claude-sonnet-4-5-20250929
```

---

### Q29: Human-in-the-Loop 팝업이 나타나지 않습니다

**A**: Worker 프롬프트에 `@ASK_USER:` 패턴이 없을 수 있습니다.

**해결책**:

```bash
# 1. Worker 프롬프트 확인
grep "@ASK_USER:" prompts/[worker_name].txt

# 2. 패턴 추가 (프롬프트 수정)
Worker 프롬프트에 다음 내용 추가:

"필요시 사용자 입력을 요청하세요:
@ASK_USER: '이 결정에 동의하시나요?'"

# 3. 서버 재시작
```

---

### Q30: 워크플로우 저장이 안 됩니다

**A**: 디렉토리 권한 또는 저장 경로 문제일 가능성이 있습니다.

**해결책**:

```bash
# 1. 저장 디렉토리 확인
ls -la ~/.claude-flow/workflows/

# 2. 디렉토리 권한 확인
chmod 755 ~/.claude-flow/
chmod 755 ~/.claude-flow/workflows/

# 3. 디렉토리 생성 (없으면)
mkdir -p ~/.claude-flow/workflows/

# 4. 파일 이름 확인 (특수문자 제거)
# 예: "My Workflow" (O), "My/Workflow" (X)

# 5. 로그 확인
grep "workflow" ~/.claude-flow/logs/session-*.log
```

---

## 성능 최적화

### Q31: 실행 시간을 줄이려면?

**A**: 다음 최적화 방법들을 시도해보세요.

**최적화 1: 병렬 실행 사용**

```
순차: [Coder] → [Tester] → [Reviewer] → [Merge]
시간: 4 라운드

병렬: [Coder]
      [Tester] → [Merge]
      [Reviewer]
시간: 2 라운드 (50% 단축)
```

**최적화 2: Thinking 비활성화**

```
Thinking 활성화: +5-10초 (깊은 분석)
Thinking 비활성화: 즉시 응답 (간단한 작업)

사용 권장:
- ✅ 복잡한 분석, 아키텍처 설계
- ❌ 간단한 포맷팅, 코드 복사
```

**최적화 3: 더 작은 모델 사용**

```
Claude Sonnet (전체 기능): ~5초
Claude Haiku (빠름): ~1초

권장:
- 간단한 작업: Haiku
- 복잡한 분석: Sonnet
```

**최적화 4: 출력 추출 설정**

```
전체 텍스트 (전송): 5KB (느림)
마커 사이만 (전송): 100B (빠름)

효과: 문맥 크기 감소 → 다음 Worker 더 빠름
```

---

### Q32: 토큰 사용량을 줄이려면?

**A**: 다음 방법으로 토큰 사용량을 절감할 수 있습니다.

**방법 1: 입력값 최소화**

```
전: 5000줄 코드 전체 (500 토큰)
후: 주요 부분만 (100 토큰)

효과: 80% 감소
```

**방법 2: 세션 재활용**

```
Claude Flow는 자동으로 이전 세션 컨텍스트 재사용:
- 노드 1: 500 토큰
- 노드 2: 200 토큰 (재사용으로 감소)
- 노드 3: 150 토큰

총합: 50% 절감 (순차 실행 대비)
```

**방법 3: 더 작은 모델 사용**

```
Sonnet: 1000 토큰 사용
Haiku: 300 토큰 사용

적절한 작업에 적절한 모델 사용 → 70% 절감
```

**방법 4: 출력 추출 설정**

```
전: 모든 내용 다음 Worker로 전달
후: 마커 사이의 핵심만 전달

다음 Worker의 입력 크기 감소 → 30% 절감
```

---

### Q33: 메모리 사용량이 높습니다

**A**: 대용량 파일 처리 또는 병렬 작업으로 인한 것일 수 있습니다.

**해결책**:

```bash
# 1. 메모리 사용량 확인
ps aux | grep claude-flow-web
top

# 2. 캐시 삭제
rm -rf ~/.claude-flow/cache/
rm -rf ~/.claude/cache/

# 3. 불필요한 세션 삭제
rm -rf ~/.claude-flow/[프로젝트]/sessions/old-session-id

# 4. 병렬 작업 수 제한
# Worker 노드를 순차 실행으로 변경 (병렬도 줄임)

# 5. 서버 재시작
pkill -f claude-flow-web
claude-flow-web
```

---

## 고급 기능

### Q34: Python 스크립트에서 Claude Flow를 사용할 수 있나요?

**A**: 네, Python SDK를 통해 프로그래밍 방식으로 사용할 수 있습니다.

```python
from src.presentation.web.services.workflow_executor import WorkflowExecutor
from src.infrastructure.config.loader import JsonConfigLoader

# 프로젝트 경로 설정
project_path = "/path/to/claude-flow-web"

# WorkflowExecutor 생성
executor = WorkflowExecutor(project_path=project_path)

# 워크플로우 정의
workflow = {
    "nodes": [
        {
            "id": "node_1",
            "type": "input",
            "data": {"value": "분석할 코드"}
        },
        {
            "id": "node_2",
            "type": "worker",
            "data": {
                "agent_name": "code_reviewer",
                "task_template": "{{input}}을 리뷰해주세요"
            }
        }
    ],
    "edges": [{"source": "node_1", "target": "node_2"}]
}

# 워크플로우 실행
result = executor.execute(
    workflow=workflow,
    input_value="코드 내용"
)

# 결과 확인
print(result)
```

---

### Q35: 워크플로우를 버전 관리할 수 있나요?

**A**: 워크플로우 파일을 Git으로 관리할 수 있습니다.

```bash
# 1. 워크플로우 파일 확인
ls ~/.claude-flow/workflows/

# 2. Git 저장소에 추가
cp ~/.claude-flow/workflows/*.json ./workflows/
git add workflows/
git commit -m "Add workflow templates"

# 3. 다른 환경에서 복원
cp ./workflows/*.json ~/.claude-flow/workflows/
```

---

### Q36: 여러 프로젝트를 관리할 수 있나요?

**A**: 네, 프로젝트별로 독립적인 워크플로우, 세션, 설정을 관리할 수 있습니다.

```bash
# 1. 프로젝트 생성
mkdir -p ~/my-projects/project-1
cd ~/my-projects/project-1

# 2. Claude Flow 초기화
claude-flow-web

# 3. 프로젝트별 설정
# UI: [프로젝트] → [프로젝트 선택] → [새 프로젝트]

# 4. 프로젝트 데이터
~/.claude-flow/project-1/
  ├── workflows/
  ├── sessions/
  ├── logs/
  └── custom_workers/
```

---

### Q37: Claude Flow를 Docker에서 실행할 수 있나요?

**A**: 네, Dockerfile을 작성하여 실행할 수 있습니다.

```dockerfile
FROM python:3.11

WORKDIR /app

# 의존성 설치
COPY requirements.txt .
RUN pip install -r requirements.txt

# 코드 복사
COPY . .

# 웹 빌드
RUN cd src/presentation/web/frontend && npm install && npm run build

# 포트 노출
EXPOSE 5173

# 서버 시작
CMD ["python", "-m", "src.presentation.web.app"]
```

```bash
# 빌드 및 실행
docker build -t claude-flow .
docker run -p 5173:5173 \
  -e CLAUDE_CODE_OAUTH_TOKEN='your-token' \
  -v ~/.claude-flow:/root/.claude-flow \
  claude-flow
```

---

### Q38: 워크플로우 실행을 자동화할 수 있나요?

**A**: REST API를 통해 자동화할 수 있습니다.

```bash
# 워크플로우 실행 (SSE 스트리밍)
curl -N \
  -H "Content-Type: application/json" \
  -d '{
    "workflow": {...},
    "input": "자동화된 입력"
  }' \
  http://localhost:5173/api/workflows/execute
```

**cron으로 정기 실행**:

```bash
# 매일 오전 10시에 코드 분석
0 10 * * * curl -s -X POST http://localhost:5173/api/workflows/execute \
  -H "Content-Type: application/json" \
  -d '{"workflow": {...}, "input": "daily analysis"}'
```

---

## 더 많은 정보

- **기술 상세 가이드**: [CLAUDE.md](../CLAUDE.md)
- **빠른 시작**: [README.md](../README.md#빠른-시작)
- **설치 가이드**: [README.md](../README.md#설치-가이드)
- **API 레퍼런스**: (문서화 예정)

**여전히 해결되지 않는 문제가 있다면?**

- GitHub Issues에서 버그 리포트
- GitHub Discussions에서 질문
- 로그 파일 (`~/.claude-flow/logs/`) 확인

행운을 빕니다! 🚀
