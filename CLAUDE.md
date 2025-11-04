# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## 프로젝트 개요

**Claude Flow**는 그룹 챗 오케스트레이션 시스템으로, Manager Agent가 전문화된 Worker Agent들을 조율하여 복잡한 소프트웨어 개발 작업을 자동화하는 시스템입니다.

- **이름**: claude-flow
- **버전**: 4.0.0
- **Python 요구사항**: 3.10 이상
- **주요 기술**: FastAPI, React (ReactFlow), Claude Agent SDK, Python
- **라이선스**: MIT

---

## 핵심 명령어

### 설치 및 환경 설정

```bash
# 1. 프로젝트 설치 (일반 모드 또는 개발 모드)
./setup.sh

# 2. 웹 프론트엔드 빌드
./web-build.sh

# 3. 환경변수 설정 (.env 파일 생성)
cp .env.example .env
# CLAUDE_CODE_OAUTH_TOKEN 설정 필요
```

### 실행 명령어

```bash
# 웹 UI 실행 (드래그 앤 드롭 워크플로우 에디터)
claude-flow-web

# 또는
python -m src.presentation.web.app

# 기본 접속 주소: http://localhost:5173
```

### 개발 명령어

```bash
# 프론트엔드 개발 모드 (Hot Reload)
cd src/presentation/web/frontend
npm run dev

# 프론트엔드 프로덕션 빌드
cd src/presentation/web/frontend
npm run build

# 코드 포맷팅 (Black)
black src/ --line-length 100

# 코드 린팅 (Ruff)
ruff check src/

# 타입 체크 (mypy)
mypy src/
```

### 테스트 명령어

**주의**: 현재 이 프로젝트에는 테스트 파일이 없습니다. 테스트를 추가할 경우 다음 명령어를 사용할 수 있습니다.

```bash
# 단위 테스트 실행 (pytest)
pytest tests/

# 특정 테스트 파일 실행
pytest tests/test_workflow_executor.py

# 커버리지 포함 테스트
pytest --cov=src tests/
```

---

## 아키텍처 개요

### Clean Architecture (4-레이어 구조)

```
src/
├── domain/          # 핵심 도메인 모델 (AgentConfig, Message, Role)
├── application/     # 비즈니스 로직 (현재 비어있음, Presentation의 Services가 담당)
├── infrastructure/  # 외부 시스템 통합 (Claude SDK, 설정, 로깅, 스토리지)
└── presentation/    # 사용자 인터페이스 (FastAPI + React)
```

### 핵심 컴포넌트

#### 1. Domain Layer (`src/domain/`)
- **AgentConfig** (`models/agent.py`): Worker 에이전트 설정 모델
  - 이름, 역할, 프롬프트, 허용 도구, 모델 등 정의
- **Message** (`models/message.py`): 대화 메시지 모델
- **Role**: 메시지 발신자 역할 (user, assistant, system)

#### 2. Infrastructure Layer (`src/infrastructure/`)

**Claude SDK 통합** (`infrastructure/claude/`):
- `WorkerAgent` (`worker_client.py`): Claude Agent SDK 래퍼
  - 시스템 프롬프트 로드 (파일 또는 문자열)
  - 프로젝트별 CLAUDE.md 자동 로드
  - Thinking 모드 지원 (ultrathink 프롬프트)
  - 세션 재활용 (resume_session_id)
  - Human-in-the-Loop 지원 (user_input_callback)

- `SDKExecutor` (`sdk_executor.py`): Template Method Pattern 실행 래퍼
  - `WorkerSDKExecutor.query()`: 스트리밍 응답 처리
  - `WorkerResponseHandler`: 응답 파싱 및 토큰 사용량 추출
  - 응답 타입: AssistantMessage, ResultMessage, UserMessage, SystemMessage

**설정 관리** (`infrastructure/config/`):
- `JsonConfigLoader`: agent_config.json, system_config.json 로드
- `Validator`: 설정 검증 및 프로젝트 루트 탐색

**로깅** (`infrastructure/logging/`):
- `StructuredLogger`: structlog 기반 구조화 로깅 (세션별 파일 핸들러)
- `ErrorTracker`: 예외 추적 및 로깅

**스토리지** (`infrastructure/storage/`):
- `CustomWorkerRepository`: `.claude-flow/custom_workers/` 디렉토리 관리

#### 3. Presentation Layer (`src/presentation/web/`)

**FastAPI 앱** (`app.py`):
- CORS 미들웨어 설정
- 다중 경로 환경변수 로드 (`.env`, `~/.claude-flow/.env`)
- React 빌드 정적 파일 서빙 (`static-react/`)

**REST API 라우터** (`routers/`):
- `workflows/`: 워크플로우 실행, 취소, 저장/로드
- `projects/`: 프로젝트 선택, 워크플로우 목록, 세션 관리, 로그 조회
- `agents.py`: 에이전트 목록 조회
- `templates.py`: 템플릿 갤러리 CRUD
- `custom_workers.py`: 커스텀 워커 CRUD
- `filesystem.py`: 디렉토리 탐색기
- `health.py`: 헬스 체크

**서비스 레이어** (`services/`):

핵심 워크플로우 실행 엔진:
1. `WorkflowExecutor`: 워크플로우 오케스트레이션 (병렬 실행, 세션 관리, 취소 처리)
2. `WorkflowNodeExecutor`: Strategy Pattern - 노드 타입별 실행기 선택
3. `WorkflowGraphManager`: 위상 정렬, 실행 그룹 계산, 순환 참조 감지
4. `WorkflowTemplateRenderer`: Jinja2 템플릿 렌더링 (`{{input}}`, `{{node_1.output}}`)
5. `WorkflowConditionEvaluator`: 조건 평가 (contains, regex, length, custom, LLM)
6. `TemplateManager`: 템플릿 CRUD (내장 vs 사용자 템플릿)

노드 실행기들 (`services/node_executors/`):
- `InputExecutor`: Input 노드 실행 (워크플로우 시작점)
- `WorkerExecutor`: Worker 노드 실행 (Claude SDK 호출)
- `ConditionExecutor`: 조건 분기 노드 (if-else)
- `MergeExecutor`: 병합 노드 (여러 분기 통합)

**React 프론트엔드** (`frontend/`):
- `WorkflowCanvas.tsx`: ReactFlow 기반 워크플로우 캔버스
- `NodePanel.tsx`: 노드 팔레트 (드래그 앤 드롭)
- `RightSidebar.tsx`: 노드 설정 패널, 실행 로그
- `AskUserModal.tsx`: 사용자 입력 대화창 (Human-in-the-Loop)
- 노드 컴포넌트: `WorkerNode`, `InputNode`, `ConditionNode`, `MergeNode`
- 상태 관리: Zustand (`stores/workflowStore`)

---

## 워크플로우 시스템

### 노드 타입

1. **Input 노드**: 워크플로우 시작점, 초기 입력 저장 및 전달
2. **Worker 노드**: Claude SDK 실행, 세션 재활용, Human-in-the-Loop 지원
   - 설정: agent_name, task_template, allowed_tools, thinking
3. **Condition 노드**: 조건 분기 (true/false 경로)
   - 조건 타입: contains, regex, length, custom, LLM
4. **Merge 노드**: 여러 분기 통합
   - 병합 전략: concatenate, first, last, custom

### 실행 흐름

```
1. 사용자 → [Frontend] 워크플로우 실행 요청
2. [API] POST /workflows/execute
3. [WorkflowExecutor] 위상 정렬 및 실행 그룹 계산
4. [WorkflowNodeExecutor] 노드 타입별 실행기 선택
5. [NodeExecutor] 노드 실행 (InputExecutor → WorkerExecutor → ConditionExecutor → MergeExecutor)
6. [SSE Stream] 실시간 이벤트 전송 (node_start → node_output → node_complete → workflow_complete)
```

### 세션 관리

- **노드별 세션 재활용**: `node_sessions: Dict[node_id, sdk_session_id]`
  - Worker 실행 후 SDK 세션 ID 저장
  - 다음 실행 시 `resume_session_id`로 전달 → 컨텍스트 유지
- **세션 이력**: `node_session_history: Dict[node_id, List[SessionInfo]]`
  - 사용자가 과거 세션 선택 및 복원 가능

### Human-in-the-Loop

Worker가 `@ASK_USER: 질문내용` 패턴 출력 → Frontend가 AskUserModal 표시 → 사용자 답변 → Queue 전달 → Worker 재개

---

## 프롬프트 라이브러리

`prompts/` 디렉토리에 27개의 사전 정의 Worker 프롬프트 제공:

- `feature_planner.txt`: 기능 기획
- `backend_coder.txt`: 백엔드 코딩
- `frontend_coder.txt`: 프론트엔드 코딩
- `bug_fixer.txt`: 버그 수정
- `test_coder.txt`: 테스트 코드 작성
- `security_reviewer.txt`: 보안 리뷰
- `documenter.txt`: 문서화
- 등 (총 27개)

### 프롬프트 사용 방법

Worker 노드 설정 시 `agent_name` 필드에 프롬프트 파일명 (확장자 제외)을 지정합니다.

예: `agent_name: "backend_coder"` → `prompts/backend_coder.txt` 로드

---

## 템플릿 시스템

**템플릿 위치**:
- 내장: `templates/*.json` (읽기 전용)
- 사용자: `~/.claude-flow/templates/*.json` (CRUD 가능)

**템플릿 구조**:
```json
{
  "id": "template-id",
  "name": "템플릿 이름",
  "description": "설명",
  "category": "카테고리",
  "workflow": { ... },
  "tags": ["tag1", "tag2"],
  "is_builtin": false
}
```

---

## 디자인 패턴

1. **Clean Architecture**: 의존성 역전 (Domain ← Infrastructure)
2. **Strategy Pattern**: `BaseNodeExecutor` → 노드 타입별 실행기
3. **Template Method Pattern**: `SDKExecutor` → `WorkerSDKExecutor`
4. **Repository Pattern**: `CustomWorkerRepository`
5. **Facade Pattern**: `WorkflowExecutor`
6. **Observer Pattern**: SSE (Server-Sent Events) 실시간 스트리밍

---

## 코딩 컨벤션

### Python 스타일

- **포맷터**: Black (line-length: 100)
- **린터**: Ruff (line-length: 100)
- **타입 힌팅**: mypy (점진적 타입 힌팅 적용 중)
  - `disallow_untyped_defs: false` (나중에 true로 변경 예정)
  - `disallow_incomplete_defs: true`
  - `check_untyped_defs: true`

### TypeScript/React 스타일

- **프레임워크**: React 18 + TypeScript
- **UI 라이브러리**: ReactFlow (워크플로우 캔버스)
- **상태 관리**: Zustand
- **빌드 도구**: Vite
- **스타일링**: Tailwind CSS (추정)

---

## 중요 파일 경로 (Quick Reference)

### 핵심 도메인
- `src/domain/models/agent.py`: AgentConfig, AgentRole
- `src/domain/models/message.py`: Message, Role

### Claude SDK 통합
- `src/infrastructure/claude/worker_client.py`: WorkerAgent (SDK 래퍼)
- `src/infrastructure/claude/sdk_executor.py`: SDKExecutor, WorkerSDKExecutor

### 워크플로우 실행 엔진
- `src/presentation/web/services/workflow_executor.py`: 워크플로우 오케스트레이션
- `src/presentation/web/services/workflow_node_executor.py`: 노드 실행 위임
- `src/presentation/web/services/node_executors/worker_executor.py`: Worker 실행

### 설정 및 로깅
- `src/infrastructure/config/loader.py`: 설정 로더
- `src/infrastructure/logging/structured_logger.py`: 구조화 로깅

### API 라우터
- `src/presentation/web/routers/workflows/core.py`: 워크플로우 API
- `src/presentation/web/routers/workflows/execution.py`: 워크플로우 실행 API

### 프론트엔드
- `src/presentation/web/frontend/src/App.tsx`: 메인 앱
- `src/presentation/web/frontend/src/components/WorkflowCanvas.tsx`: 워크플로우 캔버스

### 설정 파일
- `config/agent_config.json`: 에이전트 설정
- `config/system_config.json`: 시스템 설정
- `.env`: 환경변수 (CLAUDE_CODE_OAUTH_TOKEN 필수)

---

## 디렉토리 구조 개요

```
claude-flow-web/
├── src/
│   ├── domain/              # 도메인 모델
│   ├── application/         # 비즈니스 로직 (현재 비어있음)
│   ├── infrastructure/      # 외부 시스템 통합
│   │   ├── claude/          # Claude SDK 통합
│   │   ├── config/          # 설정 관리
│   │   ├── logging/         # 로깅
│   │   ├── storage/         # 스토리지
│   │   └── errors/          # 에러 정의
│   └── presentation/
│       └── web/
│           ├── routers/     # FastAPI 라우터
│           ├── services/    # 워크플로우 실행 엔진
│           ├── schemas/     # Pydantic 스키마
│           ├── frontend/    # React 프론트엔드
│           └── static-react/  # 빌드된 React 앱
├── prompts/                 # Worker 프롬프트 라이브러리 (27개)
├── templates/               # 워크플로우 템플릿
├── config/                  # 설정 파일
├── docs/                    # 문서
├── pyproject.toml           # Python 프로젝트 설정
├── requirements.txt         # Python 의존성
├── setup.sh                 # 설치 스크립트
├── web-build.sh             # 웹 빌드 스크립트
├── cleanup.sh               # 정리 스크립트
└── .env                     # 환경변수 (gitignore)
```

---

## 환경변수

### 필수 환경변수

- `CLAUDE_CODE_OAUTH_TOKEN`: Claude Code OAuth 토큰 (필수)
  - Claude Code CLI에서 발급받은 토큰

### 환경변수 로드 우선순위

1. 프로젝트 루트의 `.env`
2. `~/.claude-flow/.env`
3. 시스템 환경변수

---

## 일반적인 작업 흐름

### 새로운 노드 타입 추가

1. `src/presentation/web/schemas/workflow_nodes.py`에 노드 데이터 스키마 정의
2. `src/presentation/web/services/node_executors/`에 실행기 구현 (`BaseNodeExecutor` 상속)
3. `src/presentation/web/services/workflow_node_executor.py`에 실행기 등록
4. `src/presentation/web/frontend/src/components/`에 노드 컴포넌트 추가
5. `src/presentation/web/frontend/src/stores/workflowStore.ts`에 노드 타입 등록

### 새로운 Worker 프롬프트 추가

1. `prompts/` 디렉토리에 새 `.txt` 파일 생성
2. 프롬프트 내용 작성 (시스템 프롬프트 형식)
3. Worker 노드 설정에서 `agent_name`으로 참조

### 새로운 템플릿 추가

1. 템플릿 JSON 파일 작성 (Workflow 구조 정의)
2. `templates/` 디렉토리에 저장 (내장 템플릿)
   - 또는 `~/.claude-flow/templates/` (사용자 템플릿)
3. UI에서 템플릿 갤러리로 로드 가능

---

## 문제 해결

### 웹 UI가 빌드되지 않는 경우

```bash
cd src/presentation/web/frontend
rm -rf node_modules package-lock.json
npm install
npm run build
```

### Claude SDK 세션이 재활용되지 않는 경우

- `src/presentation/web/services/workflow_executor.py`의 `node_sessions` 딕셔너리 확인
- `src/infrastructure/claude/worker_client.py`의 `resume_session_id` 파라미터 전달 확인

### Human-in-the-Loop이 작동하지 않는 경우

- Worker 프롬프트에서 `@ASK_USER:` 패턴 사용 확인
- `src/infrastructure/claude/sdk_executor.py`의 패턴 감지 로직 확인
- `src/presentation/web/services/node_executors/worker_executor.py`의 `user_input_queues` 관리 확인

---

## 추가 참고 자료

- **Claude Agent SDK 기능 가이드**: `claude-agent-sdk-features.md` (프로젝트 루트)
  - Claude SDK의 모든 기능 (도구, 훅, 권한, 서브에이전트 등) 상세 설명
  - 공식 문서: https://docs.claude.com/en/api/agent-sdk/overview

- **프로젝트 문서**: `docs/` 디렉토리 (현재 비어있음)

---

## 주의사항

1. **환경변수 필수**: `CLAUDE_CODE_OAUTH_TOKEN` 없이 실행 불가
2. **Node.js 필수**: 웹 프론트엔드 빌드 및 Claude Code CLI 설치에 필요
3. **Python 버전**: Python 3.10 이상 필수
4. **세션 데이터**: `.claude-flow/` 디렉토리에 세션 로그, 커스텀 워커, 템플릿 저장
5. **빌드 출력**: `src/presentation/web/static-react/`에 React 빌드 파일 생성

---

## 향후 개선 사항

- **Application Layer**: 비즈니스 로직을 Presentation에서 분리하여 Application Layer로 이동
- **테스트**: 단위 테스트 및 통합 테스트 추가 (pytest)
- **타입 힌팅**: 점진적으로 `disallow_untyped_defs: true`로 전환
- **문서화**: `docs/` 디렉토리에 API 문서 및 사용자 가이드 추가
