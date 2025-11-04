/**
 * Merge 노드 컴포넌트 (병합)
 *
 * 여러 분기의 출력을 하나로 통합합니다.
 */

import { memo } from 'react'
import { Handle, Position, NodeProps } from 'reactflow'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import { Merge, Loader2, CheckCircle2, XCircle, Clock } from 'lucide-react'
import { useWorkflowStore } from '@/stores/workflowStore'

interface MergeNodeData {
  merge_strategy: string
  separator?: string
  custom_template?: string
  // 실행 상태
  isExecuting?: boolean
  isCompleted?: boolean
  hasError?: boolean
}

export const MergeNode = memo(({ id, data, selected }: NodeProps<MergeNodeData>) => {
  const { merge_strategy, separator } = data

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
  let statusClass = 'border-sky-400 bg-sky-50'
  let statusText = ''
  let statusColor = ''

  if (isExecuting) {
    statusClass = 'border-yellow-500 bg-yellow-50'
    statusText = '병합 중...'
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

  // 병합 전략 표시 텍스트
  const mergeStrategyText: Record<string, string> = {
    concatenate: '연결',
    first: '첫 번째만',
    last: '마지막만',
    custom: '커스텀',
  }

  return (
    <div style={{ width: '260px', display: 'block', boxSizing: 'border-box', position: 'relative' }}>
      {/* 입력 핸들 (위쪽 가운데) - 여러 입력 지원 */}
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
              <Merge className="h-4 w-4" />
              <span>병합 노드</span>
            </div>
            {isExecuting && <Loader2 className="h-4 w-4 animate-spin" />}
            {isCompleted && <CheckCircle2 className="h-4 w-4 text-green-600" />}
            {hasError && <XCircle className="h-4 w-4 text-red-600" />}
          </CardTitle>
        </CardHeader>

        <CardContent className="p-3 pt-0 space-y-2">
          {/* 병합 전략 */}
          <div className="text-xs text-gray-600">
            <span className="font-medium">전략:</span>{' '}
            {mergeStrategyText[merge_strategy] || merge_strategy}
          </div>

          {/* 구분자 (concatenate 전략일 때만) */}
          {merge_strategy === 'concatenate' && separator && (
            <div className="text-xs text-gray-600">
              <span className="font-medium">구분자:</span>{' '}
              <span className="font-mono bg-gray-100 px-1 rounded">
                {separator === '\n\n---\n\n'
                  ? '--- (구분선)'
                  : separator.length > 20
                  ? `${separator.substring(0, 20)}...`
                  : separator}
              </span>
            </div>
          )}

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

      {/* 출력 핸들 (아래쪽 가운데) */}
      <Handle
        type="source"
        position={Position.Bottom}
        style={{
          background: '#555',
          width: '12px',
          height: '12px',
          border: '2px solid white',
          bottom: '-6px',
        }}
      />
    </div>
  )
})

MergeNode.displayName = 'MergeNode'
