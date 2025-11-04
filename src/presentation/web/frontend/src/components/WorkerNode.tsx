/**
 * Worker 노드 컴포넌트 (React Flow 커스텀 노드)
 *
 * Worker Agent를 나타내는 노드입니다.
 * - Agent 선택
 * - 작업 템플릿 입력
 * - 실행 상태 표시
 */

import { memo } from 'react'
import { Handle, Position, NodeProps } from 'reactflow'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import { Loader2, CheckCircle2, XCircle, Clock, AlertTriangle, AlertCircle, Info } from 'lucide-react'
import { useWorkflowStore } from '@/stores/workflowStore'
import { WorkflowValidationError } from '@/lib/api'

interface WorkerNodeData {
  agent_name: string
  task_template: string
  config?: Record<string, any>
  // 실행 상태 (옵션 - 레거시, nodeMeta 우선)
  isExecuting?: boolean
  isCompleted?: boolean
  hasError?: boolean
  // 검증 상태
  validationErrors?: WorkflowValidationError[]
  hasValidationError?: boolean
  hasValidationWarning?: boolean
}

export const WorkerNode = memo(({ id, data, selected }: NodeProps<WorkerNodeData>) => {
  const { agent_name } = data

  // Store에서 노드 실행 메타데이터 가져오기 (shallow equality로 최적화)
  const nodeMeta = useWorkflowStore(
    (state) => state.execution.nodeMeta[id],
    (a, b) => {
      // 값이 정확히 같으면 재렌더링 방지
      if (a === b) return true
      // 둘 다 undefined면 같음
      if (!a && !b) return true
      // 하나만 undefined면 다름
      if (!a || !b) return false
      // 각 필드 비교
      return (
        a.status === b.status &&
        a.elapsedTime === b.elapsedTime &&
        a.tokenUsage?.total_tokens === b.tokenUsage?.total_tokens
      )
    }
  )

  // nodeMeta 우선, 없으면 data fallback
  const status = nodeMeta?.status || 'idle'
  const isExecuting = status === 'running' || data.isExecuting
  const isCompleted = status === 'completed' || data.isCompleted
  const hasError = status === 'error' || data.hasError
  const elapsedTime = nodeMeta?.elapsedTime
  const tokenUsage = nodeMeta?.tokenUsage

  // 검증 상태
  const hasValidationError = data.hasValidationError || false
  const hasValidationWarning = data.hasValidationWarning || false
  const validationErrors = data.validationErrors || []

  // Agent별 색상 매핑
  const agentColors: Record<string, { border: string; bg: string; text: string }> = {
    planner: { border: 'border-orange-400', bg: 'bg-orange-50', text: 'text-orange-700' },
    coder: { border: 'border-green-400', bg: 'bg-green-50', text: 'text-green-700' },
    reviewer: { border: 'border-red-400', bg: 'bg-red-50', text: 'text-red-700' },
    tester: { border: 'border-indigo-400', bg: 'bg-indigo-50', text: 'text-indigo-700' },
    committer: { border: 'border-cyan-400', bg: 'bg-cyan-50', text: 'text-cyan-700' },
    ideator: { border: 'border-pink-400', bg: 'bg-pink-50', text: 'text-pink-700' },
    product_manager: { border: 'border-violet-400', bg: 'bg-violet-50', text: 'text-violet-700' },
  }

  // 기본 색상 (agent_name이 매칭되지 않을 때)
  const defaultColors = { border: 'border-gray-400', bg: 'bg-gray-50', text: 'text-gray-700' }
  const colors = agentColors[agent_name] || defaultColors

  // 상태별 스타일 (우선순위: 실행 중 > 에러 > 검증 에러 > 검증 경고 > 완료 > 기본)
  let statusClass = `${colors.border} ${colors.bg}`
  let statusText = ''
  let statusColor = ''
  let statusIcon = null

  if (isExecuting) {
    statusClass = 'border-yellow-500 bg-yellow-50'
    statusText = '실행 중...'
    statusColor = 'text-yellow-700'
  } else if (hasError) {
    statusClass = 'border-red-500 bg-red-50'
    statusText = '에러 발생'
    statusColor = 'text-red-700'
  } else if (hasValidationError) {
    statusClass = 'border-red-600 bg-red-50 border-dashed'
    statusText = '검증 에러'
    statusColor = 'text-red-700'
    statusIcon = <AlertCircle className="h-4 w-4 text-red-600" />
  } else if (hasValidationWarning) {
    statusClass = 'border-yellow-600 bg-yellow-50 border-dashed'
    statusText = '검증 경고'
    statusColor = 'text-yellow-700'
    statusIcon = <AlertTriangle className="h-4 w-4 text-yellow-600" />
  } else if (isCompleted) {
    statusClass = 'border-green-500 bg-green-50'
    statusText = '완료'
    statusColor = 'text-green-700'
  }

  return (
    <div style={{ width: '260px', display: 'block', boxSizing: 'border-box' }}>
      {/* 입력 핸들 (위쪽 가운데) */}
      <Handle
        type="target"
        position={Position.Top}
        id="input"
        style={{
          position: 'absolute',
          top: 0,
          left: '50%',
          transform: 'translate(-50%, -50%)',
          backgroundColor: '#3b82f6',
          width: '12px',
          height: '12px',
          borderRadius: '50%',
          zIndex: 1
        }}
      />

      <Card
        style={{ width: '260px', boxSizing: 'border-box' }}
        className={cn(
          'border-2 cursor-pointer',
          'shadow-node hover:shadow-node-hover hover:-translate-y-0.5',
          'transition-shadow duration-200',
          statusClass,
          selected && 'ring-2 ring-blue-500 shadow-node-selected',
          // 애니메이션 제거 (번쩍거림 방지)
          hasError && 'animate-shake'
        )}
      >
        <CardHeader className="py-2 px-3">
          <CardTitle className="text-sm flex items-center justify-between">
            <span className="flex items-center gap-1.5">
              {isExecuting && <Loader2 className="h-3.5 w-3.5 animate-spin text-yellow-600" />}
              {!isExecuting && isCompleted && !hasError && !hasValidationError && <CheckCircle2 className="h-3.5 w-3.5 text-green-600" />}
              {!isExecuting && hasError && <XCircle className="h-3.5 w-3.5 text-red-600" />}
              {!isExecuting && !isCompleted && !hasError && statusIcon}
              {agent_name || '워커 선택'}
            </span>
            {statusText && (
              <span className={cn('text-[10px] font-normal', statusColor)}>
                {statusText}
              </span>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent className="py-1.5 px-3 space-y-1">
          <div className="text-[11px] text-muted-foreground line-clamp-1">
            {data.task_template?.substring(0, 80) || '작업 템플릿을 입력하세요...'}
            {(data.task_template?.length || 0) > 80 && '...'}
          </div>

          {/* 실행 시간 및 토큰 사용량 표시 */}
          {(elapsedTime !== undefined || (tokenUsage && tokenUsage.total_tokens > 0)) && (
            <div className="flex items-center gap-1.5 flex-wrap">
              {elapsedTime !== undefined && (
                <Badge variant="outline" className="text-node-xs px-1.5 py-0.5 h-auto border-gray-300">
                  <Clock className="h-2.5 w-2.5 mr-0.5" />
                  {elapsedTime.toFixed(1)}s
                </Badge>
              )}
              {tokenUsage && tokenUsage.total_tokens > 0 && (
                <Badge variant="outline" className="text-node-xs px-1.5 py-0.5 h-auto font-mono border-gray-300">
                  {tokenUsage.total_tokens.toLocaleString()} tok
                </Badge>
              )}
            </div>
          )}

          {/* 검증 에러 표시 */}
          {validationErrors.length > 0 && (
            <div className="space-y-1">
              {validationErrors.map((error, idx) => (
                <div
                  key={idx}
                  className={cn(
                    'p-1 rounded text-node-xs flex items-start gap-1',
                    error.severity === 'error' && 'bg-red-100 text-red-800',
                    error.severity === 'warning' && 'bg-yellow-100 text-yellow-800',
                    error.severity === 'info' && 'bg-blue-100 text-blue-800'
                  )}
                >
                  <div className="flex-shrink-0 mt-0.5">
                    {error.severity === 'error' && <AlertCircle className="h-3 w-3" />}
                    {error.severity === 'warning' && <AlertTriangle className="h-3 w-3" />}
                    {error.severity === 'info' && <Info className="h-3 w-3" />}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="font-medium">{error.message}</div>
                    {error.suggestion && (
                      <div className="mt-0.5 opacity-90">{error.suggestion}</div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* 출력 핸들 (아래쪽 가운데) */}
      <Handle
        type="source"
        position={Position.Bottom}
        id="output"
        style={{
          position: 'absolute',
          bottom: 0,
          left: '50%',
          transform: 'translate(-50%, 50%)',
          backgroundColor: '#3b82f6',
          width: '12px',
          height: '12px',
          borderRadius: '50%',
          zIndex: 1
        }}
      />
    </div>
  )
})

WorkerNode.displayName = 'WorkerNode'
