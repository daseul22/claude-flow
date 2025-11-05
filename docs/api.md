# Claude Flow API 문서

**버전**: 4.0.1
**기본 URL**: `http://localhost:5173/api`
**프로토콜**: HTTP/REST (일부는 Server-Sent Events)

---

## 📚 관련 문서

- **[문서 INDEX](INDEX.md)** - 모든 문서의 전체 목록
- **[프로젝트 README](../README.md)** - 프로젝트 개요 및 빠른 시작
- **[아키텍처](architecture.md)** - 시스템 설계 및 컴포넌트
- **[코드 레퍼런스](code-reference.md)** - 핵심 클래스 및 함수
- **[OpenAPI 스펙](openapi.yaml)** - 기계 가독형 API 정의 (Swagger/Postman)

---

## 📋 목차

1. [개요](#개요)
2. [인증 및 권한](#인증-및-권한)
3. [공통 응답 형식](#공통-응답-형식)
4. [엔드포인트](#엔드포인트)
   - [워크플로우 실행](#워크플로우-실행)
   - [워크플로우 관리](#워크플로우-관리)
   - [워크플로우 설계](#워크플로우-설계)
   - [에이전트](#에이전트)
   - [템플릿](#템플릿)
   - [커스텀 워커](#커스텀-워커)
   - [프로젝트](#프로젝트)
   - [로그](#로그)
   - [파일 시스템](#파일-시스템)
   - [헬스 체크](#헬스-체크)
5. [에러 처리](#에러-처리)
6. [사용 예제](#사용-예제)

---

## 개요

Claude Flow는 **그룹 챗 오케스트레이션 시스템**으로, 여러 AI 에이전트(Worker)를 조율하여 복잡한 소프트웨어 개발 작업을 자동화합니다.

### 핵심 개념

- **워크플로우 (Workflow)**: Input → Worker → Condition → Merge 노드로 구성된 DAG (Directed Acyclic Graph)
- **노드 (Node)**: 워크플로우의 단위 작업 (Input, Worker, Condition, Merge)
- **세션 (Session)**: 워크플로우 실행 컨텍스트 (상태, 로그, 노드 출력 저장)
- **Worker**: Claude Agent SDK를 사용한 AI 에이전트 (코딩, 코드리뷰, 테스트 등)
- **템플릿**: 재사용 가능한 워크플로우 패턴

### 기본 흐름

```
사용자 요청
    ↓
[POST /api/workflows/execute] SSE 스트리밍 시작
    ↓
백그라운드 워크플로우 실행
    ├─ 위상 정렬 및 실행 그룹 계산
    ├─ 병렬 노드 실행 (가능한 경우)
    └─ 각 노드의 출력을 다음 노드로 전달
    ↓
클라이언트가 실시간 이벤트 수신
    ├─ node_start: 노드 시작
    ├─ node_output: 스트리밍 출력
    ├─ node_complete: 노드 완료
    └─ workflow_complete: 워크플로우 완료
```

---

## 인증 및 권한

현재 Claude Flow는 **인증 없이 실행**되지만, Claude Agent SDK 사용 시 **환경변수 `CLAUDE_CODE_OAUTH_TOKEN` 필요**:

```bash
export CLAUDE_CODE_OAUTH_TOKEN="your-token-here"
```

향후 버전에서 인증 및 권한 관리 추가 예정.

---

## 공통 응답 형식

### 성공 응답 (2xx)

```json
{
  "status": "success",
  "data": { /* 엔드포인트별 데이터 */ }
}
```

### 에러 응답 (4xx, 5xx)

```json
{
  "detail": "에러 메시지"
}
```

### SSE 응답 형식

```
data: {"event_type": "node_start", "node_id": "node-1", "data": {...}, "timestamp": "2025-11-05T..."}
data: {"event_type": "node_output", "node_id": "node-1", "data": {"chunk": "..."}, "timestamp": "..."}
data: [DONE]
```

---

## 엔드포인트

### 워크플로우 실행

#### 1. 워크플로우 실행 (SSE 스트리밍)

```
POST /api/workflows/execute
Content-Type: application/json
```

**설명**: 워크플로우를 백그라운드에서 실행하고, Server-Sent Events(SSE)로 실시간 진행 상황을 스트리밍합니다.

**요청**:

```json
{
  "workflow": {
    "id": "optional-uuid",
    "name": "코드 리뷰 워크플로우",
    "description": "코드 작성 → 리뷰 → 커밋",
    "nodes": [
      {
        "id": "input-1",
        "type": "Input",
        "label": "초기 입력",
        "data": {}
      },
      {
        "id": "worker-1",
        "type": "Worker",
        "label": "코드 리뷰",
        "data": {
          "agent_name": "code_reviewer",
          "task_template": "다음 코드를 리뷰해주세요: {{input}}"
        }
      }
    ],
    "edges": [
      {
        "id": "edge-1",
        "source": "input-1",
        "target": "worker-1"
      }
    ]
  },
  "initial_input": "def hello():\n  print('hello')",
  "session_id": "optional-session-id",
  "start_node_id": "optional-node-id",
  "last_event_index": null
}
```

**응답** (SSE 스트리밍):

```
data: {"event_type": "workflow_start", "node_id": "", "data": {"session_id": "abc-123"}, "timestamp": "2025-11-05T10:00:00Z"}

data: {"event_type": "node_start", "node_id": "input-1", "data": {"status": "running"}, "timestamp": "2025-11-05T10:00:01Z"}

data: {"event_type": "node_complete", "node_id": "input-1", "data": {"output": "def hello():\n  print('hello')"}, "timestamp": "2025-11-05T10:00:02Z"}

data: {"event_type": "node_start", "node_id": "worker-1", "data": {"status": "running"}, "timestamp": "2025-11-05T10:00:03Z"}

data: {"event_type": "node_output", "node_id": "worker-1", "data": {"chunk": "이 코드를 리뷰하겠습니다..."}, "timestamp": "2025-11-05T10:00:04Z"}

data: {"event_type": "node_output", "node_id": "worker-1", "data": {"chunk": " 함수명이 좋고"}, "timestamp": "2025-11-05T10:00:05Z"}

data: {"event_type": "node_complete", "node_id": "worker-1", "data": {"output": "이 코드를 리뷰하겠습니다... 함수명이 좋고"}, "timestamp": "2025-11-05T10:00:06Z"}

data: {"event_type": "workflow_complete", "node_id": "", "data": {"status": "success", "total_time": 6.0}, "timestamp": "2025-11-05T10:00:07Z"}

data: [DONE]
```

**이벤트 타입**:
- `workflow_start`: 워크플로우 시작
- `node_start`: 노드 시작
- `node_output`: 스트리밍 출력 청크
- `node_complete`: 노드 완료
- `workflow_complete`: 워크플로우 완료
- `workflow_error`: 워크플로우 에러
- `ask_user`: Human-in-the-Loop 사용자 입력 요청

**HTTP 상태 코드**:
- `200`: 스트리밍 시작
- `400`: 워크플로우 검증 실패
- `500`: 서버 에러

---

#### 2. 세션 조회

```
GET /api/workflows/sessions/{session_id}
```

**설명**: 이전 세션 상태를 조회하여 워크플로우 진행 상황을 복원합니다.

**응답**:

```json
{
  "session_id": "abc-123",
  "workflow": {
    "id": "wf-1",
    "name": "코드 리뷰 워크플로우",
    "nodes": [...],
    "edges": [...]
  },
  "initial_input": "코드 입력...",
  "status": "running",
  "current_node_id": "worker-1",
  "node_outputs": {
    "input-1": "코드 입력...",
    "worker-1": "리뷰 결과..."
  },
  "logs": [
    {
      "event_type": "workflow_start",
      "node_id": "",
      "data": {...},
      "timestamp": "2025-11-05T10:00:00Z"
    },
    ...
  ],
  "start_time": "2025-11-05T10:00:00Z",
  "end_time": null,
  "error": null
}
```

**HTTP 상태 코드**:
- `200`: 성공
- `404`: 세션을 찾을 수 없음
- `500`: 서버 에러

---

#### 3. 워크플로우 취소

```
POST /api/workflows/sessions/{session_id}/cancel
```

**설명**: 실행 중인 워크플로우를 중단합니다.

**응답**:

```json
{
  "message": "워크플로우가 취소되었습니다",
  "session_id": "abc-123"
}
```

**HTTP 상태 코드**:
- `200`: 성공
- `404`: 세션을 찾을 수 없음
- `500`: 서버 에러

---

#### 4. 노드의 세션 목록 조회

```
GET /api/workflows/nodes/{node_id}/sessions
```

**설명**: 특정 노드의 세션 이력을 조회하여 이전 대화를 선택할 수 있습니다.

**응답**:

```json
{
  "node_id": "worker-1",
  "agent_name": "Backend Coder",
  "current_session_id": "uuid-456",
  "session_history": [
    {
      "session_id": "uuid-456",
      "agent_name": "Backend Coder",
      "created_at": "2025-10-30T18:00:00",
      "last_used_at": "2025-10-30T18:05:00",
      "is_current": true
    },
    {
      "session_id": "uuid-789",
      "agent_name": "Backend Coder",
      "created_at": "2025-10-29T14:00:00",
      "last_used_at": "2025-10-29T14:30:00",
      "is_current": false
    }
  ]
}
```

---

#### 5. 노드에 추가 프롬프트 전송 (주도적 대화)

```
POST /api/workflows/nodes/{node_id}/continue
Content-Type: application/json
```

**설명**: 로그 상세 모달에서 추가 질문/지시를 입력할 때 사용합니다. 해당 노드의 이전 세션을 이어서 실행합니다.

**요청**:

```json
{
  "prompt": "테스트 코드도 작성해줘"
}
```

**응답**:

```json
{
  "message": "노드 추가 대화가 시작되었습니다",
  "node_id": "node-123",
  "session_id": "new-session-456"
}
```

**HTTP 상태 코드**:
- `200`: 성공
- `404`: 노드의 세션을 찾을 수 없음
- `500`: 서버 에러

---

#### 6. 세션 이벤트 스트리밍

```
GET /api/workflows/sessions/{session_id}/stream
```

**설명**: 추가 프롬프트 실행 결과를 실시간으로 수신합니다.

**응답** (SSE):

```
data: {"event_type": "node_output", "node_id": "node-1", "data": {...}, "timestamp": "..."}
data: {"event_type": "node_complete", "node_id": "node-1", "data": {...}, "timestamp": "..."}
data: [DONE]
```

---

#### 7. 사용자 입력 전달 (Human-in-the-Loop)

```
POST /api/workflows/sessions/{session_id}/user-input
Content-Type: application/json
```

**설명**: Worker가 `@ASK_USER:` 패턴으로 질문했을 때, 웹 UI에서 사용자 답변을 이 엔드포인트로 전송합니다.

**요청**:

```json
{
  "answer": "네, 진행해주세요"
}
```

**응답**:

```json
{
  "message": "사용자 입력이 전달되었습니다",
  "session_id": "abc-123"
}
```

---

#### 8. 세션 삭제

```
DELETE /api/workflows/sessions/{session_id}
```

**설명**: 완료된 세션을 정리합니다.

**응답**:

```json
{
  "message": "세션이 삭제되었습니다"
}
```

---

#### 9. 모든 노드 SDK 세션 초기화

```
POST /api/workflows/clear-node-sessions
```

**설명**: Claude Code SDK가 저장한 모든 세션 파일(.jsonl)을 삭제하여 각 노드의 대화 컨텍스트를 초기화합니다.

**응답**:

```json
{
  "message": "모든 노드 세션이 초기화되었습니다",
  "deleted_sessions": 824
}
```

---

### 워크플로우 관리

#### 1. 워크플로우 저장

```
POST /api/workflows
Content-Type: application/json
```

**설명**: 워크플로우를 파일에 저장합니다.

**요청**:

```json
{
  "workflow": {
    "id": "uuid-v4",
    "name": "코드 리뷰 워크플로우",
    "description": "코드 작성 → 리뷰 → 커밋",
    "nodes": [...],
    "edges": [...]
  }
}
```

**응답**:

```json
{
  "workflow_id": "uuid-v4",
  "message": "워크플로우가 저장되었습니다"
}
```

---

#### 2. 워크플로우 목록 조회

```
GET /api/workflows
```

**설명**: 저장된 모든 워크플로우의 메타데이터를 조회합니다.

**응답**:

```json
{
  "workflows": [
    {
      "id": "uuid-1",
      "name": "코드 리뷰 워크플로우",
      "description": "코드 작성 → 리뷰 → 커밋",
      "node_count": 3,
      "edge_count": 2
    },
    ...
  ]
}
```

---

#### 3. 워크플로우 조회

```
GET /api/workflows/{workflow_id}
```

**설명**: 특정 워크플로우의 전체 데이터를 조회합니다.

**응답**:

```json
{
  "id": "uuid-1",
  "name": "코드 리뷰 워크플로우",
  "description": "...",
  "nodes": [...],
  "edges": [...]
}
```

---

#### 4. 워크플로우 삭제

```
DELETE /api/workflows/{workflow_id}
```

**응답**:

```json
{
  "message": "워크플로우가 삭제되었습니다"
}
```

---

#### 5. 워크플로우 검증

```
POST /api/workflows/validate
Content-Type: application/json
```

**설명**: 실행 전 워크플로우의 유효성을 검사합니다.

**요청**:

```json
{
  "name": "test",
  "nodes": [...],
  "edges": [...]
}
```

**응답**:

```json
{
  "valid": true,
  "errors": []
}
```

또는

```json
{
  "valid": false,
  "errors": [
    {
      "severity": "error",
      "node_id": "node-1",
      "message": "순환 참조가 감지되었습니다",
      "suggestion": "노드 간 연결을 확인하여 순환 참조를 제거하세요"
    }
  ]
}
```

**검증 항목**:
- 순환 참조
- 고아 노드
- 템플릿 변수 유효성
- Worker 도구 권한
- Input 노드 존재 여부
- Manager 노드 검증

---

### 워크플로우 설계

#### 1. 워크플로우 자동 설계

```
POST /api/workflows/design
Content-Type: application/json
```

**설명**: workflow_designer Worker를 사용하여 요구사항으로부터 워크플로우를 자동 설계합니다.

**요청**:

```json
{
  "requirements": "코드 리뷰 후 테스트 실행하는 워크플로우",
  "session_id": "optional-session-id"
}
```

**응답** (SSE 스트리밍):

```
data: {생성된 워크플로우 JSON 청크 1}
data: {생성된 워크플로우 JSON 청크 2}
...
data: [DONE]
```

---

### 에이전트

#### 1. 에이전트 목록 조회

```
GET /api/agents
```

**설명**: 사용 가능한 Worker Agent 목록을 조회합니다 (기본 + 커스텀).

**응답**:

```json
{
  "agents": [
    {
      "name": "backend_coder",
      "role": "백엔드 개발",
      "description": "백엔드 개발 전문가",
      "system_prompt": "당신은 백엔드 개발 전문가입니다...",
      "allowed_tools": ["read", "write", "edit", "bash", "glob", "grep"],
      "model": "claude-sonnet-4-5-20250929",
      "is_custom": false
    },
    {
      "name": "my_custom_worker",
      "role": "커스텀 작업",
      "description": "커스텀 작업 전문가",
      "system_prompt": "...",
      "allowed_tools": ["read", "bash"],
      "model": "claude-sonnet-4-5-20250929",
      "is_custom": true
    }
  ]
}
```

**특징**:
- prompts/ 디렉토리 자동 스캔 (새 프롬프트 즉시 반영)
- 커스텀 워커 포함
- 각 에이전트의 시스템 프롬프트 포함

---

#### 2. 사용 가능한 도구 목록

```
GET /api/tools
```

**응답**:

```json
{
  "tools": [
    {
      "name": "read",
      "description": "파일 읽기",
      "category": "파일",
      "readonly": true
    },
    {
      "name": "write",
      "description": "파일 쓰기",
      "category": "파일",
      "readonly": false
    },
    {
      "name": "edit",
      "description": "파일 편집",
      "category": "파일",
      "readonly": false
    },
    {
      "name": "glob",
      "description": "파일 검색 (패턴)",
      "category": "검색",
      "readonly": true
    },
    {
      "name": "grep",
      "description": "코드 검색 (내용)",
      "category": "검색",
      "readonly": true
    },
    {
      "name": "bash",
      "description": "쉘 명령 실행",
      "category": "실행",
      "readonly": false
    }
  ]
}
```

---

#### 3. 에이전트 실행 (직접 실행)

```
POST /api/execute
Content-Type: application/json
```

**설명**: Worker Agent를 직접 실행하고 결과를 SSE로 스트리밍합니다.

**요청**:

```json
{
  "agent_name": "backend_coder",
  "task_description": "Python 함수를 작성해주세요: 두 숫자의 합을 반환하는 함수",
  "session_id": "optional-session-id"
}
```

**응답** (SSE):

```
data: {Worker 출력 청크 1}
data: {Worker 출력 청크 2}
...
data: [DONE]
```

---

### 템플릿

#### 1. 템플릿 목록 조회

```
GET /api/templates
```

**응답**:

```json
{
  "templates": [
    {
      "id": "code_review",
      "name": "코드 리뷰 워크플로우",
      "description": "계획 수립 → 코드 작성 → 코드 리뷰",
      "category": "code_review",
      "node_count": 4,
      "edge_count": 3,
      "tags": ["code-review", "planner", "coder", "reviewer"],
      "is_builtin": true,
      "created_at": "2025-10-28T00:00:00Z",
      "updated_at": "2025-10-28T00:00:00Z"
    },
    ...
  ]
}
```

---

#### 2. 템플릿 조회

```
GET /api/templates/{template_id}
```

**응답**:

```json
{
  "id": "code_review",
  "name": "코드 리뷰 워크플로우",
  "description": "계획 수립 → 코드 작성 → 코드 리뷰",
  "category": "code_review",
  "workflow": {
    "id": "code_review_workflow",
    "name": "코드 리뷰 워크플로우",
    "nodes": [...],
    "edges": [...]
  },
  "tags": ["code-review", "planner", "coder", "reviewer"],
  "is_builtin": true,
  "created_at": "2025-10-28T00:00:00Z",
  "updated_at": "2025-10-28T00:00:00Z"
}
```

---

#### 3. 템플릿 저장 (사용자 정의)

```
POST /api/templates
Content-Type: application/json
```

**요청**:

```json
{
  "name": "내 워크플로우",
  "description": "사용자 정의 워크플로우",
  "category": "custom",
  "workflow": {
    "name": "내 워크플로우",
    "nodes": [...],
    "edges": [...]
  },
  "tags": ["custom"]
}
```

**응답**:

```json
{
  "template_id": "abc123",
  "message": "템플릿 저장 완료"
}
```

---

#### 4. 템플릿 삭제

```
DELETE /api/templates/{template_id}
```

**설명**: 내장 템플릿은 삭제 불가합니다.

**응답**:

```json
{
  "message": "템플릿 삭제 완료",
  "template_id": "abc123"
}
```

---

#### 5. 템플릿 검증

```
POST /api/templates/validate
Content-Type: application/json
```

**요청**:

```json
{
  "nodes": [...],
  "edges": [...]
}
```

**응답**:

```json
{
  "valid": true,
  "errors": []
}
```

---

### 커스텀 워커

#### 1. 커스텀 워커 프롬프트 생성

```
POST /api/custom-workers/generate
Content-Type: application/json
```

**설명**: worker_prompt_engineer를 실행하여 커스텀 워커 프롬프트를 생성합니다.

**요청**:

```json
{
  "worker_requirements": "데이터 분석 및 시각화를 수행하는 워커",
  "session_id": "optional-session-id"
}
```

**응답** (SSE):

```
data: {생성된 프롬프트 청크 1}
data: {생성된 프롬프트 청크 2}
...
data: [DONE]
```

---

#### 2. 커스텀 워커 저장

```
POST /api/custom-workers/save
Content-Type: application/json
```

**요청**:

```json
{
  "project_path": "/path/to/project",
  "worker_name": "data_analyzer",
  "role": "데이터 분석",
  "prompt_content": "# 당신은 데이터 분석 전문가입니다...",
  "allowed_tools": ["read", "bash", "glob"],
  "model": "claude-sonnet-4-5-20250929",
  "thinking": false
}
```

**응답**:

```json
{
  "success": true,
  "message": "커스텀 워커 'data_analyzer' 저장 완료",
  "prompt_path": "/path/to/project/.claude-flow/worker/data_analyzer.txt"
}
```

---

#### 3. 커스텀 워커 목록 조회

```
GET /api/custom-workers?project_path=/path/to/project
```

**응답**:

```json
{
  "workers": [
    {
      "name": "data_analyzer",
      "role": "데이터 분석",
      "allowed_tools": ["read", "bash", "glob"],
      "model": "claude-sonnet-4-5-20250929",
      "thinking": false,
      "prompt_preview": "# 당신은 데이터 분석 전문가입니다..."
    }
  ]
}
```

---

#### 4. 커스텀 워커 삭제

```
DELETE /api/custom-workers/{worker_name}?project_path=/path/to/project
```

**응답**:

```json
{
  "success": true,
  "message": "커스텀 워커 'data_analyzer' 삭제 완료"
}
```

---

### 프로젝트

#### 1. 프로젝트 선택

```
POST /api/projects/select
Content-Type: application/json
```

**요청**:

```json
{
  "project_path": "/path/to/project"
}
```

**응답**:

```json
{
  "project_path": "/path/to/project",
  "message": "프로젝트가 선택되었습니다",
  "has_existing_config": true
}
```

---

#### 2. 현재 프로젝트 정보 조회

```
GET /api/projects/current
```

**응답**:

```json
{
  "project_path": "/path/to/project",
  "has_existing_config": true
}
```

---

#### 3. 워크플로우 목록 조회 (프로젝트별)

```
GET /api/projects/workflows/list
```

**응답**:

```json
{
  "workflows": [
    {
      "name": "code-review",
      "display_name": "코드 리뷰",
      "description": "코드 리뷰 워크플로우",
      "last_modified": "2025-11-05T10:00:00Z",
      "size": 2048
    },
    ...
  ]
}
```

---

#### 4. Display 설정 로드

```
GET /api/projects/display-config
```

**응답**:

```json
{
  "has_config": true,
  "config": {
    "layout_config": {...},
    "canvas_state": {...}
  }
}
```

---

#### 5. Display 설정 저장

```
POST /api/projects/display-config
Content-Type: application/json
```

**요청**:

```json
{
  "config": {
    "layout_config": {...},
    "canvas_state": {...}
  }
}
```

**응답**:

```json
{
  "message": "Display 설정이 저장되었습니다"
}
```

---

#### 6. 워크플로우 저장 (프로젝트별)

```
POST /api/projects/workflows/{workflow_name}
Content-Type: application/json
```

**요청**:

```json
{
  "workflow": {
    "name": "코드 리뷰",
    "nodes": [...],
    "edges": [...]
  }
}
```

**응답**:

```json
{
  "message": "워크플로우가 저장되었습니다",
  "workflow_name": "code-review",
  "config_path": "/path/to/.claude-flow/workflows/code-review.json"
}
```

---

#### 7. 워크플로우 로드 (프로젝트별)

```
GET /api/projects/workflows/{workflow_name}
```

**응답**:

```json
{
  "project_path": "/path/to/project",
  "workflow": {
    "name": "코드 리뷰",
    "nodes": [...],
    "edges": [...]
  },
  "last_modified": "2025-11-05T10:00:00Z"
}
```

---

#### 8. 워크플로우 삭제 (프로젝트별)

```
DELETE /api/projects/workflows/{workflow_name}
```

**응답**:

```json
{
  "message": "워크플로우가 삭제되었습니다",
  "workflow_name": "code-review"
}
```

---

#### 9. 워크플로우 이름 변경

```
PUT /api/projects/workflows/{old_name}/rename?new_name=new_name
```

**응답**:

```json
{
  "message": "워크플로우 이름이 변경되었습니다",
  "old_name": "code-review",
  "new_name": "code-review-v2"
}
```

---

### 로그

#### 1. 로그 파일 목록 조회

```
GET /api/projects/logs/list
```

**응답**:

```json
{
  "logs": [
    {
      "path": "session-abc/debug.log",
      "name": "debug.log",
      "size": 1024,
      "modified": "2025-11-05T10:00:00Z",
      "type": "session"
    },
    ...
  ],
  "total_count": 10,
  "total_size": 10240
}
```

---

#### 2. 로그 파일 내용 조회

```
GET /api/projects/logs/content?file_path=session-abc/debug.log&max_lines=1000
```

**응답**:

```json
{
  "content": "[2025-11-05 10:00:00] INFO: 워크플로우 시작...\n[2025-11-05 10:00:01] DEBUG: 노드 1 실행...",
  "file_info": {
    "path": "session-abc/debug.log",
    "name": "debug.log",
    "size": 1024,
    "modified": "2025-11-05T10:00:00Z",
    "type": "session"
  }
}
```

---

#### 3. 로그 파일 비우기

```
DELETE /api/projects/logs
```

**응답**:

```json
{
  "message": "로그 파일이 삭제되었습니다",
  "deleted_files": 50,
  "freed_space_mb": 12.34
}
```

---

### 파일 시스템

#### 1. 홈 디렉토리 조회

```
GET /api/filesystem/home
```

**응답**:

```json
{
  "home_path": "/Users/username"
}
```

---

#### 2. 디렉토리 브라우징

```
GET /api/filesystem/browse?path=/Users/username/projects
```

**응답**:

```json
{
  "current_path": "/Users/username/projects",
  "parent_path": "/Users/username",
  "entries": [
    {
      "name": "my-project",
      "path": "/Users/username/projects/my-project",
      "is_directory": true,
      "is_readable": true
    },
    {
      "name": "README.md",
      "path": "/Users/username/projects/README.md",
      "is_directory": false,
      "is_readable": true
    }
  ]
}
```

**특징**:
- 숨김 파일 (.으로 시작) 제외 (.claude-flow 제외)
- 버전 관리 폴더 (node_modules, venv, __pycache__ 등) 제외
- 디렉토리 먼저, 이름순 정렬
- Path Traversal 방어 (홈 디렉토리 밖 접근 차단)

---

### 헬스 체크

#### 1. 서비스 상태 확인

```
GET /health
```

**응답**:

```json
{
  "status": "ok",
  "message": "Service is running"
}
```

---

## 에러 처리

### 에러 응답 형식

```json
{
  "detail": "에러 메시지"
}
```

### 일반적인 에러 코드

| 코드 | 설명 | 예시 메시지 |
|------|------|-----------|
| 400 | 잘못된 요청 | "워크플로우에 노드가 없습니다" |
| 404 | 리소스 없음 | "워크플로우를 찾을 수 없습니다" |
| 500 | 서버 에러 | "워크플로우 실행 실패: 내부 에러" |

### 워크플로우 검증 에러

```json
{
  "valid": false,
  "errors": [
    {
      "severity": "error",
      "node_id": "node-1",
      "message": "순환 참조가 감지되었습니다",
      "suggestion": "노드 간 연결을 확인하여 순환 참조를 제거하세요"
    }
  ]
}
```

### 워크플로우 실행 에러

SSE 스트림에서 에러 수신:

```
data: {"event_type": "workflow_error", "node_id": "", "data": {"error": "Worker 실행 실패: ..."}, "timestamp": "..."}
data: [DONE]
```

---

## 사용 예제

### 예제 1: 간단한 워크플로우 실행 (curl)

```bash
curl -X POST http://localhost:5173/api/workflows/execute \
  -H "Content-Type: application/json" \
  -d '{
    "workflow": {
      "name": "코드 리뷰",
      "nodes": [
        {
          "id": "input-1",
          "type": "Input",
          "label": "입력",
          "data": {}
        },
        {
          "id": "worker-1",
          "type": "Worker",
          "label": "리뷰",
          "data": {
            "agent_name": "code_reviewer",
            "task_template": "{{input}} 리뷰해주세요"
          }
        }
      ],
      "edges": [
        {
          "id": "edge-1",
          "source": "input-1",
          "target": "worker-1"
        }
      ]
    },
    "initial_input": "def hello(): print(\"hello\")"
  }' \
  --no-buffer
```

### 예제 2: JavaScript에서 SSE 수신

```javascript
const eventSource = new EventSource(
  'http://localhost:5173/api/workflows/execute'
);

eventSource.onmessage = (event) => {
  if (event.data === '[DONE]') {
    eventSource.close();
    console.log('워크플로우 완료');
  } else {
    const data = JSON.parse(event.data);
    console.log(`[${data.event_type}] ${data.node_id}: `, data.data);
  }
};

eventSource.onerror = (error) => {
  console.error('SSE 에러:', error);
  eventSource.close();
};
```

### 예제 3: Python에서 워크플로우 실행

```python
import requests
import json

# 워크플로우 실행 요청
response = requests.post(
    'http://localhost:5173/api/workflows/execute',
    json={
        'workflow': {
            'name': '코드 리뷰',
            'nodes': [...],
            'edges': [...]
        },
        'initial_input': 'def hello(): print("hello")'
    },
    stream=True
)

# SSE 스트림 처리
for line in response.iter_lines():
    if line:
        data = json.loads(line.decode('utf-8').replace('data: ', ''))
        if data == '[DONE]':
            break
        print(f"[{data['event_type']}] {data['node_id']}: {data['data']}")
```

### 예제 4: 에이전트 직접 실행

```bash
curl -X POST http://localhost:5173/api/execute \
  -H "Content-Type: application/json" \
  -d '{
    "agent_name": "backend_coder",
    "task_description": "Python 함수 작성: 피보나치 수열 생성",
    "session_id": "optional-session-id"
  }' \
  --no-buffer
```

---

## 추가 정보

- **공식 문서**: [CLAUDE.md](../CLAUDE.md)
- **개발자 가이드**: [아키텍처 문서](./architecture.md) (준비 중)
- **튜토리얼**: [사용자 가이드](./tutorial.md) (준비 중)

---

**마지막 수정**: 2025-11-05
**버전**: 4.0.1
**상태**: 초안 작성 완료
