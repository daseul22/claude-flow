# 로그 및 세션 저장 테스트 가이드

## 문제 상황
- 로그 파일이 `~/.claude-flow/{project}/logs/`에 저장되지 않음
- 세션 파일이 `~/.claude-flow/{project}/web-sessions/`에 저장되지 않음
- 설정 메뉴의 "로그 & 세션 뷰어" 기능이 빈 목록 표시

## 수정 사항

### 1. 로그 디렉토리 경로 수정
- ✅ `validator.py`: `.better-llm` → `.claude-flow` 변경
- ✅ `structured_logger.py`: `project_path` 인자 추가

### 2. 세션 저장 로직 개선
- ✅ `workflow_session_store.py`: 디렉토리 자동 생성
- ✅ 로그 레벨 info로 변경하여 저장 확인 가능
- ✅ `background_workflow_manager.py`: `project_path`를 `get_session_store()`에 전달

### 3. LLM 조건 파싱 개선
- ✅ 한글/영어 모두 지원
- ✅ 파싱 실패 시 명확한 에러 로그

## 테스트 방법

### Step 1: 웹 서버 실행
```bash
# 터미널에서 실행
claude-flow-web

# 또는
python3 -m src.presentation.web.app
```

### Step 2: 워크플로우 실행

1. 브라우저에서 http://localhost:8000 접속
2. 프로젝트 선택: `/Users/simdaseul/dallem-repo/claude-flow-web`
3. 워크플로우 로드: "자동 버그 분석 및 수정 파이프라인" (test.json)
4. **실행** 버튼 클릭
5. 실행 로그 패널에서 로그 확인

### Step 3: 로그 및 세션 확인

**터미널에서 확인:**
```bash
# 로그 디렉토리 확인
ls -lh ~/.claude-flow/claude-flow-web/logs/

# 세션 디렉토리 확인
ls -lh ~/.claude-flow/claude-flow-web/web-sessions/

# 로그 파일 내용 확인 (system.log)
tail -50 ~/.claude-flow/claude-flow-web/logs/system.log

# 세션 파일 확인
cat ~/.claude-flow/claude-flow-web/web-sessions/*.json | jq .
```

**웹 UI에서 확인:**
1. 헤더의 **설정 메뉴 (⚙️)** 클릭
2. **"로그 & 세션 보기"** 클릭
3. **세션 탭**: 세션 파일 목록 표시 여부 확인
4. **로그 탭**: 로그 파일 목록 표시 여부 확인

## 예상 결과

### 성공 시
```
~/.claude-flow/claude-flow-web/
├── logs/
│   ├── system.log (모든 로그)
│   ├── claude-flow.log (앱 로그)
│   ├── claude-flow-error.log (에러 로그)
│   └── {session-id}/
│       ├── debug.log
│       ├── info.log
│       └── error.log
└── web-sessions/
    └── {session-id}.json (세션 파일)
```

### 로그 파일 내용 예시
```json
{
  "event": "세션 저장 완료",
  "session_id": "wf-123456",
  "path": "~/.claude-flow/claude-flow-web/web-sessions/wf-123456.json",
  "timestamp": "2025-11-05T22:00:00Z"
}
```

### 세션 파일 내용 예시
```json
{
  "session_id": "wf-123456",
  "workflow": {...},
  "status": "running",
  "logs": [
    {
      "event_type": "node_start",
      "node_id": "input-1",
      ...
    }
  ],
  "node_outputs": {},
  "start_time": "2025-11-05T22:00:00Z"
}
```

## 문제 해결

### 로그가 저장되지 않는 경우

1. **디렉토리 권한 확인:**
```bash
ls -ld ~/.claude-flow/
chmod 755 ~/.claude-flow/
```

2. **수동으로 디렉토리 생성 후 재시도:**
```bash
mkdir -p ~/.claude-flow/claude-flow-web/logs
mkdir -p ~/.claude-flow/claude-flow-web/web-sessions
```

3. **로그 레벨 확인 (.env 파일):**
```bash
# .env 파일에 추가
LOG_LEVEL=INFO
```

### 세션이 저장되지 않는 경우

1. **터미널에서 앱 시작 로그 확인:**
```
🚀 Claude Flow 시작...
워크플로우 세션 저장소 초기화: ~/.claude-flow/claude-flow-web/web-sessions
```

2. **워크플로우 실행 시 로그 확인:**
```
세션 생성: wf-123456 (워크플로우: 자동 버그 분석...)
세션 저장 완료: wf-123456 → ~/.claude-flow/claude-flow-web/web-sessions/wf-123456.json
```

3. **Python 로깅 모듈 확인:**
```python
# 터미널에서 Python 실행
python3
>>> import logging
>>> logging.getLogger().handlers  # 핸들러 목록 확인
```

## 디버깅 팁

### 실시간 로그 모니터링
```bash
# 터미널 1: 웹 서버 실행
claude-flow-web

# 터미널 2: 로그 실시간 모니터링
tail -f ~/.claude-flow/claude-flow-web/logs/system.log
```

### 세션 파일 실시간 확인
```bash
watch -n 1 'ls -lh ~/.claude-flow/claude-flow-web/web-sessions/'
```

### API 직접 호출 테스트
```bash
# 세션 목록 조회
curl http://localhost:8000/api/projects/sessions/list

# 로그 목록 조회
curl http://localhost:8000/api/projects/logs/list
```

## 추가 정보

### 로그 파일 타입
- `system.log`: 모든 레벨 (DEBUG, INFO, WARNING, ERROR)
- `claude-flow.log`: 앱 전체 로그
- `claude-flow-error.log`: ERROR 이상만
- `{session-id}/debug.log`: DEBUG 레벨만
- `{session-id}/info.log`: INFO, WARNING 레벨
- `{session-id}/error.log`: ERROR, CRITICAL 레벨

### 세션 상태
- `running`: 실행 중
- `completed`: 완료
- `error`: 에러 발생
- `cancelled`: 사용자 취소

## 기대 효과

✅ 워크플로우 실행 후 로그가 `~/.claude-flow/claude-flow-web/logs/`에 저장됨
✅ 세션 파일이 `~/.claude-flow/claude-flow-web/web-sessions/`에 저장됨
✅ 웹 UI의 "로그 & 세션 보기"에서 파일 목록 표시
✅ LLM 조건 평가가 정상 작동 (파싱 실패 시 명확한 로그)
