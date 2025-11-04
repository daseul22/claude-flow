/**
 * Input 노드 설정 컴포넌트
 *
 * 워크플로우 시작점인 Input 노드의 설정을 관리합니다.
 */

import React from 'react'
import { FieldHint } from '@/components/ui/field-hint'
import { Badge } from '@/components/ui/badge'
import { useWorkflowStore } from '@/stores/workflowStore'
import { WorkflowNode } from '@/lib/api'
import { useNodeConfig } from './hooks/useNodeConfig'
import { useAutoSave } from './hooks/useAutoSave'
import { useKeyboardShortcuts } from './hooks/useKeyboardShortcuts'

interface InputNodeConfigProps {
  node: WorkflowNode
}

interface InputNodeData {
  initial_input: string
  parallel_execution?: boolean
}

/**
 * 노드별 실행 로그 컴포넌트 (3가지 로그 타입 분리)
 */

export const InputNodeConfig: React.FC<InputNodeConfigProps> = ({ node }) => {

  // 노드 설정 Hook 사용
  const { data, setData, hasChanges, save, reset } = useNodeConfig<InputNodeData>({
    nodeId: node.id,
    initialData: {
      initial_input: node.data.initial_input || '',
      parallel_execution: node.data.parallel_execution ?? false,
    },
    onValidate: (_data) => {
      const errors: Record<string, string> = {}
      // 빈 입력도 허용 (빈 문자열 전달 가능)
      return errors
    },
  })

  // 자동 저장
  useAutoSave({
    hasChanges,
    onSave: save,
    delay: 3000,
  })

  // 키보드 단축키
  useKeyboardShortcuts({
    handlers: {
      onSave: hasChanges ? save : undefined,
      onReset: hasChanges ? reset : undefined,
    },
  })

  // 입력 필드에서 키 이벤트 전파 방지 (단, 저장 단축키는 예외)
  const handleInputKeyDown = (e: React.KeyboardEvent) => {
    const isMac = navigator.platform.toUpperCase().indexOf('MAC') >= 0
    const cmdOrCtrl = isMac ? e.metaKey : e.ctrlKey

    // Cmd+S / Ctrl+S는 전파 허용 (저장 기능)
    if (cmdOrCtrl && e.key === 's') {
      return // stopPropagation 하지 않고 전파 허용
    }

    e.stopPropagation()
  }

  // 연결 상태 확인
  const edges = useWorkflowStore((state) => state.edges)
  const connectedEdges = edges.filter((e) => e.source === node.id)

  return (
    <div className="h-full overflow-hidden flex flex-col">
      <div className="flex-1 overflow-hidden">
        <div className="h-full overflow-y-auto px-3 pb-3 pt-3 space-y-3">
            {/* 초기 입력 */}
            <div className="space-y-2">
              <label className="text-sm font-medium">초기 입력</label>
              <textarea
                className="w-full p-3 border rounded-md text-sm focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
                rows={10}
                value={data.initial_input}
                onChange={(e) => setData({ ...data, initial_input: e.target.value })}
                onKeyDown={handleInputKeyDown}
                placeholder="아키텍처 패턴 리뷰 해주세요"
              />
              <FieldHint
                hint="이 입력이 연결된 첫 번째 노드로 전달됩니다."
                tooltip="워크플로우를 시작하는 초기 입력입니다. 비어있어도 실행 가능하며, 빈 문자열이 전달됩니다."
              />
            </div>

            {/* 미리보기 */}
            {data.initial_input.trim() && (
              <div className="bg-emerald-50 border border-emerald-200 rounded-md p-3">
                <div className="text-xs font-medium text-emerald-900 mb-2">초기 입력 미리보기</div>
                <div className="text-sm text-gray-700 whitespace-pre-wrap bg-white p-3 rounded border">
                  {data.initial_input}
                </div>
                <div className="text-xs text-emerald-700 mt-2">글자 수: {data.initial_input.length}자</div>
              </div>
            )}

            {/* 연결 상태 */}
            <div className="bg-gray-50 border rounded-md p-3">
              <div className="text-xs font-medium mb-2">연결 상태</div>
              <div className="text-xs text-muted-foreground">
                {connectedEdges.length > 0 ? (
                  <Badge variant="success" className="flex items-center gap-2">
                    <span className="w-2 h-2 bg-green-500 rounded-full"></span>
                    <span>{connectedEdges.length}개 노드에 연결됨</span>
                  </Badge>
                ) : (
                  <Badge variant="warning" className="flex items-center gap-2">
                    <span className="w-2 h-2 bg-yellow-500 rounded-full"></span>
                    <span>연결된 노드 없음 (실행 불가)</span>
                  </Badge>
                )}
              </div>
            </div>

            {/* 병렬 실행 옵션 */}
            <div className="space-y-2 border-t pt-4">
              <label className="text-sm font-medium">병렬 실행</label>
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={data.parallel_execution ?? false}
                  onChange={(e) => setData({ ...data, parallel_execution: e.target.checked })}
                  className="w-4 h-4"
                />
                <span>자식 노드들을 병렬로 실행</span>
              </label>
              <FieldHint
                hint={data.parallel_execution
                  ? '✅ 자식 노드들이 동시에 실행되어 전체 실행 시간이 단축됩니다'
                  : '⚪ 자식 노드들이 순차적으로 실행됩니다'}
                tooltip="이 노드에서 여러 자식 노드로 연결된 경우, 자식 노드들을 병렬로 실행할지 순차적으로 실행할지 선택합니다. 병렬 실행은 실행 시간을 단축시키지만, 노드 간 순서가 보장되지 않습니다."
              />
            </div>
        </div>
      </div>
    </div>
  )
}
