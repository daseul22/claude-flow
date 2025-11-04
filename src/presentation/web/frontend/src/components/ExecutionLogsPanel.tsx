/**
 * 워크플로우 실행 로그 패널
 *
 * 실시간으로 워크플로우 실행 로그를 표시합니다.
 */

import React, { useEffect, useRef, useState, useMemo } from 'react'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { useWorkflowStore } from '@/stores/workflowStore'
import { FileText, Clock, Zap, CheckCircle2, AlertCircle, Info, Filter } from 'lucide-react'
import { ParsedContent } from './ParsedContent'

export const ExecutionLogsPanel: React.FC = () => {
  const { execution, nodes, selectedNodeId: canvasSelectedNodeId } = useWorkflowStore()
  const scrollRef = useRef<HTMLDivElement>(null)

  // 필터 상태
  const [selectedNodeId, setSelectedNodeId] = useState<string>('all')
  const [selectedLogType, setSelectedLogType] = useState<string>('all')
  const [showSystemLogs, setShowSystemLogs] = useState<boolean>(false) // 시스템 로그 기본 숨김

  // 캔버스에서 노드 선택 시 자동으로 필터 적용
  useEffect(() => {
    if (canvasSelectedNodeId) {
      setSelectedNodeId(canvasSelectedNodeId)
    }
  }, [canvasSelectedNodeId])

  // 세션 복원 시 현재 실행 중인 노드로 필터 자동 설정
  useEffect(() => {
    if (execution.isExecuting && execution.currentNodeId) {
      setSelectedNodeId(execution.currentNodeId)
      console.log('[ExecutionLogsPanel] 실행 중인 노드로 필터 자동 설정:', execution.currentNodeId)
    }
  }, [execution.currentNodeId, execution.isExecuting])

  // 새 로그가 추가될 때마다 자동 스크롤
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [execution.logs])

  // 로그 카테고리 분류
  type LogCategory = 'system' | 'agent' | 'user' | 'default'

  const getLogCategory = (logType: string): LogCategory => {
    // 시스템 로그: start, complete, error
    if (['start', 'complete', 'error'].includes(logType)) {
      return 'system'
    }

    // 사용자 입력
    if (logType === 'input') {
      return 'user'
    }

    // 에이전트 응답: execution, output
    if (logType === 'execution' || logType === 'output') {
      return 'agent'
    }

    return 'default'
  }

  // 카테고리별 라벨
  const getCategoryLabel = (category: LogCategory): string => {
    switch (category) {
      case 'system':
        return 'SYSTEM'
      case 'agent':
        return 'AGENT'
      case 'user':
        return 'USER'
      default:
        return ''
    }
  }

  // 카테고리별 라벨 색상
  const getCategoryLabelClass = (category: LogCategory): string => {
    switch (category) {
      case 'system':
        return 'bg-gray-100 text-gray-600'
      case 'agent':
        return 'bg-gray-100 text-gray-700'
      case 'user':
        return 'bg-gray-100 text-gray-700'
      default:
        return 'bg-gray-100 text-gray-600'
    }
  }

  // 로그 타입에 따른 아이콘 및 색상
  const getLogIcon = (type: string, category: LogCategory) => {
    if (category === 'system') {
      switch (type) {
        case 'start':
          return <Zap className="h-4 w-4 text-blue-500" />
        case 'complete':
          return <CheckCircle2 className="h-4 w-4 text-green-500" />
        case 'error':
          return <AlertCircle className="h-4 w-4 text-red-500" />
        default:
          return <Info className="h-4 w-4 text-gray-500" />
      }
    }

    if (category === 'user') {
      return <Info className="h-4 w-4 text-gray-500" />
    }

    // agent
    return <FileText className="h-4 w-4 text-gray-500" />
  }

  const getLogColor = (category: LogCategory) => {
    switch (category) {
      case 'system':
        return 'text-gray-800 bg-white border-l-2 border-gray-200'
      case 'agent':
        return 'text-gray-800 bg-white border-l-2 border-gray-300'
      case 'user':
        return 'text-gray-800 bg-white border-l-2 border-gray-300'
      default:
        return 'text-gray-800 bg-white'
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
      // 시스템 로그 필터
      if (!showSystemLogs) {
        const category = getLogCategory(log.type)
        if (category === 'system') {
          return false
        }
      }
      return true
    })
  }, [execution.logs, selectedNodeId, selectedLogType, showSystemLogs])

  // 전역 tool_use_id → tool_name 매핑 생성
  const toolUseIdToName = useMemo(() => {
    const mapping: Record<string, string> = {}

    execution.logs.forEach((log) => {
      try {
        // JSON 메시지 파싱 시도
        const trimmed = log.message.trim()
        if (trimmed.startsWith('{') && trimmed.includes('"role"')) {
          const data = JSON.parse(trimmed)
          if (data.role === 'assistant' && Array.isArray(data.content)) {
            for (const block of data.content) {
              if (block.type === 'tool_use' && block.id && block.name) {
                mapping[block.id] = block.name
              }
            }
          }
        }
      } catch (e) {
        // JSON 파싱 실패 시 무시
      }
    })

    return mapping
  }, [execution.logs])

  // 로그 그룹화 (1분 단위, 같은 노드/카테고리)
  interface LogGroup {
    timestamp: number
    nodeId: string | null
    category: LogCategory
    logs: typeof execution.logs
  }

  const groupedLogs = useMemo(() => {
    const groups: LogGroup[] = []

    filteredLogs.forEach((log) => {
      const category = getLogCategory(log.type)
      const logTime = new Date(log.timestamp).getTime()

      // 마지막 그룹과 비교 (1분 이내 + 같은 노드 + 같은 카테고리)
      const lastGroup = groups[groups.length - 1]
      const timeDiff = lastGroup ? logTime - lastGroup.timestamp : Infinity
      const isSameNode = lastGroup?.nodeId === log.nodeId
      const isSameCategory = lastGroup?.category === category

      if (lastGroup && timeDiff < 60000 && isSameNode && isSameCategory) {
        // 기존 그룹에 추가
        lastGroup.logs.push(log)
      } else {
        // 새 그룹 생성
        groups.push({
          timestamp: logTime,
          nodeId: log.nodeId,
          category,
          logs: [log]
        })
      }
    })

    return groups
  }, [filteredLogs])

  return (
    <Card className="h-full flex flex-col overflow-hidden">
      <CardHeader className="pb-3 flex-shrink-0">
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
        <div className="flex items-center gap-2 mb-2 flex-wrap">
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
          <label className="flex items-center gap-1 text-sm text-gray-600 cursor-pointer">
            <input
              type="checkbox"
              checked={showSystemLogs}
              onChange={(e) => setShowSystemLogs(e.target.checked)}
              className="rounded"
            />
            <span>시스템 로그</span>
          </label>
          {(selectedNodeId !== 'all' || selectedLogType !== 'all' || !showSystemLogs) && (
            <Badge variant="outline" className="text-xs">
              {filteredLogs.length} / {execution.logs.length}
            </Badge>
          )}
        </div>

        {formatTokenUsage()}
      </CardHeader>
      <CardContent className="flex-1 p-0 overflow-hidden min-h-0">
        <div
          ref={scrollRef}
          className="h-full overflow-y-auto overflow-x-hidden p-4 space-y-2"
        >
          {groupedLogs.length === 0 ? (
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
            groupedLogs.map((group, groupIndex) => {
              const categoryLabel = getCategoryLabel(group.category)
              const firstLog = group.logs[0]
              const isUser = group.category === 'user'

              return (
                <div
                  key={groupIndex}
                  className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}
                >
                  <div
                    className={`flex items-start gap-3 p-3 rounded-lg transition-colors max-w-[85%] ${
                      isUser
                        ? 'bg-blue-50 border-l-2 border-blue-400'
                        : getLogColor(group.category)
                    }`}
                  >
                    {!isUser && (
                      <div className="flex-shrink-0 mt-0.5">{getLogIcon(firstLog.type, group.category)}</div>
                    )}
                    <div className="flex-1 min-w-0 space-y-2">
                      {/* 헤더: 카테고리, 노드, 시간 (그룹당 한번만) */}
                      <div className={`flex items-center gap-2 flex-wrap ${isUser ? 'justify-end' : ''}`}>
                        {categoryLabel && (
                          <span className={`text-xs font-semibold px-2 py-0.5 rounded ${
                            isUser ? 'bg-blue-200 text-blue-800' : getCategoryLabelClass(group.category)
                          }`}>
                            {categoryLabel}
                          </span>
                        )}
                        {group.nodeId && (
                          <Badge variant="outline" className="text-xs">
                            {getNodeName(group.nodeId)}
                          </Badge>
                        )}
                        <span className="text-xs text-muted-foreground flex items-center gap-1">
                          <Clock className="h-3 w-3" />
                          {new Date(group.timestamp).toLocaleTimeString()}
                        </span>
                      </div>

                      {/* 로그 내용들 (채팅처럼 연속으로) */}
                      <div className="space-y-1">
                        {group.logs.map((log, logIndex) => (
                          <ParsedContent key={logIndex} content={log.message} toolUseIdToName={toolUseIdToName} />
                        ))}
                      </div>
                    </div>
                    {isUser && (
                      <div className="flex-shrink-0 mt-0.5">{getLogIcon(firstLog.type, group.category)}</div>
                    )}
                  </div>
                </div>
              )
            })
          )}
        </div>
      </CardContent>
    </Card>
  )
}
