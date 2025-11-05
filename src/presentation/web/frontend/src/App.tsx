/**
 * Claude Flow 워크플로우 캔버스 앱
 *
 * 메인 레이아웃 및 컴포넌트 조합
 */

import { useState, useEffect, useCallback, useRef } from 'react'
import { ReactFlowProvider } from 'reactflow'
import { WorkflowCanvas } from './components/WorkflowCanvas'
import { NodePanel } from './components/NodePanel'
import { RightSidebar } from './components/RightSidebar'
import { HeaderBar } from './components/HeaderBar'
import { ProjectSelector } from './components/ProjectSelector'
import { Button } from './components/ui/button'
import { useWorkflowStore } from './stores/workflowStore'
import {
  selectProject,
  saveProjectWorkflowByName,
  loadProjectWorkflowByName,
  listProjectWorkflows,
  sendUserInput,
  clearProjectSessions,
  clearProjectLogs,
  clearNodeSessions,
  loadDisplayConfig,
  saveDisplayConfig,
} from './lib/api'
import { ChevronLeft, ChevronRight, PanelLeftClose, PanelRightClose, Folder } from 'lucide-react'
import { ToastContainer, ToastType } from './components/Toast'
import { TemplateGallery } from './components/TemplateGallery'
import { LogsAndSessionsViewer } from './components/LogsAndSessionsViewer'
import { AskUserModal } from './components/AskUserModal'
import { UIPreviewModal } from './components/UIPreviewModal'
import { useSessionRestore } from './hooks/useSessionRestore'

const STORAGE_KEY_PROJECT_PATH = 'claude-flow-last-project-path'
const STORAGE_KEY_SESSION_ID = 'claude-flow-workflow-session-id'

function App() {
  const {
    getWorkflow: getCurrentWorkflow,
    loadWorkflow,
    workflowName,
    setWorkflowName,
    currentWorkflowFileName,
    setCurrentWorkflowFileName,
    nodes,
    edges,
    restoreFromSession,
    execution,
    setSelectedNodeId,
    clearPendingUserInput,
  } = useWorkflowStore()

  // 프로젝트 관련 상태
  const [currentProjectPath, setCurrentProjectPath] = useState<string | null>(null)
  const [showProjectDialog, setShowProjectDialog] = useState(false)

  // 템플릿 갤러리 상태
  const [showTemplateGallery, setShowTemplateGallery] = useState(false)

  // 로그/세션 뷰어 상태
  const [showLogsViewer, setShowLogsViewer] = useState(false)

  // UI Preview 모달 상태
  const [showUIPreview, setShowUIPreview] = useState(false)

  // 사이드바 토글 상태
  const [leftSidebarOpen, setLeftSidebarOpen] = useState(true)
  const [rightSidebarOpen, setRightSidebarOpen] = useState(true)

  // 저장 상태 표시
  const [saveStatus, setSaveStatus] = useState<'idle' | 'pending' | 'saving' | 'saved'>('idle')

  // 자동 저장 타이머 추적
  const autoSaveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // 초기 로드 완료 여부 (무한 루프 방지용)
  const initialLoadDone = useRef(false)

  // 토스트 알림 상태
  const [toasts, setToasts] = useState<Array<{
    id: string
    type: ToastType
    message: string
    duration?: number
  }>>([])


  // 토스트 추가 함수 (useCallback으로 메모이제이션)
  const addToast = useCallback((type: ToastType, message: string, duration = 3000) => {
    const id = `toast-${Date.now()}`
    setToasts((prev) => [...prev, { id, type, message, duration }])
  }, [])

  // 토스트 제거 함수
  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  // Display 설정 로드 (앱 시작 시 항상 실행)
  useEffect(() => {
    const loadDisplaySettings = async () => {
      try {
        const config = await loadDisplayConfig()
        setLeftSidebarOpen(config.left_sidebar_open)
        setRightSidebarOpen(config.right_sidebar_open)
        console.log('✅ Display 설정 로드:', config)
      } catch (err) {
        console.warn('Display 설정 로드 실패 (기본값 사용):', err)
      }
    }

    loadDisplaySettings()
  }, [])

  // 세션 복원 (앱 시작 시 자동 로드)
  useSessionRestore({
    onProjectPathChange: setCurrentProjectPath,
    onWorkflowFileNameChange: setCurrentWorkflowFileName,
    addToast,
    initialLoadDone,
  })

  // 수동 저장 핸들러
  const handleManualSave = useCallback(() => {
    // 실행 중일 때는 저장 금지
    if (execution.isExecuting) {
      addToast('warning', '워크플로우 실행 중에는 저장할 수 없습니다')
      return
    }

    if (currentProjectPath && nodes.length > 0) {
      // 자동 저장 타이머가 있으면 취소
      if (autoSaveTimerRef.current) {
        clearTimeout(autoSaveTimerRef.current)
        autoSaveTimerRef.current = null
        console.log('🚫 자동 저장 타이머 취소됨 (수동 저장 시작)')
      }

      setSaveStatus('saving')
      const workflow = getCurrentWorkflow()
      saveProjectWorkflowByName(currentWorkflowFileName, workflow)
        .then(() => {
          setSaveStatus('saved')
          addToast('success', '워크플로우가 저장되었습니다')
          setTimeout(() => setSaveStatus('idle'), 2000)
        })
        .catch((err) => {
          setSaveStatus('idle')
          addToast('error', `저장 실패: ${err}`)
        })
    } else {
      addToast('warning', '저장할 프로젝트 또는 노드가 없습니다')
    }
  }, [execution.isExecuting, currentProjectPath, nodes, getCurrentWorkflow, addToast, currentWorkflowFileName])

  // Human-in-the-Loop: 사용자 입력 핸들러
  const handleUserInputSubmit = useCallback(async (answer: string) => {
    if (!execution.pendingUserInput) return

    try {
      await sendUserInput(execution.pendingUserInput.sessionId, answer)
      clearPendingUserInput()
      addToast('success', '답변이 Worker에게 전달되었습니다')
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : String(err)
      addToast('error', `답변 전송 실패: ${errorMsg}`)
    }
  }, [execution.pendingUserInput, clearPendingUserInput, addToast])

  const handleUserInputCancel = useCallback(() => {
    clearPendingUserInput()
    addToast('warning', '사용자 입력이 취소되었습니다')
  }, [clearPendingUserInput, addToast])

  // 전역 키보드 단축키 핸들링
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const isMac = navigator.platform.toUpperCase().indexOf('MAC') >= 0
      const cmdOrCtrl = isMac ? e.metaKey : e.ctrlKey

      // Cmd/Ctrl + S: 수동 저장
      if (cmdOrCtrl && e.key === 's') {
        e.preventDefault()
        handleManualSave()
      }

      // Esc: 선택 해제
      if (e.key === 'Escape' && !showProjectDialog) {
        setSelectedNodeId(null)
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [showProjectDialog, handleManualSave, setSelectedNodeId])

  // 노드/엣지 변경 시 자동 저장 (debounce)
  useEffect(() => {
    // 프로젝트 선택되지 않았거나 노드가 없으면 스킵
    if (!currentProjectPath || nodes.length === 0) {
      // 노드가 있는데 프로젝트가 선택되지 않았으면 경고
      if (nodes.length > 0 && !currentProjectPath) {
        console.warn('⚠️  프로젝트가 선택되지 않았습니다. 자동 저장을 건너뜁니다.')
      }
      return
    }

    // 실행 중일 때는 자동 저장 스킵
    if (execution.isExecuting) {
      console.log('⏸️  워크플로우 실행 중이므로 자동 저장을 건너뜁니다.')
      return
    }

    // 자동 저장 대기 상태 (5초 타이머 시작)
    setSaveStatus('pending')

    const timer = setTimeout(() => {
      // 실제 저장 시작 - 상태를 'saving'으로 변경
      setSaveStatus('saving')
      const workflow = getCurrentWorkflow()

      saveProjectWorkflowByName(currentWorkflowFileName, workflow)
        .then(() => {
          console.log('✅ 자동 저장 완료')
          setSaveStatus('saved')
          addToast('success', '워크플로우가 자동 저장되었습니다')
          autoSaveTimerRef.current = null
          // 2초 후 상태 초기화
          setTimeout(() => setSaveStatus('idle'), 2000)
        })
        .catch((err) => {
          console.error('❌ 자동 저장 실패:', err)
          setSaveStatus('idle')
          autoSaveTimerRef.current = null
          const errorMsg = err instanceof Error ? err.message : String(err)
          addToast('error', `자동 저장 실패: ${errorMsg}`)
        })
    }, 5000) // 5초 debounce

    // 타이머를 ref에 저장 (수동 저장 시 취소 가능하도록)
    autoSaveTimerRef.current = timer

    return () => {
      clearTimeout(timer)
      if (autoSaveTimerRef.current === timer) {
        autoSaveTimerRef.current = null
      }
    }
  }, [nodes, edges, workflowName, currentProjectPath, execution.isExecuting, getCurrentWorkflow, addToast, currentWorkflowFileName])

  // Display 설정 변경 시 자동 저장 (debounce)
  useEffect(() => {
    // 프로젝트 선택되지 않았으면 스킵
    if (!currentProjectPath) {
      return
    }

    // 초기 로드 중이면 스킵 (무한 루프 방지)
    if (!initialLoadDone.current) {
      return
    }

    const timer = setTimeout(async () => {
      try {
        // 기존 설정 로드 (expanded_sections 보존)
        const existingConfig = await loadDisplayConfig()

        const displayConfig = {
          left_sidebar_open: leftSidebarOpen,
          right_sidebar_open: rightSidebarOpen,
          expanded_sections: existingConfig.expanded_sections, // 기존 값 유지
        }

        console.log('💾 Display 설정 자동 저장 중 (사이드바)...', displayConfig)

        await saveDisplayConfig(displayConfig)
        console.log('✅ Display 설정 자동 저장 완료')
      } catch (err) {
        console.error('❌ Display 설정 저장 실패:', err)
      }
    }, 1000) // 1초 debounce

    return () => clearTimeout(timer)
  }, [leftSidebarOpen, rightSidebarOpen, currentProjectPath])

  // 프로젝트 선택 핸들러
  const handleSelectProject = async (path: string) => {
    try {
      const result = await selectProject(path)
      setCurrentProjectPath(result.project_path)
      localStorage.setItem(STORAGE_KEY_PROJECT_PATH, result.project_path)

      // 워크플로우 목록 로드
      try {
        const workflowsResult = await listProjectWorkflows()

        if (workflowsResult.workflows.length > 0) {
          // 첫 번째 워크플로우 로드
          const firstWorkflow = workflowsResult.workflows[0]
          const workflowData = await loadProjectWorkflowByName(firstWorkflow.name)
          loadWorkflow(workflowData.workflow)
          setCurrentWorkflowFileName(firstWorkflow.name)
          addToast('success', `프로젝트 및 워크플로우 로드 완료: ${workflowData.workflow.name}`)
        } else {
          // 워크플로우가 없으면 기본 워크플로우 생성 (빈 워크플로우)
          addToast('info', '새 프로젝트가 선택되었습니다. 워크플로우를 구성하세요.')
        }
      } catch (err) {
        console.warn('워크플로우 로드 실패:', err)
        addToast('warning', '워크플로우를 로드할 수 없습니다. 새로운 워크플로우를 생성하세요.')
      }

      setShowProjectDialog(false)
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : String(err)
      addToast('error', `프로젝트 선택 실패: ${errorMsg}`)
    }
  }

  // 세션 비우기 핸들러
  const handleClearSessions = async () => {
    if (!currentProjectPath) {
      addToast('warning', '프로젝트가 선택되지 않았습니다')
      return
    }

    if (!confirm('모든 세션 데이터를 삭제하시겠습니까? 이 작업은 되돌릴 수 없습니다.')) {
      return
    }

    try {
      const result = await clearProjectSessions()
      addToast(
        'success',
        `${result.message} (${result.deleted_files}개 파일, ${result.freed_space_mb} MB 확보)`
      )

      // localStorage의 세션 ID도 삭제
      localStorage.removeItem(STORAGE_KEY_SESSION_ID)
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : String(err)
      addToast('error', `세션 삭제 실패: ${errorMsg}`)
    }
  }

  // 로그 비우기 핸들러
  const handleClearLogs = async () => {
    if (!currentProjectPath) {
      addToast('warning', '프로젝트가 선택되지 않았습니다')
      return
    }

    if (!confirm('모든 로그 파일을 삭제하시겠습니까? 이 작업은 되돌릴 수 없습니다.')) {
      return
    }

    try {
      const result = await clearProjectLogs()
      addToast(
        'success',
        `${result.message} (${result.deleted_files}개 파일, ${result.freed_space_mb} MB 확보)`
      )
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : String(err)
      addToast('error', `로그 삭제 실패: ${errorMsg}`)
    }
  }

  // 모든 노드 세션 초기화 핸들러
  const handleClearNodeSessions = async () => {
    if (!currentProjectPath) {
      addToast('warning', '프로젝트가 선택되지 않았습니다')
      return
    }

    if (!confirm('모든 노드의 세션을 초기화하시겠습니까?\n각 노드의 대화 기록이 모두 삭제됩니다.')) {
      return
    }

    try {
      const result = await clearNodeSessions()
      addToast('success', `세션 초기화 완료! ${result.deleted_sessions}개의 세션이 삭제되었습니다.`)
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : String(err)
      addToast('error', `세션 초기화 실패: ${errorMsg}`)
    }
  }

  return (
    <ReactFlowProvider>
      <div className="h-screen flex flex-col bg-background transition-colors duration-300">
        {/* 헤더 */}
        <HeaderBar
          currentProjectPath={currentProjectPath}
          currentWorkflow={getCurrentWorkflow()}
          currentWorkflowFileName={currentWorkflowFileName}
          workflowName={workflowName}
          saveStatus={saveStatus}
          nodeCount={nodes.length}
          isExecuting={execution.isExecuting}
          onWorkflowChange={(workflow, workflowName) => {
            loadWorkflow(workflow)
            setCurrentWorkflowFileName(workflowName)
          }}
          onWorkflowNameChange={setWorkflowName}
          onManualSave={handleManualSave}
          onOpenTemplateGallery={() => setShowTemplateGallery(true)}
          onOpenProjectDialog={() => setShowProjectDialog(true)}
          onOpenUIPreview={() => setShowUIPreview(true)}
          onOpenLogsViewer={() => setShowLogsViewer(true)}
          onClearNodeSessions={handleClearNodeSessions}
          onClearSessions={handleClearSessions}
          onClearLogs={handleClearLogs}
        />

        {/* 프로젝트 미선택 경고 배너 */}
        {!currentProjectPath && (
          <div className="bg-yellow-100 border-b border-yellow-300 px-6 py-3 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="text-yellow-800 font-medium">
                ⚠️ 프로젝트가 선택되지 않았습니다
              </div>
              <div className="text-yellow-700 text-sm">
                워크플로우를 저장하려면 먼저 프로젝트를 선택하세요.
              </div>
            </div>
            <Button
              size="sm"
              onClick={() => setShowProjectDialog(true)}
              className="bg-yellow-600 hover:bg-yellow-700 text-white"
            >
              <Folder className="mr-2 h-4 w-4" />
              프로젝트 선택
            </Button>
          </div>
        )}

        {/* 메인 레이아웃 */}
        <div className="flex-1 flex overflow-hidden">
          {/* 왼쪽: 노드 패널 */}
          {leftSidebarOpen && (
            <aside className="w-80 border-r bg-white p-4 overflow-y-auto transition-transform duration-300 ease-out">
              <NodePanel />
            </aside>
          )}

          {/* 중앙: 캔버스 */}
          <main className="flex-1 relative">
            <WorkflowCanvas />

            {/* 사이드바 토글 버튼 */}
            <div className="absolute top-4 left-4 flex gap-2 z-10">
              <Button
                size="sm"
                variant="outline"
                className="bg-white shadow-md"
                onClick={() => setLeftSidebarOpen(!leftSidebarOpen)}
                title={leftSidebarOpen ? "왼쪽 패널 닫기" : "왼쪽 패널 열기"}
              >
                {leftSidebarOpen ? (
                  <PanelLeftClose className="h-4 w-4" />
                ) : (
                  <ChevronRight className="h-4 w-4" />
                )}
              </Button>
            </div>

            <div className="absolute top-4 right-4 flex gap-2 z-10">
              <Button
                size="sm"
                variant="outline"
                className="bg-white shadow-md"
                onClick={() => setRightSidebarOpen(!rightSidebarOpen)}
                title={rightSidebarOpen ? "오른쪽 패널 닫기" : "오른쪽 패널 열기"}
              >
                {rightSidebarOpen ? (
                  <PanelRightClose className="h-4 w-4" />
                ) : (
                  <ChevronLeft className="h-4 w-4" />
                )}
              </Button>
            </div>
          </main>

          {/* 오른쪽: 탭 기반 사이드바 */}
          {rightSidebarOpen && <RightSidebar addToast={addToast} />}
        </div>

        {/* 토스트 알림 */}
        <ToastContainer toasts={toasts} onRemoveToast={removeToast} />

        {/* 템플릿 갤러리 */}
        {showTemplateGallery && (
          <TemplateGallery
            onClose={() => setShowTemplateGallery(false)}
            onSelectTemplate={(workflow) => {
              loadWorkflow(workflow)
              addToast('success', `템플릿 "${workflow.name}"이(가) 로드되었습니다`)
            }}
            onImportTemplate={(workflow) => {
              loadWorkflow(workflow)
              addToast('success', `워크플로우 "${workflow.name}"이(가) 가져오기 되었습니다`)
            }}
          />
        )}

        {/* UI Preview 모달 */}
        <UIPreviewModal
          isOpen={showUIPreview}
          onClose={() => setShowUIPreview(false)}
        />

        {/* 로그 & 세션 뷰어 */}
        <LogsAndSessionsViewer
          isOpen={showLogsViewer}
          onClose={() => setShowLogsViewer(false)}
          projectPath={currentProjectPath}
        />

        {/* 프로젝트 선택 다이얼로그 */}
        <ProjectSelector
          isOpen={showProjectDialog}
          currentProjectPath={currentProjectPath}
          onSelectProject={handleSelectProject}
          onClose={() => setShowProjectDialog(false)}
        />

        {/* Human-in-the-Loop: 사용자 입력 모달 */}
        {execution.pendingUserInput && (
          <AskUserModal
            question={execution.pendingUserInput.question}
            onSubmit={handleUserInputSubmit}
            onCancel={handleUserInputCancel}
          />
        )}
      </div>
    </ReactFlowProvider>
  )
}

export default App
