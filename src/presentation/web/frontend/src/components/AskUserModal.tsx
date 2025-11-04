/**
 * Human-in-the-Loop 사용자 입력 모달
 *
 * Worker가 ask_user를 호출하면 이 모달이 표시됩니다.
 */

import { useState } from 'react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { MessageCircleQuestion } from 'lucide-react'

interface AskUserModalProps {
  question: string
  onSubmit: (answer: string) => void
  onCancel: () => void
}

export const AskUserModal: React.FC<AskUserModalProps> = ({
  question,
  onSubmit,
  onCancel,
}) => {
  const [answer, setAnswer] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  const handleSubmit = async () => {
    if (!answer.trim()) return

    setIsSubmitting(true)
    try {
      await onSubmit(answer)
      setAnswer('')
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    // Ctrl+Enter로 제출
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
      e.preventDefault()
      handleSubmit()
    }
  }

  return (
    <Dialog open={true} onOpenChange={(open) => !open && onCancel()}>
      <DialogContent className="sm:max-w-[600px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <MessageCircleQuestion className="h-5 w-5 text-blue-600" />
            Worker가 질문합니다
          </DialogTitle>
          <DialogDescription>
            워크플로우 실행 중 사용자 입력이 필요합니다
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <label className="text-sm font-medium">질문</label>
            <div className="p-3 bg-blue-50 border border-blue-200 rounded-md text-sm">
              {question}
            </div>
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium">답변</label>
            <Textarea
              value={answer}
              onChange={(e) => setAnswer(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="답변을 입력하세요... (Ctrl+Enter로 제출)"
              className="min-h-[120px] resize-none"
              autoFocus
            />
            <p className="text-xs text-muted-foreground">
              Ctrl+Enter를 눌러 빠르게 제출할 수 있습니다
            </p>
          </div>
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={onCancel}
            disabled={isSubmitting}
          >
            취소
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={!answer.trim() || isSubmitting}
          >
            {isSubmitting ? '제출 중...' : '답변 제출'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
