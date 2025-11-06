# 📊 데이터 흐름 상세 가이드

> **중요**: 이 문서는 Claude Flow Web 시스템의 모든 데이터 흐름을 정의합니다.
> 코드 수정, 버그 수정, 기능 추가 시 **반드시 참조**하여 데이터 흐름을 정확히 이해해야 합니다.

---

## 목차

1. [전체 아키텍처 데이터 흐름](#1-전체-아키텍처-데이터-흐름)
2. [워크플로우 실행 데이터 흐름](#2-워크플로우-실행-데이터-흐름)
3. [노드별 데이터 변환](#3-노드별-데이터-변환)
4. [이벤트 스트리밍 데이터 구조](#4-이벤트-스트리밍-데이터-구조)
5. [세션 관리 데이터 흐름](#5-세션-관리-데이터-흐름)
6. [Human-in-the-Loop 데이터 흐름](#6-human-in-the-loop-데이터-흐름)
7. [템플릿 렌더링 데이터 흐름](#7-템플릿-렌더링-데이터-흐름)
8. [에러 처리 데이터 흐름](#8-에러-처리-데이터-흐름)

---

## 1. 전체 아키텍처 데이터 흐름

### 1.1 계층별 데이터 흐름

```
┌─────────────────────────────────────────────────────────────┐
│                      Frontend (React)                        │
│  - WorkflowCanvas: Workflow 객체 (nodes, edges)            │
│  - NodeConfig: NodeData 편집                                 │
│  - ExecutionLog: ExecutionEvent 수신 및 표시                │
└────────────────────┬────────────────────────────────────────┘
                     │ HTTP/SSE
                     ↓
┌─────────────────────────────────────────────────────────────┐
│              Presentation Layer (FastAPI)                    │
│  - Routers: Pydantic 스키마 검증                            │
│  - Services: 비즈니스 로직 수행                             │
│    * WorkflowExecutor: 워크플로우 오케스트레이션           │
│    * NodeExecutor: 노드별 실행                              │
│    * TemplateRenderer: Jinja2 변수 치환                     │
└────────────────────┬────────────────────────────────────────┘
                     │ SDK 호출
                     ↓
┌─────────────────────────────────────────────────────────────┐
│              Infrastructure Layer                            │
│  - WorkerAgent: Claude SDK 래퍼                             │
│  - SDKExecutor: 스트리밍 응답 처리                          │
│  - StructuredLogger: 구조화 로깅                            │
│  - ConfigLoader: 설정 로드 (agent_config.json)             │
└────────────────────┬────────────────────────────────────────┘
                     │ HTTP API
                     ↓
┌─────────────────────────────────────────────────────────────┐
│                   Claude Agent SDK                           │
│  - AssistantMessage, UserMessage, SystemMessage             │
│  - TextBlock, ToolUseBlock, ToolResultBlock                 │
│  - 세션 관리 및 컨텍스트 유지                               │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 주요 데이터 객체

#### Frontend (TypeScript)

```typescript
// 워크플로우 정의
interface Workflow {
  nodes: WorkflowNode[];  // 노드 배열
  edges: WorkflowEdge[];  // 엣지 배열
}

interface WorkflowNode {
  id: string;             // 노드 고유 ID (예: "input-1", "worker-2")
  type: 'input' | 'worker' | 'condition' | 'merge';
  position: { x: number; y: number };
  data: NodeData;         // 노드별 설정 데이터
}

interface WorkflowEdge {
  id: string;             // 엣지 ID
  source: string;         // 출발 노드 ID
  target: string;         // 도착 노드 ID
  sourceHandle?: string;  // 출발 핸들 (condition: "true"/"false")
  targetHandle?: string;
}

// 노드별 데이터 구조
interface InputNodeData {
  label: string;
  input_text: string;     // 초기 입력 텍스트
}

interface WorkerNodeData {
  label: string;
  agent_name: string;     // Worker 이름 (예: "backend_coder")
  task_template: string;  // Jinja2 템플릿 (예: "{{input}}을 분석해주세요")
  allowed_tools?: string[];
  thinking?: boolean;
  output_extraction?: OutputExtractionConfig;
}

interface ConditionNodeData {
  label: string;
  condition_type: 'contains' | 'regex' | 'length' | 'custom' | 'llm';
  condition_value: string;
  max_iterations?: number | null;
}

interface MergeNodeData {
  label: string;
  merge_strategy: 'concatenate' | 'first' | 'last' | 'custom';
}

// 실행 이벤트 구조
interface ExecutionEvent {
  event_type: 'workflow_start' | 'node_start' | 'node_output' |
              'node_complete' | 'workflow_complete' | 'workflow_error' |
              'ask_user';
  timestamp: string;
  node_id?: string;
  data?: any;
}
```

#### Backend (Python)

```python
# Pydantic 스키마 (src/presentation/web/schemas/)
class WorkflowNode(BaseModel):
    id: str
    type: Literal["input", "worker", "condition", "merge"]
    position: Dict[str, float]
    data: Union[InputNodeData, WorkerNodeData, ConditionNodeData, MergeNodeData]

class WorkflowEdge(BaseModel):
    id: str
    source: str
    target: str
    sourceHandle: Optional[str] = None
    targetHandle: Optional[str] = None

class Workflow(BaseModel):
    nodes: List[WorkflowNode]
    edges: List[WorkflowEdge]

# 실행 이벤트 (src/presentation/web/services/workflow_executor.py)
class WorkflowNodeExecutionEvent:
    event_type: str  # "node_start", "node_output", "node_complete" 등
    timestamp: str
    node_id: Optional[str]
    data: Optional[Dict[str, Any]]
```

---

## 2. 워크플로우 실행 데이터 흐름

### 2.1 전체 실행 흐름 (동적 노드 선택 방식)

```
사용자가 "실행" 버튼 클릭
        ↓
[Frontend] POST /workflows/execute
        ↓
[WorkflowExecutor.execute_workflow()]
        ↓
1. 세션 ID 생성 (UUID)
        ↓
2. 로깅 세션 파일 핸들러 추가
   - ~/.claude-flow/{project}/logs/session_{session_id}.log
        ↓
3. Input 노드 탐색 (시작점)
   - _find_input_node(workflow)
        ↓
4. 동적 노드 선택 루프 시작
   - current_node_id = input_node.id
   - executed_nodes = set()
   - pending_merge_nodes = set()
        ↓
   ┌─────────────────────────────────────┐
   │ while current_node_id or pending:    │
   │   1. 노드 실행                       │
   │   2. next_node_id 추출               │
   │   3. 다음 노드 결정                  │
   │      - Condition: next_node_id 사용 │
   │      - 일반: 자식 노드 탐색          │
   │      - Merge: 대기 큐 추가           │
   │   4. 실행 완료 마킹                  │
   └─────────────────────────────────────┘
        ↓
5. workflow_complete 이벤트 전송
        ↓
6. 세션 로그 핸들러 제거
        ↓
[Frontend] 실행 로그 패널에 결과 표시
```

### 2.2 노드 실행 데이터 흐름 (execute_node)

```python
# 입력: current_node_id, node_outputs, workflow
# 출력: WorkflowNodeExecutionEvent 스트림

async def execute_node(node_id: str) -> AsyncGenerator[WorkflowNodeExecutionEvent]:
    """
    node_id → WorkflowNode 조회
             ↓
    node.type에 따라 NodeExecutor 선택
             ↓
    ┌───────────────────────────────────────────┐
    │ InputExecutor                              │
    │ - 입력: node.data.input_text              │
    │ - 출력: node_outputs[node_id] = input_text │
    ├───────────────────────────────────────────┤
    │ WorkerExecutor                             │
    │ - 입력: 템플릿 렌더링된 task              │
    │ - 처리: Claude SDK 호출 (스트리밍)        │
    │ - 출력: node_outputs[node_id] = response  │
    ├───────────────────────────────────────────┤
    │ ConditionExecutor                          │
    │ - 입력: 부모 노드 출력                    │
    │ - 처리: 조건 평가 (LLM/일반)             │
    │ - 출력: next_node_id (분기 경로)          │
    │         node_outputs[node_id] = 부모 출력 │
    ├───────────────────────────────────────────┤
    │ MergeExecutor                              │
    │ - 입력: 모든 부모 노드 출력               │
    │ - 처리: 병합 전략 적용                    │
    │ - 출력: node_outputs[node_id] = merged    │
    └───────────────────────────────────────────┘
             ↓
    이벤트 스트리밍 (node_start → node_output → node_complete)
    """
```

---

## 3. 노드별 데이터 변환

### 3.1 Input 노드 (`InputExecutor`)

**파일**: `src/presentation/web/services/node_executors/input_executor.py`

```
입력 데이터:
- node.data.input_text: str (사용자가 입력한 초기 텍스트)

처리 과정:
1. node_start 이벤트 전송
2. input_text를 그대로 node_outputs에 저장
3. node_complete 이벤트 전송

출력 데이터:
- node_outputs[node_id] = input_text
- 다음 노드가 이 값을 사용

이벤트 구조:
{
  "event_type": "node_start",
  "node_id": "input-1",
  "data": {"node_type": "input", "label": "시작"}
}
{
  "event_type": "node_output",
  "node_id": "input-1",
  "data": {"chunk": "사용자 입력 텍스트", "chunk_type": "input"}
}
{
  "event_type": "node_complete",
  "node_id": "input-1",
  "data": {"output": "사용자 입력 텍스트"}
}
```

### 3.2 Worker 노드 (`WorkerExecutor`)

**파일**: `src/presentation/web/services/node_executors/worker_executor.py`

```
입력 데이터:
1. node.data.task_template: str (Jinja2 템플릿)
   예: "{{input}}을 분석해주세요"

2. node_outputs: Dict[str, str] (이전 노드들의 출력)
   예: {"input-1": "사용자 입력", "worker-1": "이전 결과"}

처리 과정:
1. 템플릿 렌더링 (WorkflowTemplateRenderer)
   - task_template에서 {{변수}} 치환
   - 변수 참조: {{input}}, {{node_1.output}}, {{worker_1.output}}
   - 렌더링 결과: "사용자 입력을 분석해주세요"

2. Agent 설정 로드 (JsonConfigLoader)
   - agent_name으로 AgentConfig 조회
   - 프롬프트 파일 로드: prompts/{agent_name}.txt

3. Claude SDK 호출 (WorkerAgent)
   입력:
   - system_prompt: 프롬프트 파일 내용
   - task: 렌더링된 task
   - allowed_tools: ["read", "write", "edit", "bash", "glob", "grep"]
   - thinking: true/false
   - resume_session_id: 이전 세션 ID (재활용)
   - user_input_callback: Human-in-the-Loop 콜백

4. 스트리밍 응답 처리
   async for response in sdk.query():
       if isinstance(response, AssistantMessage):
           for content_block in response.content:
               if isinstance(content_block, TextBlock):
                   chunk = content_block.text
                   yield node_output(chunk, "text")
               elif isinstance(content_block, ToolUseBlock):
                   yield node_output(tool_use_data, "tool_use")
       elif isinstance(response, ResultMessage):
           for result_block in response.content:
               yield node_output(result_data, "tool_result")

5. 출력 추출 (extract_text_with_strategy)
   전략:
   - full: 모든 텍스트 블록 추출
   - last_block: 마지막 텍스트 블록만
   - between_markers: 마커 사이 텍스트만

   자동 마커 감지:
   - "---NEXT_WORKER_OUTPUT_START---" / "---NEXT_WORKER_OUTPUT_END---"
   - 프롬프트가 표준 마커를 사용하면 자동 추출

출력 데이터:
- node_outputs[node_id] = extracted_text
- session_id_map[node_id] = sdk_session_id (세션 재활용용)

이벤트 구조:
{
  "event_type": "node_start",
  "node_id": "worker-1",
  "data": {
    "node_type": "worker",
    "label": "Backend Coder",
    "agent_name": "backend_coder",
    "task": "사용자 입력을 분석해주세요"
  }
}
{
  "event_type": "node_output",
  "node_id": "worker-1",
  "data": {
    "chunk": "분석 중입니다...",
    "chunk_type": "text"
  }
}
{
  "event_type": "node_output",
  "node_id": "worker-1",
  "data": {
    "chunk": {"tool": "read", "path": "file.py"},
    "chunk_type": "tool_use"
  }
}
{
  "event_type": "node_complete",
  "node_id": "worker-1",
  "data": {
    "output": "분석 결과...",
    "session_id": "sdk-session-123",
    "total_tokens": 1500
  }
}
```

### 3.3 Condition 노드 (`ConditionExecutor`)

**파일**: `src/presentation/web/services/node_executors/condition_executor.py`

```
입력 데이터:
1. 부모 노드 출력 (parent_output)
   - 이전 노드의 node_outputs[parent_id]

2. node.data (ConditionNodeData)
   - condition_type: 'contains' | 'regex' | 'length' | 'custom' | 'llm'
   - condition_value: str
   - max_iterations: int | None

처리 과정:
1. 부모 노드 출력 조회
   parent_nodes = graph_manager.get_parent_nodes(node_id)
   parent_id = parent_nodes[0]
   parent_output = node_outputs[parent_id]

2. 조건 평가 (WorkflowConditionEvaluator)

   2.1 일반 조건 평가 (contains, regex, length, custom)
       - contains: parent_output에 condition_value 포함 여부
       - regex: re.search(condition_value, parent_output)
       - length: len(parent_output) 비교
       - custom: AST 기반 안전 평가 (eval 대체)

   2.2 LLM 조건 평가 (llm)
       - Claude SDK에 조건 평가 요청
       - 프롬프트:
         """
         다음 텍스트가 조건을 만족하는지 판단해주세요.

         조건: {condition_value}
         텍스트: {parent_output}

         판단: YES/NO
         이유: 간단한 설명
         """
       - 응답 파싱: "판단: YES" → True, "판단: NO" → False
       - 실시간 스트리밍: LLM 사고 과정을 UI에 표시

3. 반복 제한 체크
   if max_iterations is not None and current_iteration >= max_iterations:
       condition_result = True  # 강제로 True로 전환

4. 다음 노드 결정
   edges = workflow.edges
   if condition_result:
       next_edge = [e for e in edges if e.source == node_id and e.sourceHandle == "true"]
   else:
       next_edge = [e for e in edges if e.source == node_id and e.sourceHandle == "false"]

   next_node_id = next_edge[0].target

출력 데이터:
- node_outputs[node_id] = parent_output (부모 출력을 그대로 전달!)
- next_node_id: 분기 경로 (node_complete 이벤트의 "next_node" 필드)

⚠️ 중요: Condition 노드는 데이터 변환을 하지 않음!
- 평가 결과는 분기 경로 결정에만 사용
- 다음 노드는 부모 노드의 원본 출력을 받음
- 평가 메타정보는 로그로만 표시

이벤트 구조:
{
  "event_type": "node_start",
  "node_id": "condition-1",
  "data": {
    "node_type": "condition",
    "label": "성공 여부 확인",
    "condition_type": "contains",
    "condition_value": "SUCCESS"
  }
}
{
  "event_type": "node_output",
  "node_id": "condition-1",
  "data": {
    "chunk": "부모 노드 출력: ...",
    "chunk_type": "input"
  }
}
{
  "event_type": "node_output",
  "node_id": "condition-1",
  "data": {
    "chunk": "조건 평가 중...",
    "chunk_type": "text"
  }
}
{
  "event_type": "node_complete",
  "node_id": "condition-1",
  "data": {
    "output": "부모 노드 출력 (변경되지 않음)",
    "next_node": "worker-2",
    "condition_result": true,
    "evaluation_result": "조건 타입: contains\n조건 값: SUCCESS\n평가 결과: True",
    "forwarded_output": "부모 노드 출력 (150자)"
  }
}
```

### 3.4 Merge 노드 (`MergeExecutor`)

**파일**: `src/presentation/web/services/node_executors/merge_executor.py`

```
입력 데이터:
1. 모든 부모 노드 출력
   parent_nodes = graph_manager.get_parent_nodes(node_id)
   parent_outputs = [node_outputs[parent_id] for parent_id in parent_nodes]

2. node.data (MergeNodeData)
   - merge_strategy: 'concatenate' | 'first' | 'last' | 'custom'

처리 과정:
1. 모든 부모 노드 완료 확인
   - WorkflowExecutor가 대기 큐(pending_merge_nodes)로 관리
   - _can_execute_merge_node()로 실행 가능 여부 확인

2. 병합 전략 적용

   2.1 concatenate (기본)
       merged = "\n\n".join(parent_outputs)

   2.2 first
       merged = parent_outputs[0]

   2.3 last
       merged = parent_outputs[-1]

   2.4 custom (추후 구현 예정)
       # 사용자 정의 병합 로직

출력 데이터:
- node_outputs[node_id] = merged_output

이벤트 구조:
{
  "event_type": "node_start",
  "node_id": "merge-1",
  "data": {
    "node_type": "merge",
    "label": "결과 병합",
    "merge_strategy": "concatenate"
  }
}
{
  "event_type": "node_complete",
  "node_id": "merge-1",
  "data": {
    "output": "병합된 텍스트...",
    "parent_outputs_count": 3
  }
}
```

---

## 4. 이벤트 스트리밍 데이터 구조

### 4.1 SSE (Server-Sent Events) 구조

**파일**: `src/presentation/web/routers/workflows/execution.py`

```python
@router.post("/execute")
async def execute_workflow():
    """
    워크플로우 실행 (SSE 스트리밍)
    """

    async def event_generator():
        async for event in executor.execute_workflow(...):
            # 이벤트를 JSON으로 직렬화
            event_json = json.dumps({
                "event_type": event.event_type,
                "timestamp": event.timestamp,
                "node_id": event.node_id,
                "data": event.data
            })

            # SSE 형식으로 전송
            yield f"data: {event_json}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )
```

### 4.2 이벤트 타입별 데이터 구조

#### workflow_start

```json
{
  "event_type": "workflow_start",
  "timestamp": "2025-11-05T14:30:00.123456",
  "node_id": null,
  "data": {
    "session_id": "uuid-123",
    "total_nodes": 5
  }
}
```

#### node_start

```json
{
  "event_type": "node_start",
  "timestamp": "2025-11-05T14:30:01.234567",
  "node_id": "worker-1",
  "data": {
    "node_type": "worker",
    "label": "Backend Coder",
    "agent_name": "backend_coder",
    "task": "렌더링된 task 텍스트..."
  }
}
```

#### node_output (텍스트)

```json
{
  "event_type": "node_output",
  "timestamp": "2025-11-05T14:30:02.345678",
  "node_id": "worker-1",
  "data": {
    "chunk": "분석 중입니다...",
    "chunk_type": "text"
  }
}
```

#### node_output (도구 사용)

```json
{
  "event_type": "node_output",
  "timestamp": "2025-11-05T14:30:03.456789",
  "node_id": "worker-1",
  "data": {
    "chunk": {
      "tool": "read",
      "path": "/path/to/file.py",
      "input": {"file_path": "/path/to/file.py"}
    },
    "chunk_type": "tool_use"
  }
}
```

#### node_output (도구 결과)

```json
{
  "event_type": "node_output",
  "timestamp": "2025-11-05T14:30:04.567890",
  "node_id": "worker-1",
  "data": {
    "chunk": {
      "tool": "read",
      "output": "파일 내용..."
    },
    "chunk_type": "tool_result"
  }
}
```

#### node_complete

```json
{
  "event_type": "node_complete",
  "timestamp": "2025-11-05T14:30:10.678901",
  "node_id": "worker-1",
  "data": {
    "output": "최종 출력 텍스트...",
    "session_id": "sdk-session-123",
    "total_tokens": 1500,
    "input_tokens": 500,
    "output_tokens": 1000
  }
}
```

#### workflow_complete

```json
{
  "event_type": "workflow_complete",
  "timestamp": "2025-11-05T14:30:30.789012",
  "node_id": null,
  "data": {
    "session_id": "uuid-123",
    "total_execution_time": "30.5s",
    "executed_nodes": ["input-1", "worker-1", "condition-1", "worker-2"]
  }
}
```

#### workflow_error

```json
{
  "event_type": "workflow_error",
  "timestamp": "2025-11-05T14:30:15.890123",
  "node_id": "worker-1",
  "data": {
    "error": "Agent를 찾을 수 없습니다: unknown_agent",
    "traceback": "..."
  }
}
```

#### ask_user

```json
{
  "event_type": "ask_user",
  "timestamp": "2025-11-05T14:30:05.901234",
  "node_id": "worker-1",
  "data": {
    "question": "사용자에게 질문할 내용..."
  }
}
```

---

## 5. 세션 관리 데이터 흐름

### 5.1 노드별 세션 재활용 메커니즘

**파일**: `src/presentation/web/services/workflow_executor.py`

```python
class WorkflowExecutor:
    def __init__(self):
        # 노드별 현재 세션 ID 맵핑
        self.node_sessions: Dict[str, str] = {}
        # {node_id: sdk_session_id}

        # 노드별 세션 이력
        self.node_session_history: Dict[str, List[SessionInfo]] = {}
        # {node_id: [SessionInfo(session_id, timestamp, tokens), ...]}

데이터 흐름:
1. Worker 노드 실행 시작
   - node_id = "worker-1"
   - resume_session_id = self.node_sessions.get(node_id, None)
   - 첫 실행: resume_session_id = None (새 세션 생성)
   - 재실행: resume_session_id = "sdk-session-123" (세션 재활용)

2. SDK 호출 (WorkerAgent.query)
   async for response in sdk.query(
       prompt=task,
       options=ClaudeAgentOptions(resume_session_id=resume_session_id)
   ):
       # 세션 ID 추출
       if hasattr(response, 'session_id'):
           current_session_id = response.session_id

3. Worker 노드 실행 완료
   - self.node_sessions[node_id] = current_session_id
   - self.node_session_history[node_id].append(SessionInfo(...))

4. 다음 실행 시
   - 동일 노드 재실행 → 이전 세션 ID로 컨텍스트 유지
   - 컨텍스트 윈도우: 이전 대화 이력 모두 유지
   - Artifact Storage: 이전 출력이 파일로 저장되어 있으면 참조 가능
```

### 5.2 세션 이력 데이터 구조

```python
class SessionInfo(BaseModel):
    session_id: str          # SDK 세션 ID
    timestamp: str           # 생성 시간
    input_text: str          # 입력 텍스트
    output_text: str         # 출력 텍스트
    total_tokens: int        # 총 토큰 사용량
    input_tokens: int        # 입력 토큰
    output_tokens: int       # 출력 토큰

# API 응답: GET /api/projects/{project}/nodes/{node_id}/sessions
{
  "node_id": "worker-1",
  "sessions": [
    {
      "session_id": "sdk-session-123",
      "timestamp": "2025-11-05T14:30:00",
      "input_text": "첫 번째 실행 입력",
      "output_text": "첫 번째 실행 출력...",
      "total_tokens": 1500,
      "input_tokens": 500,
      "output_tokens": 1000
    },
    {
      "session_id": "sdk-session-456",
      "timestamp": "2025-11-05T15:00:00",
      "input_text": "두 번째 실행 입력",
      "output_text": "두 번째 실행 출력...",
      "total_tokens": 2000,
      "input_tokens": 800,
      "output_tokens": 1200
    }
  ]
}
```

---

## 6. Human-in-the-Loop 데이터 흐름

### 6.1 전체 흐름

**파일**: `src/presentation/web/services/node_executors/worker_executor.py`

```
Worker 노드 실행 중
        ↓
Worker가 "@ASK_USER: 질문내용" 패턴 출력
        ↓
[WorkerSDKExecutor] 패턴 감지
        ↓
[WorkflowExecutor] ask_user 이벤트 전송
        ↓
[Frontend] AskUserModal 표시 (사용자에게 입력 대기)
        ↓
사용자가 답변 입력
        ↓
[Frontend] PUT /workflows/user-response
        ↓
[WorkflowExecutor] user_input_queues[node_id]에 답변 추가
        ↓
[WorkerAgent] user_input_callback 호출 → 답변 반환
        ↓
Worker 실행 재개 (답변을 받아서 계속 작업)
```

### 6.2 데이터 구조

```python
# WorkflowExecutor
class WorkflowExecutor:
    def __init__(self):
        # 노드별 사용자 입력 대기 큐
        self.user_input_queues: Dict[str, asyncio.Queue] = {}
        # {node_id: Queue}

# user_input_callback 함수
async def user_input_callback(question: str) -> str:
    # 1. ask_user 이벤트 전송
    await event_queue.put(WorkflowNodeExecutionEvent(
        event_type="ask_user",
        node_id=node_id,
        data={"question": question}
    ))

    # 2. 사용자 응답 대기
    response = await user_input_queue.get()  # 블로킹

    # 3. Worker에게 응답 반환
    return response

# API 엔드포인트
@router.put("/user-response")
async def submit_user_response(
    session_id: str,
    node_id: str,
    response: str
):
    # 대기 큐에 답변 추가
    executor = get_executor()
    await executor.user_input_queues[node_id].put(response)

    return {"status": "success"}
```

### 6.3 프론트엔드 처리

```typescript
// AskUserModal.tsx
const handleSubmit = async () => {
  await fetch('/api/workflows/user-response', {
    method: 'PUT',
    body: JSON.stringify({
      session_id: sessionId,
      node_id: nodeId,
      response: userInput
    })
  });

  setModalOpen(false);
};

// EventStream 처리
eventSource.addEventListener('message', (e) => {
  const event = JSON.parse(e.data);

  if (event.event_type === 'ask_user') {
    // 모달 표시
    setAskUserQuestion(event.data.question);
    setAskUserNodeId(event.node_id);
    setModalOpen(true);
  }
});
```

---

## 7. 템플릿 렌더링 데이터 흐름

### 7.1 Jinja2 변수 치환 메커니즘

**파일**: `src/presentation/web/services/workflow_template_renderer.py`

```python
class WorkflowTemplateRenderer:
    def render_task_template(
        self,
        template_str: str,
        node_outputs: Dict[str, str],
        workflow: Workflow
    ) -> str:
        """
        Jinja2 템플릿 렌더링

        입력:
        - template_str: "{{input}}을 분석해주세요. 이전 결과: {{worker_1.output}}"
        - node_outputs: {
            "input-1": "사용자 입력",
            "worker-1": "이전 Worker 결과"
          }
        - workflow: Workflow 객체 (노드 정보)

        처리:
        1. 노드 ID → 라벨 맵핑 생성
           {
             "input-1": "input",
             "worker-1": "worker_1"
           }

        2. Jinja2 컨텍스트 생성
           {
             "input": "사용자 입력",
             "worker_1": {"output": "이전 Worker 결과"},
             "node_outputs": node_outputs
           }

        3. Jinja2 렌더링
           "사용자 입력을 분석해주세요. 이전 결과: 이전 Worker 결과"

        출력:
        - 렌더링된 문자열
        """
```

### 7.2 지원 변수 형식

```jinja2
# 1. Input 노드 참조 (단축 변수)
{{input}}
# → node_outputs["input-1"]

# 2. 특정 노드 출력 참조 (라벨 기반)
{{worker_1.output}}
# → node_outputs["worker-1"]

# 3. 특정 노드 출력 참조 (노드 ID 기반)
{{node_outputs["worker-1"]}}
# → node_outputs["worker-1"]

# 4. 조건부 렌더링
{% if worker_1.output %}
이전 결과: {{worker_1.output}}
{% else %}
이전 결과 없음
{% endif %}

# 5. 리스트 순회 (추후 지원 예정)
{% for item in items %}
- {{item}}
{% endfor %}
```

### 7.3 에러 처리

```python
try:
    rendered = template.render(context)
except jinja2.TemplateError as e:
    logger.error(f"템플릿 렌더링 실패: {e}")
    # Fallback: 원본 템플릿 반환
    return template_str
```

---

## 8. 에러 처리 데이터 흐름

### 8.1 에러 전파 메커니즘

```
[NodeExecutor] 에러 발생
        ↓
try-except 블록에서 에러 캐치
        ↓
logger.error() 호출 (구조화 로깅)
        ↓
workflow_error 이벤트 생성
        ↓
yield WorkflowNodeExecutionEvent(
    event_type="workflow_error",
    node_id=node_id,
    data={
        "error": str(e),
        "traceback": traceback.format_exc()
    }
)
        ↓
[Frontend] 에러 메시지 표시
        ↓
워크플로우 실행 중단
```

### 8.2 에러 타입별 처리

#### Agent 찾을 수 없음

```python
# worker_executor.py
agent_config = config_loader.get_agent_config(agent_name)
if not agent_config:
    raise ValueError(f"Agent를 찾을 수 없습니다: {agent_name}")
```

#### 템플릿 렌더링 실패

```python
# workflow_template_renderer.py
try:
    rendered = template.render(context)
except jinja2.TemplateError as e:
    logger.error(f"템플릿 렌더링 실패: {e}")
    return template_str  # Fallback
```

#### SDK 호출 실패

```python
# worker_executor.py
try:
    async for response in worker.query(...):
        # 스트리밍 처리
except Exception as e:
    logger.error(f"SDK 호출 실패: {e}")
    yield workflow_error(e)
```

#### Condition 평가 실패

```python
# condition_executor.py
try:
    condition_result = evaluator.evaluate_condition(...)
except Exception as e:
    logger.error(f"조건 평가 실패: {e}")
    # Fallback: False 반환
    condition_result = False
```

---

## 9. 주요 데이터 변환 체크리스트

### 9.1 Condition 노드 주의사항 ⚠️

**절대 규칙**:
- ✅ Condition 노드는 **부모 노드의 출력을 그대로 전달**
- ❌ Condition 노드는 **평가 결과 메타정보를 전달하지 않음**

**잘못된 구현** (BUG):
```python
# ❌ 평가 결과를 다음 노드로 전달 (잘못됨!)
node_outputs[node_id] = f"조건 평가 결과: {condition_result}\n분기: {next_node_id}"
```

**올바른 구현**:
```python
# ✅ 부모 출력을 그대로 전달
node_outputs[node_id] = parent_output

# 평가 결과는 로그와 이벤트에만 포함
event.data = {
    "output": parent_output,  # 실제 전달 값
    "next_node": next_node_id,  # 분기 경로
    "evaluation_result": "조건 타입: contains\n평가 결과: True"  # 로그용
}
```

### 9.2 Worker 노드 출력 추출 주의사항 ⚠️

**출력 추출 우선순위**:
1. 사용자 지정 `OutputExtractionConfig` (명시적 설정)
2. 자동 마커 감지 (표준 마커: `---NEXT_WORKER_OUTPUT_START/END---`)
3. 기본 전략 (`full` - 전체 텍스트)

**프롬프트 작성 시 주의**:
- Worker가 **파일로만 저장**하고 텍스트 출력을 하지 않으면 SDK 출력에 마커 없음
- 반드시 **대화 응답으로 직접 출력**해야 SDK 출력에 포함됨

**올바른 프롬프트 예시**:
```
작업 완료 시 필수 조치:

1. 상세 작업 보고서 (파일로 저장)
   - artifacts/report.md에 저장

2. 다음 워커를 위한 요약 (텍스트로 출력)
   ---NEXT_WORKER_OUTPUT_START---
   핵심 결과만 요약
   ---NEXT_WORKER_OUTPUT_END---
```

### 9.3 세션 재활용 주의사항 ⚠️

**세션 ID 전달 흐름**:
```
WorkflowExecutor.node_sessions[node_id] = "sdk-session-123"
        ↓
next execution
        ↓
resume_session_id = WorkflowExecutor.node_sessions.get(node_id)
        ↓
WorkerAgent.query(options=ClaudeAgentOptions(resume_session_id=...))
```

**주의사항**:
- 노드 ID가 변경되면 세션이 재활용되지 않음
- 워크플로우를 수정하면 노드 ID가 변경될 수 있음 (ReactFlow가 자동 생성)
- 세션 재활용이 필요한 경우 노드 ID를 고정하거나 라벨 기반 세션 관리 필요

---

## 10. 참고 자료

- **API 레퍼런스**: `docs/api.md` (43개 엔드포인트)
- **코드 레퍼런스**: `docs/code-reference.md` (핵심 클래스 및 함수)
- **아키텍처**: `docs/architecture.md` (Clean Architecture 및 디자인 패턴)
- **데이터베이스**: `docs/database.md` (데이터 모델 및 파일 구조)
- **FAQ**: `docs/faq.md` (자주 묻는 질문)

---

## 변경 이력

- **2025-11-05**: 초안 작성 (동적 노드 선택 알고리즘 반영)
