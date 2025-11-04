/**
 * 워크플로우 실행 로그 패널
 *
 * 실시간으로 워크플로우 실행 로그를 표시합니다.
 */

import React, { useEffect, useRef, useState, useMemo } from 'react'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Badge } from '@/components/ui/badge'
import { useWorkflowStore } from '@/stores/workflowStore'
import { FileText, Clock, Zap, CheckCircle2, AlertCircle, Info, Filter } from 'lucide-react'

export const ExecutionLogsPanel: React.FC = () => {
  const { execution, nodes } = useWorkflowStore()
  const scrollRef = useRef<HTMLDivElement>(null)

  // 필터 상태
  const [selectedNodeId, setSelectedNodeId] = useState<string>('all')
  const [selectedLogType, setSelectedLogType] = useState<string>('all')

  // 새 로그가 추가될 때마다 자동 스크롤
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [execution.logs])

  // 로그 타입에 따른 아이콘 및 색상
  const getLogIcon = (type: string) => {
    switch (type) {
      case 'start':
        return <Zap className="h-4 w-4 text-blue-600" />
      case 'complete':
        return <CheckCircle2 className="h-4 w-4 text-green-600" />
      case 'error':
        return <AlertCircle className="h-4 w-4 text-red-600" />
      case 'input':
        return <Info className="h-4 w-4 text-purple-600" />
      default:
        return <FileText className="h-4 w-4 text-gray-600" />
    }
  }

  const getLogColor = (type: string) => {
    switch (type) {
      case 'start':
        return 'text-blue-700 bg-blue-50'
      case 'complete':
        return 'text-green-700 bg-green-50'
      case 'error':
        return 'text-red-700 bg-red-50'
      case 'input':
        return 'text-purple-700 bg-purple-50'
      default:
        return 'text-gray-700 bg-gray-50'
    }
  }

  // 노드 이름 가져오기
  const getNodeName = (nodeId: string) => {
    const node = nodes.find((n) => n.id === nodeId)
    return node?.data.agent_name || node?.type || nodeId
  }

  // 토큰 사용량 포맷팅
  const formatTokenUsage = () => {
    const { input_tokens, output_tokens, total_tokens} = execution.totalTokenUsage
    if (total_tokens === 0) return null
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Zap className="h-3 w-3" />
        <span>
          총 토큰: {total_tokens.toLocaleString()} (입력: {input_tokens.toLocaleString()}, 출력:{' '}
          {output_tokens.toLocaleString()})
        </span>
      </div>
    )
  }

  // 로그별로 노드 ID 목록 추출 (중복 제거)
  const uniqueNodeIds = useMemo(() => {
    const nodeIds = new Set(execution.logs.map(log => log.nodeId).filter(Boolean))
    return Array.from(nodeIds)
  }, [execution.logs])

  // 필터링된 로그
  const filteredLogs = useMemo(() => {
    return execution.logs.filter(log => {
      // 노드 필터
      if (selectedNodeId !== 'all' && log.nodeId !== selectedNodeId) {
        return false
      }
      // 로그 타입 필터
      if (selectedLogType !== 'all' && log.type !== selectedLogType) {
        return false
      }
      return true
    })
  }, [execution.logs, selectedNodeId, selectedLogType])

  return (
    <Card className="h-full flex flex-col">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between mb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <FileText className="h-4 w-4" />
            실행 로그
          </CardTitle>
          {execution.isExecuting && (
            <Badge variant="default" className="animate-pulse">
              실행 중
            </Badge>
          )}
        </div>

        {/* 필터 UI */}
        <div className="flex items-center gap-2 mb-2">
          <Filter className="h-4 w-4 text-muted-foreground" />
          <select
            value={selectedNodeId}
            onChange={(e) => setSelectedNodeId(e.target.value)}
            className="text-sm border rounded px-2 py-1 bg-white"
          >
            <option value="all">모든 노드</option>
            {uniqueNodeIds.map(nodeId => (
              <option key={nodeId} value={nodeId}>
                {getNodeName(nodeId)}
              </option>
            ))}
          </select>
          <select
            value={selectedLogType}
            onChange={(e) => setSelectedLogType(e.target.value)}
            className="text-sm border rounded px-2 py-1 bg-white"
          >
            <option value="all">모든 타입</option>
            <option value="input">입력</option>
            <option value="execution">실행</option>
            <option value="output">출력</option>
            <option value="start">시작</option>
            <option value="complete">완료</option>
            <option value="error">에러</option>
          </select>
          {(selectedNodeId !== 'all' || selectedLogType !== 'all') && (
            <Badge variant="outline" className="text-xs">
              {filteredLogs.length} / {execution.logs.length}
            </Badge>
          )}
        </div>

        {formatTokenUsage()}
      </CardHeader>
      <CardContent className="flex-1 p-0 overflow-hidden">
        <ScrollArea className="h-full">
          <div ref={scrollRef} className="p-4 space-y-2">
            {filteredLogs.length === 0 ? (
              <div className="text-center text-muted-foreground py-8">
                <FileText className="h-12 w-12 mx-auto mb-2 opacity-50" />
                {execution.logs.length === 0 ? (
                  <>
                    <p>실행 로그가 없습니다</p>
                    <p className="text-xs">워크플로우를 실행하면 로그가 표시됩니다</p>
                  </>
                ) : (
                  <>
                    <p>필터 조건에 맞는 로그가 없습니다</p>
                    <p className="text-xs">필터를 변경해보세요</p>
                  </>
                )}
              </div>
            ) : (
              filteredLogs.map((log, index) => (
                <div
                  key={index}
                  className={`flex items-start gap-3 p-3 rounded-lg transition-colors ${getLogColor(log.type)}`}
                >
                  <div className="flex-shrink-0 mt-0.5">{getLogIcon(log.type)}</div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      {log.nodeId && (
                        <Badge variant="outline" className="text-xs">
                          {getNodeName(log.nodeId)}
                        </Badge>
                      )}
                      <span className="text-xs text-muted-foreground flex items-center gap-1">
                        <Clock className="h-3 w-3" />
                        {new Date(log.timestamp).toLocaleTimeString()}
                      </span>
                    </div>
                    <p className="text-sm whitespace-pre-wrap break-words">{log.message}</p>
                  </div>
                </div>
              ))
            )}
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  )
}
