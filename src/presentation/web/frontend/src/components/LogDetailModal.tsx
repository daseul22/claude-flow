import { X, Maximize2, Send, Loader2, RefreshCw, History } from 'lucide-react'
import { useState, useEffect } from 'react'
import { LogItem, useWorkflowStore } from '@/stores/workflowStore'
import { ParsedContent } from './ParsedContent'
import { Button } from './ui/button'
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
            <div className="h-full p-4 bg-gray-50">
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

type TabType = 'input' | 'execution' | 'output' | 'error' | 'other'

function LogSection({ section }: { section: NodeLogSection }) {
  // 로그 타입별 분류
  const inputLogs = section.logs.filter(log => log.type === 'input')
  const executionLogs = section.logs.filter(log => log.type === 'execution')
  const outputLogs = section.logs.filter(log => log.type === 'output')
  const errorLogs = section.logs.filter(log => log.type === 'error')
  const otherLogs = section.logs.filter(log => !['input', 'execution', 'output', 'error'].includes(log.type))

  // 탭 정의 (로그가 있는 탭만 표시)
  const tabs = [
    { id: 'input' as TabType, label: '📥 입력', logs: inputLogs, color: 'blue' },
    { id: 'execution' as TabType, label: '🔧 실행 과정', logs: executionLogs, color: 'purple' },
    { id: 'output' as TabType, label: '📤 출력', logs: outputLogs, color: 'green' },
    { id: 'error' as TabType, label: '❌ 에러', logs: errorLogs, color: 'red' },
    { id: 'other' as TabType, label: '📝 기타', logs: otherLogs, color: 'gray' },
  ].filter(tab => tab.logs.length > 0)

  // 초기 탭 선택: 로그가 있는 첫 번째 탭 (에러 우선, 그 다음 출력)
  const getInitialTab = (): TabType => {
    if (errorLogs.length > 0) return 'error'
    if (outputLogs.length > 0) return 'output'
    if (executionLogs.length > 0) return 'execution'
    if (inputLogs.length > 0) return 'input'
    if (otherLogs.length > 0) return 'other'
    return 'output' // 폴백
  }

  // 탭 상태
  const [activeTab, setActiveTab] = useState<TabType>(getInitialTab())

  // 로그가 변경되면 활성 탭이 유효한지 확인
  useEffect(() => {
    const currentTabHasLogs = tabs.some(tab => tab.id === activeTab && tab.logs.length > 0)
    if (!currentTabHasLogs && tabs.length > 0) {
      setActiveTab(tabs[0].id)
    }
  }, [section.logs.length, activeTab, tabs])

  // 세션 관리 상태
  const [sessions, setSessions] = useState<NodeSession[]>([])
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null)
  const [isLoadingSessions, setIsLoadingSessions] = useState(false)
  const [showSessionSelect, setShowSessionSelect] = useState(false)

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

  // 컴포넌트 마운트 시 세션 목록 불러오기
  useEffect(() => {
    loadSessions()
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

  // 활성 탭의 로그
  const activeTabLogs = tabs.find(tab => tab.id === activeTab)?.logs || []

  return (
    <div className="flex flex-col h-full">
      {/* 노드 제목 */}
      <div className="p-3 bg-gray-100 border-b border-gray-200">
        <h3 className="font-semibold text-gray-900">{section.nodeName}</h3>
        <p className="text-xs text-gray-600 mt-1">Node ID: {section.nodeId}</p>
      </div>

      {/* 탭 버튼 */}
      {section.logs.length > 0 && tabs.length > 0 && (
        <div className="flex border-b border-gray-200 bg-gray-50">
          {tabs.map((tab) => {
            const isActive = activeTab === tab.id
            const colorClasses = {
              blue: isActive ? 'bg-blue-500 text-white' : 'text-blue-700 hover:bg-blue-50',
              purple: isActive ? 'bg-purple-500 text-white' : 'text-purple-700 hover:bg-purple-50',
              green: isActive ? 'bg-green-500 text-white' : 'text-green-700 hover:bg-green-50',
              red: isActive ? 'bg-red-500 text-white' : 'text-red-700 hover:bg-red-50',
              gray: isActive ? 'bg-gray-500 text-white' : 'text-gray-700 hover:bg-gray-100',
            }

            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`
                  flex items-center gap-2 px-4 py-2 font-medium text-sm transition-colors
                  ${colorClasses[tab.color as keyof typeof colorClasses]}
                  ${isActive ? 'border-b-2 border-current' : ''}
                `}
              >
                <span>{tab.label}</span>
                <span className={`
                  px-2 py-0.5 rounded-full text-xs font-semibold
                  ${isActive ? 'bg-white/20' : 'bg-gray-200 text-gray-700'}
                `}>
                  {tab.logs.length}
                </span>
              </button>
            )
          })}
        </div>
      )}

      {/* 로그 내용 - 고정 높이 영역 */}
      <div className="flex-1 overflow-y-auto bg-white min-h-0">
        {section.logs.length === 0 ? (
          <div className="h-full flex items-center justify-center text-gray-500">
            로그가 없습니다
          </div>
        ) : (
          <div className="p-4 space-y-2">
            {activeTabLogs.map((log, idx) => (
              <LogItemComponent key={idx} log={log} />
            ))}
          </div>
        )}
      </div>

      {/* 추가 프롬프트 입력 UI - 고정 하단 */}
      <div className="flex-shrink-0 p-3 border-t border-gray-200 bg-blue-50 relative">
        <div className="space-y-2">
          {/* 세션 선택 버튼 */}
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowSessionSelect(!showSessionSelect)}
              className="flex items-center gap-2 px-3 py-2 bg-white border border-gray-300 rounded-md hover:bg-gray-50 text-sm"
            >
              <History className="w-4 h-4" />
              <span>세션 선택 ({sessions.length})</span>
            </button>
            <button
              onClick={loadSessions}
              disabled={isLoadingSessions}
              className="p-2 bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50"
              title="새로고침"
            >
              <RefreshCw className={`w-4 h-4 ${isLoadingSessions ? 'animate-spin' : ''}`} />
            </button>
          </div>

          {/* 세션 목록 드롭다운 - absolute positioning으로 위로 표시 */}
          {showSessionSelect && (
            <div className="absolute bottom-full left-3 right-3 mb-1 bg-white border border-gray-300 rounded-md shadow-lg max-h-60 overflow-y-auto z-10">
              {sessions.length === 0 ? (
                <div className="px-4 py-3 text-sm text-gray-500 text-center">
                  세션이 없습니다
                </div>
              ) : (
                <>
                  {/* 새 세션 시작 옵션 */}
                  <button
                    onClick={() => {
                      setSelectedSessionId(null)
                      setShowSessionSelect(false)
                    }}
                    className={`w-full px-4 py-2 text-left hover:bg-blue-50 border-b border-gray-200 ${
                      selectedSessionId === null ? 'bg-blue-100' : ''
                    }`}
                  >
                    <div className="font-medium text-sm text-blue-600">
                      🆕 새 세션 시작
                    </div>
                    <div className="text-xs text-gray-500 mt-1">
                      새로운 컨텍스트로 시작합니다
                    </div>
                  </button>

                  {/* 기존 세션 목록 */}
                  {sessions.map((session) => (
                    <button
                      key={session.session_id}
                      onClick={() => {
                        setSelectedSessionId(session.session_id)
                        setShowSessionSelect(false)
                      }}
                      className={`w-full px-4 py-2 text-left hover:bg-gray-50 ${
                        selectedSessionId === session.session_id ? 'bg-gray-100' : ''
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <div className="font-medium text-sm">
                          {session.session_id.substring(0, 8)}...
                          {session.is_current && (
                            <span className="ml-2 px-2 py-0.5 bg-green-100 text-green-700 text-xs rounded-full">
                              현재
                            </span>
                          )}
                        </div>
                        <div className="text-xs text-gray-500">
                          {new Date(session.last_used_at).toLocaleString('ko-KR', {
                            month: 'short',
                            day: 'numeric',
                            hour: '2-digit',
                            minute: '2-digit'
                          })}
                        </div>
                      </div>
                      <div className="text-xs text-gray-500 mt-1">
                        생성: {new Date(session.created_at).toLocaleString('ko-KR', {
                          year: 'numeric',
                          month: 'short',
                          day: 'numeric',
                          hour: '2-digit',
                          minute: '2-digit'
                        })}
                      </div>
                    </button>
                  ))}
                </>
              )}
            </div>
          )}

          {/* 선택된 세션 표시 */}
          {selectedSessionId === null ? (
            <div className="text-xs text-gray-600 px-2">
              🆕 새 세션으로 시작합니다
            </div>
          ) : (
            <div className="text-xs text-gray-600 px-2">
              📝 세션: {selectedSessionId.substring(0, 8)}... 사용 중
            </div>
          )}

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
              placeholder="이 노드에 추가 프롬프트 입력..."
              className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              disabled={isSending}
            />
            <Button
              onClick={handleSendPrompt}
              disabled={!userInput.trim() || isSending}
              className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed flex items-center gap-2"
            >
              {isSending ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>전송 중...</span>
                </>
              ) : (
                <>
                  <Send className="w-4 h-4" />
                  <span>전송</span>
                </>
              )}
            </Button>
          </div>
          {sendError && (
            <div className="text-sm text-red-600 bg-red-50 px-3 py-2 rounded-md border border-red-200">
              ❌ {sendError}
            </div>
          )}
          <p className="text-xs text-gray-600">
            💡 이 노드의 이전 대화 컨텍스트를 유지하며 추가 작업을 요청할 수 있습니다
          </p>
        </div>
      </div>
    </div>
  )
}

function LogItemComponent({ log }: { log: LogItem }) {
  return (
    <div className="bg-white rounded p-2 border border-gray-200 shadow-sm">
      <div className="text-xs text-gray-500 mb-1">
        {new Date(log.timestamp).toLocaleString()}
      </div>
      <ParsedContent content={log.message} />
    </div>
  )
}
