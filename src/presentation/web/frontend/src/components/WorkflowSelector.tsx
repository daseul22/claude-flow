import { useEffect, useState } from 'react'
import { ChevronDown, Plus, Trash2, Edit2, Check, X } from 'lucide-react'
import {
  listProjectWorkflows,
  loadProjectWorkflowByName,
  saveProjectWorkflowByName,
  deleteProjectWorkflow,
  renameProjectWorkflow,
  type WorkflowInfo,
  type Workflow,
} from '../lib/api'
import { Button } from './ui/button'

interface WorkflowSelectorProps {
  currentProjectPath: string | null
  currentWorkflow: Workflow | null
  currentWorkflowName: string
  onWorkflowChange: (workflow: Workflow, workflowName: string) => void
  onWorkflowNameChange: (name: string) => void
}

export function WorkflowSelector({
  currentProjectPath,
  currentWorkflow: _currentWorkflow,
  currentWorkflowName,
  onWorkflowChange,
  onWorkflowNameChange,
}: WorkflowSelectorProps) {
  const [workflows, setWorkflows] = useState<WorkflowInfo[]>([])
  const [showDropdown, setShowDropdown] = useState(false)
  const [isCreating, setIsCreating] = useState(false)
  const [newWorkflowName, setNewWorkflowName] = useState('')
  const [isRenaming, setIsRenaming] = useState<string | null>(null)
  const [renamingValue, setRenamingValue] = useState('')
  const [error, setError] = useState<string | null>(null)

  // 워크플로우 목록 로드
  const loadWorkflows = async () => {
    if (!currentProjectPath) return

    try {
      const result = await listProjectWorkflows()
      setWorkflows(result.workflows)
    } catch (err: any) {
      console.error('워크플로우 목록 로드 실패:', err)
      setError(err.message || '워크플로우 목록을 로드할 수 없습니다')
    }
  }

  // 프로젝트 선택 시 워크플로우 목록 로드
  useEffect(() => {
    if (currentProjectPath) {
      loadWorkflows()
    }
  }, [currentProjectPath])

  // 워크플로우 선택
  const handleSelectWorkflow = async (workflowName: string) => {
    try {
      setError(null)
      const result = await loadProjectWorkflowByName(workflowName)
      onWorkflowChange(result.workflow, workflowName)
      setShowDropdown(false)
    } catch (err: any) {
      console.error('워크플로우 로드 실패:', err)
      setError(err.message || '워크플로우를 로드할 수 없습니다')
    }
  }

  // 새 워크플로우 생성
  const handleCreateWorkflow = async () => {
    if (!newWorkflowName.trim()) {
      setError('워크플로우 이름을 입력하세요')
      return
    }

    try {
      setError(null)

      // 빈 워크플로우 생성
      const emptyWorkflow: Workflow = {
        name: newWorkflowName,
        description: '',
        nodes: [],
        edges: [],
      }

      await saveProjectWorkflowByName(newWorkflowName, emptyWorkflow)
      onWorkflowChange(emptyWorkflow, newWorkflowName)

      // 목록 갱신
      await loadWorkflows()

      setIsCreating(false)
      setNewWorkflowName('')
      setShowDropdown(false)
    } catch (err: any) {
      console.error('워크플로우 생성 실패:', err)
      setError(err.message || '워크플로우를 생성할 수 없습니다')
    }
  }

  // 워크플로우 삭제
  const handleDeleteWorkflow = async (workflowName: string, e: React.MouseEvent) => {
    e.stopPropagation()

    if (!confirm(`워크플로우 "${workflowName}"를 삭제하시겠습니까?`)) {
      return
    }

    try {
      setError(null)
      await deleteProjectWorkflow(workflowName)

      // 목록 갱신
      await loadWorkflows()

      // 삭제된 워크플로우가 현재 워크플로우면 다른 워크플로우 로드
      if (currentWorkflowName === workflowName) {
        const remaining = workflows.filter((w) => w.name !== workflowName)
        if (remaining.length > 0) {
          await handleSelectWorkflow(remaining[0].name)
        } else {
          // 워크플로우가 하나도 없으면 빈 워크플로우 생성
          const defaultWorkflow: Workflow = {
            name: 'default',
            description: '',
            nodes: [],
            edges: [],
          }
          onWorkflowChange(defaultWorkflow, 'default')
        }
      }
    } catch (err: any) {
      console.error('워크플로우 삭제 실패:', err)
      setError(err.message || '워크플로우를 삭제할 수 없습니다')
    }
  }

  // 워크플로우 이름 변경 시작
  const handleStartRename = (workflowName: string, e: React.MouseEvent) => {
    e.stopPropagation()
    setIsRenaming(workflowName)
    setRenamingValue(workflowName)
  }

  // 워크플로우 이름 변경 완료
  const handleCompleteRename = async (oldName: string) => {
    if (!renamingValue.trim() || renamingValue === oldName) {
      setIsRenaming(null)
      return
    }

    try {
      setError(null)
      await renameProjectWorkflow(oldName, renamingValue)

      // 목록 갱신
      await loadWorkflows()

      // 이름 변경된 워크플로우가 현재 워크플로우면 이름 업데이트
      if (currentWorkflowName === oldName) {
        onWorkflowNameChange(renamingValue)
      }

      setIsRenaming(null)
    } catch (err: any) {
      console.error('워크플로우 이름 변경 실패:', err)
      setError(err.message || '워크플로우 이름을 변경할 수 없습니다')
    }
  }

  // 워크플로우 이름 변경 취소
  const handleCancelRename = () => {
    setIsRenaming(null)
    setRenamingValue('')
  }

  if (!currentProjectPath) {
    return null
  }

  return (
    <div className="relative">
      {/* 현재 워크플로우 표시 및 드롭다운 버튼 */}
      <button
        onClick={() => setShowDropdown(!showDropdown)}
        className="flex items-center gap-2 px-3 py-1.5 border rounded-md hover:bg-gray-50 transition-colors"
      >
        <span className="text-sm font-medium">{currentWorkflowName || 'default'}</span>
        <ChevronDown className="h-4 w-4 text-gray-500" />
      </button>

      {/* 드롭다운 메뉴 */}
      {showDropdown && (
        <div className="absolute left-0 top-full mt-2 w-80 bg-white border rounded-lg shadow-lg z-50">
          {/* 헤더 */}
          <div className="px-4 py-3 border-b">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold">워크플로우 선택</h3>
              <button
                onClick={() => {
                  setIsCreating(true)
                  setNewWorkflowName('')
                }}
                className="text-primary hover:text-primary/80 transition-colors"
                title="새 워크플로우 생성"
              >
                <Plus className="h-4 w-4" />
              </button>
            </div>
          </div>

          {/* 에러 메시지 */}
          {error && (
            <div className="px-4 py-2 bg-red-50 border-b border-red-200">
              <p className="text-xs text-red-600">{error}</p>
            </div>
          )}

          {/* 새 워크플로우 생성 폼 */}
          {isCreating && (
            <div className="px-4 py-3 border-b bg-gray-50">
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  value={newWorkflowName}
                  onChange={(e) => setNewWorkflowName(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      handleCreateWorkflow()
                    } else if (e.key === 'Escape') {
                      setIsCreating(false)
                      setNewWorkflowName('')
                    }
                  }}
                  placeholder="워크플로우 이름 입력"
                  className="flex-1 px-2 py-1 border rounded text-sm outline-none focus:ring-2 focus:ring-primary"
                  autoFocus
                />
                <Button
                  size="sm"
                  onClick={handleCreateWorkflow}
                  disabled={!newWorkflowName.trim()}
                >
                  <Check className="h-3 w-3" />
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    setIsCreating(false)
                    setNewWorkflowName('')
                  }}
                >
                  <X className="h-3 w-3" />
                </Button>
              </div>
            </div>
          )}

          {/* 워크플로우 목록 */}
          <div className="max-h-96 overflow-y-auto">
            {workflows.length === 0 ? (
              <div className="px-4 py-8 text-center text-sm text-gray-500">
                워크플로우가 없습니다.
              </div>
            ) : (
              workflows.map((workflow) => (
                <div
                  key={workflow.name}
                  className={`px-4 py-3 hover:bg-gray-50 transition-colors cursor-pointer border-b last:border-b-0 ${
                    currentWorkflowName === workflow.name ? 'bg-blue-50' : ''
                  }`}
                  onClick={() => handleSelectWorkflow(workflow.name)}
                >
                  {isRenaming === workflow.name ? (
                    // 이름 변경 모드
                    <div className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
                      <input
                        type="text"
                        value={renamingValue}
                        onChange={(e) => setRenamingValue(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') {
                            handleCompleteRename(workflow.name)
                          } else if (e.key === 'Escape') {
                            handleCancelRename()
                          }
                        }}
                        className="flex-1 px-2 py-1 border rounded text-sm outline-none focus:ring-2 focus:ring-primary"
                        autoFocus
                      />
                      <button
                        onClick={() => handleCompleteRename(workflow.name)}
                        className="text-green-600 hover:text-green-700"
                      >
                        <Check className="h-4 w-4" />
                      </button>
                      <button
                        onClick={handleCancelRename}
                        className="text-gray-600 hover:text-gray-700"
                      >
                        <X className="h-4 w-4" />
                      </button>
                    </div>
                  ) : (
                    // 일반 모드
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <h4 className="text-sm font-medium truncate">
                            {workflow.display_name}
                          </h4>
                          {currentWorkflowName === workflow.name && (
                            <span className="text-xs px-1.5 py-0.5 bg-blue-100 text-blue-700 rounded">
                              현재
                            </span>
                          )}
                        </div>
                        {workflow.description && (
                          <p className="text-xs text-gray-500 mt-1 line-clamp-2">
                            {workflow.description}
                          </p>
                        )}
                        <div className="flex items-center gap-3 mt-2 text-xs text-gray-400">
                          <span>
                            {workflow.last_modified
                              ? new Date(workflow.last_modified).toLocaleString('ko-KR', {
                                  month: 'short',
                                  day: 'numeric',
                                  hour: '2-digit',
                                  minute: '2-digit',
                                })
                              : '날짜 없음'}
                          </span>
                          <span>
                            {workflow.size != null
                              ? `${(workflow.size / 1024).toFixed(1)} KB`
                              : '크기 없음'}
                          </span>
                        </div>
                      </div>
                      <div className="flex items-center gap-1">
                        <button
                          onClick={(e) => handleStartRename(workflow.name, e)}
                          className="p-1 text-gray-400 hover:text-blue-600 transition-colors"
                          title="이름 변경"
                        >
                          <Edit2 className="h-3.5 w-3.5" />
                        </button>
                        <button
                          onClick={(e) => handleDeleteWorkflow(workflow.name, e)}
                          className="p-1 text-gray-400 hover:text-red-600 transition-colors"
                          title="삭제"
                          disabled={workflows.length === 1}
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  )
}
