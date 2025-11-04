/**
 * Worker 노드 설정 컴포넌트
 *
 * 특정 작업을 수행하는 Worker 노드의 설정을 관리합니다.
 */

import React, { useState, useEffect, useRef } from 'react'
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { Badge } from '@/components/ui/badge'
import { useWorkflowStore } from '@/stores/workflowStore'
import { Search, ChevronDown } from 'lucide-react'
import { cn } from '@/lib/utils'
import { WorkflowNode, getAgents, Agent, getTools, Tool } from '@/lib/api'
import { useNodeConfig } from './hooks/useNodeConfig'
import { useAutoSave } from './hooks/useAutoSave'
import { useKeyboardShortcuts } from './hooks/useKeyboardShortcuts'
import { generateTemplatePreview } from '@/lib/templateRenderer'
import { FieldHint } from '@/components/ui/field-hint'

interface WorkerNodeConfigProps {
  node: WorkflowNode
}

interface WorkerNodeData {
  task_template: string
  allowed_tools?: string[]
  thinking?: boolean
  system_prompt?: string  // 커스텀 워커용 시스템 프롬프트
  parallel_execution?: boolean  // 병렬 실행 플래그
  config?: {
    output_format?: string
    custom_prompt?: string
  }
}

export const WorkerNodeConfig: React.FC<WorkerNodeConfigProps> = ({ node }) => {
  const [isToolsOpen, setIsToolsOpen] = useState(false)
  const [agents, setAgents] = useState<Agent[]>([])
  const [tools, setTools] = useState<Tool[]>([])
  const [toolSearchQuery, setToolSearchQuery] = useState('')
  const [useDefaultTools, setUseDefaultTools] = useState(true)
  const [canModifyTools, setCanModifyTools] = useState(true)
  const [systemPrompt, setSystemPrompt] = useState('')
  const searchInputRef = useRef<HTMLInputElement>(null)
  const nodes = useWorkflowStore((state) => state.nodes)

  // Agent 및 Tool 목록 로드
  useEffect(() => {
    const loadData = async () => {
      try {
        const [agentList, toolList] = await Promise.all([getAgents(), getTools()])
        setAgents(agentList)
        setTools(toolList)
      } catch (error) {
        console.error('❌ 데이터 로드 실패:', error)
      }
    }
    loadData()
  }, [])

  // 초기 데이터 설정
  const initialData: WorkerNodeData = {
    task_template: node.data.task_template || '',
    allowed_tools: node.data.allowed_tools || [],
    thinking: node.data.thinking,
    system_prompt: node.data.system_prompt || '',  // 커스텀 워커용
    parallel_execution: node.data.parallel_execution ?? false,
    config: {
      output_format: node.data.config?.output_format || 'plain_text',
      custom_prompt: node.data.config?.custom_prompt || '',
    },
  }

  // allowed_tools 여부로 기본 설정 사용 여부 판단
  useEffect(() => {
    if (node.data.allowed_tools && node.data.allowed_tools.length > 0) {
      setUseDefaultTools(false)
    } else {
      setUseDefaultTools(true)
    }
  }, [node.data.allowed_tools])

  // 시스템 프롬프트 및 도구 수정 가능 여부 설정
  useEffect(() => {
    if (agents.length === 0) return

    const agent = agents.find((a) => a.name === node.data.agent_name)
    if (agent) {
      // 커스텀 워커인 경우 노드 데이터의 system_prompt 사용, 없으면 agent의 것 사용
      const promptToUse = agent.is_custom && node.data.system_prompt
        ? node.data.system_prompt
        : agent.system_prompt || ''
      setSystemPrompt(promptToUse)

      // 커스텀 워커는 항상 도구 수정 가능, 기본 워커는 쓰기 도구가 있어야 수정 가능
      if (agent.is_custom) {
        setCanModifyTools(true)
      } else {
        const hasWriteTools = agent.allowed_tools.some((tool) => ['write', 'edit', 'bash'].includes(tool))
        setCanModifyTools(hasWriteTools)
      }
    } else {
      setSystemPrompt(`❌ Agent '${node.data.agent_name}'의 시스템 프롬프트를 찾을 수 없습니다.`)
    }
  }, [agents, node.data.agent_name, node.data.system_prompt])

  // 노드 설정 Hook
  const { data, setData, hasChanges, save, reset } = useNodeConfig<WorkerNodeData>({
    nodeId: node.id,
    initialData,
    onValidate: (data) => {
      const errors: Record<string, string> = {}

      if (!data.task_template.trim()) {
        errors.task_template = '작업 템플릿을 입력하세요'
      }

      // 변수 구문 검증
      const openBraces = (data.task_template.match(/\{\{/g) || []).length
      const closeBraces = (data.task_template.match(/\}\}/g) || []).length
      if (openBraces !== closeBraces) {
        errors.task_template = '변수 구문이 올바르지 않습니다 ({{ }})'
      }

      // 도구 선택 검증
      if (!useDefaultTools && (!data.allowed_tools || data.allowed_tools.length === 0)) {
        errors.tools = '최소 1개의 도구를 선택하거나 기본 설정을 사용하세요'
      }

      return errors
    },
  })

  // 자동 저장
  useAutoSave({
    hasChanges,
    onSave: save,
    delay: 3000,
  })

  // 키보드 단축키
  useKeyboardShortcuts({
    handlers: {
      onSave: hasChanges ? save : undefined,
      onReset: hasChanges ? reset : undefined,
      onSearch: () => searchInputRef.current?.focus(),
    },
  })

  // 입력 필드에서 키 이벤트 전파 방지
  const handleInputKeyDown = (e: React.KeyboardEvent) => {
    e.stopPropagation()
  }

  // 도구 토글
  const handleToggleTool = (toolName: string) => {
    const currentTools = data.allowed_tools || []
    const newTools = currentTools.includes(toolName)
      ? currentTools.filter((t) => t !== toolName)
      : [...currentTools, toolName]

    setData({ ...data, allowed_tools: newTools })
  }

  // 필터링된 도구
  const filteredTools = tools.filter(
    (tool) =>
      tool.name.toLowerCase().includes(toolSearchQuery.toLowerCase()) ||
      tool.description.toLowerCase().includes(toolSearchQuery.toLowerCase())
  )

  // 현재 Agent 정보
  const currentAgent = agents.find((a) => a.name === node.data.agent_name)

  return (
    <div className="h-full overflow-hidden flex flex-col">
      {/* 설정 내용 */}
      <div className="flex-1 overflow-y-auto px-3 pb-3 space-y-3 pt-3">
          {/* 작업 템플릿 */}
          <div className="space-y-2">
            <label className="text-sm font-medium">작업 템플릿</label>
            <textarea
              className="w-full p-2 border rounded-md text-sm font-mono"
              rows={4}
              value={data.task_template}
              onChange={(e) => setData({ ...data, task_template: e.target.value })}
              onKeyDown={handleInputKeyDown}
              placeholder="예: {{input}}을(를) 분석해주세요."
            />
            <FieldHint
              hint="변수: {{parent}} (부모 출력), {{input}} (초기 입력), {{node_<id>}} (특정 노드)"
              tooltip="{{parent}}: 직전 부모 노드 출력 | {{input}}: Input 노드의 초기 입력값 | {{node_<id>}}: 특정 노드 출력 (예: {{node_merge-123}})"
            />

            {/* 실시간 미리보기 (간소화) */}
            {data.task_template.includes('{{') && (
              <div className="text-xs bg-blue-50 border border-blue-200 rounded p-2">
                <div className="font-medium text-blue-900 mb-1">미리보기</div>
                <div className="text-blue-800 font-mono">
                  {generateTemplatePreview(data.task_template, nodes, node.id)}
                </div>
              </div>
            )}
          </div>

          {/* 출력 형식 + 병렬 실행 (2열 Grid) */}
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-2">
              <label className="text-sm font-medium">출력 형식</label>
              <select
                className="w-full p-2 border rounded-md text-sm"
                value={data.config?.output_format || 'plain_text'}
                onChange={(e) => setData({ ...data, config: { ...data.config, output_format: e.target.value } })}
              >
                <option value="plain_text">Plain Text</option>
                <option value="markdown">Markdown</option>
                <option value="json">JSON</option>
                <option value="code">Code Block</option>
              </select>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium">실행 모드</label>
              <label className="flex items-center gap-2 text-sm border rounded-md p-2 cursor-pointer hover:bg-gray-50">
                <input
                  type="checkbox"
                  checked={data.parallel_execution ?? false}
                  onChange={(e) => setData({ ...data, parallel_execution: e.target.checked })}
                  className="w-4 h-4"
                />
                <span>병렬 실행</span>
              </label>
              <FieldHint
                hint={data.parallel_execution ? "✅ 자식 노드 동시 실행" : "⚪ 자식 노드 순차 실행"}
              />
            </div>
          </div>

          {/* 도구 설정 (Collapsible) */}
          <Collapsible open={isToolsOpen} onOpenChange={setIsToolsOpen}>
            <CollapsibleTrigger className="flex items-center justify-between w-full p-2 hover:bg-gray-50 rounded-md border">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium">🔧 도구 설정</span>
                <Badge variant="outline" className="text-xs">
                  {useDefaultTools ? '기본값' : `${(data.allowed_tools || []).length}개 선택`}
                </Badge>
              </div>
              <ChevronDown className={cn("h-4 w-4 transition-transform", isToolsOpen && "transform rotate-180")} />
            </CollapsibleTrigger>
            <CollapsibleContent className="mt-2 space-y-2">
              {canModifyTools && (
                <label className="flex items-center gap-2 text-xs">
                  <input
                    type="checkbox"
                    checked={useDefaultTools}
                    onChange={(e) => {
                      setUseDefaultTools(e.target.checked)
                      if (e.target.checked) {
                        setData({ ...data, allowed_tools: [] })
                      }
                    }}
                    className="w-3 h-3"
                  />
                  기본 설정 사용
                </label>
              )}

              {canModifyTools && !useDefaultTools ? (
                <>
                  <div className="relative">
                    <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                    <input
                      ref={searchInputRef}
                      type="text"
                      placeholder="도구 검색..."
                      className="w-full pl-8 p-2 border rounded-md text-xs"
                      value={toolSearchQuery}
                      onChange={(e) => setToolSearchQuery(e.target.value)}
                      onKeyDown={handleInputKeyDown}
                    />
                  </div>

                  <div className="flex flex-wrap gap-1.5 max-h-48 overflow-y-auto p-2 border rounded-md">
                    {filteredTools.map((tool) => (
                      <Badge
                        key={tool.name}
                        onClick={() => handleToggleTool(tool.name)}
                        className={cn(
                          "cursor-pointer text-xs",
                          (data.allowed_tools || []).includes(tool.name)
                            ? "bg-blue-600 text-white hover:bg-blue-700"
                            : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                        )}
                        title={tool.description}
                      >
                        {tool.name}
                      </Badge>
                    ))}
                  </div>
                </>
              ) : (
                <div className="flex flex-wrap gap-1.5 p-2 bg-gray-50 border rounded-md">
                  {currentAgent?.allowed_tools.map((toolName) => (
                    <Badge key={toolName} variant="outline" className="text-xs">
                      {toolName}
                    </Badge>
                  )) || <span className="text-xs text-muted-foreground">도구 없음</span>}
                </div>
              )}

              {/* Thinking 모드 */}
              <div className="flex items-center gap-2 pt-2 border-t">
                <input
                  type="checkbox"
                  id="thinking-mode"
                  checked={data.thinking ?? currentAgent?.thinking ?? false}
                  onChange={(e) => setData({ ...data, thinking: e.target.checked })}
                  className="w-4 h-4"
                />
                <label htmlFor="thinking-mode" className="text-xs cursor-pointer">
                  Thinking 모드 {data.thinking ? '✅' : '⚪'}
                </label>
              </div>
            </CollapsibleContent>
          </Collapsible>

          {/* 고급 설정 (Accordion) */}
          <Accordion type="single" collapsible className="border rounded-md">
            <AccordionItem value="advanced" className="border-0">
              <AccordionTrigger className="px-3 py-2 hover:no-underline hover:bg-gray-50">
                <span className="text-sm font-medium">⚙️ 고급 설정</span>
              </AccordionTrigger>
              <AccordionContent className="px-3 pb-3 space-y-3">
                {/* 추가 지시사항 */}
                <div className="space-y-2">
                  <label className="text-sm font-medium">추가 지시사항</label>
                  <textarea
                    className="w-full p-2 border rounded-md text-xs"
                    rows={4}
                    value={data.config?.custom_prompt || ''}
                    onChange={(e) => setData({ ...data, config: { ...data.config, custom_prompt: e.target.value } })}
                    onKeyDown={handleInputKeyDown}
                    placeholder="예: 코드 작성 시 주석을 포함해주세요."
                  />
                  <FieldHint hint="워커의 기본 시스템 프롬프트에 추가됩니다" />
                </div>

                {/* 시스템 프롬프트 (커스텀 워커만) */}
                {currentAgent?.is_custom && (
                  <div className="space-y-2">
                    <label className="text-sm font-medium">시스템 프롬프트</label>
                    <textarea
                      className="w-full p-2 border rounded-md text-xs font-mono"
                      rows={10}
                      value={data.system_prompt || systemPrompt}
                      onChange={(e) => setData({ ...data, system_prompt: e.target.value })}
                      onKeyDown={handleInputKeyDown}
                    />
                    <FieldHint hint="커스텀 워커의 시스템 프롬프트 (수정 가능)" />
                  </div>
                )}
              </AccordionContent>
            </AccordionItem>
          </Accordion>
      </div>
    </div>
  )
}
