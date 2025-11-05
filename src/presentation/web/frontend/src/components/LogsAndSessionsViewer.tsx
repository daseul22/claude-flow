/**
 * 로그, 세션 및 보고서 파일 뷰어
 *
 * 프로젝트의 로그 파일, 세션 파일, 보고서 파일을 목록으로 표시하고,
 * 선택한 파일의 상세 내용을 보여줍니다.
 */

import { useState, useEffect } from 'react'
import { X, FileText, Clock, HardDrive, AlertCircle, RefreshCw, FileCode } from 'lucide-react'
import { Button } from './ui/button'

interface LogFileInfo {
  path: string
  name: string
  size: number
  modified: string
  type: string
}

interface SessionFileInfo {
  session_id: string
  path: string
  size: number
  created: string
  modified: string
  status: string
}

interface ReportFileInfo {
  path: string
  name: string
  size: number
  modified: string
  node_id: string
  extension: string
}

interface LogsAndSessionsViewerProps {
  isOpen: boolean
  onClose: () => void
  projectPath: string | null
}

export function LogsAndSessionsViewer({
  isOpen,
  onClose,
  projectPath
}: LogsAndSessionsViewerProps) {
  const [activeTab, setActiveTab] = useState<'logs' | 'sessions' | 'reports'>('logs')
  const [logs, setLogs] = useState<LogFileInfo[]>([])
  const [sessions, setSessions] = useState<SessionFileInfo[]>([])
  const [reports, setReports] = useState<ReportFileInfo[]>([])
  const [selectedLog, setSelectedLog] = useState<LogFileInfo | null>(null)
  const [selectedSession, setSelectedSession] = useState<SessionFileInfo | null>(null)
  const [selectedReport, setSelectedReport] = useState<ReportFileInfo | null>(null)
  const [logContent, setLogContent] = useState<string>('')
  const [sessionContent, setSessionContent] = useState<any>(null)
  const [reportContent, setReportContent] = useState<string>('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // 로그 파일 목록 로드
  const loadLogs = async () => {
    if (!projectPath) return

    setLoading(true)
    setError(null)
    try {
      const response = await fetch('/api/projects/logs/list')
      if (!response.ok) throw new Error('로그 목록 로드 실패')
      const data = await response.json()
      setLogs(data.logs || [])
    } catch (err) {
      setError(err instanceof Error ? err.message : '로그 목록 로드 실패')
    } finally {
      setLoading(false)
    }
  }

  // 세션 파일 목록 로드
  const loadSessions = async () => {
    if (!projectPath) return

    setLoading(true)
    setError(null)
    try {
      const response = await fetch('/api/projects/sessions/list')
      if (!response.ok) throw new Error('세션 목록 로드 실패')
      const data = await response.json()
      setSessions(data.sessions || [])
    } catch (err) {
      setError(err instanceof Error ? err.message : '세션 목록 로드 실패')
    } finally {
      setLoading(false)
    }
  }

  // 로그 파일 내용 로드
  const loadLogContent = async (log: LogFileInfo) => {
    setLoading(true)
    setError(null)
    try {
      const response = await fetch(
        `/api/projects/logs/content?file_path=${encodeURIComponent(log.path)}&max_lines=1000`
      )
      if (!response.ok) throw new Error('로그 내용 로드 실패')
      const data = await response.json()
      setLogContent(data.content || '')
      setSelectedLog(log)
    } catch (err) {
      setError(err instanceof Error ? err.message : '로그 내용 로드 실패')
    } finally {
      setLoading(false)
    }
  }

  // 세션 파일 내용 로드
  const loadSessionContent = async (session: SessionFileInfo) => {
    setLoading(true)
    setError(null)
    try {
      const response = await fetch(
        `/api/projects/sessions/content?session_id=${encodeURIComponent(session.session_id)}`
      )
      if (!response.ok) throw new Error('세션 내용 로드 실패')
      const data = await response.json()
      setSessionContent(data.content || {})
      setSelectedSession(session)
    } catch (err) {
      setError(err instanceof Error ? err.message : '세션 내용 로드 실패')
    } finally {
      setLoading(false)
    }
  }

  // 보고서 파일 목록 로드
  const loadReports = async () => {
    if (!projectPath) return

    setLoading(true)
    setError(null)
    try {
      const response = await fetch('/api/projects/reports/list')
      if (!response.ok) throw new Error('보고서 목록 로드 실패')
      const data = await response.json()
      setReports(data.reports || [])
    } catch (err) {
      setError(err instanceof Error ? err.message : '보고서 목록 로드 실패')
    } finally {
      setLoading(false)
    }
  }

  // 보고서 파일 내용 로드
  const loadReportContent = async (report: ReportFileInfo) => {
    setLoading(true)
    setError(null)
    try {
      const response = await fetch(
        `/api/projects/reports/content?file_path=${encodeURIComponent(report.path)}`
      )
      if (!response.ok) throw new Error('보고서 내용 로드 실패')
      const data = await response.json()
      setReportContent(data.content || '')
      setSelectedReport(report)
    } catch (err) {
      setError(err instanceof Error ? err.message : '보고서 내용 로드 실패')
    } finally {
      setLoading(false)
    }
  }

  // 탭 변경 시 목록 로드
  useEffect(() => {
    if (!isOpen || !projectPath) return

    if (activeTab === 'logs') {
      loadLogs()
    } else if (activeTab === 'sessions') {
      loadSessions()
    } else {
      loadReports()
    }
  }, [isOpen, activeTab, projectPath])

  // 파일 크기 포맷
  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  // 날짜 포맷
  const formatDate = (isoString: string) => {
    const date = new Date(isoString)
    return date.toLocaleString('ko-KR', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    })
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl w-[90vw] h-[85vh] flex flex-col">
        {/* 헤더 */}
        <div className="flex items-center justify-between p-4 border-b dark:border-gray-700">
          <h2 className="text-xl font-semibold">로그, 세션 & 보고서 뷰어</h2>
          <Button
            variant="ghost"
            size="sm"
            onClick={onClose}
            className="h-8 w-8 p-0"
          >
            <X className="h-4 w-4" />
          </Button>
        </div>

        {/* 탭 */}
        <div className="flex border-b dark:border-gray-700">
          <button
            className={`px-4 py-2 font-medium ${
              activeTab === 'logs'
                ? 'border-b-2 border-blue-500 text-blue-600 dark:text-blue-400'
                : 'text-gray-600 dark:text-gray-400'
            }`}
            onClick={() => {
              setActiveTab('logs')
              setSelectedLog(null)
              setLogContent('')
            }}
          >
            <FileText className="inline h-4 w-4 mr-1" />
            로그 파일
          </button>
          <button
            className={`px-4 py-2 font-medium ${
              activeTab === 'sessions'
                ? 'border-b-2 border-blue-500 text-blue-600 dark:text-blue-400'
                : 'text-gray-600 dark:text-gray-400'
            }`}
            onClick={() => {
              setActiveTab('sessions')
              setSelectedSession(null)
              setSessionContent(null)
            }}
          >
            <Clock className="inline h-4 w-4 mr-1" />
            세션 파일
          </button>
          <button
            className={`px-4 py-2 font-medium ${
              activeTab === 'reports'
                ? 'border-b-2 border-blue-500 text-blue-600 dark:text-blue-400'
                : 'text-gray-600 dark:text-gray-400'
            }`}
            onClick={() => {
              setActiveTab('reports')
              setSelectedReport(null)
              setReportContent('')
            }}
          >
            <FileCode className="inline h-4 w-4 mr-1" />
            보고서 파일
          </button>
          <div className="ml-auto px-4 py-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() =>
                activeTab === 'logs' ? loadLogs() :
                activeTab === 'sessions' ? loadSessions() :
                loadReports()
              }
              disabled={loading}
            >
              <RefreshCw className={`h-4 w-4 mr-1 ${loading ? 'animate-spin' : ''}`} />
              새로고침
            </Button>
          </div>
        </div>

        {/* 에러 표시 */}
        {error && (
          <div className="mx-4 mt-4 p-3 bg-red-100 dark:bg-red-900/20 border border-red-300 dark:border-red-700 rounded flex items-center gap-2 text-red-700 dark:text-red-400">
            <AlertCircle className="h-4 w-4" />
            {error}
          </div>
        )}

        {/* 컨텐츠 영역 */}
        <div className="flex-1 flex overflow-hidden">
          {/* 왼쪽: 파일 목록 */}
          <div className="w-1/3 border-r dark:border-gray-700 overflow-y-auto">
            {activeTab === 'logs' ? (
              <div className="p-2">
                {logs.length === 0 && !loading && (
                  <p className="text-center text-gray-500 py-8">로그 파일이 없습니다</p>
                )}
                {logs.map((log) => (
                  <div
                    key={log.path}
                    className={`p-3 mb-2 rounded cursor-pointer transition-colors ${
                      selectedLog?.path === log.path
                        ? 'bg-blue-100 dark:bg-blue-900/30 border-2 border-blue-500'
                        : 'bg-gray-50 dark:bg-gray-700/50 hover:bg-gray-100 dark:hover:bg-gray-700 border-2 border-transparent'
                    }`}
                    onClick={() => loadLogContent(log)}
                  >
                    <div className="font-medium text-sm">{log.name}</div>
                    <div className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                      {log.path}
                    </div>
                    <div className="flex items-center gap-3 mt-2 text-xs text-gray-600 dark:text-gray-400">
                      <span className="flex items-center gap-1">
                        <HardDrive className="h-3 w-3" />
                        {formatSize(log.size)}
                      </span>
                      <span className="flex items-center gap-1">
                        <Clock className="h-3 w-3" />
                        {formatDate(log.modified)}
                      </span>
                    </div>
                    <div className="mt-1">
                      <span className={`text-xs px-2 py-0.5 rounded ${
                        log.type === 'error' ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400' :
                        log.type === 'system' ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400' :
                        log.type === 'debug' ? 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400' :
                        'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-400'
                      }`}>
                        {log.type}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            ) : activeTab === 'sessions' ? (
              <div className="p-2">
                {sessions.length === 0 && !loading && (
                  <p className="text-center text-gray-500 py-8">세션 파일이 없습니다</p>
                )}
                {sessions.map((session) => (
                  <div
                    key={session.session_id}
                    className={`p-3 mb-2 rounded cursor-pointer transition-colors ${
                      selectedSession?.session_id === session.session_id
                        ? 'bg-blue-100 dark:bg-blue-900/30 border-2 border-blue-500'
                        : 'bg-gray-50 dark:bg-gray-700/50 hover:bg-gray-100 dark:hover:bg-gray-700 border-2 border-transparent'
                    }`}
                    onClick={() => loadSessionContent(session)}
                  >
                    <div className="font-medium text-sm">{session.session_id}</div>
                    <div className="flex items-center gap-3 mt-2 text-xs text-gray-600 dark:text-gray-400">
                      <span className="flex items-center gap-1">
                        <HardDrive className="h-3 w-3" />
                        {formatSize(session.size)}
                      </span>
                      <span className="flex items-center gap-1">
                        <Clock className="h-3 w-3" />
                        {formatDate(session.modified)}
                      </span>
                    </div>
                    <div className="mt-1">
                      <span className={`text-xs px-2 py-0.5 rounded ${
                        session.status === 'completed' ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' :
                        session.status === 'running' ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400' :
                        session.status === 'error' ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400' :
                        'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-400'
                      }`}>
                        {session.status}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="p-2">
                {reports.length === 0 && !loading && (
                  <p className="text-center text-gray-500 py-8">보고서 파일이 없습니다</p>
                )}
                {reports.map((report) => (
                  <div
                    key={report.path}
                    className={`p-3 mb-2 rounded cursor-pointer transition-colors ${
                      selectedReport?.path === report.path
                        ? 'bg-blue-100 dark:bg-blue-900/30 border-2 border-blue-500'
                        : 'bg-gray-50 dark:bg-gray-700/50 hover:bg-gray-100 dark:hover:bg-gray-700 border-2 border-transparent'
                    }`}
                    onClick={() => loadReportContent(report)}
                  >
                    <div className="font-medium text-sm">{report.name}</div>
                    <div className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                      {report.path}
                    </div>
                    <div className="flex items-center gap-3 mt-2 text-xs text-gray-600 dark:text-gray-400">
                      <span className="flex items-center gap-1">
                        <HardDrive className="h-3 w-3" />
                        {formatSize(report.size)}
                      </span>
                      <span className="flex items-center gap-1">
                        <Clock className="h-3 w-3" />
                        {formatDate(report.modified)}
                      </span>
                    </div>
                    <div className="mt-1 flex items-center gap-2">
                      <span className="text-xs px-2 py-0.5 rounded bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400">
                        {report.node_id}
                      </span>
                      <span className="text-xs px-2 py-0.5 rounded bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-400">
                        .{report.extension}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* 오른쪽: 파일 내용 */}
          <div className="flex-1 overflow-hidden flex flex-col">
            {activeTab === 'logs' && selectedLog ? (
              <>
                <div className="p-3 border-b dark:border-gray-700 bg-gray-50 dark:bg-gray-800">
                  <div className="text-sm font-medium">{selectedLog.name}</div>
                  <div className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                    {selectedLog.path} • {formatSize(selectedLog.size)} • 최근 1000줄
                  </div>
                </div>
                <div className="flex-1 overflow-auto p-4">
                  <pre className="text-xs font-mono whitespace-pre-wrap bg-gray-900 text-gray-100 p-4 rounded">
                    {logContent || '로그 내용이 없습니다.'}
                  </pre>
                </div>
              </>
            ) : activeTab === 'sessions' && selectedSession ? (
              <>
                <div className="p-3 border-b dark:border-gray-700 bg-gray-50 dark:bg-gray-800">
                  <div className="text-sm font-medium">{selectedSession.session_id}</div>
                  <div className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                    {formatSize(selectedSession.size)} • {sessionContent?.status || '상태 확인 불가'}
                  </div>
                </div>
                <div className="flex-1 overflow-auto p-4">
                  <pre className="text-xs font-mono whitespace-pre-wrap bg-gray-900 text-gray-100 p-4 rounded">
                    {JSON.stringify(sessionContent, null, 2)}
                  </pre>
                </div>
              </>
            ) : activeTab === 'reports' && selectedReport ? (
              <>
                <div className="p-3 border-b dark:border-gray-700 bg-gray-50 dark:bg-gray-800">
                  <div className="text-sm font-medium">{selectedReport.name}</div>
                  <div className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                    {selectedReport.path} • {formatSize(selectedReport.size)} • 노드: {selectedReport.node_id}
                  </div>
                </div>
                <div className="flex-1 overflow-auto p-4">
                  <pre className="text-xs font-mono whitespace-pre-wrap bg-gray-900 text-gray-100 p-4 rounded">
                    {reportContent || '보고서 내용이 없습니다.'}
                  </pre>
                </div>
              </>
            ) : (
              <div className="flex-1 flex items-center justify-center text-gray-500">
                {loading ? '로딩 중...' : '파일을 선택하세요'}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
