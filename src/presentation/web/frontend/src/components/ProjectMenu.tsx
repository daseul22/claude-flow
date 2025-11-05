/**
 * 프로젝트 관리 메뉴 컴포넌트
 *
 * 프로젝트 관련 작업을 수행하는 드롭다운 메뉴
 * - UI Preview (실험적 기능)
 * - 로그 & 세션 보기
 */

import { useState, useEffect } from 'react'
import { Button } from './ui/button'
import { Settings, Eye, Palette } from 'lucide-react'

interface ProjectMenuProps {
  /**
   * 프로젝트 경로 (null이면 메뉴 비활성화)
   */
  projectPath: string | null

  /**
   * UI Preview 모달 열기 핸들러
   */
  onOpenUIPreview: () => void

  /**
   * 로그 & 세션 뷰어 열기 핸들러
   */
  onOpenLogsViewer: () => void
}

/**
 * 프로젝트 관리 드롭다운 메뉴
 */
export function ProjectMenu({
  projectPath,
  onOpenUIPreview,
  onOpenLogsViewer,
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
        title="프로젝트 관리 및 UI 실험"
        aria-label="프로젝트 관리 메뉴 열기"
        aria-expanded={isOpen}
        aria-haspopup="true"
      >
        <Settings className="h-4 w-4" />
      </Button>

      {/* 드롭다운 메뉴 */}
      {isOpen && (
        <div
          className="absolute right-0 top-full mt-2 w-56 bg-white border rounded-lg shadow-lg z-50"
          role="menu"
          aria-label="프로젝트 관리 메뉴"
        >
          <div className="py-1">
            {/* UI Preview (프로젝트 없이도 사용 가능) */}
            <button
              onClick={() => {
                onOpenUIPreview()
                setIsOpen(false)
              }}
              className="w-full text-left px-4 py-2 hover:bg-gray-100 flex items-center gap-2 transition-colors"
              role="menuitem"
              aria-label="UI Preview 열기"
            >
              <Palette className="h-4 w-4 text-purple-600" />
              <span>🎨 UI Preview</span>
              <span className="ml-auto text-xs text-gray-500">실험</span>
            </button>

            {/* 구분선 */}
            {projectPath && <div className="my-1 border-t" />}

            {/* 프로젝트 관련 메뉴들 (프로젝트 선택 시에만) */}
            {projectPath && (
              <button
                onClick={() => {
                  onOpenLogsViewer()
                  setIsOpen(false)
                }}
                className="w-full text-left px-4 py-2 hover:bg-gray-100 flex items-center gap-2 transition-colors"
                role="menuitem"
                aria-label="로그, 세션 및 보고서 관리"
              >
                <Eye className="h-4 w-4 text-green-600" />
                <span>로그, 세션 & 보고서 관리</span>
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
