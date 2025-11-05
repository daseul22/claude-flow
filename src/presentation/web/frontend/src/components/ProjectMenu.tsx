/**
 * 프로젝트 관리 메뉴 컴포넌트
 *
 * 프로젝트 관련 작업을 수행하는 드롭다운 메뉴
 * - 로그 & 세션 보기
 * - 노드 세션 초기화
 * - 프로젝트 세션 비우기
 * - 로그 비우기
 */

import { useState, useEffect } from 'react'
import { Button } from './ui/button'
import { Settings, Eye, Trash2, FileText } from 'lucide-react'

interface ProjectMenuProps {
  /**
   * 프로젝트 경로 (null이면 메뉴 비활성화)
   */
  projectPath: string | null

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
 * 프로젝트 관리 드롭다운 메뉴
 */
export function ProjectMenu({
  projectPath,
  onOpenLogsViewer,
  onClearNodeSessions,
  onClearSessions,
  onClearLogs,
}: ProjectMenuProps) {
  const [isOpen, setIsOpen] = useState(false)

  // 외부 클릭 감지로 메뉴 닫기
  useEffect(() => {
    if (!isOpen) return

    const handleClickOutside = (e: MouseEvent) => {
      const target = e.target as HTMLElement
      // 메뉴 버튼이나 메뉴 내부를 클릭한 경우 무시
      if (target.closest('.project-menu-container')) {
        return
      }
      setIsOpen(false)
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [isOpen])

  return (
    <div className="relative project-menu-container">
      <Button
        onClick={() => setIsOpen(!isOpen)}
        variant="outline"
        disabled={!projectPath}
        title="프로젝트 관리"
        aria-label="프로젝트 관리 메뉴 열기"
        aria-expanded={isOpen}
        aria-haspopup="true"
      >
        <Settings className="h-4 w-4" />
      </Button>

      {/* 드롭다운 메뉴 */}
      {isOpen && projectPath && (
        <div
          className="absolute right-0 top-full mt-2 w-56 bg-white border rounded-lg shadow-lg z-50"
          role="menu"
          aria-label="프로젝트 관리 메뉴"
        >
          <div className="py-1">
            <button
              onClick={() => {
                onOpenLogsViewer()
                setIsOpen(false)
              }}
              className="w-full text-left px-4 py-2 hover:bg-gray-100 flex items-center gap-2 transition-colors"
              role="menuitem"
              aria-label="로그 및 세션 보기"
            >
              <Eye className="h-4 w-4 text-green-600" />
              <span>로그 & 세션 보기</span>
            </button>

            <button
              onClick={async () => {
                await onClearNodeSessions()
                setIsOpen(false)
              }}
              className="w-full text-left px-4 py-2 hover:bg-gray-100 flex items-center gap-2 transition-colors"
              role="menuitem"
              aria-label="모든 노드 세션 초기화"
            >
              <Trash2 className="h-4 w-4 text-red-600" />
              <span>모든 노드 세션 초기화</span>
            </button>

            <button
              onClick={async () => {
                await onClearSessions()
                setIsOpen(false)
              }}
              className="w-full text-left px-4 py-2 hover:bg-gray-100 flex items-center gap-2 transition-colors"
              role="menuitem"
              aria-label="프로젝트 세션 비우기"
            >
              <Trash2 className="h-4 w-4 text-orange-600" />
              <span>프로젝트 세션 비우기</span>
            </button>

            <button
              onClick={async () => {
                await onClearLogs()
                setIsOpen(false)
              }}
              className="w-full text-left px-4 py-2 hover:bg-gray-100 flex items-center gap-2 transition-colors"
              role="menuitem"
              aria-label="로그 비우기"
            >
              <FileText className="h-4 w-4 text-blue-600" />
              <span>로그 비우기</span>
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
