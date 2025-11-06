/**
 * Claude Flow API 클라이언트
 *
 * 백엔드 API와 통신하는 함수들을 제공합니다.
 */

export const API_BASE = '/api'

/**
 * Agent 정보
 */
export interface Agent {
  name: string
  role: string
  description: string
  system_prompt: string  // 시스템 프롬프트 원본
  allowed_tools: string[]  // 기본 도구 목록
  model?: string  // 모델 정보 (옵셔널)
  thinking?: boolean  // Thinking 모드 기본값 (옵셔널)
  is_custom?: boolean  // 커스텀 워커 여부 (옵셔널)
}

/**
 * 워크플로우 노드 데이터 (타입별로 다름)
 */
export type WorkflowNodeData =
  | {
      // Worker 노드
      agent_name: string
      task_template: string
      allowed_tools?: string[]
      config?: Record<string, any>
    }
  | {
      // Manager 노드
      task_description: string
      available_workers: string[]
    }
  | {
      // Input 노드
      initial_input: string
    }
  | {
      // Condition 노드
      condition_type: string
      condition_value: string
    }
  | {
      // Loop 노드
      max_iterations: number
      loop_condition: string
      loop_condition_type: string
    }
  | {
      // Merge 노드
      merge_strategy: string
      separator: string
    }

/**
 * 워크플로우 노드
 */
export interface WorkflowNode {
  id: string
  type: string
  position: { x: number; y: number }
  data: WorkflowNodeData & Record<string, any> // 유연한 타입
}

/**
 * 워크플로우 엣지
 */
export interface WorkflowEdge {
  id: string
  source: string
  target: string
  sourceHandle?: string
  targetHandle?: string
}

/**
 * 워크플로우
 */
export interface Workflow {
  id?: string
  name: string
  description?: string
  nodes: WorkflowNode[]
  edges: WorkflowEdge[]
  metadata?: Record<string, any>
}

/**
 * 워크플로우 실행 이벤트
 */
export interface WorkflowExecutionEvent {
  event_type: 'node_start' | 'node_output' | 'node_complete' | 'node_error' | 'workflow_complete' | 'user_input_request'
  node_id: string
  data: Record<string, any>
  timestamp?: string  // ISO 8601 형식
  elapsed_time?: number  // 초 단위
  token_usage?: {
    input_tokens: number
    output_tokens: number
    total_tokens: number
  }
}

/**
 * 워크플로우 검증 에러
 */
export interface WorkflowValidationError {
  severity: 'error' | 'warning' | 'info'
  node_id: string
  message: string
  suggestion: string
}

/**
 * 워크플로우 검증 응답
 */
export interface WorkflowValidateResponse {
  valid: boolean
  errors: WorkflowValidationError[]
}

/**
 * Agent 목록 조회
 */
export async function getAgents(): Promise<Agent[]> {
  const response = await fetch(`${API_BASE}/agents`)
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`)
  }
  const data = await response.json()
  return data.agents
}

/**
 * 워크플로우 실행 (SSE 스트리밍)
 *
 * @param workflow 워크플로우 정의
 * @param initialInput 초기 입력 데이터
 * @param onEvent 이벤트 콜백
 * @param onComplete 완료 콜백
 * @param onError 에러 콜백
 * @param signal AbortSignal (연결 중단용)
 * @param sessionId 세션 ID (재접속 시 사용, optional)
 * @param lastEventIndex 마지막 수신 이벤트 인덱스 (재접속 시 중복 방지, optional)
 * @param startNodeId 시작 노드 ID (Input 노드 선택, optional)
 * @returns 세션 ID (X-Session-ID 헤더에서 추출)
 */
export async function executeWorkflow(
  workflow: Workflow,
  initialInput: string,
  onEvent: (event: WorkflowExecutionEvent) => void,
  onComplete: () => void,
  onError: (error: string) => void,
  signal?: AbortSignal,
  sessionId?: string,
  lastEventIndex?: number,
  startNodeId?: string,
  onSessionId?: (sessionId: string) => void
): Promise<string | null> {
  const requestBody: any = {
    workflow,
    initial_input: initialInput,
  }

  // 재접속 시 세션 ID 및 마지막 이벤트 인덱스 전달
  if (sessionId) {
    requestBody.session_id = sessionId
  }
  if (lastEventIndex !== undefined) {
    requestBody.last_event_index = lastEventIndex
  }
  // 시작 노드 ID 전달 (Input 노드 선택)
  if (startNodeId) {
    requestBody.start_node_id = startNodeId
  }

  console.log('[executeWorkflow] 요청:', {
    sessionId,
    lastEventIndex,
    isReconnect: !!sessionId
  })

  const response = await fetch(`${API_BASE}/workflows/execute`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'text/event-stream',
    },
    body: JSON.stringify(requestBody),
    signal,
  })

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`)
  }

  // 세션 ID 추출 (X-Session-ID 헤더)
  const returnedSessionId = response.headers.get('X-Session-ID')
  console.log('[executeWorkflow] 반환된 세션 ID:', returnedSessionId)

  // 세션 ID를 즉시 콜백으로 전달 (중지 버튼이 즉시 작동하도록)
  if (returnedSessionId && onSessionId) {
    onSessionId(returnedSessionId)
  }

  const reader = response.body?.getReader()
  if (!reader) {
    throw new Error('응답 본문을 읽을 수 없습니다')
  }

  const decoder = new TextDecoder('utf-8')
  let buffer = ''

  try {
    while (true) {
      const { done, value } = await reader.read()

      if (done) {
        console.log('[SSE] 스트림 종료 (done=true)')
        onComplete()
        break
      }

      // 청크를 문자열로 변환
      const chunk = decoder.decode(value, { stream: true })
      buffer += chunk

      console.log('[SSE] 원본 청크 수신:', chunk.length, '바이트')
      console.log('[SSE] 원본 데이터:', JSON.stringify(chunk.substring(0, 200)))

      // ✅ CRLF (\r\n\r\n) 또는 LF (\n\n) 모두 처리
      // SSE 표준: 메시지는 빈 줄(\n\n 또는 \r\n\r\n)로 구분
      const messages = buffer.split(/\r\n\r\n|\n\n/)
      buffer = messages.pop() || ''

      console.log('[SSE] 파싱된 메시지 개수:', messages.length)

      for (const message of messages) {
        if (!message.trim()) {
          console.log('[SSE] 빈 메시지 건너뜀')
          continue
        }

        console.log('[SSE] 메시지 처리:', JSON.stringify(message.substring(0, 100)))

        // ✅ CRLF (\r\n) 또는 LF (\n) 모두 처리
        const lines = message.split(/\r\n|\n/)
        let dataContent = ''

        for (const line of lines) {
          const trimmedLine = line.trim()
          if (trimmedLine.startsWith('data:')) {
            const lineData = trimmedLine.substring(5).trim()
            if (dataContent) {
              dataContent += '\n' + lineData
            } else {
              dataContent = lineData
            }
          }
        }

        if (!dataContent) {
          console.warn('[SSE] data: 필드 없음, 메시지 무시:', message)
          continue
        }

        console.log('[SSE] data 추출 완료:', dataContent.substring(0, 100))

        // [DONE] 시그널
        if (dataContent === '[DONE]') {
          console.log('[SSE] [DONE] 시그널 수신')
          onComplete()
          return returnedSessionId
        }

        // ERROR 시그널
        if (dataContent.startsWith('ERROR:')) {
          const errorMsg = dataContent.substring(7)
          console.error('[SSE] ERROR 시그널:', errorMsg)
          onError(errorMsg)
          return returnedSessionId
        }

        // 이벤트 파싱 (JSON)
        try {
          const event: WorkflowExecutionEvent = JSON.parse(dataContent)
          console.log('[SSE] ✅ 이벤트 파싱 성공:', event.event_type, event.node_id, event.data)
          onEvent(event)
        } catch (e) {
          console.error('[SSE] ❌ JSON 파싱 실패:', dataContent, e)
        }
      }
    }
  } catch (error) {
    // AbortError는 정상적인 중단이므로 에러로 처리하지 않음
    if (error instanceof Error && error.name === 'AbortError') {
      console.log('[SSE] 사용자가 실행을 중단했습니다')
      onComplete()
      return returnedSessionId
    }
    const errorMsg = error instanceof Error ? error.message : String(error)
    onError(errorMsg)
    return returnedSessionId
  } finally {
    reader.releaseLock()
  }

  return returnedSessionId
}

/**
 * 워크플로우 저장
 */
export async function saveWorkflow(workflow: Workflow): Promise<string> {
  const response = await fetch(`${API_BASE}/workflows`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ workflow }),
  })

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`)
  }

  const data = await response.json()
  return data.workflow_id
}

/**
 * 워크플로우 목록 조회
 */
export async function getWorkflows(): Promise<any[]> {
  const response = await fetch(`${API_BASE}/workflows`)
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`)
  }
  const data = await response.json()
  return data.workflows
}

/**
 * 워크플로우 조회 (단일)
 */
export async function getWorkflow(workflowId: string): Promise<Workflow> {
  const response = await fetch(`${API_BASE}/workflows/${workflowId}`)
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`)
  }
  return await response.json()
}

/**
 * 워크플로우 삭제
 */
export async function deleteWorkflow(workflowId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/workflows/${workflowId}`, {
    method: 'DELETE',
  })

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`)
  }
}

// ==================== 프로젝트 API ====================

/**
 * 프로젝트 정보
 */
export interface ProjectInfo {
  project_path: string | null
  has_existing_config: boolean
}

/**
 * 프로젝트 선택
 */
export async function selectProject(projectPath: string): Promise<{
  project_path: string
  message: string
  has_existing_config: boolean
}> {
  const response = await fetch(`${API_BASE}/projects/select`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ project_path: projectPath }),
  })

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
  }

  return await response.json()
}

/**
 * 현재 프로젝트 정보 조회
 */
export async function getCurrentProject(): Promise<ProjectInfo> {
  const response = await fetch(`${API_BASE}/projects/current`)

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`)
  }

  return await response.json()
}

/**
 * 프로젝트에 워크플로우 저장
 */
export async function saveProjectWorkflow(
  workflow: Workflow,
  projectPath?: string
): Promise<{ message: string; config_path: string }> {
  const response = await fetch(`${API_BASE}/projects/workflow`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      project_path: projectPath,
      workflow,
    }),
  })

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
  }

  return await response.json()
}

/**
 * 프로젝트에서 워크플로우 로드
 */
export async function loadProjectWorkflow(
  projectPath?: string
): Promise<{
  project_path: string
  workflow: Workflow
  last_modified: string | null
}> {
  const url = projectPath
    ? `${API_BASE}/projects/workflow?project_path=${encodeURIComponent(projectPath)}`
    : `${API_BASE}/projects/workflow`

  const response = await fetch(url)

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
  }

  return await response.json()
}

// ==================== 워크플로우 관리 API (다중 워크플로우 지원) ====================

/**
 * 워크플로우 정보
 */
export interface WorkflowInfo {
  name: string
  display_name: string
  description: string
  last_modified: string
  size: number
}

/**
 * 워크플로우 목록 조회
 */
export async function listProjectWorkflows(): Promise<{
  workflows: WorkflowInfo[]
  total_count: number
  current_workflow: string | null
}> {
  const response = await fetch(`${API_BASE}/projects/workflows/list`)

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
  }

  return await response.json()
}

/**
 * 특정 워크플로우 로드
 */
export async function loadProjectWorkflowByName(
  workflowName: string
): Promise<{
  project_path: string
  workflow: Workflow
  last_modified: string | null
}> {
  const response = await fetch(`${API_BASE}/projects/workflows/${encodeURIComponent(workflowName)}`)

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
  }

  return await response.json()
}

/**
 * 워크플로우 저장 (이름 지정)
 */
export async function saveProjectWorkflowByName(
  workflowName: string,
  workflow: Workflow
): Promise<{ message: string; workflow_name: string; config_path: string }> {
  const response = await fetch(`${API_BASE}/projects/workflows/${encodeURIComponent(workflowName)}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      workflow,
    }),
  })

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
  }

  return await response.json()
}

/**
 * 워크플로우 삭제
 */
export async function deleteProjectWorkflow(
  workflowName: string
): Promise<{ message: string; workflow_name: string }> {
  const response = await fetch(`${API_BASE}/projects/workflows/${encodeURIComponent(workflowName)}`, {
    method: 'DELETE',
  })

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
  }

  return await response.json()
}

/**
 * 워크플로우 이름 변경
 */
export async function renameProjectWorkflow(
  oldName: string,
  newName: string
): Promise<{ message: string; old_name: string; new_name: string }> {
  const response = await fetch(
    `${API_BASE}/projects/workflows/${encodeURIComponent(oldName)}/rename?new_name=${encodeURIComponent(newName)}`,
    {
      method: 'PUT',
    }
  )

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
  }

  return await response.json()
}

// ==================== 파일 시스템 API ====================

/**
 * 디렉토리 엔트리
 */
export interface DirectoryEntry {
  name: string
  path: string
  is_directory: boolean
  is_readable: boolean
}

/**
 * 디렉토리 브라우징 응답
 */
export interface DirectoryBrowseResponse {
  current_path: string
  parent_path: string | null
  entries: DirectoryEntry[]
}

/**
 * 홈 디렉토리 조회
 */
export async function getHomeDirectory(): Promise<{ home_path: string }> {
  const response = await fetch(`${API_BASE}/filesystem/home`)

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`)
  }

  return await response.json()
}

/**
 * 디렉토리 브라우징
 */
export async function browseDirectory(
  path?: string
): Promise<DirectoryBrowseResponse> {
  const url = path
    ? `${API_BASE}/filesystem/browse?path=${encodeURIComponent(path)}`
    : `${API_BASE}/filesystem/browse`

  const response = await fetch(url)

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
  }

  return await response.json()
}

// ==================== Tool API ====================

/**
 * Tool (도구) 정보
 */
export interface Tool {
  name: string
  description: string
  category: string
  readonly: boolean
}

/**
 * 사용 가능한 도구 목록 조회
 */
export async function getTools(): Promise<Tool[]> {
  const response = await fetch(`${API_BASE}/tools`)
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`)
  }
  const data = await response.json()
  return data.tools
}

// ==================== Template API ====================

/**
 * 템플릿 메타데이터 (목록 조회용)
 */
export interface TemplateMetadata {
  id: string
  name: string
  description: string | null
  category: string
  node_count: number
  edge_count: number
  thumbnail: string | null
  tags: string[]
  is_builtin: boolean
  created_at: string | null
  updated_at: string | null
}

/**
 * 템플릿 (전체)
 */
export interface Template {
  id: string
  name: string
  description: string | null
  category: string
  workflow: Workflow
  thumbnail: string | null
  tags: string[]
  is_builtin: boolean
  metadata: Record<string, any>
  created_at: string | null
  updated_at: string | null
}

/**
 * 템플릿 저장 요청
 */
export interface TemplateSaveRequest {
  name: string
  description: string | null
  category: string
  workflow: Workflow
  tags: string[]
}

/**
 * 템플릿 목록 조회
 */
export async function getTemplates(): Promise<TemplateMetadata[]> {
  const response = await fetch(`${API_BASE}/templates`)
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`)
  }
  const data = await response.json()
  return data.templates
}

/**
 * 템플릿 상세 조회
 */
export async function getTemplate(templateId: string): Promise<Template> {
  const response = await fetch(`${API_BASE}/templates/${templateId}`)
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
  }
  return await response.json()
}

/**
 * 템플릿 저장
 */
export async function saveTemplate(template: TemplateSaveRequest): Promise<string> {
  const response = await fetch(`${API_BASE}/templates`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(template),
  })

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
  }

  const data = await response.json()
  return data.template_id
}

/**
 * 템플릿 삭제
 */
export async function deleteTemplate(templateId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/templates/${templateId}`, {
    method: 'DELETE',
  })

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
  }
}

/**
 * 템플릿 검증 (워크플로우 유효성 검사)
 */
export async function validateTemplate(workflow: Workflow): Promise<{ valid: boolean; errors: string[] }> {
  const response = await fetch(`${API_BASE}/templates/validate`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(workflow),
  })

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
  }

  return await response.json()
}

/**
 * 워크플로우 검증 (유효성 검사)
 *
 * 워크플로우 실행 전 다음 항목을 검증합니다:
 * - 순환 참조 검사
 * - 고아 노드 검사
 * - 템플릿 변수 유효성 검사
 * - Worker별 도구 권한 검사
 * - Input 노드 존재 여부 검사
 * - Manager 노드 검증
 */
export async function validateWorkflow(workflow: Workflow): Promise<WorkflowValidateResponse> {
  const response = await fetch(`${API_BASE}/workflows/validate`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(workflow),
  })

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
  }

  return await response.json()
}

/**
 * 워크플로우 세션 정보
 */
export interface WorkflowSession {
  session_id: string
  workflow: Workflow
  initial_input: string
  project_path: string | null  // 프로젝트 경로 (세션 복원용)
  status: "running" | "completed" | "error" | "cancelled"
  current_node_id: string | null
  node_outputs: Record<string, string>
  node_inputs: Record<string, string>  // 노드별 입력 (디버깅용)
  logs: WorkflowExecutionEvent[]
  start_time: string
  end_time: string | null
  error: string | null
}

/**
 * 워크플로우 세션 조회
 */
export async function getWorkflowSession(sessionId: string): Promise<WorkflowSession> {
  const response = await fetch(`${API_BASE}/workflows/sessions/${sessionId}`)

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
  }

  return await response.json()
}

/**
 * 워크플로우 실행 취소
 */
export async function cancelWorkflowSession(sessionId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/workflows/sessions/${sessionId}/cancel`, {
    method: "POST",
  })

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
  }
}

/**
 * 사용자 입력을 Worker에게 전달 (Human-in-the-Loop)
 */
export async function sendUserInput(sessionId: string, answer: string): Promise<void> {
  const response = await fetch(`${API_BASE}/workflows/sessions/${sessionId}/user-input`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ answer }),
  })

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
  }
}

/**
 * 노드의 세션 목록 조회
 */
export interface NodeSession {
  session_id: string
  agent_name: string
  created_at: string
  last_used_at: string
  is_current: boolean
}

export interface NodeSessionsResponse {
  node_id: string
  agent_name: string
  current_session_id: string | null
  session_history: NodeSession[]
}

export async function getNodeSessions(nodeId: string): Promise<NodeSessionsResponse> {
  const response = await fetch(`${API_BASE}/workflows/nodes/${nodeId}/sessions`, {
    method: "GET",
  })

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
  }

  return await response.json()
}

/**
 * 노드에 추가 프롬프트를 전달하여 대화 계속하기 (Proactive)
 */
export async function continueNodeConversation(nodeId: string, prompt: string): Promise<{ session_id: string; node_id: string }> {
  const response = await fetch(`${API_BASE}/workflows/nodes/${nodeId}/continue`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ prompt }),
  })

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
  }

  const data = await response.json()
  return {
    session_id: data.session_id,
    node_id: data.node_id,
  }
}

/**
 * 워크플로우 세션 삭제
 */
export async function deleteWorkflowSession(sessionId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/workflows/sessions/${sessionId}`, {
    method: "DELETE",
  })

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
  }
}

/**
 * 모든 노드 세션 초기화
 */
export async function clearNodeSessions(): Promise<{
  message: string
  deleted_sessions: number
}> {
  const response = await fetch(`${API_BASE}/workflows/clear-node-sessions`, {
    method: "POST",
  })

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
  }

  return response.json()
}

/**
 * 프로젝트 세션 데이터 비우기
 */
export async function clearProjectSessions(): Promise<{
  message: string
  deleted_files: number
  freed_space_mb: number
}> {
  const response = await fetch(`${API_BASE}/projects/sessions`, {
    method: "DELETE",
  })

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
  }

  return await response.json()
}

/**
 * 프로젝트 로그 파일 비우기
 */
export async function clearProjectLogs(): Promise<{
  message: string
  deleted_files: number
  freed_space_mb: number
}> {
  const response = await fetch(`${API_BASE}/projects/logs`, {
    method: "DELETE",
  })

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
  }

  return await response.json()
}

/**
 * 프로젝트 보고서 파일 비우기
 */
export async function clearProjectReports(): Promise<{
  message: string
  deleted_files: number
  freed_space_mb: number
}> {
  const response = await fetch(`${API_BASE}/projects/reports`, {
    method: "DELETE",
  })

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
  }

  return await response.json()
}

// ==================== 커스텀 워커 API ====================

/**
 * 커스텀 워커 정보
 */
export interface CustomWorkerInfo {
  name: string
  role: string
  allowed_tools: string[]
  model: string
  thinking: boolean
  prompt_preview: string
}

/**
 * 커스텀 워커 생성 요청
 */
export interface CustomWorkerGenerateRequest {
  worker_requirements: string
  session_id?: string
}

/**
 * 커스텀 워커 저장 요청
 */
export interface CustomWorkerSaveRequest {
  project_path: string
  worker_name: string
  role: string
  prompt_content: string
  allowed_tools: string[]
  model: string
  thinking: boolean
}

/**
 * 커스텀 워커 프롬프트 생성 (SSE 스트리밍)
 *
 * @param workerRequirements 워커 요구사항
 * @param onData 데이터 콜백
 * @param onComplete 완료 콜백
 * @param onError 에러 콜백
 * @param signal AbortSignal (연결 중단용)
 * @returns 세션 ID
 */
export async function generateCustomWorker(
  workerRequirements: string,
  onData: (chunk: string) => void,
  onComplete: (finalOutput: string) => void,
  onError: (error: string) => void,
  signal?: AbortSignal,
  sessionId?: string
): Promise<string | null> {
  const requestBody: CustomWorkerGenerateRequest = {
    worker_requirements: workerRequirements,
    session_id: sessionId,
  }

  const response = await fetch(`${API_BASE}/custom-workers/generate`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'text/event-stream',
    },
    body: JSON.stringify(requestBody),
    signal,
  })

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`)
  }

  const returnedSessionId = response.headers.get('X-Session-ID')

  const reader = response.body?.getReader()
  if (!reader) {
    throw new Error('응답 본문을 읽을 수 없습니다')
  }

  const decoder = new TextDecoder('utf-8')
  let buffer = ''
  let accumulatedOutput = ''

  try {
    while (true) {
      const { done, value } = await reader.read()

      if (done) {
        onComplete(accumulatedOutput)
        break
      }

      const chunk = decoder.decode(value, { stream: true })
      buffer += chunk

      const messages = buffer.split(/\r\n\r\n|\n\n/)
      buffer = messages.pop() || ''

      for (const message of messages) {
        if (!message.trim()) continue

        const lines = message.split(/\r\n|\n/)
        let dataContent = ''

        for (const line of lines) {
          const trimmedLine = line.trim()
          if (trimmedLine.startsWith('data:')) {
            const lineData = trimmedLine.substring(5).trim()
            if (dataContent) {
              dataContent += '\n' + lineData
            } else {
              dataContent = lineData
            }
          }
        }

        if (!dataContent) continue

        // [DONE] 시그널
        if (dataContent === '[DONE]') {
          onComplete(accumulatedOutput)
          return returnedSessionId
        }

        // ERROR 시그널
        if (dataContent.startsWith('ERROR:')) {
          const errorMsg = dataContent.substring(7)
          onError(errorMsg)
          return returnedSessionId
        }

        // 일반 데이터 청크
        accumulatedOutput += dataContent
        onData(dataContent)
      }
    }
  } catch (error) {
    if (error instanceof Error && error.name === 'AbortError') {
      onComplete(accumulatedOutput)
      return returnedSessionId
    }
    const errorMsg = error instanceof Error ? error.message : String(error)
    onError(errorMsg)
    return returnedSessionId
  } finally {
    reader.releaseLock()
  }

  return returnedSessionId
}

/**
 * 커스텀 워커 저장
 */
export async function saveCustomWorker(
  request: CustomWorkerSaveRequest
): Promise<{
  success: boolean
  message: string
  prompt_path: string
}> {
  const response = await fetch(`${API_BASE}/custom-workers/save`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  })

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
  }

  return await response.json()
}

/**
 * 커스텀 워커 목록 조회
 */
export async function getCustomWorkers(
  projectPath: string
): Promise<CustomWorkerInfo[]> {
  const response = await fetch(
    `${API_BASE}/custom-workers?project_path=${encodeURIComponent(projectPath)}`
  )

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
  }

  const data = await response.json()
  return data.workers
}

/**
 * 커스텀 워커 삭제
 */
export async function deleteCustomWorker(
  workerName: string,
  projectPath: string
): Promise<void> {
  const response = await fetch(
    `${API_BASE}/custom-workers/${workerName}?project_path=${encodeURIComponent(projectPath)}`,
    {
      method: 'DELETE',
    }
  )

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
  }
}

// ==================== Display Config API ====================

/**
 * Display 설정
 */
export interface DisplayConfig {
  left_sidebar_open: boolean
  right_sidebar_open: boolean
  expanded_sections: string[]
}

/**
 * Display 설정 로드
 */
export async function loadDisplayConfig(): Promise<DisplayConfig> {
  const response = await fetch(`${API_BASE}/projects/display-config`)

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
  }

  const data = await response.json()
  return data.config
}

/**
 * Display 설정 저장
 */
export async function saveDisplayConfig(config: DisplayConfig): Promise<{
  message: string
  config_path: string
}> {
  const response = await fetch(`${API_BASE}/projects/display-config`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ config }),
  })

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
  }

  return await response.json()
}

// ==================== 워크플로우 설계 API ====================

/**
 * 워크플로우 설계 요청
 */
export interface WorkflowDesignRequest {
  requirements: string
  session_id?: string
  current_workflow?: Workflow | null
  mode?: 'create' | 'improve'
}

/**
 * 워크플로우 자동 설계 (SSE 스트리밍)
 *
 * workflow_designer를 실행하여 요구사항으로부터 워크플로우를 자동 설계합니다.
 *
 * @param requirements 워크플로우 요구사항
 * @param onData 데이터 콜백
 * @param onComplete 완료 콜백
 * @param onError 에러 콜백
 * @param signal AbortSignal (연결 중단용)
 * @param sessionId 세션 ID (선택적)
 * @param currentWorkflow 현재 워크플로우 (개선 모드일 때)
 * @param mode 워크플로우 설계 모드 (create | improve)
 * @returns 세션 ID
 */
export async function designWorkflow(
  requirements: string,
  onData: (chunk: string) => void,
  onComplete: (finalOutput: string) => void,
  onError: (error: string) => void,
  signal?: AbortSignal,
  sessionId?: string,
  currentWorkflow?: Workflow | null,
  mode: 'create' | 'improve' = 'create'
): Promise<string | null> {
  const requestBody: WorkflowDesignRequest = {
    requirements,
    session_id: sessionId,
    current_workflow: currentWorkflow,
    mode,
  }

  const response = await fetch(`${API_BASE}/workflows/design`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'text/event-stream',
    },
    body: JSON.stringify(requestBody),
    signal,
  })

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`)
  }

  const returnedSessionId = response.headers.get('X-Session-ID')

  const reader = response.body?.getReader()
  if (!reader) {
    throw new Error('응답 본문을 읽을 수 없습니다')
  }

  const decoder = new TextDecoder('utf-8')
  let buffer = ''
  let accumulatedOutput = ''

  try {
    while (true) {
      const { done, value } = await reader.read()

      if (done) {
        onComplete(accumulatedOutput)
        break
      }

      const chunk = decoder.decode(value, { stream: true })
      buffer += chunk

      const messages = buffer.split(/\r\n\r\n|\n\n/)
      buffer = messages.pop() || ''

      for (const message of messages) {
        if (!message.trim()) continue

        const lines = message.split(/\r\n|\n/)
        let dataContent = ''

        for (const line of lines) {
          const trimmedLine = line.trim()
          if (trimmedLine.startsWith('data:')) {
            const lineData = trimmedLine.substring(5).trim()
            if (dataContent) {
              dataContent += '\n' + lineData
            } else {
              dataContent = lineData
            }
          }
        }

        if (!dataContent) continue

        // [DONE] 시그널
        if (dataContent === '[DONE]') {
          onComplete(accumulatedOutput)
          return returnedSessionId
        }

        // ERROR 시그널
        if (dataContent.startsWith('ERROR:')) {
          const errorMsg = dataContent.substring(7)
          onError(errorMsg)
          return returnedSessionId
        }

        // 일반 데이터 청크
        accumulatedOutput += dataContent
        onData(dataContent)
      }
    }
  } catch (error) {
    if (error instanceof Error && error.name === 'AbortError') {
      onComplete(accumulatedOutput)
      return returnedSessionId
    }
    const errorMsg = error instanceof Error ? error.message : String(error)
    onError(errorMsg)
    return returnedSessionId
  } finally {
    reader.releaseLock()
  }

  return returnedSessionId
}

