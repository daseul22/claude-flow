/**
 * 워크플로우 상태 관리 (Zustand)
 *
 * React Flow의 노드 및 엣지 상태를 관리합니다.
 */

import { create } from 'zustand'
import { WorkflowNode, WorkflowEdge, Workflow, WorkflowValidationError } from '@/lib/api'

export type NodeExecutionStatus = 'idle' | 'running' | 'completed' | 'error'

export interface NodeExecutionMeta {
  status: NodeExecutionStatus
  startTime?: number
  endTime?: number
  elapsedTime?: number
  tokenUsage?: {
    input_tokens: number
    output_tokens: number
    total_tokens: number
  }
  error?: string
}

export interface LogItem {
  nodeId: string
  type: 'start' | 'input' | 'execution' | 'output' | 'complete' | 'error'
  message: string
  timestamp: number
}

export interface PendingUserInput {
  nodeId: string
  question: string
  sessionId: string
}

interface WorkflowExecutionState {
  isExecuting: boolean
  currentNodeId: string | null
  nodeOutputs: Record<string, string>
  nodeInputs: Record<string, string>  // 노드별 입력 (디버깅용)
  nodeMeta: Record<string, NodeExecutionMeta>
  logs: LogItem[]
  totalTokenUsage: {
    input_tokens: number
    output_tokens: number
    total_tokens: number
  }
  pendingUserInput: PendingUserInput | null  // Human-in-the-Loop
}

interface WorkflowStore {
  // 워크플로우 정의
  nodes: WorkflowNode[]
  edges: WorkflowEdge[]
  workflowName: string
  workflowDescription: string
  currentWorkflowFileName: string  // 파일 시스템에서 사용하는 워크플로우 이름

  // 선택된 노드
  selectedNodeId: string | null

  // 복사된 노드 (복사/붙여넣기)
  copiedNode: WorkflowNode | null

  // 실행 상태
  execution: WorkflowExecutionState

  // 검증 상태
  validationErrors: WorkflowValidationError[]
  isValidating: boolean

  // 노드/엣지 조작
  setNodes: (nodes: WorkflowNode[]) => void
  setEdges: (edges: WorkflowEdge[]) => void
  addNode: (node: WorkflowNode) => void
  updateNode: (nodeId: string, data: Partial<WorkflowNode['data']>) => void
  updateNodePosition: (nodeId: string, position: { x: number; y: number }) => void
  deleteNode: (nodeId: string) => void
  addEdge: (edge: WorkflowEdge) => void
  deleteEdge: (edgeId: string) => void

  // 노드 선택
  setSelectedNodeId: (nodeId: string | null) => void
  getSelectedNode: () => WorkflowNode | null

  // 복사/붙여넣기
  copyNode: (nodeId: string) => void
  pasteNode: () => WorkflowNode | null

  // 워크플로우 메타데이터
  setWorkflowName: (name: string) => void
  setWorkflowDescription: (description: string) => void
  setCurrentWorkflowFileName: (fileName: string) => void

  // 워크플로우 전체 로드/저장
  loadWorkflow: (workflow: Workflow) => void
  getWorkflow: () => Workflow
  clearWorkflow: () => void

  // 실행 상태 관리
  startExecution: () => void
  stopExecution: () => void
  setCurrentNode: (nodeId: string | null) => void
  setNodeInput: (nodeId: string, input: string) => void
  addNodeOutput: (nodeId: string, output: string) => void
  addLog: (nodeId: string, type: WorkflowExecutionState['logs'][0]['type'], message: string) => void
  clearExecution: () => void

  // Human-in-the-Loop
  setPendingUserInput: (input: PendingUserInput | null) => void
  clearPendingUserInput: () => void

  // 노드별 실행 상태 관리
  setNodeStatus: (nodeId: string, status: NodeExecutionStatus) => void
  setNodeStartTime: (nodeId: string, timestamp: number) => void
  setNodeCompleted: (nodeId: string, elapsedTime: number, tokenUsage?: NodeExecutionMeta['tokenUsage']) => void
  setNodeError: (nodeId: string, error: string) => void
  getNodeMeta: (nodeId: string) => NodeExecutionMeta | null

  // 검증 상태 관리
  setValidationErrors: (errors: WorkflowValidationError[]) => void
  setIsValidating: (isValidating: boolean) => void
  clearValidationErrors: () => void
  getValidationErrorsForNode: (nodeId: string) => WorkflowValidationError[]

  // 세션 복원
  restoreFromSession: (session: any) => void
}

const initialExecutionState: WorkflowExecutionState = {
  isExecuting: false,
  currentNodeId: null,
  nodeOutputs: {},
  nodeInputs: {},  // 노드별 입력 초기화
  nodeMeta: {},
  logs: [],
  totalTokenUsage: {
    input_tokens: 0,
    output_tokens: 0,
    total_tokens: 0,
  },
  pendingUserInput: null,  // Human-in-the-Loop
}

export const useWorkflowStore = create<WorkflowStore>((set, get) => ({
  // 초기 상태
  nodes: [],
  edges: [],
  workflowName: '새 프로젝트',
  workflowDescription: '',
  currentWorkflowFileName: 'default',
  selectedNodeId: null,
  copiedNode: null,
  execution: initialExecutionState,
  validationErrors: [],
  isValidating: false,

  // 노드/엣지 조작
  setNodes: (nodes) => set({ nodes }),
  setEdges: (edges) => set({ edges }),

  addNode: (node) =>
    set((state) => ({ nodes: [...state.nodes, node] })),

  updateNode: (nodeId, data) =>
    set((state) => {
      // 변경된 노드만 새로 생성하고, 나머지는 기존 참조 유지 (재렌더링 최적화)
      const targetNode = state.nodes.find(n => n.id === nodeId)
      if (!targetNode) return state

      const updatedNode = { ...targetNode, data: { ...targetNode.data, ...data } }

      // 노드 배열에서 변경된 노드만 교체
      const newNodes = state.nodes.map((node) =>
        node.id === nodeId ? updatedNode : node
      )

      return { nodes: newNodes }
    }),

  updateNodePosition: (nodeId, position) =>
    set((state) => {
      // 변경된 노드만 새로 생성하고, 나머지는 기존 참조 유지
      const targetNode = state.nodes.find(n => n.id === nodeId)
      if (!targetNode) return state

      const updatedNode = { ...targetNode, position }

      const newNodes = state.nodes.map((node) =>
        node.id === nodeId ? updatedNode : node
      )

      return { nodes: newNodes }
    }),

  deleteNode: (nodeId) =>
    set((state) => ({
      nodes: state.nodes.filter((node) => node.id !== nodeId),
      edges: state.edges.filter(
        (edge) => edge.source !== nodeId && edge.target !== nodeId
      ),
      // 삭제된 노드가 선택되어 있었다면 선택 해제
      selectedNodeId: state.selectedNodeId === nodeId ? null : state.selectedNodeId,
    })),

  addEdge: (edge) =>
    set((state) => ({ edges: [...state.edges, edge] })),

  deleteEdge: (edgeId) =>
    set((state) => ({
      edges: state.edges.filter((edge) => edge.id !== edgeId),
    })),

  // 노드 선택
  setSelectedNodeId: (nodeId) => set({ selectedNodeId: nodeId }),

  getSelectedNode: () => {
    const state = get()
    if (!state.selectedNodeId) return null
    return state.nodes.find((node) => node.id === state.selectedNodeId) || null
  },

  // 복사/붙여넣기
  copyNode: (nodeId) => {
    const state = get()
    const nodeToCopy = state.nodes.find((node) => node.id === nodeId)
    if (!nodeToCopy) {
      console.warn(`[workflowStore] 노드를 찾을 수 없습니다: ${nodeId}`)
      return
    }
    set({ copiedNode: nodeToCopy })
    console.log('[workflowStore] 노드 복사됨:', nodeId)
  },

  pasteNode: () => {
    const state = get()
    if (!state.copiedNode) {
      console.warn('[workflowStore] 복사된 노드가 없습니다')
      return null
    }

    // 새 노드 ID 생성
    const newNodeId = `${state.copiedNode.type}-${Date.now()}`

    // 새 노드 위치 (원본에서 오프셋)
    const newPosition = {
      x: state.copiedNode.position.x + 50,
      y: state.copiedNode.position.y + 50,
    }

    // 새 노드 생성
    const newNode: WorkflowNode = {
      ...state.copiedNode,
      id: newNodeId,
      position: newPosition,
    }

    // 노드 추가
    set((state) => ({
      nodes: [...state.nodes, newNode],
      selectedNodeId: newNodeId,  // 새 노드 선택
    }))

    console.log('[workflowStore] 노드 붙여넣기 완료:', newNodeId)
    return newNode
  },

  // 워크플로우 메타데이터
  setWorkflowName: (name) => set({ workflowName: name }),
  setWorkflowDescription: (description) => set({ workflowDescription: description }),
  setCurrentWorkflowFileName: (fileName) => set({ currentWorkflowFileName: fileName }),

  // 워크플로우 전체 로드/저장
  loadWorkflow: (workflow) => {
    // 유효하지 않은 엣지 필터링 (존재하지 않는 노드를 참조하는 엣지 제거)
    const nodeIds = new Set(workflow.nodes.map(node => node.id))
    const validEdges = workflow.edges.filter(edge => {
      const isValid = nodeIds.has(edge.source) && nodeIds.has(edge.target)
      if (!isValid) {
        console.warn(`[워크플로우 로드] 유효하지 않은 엣지 발견: ${edge.id} (source: ${edge.source}, target: ${edge.target})`)
      }
      return isValid
    })

    set({
      nodes: workflow.nodes,
      edges: validEdges,
      workflowName: workflow.name,
      workflowDescription: workflow.description || '',
    })
  },

  getWorkflow: () => {
    const state = get()

    // 유효하지 않은 엣지 필터링 (존재하지 않는 노드를 참조하는 엣지 제거)
    const nodeIds = new Set(state.nodes.map(node => node.id))
    const validEdges = state.edges.filter(edge => {
      const isValid = nodeIds.has(edge.source) && nodeIds.has(edge.target)
      if (!isValid) {
        console.warn(`[워크플로우] 유효하지 않은 엣지 발견: ${edge.id} (source: ${edge.source}, target: ${edge.target})`)
      }
      return isValid
    })

    return {
      name: state.workflowName,
      description: state.workflowDescription,
      nodes: state.nodes,
      edges: validEdges,
    }
  },

  clearWorkflow: () =>
    set({
      nodes: [],
      edges: [],
      workflowName: '새 프로젝트',
      workflowDescription: '',
      currentWorkflowFileName: 'default',
      execution: initialExecutionState,
    }),

  // 실행 상태 관리
  startExecution: () =>
    set((state) => ({
      execution: {
        ...state.execution,
        isExecuting: true,
        currentNodeId: null,
        nodeOutputs: {},
        nodeInputs: {},  // 노드 입력 초기화
        logs: [
          {
            nodeId: '',
            type: 'start',
            message: '🚀 워크플로우 실행 시작...',
            timestamp: Date.now(),
          }
        ],
      },
    })),

  stopExecution: () =>
    set((state) => ({
      execution: {
        ...state.execution,
        isExecuting: false,
        currentNodeId: null,
        // 모든 노드 상태 초기화 (실행 중단 시)
        nodeMeta: Object.keys(state.execution.nodeMeta).reduce((acc, nodeId) => {
          acc[nodeId] = {
            ...state.execution.nodeMeta[nodeId],
            status: 'idle' as NodeExecutionStatus,
          }
          return acc
        }, {} as Record<string, NodeExecutionMeta>),
      },
      // 노드 데이터의 isExecuting 플래그도 초기화
      nodes: state.nodes.map(node => ({
        ...node,
        data: {
          ...node.data,
          isExecuting: false,
        }
      })),
    })),

  setCurrentNode: (nodeId) =>
    set((state) => ({
      execution: {
        ...state.execution,
        currentNodeId: nodeId,
      },
    })),

  addNodeOutput: (nodeId, output) =>
    set((state) => ({
      execution: {
        ...state.execution,
        nodeOutputs: {
          ...state.execution.nodeOutputs,
          [nodeId]: (state.execution.nodeOutputs[nodeId] || '') + output,
        },
      },
    })),

  setNodeInput: (nodeId, input) =>
    set((state) => ({
      execution: {
        ...state.execution,
        nodeInputs: {
          ...state.execution.nodeInputs,
          [nodeId]: input,
        },
      },
    })),

  addLog: (nodeId, type, message) => {
    console.log('[workflowStore] addLog 호출:', { nodeId, type, message })

    set((state) => {
      const newLog = {
        nodeId,
        type,
        message,
        timestamp: Date.now(),
      }
      const newLogs = [...state.execution.logs, newLog]

      console.log('[workflowStore] logs 업데이트:', {
        이전: state.execution.logs.length,
        이후: newLogs.length,
        마지막_로그: newLog
      })

      return {
        execution: {
          ...state.execution,
          logs: newLogs,
        },
      }
    })
  },

  clearExecution: () =>
    set({
      execution: initialExecutionState,
    }),

  // Human-in-the-Loop 구현
  setPendingUserInput: (input) =>
    set((state) => ({
      execution: {
        ...state.execution,
        pendingUserInput: input,
      },
    })),

  clearPendingUserInput: () =>
    set((state) => ({
      execution: {
        ...state.execution,
        pendingUserInput: null,
      },
    })),

  // 노드별 실행 상태 관리 구현
  setNodeStatus: (nodeId, status) =>
    set((state) => ({
      execution: {
        ...state.execution,
        nodeMeta: {
          ...state.execution.nodeMeta,
          [nodeId]: {
            ...(state.execution.nodeMeta[nodeId] || { status: 'idle' }),
            status,
          },
        },
      },
    })),

  setNodeStartTime: (nodeId, timestamp) =>
    set((state) => ({
      execution: {
        ...state.execution,
        nodeMeta: {
          ...state.execution.nodeMeta,
          [nodeId]: {
            ...(state.execution.nodeMeta[nodeId] || { status: 'idle' }),
            status: 'running',
            startTime: timestamp,
          },
        },
      },
    })),

  setNodeCompleted: (nodeId, elapsedTime, tokenUsage) =>
    set((state) => {
      console.log('[workflowStore] setNodeCompleted 호출:', {
        nodeId,
        elapsedTime,
        tokenUsage,
      })

      const updatedMeta = {
        ...state.execution.nodeMeta,
        [nodeId]: {
          ...(state.execution.nodeMeta[nodeId] || { status: 'idle' }),
          status: 'completed' as NodeExecutionStatus,
          endTime: Date.now(),
          elapsedTime,
          tokenUsage,
        },
      }

      // 전체 토큰 사용량 업데이트
      const newTotalTokenUsage = { ...state.execution.totalTokenUsage }
      if (tokenUsage) {
        newTotalTokenUsage.input_tokens += tokenUsage.input_tokens
        newTotalTokenUsage.output_tokens += tokenUsage.output_tokens
        newTotalTokenUsage.total_tokens += tokenUsage.total_tokens
      }

      console.log('[workflowStore] 업데이트된 nodeMeta:', updatedMeta[nodeId])

      return {
        execution: {
          ...state.execution,
          nodeMeta: updatedMeta,
          totalTokenUsage: newTotalTokenUsage,
        },
      }
    }),

  setNodeError: (nodeId, error) =>
    set((state) => ({
      execution: {
        ...state.execution,
        nodeMeta: {
          ...state.execution.nodeMeta,
          [nodeId]: {
            ...(state.execution.nodeMeta[nodeId] || { status: 'idle' }),
            status: 'error',
            endTime: Date.now(),
            error,
          },
        },
      },
    })),

  getNodeMeta: (nodeId) => {
    const state = get()
    return state.execution.nodeMeta[nodeId] || null
  },

  // 검증 상태 관리
  setValidationErrors: (errors) => set({ validationErrors: errors }),

  setIsValidating: (isValidating) => set({ isValidating }),

  clearValidationErrors: () => set({ validationErrors: [] }),

  getValidationErrorsForNode: (nodeId) => {
    const state = get()
    return state.validationErrors.filter((error) => error.node_id === nodeId)
  },

  // 세션 복원
  restoreFromSession: (session) => {
    console.log('[workflowStore] 세션 복원 시작:', session.session_id)

    // workflow_complete 이벤트 확인 (실제 완료 여부 판단)
    const hasWorkflowComplete = session.logs.some((log: any) => log.event_type === 'workflow_complete')
    const hasWorkflowError = session.logs.some((log: any) => log.event_type === 'workflow_error' || log.event_type === 'node_error')

    // 실행 상태 결정
    // 1. workflow_complete 이벤트가 있으면 무조건 완료
    // 2. error 이벤트가 있으면 에러 상태
    // 3. 그 외에는 세션 상태 따름
    const isStillRunning = !hasWorkflowComplete && !hasWorkflowError && session.status === 'running'

    console.log('[workflowStore] 실행 상태 판단:', {
      hasWorkflowComplete,
      hasWorkflowError,
      sessionStatus: session.status,
      isStillRunning,
    })

    // 실행 상태 복원
    const nodeMeta: Record<string, NodeExecutionMeta> = {}

    // 로그를 바탕으로 노드별 실행 상태 재구성
    for (const log of session.logs) {
      const nodeId = log.node_id

      if (log.event_type === 'node_start') {
        nodeMeta[nodeId] = {
          status: isStillRunning && session.current_node_id === nodeId ? 'running' : 'completed',
          startTime: new Date(log.timestamp || Date.now()).getTime(),
        }
      } else if (log.event_type === 'node_complete') {
        if (nodeMeta[nodeId]) {
          nodeMeta[nodeId].status = 'completed'
          nodeMeta[nodeId].endTime = new Date(log.timestamp || Date.now()).getTime()
          nodeMeta[nodeId].elapsedTime = log.elapsed_time
          nodeMeta[nodeId].tokenUsage = log.token_usage

          console.log('[workflowStore] 세션 복원 - node_complete:', {
            nodeId,
            elapsed_time: log.elapsed_time,
            token_usage: log.token_usage,
          })
        }
      } else if (log.event_type === 'node_error') {
        if (nodeMeta[nodeId]) {
          nodeMeta[nodeId].status = 'error'
          nodeMeta[nodeId].error = log.data.error
        }
      }
    }

    // 각 노드의 data 속성도 업데이트 (UI 동기화)
    const updatedNodes = session.workflow.nodes.map((node: WorkflowNode) => {
      const meta = nodeMeta[node.id]
      if (!meta) return node

      return {
        ...node,
        data: {
          ...node.data,
          isExecuting: meta.status === 'running',
          isCompleted: meta.status === 'completed',
          hasError: meta.status === 'error',
        }
      }
    })

    // 워크플로우 정의 복원 (업데이트된 노드 포함)
    set({
      workflowName: session.workflow.name,
      workflowDescription: session.workflow.description || '',
      nodes: updatedNodes,
      edges: session.workflow.edges,
    })

    // 실행 상태 복원
    const execution: WorkflowExecutionState = {
      isExecuting: isStillRunning,
      currentNodeId: isStillRunning ? session.current_node_id : null,
      nodeOutputs: session.node_outputs,
      nodeInputs: session.node_inputs || {},  // 노드 입력 복원
      nodeMeta,
      logs: session.logs.map((log: any) => {
        // 이벤트 타입별로 메시지 재구성 (InputNode.tsx의 로직과 동일)
        let message = ''
        const eventType = log.event_type
        const eventData = log.data

        switch (eventType) {
          case 'node_start':
            message = `▶️  ${eventData.agent_name || eventData.node_type || 'Unknown'} 실행 시작`
            break

          case 'node_output':
            message = eventData.chunk || ''
            break

          case 'node_complete':
            message = `✅ ${eventData.agent_name || eventData.node_type || 'Unknown'} 완료`
            if (log.elapsed_time !== undefined) {
              message += ` (${log.elapsed_time.toFixed(1)}초)`
            }
            if (log.token_usage && log.token_usage.total_tokens > 0) {
              message += ` [${log.token_usage.total_tokens.toLocaleString()} tokens]`
            }
            break

          case 'node_error':
            message = `❌ ${eventData.error || 'Unknown error'}`
            break

          case 'workflow_complete':
            message = eventData.message || '🎉 워크플로우 실행 완료'
            break

          default:
            // 기본값: chunk 또는 message 필드 사용
            message = eventData.chunk || eventData.message || ''
        }

        return {
          nodeId: log.node_id,
          type: eventType.replace('node_', '').replace('workflow_', ''),
          message,
          timestamp: new Date(log.timestamp || Date.now()).getTime(),
        }
      }),
      totalTokenUsage: {
        input_tokens: 0,
        output_tokens: 0,
        total_tokens: 0,
      },
      pendingUserInput: null,  // 세션 복원 시 사용자 입력 요청 없음
    }

    // 전체 토큰 사용량 계산
    Object.values(nodeMeta).forEach((meta) => {
      if (meta.tokenUsage) {
        execution.totalTokenUsage.input_tokens += meta.tokenUsage.input_tokens
        execution.totalTokenUsage.output_tokens += meta.tokenUsage.output_tokens
        execution.totalTokenUsage.total_tokens += meta.tokenUsage.total_tokens
      }
    })

    set({ execution })

    console.log('[workflowStore] 세션 복원 완료:', {
      status: session.status,
      currentNodeId: session.current_node_id,
      logsCount: session.logs.length,
      nodeOutputsCount: Object.keys(session.node_outputs).length,
    })
  },
}))
