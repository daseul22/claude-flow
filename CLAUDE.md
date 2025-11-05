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

`prompts/` 디렉토리에 47개의 사전 정의 Worker 프롬프트 제공:

- `feature_planner.txt`: 기능 기획
- `backend_coder.txt`: 백엔드 코딩
- `frontend_coder.txt`: 프론트엔드 코딩
- `bug_fixer.txt`: 버그 수정
- `test_coder.txt`: 테스트 코드 작성
- `security_reviewer.txt`: 보안 리뷰
- `documenter.txt`: 문서화
- 등 (총 47개)

### 프롬프트 자동 등록 시스템

**v4.0.0부터 프롬프트 자동 스캔 기능 추가**

`prompts/` 디렉토리의 모든 `.txt` 파일이 자동으로 Worker로 등록됩니다. `agent_config.json`에 수동 등록할 필요가 없습니다.

#### YAML Front Matter (선택 사항)

프롬프트 파일 상단에 YAML Front Matter를 추가하여 메타데이터를 지정할 수 있습니다:

```txt
---
role: 통합 테스트 실행
allowed_tools:
  - read
  - bash
  - glob
  - grep
model: claude-haiku-4-5-20251001
thinking: false
---

# Integration Tester

[프롬프트 내용...]
```

**메타데이터 필드**:
- `role` (문자열): Worker 역할 설명
- `allowed_tools` (배열): 허용 도구 목록 (`read`, `write`, `edit`, `bash`, `glob`, `grep`)
- `model` (문자열): Claude 모델 (`claude-sonnet-4-5-20250929`, `claude-haiku-4-5-20251001` 등)
- `thinking` (boolean): Thinking 모드 활성화 여부

**기본값**:
- 메타데이터가 없는 프롬프트는 기본값 사용:
  - `role`: `{파일명} 전문가`
  - `allowed_tools`: `["read", "write", "edit", "glob", "grep"]`
  - `model`: `"claude-sonnet-4-5-20250929"`
  - `thinking`: `true`

#### 새 프롬프트 추가 방법

1. `prompts/` 디렉토리에 `.txt` 파일 생성
2. (선택) YAML Front Matter로 메타데이터 지정
3. 프롬프트 내용 작성
4. 서버 재시작 → 자동으로 UI에 표시됨

**주의**: `local.txt`는 범용 Worker로 빈 프롬프트 파일이므로 자동 스캔에서 제외됩니다.

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
- `src/infrastructure/config/loader.py`: 설정 로더 (자동 스캔 로직 포함)
  - `JsonConfigLoader.load_agent_configs(auto_scan=True)`: 하이브리드 로딩
  - `_scan_prompts_directory()`: prompts/ 디렉토리 자동 스캔
  - `_parse_prompt_metadata()`: YAML Front Matter 파싱
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

**자동 등록 방식 (v4.0.0+)**:

1. `prompts/` 디렉토리에 새 `.txt` 파일 생성 (예: `my_custom_worker.txt`)
2. (선택) YAML Front Matter로 메타데이터 지정:
   ```txt
   ---
   role: 커스텀 작업 수행
   allowed_tools:
     - read
     - write
   model: claude-sonnet-4-5-20250929
   thinking: true
   ---
   ```
3. 프롬프트 내용 작성 (시스템 프롬프트 형식)
4. 서버 재시작 → 자동으로 UI에 표시됨
5. Worker 노드 설정에서 `agent_name: "my_custom_worker"`로 참조

**기존 방식 (하위 호환)**:
- `config/agent_config.json`에 등록된 Worker는 자동 스캔보다 우선 적용됨
- 동일한 이름의 Worker가 있으면 `agent_config.json` 설정 사용

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

## UI/UX 개선 이력

### [2025-11-05] Worker 노드 출력 추출 설정 UI 추가

**개선 파일**: `src/presentation/web/frontend/src/components/node-config/WorkerNodeConfig.tsx`

**배경**:
- 백엔드에는 출력 추출 로직이 완벽히 구현되어 있었으나 (workflow_utils.py)
- 프론트엔드 UI에서 이 기능을 설정할 수 있는 인터페이스가 없었음
- 사용자가 노드의 출력 중 일부만 파싱해서 다음 노드로 전달하고 싶어도 설정 불가능

**개선 사항**:
- Worker 노드 설정의 "고급 설정" 섹션에 "출력 추출 전략" UI 추가
- 3가지 전략 선택 가능:
  1. **전체 텍스트** (full): 모든 텍스트 블록 추출 (기본)
  2. **마지막 블록만** (last_block): 마지막 텍스트 블록만 추출
  3. **마커 사이 텍스트** (between_markers): 시작/종료 마커 사이의 텍스트만 추출
- between_markers 선택 시 시작/종료 마커 입력 필드 표시

**기술 세부사항**:
- `OutputExtractionConfig` 인터페이스 추가
- `output_extraction` 필드를 `WorkerNodeData`에 추가
- 백엔드의 `extract_text_with_strategy()` 함수와 완벽히 호환

**사용 방법**:
1. Worker 노드 선택 → 노드 설정 패널
2. "⚙️ 고급 설정" 아코디언 열기
3. "📤 출력 추출 전략" 드롭다운에서 전략 선택
4. "마커 사이 텍스트" 선택 시 시작/종료 마커 입력
5. 작업 템플릿에서 Worker에게 마커 사용 지시
   - 예: `결과를 <!-- START -->와 <!-- END --> 사이에 작성해주세요`

**예제**:
```
작업 템플릿: "{{input}}을 분석하고, 결과를 <!-- RESULT -->와 <!-- /RESULT --> 사이에 작성해주세요."
출력 추출 전략: "마커 사이 텍스트"
시작 마커: "<!-- RESULT -->"
종료 마커: "<!-- /RESULT -->"
```

---

### [2025-11-05] 로그 상세 모달 노드 필터링 기능 추가

**개선 파일**: `src/presentation/web/frontend/src/components/LogDetailModal.tsx`

**배경**:
- 실행 노드가 많아지면 로그 상세 모달에서 여러 노드를 그리드로 분할 표시
- 노드가 많을수록 개별 로그를 전체 화면으로 보기 어려워짐

**개선 사항**:
- 로그 상세 모달 헤더에 노드 필터 드롭다운 추가
- 사용자가 특정 노드를 선택하면 해당 노드의 로그만 전체 화면으로 표시
- "모든 노드" 옵션으로 기존 동작 유지 (다중 노드 그리드 뷰)

**기능 세부사항**:
- 노드가 2개 이상일 때만 필터 드롭다운 표시
- 단일 노드 선택 시 전체 화면 활용하여 로그 가독성 향상
- 필터 상태는 모달 내부에서 관리 (모달 닫으면 초기화)

**사용 방법**:
1. 실행 로그 패널에서 "전체 상세보기" 클릭
2. 헤더의 드롭다운에서 특정 노드 선택
3. 선택한 노드의 로그만 전체 화면으로 표시됨

---

## 보안 수정 이력

### [2025-11-05] Critical 보안 취약점 2개 수정

#### BUG-002: Path Traversal (CWE-22)

**수정 파일**: `src/presentation/web/routers/filesystem.py`

**문제**: `is_safe_path()` 함수가 정의되어 있으나 `browse_directory()`에서 호출되지 않음

**해결**:
```python
# Before
@router.get("/browse")
async def browse_directory(path: Optional[str] = None):
    target_path = Path(path).resolve()  # 검증 없음
    # ...

# After
@router.get("/browse")
async def browse_directory(path: Optional[str] = None):
    target_path = Path(path).resolve()
    if not is_safe_path(Path.home(), target_path):  # 검증 추가
        raise HTTPException(403, "접근 권한이 없는 경로입니다")
```

#### BUG-003: Remote Code Execution (CWE-94)

**수정 파일**: `src/presentation/web/services/workflow_condition_evaluator.py`

**문제**: Condition 노드의 "custom" 타입에서 `eval()` 직접 사용

**해결**:
- `eval()` 제거
- AST 기반 화이트리스트 파싱 구현 (`_is_safe_ast_node()`)
- 허용 함수: `len`, `str`, `int`, `float`, `bool`, `abs`, `min`, `max`, `sum`, `round`, `pow`
- 차단: 속성 접근, 메서드 호출, 위험한 함수 호출

**마이그레이션**: 자세한 내용은 [SECURITY.md](SECURITY.md#bug-003-remote-code-execution-rce-via-eval-cwe-94)를 참조

**테스트 결과**: ✅ 11/11 통과
- Path Traversal 방어: 4/4 통과
- RCE 방지: 7/7 통과

자세한 내용은 [SECURITY.md](SECURITY.md)와 [CHANGELOG.md](CHANGELOG.md)를 참조하세요.

---

## 최근 개선사항 (v4.0.1)

### [2025-11-05] 자동 출력 추출 기능 추가 + 프롬프트 개선

**배경**:
- Worker가 전체 보고서를 출력하면 다음 노드가 불필요한 내용까지 받는 문제
- 프롬프트에 마커가 언급되어 있었으나 "선택 사항"으로 설명됨
- Worker가 보고서를 파일로만 저장하고 텍스트 출력을 하지 않아 SDK 출력에 마커가 없음

**개선 사항**:

1. **백엔드: 자동 마커 감지 로직 추가**
   - `workflow_utils.py:extract_text_with_strategy()` 자동 마커 감지 구현
   - 프롬프트가 표준 마커(`---NEXT_WORKER_OUTPUT_START/END---`)를 사용하면 자동으로 마커 사이 텍스트만 추출
   - 사용자 지정 마커(UI 설정)가 자동 마커보다 우선 적용

2. **프롬프트: 출력 형식 필수화**
   - 마커 사용을 "선택 사항"에서 **"필수 조치"**로 변경
   - "작업 완료 시 필수 조치"를 두 부분으로 분리:
     - **1. 상세 작업 보고서** (파일로 저장)
     - **2. 다음 워커를 위한 요약** (마커로 감싸서 텍스트로 출력)
   - "올바른 예시"와 "잘못된 예시" 추가
   - **중요**: 요약은 파일 저장이 아닌 **대화 응답으로 직접 출력**해야 SDK 출력에 포함됨

3. **적용 프롬프트**:
   - ✅ **전체 46개 프롬프트 수정 완료** (100%)
   - 스킵: `_simple.txt` 파일 22개 (간단 버전), `local.txt` 1개 (범용 워커)
   - 상세 목록: `PROMPT_UPDATE_REPORT.md` 참조

**우선순위**:
1. 사용자 지정 `OutputExtractionConfig` (명시적 설정)
2. 자동 마커 감지 (표준 마커 존재 시)
3. 기본 전략 (full - 전체 텍스트 반환)

**코드 개선**:
- `_extract_all_text_blocks()` 헬퍼 함수 추가 (코드 중복 제거)
- `extract_text_from_worker_output()` 리팩토링
- `last_block` 전략 개선 (헬퍼 함수 재사용)

**영향**:
- ✅ Zero-configuration: 설정 없이 자동으로 핵심 출력만 추출
- ✅ 프롬프트 호환성: 기존 47개 프롬프트와 완벽 호환
- ✅ 유연성 유지: 사용자가 원하면 여전히 커스텀 마커 사용 가능
- ✅ 컨텍스트 절감: 불필요한 보고서 내용이 다음 노드로 전달되지 않음

**테스트 결과**: ✅ 4/4 통과
- 자동 마커 감지 (표준 마커 사용 시)
- 마커 없을 때 전체 텍스트 반환
- 사용자 지정 마커 우선 적용
- last_block 전략 검증

---

### [2025-11-05] workflow_designer 프롬프트 출력 형식 정리

**배경**:
- workflow_designer는 사용자 UI로 직접 JSON을 반환하는 특수 노드
- 다른 Worker들과 달리 다음 노드로 전달되지 않음
- 그러나 일반 Worker용 "작업 완료 시 필수 조치" 섹션이 포함되어 있어 혼란 발생

**문제점**:
1. JSON 출력과 마커 출력 지침이 충돌
2. 역할(UI로 반환)과 출력 형식(마커 사용) 불일치
3. 불필요한 69줄의 마커 출력 지침 포함

**개선 사항**:
- "작업 완료 시 필수 조치" 섹션 삭제 (69줄)
- "출력 규칙" 섹션으로 대체 (11줄):
  - UI로 직접 반환됨을 명시
  - 마커 출력 불필요함을 명확히 설명
  - JSON 형식만 출력하도록 간결화

**영향**:
- ✅ 역할과 출력 형식 일치
- ✅ 프롬프트 명확성 향상
- ✅ 불필요한 지침 제거로 58줄 단축
- ✅ workflow_designer 사용 시 혼란 방지

**수정 파일**:
- `prompts/workflow_designer.txt` (962-1030줄 → 962-972줄)

---

### [2025-11-05] 커스텀 워커 캐시 무효화 개선

**배경**:
- 커스텀 워커는 이미 완벽히 구현되어 있었음
- `WorkflowExecutor`가 프로젝트별로 캐싱되어 메모리에 유지됨
- 커스텀 워커 저장 후에도 기존 캐시가 유지되어 **새 워커가 즉시 반영되지 않음**

**문제 시나리오**:
1. 사용자가 커스텀 워커 생성 및 저장
2. `/api/agents` API는 최신 커스텀 워커 목록 반환 ✅
3. Worker 노드 설정 패널에서 새 커스텀 워커 선택 가능 ✅
4. 워크플로우 실행 시 "Agent를 찾을 수 없습니다" 에러 ❌
   - **이유**: `WorkflowExecutor`가 캐시되어 있어 이전 상태 유지

**해결 방법**:

1. **캐시 무효화 함수 추가** (`dependencies.py`):
   ```python
   def clear_executor_cache(project_path: str | None = None) -> None:
       """
       WorkflowExecutor 캐시 무효화

       커스텀 워커 저장/삭제 후 호출하여 최신 상태를 반영합니다.
       """
       if project_path is None:
           _executors.clear()  # 전체 무효화
       else:
           cache_key = project_path or "~default"
           if cache_key in _executors:
               del _executors[cache_key]  # 특정 프로젝트만 무효화
   ```

2. **커스텀 워커 저장 시 캐시 무효화** (`custom_workers.py:save_custom_worker()`):
   ```python
   # 커스텀 워커 저장
   prompt_path = repository.save_custom_worker(...)

   # WorkflowExecutor 캐시 무효화
   from src.presentation.web.routers.workflows.dependencies import clear_executor_cache
   clear_executor_cache(str(project_path))
   ```

3. **커스텀 워커 삭제 시 캐시 무효화** (`custom_workers.py:delete_custom_worker()`):
   ```python
   # 커스텀 워커 삭제
   success = repository.delete_custom_worker(worker_name)

   # WorkflowExecutor 캐시 무효화
   from src.presentation.web.routers.workflows.dependencies import clear_executor_cache
   clear_executor_cache(project_path)
   ```

**영향**:
- ✅ 커스텀 워커 저장/삭제 후 즉시 반영
- ✅ 워크플로우 실행 시 최신 커스텀 워커 인식
- ✅ 기존 노드와 완벽히 소통 가능
- ✅ 프로젝트별 캐시 관리로 성능 유지

**테스트 시나리오**:
1. 커스텀 워커 생성 및 저장
2. Worker 노드 설정 패널에서 새 커스텀 워커 선택
3. 워크플로우 실행 → 정상 작동 확인
4. 커스텀 워커 삭제
5. Worker 노드 설정 패널에서 삭제된 워커 미표시 확인

**수정 파일**:
- `src/presentation/web/routers/workflows/dependencies.py` (캐시 무효화 함수 추가)
- `src/presentation/web/routers/custom_workers.py` (저장/삭제 시 캐시 무효화 호출)

---

## 향후 개선 사항

- **Application Layer**: 비즈니스 로직을 Presentation에서 분리하여 Application Layer로 이동
- **테스트**: 단위 테스트 및 통합 테스트 추가 (pytest)
- **타입 힌팅**: 점진적으로 `disallow_untyped_defs: true`로 전환
- **문서화**: `docs/` 디렉토리에 API 문서 및 사용자 가이드 추가
- **보안**: AST 화이트리스트를 설정 파일로 분리하여 확장 가능하도록 개선
