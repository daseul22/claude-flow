/**
 * 검증 에러 패널 컴포넌트
 *
 * 워크플로우 검증 에러를 목록으로 표시하고, 클릭 시 해당 노드로 포커스 이동
 */

import { useMemo } from 'react'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { AlertCircle, AlertTriangle, Info, ChevronRight } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useWorkflowStore } from '@/stores/workflowStore'

export const ValidationErrorsPanel: React.FC = () => {
  const validationErrors = useWorkflowStore((state) => state.validationErrors)
  const setSelectedNodeId = useWorkflowStore((state) => state.setSelectedNodeId)
  const nodes = useWorkflowStore((state) => state.nodes)

  // severity별로 그룹핑
  const groupedErrors = useMemo(() => {
    const errors = validationErrors.filter((e) => e.severity === 'error')
    const warnings = validationErrors.filter((e) => e.severity === 'warning')
    const infos = validationErrors.filter((e) => e.severity === 'info')
    return { errors, warnings, infos }
  }, [validationErrors])

  // 노드 이름 가져오기
  const getNodeName = (nodeId: string) => {
    const node = nodes.find((n) => n.id === nodeId)
    if (!node) return nodeId

    // 노드 타입별로 이름 추출
    if (node.type === 'worker' && typeof node.data === 'object' && 'agent_name' in node.data) {
      return node.data.agent_name || nodeId
    } else if (node.type === 'manager') {
      return 'Manager'
    } else if (node.type === 'input') {
      return 'Input'
    }
    return nodeId
  }

  // 노드로 포커스 이동
  const handleErrorClick = (nodeId: string) => {
    if (nodeId) {
      setSelectedNodeId(nodeId)
      // TODO: 캔버스를 해당 노드 위치로 이동 (React Flow의 fitView 사용)
    }
  }

  if (validationErrors.length === 0) {
    return null
  }

  return (
    <Card className="border-2 h-full flex flex-col overflow-hidden">
      <CardHeader className="pb-3 flex-shrink-0">
        <CardTitle className="text-base flex items-center gap-2">
          <AlertCircle className="h-5 w-5 text-red-600" />
          검증 결과
          <span className="text-xs font-normal text-gray-600">
            ({validationErrors.length}개)
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent className="flex-1 p-0 overflow-hidden min-h-0">
        <div className="h-full overflow-y-auto overflow-x-hidden p-6 space-y-3">
        {/* 에러 목록 */}
        {groupedErrors.errors.length > 0 && (
          <div>
            <div className="flex items-center gap-2 mb-2">
              <AlertCircle className="h-4 w-4 text-red-600" />
              <span className="text-sm font-semibold text-red-700">
                에러 ({groupedErrors.errors.length})
              </span>
            </div>
            <div className="space-y-1">
              {groupedErrors.errors.map((error, idx) => (
                <button
                  key={idx}
                  onClick={() => handleErrorClick(error.node_id)}
                  className={cn(
                    'w-full text-left p-2 rounded text-sm transition-colors',
                    'bg-red-50 hover:bg-red-100 border border-red-200',
                    'flex items-start gap-2 group'
                  )}
                >
                  <ChevronRight className="h-4 w-4 text-red-500 mt-0.5 group-hover:translate-x-1 transition-transform" />
                  <div className="flex-1">
                    <div className="font-medium text-red-900">
                      {error.node_id ? `[${getNodeName(error.node_id)}] ` : ''}
                      {error.message}
                    </div>
                    {error.suggestion && (
                      <div className="text-xs text-red-700 mt-1">
                        💡 {error.suggestion}
                      </div>
                    )}
                  </div>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* 경고 목록 */}
        {groupedErrors.warnings.length > 0 && (
          <div>
            <div className="flex items-center gap-2 mb-2">
              <AlertTriangle className="h-4 w-4 text-yellow-600" />
              <span className="text-sm font-semibold text-yellow-700">
                경고 ({groupedErrors.warnings.length})
              </span>
            </div>
            <div className="space-y-1">
              {groupedErrors.warnings.map((warning, idx) => (
                <button
                  key={idx}
                  onClick={() => handleErrorClick(warning.node_id)}
                  className={cn(
                    'w-full text-left p-2 rounded text-sm transition-colors',
                    'bg-yellow-50 hover:bg-yellow-100 border border-yellow-200',
                    'flex items-start gap-2 group'
                  )}
                >
                  <ChevronRight className="h-4 w-4 text-yellow-500 mt-0.5 group-hover:translate-x-1 transition-transform" />
                  <div className="flex-1">
                    <div className="font-medium text-yellow-900">
                      {warning.node_id ? `[${getNodeName(warning.node_id)}] ` : ''}
                      {warning.message}
                    </div>
                    {warning.suggestion && (
                      <div className="text-xs text-yellow-700 mt-1">
                        💡 {warning.suggestion}
                      </div>
                    )}
                  </div>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* 정보 목록 */}
        {groupedErrors.infos.length > 0 && (
          <div>
            <div className="flex items-center gap-2 mb-2">
              <Info className="h-4 w-4 text-blue-600" />
              <span className="text-sm font-semibold text-blue-700">
                정보 ({groupedErrors.infos.length})
              </span>
            </div>
            <div className="space-y-1">
              {groupedErrors.infos.map((info, idx) => (
                <button
                  key={idx}
                  onClick={() => handleErrorClick(info.node_id)}
                  className={cn(
                    'w-full text-left p-2 rounded text-sm transition-colors',
                    'bg-blue-50 hover:bg-blue-100 border border-blue-200',
                    'flex items-start gap-2 group'
                  )}
                >
                  <ChevronRight className="h-4 w-4 text-blue-500 mt-0.5 group-hover:translate-x-1 transition-transform" />
                  <div className="flex-1">
                    <div className="font-medium text-blue-900">
                      {info.node_id ? `[${getNodeName(info.node_id)}] ` : ''}
                      {info.message}
                    </div>
                    {info.suggestion && (
                      <div className="text-xs text-blue-700 mt-1">
                        💡 {info.suggestion}
                      </div>
                    )}
                  </div>
                </button>
              ))}
            </div>
          </div>
        )}
        </div>
      </CardContent>
    </Card>
  )
}
