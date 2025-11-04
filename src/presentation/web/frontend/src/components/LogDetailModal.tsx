import { X, Maximize2, Send, Loader2, RefreshCw, History, FileText, Clock, Zap, CheckCircle2, AlertCircle, Info, Filter, Eye, EyeOff, ChevronDown, ChevronUp } from 'lucide-react'
import { useState, useEffect, useMemo, useRef } from 'react'
import { LogItem, useWorkflowStore } from '@/stores/workflowStore'
import { ParsedContent } from './ParsedContent'
import { Button } from './ui/button'
import { Badge } from './ui/badge'
import { Separator } from './ui/separator'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from './ui/select'
import { continueNodeConversation, API_BASE, getNodeSessions, type NodeSession } from '@/lib/api'

interface NodeLogSection {
  nodeId: string
  nodeName: string
  logs: LogItem[]
}

interface LogDetailModalProps {
  isOpen: boolean
  onClose: () => void
  sections: NodeLogSection[]
  title?: string
}

export function LogDetailModal({ isOpen, onClose, sections, title = "실행 로그 상세" }: LogDetailModalProps) {
  if (!isOpen) return null

  const hasSections = sections.length > 0
  const singleSection = sections.length === 1

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4" data-modal="log-detail">
      <div className="bg-white rounded-lg w-full h-full max-w-7xl max-h-[90vh] flex flex-col shadow-2xl border border-gray-200" role="dialog" aria-modal="true">
        {/* 헤더 */}
        <div className="flex items-center justify-between p-4 border-b border-gray-200 bg-gray-50">
          <div className="flex items-center gap-2">
            <Maximize2 className="w-5 h-5 text-blue-600" />
            <h2 className="text-lg font-semibold text-gray-900">{title}</h2>
            {hasSections && (
              <span className="text-sm text-gray-600">
                ({sections.length}개 노드)
              </span>
            )}
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <X className="w-5 h-5 text-gray-600" />
          </button>
        </div>

        {/* 로그 내용 */}
        <div className="flex-1 overflow-hidden">
          {!hasSections ? (
            <div className="h-full flex items-center justify-center text-gray-500">
              로그가 없습니다
            </div>
          ) : singleSection ? (
            // 단일 노드: 전체 화면
            <div className="h-full bg-gray-50">
              <LogSection section={sections[0]} />
            </div>
          ) : (
            // 다중 노드: 좌우 분할 또는 그리드
            <div className={`h-full grid ${sections.length === 2 ? 'grid-cols-2' : 'grid-cols-1 md:grid-cols-2 lg:grid-cols-3'} gap-4 p-4 overflow-y-auto bg-gray-50`}>
              {sections.map((section) => (
                <div key={section.nodeId} className="border border-gray-200 rounded-lg overflow-hidden bg-white">
                  <LogSection section={section} />
                </div>
              ))}
            </div>
          )}
        </div>

        {/* 푸터 */}
        <div className="p-4 border-t border-gray-200 bg-gray-50 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-gray-200 hover:bg-gray-300 text-gray-900 rounded-lg transition-colors"
          >
            닫기
          </button>
        </div>
      </div>
    </div>
  )
}

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

function LogSection({ section }: { section: NodeLogSection }) {
  const scrollRef = useRef<HTMLDivElement>(null)

  // 필터 상태
  const [selectedLogType, setSelectedLogType] = useState<string>('all')
  const [showSystemLogs, setShowSystemLogs] = useState<boolean>(false) // 시스템 로그 기본 숨김
  const [showToolLogs, setShowToolLogs] = useState<boolean>(true) // 툴 로그 기본 표시
  const [showThinkingLogs, setShowThinkingLogs] = useState<boolean>(true) // 사고과정 로그 기본 표시
  const [isFilterExpanded, setIsFilterExpanded] = useState<boolean>(false) // 필터 접힘/펼침 상태

  // 새 로그가 추가될 때마다 자동 스크롤
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [section.logs])

  // 필터링된 로그
  const filteredLogs = useMemo(() => {
    return section.logs.filter(log => {
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
  }, [section.logs, selectedLogType, showSystemLogs])

  // 전역 tool_use_id → tool_name 매핑 생성
  const toolUseIdToName = useMemo(() => {
    const mapping: Record<string, string> = {}

    section.logs.forEach((log) => {
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
  }, [section.logs])

  // 로그 그룹화 (1분 단위, 같은 카테고리)
  interface LogGroup {
    timestamp: number
    category: LogCategory
    logs: typeof section.logs
  }

  const groupedLogs = useMemo(() => {
    const groups: LogGroup[] = []

    filteredLogs.forEach((log) => {
      const category = getLogCategory(log.type)
      const logTime = new Date(log.timestamp).getTime()

      // 마지막 그룹과 비교 (1분 이내 + 같은 카테고리)
      const lastGroup = groups[groups.length - 1]
      const timeDiff = lastGroup ? logTime - lastGroup.timestamp : Infinity
      const isSameCategory = lastGroup?.category === category

      if (lastGroup && timeDiff < 60000 && isSameCategory) {
        // 기존 그룹에 추가
        lastGroup.logs.push(log)
      } else {
        // 새 그룹 생성
        groups.push({
          timestamp: logTime,
          category,
          logs: [log]
        })
      }
    })

    return groups
  }, [filteredLogs])

  // 세션 관리 상태
  const [sessions, setSessions] = useState<NodeSession[]>([])
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null)
  const [isLoadingSessions, setIsLoadingSessions] = useState(false)

  // 추가 프롬프트 입력 상태
  const [userInput, setUserInput] = useState('')
  const [isSending, setIsSending] = useState(false)
  const [sendError, setSendError] = useState<string | null>(null)
  const [_continueSessionId, setContinueSessionId] = useState<string | null>(null)

  // Zustand store
  const addLog = useWorkflowStore((state) => state.addLog)

  // 세션 목록 불러오기
  const loadSessions = async () => {
    setIsLoadingSessions(true)
    try {
      const data = await getNodeSessions(section.nodeId)
      setSessions(data.session_history)
      setSelectedSessionId(data.current_session_id)
    } catch (error) {
      console.error('세션 목록 불러오기 실패:', error)
    } finally {
      setIsLoadingSessions(false)
    }
  }

  // 컴포넌트 마운트 시 세션 목록 불러오기 + 주기적 새로고침
  useEffect(() => {
    loadSessions()

    // 5초마다 세션 목록 자동 새로고침 (워크플로우 실행 중에만)
    const interval = setInterval(() => {
      const isExecuting = useWorkflowStore.getState().execution.isExecuting
      if (isExecuting) {
        loadSessions()
      }
    }, 5000)

    return () => clearInterval(interval)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [section.nodeId])

  // 추가 프롬프트 전송
  const handleSendPrompt = async () => {
    if (!userInput.trim() || isSending) return

    setIsSending(true)
    setSendError(null)

    try {
      // API 호출
      const apiResponse = await continueNodeConversation(section.nodeId, userInput.trim())
      const sessionId = apiResponse.session_id

      // 입력 로그 추가
      addLog(section.nodeId, 'input', `📝 추가 프롬프트: ${userInput.trim()}`)
      setUserInput('') // 입력 초기화

      // SSE 연결 시작 (fetch + ReadableStream 패턴)
      setContinueSessionId(sessionId)

      const sseResponse = await fetch(`${API_BASE}/workflows/sessions/${sessionId}/stream`, {
        method: 'GET',
        headers: {
          'Accept': 'text/event-stream',
        },
      })

      if (!sseResponse.ok) {
        throw new Error(`SSE 연결 실패: ${sseResponse.status}`)
      }

      const reader = sseResponse.body?.getReader()
      if (!reader) {
        throw new Error('SSE 스트림을 읽을 수 없습니다')
      }

      const decoder = new TextDecoder('utf-8')
      let buffer = ''

      // 백그라운드에서 SSE 읽기
      ;(async () => {
        try {
          while (true) {
            const { done, value } = await reader.read()

            if (done) {
              setIsSending(false)
              setContinueSessionId(null)
              break
            }

            // 청크를 문자열로 변환
            const chunk = decoder.decode(value, { stream: true })
            buffer += chunk

            // SSE 메시지 파싱 (빈 줄로 구분)
            const messages = buffer.split(/\r\n\r\n|\n\n/)
            buffer = messages.pop() || ''

            for (const message of messages) {
              if (!message.trim()) continue

              const lines = message.split(/\r\n|\n/)
              let dataContent = ''

              for (const line of lines) {
                const trimmedLine = line.trim()
                if (trimmedLine.startsWith('data:')) {
                  const lineData = trimmedLine.substring(5).trim()
                  if (lineData !== '[DONE]') {
                    dataContent += lineData
                  }
                }
              }

              if (!dataContent) continue

              try {
                const event = JSON.parse(dataContent)
                const { event_type, node_id, data } = event

                // 청크 타입에 따라 로그 타입 결정
                let logType: 'input' | 'execution' | 'output' | 'error' | 'complete' | 'start' = 'execution'
                if (data?.chunk_type === 'text') {
                  logType = 'output'
                } else if (data?.chunk_type === 'thinking' || data?.chunk_type === 'tool') {
                  logType = 'execution'
                }

                switch (event_type) {
                  case 'node_start':
                    addLog(node_id, 'start', '🚀 노드 추가 대화 시작')
                    break
                  case 'node_output':
                    if (data?.chunk) {
                      addLog(node_id, logType, data.chunk)
                    }
                    break
                  case 'node_complete':
                    addLog(node_id, 'complete', '✅ 노드 추가 대화 완료')
                    break
                  case 'node_error':
                    addLog(node_id, 'error', `❌ 에러: ${data?.error || '알 수 없는 오류'}`)
                    break
                }
              } catch (parseError) {
                console.error('SSE 메시지 파싱 에러:', parseError)
              }
            }
          }
        } catch (streamError) {
          console.error('SSE 스트림 에러:', streamError)
          setIsSending(false)
          setContinueSessionId(null)
        }
      })()

    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : '알 수 없는 오류가 발생했습니다'
      setSendError(errorMessage)
      setIsSending(false)
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* 노드 제목 - 컴팩트하게 */}
      <div className="p-2 bg-gray-100 border-b border-gray-200 flex-shrink-0">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="font-semibold text-gray-900 text-sm">{section.nodeName}</h3>
            <p className="text-xs text-gray-500">ID: {section.nodeId.substring(0, 12)}...</p>
          </div>
          {/* 필터 토글 버튼 */}
          <button
            onClick={() => setIsFilterExpanded(!isFilterExpanded)}
            className="flex items-center gap-1 px-2 py-1 text-xs bg-white border border-gray-300 rounded hover:bg-gray-50 transition-colors"
          >
            <Filter className="h-3 w-3" />
            <span>필터</span>
            {(selectedLogType !== 'all' || !showSystemLogs) && (
              <Badge variant="secondary" className="text-xs ml-1">
                {filteredLogs.length}/{section.logs.length}
              </Badge>
            )}
            {isFilterExpanded ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
          </button>
        </div>

        {/* 필터 UI - 아코디언 */}
        {isFilterExpanded && (
          <div className="mt-2 pt-2 border-t border-gray-200 space-y-2">
            {/* 타입 선택 */}
            <div className="flex items-center gap-2">
              <span className="text-xs text-gray-600 w-12">타입:</span>
              <Select value={selectedLogType} onValueChange={setSelectedLogType}>
                <SelectTrigger className="h-7 text-xs flex-1">
                  <SelectValue placeholder="타입 선택" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">모든 타입</SelectItem>
                  <SelectItem value="input">입력</SelectItem>
                  <SelectItem value="execution">실행</SelectItem>
                  <SelectItem value="output">출력</SelectItem>
                  <SelectItem value="start">시작</SelectItem>
                  <SelectItem value="complete">완료</SelectItem>
                  <SelectItem value="error">에러</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* 로그 표시 옵션 - 한 줄로 */}
            <div className="flex items-center gap-2">
              <span className="text-xs text-gray-600 w-12">표시:</span>
              <div className="flex items-center gap-1 flex-wrap flex-1">
                <Badge
                  variant={showSystemLogs ? "default" : "outline"}
                  className="cursor-pointer select-none text-xs transition-colors h-6"
                  onClick={() => setShowSystemLogs(!showSystemLogs)}
                >
                  {showSystemLogs ? <Eye className="h-3 w-3 mr-1" /> : <EyeOff className="h-3 w-3 mr-1" />}
                  시스템
                </Badge>
                <Badge
                  variant={showToolLogs ? "default" : "outline"}
                  className="cursor-pointer select-none text-xs transition-colors h-6"
                  onClick={() => setShowToolLogs(!showToolLogs)}
                >
                  {showToolLogs ? <Eye className="h-3 w-3 mr-1" /> : <EyeOff className="h-3 w-3 mr-1" />}
                  툴
                </Badge>
                <Badge
                  variant={showThinkingLogs ? "default" : "outline"}
                  className="cursor-pointer select-none text-xs transition-colors h-6"
                  onClick={() => setShowThinkingLogs(!showThinkingLogs)}
                >
                  {showThinkingLogs ? <Eye className="h-3 w-3 mr-1" /> : <EyeOff className="h-3 w-3 mr-1" />}
                  사고
                </Badge>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* 로그 내용 - 채팅 스타일 */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto bg-white min-h-0 p-4 space-y-2"
      >
        {groupedLogs.length === 0 ? (
          <div className="h-full flex items-center justify-center text-gray-500">
            <div className="text-center">
              <FileText className="h-12 w-12 mx-auto mb-2 opacity-50" />
              {section.logs.length === 0 ? (
                <>
                  <p>로그가 없습니다</p>
                  <p className="text-xs">노드 실행 시 로그가 표시됩니다</p>
                </>
              ) : (
                <>
                  <p>필터 조건에 맞는 로그가 없습니다</p>
                  <p className="text-xs">필터를 변경해보세요</p>
                </>
              )}
            </div>
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
                    {/* 헤더: 카테고리, 시간 (그룹당 한번만) */}
                    <div className={`flex items-center gap-2 flex-wrap ${isUser ? 'justify-end' : ''}`}>
                      {categoryLabel && (
                        <span className={`text-xs font-semibold px-2 py-0.5 rounded ${
                          isUser ? 'bg-blue-200 text-blue-800' : getCategoryLabelClass(group.category)
                        }`}>
                          {categoryLabel}
                        </span>
                      )}
                      <span className="text-xs text-muted-foreground flex items-center gap-1">
                        <Clock className="h-3 w-3" />
                        {new Date(group.timestamp).toLocaleTimeString()}
                      </span>
                    </div>

                    {/* 로그 내용들 (채팅처럼 연속으로) */}
                    <div className="space-y-1">
                      {group.logs.map((log, logIndex) => (
                        <ParsedContent
                          key={logIndex}
                          content={log.message}
                          toolUseIdToName={toolUseIdToName}
                          showToolLogs={showToolLogs}
                          showThinkingLogs={showThinkingLogs}
                        />
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

      {/* 추가 프롬프트 입력 UI - 컴팩트하게 */}
      <div className="flex-shrink-0 p-2 border-t border-gray-200 bg-blue-50">
        <div className="space-y-2">
          {/* 세션 선택 - 인라인 셀렉트 */}
          <div className="flex items-center gap-2">
            <Select
              value={selectedSessionId || 'new'}
              onValueChange={(value) => setSelectedSessionId(value === 'new' ? null : value)}
            >
              <SelectTrigger className="h-7 text-xs flex-1">
                <div className="flex items-center gap-1">
                  <History className="w-3 h-3" />
                  <SelectValue placeholder="세션 선택" />
                </div>
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="new">🆕 새 세션</SelectItem>
                {sessions.map((session) => (
                  <SelectItem key={session.session_id} value={session.session_id}>
                    {session.session_id.substring(0, 8)}...
                    {session.is_current && ' (현재)'}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <button
              onClick={loadSessions}
              disabled={isLoadingSessions}
              className="p-1 bg-white border border-gray-300 rounded hover:bg-gray-50 disabled:opacity-50"
              title="새로고침"
            >
              <RefreshCw className={`w-3 h-3 ${isLoadingSessions ? 'animate-spin' : ''}`} />
            </button>
          </div>

          {/* 입력 필드 */}
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={userInput}
              onChange={(e) => setUserInput(e.target.value)}
              onKeyPress={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  handleSendPrompt()
                }
              }}
              placeholder="추가 프롬프트 입력..."
              className="flex-1 px-2 py-1.5 text-sm border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-500"
              disabled={isSending}
            />
            <Button
              onClick={handleSendPrompt}
              disabled={!userInput.trim() || isSending}
              size="sm"
              className="px-3 py-1.5 h-auto bg-blue-600 text-white rounded hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed flex items-center gap-1"
            >
              {isSending ? (
                <>
                  <Loader2 className="w-3 h-3 animate-spin" />
                  <span className="text-xs">전송중</span>
                </>
              ) : (
                <>
                  <Send className="w-3 h-3" />
                  <span className="text-xs">전송</span>
                </>
              )}
            </Button>
          </div>
          {sendError && (
            <div className="text-xs text-red-600 bg-red-50 px-2 py-1 rounded border border-red-200">
              ❌ {sendError}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
