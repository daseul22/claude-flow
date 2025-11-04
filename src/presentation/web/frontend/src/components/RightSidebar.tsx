/**
 * 오른쪽 사이드바 컴포넌트
 *
 * 탭 형태로 여러 패널을 관리합니다:
 * - 노드 설정 (Node Config)
 * - 실행 로그 (Execution Logs)
 * - 검증 (Validation)
 */

import React, { useEffect, useState, useRef } from 'react'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { NodeConfigPanel } from './NodeConfigPanel'
import { ExecutionLogsPanel } from './ExecutionLogsPanel'
import { ValidationErrorsPanel } from './ValidationErrorsPanel'
import { useWorkflowStore } from '@/stores/workflowStore'
import { Settings, FileText, AlertCircle } from 'lucide-react'
import { Badge } from './ui/badge'

interface RightSidebarProps {
  className?: string
}

export const RightSidebar: React.FC<RightSidebarProps> = ({ className = '' }) => {
  const getSelectedNode = useWorkflowStore((state) => state.getSelectedNode)
  const validationErrors = useWorkflowStore((state) => state.validationErrors)
  const execution = useWorkflowStore((state) => state.execution)

  const [activeTab, setActiveTab] = useState<'node-config' | 'logs' | 'validation'>('node-config')

  // 이전 실행 상태 추적 (실행 시작 감지용)
  const prevIsExecutingRef = useRef(false)

  // 노드 선택 시 자동으로 노드 설정 탭 활성화 (실행 중이 아닐 때만)
  useEffect(() => {
    const selectedNode = getSelectedNode()
    if (selectedNode && !execution.isExecuting) {
      setActiveTab('node-config')
    }
  }, [getSelectedNode, execution.isExecuting])

  // 실행 시작 시 또는 세션 복원 시에만 로그 탭으로 자동 전환 (한 번만)
  useEffect(() => {
    const wasNotExecuting = !prevIsExecutingRef.current
    const isNowExecuting = execution.isExecuting

    // 실행 상태가 false → true로 변경될 때만 자동 전환
    if (wasNotExecuting && isNowExecuting) {
      setActiveTab('logs')
      console.log('[RightSidebar] 실행 시작/복원 → 로그 탭으로 자동 전환')
    }

    // 이전 상태 업데이트
    prevIsExecutingRef.current = execution.isExecuting
  }, [execution.isExecuting])

  // 검증 오류 개수
  const validationErrorCount = validationErrors.length

  // 실행 로그 개수 (실행 중일 때만 표시)
  const logCount = execution.isExecuting ? execution.logs.length : 0

  return (
    <aside className={`w-[32rem] border-l bg-white flex flex-col overflow-hidden transition-all duration-300 ease-out ${className}`}>
      <Tabs value={activeTab} onValueChange={(value) => setActiveTab(value as any)} className="flex flex-col h-full">
        {/* 탭 헤더 */}
        <TabsList className="w-full grid grid-cols-3 rounded-none border-b bg-gray-50 h-12">
          <TabsTrigger value="node-config" className="flex items-center gap-2 data-[state=active]:bg-white data-[state=active]:shadow-sm">
            <Settings className="h-4 w-4" />
            <span className="hidden sm:inline">노드 설정</span>
          </TabsTrigger>
          <TabsTrigger value="logs" className="flex items-center gap-2 data-[state=active]:bg-white data-[state=active]:shadow-sm relative">
            <FileText className="h-4 w-4" />
            <span className="hidden sm:inline">실행 로그</span>
            {logCount > 0 && (
              <Badge variant="secondary" className="ml-1 h-5 min-w-5 px-1 text-xs">
                {logCount}
              </Badge>
            )}
          </TabsTrigger>
          <TabsTrigger value="validation" className="flex items-center gap-2 data-[state=active]:bg-white data-[state=active]:shadow-sm relative">
            <AlertCircle className="h-4 w-4" />
            <span className="hidden sm:inline">검증</span>
            {validationErrorCount > 0 && (
              <Badge variant="destructive" className="ml-1 h-5 min-w-5 px-1 text-xs">
                {validationErrorCount}
              </Badge>
            )}
          </TabsTrigger>
        </TabsList>

        {/* 탭 내용 */}
        <div className="flex-1 overflow-hidden min-h-0">
          <TabsContent value="node-config" className="h-full m-0 p-0 flex flex-col">
            <div className="flex-1 overflow-y-auto px-4 py-4">
              <NodeConfigPanel />
            </div>
          </TabsContent>

          <TabsContent value="logs" className="h-full m-0 p-0 flex flex-col">
            <div className="h-full px-4 py-4 overflow-hidden flex flex-col">
              <ExecutionLogsPanel />
            </div>
          </TabsContent>

          <TabsContent value="validation" className="h-full m-0 p-0 flex flex-col">
            <div className="h-full px-4 py-4 overflow-hidden flex flex-col">
              <ValidationErrorsPanel />
            </div>
          </TabsContent>
        </div>
      </Tabs>
    </aside>
  )
}
