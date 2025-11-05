/**
 * 헤더 바 컴포넌트
 *
 * 애플리케이션 상단 헤더 (타이틀, 워크플로우 정보, 저장 버튼 등)
 * - 워크플로우 이름 및 선택
 * - 프로젝트 정보 표시
 * - 저장 버튼 (수동 저장 및 상태 표시)
 * - 템플릿 갤러리 버튼
 * - 프로젝트 선택 버튼
 * - 프로젝트 관리 메뉴
 */

import { WorkflowSelector } from './WorkflowSelector'
import { Button } from './ui/button'
import { ProjectMenu } from './ProjectMenu'
import { Workflow } from '../lib/api'
import { Folder, BookTemplate, Save } from 'lucide-react'

interface HeaderBarProps {
  /**
   * 현재 프로젝트 경로
   */
  currentProjectPath: string | null

  /**
   * 현재 워크플로우
   */
  currentWorkflow: Workflow

  /**
   * 현재 워크플로우 파일명
   */
  currentWorkflowFileName: string

  /**
   * 워크플로우 이름
   */
  workflowName: string

  /**
   * 저장 상태
   */
  saveStatus: 'idle' | 'pending' | 'saving' | 'saved'

  /**
   * 노드 개수 (저장 버튼 활성화 조건)
   */
  nodeCount: number

  /**
   * 실행 중 여부 (저장 버튼 비활성화 조건)
   */
  isExecuting: boolean

  /**
   * 워크플로우 변경 핸들러
   */
  onWorkflowChange: (workflow: Workflow, workflowName: string) => void

  /**
   * 워크플로우 이름 변경 핸들러
   */
  onWorkflowNameChange: (name: string) => void

  /**
   * 수동 저장 핸들러
   */
  onManualSave: () => void

  /**
   * 템플릿 갤러리 열기 핸들러
   */
  onOpenTemplateGallery: () => void

  /**
   * 프로젝트 선택 다이얼로그 열기 핸들러
   */
  onOpenProjectDialog: () => void

  /**
   * 로그 & 세션 뷰어 열기 핸들러
   */
  onOpenLogsViewer: () => void

  /**
   * 노드 세션 초기화 핸들러
   */
  onClearNodeSessions: () => Promise<void>

  /**
   * 프로젝트 세션 비우기 핸들러
   */
  onClearSessions: () => Promise<void>

  /**
   * 로그 비우기 핸들러
   */
  onClearLogs: () => Promise<void>
}

/**
 * 헤더 바 컴포넌트
 */
export function HeaderBar({
  currentProjectPath,
  currentWorkflow,
  currentWorkflowFileName,
  workflowName,
  saveStatus,
  nodeCount,
  isExecuting,
  onWorkflowChange,
  onWorkflowNameChange,
  onManualSave,
  onOpenTemplateGallery,
  onOpenProjectDialog,
  onOpenLogsViewer,
  onClearNodeSessions,
  onClearSessions,
  onClearLogs,
}: HeaderBarProps) {
  return (
    <header className="border-b bg-white px-6 py-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <h1 className="text-2xl font-bold text-primary">Claude Flow</h1>

          {/* 워크플로우 선택 */}
          {currentProjectPath && (
            <WorkflowSelector
              currentProjectPath={currentProjectPath}
              currentWorkflow={currentWorkflow}
              currentWorkflowName={currentWorkflowFileName}
              onWorkflowChange={onWorkflowChange}
              onWorkflowNameChange={onWorkflowNameChange}
            />
          )}

          {/* 워크플로우 이름 입력 */}
          <input
            type="text"
            value={workflowName}
            onChange={(e) => onWorkflowNameChange(e.target.value)}
            className="text-lg font-medium border-b border-transparent hover:border-gray-300 focus:border-primary outline-none px-2"
            placeholder="워크플로우 이름"
            aria-label="워크플로우 이름 입력"
          />

          {/* 프로젝트 경로 표시 */}
          {currentProjectPath && (
            <div className="text-sm text-muted-foreground flex items-center gap-2">
              <Folder className="h-4 w-4" aria-hidden="true" />
              <span
                className="max-w-[200px] truncate"
                title={currentProjectPath}
                aria-label={`현재 프로젝트: ${currentProjectPath}`}
              >
                {currentProjectPath.split('/').pop()}
              </span>
            </div>
          )}

          {/* 저장 상태 표시 */}
          {currentProjectPath && (
            <div
              className="text-xs text-muted-foreground flex items-center gap-1"
              role="status"
              aria-live="polite"
            >
              {saveStatus === 'pending' && (
                <>
                  <div
                    className="w-2 h-2 bg-blue-400 rounded-full animate-pulse"
                    aria-hidden="true"
                  />
                  <span>자동 저장 대기 중...</span>
                </>
              )}
              {saveStatus === 'saving' && (
                <>
                  <div
                    className="w-2 h-2 bg-yellow-500 rounded-full animate-pulse"
                    aria-hidden="true"
                  />
                  <span>저장 중...</span>
                </>
              )}
              {saveStatus === 'saved' && (
                <>
                  <div
                    className="w-2 h-2 bg-green-500 rounded-full"
                    aria-hidden="true"
                  />
                  <span>저장됨</span>
                </>
              )}
            </div>
          )}
        </div>

        {/* 오른쪽 버튼 그룹 */}
        <div className="flex gap-2">
          <Button
            onClick={onManualSave}
            variant="outline"
            disabled={!currentProjectPath || nodeCount === 0 || isExecuting}
            title={
              isExecuting
                ? '워크플로우 실행 중에는 저장할 수 없습니다'
                : '워크플로우 저장 (Cmd+S)'
            }
            aria-label="워크플로우 수동 저장"
          >
            <Save className="mr-2 h-4 w-4" />
            저장
          </Button>

          <Button
            onClick={onOpenTemplateGallery}
            variant="outline"
            aria-label="템플릿 갤러리 열기"
          >
            <BookTemplate className="mr-2 h-4 w-4" />
            템플릿
          </Button>

          <Button
            onClick={onOpenProjectDialog}
            variant="outline"
            aria-label="프로젝트 선택 다이얼로그 열기"
          >
            <Folder className="mr-2 h-4 w-4" />
            프로젝트 선택
          </Button>

          {/* 프로젝트 관리 메뉴 */}
          <ProjectMenu
            projectPath={currentProjectPath}
            onOpenLogsViewer={onOpenLogsViewer}
            onClearNodeSessions={onClearNodeSessions}
            onClearSessions={onClearSessions}
            onClearLogs={onClearLogs}
          />
        </div>
      </div>
    </header>
  )
}
