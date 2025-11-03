/**
 * 오른쪽 사이드바 컴포넌트
 *
 * 탭 형태로 여러 패널을 관리합니다:
 * - 노드 설정 (Node Config)
 * - 실행 로그 (Execution Logs)
 * - 검증 (Validation)
 */

import React, { useEffect, useState } from 'react'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { NodeConfigPanel } from './NodeConfigPanel'
import { ExecutionLogsPanel } from './ExecutionLogsPanel'
import { ValidationErrorsPanel } from './ValidationErrorsPanel'
import { useWorkflowStore } from '@/stores/workflowStore'
import { Settings, FileText, AlertCircle, ChevronRight } from 'lucide-react'
import { Badge } from './ui/badge'

interface RightSidebarProps {
  className?: string
}

export const RightSidebar: React.FC<RightSidebarProps> = ({ className = '' }) => {
  const getSelectedNode = useWorkflowStore((state) => state.getSelectedNode)
  const validationErrors = useWorkflowStore((state) => state.validationErrors)
  const execution = useWorkflowStore((state) => state.execution)

  const [activeTab, setActiveTab] = useState<'node-config' | 'logs' | 'validation'>('node-config')

  // 노드 선택 시 자동으로 노드 설정 탭 활성화
  useEffect(() => {
    const selectedNode = getSelectedNode()
    if (selectedNode) {
      setActiveTab('node-config')
    }
  }, [getSelectedNode])

  // 실행 중일 때는 로그 탭을 자동으로 활성화 (선택사항)
  useEffect(() => {
    if (execution.isExecuting && activeTab !== 'logs') {
      // 실행 시작 시 로그 탭으로 자동 전환 (선택사항)
      // setActiveTab('logs')
    }
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
        <div className="flex-1 overflow-hidden">
          <TabsContent value="node-config" className="h-full m-0 p-0 data-[state=active]:flex data-[state=active]:flex-col">
            <div className="flex-1 overflow-y-auto px-4 py-4">
              <NodeConfigPanel />
            </div>
          </TabsContent>

          <TabsContent value="logs" className="h-full m-0 p-0 data-[state=active]:flex data-[state=active]:flex-col">
            <div className="flex-1 overflow-y-auto px-4 py-4">
              <ExecutionLogsPanel />
            </div>
          </TabsContent>

          <TabsContent value="validation" className="h-full m-0 p-0 data-[state=active]:flex data-[state=active]:flex-col">
            <div className="flex-1 overflow-y-auto px-4 py-4">
              <ValidationErrorsPanel />
            </div>
          </TabsContent>
        </div>
      </Tabs>
    </aside>
  )
}
