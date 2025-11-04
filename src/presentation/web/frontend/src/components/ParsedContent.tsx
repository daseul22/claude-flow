/**
 * 파싱된 로그 메시지 렌더링 컴포넌트
 *
 * logParser로 파싱된 메시지를 블럭 종류별로 다르게 표시합니다.
 */

import React, { useState } from 'react'
import { ChevronDown, ChevronRight, Brain } from 'lucide-react'
import { parseLogMessageBlocks, ParsedLogMessage } from '@/lib/logParser'

interface ParsedContentProps {
  content: string
  className?: string
  toolUseIdToName?: Record<string, string>
}

/**
 * 단일 블록 렌더링 컴포넌트
 */
const ParsedBlock: React.FC<{ block: ParsedLogMessage; blockIndex: number }> = ({ block, blockIndex }) => {
  const [isExpanded, setIsExpanded] = useState(false)

  const toggleExpanded = () => {
    setIsExpanded(!isExpanded)
  }

  switch (block.type) {
    case 'user_message':
      return (
        <div className="space-y-1" key={blockIndex}>
          <div className="text-xs font-medium text-gray-600">👤 사용자</div>
          <div className="text-sm whitespace-pre-wrap text-gray-800">
            {block.content}
          </div>
        </div>
      )

    case 'assistant_message':
      return (
        <div className="space-y-1" key={blockIndex}>
          <div className="text-xs font-medium text-gray-600">🤖 어시스턴트</div>
          <div className="text-sm whitespace-pre-wrap text-gray-800">
            {block.content}
          </div>
        </div>
      )

    case 'tool_use':
      return (
        <div className="space-y-1" key={blockIndex}>
          <div
            className="flex items-center gap-2 cursor-pointer hover:bg-gray-50 p-1 rounded transition-colors"
            onClick={toggleExpanded}
          >
            {isExpanded ? (
              <ChevronDown className="h-3 w-3 text-gray-500 flex-shrink-0" />
            ) : (
              <ChevronRight className="h-3 w-3 text-gray-500 flex-shrink-0" />
            )}
            <div className="text-xs font-medium text-gray-700 overflow-hidden text-ellipsis whitespace-nowrap">
              🔧 {block.toolUse?.toolName}
            </div>
          </div>

          {isExpanded && block.toolUse && (
            <div className="ml-5 pl-3 border-l-2 border-gray-200 space-y-1 max-h-[300px] overflow-y-auto">
              {Object.keys(block.toolUse.input).length > 0 && (
                <div>
                  <div className="text-xs text-gray-500 mb-1">파라미터:</div>
                  <pre className="text-xs text-gray-700 bg-gray-50 p-2 rounded overflow-x-auto break-words whitespace-pre-wrap">
                    {JSON.stringify(block.toolUse.input, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          )}

          {!isExpanded && (
            <div className="ml-5 text-xs text-gray-500">
              {Object.keys(block.toolUse?.input || {}).length}개 파라미터
            </div>
          )}
        </div>
      )

    case 'tool_result':
      return (
        <div className="space-y-1" key={blockIndex}>
          <div
            className="flex items-center gap-2 cursor-pointer hover:bg-gray-50 p-1 rounded transition-colors"
            onClick={toggleExpanded}
          >
            {isExpanded ? (
              <ChevronDown className="h-3 w-3 text-gray-500 flex-shrink-0" />
            ) : (
              <ChevronRight className="h-3 w-3 text-gray-500 flex-shrink-0" />
            )}
            <div className="text-xs font-medium text-gray-700 overflow-hidden text-ellipsis whitespace-nowrap">
              ✅ {block.toolUse?.toolName} 결과
            </div>
          </div>

          {isExpanded && (
            <div className="ml-5 pl-3 border-l-2 border-gray-200 space-y-1 max-h-[300px] overflow-y-auto">
              <div>
                <div className="text-xs text-gray-500 mb-1">결과:</div>
                <div className="text-xs whitespace-pre-wrap text-gray-700 break-words">
                  {block.content}
                </div>
              </div>
            </div>
          )}

          {!isExpanded && (
            <div className="ml-5 text-xs text-gray-500 overflow-hidden text-ellipsis whitespace-nowrap">
              {block.content.length > 100 ? `${block.content.substring(0, 100)}...` : block.content}
            </div>
          )}
        </div>
      )

    case 'thinking':
      return (
        <div className="space-y-1" key={blockIndex}>
          <div
            className="flex items-center gap-2 cursor-pointer hover:bg-gray-50 p-1 rounded transition-colors"
            onClick={toggleExpanded}
          >
            {isExpanded ? (
              <ChevronDown className="h-3 w-3 text-gray-500 flex-shrink-0" />
            ) : (
              <ChevronRight className="h-3 w-3 text-gray-500 flex-shrink-0" />
            )}
            <Brain className="h-3.5 w-3.5 text-gray-500 flex-shrink-0" />
            <div className="text-xs font-medium text-gray-700 overflow-hidden text-ellipsis whitespace-nowrap">
              사고 과정
            </div>
          </div>

          {isExpanded && (
            <div className="ml-5 pl-3 border-l-2 border-gray-200 max-h-[300px] overflow-y-auto">
              <div className="text-xs whitespace-pre-wrap break-words text-gray-600 italic">
                {block.content}
              </div>
            </div>
          )}

          {!isExpanded && (
            <div className="ml-5 text-xs text-gray-500 italic overflow-hidden text-ellipsis whitespace-nowrap">
              {block.content.length > 80 ? `${block.content.substring(0, 80)}...` : block.content}
            </div>
          )}
        </div>
      )

    case 'text':
    default:
      // 일반 텍스트는 그대로 표시 (줄바꿈 유지)
      return (
        <div className="text-sm whitespace-pre-wrap break-words" key={blockIndex}>
          {block.content}
        </div>
      )
  }
}

/**
 * 파싱된 내용을 블럭 종류별로 렌더링
 */
export const ParsedContent: React.FC<ParsedContentProps> = ({ content, className = '', toolUseIdToName }) => {
  if (!content || content.trim() === '') {
    return (
      <div className={`text-sm text-muted-foreground text-center py-4 ${className}`}>
        아직 실행되지 않았습니다
      </div>
    )
  }

  // 여러 블록으로 파싱 (텍스트와 JSON 혼합 지원)
  const { blocks } = parseLogMessageBlocks(content, toolUseIdToName)

  return (
    <div className={`space-y-2 ${className}`}>
      {blocks.map((block, index) => (
        <ParsedBlock key={index} block={block} blockIndex={index} />
      ))}
    </div>
  )
}
