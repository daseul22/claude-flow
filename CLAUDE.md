# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 프로젝트 개요

**Claude Flow**는 Claude Agent SDK 기반의 워크플로우 자동화 시스템입니다. 비주얼 노드 에디터를 통해 여러 Worker Agent를 조율하여 복잡한 소프트웨어 개발 작업을 자동화합니다.

- **핵심 아키텍처**: Clean Architecture (Domain → Application → Infrastructure → Presentation)
- **기술 스택**: Python 3.10+, FastAPI, React (TypeScript), Claude Agent SDK
- **주요 기능**: 드래그 앤 드롭 워크플로우 에디터, Worker Agent 오케스트레이션, 실시간 실행 모니터링

---

## 필수 명령어

### 설치 및 설정

```bash
# 전체 설치 (권장)
./setup.sh

# Python 의존성만 설치
pip install -r requirements.txt

# 개발 도구 포함 설치
pip install -e ".[dev]"

# 프론트엔드 설치 및 빌드
cd src/presentation/web/frontend
npm install
npm run build
```

### 개발 명령어

```bash
# 웹 서버 실행 (프로덕션)
claude-flow-web
# 또는
python -m src.presentation.web.app

# 프론트엔드 개발 서버 (hot reload)
cd src/presentation/web/frontend
npm run dev  # http://localhost:5173

# 백엔드만 실행 (FastAPI)
uvicorn src.presentation.web.app:app --reload --host 127.0.0.1 --port 8000
```

### 코드 품질 검사

```bash
# 코드 포맷팅
black src/ --line-length 100

# 린팅
ruff check src/

# 타입 체크 (선택사항)
mypy src/
```

---

## 아키텍처 핵심 개념

### 1. Clean Architecture 레이어

```
presentation/    # FastAPI 라우터, React 프론트엔드
    └─ web/
        ├─ routers/       # API 엔드포인트 (agents, workflows, templates 등)
        ├─ services/      # 비즈니스 로직 (WorkflowExecutor, TemplateManager)
        └─ frontend/      # React + ReactFlow 캔버스

infrastructure/  # 외부 시스템 연동
    ├─ claude/        # Claude Agent SDK 래퍼 (SDKExecutor, WorkerAgent)
    ├─ config/        # 설정 로더 (JSON, YAML, 환경변수)
    └─ logging/       # 구조화된 로깅 (structlog)

domain/          # 비즈니스 엔티티
    └─ models/        # AgentConfig, Message, Workflow 등

application/     # 유스케이스 (현재 비어있음 - Presentation에서 직접 처리)
```

### 2. 워크플로우 실행 엔진 (`workflow_executor.py`)

워크플로우는 **비순환 방향 그래프 (DAG)**로 표현되며, 다음 노드 타입을 지원합니다:

- **Input Node**: 사용자 입력 (워크플로우 시작점)
- **Worker Node**: Claude Agent SDK 기반 워커 (Planner, Coder, Reviewer, Tester, Committer 등)
- **Condition Node**: 조건 분기 (if-else 로직)
- **Merge Node**: 여러 경로 병합

**핵심 실행 로직**:
1. 토폴로지 정렬로 실행 순서 결정
2. 각 노드를 순차 실행하며 `context` 딕셔너리로 데이터 전달
3. SSE (Server-Sent Events)로 프론트엔드에 실시간 스트리밍
4. 각 노드 실행 후 `node_start`, `node_progress`, `node_complete` 이벤트 발생

### 3. Agent SDK 통합 (`sdk_executor.py`, `worker_client.py`)

- **SDKExecutor**: Template Method Pattern으로 중복 코드 제거
  - `_setup_options()`: 각 워커별 도구 권한 설정
  - `_execute_with_sdk()`: SDK 클라이언트 실행 및 메시지 스트리밍
  - 에러 핸들링: `CLINotFoundError`, `ProcessError`, `CLIJSONDecodeError`

- **WorkerAgent**: 각 워커별 시스템 프롬프트 및 도구 설정
  - Planner: 요구사항 분석 (Read, Grep, Bash)
  - Coder: 코드 작성 (Read, Write, Edit, Bash)
  - Reviewer: 코드 리뷰 (Read, Grep)
  - Tester: 테스트 실행 (Read, Write, Bash)
  - Committer: Git 커밋 생성 (Bash)

### 4. 템플릿 시스템 (`template_manager.py`)

- **내장 템플릿** (`templates/`): code_review, test_automation, bug_fix, ideation
- **사용자 템플릿** (`user_templates/`): 사용자가 저장한 워크플로우
- 템플릿 검증: 필수 필드, 노드 연결 유효성, 템플릿 변수 ({{input}}, {{node_X}})

---

## 중요한 설정 파일

### `.env` (필수!)

반드시 `.env.example`을 복사하여 `.env` 파일 생성:

```bash
cp .env.example .env
```

필수 환경변수:
- `CLAUDE_CODE_OAUTH_TOKEN`: Claude Code OAuth 토큰 (필수!)
- `CLAUDE_CLI_PATH`: `claude` CLI 실행 파일 절대 경로 (예: `/usr/local/bin/claude`)
- `WORKER_TIMEOUT_*`: 각 워커별 타임아웃 (초 단위)
- `LOG_LEVEL`: 로그 레벨 (DEBUG, INFO, WARNING, ERROR)

### `pyproject.toml`

- 패키지 메타데이터 및 빌드 설정
- CLI 엔트리포인트: `claude-flow-web` → `src.presentation.web.app:main`

---

## 코딩 규칙

### Python 스타일

- **포맷터**: Black (line length 100)
- **린터**: Ruff
- **타입 힌트**: 모든 함수에 타입 힌트 필수
- **Docstring**: Google 스타일 (매개변수, 반환값, 예외 명시)
- **로깅**: `structlog` 사용 (`get_logger(__name__)`)

### 프론트엔드 (React/TypeScript)

- **상태 관리**: Zustand (`workflowStore.ts`)
- **UI 컴포넌트**: Radix UI + Tailwind CSS
- **그래프 렌더링**: ReactFlow
- **빌드 도구**: Vite

### 네이밍 컨벤션

- **Python**: snake_case (함수, 변수), PascalCase (클래스)
- **TypeScript**: camelCase (함수, 변수), PascalCase (컴포넌트, 타입)

---

## 주요 워크플로우 패턴

### 새로운 Worker Agent 추가

1. `src/domain/models/agent.py`에 `AgentConfig` 추가
2. `src/infrastructure/claude/worker_client.py`에 `WorkerAgent` 하위 클래스 생성
3. `src/presentation/web/routers/agents.py`에 라우터 등록
4. 프론트엔드: `frontend/src/components/` 에 커스텀 노드 추가

### 새로운 노드 타입 추가

1. `src/presentation/web/schemas/workflow.py`에 노드 데이터 클래스 정의
2. `src/presentation/web/services/workflow_executor.py`의 `_execute_node()` 로직 확장
3. 프론트엔드: `frontend/src/components/` 에 React 컴포넌트 추가
4. `frontend/src/stores/workflowStore.ts`에 노드 타입 등록

### 워크플로우 실행 디버깅

- 세션별 로그 파일: `logs/workflow_{session_id}.log`
- 백엔드 로그: `logs/app.log` (JSON 형식)
- 프론트엔드 콘솔: SSE 이벤트 디버깅용

---

## 문서 업데이트 정책

**중요**: 기능 추가, 수정, 또는 제거 시 반드시 관련 문서를 함께 업데이트해야 합니다.

### 업데이트 대상 문서

1. **[`docs/feature-specification.md`](docs/feature-specification.md)** (필수!)
   - **언제**: 사용자 관점 기능이 변경될 때마다
   - **내용**:
     - 새 기능 추가 시: 해당 섹션에 User Story 형태로 기능 설명 추가
     - 기능 수정 시: 변경된 동작, UI, 제약사항 반영
     - 기능 삭제 시: 해당 항목 제거 또는 "(지원 중단)" 표시
   - **예시**:
     - Worker 추가 → "3. 워커(Worker) 관리" 섹션 업데이트
     - 노드 타입 추가 → "2.2 노드 추가 및 배치" 섹션 업데이트
     - 세션 저장 방식 변경 → "7.2 세션 뷰어", "기술 제약사항" 섹션 업데이트

2. **`CLAUDE.md`** (이 파일)
   - **언제**: 아키텍처, 개발 패턴, 설정 파일이 변경될 때
   - **내용**:
     - "아키텍처 핵심 개념" (레이어 구조 변경, 새 컴포넌트 추가)
     - "코딩 규칙" (새 린터/포맷터 추가, 네이밍 규칙 변경)
     - "주요 워크플로우 패턴" (새 개발 패턴 추가)
     - "알려진 제약사항" (제약사항 추가/해결)
     - "최근 주요 변경사항" (날짜별 변경 기록)

3. **`README.md`**
   - **언제**: 프로젝트 소개, 설치 방법, 빠른 시작 가이드가 변경될 때
   - **내용**: 외부 사용자를 위한 고수준 개요

### 업데이트 체크리스트

기능 변경 시 다음을 확인하세요:

- [ ] `docs/feature-specification.md`에 사용자 관점 설명 추가/수정
- [ ] `CLAUDE.md`에 개발자 관점 기술 정보 추가/수정 (필요시)
- [ ] 관련 코드에 주석 및 Docstring 업데이트
- [ ] 테스트 코드 작성 또는 업데이트
- [ ] 커밋 메시지에 문서 변경사항 명시 (`docs:` prefix)

**예시 커밋**:
```bash
git commit -m "feat: Worker 세션 저장소를 파일 기반으로 변경

- WorkflowSessionStore 구현 (메모리 캐싱 + 파일 영속성)
- 서버 재시작 후에도 세션 복원 가능
- docs: feature-specification.md 세션 지속성 섹션 업데이트
"
```

### 문서 일관성 검증

문서 업데이트 후 다음을 확인하세요:

1. **모순 없는지**: 여러 문서에서 같은 기능을 다르게 설명하지 않았는지
2. **용어 통일**: "세션 복원" vs "세션 재연결" 등 용어가 일관적인지
3. **링크 유효성**: 문서 간 링크가 깨지지 않았는지
4. **날짜 최신화**: "작성일", "최근 주요 변경사항" 갱신

---

## 알려진 제약사항

1. **동시 워크플로우 실행 제한**: 현재 단일 세션만 지원 (향후 개선 예정)
2. **Worker 간 상태 공유 불가**: 각 워커는 독립적으로 실행되며, context를 통해서만 데이터 전달
3. **프론트엔드 빌드 필수**: 프로덕션 실행 시 `npm run build` 필수 (개발 시에는 `npm run dev` 별도 실행)

---

## 트러블슈팅

### "CLAUDE_CODE_OAUTH_TOKEN 환경변수가 설정되지 않았습니다"

→ `.env` 파일 생성 및 토큰 설정 확인

### "React 빌드 필요" 오류

→ `cd src/presentation/web/frontend && npm run build`

### Worker 실행 시 타임아웃

→ `.env`에서 `WORKER_TIMEOUT_*` 값 증가

### "Module not found" 오류

→ `pip install -e .` (editable mode) 또는 `pip install .`

### 프론트엔드 hot reload 작동하지 않음

→ 개발 시 프론트엔드와 백엔드를 별도 실행:
```bash
# 터미널 1
uvicorn src.presentation.web.app:app --reload --port 8000

# 터미널 2
cd src/presentation/web/frontend && npm run dev
```

---

## 참고 문서

- **프로젝트 루트**: `README.md` (프로젝트 개요)
- **기능 명세서**: [`docs/feature-specification.md`](docs/feature-specification.md) (사용자 스토리 기반 기능 문서)
- **기능 개발 계획**: `docs/feature-plan.md` (완료/진행 중인 기능)
- **SDK 레퍼런스**: `claude-agent-sdk-features.md` (Claude Agent SDK 전체 가이드)
- **환경변수 예시**: `.env.example`
- **API 문서**: http://localhost:8000/docs (FastAPI Swagger)

---

## 최근 주요 변경사항

- **2025-11-04**: 🎉🎉🎉 리팩토링 Phase 1+2+3 완료 - 전체 코드베이스 대규모 리팩토링
  - **Phase 1 (WorkflowExecutor)**: 1655줄 → 569줄 (65.6% 감소)
    - WorkflowGraphManager: 그래프 관리 로직 분리
    - WorkflowNodeExecutor: 노드 실행 로직 통합
    - WorkflowConditionEvaluator: Condition/Merge 노드 로직 분리
    - WorkflowTemplateRenderer: 템플릿 변수 치환 로직 분리
  - **Phase 2 (Router 분할)**: 대형 라우터 파일 → 패키지 구조
    - workflows.py (1508줄) → workflows/ 패키지 (dependencies, core, execution, design, __init__)
    - projects.py (1432줄) → projects/ 패키지 (dependencies, core, logs, sessions, __init__)
  - **Phase 3 (메서드 최적화)**: 대형 메서드 → 헬퍼 메서드 분리
    - WorkflowNodeExecutor._execute_worker_node: 256줄 → 194줄 (24% 감소)
    - 4개 헬퍼 메서드 추가: _parse_worker_node_data, _prepare_worker_agent_config, _render_worker_task, _save_worker_node_session
  - **결과**: 코드 가독성, 유지보수성, 테스트 용이성 대폭 향상, Clean Architecture 원칙 준수
- **2025-10-31**: 프로젝트 정리 및 미사용 코드 대량 제거
- **2025-10-30**: 로그 표시 레이아웃 개선 및 세션 로그 자동 복원
- **2025-10-29**: 추가 프롬프트 기능 버그 수정 (세션 저장 및 SDK session_id 추출)

최신 변경사항은 `git log --oneline -10` 으로 확인하세요.
