# Claude Flow TUI 사용 가이드

> LLM 피드백 루프 기반 대화형 AI 에이전트 터미널 인터페이스

---

## 설치

### 1. 패키지 설치

```bash
cd /Users/simdaseul/.cursor/worktrees/claude-flow-web/L5Thp

# 개발 모드로 설치
pip install -e .

# 또는 일반 설치
pip install .
```

### 2. 환경변수 설정

Claude Code OAuth 토큰이 필요합니다:

```bash
export CLAUDE_CODE_OAUTH_TOKEN='your-token-here'
```

또는 `.env` 파일에 추가:

```bash
echo "CLAUDE_CODE_OAUTH_TOKEN=your-token-here" >> .env
```

**토큰 발급 방법:**
1. [Claude Code](https://claude.ai/code) 접속
2. Settings → OAuth Tokens → Generate Token
3. 토큰 복사

---

## 기본 사용법

### 앱 실행

```bash
# 현재 디렉토리에서 실행
claude-flow

# 특정 디렉토리에서 실행
claude-flow /path/to/your/project
```

### 첫 실행 화면

```
┌─────────────────────────────────────────────────────────┐
│ Claude Flow TUI v1.0 시작됨                              │
│ 프로젝트: my-project                                     │
│ 경로: /Users/username/projects/my-project                │
│ Git 브랜치: main                                         │
│ ✓ CLAUDE.md 로드됨                                       │
│                                                          │
│                                                          │
│                                                          │
│                                                          │
└─────────────────────────────────────────────────────────┘
│ 메시지 입력...                                           │
│                                                          │
└─────────────────────────────────────────────────────────┘
📁 my-project [main]  Session: abc12345  🪙 0 tokens ($0.0000)
```

---

## 주요 기능

### 1. 대화하기

단순히 메시지를 입력하고 Enter를 누르세요:

```
You:
프로젝트의 README 파일을 작성해줘

Claude:
README 파일을 작성하겠습니다...
[마크다운으로 렌더링된 응답]
```

**팁:**
- `Shift+Enter`: 줄바꿈
- `Enter`: 메시지 전송
- `↑/↓`: 이전 입력 탐색

### 2. 세션 관리

**새 세션 시작:**
```
Ctrl+N
```

**세션 불러오기:**
```
Ctrl+O
```

세션 목록이 표시되면 화살표 키로 선택하고 Enter:

```
┌─ 📋 세션 목록 ─────────────────────┐
│ abc12345 | 2024-11-06 | 5개 메시지   │
│   프로젝트의 README 파일을 작성해줘... │
│ def67890 | 2024-11-05 | 3개 메시지   │
│   버그 수정: 로그인 에러...          │
│                                     │
│ [선택]  [취소]                      │
└─────────────────────────────────────┘
```

### 3. 프로젝트 정보

```
Ctrl+I
```

현재 프로젝트의 통계를 표시:

```
📁 프로젝트: my-project
📂 경로: /Users/username/projects/my-project
📊 총 세션 수: 10
🪙 총 토큰: 45,230
📅 오늘 세션: 3
🔀 Git 브랜치: main
```

### 4. 화면 관리

**화면 지우기** (대화 기록은 유지):
```
Ctrl+L
```

**작업 중단:**
```
Ctrl+C
```
- 입력 중: 입력창 초기화
- 실행 중: 작업 중단
- 아무것도 없음: 앱 종료 확인

**앱 종료:**
```
Ctrl+Q
```

---

## 고급 기능

### LLM 피드백 루프

설정 파일(`~/.claude-flow/config.json`)에서 활성화:

```json
{
  "feedback_loop_defaults": {
    "enabled": true,
    "max_iterations": 3,
    "condition_model": "claude-haiku-4.5"
  }
}
```

피드백 루프가 활성화되면, 에이전트의 출력을 자동으로 검증하고 조건이 충족될 때까지 재시도합니다.

### CLAUDE.md 자동 로드

프로젝트 루트에 `CLAUDE.md` 파일이 있으면 자동으로 로드되어 에이전트의 컨텍스트에 포함됩니다:

```markdown
# 프로젝트 컨텍스트

이 프로젝트는 ...
```

### 설정 커스터마이징

`~/.claude-flow/config.json`:

```json
{
  "theme": "dark",
  "display": {
    "show_statusbar": true,
    "show_timestamps": true,
    "show_token_counts": true
  },
  "default_model": "claude-sonnet-4.5",
  "logging": {
    "auto_save": true,
    "log_level": "INFO",
    "max_file_size_mb": 10,
    "retention_days": 30
  }
}
```

---

## 데이터 저장 위치

### 세션 파일
```
~/.claude-flow/{project-name}/sessions/{session-id}.json
```

### 로그 파일
```
~/.claude-flow/{project-name}/logs/{session-id}.log
```

### 전역 설정
```
~/.claude-flow/config.json
```

---

## 키보드 단축키 전체 목록

| 단축키 | 기능 |
|--------|------|
| `Ctrl+N` | 새 세션 |
| `Ctrl+O` | 세션 불러오기 |
| `Ctrl+I` | 프로젝트 정보 |
| `Ctrl+L` | 화면 지우기 |
| `Ctrl+C` | 중단/취소/종료 |
| `Ctrl+Q` | 앱 종료 |
| `↑/↓` | 이전 입력 탐색 |
| `Shift+Enter` | 줄바꿈 |
| `Enter` | 메시지 전송 |
| `Esc` | 모달 닫기 |

---

## 문제 해결

### 토큰 에러

```
❌ CLAUDE_CODE_OAUTH_TOKEN 환경변수가 설정되지 않았습니다.
```

**해결:**
```bash
export CLAUDE_CODE_OAUTH_TOKEN='your-token-here'
```

### SDK 없음 경고

```
Warning: claude-agent-sdk not available. Running in mock mode.
```

**해결:**
```bash
pip install claude-agent-sdk
```

### 화면이 깨짐

터미널 크기를 최소 80x24로 조정하세요:

```bash
# 터미널 크기 확인
echo $COLUMNS x $LINES
```

---

## 팁

1. **효율적인 대화**
   - 명확하고 구체적인 지시
   - 한 번에 하나의 작업 요청
   - 필요시 단계별 지시

2. **세션 활용**
   - 관련 작업은 같은 세션에서
   - 컨텍스트 유지로 효율적인 대화
   - 완료된 세션은 정기적으로 정리

3. **로그 확인**
   - 에러 발생 시 로그 파일 확인
   - `~/.claude-flow/{project}/logs/` 참조

---

## 다음 단계

- [기능명세서](./TUI_기능명세서.md) 전체 기능 확인
- [API 문서](./api.md) REST API 연동
- [아키텍처](./architecture.md) 시스템 구조 이해

---

**문의사항**
- GitHub Issues
- GitHub Discussions

