/**
 * UI Preview 모달
 *
 * 실험적인 로그 UI 기능들을 미리 볼 수 있는 모달
 * 나중에 실험적 기능을 추가할 때 사용할 수 있는 기본 틀
 */

import { X } from 'lucide-react'
import { Button } from './ui/button'

interface UIPreviewModalProps {
  isOpen: boolean
  onClose: () => void
}

/**
 * UI Preview 메인 모달
 */
export function UIPreviewModal({ isOpen, onClose }: UIPreviewModalProps) {
  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg w-full h-full max-w-6xl max-h-[90vh] flex flex-col shadow-2xl">
        {/* 헤더 */}
        <div className="flex items-center justify-between p-4 border-b">
          <div>
            <h2 className="text-xl font-bold">🎨 UI Preview (실험적 기능)</h2>
            <p className="text-sm text-gray-600 mt-1">
              실험적 UI 기능을 테스트할 수 있는 공간입니다
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <X className="w-5 h-5 text-gray-600" />
          </button>
        </div>

        {/* 콘텐츠 영역 */}
        <div className="flex-1 overflow-y-auto p-6">
          <div className="flex flex-col items-center justify-center h-full text-gray-500">
            <div className="text-6xl mb-4">🚧</div>
            <h3 className="text-xl font-semibold mb-2">준비 중입니다</h3>
            <p className="text-sm text-center max-w-md">
              실험적 UI 기능이 필요할 때 이 공간을 활용할 수 있습니다.
              <br />
              새로운 아이디어를 빠르게 프로토타입할 수 있는 샌드박스입니다.
            </p>
          </div>
        </div>

        {/* 푸터 */}
        <div className="p-4 border-t bg-gray-50 flex justify-between items-center">
          <p className="text-xs text-gray-600">
            💡 실험적 기능을 추가하려면 이 모달을 확장하세요.
          </p>
          <Button onClick={onClose} variant="outline">
            닫기
          </Button>
        </div>
      </div>
    </div>
  )
}
