/**
 * 프로젝트 선택 다이얼로그 컴포넌트
 *
 * 사용자가 프로젝트 디렉토리를 선택하는 모달 다이얼로그
 * - 디렉토리 브라우저 또는 텍스트 입력 방식 지원
 * - ESC 키로 닫기
 */

import { useState, useEffect } from 'react'
import { Button } from './ui/button'
import { DirectoryBrowser } from './DirectoryBrowser'
import { Folder } from 'lucide-react'

interface ProjectSelectorProps {
  /**
   * 다이얼로그 표시 여부
   */
  isOpen: boolean

  /**
   * 현재 선택된 프로젝트 경로
   */
  currentProjectPath: string | null

  /**
   * 프로젝트 선택 핸들러
   */
  onSelectProject: (path: string) => Promise<void>

  /**
   * 다이얼로그 닫기 핸들러
   */
  onClose: () => void
}

/**
 * 프로젝트 선택 다이얼로그
 */
export function ProjectSelector({
  isOpen,
  currentProjectPath,
  onSelectProject,
  onClose,
}: ProjectSelectorProps) {
  const [projectPathInput, setProjectPathInput] = useState('')
  const [useBrowser, setUseBrowser] = useState(true)

  // ESC 키 핸들링
  useEffect(() => {
    if (!isOpen) return

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose()
        setProjectPathInput('')
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, onClose])

  // 텍스트 입력으로 프로젝트 선택
  const handleSelectProjectManual = async () => {
    if (!projectPathInput.trim()) {
      return
    }

    await onSelectProject(projectPathInput.trim())
    setProjectPathInput('')
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl max-w-4xl w-full h-[80vh] flex flex-col">
        <div className="border-b p-4 flex items-center justify-between">
          <h2 className="text-xl font-bold">프로젝트 디렉토리 선택</h2>

          {/* 브라우저/텍스트 입력 토글 */}
          <div className="flex gap-2">
            <Button
              size="sm"
              variant={useBrowser ? 'default' : 'outline'}
              onClick={() => setUseBrowser(true)}
              aria-label="디렉토리 브라우저 모드"
            >
              <Folder className="h-4 w-4 mr-2" />
              브라우저
            </Button>
            <Button
              size="sm"
              variant={!useBrowser ? 'default' : 'outline'}
              onClick={() => setUseBrowser(false)}
              aria-label="텍스트 입력 모드"
            >
              텍스트 입력
            </Button>
          </div>
        </div>

        <div className="flex-1 overflow-hidden">
          {useBrowser ? (
            /* 디렉토리 브라우저 */
            <DirectoryBrowser
              onSelectDirectory={(path) => {
                onSelectProject(path)
                setProjectPathInput('')
              }}
              onCancel={() => {
                onClose()
                setProjectPathInput('')
              }}
            />
          ) : (
            /* 텍스트 입력 방식 */
            <div className="p-6 space-y-4">
              <div>
                <label
                  htmlFor="project-path-input"
                  className="block text-sm font-medium mb-2"
                >
                  프로젝트 경로
                </label>
                <input
                  id="project-path-input"
                  type="text"
                  value={projectPathInput}
                  onChange={(e) => setProjectPathInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      handleSelectProjectManual()
                    }
                  }}
                  className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
                  placeholder="/Users/username/my-project"
                  aria-describedby="project-path-hint"
                />
                <p id="project-path-hint" className="text-xs text-muted-foreground mt-1">
                  설정은{' '}
                  <code className="bg-gray-100 px-1 py-0.5 rounded">
                    .claude-flow/workflow-config.json
                  </code>
                  에 저장됩니다.
                </p>
              </div>

              {currentProjectPath && (
                <div
                  className="bg-blue-50 border border-blue-200 rounded-lg p-3"
                  role="status"
                  aria-live="polite"
                >
                  <div className="text-sm font-medium text-blue-900">
                    현재 선택된 프로젝트:
                  </div>
                  <div className="text-sm text-blue-700 mt-1 font-mono">
                    {currentProjectPath}
                  </div>
                </div>
              )}

              <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3">
                <div className="text-sm text-yellow-900">
                  <strong>안내:</strong>
                  <ul className="list-disc list-inside mt-1 space-y-1">
                    <li>로컬 파일 시스템 경로를 입력하세요</li>
                    <li>기존 설정이 있으면 자동으로 로드됩니다</li>
                    <li>워크플로우 변경 시 자동으로 저장됩니다</li>
                  </ul>
                </div>
              </div>

              <div className="mt-6 flex justify-end gap-2">
                <Button
                  variant="outline"
                  onClick={() => {
                    onClose()
                    setProjectPathInput('')
                  }}
                  aria-label="프로젝트 선택 취소"
                >
                  취소
                </Button>
                <Button
                  onClick={handleSelectProjectManual}
                  disabled={!projectPathInput.trim()}
                  aria-label="프로젝트 선택 확인"
                >
                  선택
                </Button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
