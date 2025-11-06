/**
 * 워크플로우 자동 설계 모달 컴포넌트
 *
 * workflow_designer를 실행하여 워크플로우를 자동 설계하고,
 * 사용자와 상호작용하며 최종 워크플로우를 캔버스에 적용합니다.
 */

import React, { useState, useRef, useEffect } from 'react'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { designWorkflow } from '@/lib/api'
import { Loader2, Send, Check, X, Wand2, ArrowDown, AlertCircle } from 'lucide-react'
import { ParsedContent } from './ParsedContent'
import { useWorkflowStore } from '@/stores/workflowStore'
import { layoutWorkflow } from '@/lib/layoutNodes'
import type { Workflow } from '@/lib/api'

interface WorkflowDesignerModalProps {
  isOpen: boolean
  onClose: () => void
  onSuccess: () => void
  onDesigningStateChange?: (isDesigning: boolean) => void
  projectPath?: string | null
}

export const WorkflowDesignerModal: React.FC<WorkflowDesignerModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
  onDesigningStateChange,
  projectPath,
}) => {
  // 단계: 'input' | 'generating' | 'preview'
  const [step, setStep] = useState<'input' | 'generating' | 'preview'>('input')

  // 모드: 'create' | 'improve'
  const [mode, setMode] = useState<'create' | 'improve'>('create')

  // 입력 필드
  const [requirements, setRequirements] = useState('')

  // 생성된 출력
  const [generatedOutput, setGeneratedOutput] = useState('')
  const [_outputChunks, setOutputChunks] = useState<string[]>([])

  // 파싱된 워크플로우
  const [parsedWorkflow, setParsedWorkflow] = useState<Workflow | null>(null)
  const [parseError, setParseError] = useState<string | null>(null)

  // 에러 및 로딩
  const [error, setError] = useState<string | null>(null)
  const [abortController, setAbortController] = useState<AbortController | null>(null)

  // 스크롤 참조 및 자동 스크롤
  const outputContainerRef = useRef<HTMLDivElement>(null)
  const [autoScroll, setAutoScroll] = useState(true)

  // 세션 ID
  const [sessionId, setSessionId] = useState<string | null>(null)

  // localStorage 키
  const STORAGE_KEY = 'workflow_design_session'

  // Workflow Store
  const loadWorkflow = useWorkflowStore((state) => state.loadWorkflow)
  const currentWorkflow = useWorkflowStore((state) => ({
    name: state.workflowName,
    nodes: state.nodes,
    edges: state.edges,
  }))

  // step 변경 시 generating 상태 알림
  useEffect(() => {
    if (onDesigningStateChange) {
      const isDesigning = step === 'generating' || step === 'preview'
      onDesigningStateChange(isDesigning)
    }
  }, [step, onDesigningStateChange])

  // 세션 저장
  const saveSession = (session: any) => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(session))
  }

  // 세션 로드
  const loadSession = () => {
    const stored = localStorage.getItem(STORAGE_KEY)
    return stored ? JSON.parse(stored) : null
  }

  // 세션 제거
  const clearSession = () => {
    localStorage.removeItem(STORAGE_KEY)
  }

  // 모달이 열릴 때 진행 중인 세션 확인 및 재접속
  useEffect(() => {
    if (!isOpen) {
      return
    }

    // 이미 재접속 중이면 중복 실행 방지
    if (step === 'generating' || step === 'preview') {
      console.log('⏭️ 이미 실행 중이므로 세션 복구 스킵:', step)
      return
    }

    const session = loadSession()
    if (!session || session.status !== 'generating') {
      console.log('ℹ️ 복구할 세션 없음')
      return
    }

    console.log('🔄 진행 중인 설계 세션 발견:', session)

    const sid = session.session_id
    const reqs = session.requirements || ''

    setSessionId(sid)
    setRequirements(reqs)
    setStep('generating')

    // 재접속 시작
    console.log('🔌 세션 재접속:', sid)
    const controller = new AbortController()
    setAbortController(controller)

    const reconnect = async () => {
      try {
        await designWorkflow(
          reqs,
          (chunk) => {
            setGeneratedOutput((prev) => prev + chunk)
            setOutputChunks((prev) => [...prev, chunk])
          },
          (finalOutput) => {
            console.log('워크플로우 설계 완료 (재접속)')
            setStep('preview')
            setAbortController(null)
            clearSession()
            extractWorkflowFromOutput(finalOutput)
          },
          (error) => {
            setError(error)
            setStep('input')
            setAbortController(null)
            clearSession()
          },
          controller.signal,
          sid,
          mode === 'improve' ? currentWorkflow : null,
          mode,
          projectPath
        )
      } catch (err) {
        const errorMsg = err instanceof Error ? err.message : String(err)
        setError(errorMsg)
        setStep('input')
        setAbortController(null)
        clearSession()
      }
    }

    reconnect()

    return () => {
      if (controller) {
        controller.abort()
      }
    }
  }, [isOpen])

  // 자동 스크롤
  useEffect(() => {
    if (autoScroll && outputContainerRef.current && step === 'generating') {
      outputContainerRef.current.scrollTop = outputContainerRef.current.scrollHeight
    }
  }, [generatedOutput, autoScroll, step])

  // 스크롤 이벤트 핸들러
  const handleScroll = () => {
    if (!outputContainerRef.current) return

    const { scrollTop, scrollHeight, clientHeight } = outputContainerRef.current
    const isAtBottom = scrollHeight - scrollTop - clientHeight < 50

    setAutoScroll(isAtBottom)
  }

  // 맨 아래로 스크롤
  const scrollToBottom = () => {
    if (outputContainerRef.current) {
      outputContainerRef.current.scrollTo({
        top: outputContainerRef.current.scrollHeight,
        behavior: 'smooth',
      })
      setAutoScroll(true)
    }
  }

  // 모달 닫기
  const handleClose = () => {
    if (step === 'input') {
      resetModal()
    }
    onClose()
  }

  // 설계 중단
  const handleAbort = () => {
    if (abortController) {
      abortController.abort()
    }
    setStep('input')
    setError('사용자가 작업을 중단했습니다')
    clearSession()
  }

  // 모달 리셋
  const resetModal = () => {
    setStep('input')
    setRequirements('')
    setGeneratedOutput('')
    setOutputChunks([])
    setParsedWorkflow(null)
    setParseError(null)
    setError(null)
    setAbortController(null)
    setSessionId(null)
    clearSession()
  }

  // 워크플로우 설계 시작
  const handleGenerate = async () => {
    if (!requirements.trim()) {
      setError('워크플로우 요구사항을 입력해주세요')
      return
    }

    setStep('generating')
    setGeneratedOutput('')
    setOutputChunks([])
    setParsedWorkflow(null)
    setParseError(null)
    setError(null)

    const newSessionId = sessionId || `wf-${Date.now()}`
    setSessionId(newSessionId)
    saveSession({
      session_id: newSessionId,
      status: 'generating',
      requirements,
    })

    const controller = new AbortController()
    setAbortController(controller)

    try {
      await designWorkflow(
        requirements,
        (chunk) => {
          setGeneratedOutput((prev) => prev + chunk)
          setOutputChunks((prev) => [...prev, chunk])
        },
        (finalOutput) => {
          console.log('워크플로우 설계 완료')
          setStep('preview')
          setAbortController(null)
          clearSession()
          extractWorkflowFromOutput(finalOutput)
        },
        (error) => {
          setError(error)
          setStep('input')
          setAbortController(null)
          clearSession()
        },
        controller.signal,
        newSessionId,
        mode === 'improve' ? currentWorkflow : null,
        mode,
        projectPath
      )
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : String(err)
      setError(errorMsg)
      setStep('input')
      setAbortController(null)
      clearSession()
    }
  }

  // 생성된 출력에서 워크플로우 JSON 추출
  const extractWorkflowFromOutput = (output: string) => {
    console.log('📥 extractWorkflowFromOutput 호출됨')
    console.log('📊 출력 길이:', output.length)
    console.log('📄 출력 미리보기 (앞 500자):', output.substring(0, 500))

    let jsonText = ''

    try {
      // 방법 1: "workflow" 필드를 찾고 그 근처의 { 부터 시작
      const workflowIdx = output.indexOf('"workflow"')
      if (workflowIdx !== -1) {
        console.log('🔍 "workflow" 필드 발견 (위치):', workflowIdx)
        // workflow 앞의 { 찾기 (최대 1000자 뒤로)
        let startIdx = -1
        for (let i = workflowIdx; i >= Math.max(0, workflowIdx - 1000); i--) {
          if (output[i] === '{') {
            startIdx = i
            break
          }
        }

        if (startIdx !== -1) {
          console.log('🔍 JSON 시작 위치 발견:', startIdx)
          // Balanced bracket matching
          let depth = 0
          let endIdx = -1
          let inString = false
          let escapeNext = false

          for (let i = startIdx; i < output.length; i++) {
            const char = output[i]

            if (escapeNext) {
              escapeNext = false
              continue
            }

            if (char === '\\') {
              escapeNext = true
              continue
            }

            if (char === '"') {
              inString = !inString
              continue
            }

            if (!inString) {
              if (char === '{') depth++
              if (char === '}') {
                depth--
                if (depth === 0) {
                  endIdx = i + 1
                  break
                }
              }
            }
          }

          if (endIdx !== -1) {
            jsonText = output.substring(startIdx, endIdx)
            console.log('✅ Balanced matching 성공 (길이):', jsonText.length)
          } else {
            console.warn('⚠️ Balanced matching 실패: JSON 끝을 찾지 못함')
          }
        } else {
          console.warn('⚠️ "workflow" 앞의 { 를 찾지 못함')
        }
      } else {
        console.warn('⚠️ "workflow" 필드를 찾지 못함')
      }

      // 방법 2: ```json ... ``` 블록에서 추출
      if (!jsonText) {
        console.log('🔄 방법 2: ```json ... ``` 블록 추출 시도')
        const jsonBlockRegex = /```json\s*\n([\s\S]+?)```/g
        let match
        const matches = []
        while ((match = jsonBlockRegex.exec(output)) !== null) {
          matches.push(match[1].trim())
        }

        if (matches.length > 0) {
          // 가장 긴 JSON 블록 선택 (가장 완전한 JSON일 가능성)
          jsonText = matches.reduce((a, b) => (a.length > b.length ? a : b))
          console.log(`✅ JSON 블록 추출 성공 (${matches.length}개 중 가장 긴 블록, 길이: ${jsonText.length})`)
        }
      }

      // 방법 3: { ... } 형태의 JSON 직접 추출
      if (!jsonText) {
        console.log('🔄 방법 3: { ... } 형태 JSON 직접 추출 시도')
        const firstBrace = output.indexOf('{')
        if (firstBrace !== -1) {
          let depth = 0
          let endIdx = -1
          let inString = false
          let escapeNext = false

          for (let i = firstBrace; i < output.length; i++) {
            const char = output[i]

            if (escapeNext) {
              escapeNext = false
              continue
            }

            if (char === '\\') {
              escapeNext = true
              continue
            }

            if (char === '"') {
              inString = !inString
              continue
            }

            if (!inString) {
              if (char === '{') depth++
              if (char === '}') {
                depth--
                if (depth === 0) {
                  endIdx = i + 1
                  break
                }
              }
            }
          }

          if (endIdx !== -1) {
            jsonText = output.substring(firstBrace, endIdx)
            console.log('✅ 직접 추출 성공 (길이):', jsonText.length)
          }
        }
      }

      if (!jsonText) {
        console.error('❌ 모든 추출 방법 실패')
        throw new Error('워크플로우 JSON을 찾을 수 없습니다')
      }

      console.log('📝 추출된 JSON 미리보기 (앞 500자):', jsonText.substring(0, 500))

      // JSON 파싱
      const parsed = JSON.parse(jsonText)
      console.log('✅ JSON 파싱 성공:', parsed)

      // workflow 필드 추출
      if (parsed.workflow) {
        setParsedWorkflow(parsed.workflow)
        setParseError(null)
        console.log('✅ 워크플로우 추출 성공:', parsed.workflow)
      } else {
        throw new Error('workflow 필드가 없습니다')
      }
    } catch (e) {
      console.error('⚠️ 워크플로우 파싱 실패:', e)
      const errorMsg = e instanceof Error ? e.message : String(e)
      setParseError(errorMsg)
      setParsedWorkflow(null)
    }
  }

  // 워크플로우 적용
  const handleApply = () => {
    if (!parsedWorkflow) {
      setError('워크플로우를 파싱할 수 없습니다')
      return
    }

    try {
      // 자동 레이아웃 적용 (가로 방향)
      const layoutedWorkflow = layoutWorkflow(
        {
          nodes: parsedWorkflow.nodes,
          edges: parsedWorkflow.edges,
        },
        'LR'
      )

      // 레이아웃이 적용된 워크플로우 로드
      const finalWorkflow: Workflow = {
        ...parsedWorkflow,
        nodes: layoutedWorkflow.nodes,
        edges: layoutedWorkflow.edges,
      }

      loadWorkflow(finalWorkflow)
      alert('워크플로우가 캔버스에 적용되었습니다 (자동 레이아웃 적용)')
      onSuccess()
      resetModal()
      onClose()
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : String(err)
      setError(errorMsg)
    }
  }

  return (
    <Dialog open={isOpen} onOpenChange={handleClose}>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Wand2 className="h-5 w-5 text-primary" />
            워크플로우 자동 설계
          </DialogTitle>
        </DialogHeader>

        {/* 단계: 입력 */}
        {step === 'input' && (
          <div className="space-y-4">
            {/* 모드 선택 */}
            <div className="flex gap-3">
              <button
                className={`flex-1 p-4 border-2 rounded-lg transition-colors ${
                  mode === 'create'
                    ? 'border-blue-500 bg-blue-50 text-blue-900'
                    : 'border-gray-300 hover:border-gray-400'
                }`}
                onClick={() => setMode('create')}
              >
                <div className="font-semibold text-sm mb-1">🆕 새로 만들기</div>
                <div className="text-xs text-muted-foreground">
                  무에서 유로 워크플로우 생성
                </div>
              </button>
              <button
                className={`flex-1 p-4 border-2 rounded-lg transition-colors ${
                  mode === 'improve'
                    ? 'border-blue-500 bg-blue-50 text-blue-900'
                    : currentWorkflow.nodes.length === 0
                    ? 'border-gray-200 bg-gray-50 cursor-not-allowed opacity-50'
                    : 'border-gray-300 hover:border-gray-400'
                }`}
                onClick={() => {
                  if (currentWorkflow.nodes.length > 0) {
                    setMode('improve')
                  }
                }}
                disabled={currentWorkflow.nodes.length === 0}
              >
                <div className="font-semibold text-sm mb-1">✨ 개선하기</div>
                <div className="text-xs text-muted-foreground">
                  {currentWorkflow.nodes.length > 0
                    ? '현재 워크플로우를 분석하고 개선'
                    : '워크플로우가 비어있습니다'}
                </div>
              </button>
            </div>

            {/* 개선 모드일 때 현재 워크플로우 표시 */}
            {mode === 'improve' && currentWorkflow.nodes.length > 0 && (
              <Alert>
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>
                  <div className="text-sm font-medium mb-1">현재 워크플로우</div>
                  <div className="text-xs text-muted-foreground">
                    {currentWorkflow.name || '이름 없음'} ({currentWorkflow.nodes.length}개 노드,{' '}
                    {currentWorkflow.edges.length}개 연결)
                  </div>
                </AlertDescription>
              </Alert>
            )}

            <div>
              <label htmlFor="requirements" className="text-sm font-medium">
                {mode === 'create' ? '원하는 워크플로우 설명' : '개선 요구사항'}
              </label>
              <Textarea
                id="requirements"
                value={requirements}
                onChange={(e) => setRequirements(e.target.value)}
                placeholder={
                  mode === 'create'
                    ? '예: 코드 작성 후 리뷰하고 테스트 실행하는 워크플로우를 만들어주세요'
                    : '예: 리뷰 단계에서 스타일, 보안, 아키텍처 리뷰를 병렬로 실행하도록 개선해주세요'
                }
                rows={6}
                className="mt-2"
              />
              <p className="text-sm text-muted-foreground mt-1">
                {mode === 'create'
                  ? 'AI가 요구사항을 분석하여 노드와 연결을 자동으로 설계합니다'
                  : 'AI가 현재 워크플로우를 분석하고 개선 사항을 제안합니다'}
              </p>
            </div>

            {error && (
              <Alert variant="destructive">
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}
          </div>
        )}

        {/* 단계: 생성 중 */}
        {step === 'generating' && (
          <div className="space-y-4">
            <Alert variant="info">
              <Loader2 className="h-4 w-4 animate-spin" />
              <AlertDescription>
                <div className="font-medium">워크플로우 설계 중...</div>
                <div className="text-xs mt-1">
                  AI가 요구사항을 분석하고 워크플로우를 설계하고 있습니다
                </div>
              </AlertDescription>
            </Alert>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <div className="text-xs font-medium">설계 로그</div>
                {!autoScroll && (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={scrollToBottom}
                    className="h-6 px-2 text-xs"
                  >
                    <ArrowDown className="h-3 w-3 mr-1" />
                    맨 아래로
                  </Button>
                )}
              </div>

              <div
                ref={outputContainerRef}
                onScroll={handleScroll}
                className="bg-slate-50 border rounded-lg p-4 max-h-96 overflow-y-auto scroll-smooth relative"
              >
                {!autoScroll && (
                  <div className="sticky top-0 z-10 flex justify-center mb-2">
                    <div className="bg-gray-800 text-white text-xs px-3 py-1.5 rounded-full shadow-lg">
                      자동 스크롤 일시 중지됨
                    </div>
                  </div>
                )}

                {generatedOutput.trim() ? (
                  <ParsedContent content={generatedOutput} />
                ) : (
                  <div className="text-gray-500 italic text-sm">
                    워크플로우 디자이너가 작업 중입니다...
                  </div>
                )}
              </div>
            </div>

            {error && (
              <Alert variant="destructive">
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>
                  <div className="font-medium mb-1">에러 발생</div>
                  <div>{error}</div>
                </AlertDescription>
              </Alert>
            )}
          </div>
        )}

        {/* 단계: 미리보기 */}
        {step === 'preview' && (
          <div className="space-y-4">
            <Alert variant="success">
              <Check className="h-4 w-4" />
              <AlertDescription>
                <span className="font-medium">워크플로우 설계 완료</span>
              </AlertDescription>
            </Alert>

            {parsedWorkflow ? (
              <div>
                <div className="text-sm font-medium mb-2">설계된 워크플로우</div>
                <div className="bg-slate-50 border rounded-lg p-4 max-h-96 overflow-y-auto">
                  <div className="space-y-2">
                    <div>
                      <span className="text-xs font-semibold text-gray-700">이름:</span>
                      <span className="text-sm ml-2">{parsedWorkflow.name}</span>
                    </div>
                    {parsedWorkflow.description && (
                      <div>
                        <span className="text-xs font-semibold text-gray-700">설명:</span>
                        <span className="text-sm ml-2">{parsedWorkflow.description}</span>
                      </div>
                    )}
                    <div>
                      <span className="text-xs font-semibold text-gray-700">노드 수:</span>
                      <span className="text-sm ml-2">{parsedWorkflow.nodes.length}개</span>
                    </div>
                    <div>
                      <span className="text-xs font-semibold text-gray-700">연결 수:</span>
                      <span className="text-sm ml-2">{parsedWorkflow.edges.length}개</span>
                    </div>
                  </div>

                  <div className="mt-4">
                    <div className="text-xs font-semibold text-gray-700 mb-2">노드 상세:</div>
                    <div className="space-y-2">
                      {parsedWorkflow.nodes.map((node) => {
                        const typeColors: Record<string, string> = {
                          input: 'bg-blue-50 border-blue-300',
                          worker: 'bg-green-50 border-green-300',
                          manager: 'bg-purple-50 border-purple-300',
                          condition: 'bg-yellow-50 border-yellow-300',
                          loop: 'bg-orange-50 border-orange-300',
                          merge: 'bg-pink-50 border-pink-300',
                        }
                        const typeIcons: Record<string, string> = {
                          input: '📥',
                          worker: '⚙️',
                          manager: '👥',
                          condition: '🔀',
                          loop: '🔁',
                          merge: '🔗',
                        }
                        const bgColor = typeColors[node.type] || 'bg-white border-gray-300'
                        const icon = typeIcons[node.type] || '📦'

                        return (
                          <div key={node.id} className={`text-xs p-3 rounded border ${bgColor}`}>
                            <div className="font-semibold flex items-center gap-2 mb-1">
                              <span>{icon}</span>
                              <span>{node.id}</span>
                              <span className="text-gray-600 font-normal">({node.type})</span>
                            </div>
                            {node.data && (
                              <div className="ml-6 mt-1 space-y-1 text-gray-700">
                                {node.data.agent_name && (
                                  <div>• Agent: <span className="font-medium">{node.data.agent_name}</span></div>
                                )}
                                {node.data.task_template && (
                                  <div>• Task: <span className="italic">{node.data.task_template.substring(0, 80)}{node.data.task_template.length > 80 ? '...' : ''}</span></div>
                                )}
                                {node.data.task_description && (
                                  <div>• Task: <span className="italic">{node.data.task_description.substring(0, 80)}{node.data.task_description.length > 80 ? '...' : ''}</span></div>
                                )}
                                {node.data.available_workers && (
                                  <div>• Workers: <span className="font-medium">{node.data.available_workers.join(', ')}</span></div>
                                )}
                                {node.data.condition_type && (
                                  <div>• Condition: <span className="font-medium">{node.data.condition_type} "{node.data.condition_value}"</span></div>
                                )}
                                {node.data.max_iterations && (
                                  <div>• Max Iterations: <span className="font-medium">{node.data.max_iterations}</span></div>
                                )}
                                {node.data.merge_strategy && (
                                  <div>• Strategy: <span className="font-medium">{node.data.merge_strategy}</span></div>
                                )}
                              </div>
                            )}
                          </div>
                        )
                      })}
                    </div>
                  </div>

                  <div className="mt-4">
                    <div className="text-xs font-semibold text-gray-700 mb-2">연결 관계:</div>
                    <div className="space-y-1">
                      {parsedWorkflow.edges.map((edge) => (
                        <div key={edge.id} className="text-xs bg-white p-2 rounded border flex items-center gap-2">
                          <span className="font-medium text-blue-600">{edge.source}</span>
                          <span className="text-gray-400">→</span>
                          <span className="font-medium text-green-600">{edge.target}</span>
                          {edge.sourceHandle && (
                            <span className="text-gray-500 text-[10px] ml-auto">({edge.sourceHandle})</span>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                <div className="mt-3 text-sm text-muted-foreground">
                  ✅ 확인 버튼을 누르면 워크플로우가 캔버스에 적용됩니다
                </div>
              </div>
            ) : (
              <Alert variant="warning">
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>
                  <div className="font-medium mb-1">파싱 실패</div>
                  <div className="text-sm">{parseError}</div>
                  <div className="mt-2 text-xs">
                    전체 출력을 확인하여 수동으로 JSON을 추출해주세요
                  </div>
                </AlertDescription>
              </Alert>
            )}

            {error && (
              <Alert variant="destructive">
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}
          </div>
        )}

        <DialogFooter>
          {step === 'input' && (
            <>
              <Button variant="outline" onClick={handleClose}>
                <X className="mr-2 h-4 w-4" />
                취소
              </Button>
              <Button onClick={handleGenerate} disabled={!requirements.trim()}>
                <Send className="mr-2 h-4 w-4" />
                설계 시작
              </Button>
            </>
          )}

          {step === 'generating' && (
            <>
              <Button variant="outline" onClick={handleClose}>
                백그라운드 실행
              </Button>
              <Button variant="destructive" onClick={handleAbort}>
                <X className="mr-2 h-4 w-4" />
                중단
              </Button>
            </>
          )}

          {step === 'preview' && (
            <>
              <Button variant="outline" onClick={() => setStep('input')}>
                다시 설계
              </Button>
              <Button variant="outline" onClick={handleClose}>
                <X className="mr-2 h-4 w-4" />
                취소
              </Button>
              <Button onClick={handleApply} disabled={!parsedWorkflow}>
                <Check className="mr-2 h-4 w-4" />
                확인 (캔버스에 적용)
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
