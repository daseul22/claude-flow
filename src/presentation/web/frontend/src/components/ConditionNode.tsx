/**
 * Condition 노드 컴포넌트 (조건 분기)
 *
 * 이전 노드의 출력을 평가하여 True/False 경로로 분기합니다.
 */

import { memo } from 'react'
import { Handle, Position, NodeProps } from 'reactflow'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import { GitBranch, Loader2, CheckCircle2, XCircle, Clock } from 'lucide-react'
import { useWorkflowStore } from '@/stores/workflowStore'

interface ConditionNodeData {
  condition_type: string
  condition_value: string
  true_branch_id?: string
  false_branch_id?: string
  max_iterations?: number | null  // 반복 제한 (null이면 반복 안함)
  // 실행 상태
  isExecuting?: boolean
  isCompleted?: boolean
  hasError?: boolean
}

export const ConditionNode = memo(({ id, data, selected }: NodeProps<ConditionNodeData>) => {
  const { condition_type, condition_value } = data

  // Store에서 노드 실행 메타데이터 가져오기 (shallow equality로 최적화)
  const nodeMeta = useWorkflowStore(
    (state) => state.execution.nodeMeta[id],
    (a, b) => {
      if (a === b) return true
      if (!a && !b) return true
      if (!a || !b) return false
      return (
        a.status === b.status &&
        a.elapsedTime === b.elapsedTime
      )
    }
  )

  const status = nodeMeta?.status || 'idle'
  const isExecuting = status === 'running' || data.isExecuting
  const isCompleted = status === 'completed' || data.isCompleted
  const hasError = status === 'error' || data.hasError
  const elapsedTime = nodeMeta?.elapsedTime

  // 상태별 스타일
  let statusClass = 'border-amber-400 bg-amber-50'
  let statusText = ''
  let statusColor = ''

  if (isExecuting) {
    statusClass = 'border-yellow-500 bg-yellow-50'
    statusText = '평가 중...'
    statusColor = 'text-yellow-700'
  } else if (hasError) {
    statusClass = 'border-red-500 bg-red-50'
    statusText = '에러 발생'
    statusColor = 'text-red-700'
  } else if (isCompleted) {
    statusClass = 'border-green-500 bg-green-50'
    statusText = '완료'
    statusColor = 'text-green-700'
  }

  // 조건 타입 표시 텍스트
  const conditionTypeText: Record<string, string> = {
    contains: '포함 검사',
    regex: '정규표현식',
    length: '길이 비교',
    custom: '커스텀 조건',
    llm: 'LLM 판단',
  }

  return (
    <div style={{ width: '260px', display: 'block', boxSizing: 'border-box' }}>
      {/* 입력 핸들 (위쪽 가운데) */}
      <Handle
        type="target"
        position={Position.Top}
        style={{
          background: '#555',
          width: '12px',
          height: '12px',
          border: '2px solid white',
          top: '-6px',
        }}
      />

      <Card
        className={cn(
          'cursor-pointer',
          'shadow-node hover:shadow-node-hover hover:-translate-y-0.5',
          'transition-shadow duration-200',
          statusClass,
          selected && 'ring-2 ring-blue-500 shadow-node-selected',
          // 애니메이션 제거 (번쩍거림 방지)
          hasError && 'animate-shake'
        )}
      >
        <CardHeader className="p-3 pb-2">
          <CardTitle className="text-base flex items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <GitBranch className="h-4 w-4" />
              <span>조건 분기</span>
            </div>
            {isExecuting && <Loader2 className="h-4 w-4 animate-spin" />}
            {isCompleted && <CheckCircle2 className="h-4 w-4 text-green-600" />}
            {hasError && <XCircle className="h-4 w-4 text-red-600" />}
          </CardTitle>
        </CardHeader>

        <CardContent className="p-3 pt-0 space-y-2">
          {/* 조건 타입 */}
          <div className="text-xs text-gray-600">
            <span className="font-medium">타입:</span>{' '}
            {conditionTypeText[condition_type] || condition_type}
          </div>

          {/* 조건 값 */}
          <div className="text-xs text-gray-600">
            <span className="font-medium">조건:</span>{' '}
            <span className="font-mono bg-gray-100 px-1 rounded">
              {condition_value.length > 30
                ? `${condition_value.substring(0, 30)}...`
                : condition_value}
            </span>
          </div>

          {/* 상태 표시 */}
          {statusText && (
            <div className={cn('text-xs font-medium', statusColor)}>{statusText}</div>
          )}

          {/* 실행 시간 표시 */}
          {elapsedTime !== undefined && (
            <Badge variant="outline" className="text-node-xs px-1.5 py-0.5 h-auto border-gray-300">
              <Clock className="h-2.5 w-2.5 mr-0.5" />
              {elapsedTime.toFixed(1)}s
            </Badge>
          )}
        </CardContent>
      </Card>

      {/* 출력 핸들 - True (왼쪽) */}
      <Handle
        type="source"
        position={Position.Left}
        id="true"
        style={{
          background: '#22c55e',
          width: '14px',
          height: '14px',
          border: '2px solid white',
          left: '-7px',
          top: '50%',
        }}
      />
      <div
        style={{
          position: 'absolute',
          left: '-50px',
          top: '50%',
          transform: 'translateY(-50%)',
          fontSize: '11px',
          fontWeight: 600,
          color: '#22c55e',
          pointerEvents: 'none',
        }}
      >
        True
      </div>

      {/* 출력 핸들 - False (오른쪽) */}
      <Handle
        type="source"
        position={Position.Right}
        id="false"
        style={{
          background: '#ef4444',
          width: '14px',
          height: '14px',
          border: '2px solid white',
          right: '-7px',
          top: '50%',
        }}
      />
      <div
        style={{
          position: 'absolute',
          right: '-50px',
          top: '50%',
          transform: 'translateY(-50%)',
          fontSize: '11px',
          fontWeight: 600,
          color: '#ef4444',
          pointerEvents: 'none',
        }}
      >
        False
      </div>
    </div>
  )
})

ConditionNode.displayName = 'ConditionNode'
