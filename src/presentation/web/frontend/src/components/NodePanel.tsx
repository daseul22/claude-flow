/**
 * 노드 패널 컴포넌트
 *
 * Agent 목록을 표시하고, 드래그 앤 드롭으로 캔버스에 추가합니다.
 */

import React, { useEffect, useState, useRef } from 'react'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Agent, getAgents, getCustomWorkers, getCurrentProject, CustomWorkerInfo, loadDisplayConfig, saveDisplayConfig } from '@/lib/api'
import { useWorkflowStore } from '@/stores/workflowStore'
import { WorkflowNode } from '@/lib/api'
import { Plus, Target, Zap, ChevronDown, ChevronUp, GitBranch, Merge, Wand2, Loader2 } from 'lucide-react'
import { CustomWorkerCreateModal } from './CustomWorkerCreateModal'
import { WorkflowDesignerModal } from './WorkflowDesignerModal'

export const NodePanel: React.FC = () => {
  const [agents, setAgents] = useState<Agent[]>([])
  const [customWorkers, setCustomWorkers] = useState<CustomWorkerInfo[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set(['input', 'advanced', 'general', 'specialized', 'custom']))
  const [isCustomWorkerModalOpen, setIsCustomWorkerModalOpen] = useState(false)
  const [isWorkflowDesignerModalOpen, setIsWorkflowDesignerModalOpen] = useState(false)
  const [projectPath, setProjectPath] = useState<string | null>(null)
  const [isWorkerGenerating, setIsWorkerGenerating] = useState(false)
  const [isWorkflowDesigning, setIsWorkflowDesigning] = useState(false)

  const { addNode, nodes } = useWorkflowStore()

  // 초기 로드 완료 플래그 (무한 루프 방지)
  const initialLoadDone = useRef(false)

  // 새로고침 시 진행 중인 세션 확인
  useEffect(() => {
    console.log('🚀 NodePanel 마운트: 세션 복구 확인 시작')

    // 커스텀 워커 세션 확인
    const workerSession = localStorage.getItem('custom_worker_session')
    console.log('📦 workerSession:', workerSession)
    if (workerSession) {
      const parsedSession = JSON.parse(workerSession)
      if (parsedSession.status === 'generating') {
        console.log('🔄 NodePanel: 진행 중인 워커 생성 세션 발견')
        setIsWorkerGenerating(true)
        setIsCustomWorkerModalOpen(true)  // 자동으로 모달 열기
      }
    }

    // 워크플로우 설계 세션 확인
    const designSession = localStorage.getItem('workflow_design_session')
    console.log('📦 designSession:', designSession)
    if (designSession) {
      try {
        const parsedSession = JSON.parse(designSession)
        console.log('📝 parsedSession:', parsedSession)
        if (parsedSession.status === 'generating') {
          console.log('🔄 NodePanel: 진행 중인 워크플로우 설계 세션 발견 → 모달 열기')
          setIsWorkflowDesigning(true)
          setIsWorkflowDesignerModalOpen(true)  // 자동으로 모달 열기
        } else {
          console.log('ℹ️ 세션 상태가 generating이 아님:', parsedSession.status)
        }
      } catch (err) {
        console.error('❌ 세션 파싱 실패:', err)
      }
    } else {
      console.log('ℹ️ 워크플로우 설계 세션 없음')
    }
  }, [])

  // 주기적으로 localStorage 체크 (백그라운드 실행 중 세션 상태 동기화)
  useEffect(() => {
    const interval = setInterval(() => {
      // 워크플로우 설계 세션 상태 체크
      const designSession = localStorage.getItem('workflow_design_session')
      if (designSession) {
        const parsedSession = JSON.parse(designSession)
        setIsWorkflowDesigning(parsedSession.status === 'generating')
      } else {
        setIsWorkflowDesigning(false)
      }
    }, 1000) // 1초마다 체크

    return () => clearInterval(interval)
  }, [])

  // 섹션 토글 함수
  const toggleSection = (section: string) => {
    setExpandedSections((prev) => {
      const next = new Set(prev)
      if (next.has(section)) {
        next.delete(section)
      } else {
        next.add(section)
      }
      return next
    })
  }

  // 역할별 템플릿 생성 함수
  const getTemplateByRole = (agentName: string, agentRole: string): string => {
    // Planner 그룹
    const planners = ['feature_planner', 'refactoring_planner', 'bug_fix_planner', 'api_planner', 'database_planner', 'product_manager', 'ideator']
    if (planners.includes(agentName)) {
      return `아래의 요구사항에 대한 ${agentRole} 계획을 수립해주세요.

---
{{parent}}
---`
    }

    // Coder 그룹
    const coders = ['frontend_coder', 'backend_coder', 'test_coder', 'infrastructure_coder', 'database_coder']
    if (coders.includes(agentName)) {
      return `아래의 지침대로 ${agentRole}을 수행해주세요.

---
{{parent}}
---`
    }

    // Reviewer 그룹
    const reviewers = ['style_reviewer', 'security_reviewer', 'architecture_reviewer']
    if (reviewers.includes(agentName)) {
      return `아래의 코드/내용을 ${agentRole} 관점에서 리뷰해주세요.

---
{{parent}}
---`
    }

    // Tester 그룹
    const testers = ['unit_tester', 'integration_tester', 'e2e_tester', 'performance_tester']
    if (testers.includes(agentName)) {
      return `아래의 지침대로 ${agentRole}을 수행해주세요.

---
{{parent}}
---`
    }

    // Summarizer 그룹
    if (agentName === 'summarizer') {
      return `아래 내용을 요약해주세요.

---
{{parent}}
---`
    }

    if (agentName === 'log_analyzer') {
      return `아래 로그를 분석해주세요.

---
{{parent}}
---`
    }

    // Bug Fixer
    if (agentName === 'bug_fixer') {
      return `아래의 지침대로 버그를 수정해주세요.

---
{{parent}}
---`
    }

    // Committer
    if (agentName === 'committer') {
      return `아래의 변경사항을 커밋해주세요.

---
{{parent}}
---`
    }

    // Documenter
    if (agentName === 'documenter') {
      return `아래의 지침대로 문서를 작성해주세요.

---
{{parent}}
---`
    }

    // Worker Prompt Engineer
    if (agentName === 'worker_prompt_engineer') {
      return `아래의 요구사항에 맞는 커스텀 워커 프롬프트를 생성해주세요.

---
{{parent}}
---`
    }

    // Workflow Designer
    if (agentName === 'workflow_designer') {
      return `아래의 요구사항에 맞는 워크플로우를 설계해주세요.

---
{{parent}}
---`
    }

    // 기본 템플릿 (커스텀 워커 등)
    return `아래의 지침대로 ${agentRole}을 수행해주세요.

---
{{parent}}
---`
  }

  // expanded_sections 변경 시 자동 저장 (debounce)
  useEffect(() => {
    // 프로젝트 선택되지 않았거나 초기 로드 중이면 스킵
    if (!projectPath || !initialLoadDone.current) {
      return
    }

    const timer = setTimeout(async () => {
      try {
        // 기존 설정 로드 (사이드바 상태 보존)
        const existingConfig = await loadDisplayConfig()

        const displayConfig = {
          left_sidebar_open: existingConfig.left_sidebar_open, // 기존 값 유지
          right_sidebar_open: existingConfig.right_sidebar_open, // 기존 값 유지
          expanded_sections: Array.from(expandedSections),
        }

        console.log('💾 NodePanel expanded_sections 자동 저장 중...', displayConfig.expanded_sections)

        await saveDisplayConfig(displayConfig)
        console.log('✅ NodePanel expanded_sections 저장 완료')
      } catch (err) {
        console.error('❌ NodePanel expanded_sections 저장 실패:', err)
      }
    }, 500) // 0.5초 debounce

    return () => clearTimeout(timer)
  }, [expandedSections, projectPath])

  // 제외 워커 (UI에 표시하지 않음)
  const excludedWorkers = ['worker_prompt_engineer', 'workflow_designer']

  // 워커 자동 분류 (하드코딩 제거)
  const filteredAgents = agents.filter((agent) => !excludedWorkers.includes(agent.name))

  // 범용 워커: _planner, _coder, _tester, _reviewer 등의 접미사가 없는 워커
  const generalWorkers = filteredAgents.filter((agent) => {
    const name = agent.name
    return !name.includes('_planner') &&
           !name.includes('_coder') &&
           !name.includes('_tester') &&
           !name.includes('_reviewer') &&
           !name.includes('_documenter') &&
           !name.includes('_manager') &&
           !name.includes('_creator') &&
           !name.includes('_writer') &&
           !name.includes('_handler') &&
           !name.includes('_migrator') &&
           !name.includes('_migration')
  })

  // 특화 워커: _planner, _coder 등의 접미사가 있는 워커
  const specializedWorkers = filteredAgents.filter((agent) => {
    const name = agent.name
    return name.includes('_planner') ||
           name.includes('_coder') ||
           name.includes('_tester') ||
           name.includes('_reviewer') ||
           name.includes('_documenter') ||
           name.includes('_manager') ||
           name.includes('_creator') ||
           name.includes('_writer') ||
           name.includes('_handler') ||
           name.includes('_migrator') ||
           name.includes('_migration')
  })

  // 레거시 호환을 위한 별칭
  const filteredGeneralWorkers = generalWorkers
  const filteredSpecializedWorkers = specializedWorkers

  // 프로젝트 경로 및 Agent 목록 로드
  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true)

        // 프로젝트 경로 로드
        const project = await getCurrentProject()
        setProjectPath(project.project_path)

        // 기본 Agent 로드
        const agentData = await getAgents()
        setAgents(agentData)

        // 커스텀 워커 로드 (프로젝트 선택된 경우만)
        if (project.project_path) {
          try {
            const customData = await getCustomWorkers(project.project_path)
            setCustomWorkers(customData)
          } catch (err) {
            console.warn('커스텀 워커 로드 실패 (무시):', err)
          }

          // Display 설정 로드 (expanded_sections)
          try {
            const displayConfig = await loadDisplayConfig()
            if (displayConfig.expanded_sections && displayConfig.expanded_sections.length > 0) {
              setExpandedSections(new Set(displayConfig.expanded_sections))
              console.log('✅ NodePanel expanded_sections 로드:', displayConfig.expanded_sections)
            }
          } catch (err) {
            console.warn('NodePanel display 설정 로드 실패 (기본값 사용):', err)
          }
        }

        initialLoadDone.current = true
      } catch (err) {
        const errorMsg = err instanceof Error ? err.message : String(err)
        setError(errorMsg)
      } finally {
        setLoading(false)
      }
    }

    loadData()
  }, [])

  // 드래그 시작 핸들러
  const onDragStart = (event: React.DragEvent, nodeType: string, nodeData: any) => {
    event.dataTransfer.setData('application/reactflow', JSON.stringify({ type: nodeType, data: nodeData }))
    event.dataTransfer.effectAllowed = 'move'
  }

  // Agent를 캔버스에 추가 (클릭)
  const handleAddAgent = (agent: Agent) => {
    // 노드 위치 계산 (기존 노드 개수에 따라 오프셋)
    const x = 100 + (nodes.length % 3) * 300
    const y = 100 + Math.floor(nodes.length / 3) * 150

    const newNode: WorkflowNode = {
      id: `node-${Date.now()}`,
      type: 'worker',
      position: { x, y },
      data: {
        agent_name: agent.name,
        task_template: getTemplateByRole(agent.name, agent.role),
      },
    }

    addNode(newNode)
  }

  // Input 노드를 캔버스에 추가
  const handleAddInput = () => {
    // 노드 위치 계산
    const x = 100 + (nodes.length % 3) * 300
    const y = 100 + Math.floor(nodes.length / 3) * 150

    const newNode: WorkflowNode = {
      id: `input-${Date.now()}`,
      type: 'input',
      position: { x, y },
      data: {
        initial_input: '',
      },
    }

    addNode(newNode)
  }

  // Condition 노드를 캔버스에 추가
  const handleAddCondition = () => {
    const x = 100 + (nodes.length % 3) * 300
    const y = 100 + Math.floor(nodes.length / 3) * 150

    const newNode: WorkflowNode = {
      id: `condition-${Date.now()}`,
      type: 'condition',
      position: { x, y },
      data: {
        condition_type: 'contains',
        condition_value: 'success',
      },
    }

    addNode(newNode)
  }

  // Merge 노드를 캔버스에 추가
  const handleAddMerge = () => {
    const x = 100 + (nodes.length % 3) * 300
    const y = 100 + Math.floor(nodes.length / 3) * 150

    const newNode: WorkflowNode = {
      id: `merge-${Date.now()}`,
      type: 'merge',
      position: { x, y },
      data: {
        merge_strategy: 'concatenate',
        separator: '\n\n---\n\n',
      },
    }

    addNode(newNode)
  }

  // 커스텀 워커를 Agent로 변환
  const customWorkerToAgent = (worker: CustomWorkerInfo): Agent => {
    return {
      name: worker.name,
      role: worker.role,
      description: `${worker.role} (커스텀 워커)`,
      system_prompt: worker.prompt_preview,
      allowed_tools: worker.allowed_tools,
      model: worker.model,
      thinking: worker.thinking,
    }
  }

  // 커스텀 워커 생성 성공 핸들러
  const handleCustomWorkerCreated = async () => {
    // 커스텀 워커 재로드
    if (projectPath) {
      try {
        const customData = await getCustomWorkers(projectPath)
        setCustomWorkers(customData)

        // Agent 목록도 재로드 (백엔드에서 병합된 목록 가져오기)
        const agentData = await getAgents()
        setAgents(agentData)
      } catch (err) {
        console.error('커스텀 워커 재로드 실패:', err)
      }
    }
  }

  if (loading) {
    return (
      <Card className="h-full">
        <CardContent className="pt-6">
          <div className="text-sm text-muted-foreground">로딩 중...</div>
        </CardContent>
      </Card>
    )
  }

  if (error) {
    return (
      <Card className="h-full">
        <CardContent className="pt-6">
          <div className="text-sm text-red-500">에러: {error}</div>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card className="h-full overflow-hidden flex flex-col border-0 shadow-none">
      <CardContent className="flex-1 overflow-y-auto space-y-3 pt-6">
        {/* 워크플로우 자동 설계 버튼 */}
        <div className="border-2 border-dashed border-blue-300 rounded-lg p-3 bg-blue-50/50">
          <Button
            variant="default"
            className="w-full bg-blue-600 hover:bg-blue-700 text-white"
            onClick={() => setIsWorkflowDesignerModalOpen(true)}
          >
            {isWorkflowDesigning ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                워크플로우 설계 중... (클릭하여 확인)
              </>
            ) : (
              <>
                <Wand2 className="mr-2 h-4 w-4" />
                워크플로우 자동 설계
              </>
            )}
          </Button>
          <p className="text-xs text-blue-700 mt-2 text-center">
            AI가 요구사항을 분석하여 워크플로우를 자동으로 설계합니다
          </p>
        </div>

        {/* Input 노드 섹션 */}
        <div className="border rounded-lg overflow-hidden bg-emerald-50/50">
          <button
            onClick={() => toggleSection('input')}
            className="w-full flex items-center justify-between p-3 hover:bg-emerald-100/50 transition-colors"
          >
            <div className="flex items-center gap-2">
              <Zap className="h-4 w-4 text-emerald-600" />
              <span className="font-semibold text-sm text-emerald-700">Input 노드</span>
              <span className="text-xs px-2 py-0.5 bg-emerald-200 text-emerald-700 rounded-full">1</span>
            </div>
            {expandedSections.has('input') ? (
              <ChevronUp className="h-4 w-4 text-emerald-600" />
            ) : (
              <ChevronDown className="h-4 w-4 text-emerald-600" />
            )}
          </button>
          {expandedSections.has('input') && (
            <div className="p-3 pt-0 space-y-2">
              <Button
                variant="outline"
                className="w-full justify-start text-left border-emerald-300 hover:bg-emerald-50 bg-white cursor-grab active:cursor-grabbing"
                onClick={handleAddInput}
                draggable
                onDragStart={(e) => onDragStart(e, 'input', { initial_input: '' })}
              >
                <Zap className="mr-2 h-4 w-4 text-emerald-600" />
                <div className="flex flex-col items-start">
                  <span className="font-medium text-emerald-700">Input</span>
                  <span className="text-xs text-muted-foreground">
                    워크플로우 시작점
                  </span>
                </div>
              </Button>
            </div>
          )}
        </div>

        {/* 고급 노드 섹션 (Condition, Loop, Merge) */}
        <div className="border rounded-lg overflow-hidden bg-blue-50/50">
          <button
            onClick={() => toggleSection('advanced')}
            className="w-full flex items-center justify-between p-3 hover:bg-blue-100/50 transition-colors"
          >
            <div className="flex items-center gap-2">
              <GitBranch className="h-4 w-4 text-blue-600" />
              <span className="font-semibold text-sm text-blue-700">고급 노드</span>
              <span className="text-xs px-2 py-0.5 bg-blue-200 text-blue-700 rounded-full">3</span>
            </div>
            {expandedSections.has('advanced') ? (
              <ChevronUp className="h-4 w-4 text-blue-600" />
            ) : (
              <ChevronDown className="h-4 w-4 text-blue-600" />
            )}
          </button>
          {expandedSections.has('advanced') && (
            <div className="p-3 pt-0 space-y-2">
              {/* Condition 노드 */}
              <Button
                variant="outline"
                className="w-full justify-start text-left border-amber-300 hover:bg-amber-50 bg-white cursor-grab active:cursor-grabbing"
                onClick={handleAddCondition}
                draggable
                onDragStart={(e) => onDragStart(e, 'condition', { condition_type: 'contains', condition_value: 'success' })}
              >
                <GitBranch className="mr-2 h-4 w-4 text-amber-600" />
                <div className="flex flex-col items-start">
                  <span className="font-medium text-amber-700">조건 분기</span>
                  <span className="text-xs text-muted-foreground">
                    조건에 따라 True/False 분기
                  </span>
                </div>
              </Button>

              {/* Merge 노드 */}
              <Button
                variant="outline"
                className="w-full justify-start text-left border-sky-300 hover:bg-sky-50 bg-white cursor-grab active:cursor-grabbing"
                onClick={handleAddMerge}
                draggable
                onDragStart={(e) => onDragStart(e, 'merge', { merge_strategy: 'concatenate', separator: '\n\n---\n\n' })}
              >
                <Merge className="mr-2 h-4 w-4 text-sky-600" />
                <div className="flex flex-col items-start">
                  <span className="font-medium text-sky-700">병합</span>
                  <span className="text-xs text-muted-foreground">
                    여러 분기 결과를 통합
                  </span>
                </div>
              </Button>
            </div>
          )}
        </div>

        {/* 범용 Worker 노드 섹션 */}
        <div className="border rounded-lg overflow-hidden bg-slate-50/50">
          <button
            onClick={() => toggleSection('general')}
            className="w-full flex items-center justify-between p-3 hover:bg-slate-100 transition-colors"
          >
            <div className="flex items-center gap-2">
              <Plus className="h-4 w-4 text-slate-600" />
              <span className="font-semibold text-sm text-slate-700">범용 워커</span>
              <span className="text-xs px-2 py-0.5 bg-slate-200 text-slate-700 rounded-full">
                {filteredGeneralWorkers.length}
              </span>
            </div>
            {expandedSections.has('general') ? (
              <ChevronUp className="h-4 w-4 text-slate-600" />
            ) : (
              <ChevronDown className="h-4 w-4 text-slate-600" />
            )}
          </button>
          {expandedSections.has('general') && (
            <div className="p-3 pt-0 space-y-2">
              {filteredGeneralWorkers.length === 0 ? (
                <div className="text-sm text-muted-foreground text-center py-4">
                  검색 결과가 없습니다
                </div>
              ) : (
                filteredGeneralWorkers.map((agent) => (
                  <Button
                    key={agent.name}
                    variant="outline"
                    className="w-full justify-start text-left hover:bg-slate-50 bg-white cursor-grab active:cursor-grabbing"
                    onClick={() => handleAddAgent(agent)}
                    draggable
                    onDragStart={(e) => onDragStart(e, 'worker', { agent_name: agent.name, task_template: getTemplateByRole(agent.name, agent.role) })}
                  >
                    <Plus className="mr-2 h-4 w-4" />
                    <div className="flex flex-col items-start flex-1">
                      <span className="font-medium">{agent.name}</span>
                      <span className="text-xs text-muted-foreground line-clamp-2">
                        {agent.role}
                      </span>
                    </div>
                  </Button>
                ))
              )}
            </div>
          )}
        </div>

        {/* 특화 Worker 노드 섹션 */}
        <div className="border rounded-lg overflow-hidden bg-orange-50/50">
          <button
            onClick={() => toggleSection('specialized')}
            className="w-full flex items-center justify-between p-3 hover:bg-orange-100/50 transition-colors"
          >
            <div className="flex items-center gap-2">
              <Target className="h-4 w-4 text-orange-600" />
              <span className="font-semibold text-sm text-orange-700">특화 워커</span>
              <span className="text-xs px-2 py-0.5 bg-orange-200 text-orange-700 rounded-full">
                {filteredSpecializedWorkers.length}
              </span>
            </div>
            {expandedSections.has('specialized') ? (
              <ChevronUp className="h-4 w-4 text-orange-600" />
            ) : (
              <ChevronDown className="h-4 w-4 text-orange-600" />
            )}
          </button>
          {expandedSections.has('specialized') && (
            <div className="p-3 pt-0 space-y-2">
              {filteredSpecializedWorkers.length === 0 ? (
                <div className="text-sm text-muted-foreground text-center py-4">
                  검색 결과가 없습니다
                </div>
              ) : (
                filteredSpecializedWorkers.map((agent) => (
                  <Button
                    key={agent.name}
                    variant="outline"
                    className="w-full justify-start text-left hover:bg-orange-50 bg-white cursor-grab active:cursor-grabbing"
                    onClick={() => handleAddAgent(agent)}
                    draggable
                    onDragStart={(e) => onDragStart(e, 'worker', { agent_name: agent.name, task_template: getTemplateByRole(agent.name, agent.role) })}
                  >
                    <Target className="mr-2 h-4 w-4 text-orange-600" />
                    <div className="flex flex-col items-start flex-1">
                      <span className="font-medium">{agent.name}</span>
                      <span className="text-xs text-muted-foreground line-clamp-2">
                        {agent.role}
                      </span>
                    </div>
                  </Button>
                ))
              )}
            </div>
          )}
        </div>

        {/* 커스텀 워커 섹션 */}
        <div className="border rounded-lg overflow-hidden bg-indigo-50/50">
          <button
            onClick={() => toggleSection('custom')}
            className="w-full flex items-center justify-between p-3 hover:bg-indigo-100/50 transition-colors"
          >
            <div className="flex items-center gap-2">
              <Wand2 className="h-4 w-4 text-indigo-600" />
              <span className="font-semibold text-sm text-indigo-700">커스텀 워커</span>
              <span className="text-xs px-2 py-0.5 bg-indigo-200 text-indigo-700 rounded-full">
                {customWorkers.length}
              </span>
            </div>
            {expandedSections.has('custom') ? (
              <ChevronUp className="h-4 w-4 text-indigo-600" />
            ) : (
              <ChevronDown className="h-4 w-4 text-indigo-600" />
            )}
          </button>
          {expandedSections.has('custom') && (
            <div className="p-3 pt-0 space-y-2">
              {/* 워커 생성 중 상태 (모달 닫혔을 때) */}
              {isWorkerGenerating && !isCustomWorkerModalOpen && (
                <Button
                  variant="outline"
                  className="w-full justify-start text-left border-amber-300 bg-amber-50 hover:bg-amber-100 animate-pulse"
                  onClick={() => setIsCustomWorkerModalOpen(true)}
                >
                  <Loader2 className="mr-2 h-4 w-4 text-amber-600 animate-spin" />
                  <div className="flex flex-col items-start">
                    <span className="font-medium text-amber-700">워커 생성 중...</span>
                    <span className="text-xs text-amber-600">
                      클릭하여 진행 상황 확인
                    </span>
                  </div>
                </Button>
              )}

              {/* 새 워커 생성 버튼 (생성 중이 아닐 때) */}
              {!isWorkerGenerating && (
                <Button
                  variant="outline"
                  className="w-full justify-start text-left border-indigo-300 hover:bg-indigo-50 bg-white"
                  onClick={() => setIsCustomWorkerModalOpen(true)}
                  disabled={!projectPath}
                >
                  <Wand2 className="mr-2 h-4 w-4 text-indigo-600" />
                  <div className="flex flex-col items-start">
                    <span className="font-medium text-indigo-700">새 워커 생성</span>
                    <span className="text-xs text-muted-foreground">
                      AI가 도와주는 커스텀 워커 제작
                    </span>
                  </div>
                </Button>
              )}

              {!projectPath && (
                <p className="text-xs text-amber-600 mt-2 px-2">
                  ⚠️ 커스텀 워커를 사용하려면 먼저 프로젝트를 선택하세요
                </p>
              )}

              {/* 커스텀 워커 목록 */}
              {customWorkers.length === 0 ? (
                <div className="text-sm text-muted-foreground text-center py-4">
                  생성된 커스텀 워커가 없습니다
                </div>
              ) : (
                customWorkers.map((worker) => {
                  const agent = customWorkerToAgent(worker)
                  return (
                    <Button
                      key={worker.name}
                      variant="outline"
                      className="w-full justify-start text-left hover:bg-indigo-50 bg-white cursor-grab active:cursor-grabbing"
                      onClick={() => handleAddAgent(agent)}
                      draggable
                      onDragStart={(e) => onDragStart(e, 'worker', { agent_name: worker.name, task_template: getTemplateByRole(worker.name, worker.role) })}
                    >
                      <Wand2 className="mr-2 h-4 w-4 text-indigo-600" />
                      <div className="flex flex-col items-start flex-1">
                        <span className="font-medium">{worker.name}</span>
                        <span className="text-xs text-muted-foreground line-clamp-2">
                          {worker.role}
                        </span>
                      </div>
                    </Button>
                  )
                })
              )}
            </div>
          )}
        </div>
      </CardContent>

      {/* 커스텀 워커 생성 모달 */}
      <CustomWorkerCreateModal
        isOpen={isCustomWorkerModalOpen}
        onClose={() => setIsCustomWorkerModalOpen(false)}
        onSuccess={handleCustomWorkerCreated}
        onGeneratingStateChange={setIsWorkerGenerating}
      />

      {/* 워크플로우 자동 설계 모달 */}
      <WorkflowDesignerModal
        isOpen={isWorkflowDesignerModalOpen}
        onClose={() => setIsWorkflowDesignerModalOpen(false)}
        onSuccess={() => {
          // 워크플로우 적용 완료
          console.log('워크플로우가 캔버스에 적용되었습니다')
        }}
        onDesigningStateChange={setIsWorkflowDesigning}
      />
    </Card>
  )
}
