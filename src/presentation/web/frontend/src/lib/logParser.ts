/**
 * 로그 메시지 파싱 유틸리티
 *
 * Claude SDK 응답 메시지를 파싱하여 보기 좋게 표시합니다.
 */

export interface ParsedLogMessage {
  type: 'user_message' | 'tool_result' | 'assistant_message' | 'tool_use' | 'thinking' | 'text' | 'tool_flow'
  content: string
  toolUse?: {
    toolName: string
    input: Record<string, any>
    output?: string
  }
  // 툴 플로우: tool_use와 tool_result를 하나로 묶음
  toolFlow?: {
    toolName: string
    input: Record<string, any>
    output: string
    duration?: number  // 소요 시간 (초)
    success: boolean
  }
}

/**
 * 여러 블록을 포함할 수 있는 파싱 결과
 */
export interface ParsedLogBlocks {
  blocks: ParsedLogMessage[]
  hasMultipleBlocks: boolean
}

/**
 * 텍스트에서 JSON 블록들을 추출
 *
 * 예: "텍스트 {"role": "assistant"} 더 많은 텍스트"
 * → [
 *     { type: 'text', text: '텍스트 ' },
 *     { type: 'json', text: '{"role": "assistant"}' },
 *     { type: 'text', text: ' 더 많은 텍스트' }
 *   ]
 */
function extractJSONBlocks(text: string): Array<{ type: 'text' | 'json'; text: string }> {
  const blocks: Array<{ type: 'text' | 'json'; text: string }> = []
  let currentPos = 0

  while (currentPos < text.length) {
    // JSON 블록 시작 찾기 ({"role":)
    const jsonStartMatch = text.substring(currentPos).match(/\{"role":\s*"(assistant|user|system)"/)

    if (!jsonStartMatch || jsonStartMatch.index === undefined) {
      // JSON 블록이 더 이상 없으면 나머지는 텍스트
      const remainingText = text.substring(currentPos)
      if (remainingText.trim()) {
        blocks.push({ type: 'text', text: remainingText })
      }
      break
    }

    const jsonStart = currentPos + jsonStartMatch.index

    // JSON 블록 시작 전 텍스트가 있으면 추가
    if (jsonStart > currentPos) {
      const textBefore = text.substring(currentPos, jsonStart)
      if (textBefore.trim()) {
        blocks.push({ type: 'text', text: textBefore })
      }
    }

    // JSON 블록 끝 찾기 (중괄호 카운팅)
    let braceCount = 0
    let inString = false
    let escaped = false
    let jsonEnd = jsonStart

    for (let i = jsonStart; i < text.length; i++) {
      const char = text[i]

      if (escaped) {
        escaped = false
        continue
      }

      if (char === '\\') {
        escaped = true
        continue
      }

      if (char === '"' && !escaped) {
        inString = !inString
        continue
      }

      if (!inString) {
        if (char === '{') braceCount++
        if (char === '}') {
          braceCount--
          if (braceCount === 0) {
            jsonEnd = i + 1
            break
          }
        }
      }
    }

    // JSON 블록 추출
    const jsonText = text.substring(jsonStart, jsonEnd)
    if (jsonText) {
      blocks.push({ type: 'json', text: jsonText })
    }

    currentPos = jsonEnd
  }

  return blocks
}

/**
 * Python 문자열 리터럴에서 내용 추출 (작은따옴표 이스케이프 처리)
 * 예: 'Hello \\'world\\'' → Hello 'world'
 */
function extractPythonString(str: string, startIndex: number): { content: string; endIndex: number } | null {
  let content = ''
  let i = startIndex
  let escaped = false

  while (i < str.length) {
    const char = str[i]

    if (escaped) {
      // 이스케이프된 문자 처리
      switch (char) {
        case 'n':
          content += '\n'
          break
        case 't':
          content += '\t'
          break
        case 'r':
          content += '\r'
          break
        case '\\':
          content += '\\'
          break
        case "'":
          content += "'"
          break
        case '"':
          content += '"'
          break
        default:
          content += char
      }
      escaped = false
    } else if (char === '\\') {
      escaped = true
    } else if (char === "'") {
      // 문자열 끝
      return { content, endIndex: i + 1 }
    } else {
      content += char
    }

    i++
  }

  // 문자열이 닫히지 않음
  return null
}

/**
 * UserMessage Python repr 형식 파싱
 * 예: UserMessage(content=[ToolResultBlock(tool_use_id='...', content='...', is_error=None)], parent_tool_use_id=None)
 */
function parseUserMessageRepr(message: string): ParsedLogMessage | null {
  // UserMessage 시작 확인
  if (!message.startsWith('UserMessage(')) {
    return null
  }

  // ToolResultBlock 파싱 시도
  if (message.includes('ToolResultBlock(')) {
    const toolUseIdMatch = message.match(/tool_use_id='([^']+)'/)
    if (!toolUseIdMatch) return null

    // content=' 위치 찾기
    const contentStartIndex = message.indexOf("content='")
    if (contentStartIndex === -1) return null

    // content 문자열 추출 (작은따옴표 이스케이프 처리)
    const extracted = extractPythonString(message, contentStartIndex + 9)
    if (!extracted) return null

    return {
      type: 'tool_result',
      content: extracted.content,
      toolUse: {
        toolName: '도구',  // ToolResultBlock에는 도구 이름이 없음
        input: {},
        output: extracted.content,
      }
    }
  }

  // TextBlock 파싱 시도
  if (message.includes('TextBlock(')) {
    const textStartIndex = message.indexOf("text='")
    if (textStartIndex === -1) return null

    // text 문자열 추출 (작은따옴표 이스케이프 처리)
    const extracted = extractPythonString(message, textStartIndex + 6)
    if (!extracted) return null

    return {
      type: 'user_message',
      content: extracted.content,
    }
  }

  return null
}

/**
 * JSON 형식의 메시지 파싱 (Pydantic model_dump 출력)
 */
function parseJSONMessage(message: string): ParsedLogMessage | null {
  try {
    const data = JSON.parse(message)

    // AssistantMessage 형식
    if (data.role === 'assistant' && data.content) {
      const blocks = Array.isArray(data.content) ? data.content : [data.content]

      for (const block of blocks) {
        // TextBlock
        if (block.type === 'text' && block.text) {
          return {
            type: 'assistant_message',
            content: block.text,
          }
        }

        // ThinkingBlock (Extended Thinking)
        // SDK에서 thinking 필드로 전송 (text가 아님)
        if (block.type === 'thinking' && (block.thinking || block.text)) {
          return {
            type: 'thinking',
            content: block.thinking || block.text,  // 하위 호환성 유지
          }
        }

        // ToolUseBlock
        if (block.type === 'tool_use' && block.name) {
          return {
            type: 'tool_use',
            content: `도구 호출: ${block.name}`,
            toolUse: {
              toolName: block.name,
              input: block.input || {},
            }
          }
        }
      }
    }

    // UserMessage 형식
    if (data.role === 'user' && data.content) {
      const blocks = Array.isArray(data.content) ? data.content : [data.content]

      for (const block of blocks) {
        // TextBlock
        if (block.type === 'text' && block.text) {
          return {
            type: 'user_message',
            content: block.text,
          }
        }

        // ToolResultBlock
        if (block.type === 'tool_result') {
          const content = typeof block.content === 'string' ? block.content : JSON.stringify(block.content, null, 2)
          return {
            type: 'tool_result',
            content,
            toolUse: {
              toolName: '도구',
              input: { tool_use_id: block.tool_use_id },
              output: content,
            }
          }
        }
      }
    }

    // SystemMessage 형식
    if (data.role === 'system') {
      if (typeof data.content === 'string') {
        return {
          type: 'text',
          content: data.content,
        }
      } else if (Array.isArray(data.content)) {
        for (const block of data.content) {
          if (block.type === 'text' && block.text) {
            return {
              type: 'text',
              content: block.text,
            }
          }
        }
      }
    }

    // ToolResultBlock (content blocks 안에 있을 수 있음)
    if (data.type === 'tool_result' && data.content) {
      const content = typeof data.content === 'string' ? data.content : JSON.stringify(data.content, null, 2)
      return {
        type: 'tool_result',
        content,
        toolUse: {
          toolName: data.tool_name || 'Unknown',
          input: {},
          output: content,
        }
      }
    }

    // 파싱 가능했지만 알 수 없는 형식
    return {
      type: 'text',
      content: JSON.stringify(data, null, 2),
    }
  } catch (e) {
    // JSON 파싱 실패
    return null
  }
}

/**
 * 로그 메시지 파싱 (메인 함수)
 */
export function parseLogMessage(message: string): ParsedLogMessage {
  // 1. UserMessage Python repr 파싱 (우선순위 최상)
  const userMessageRepr = parseUserMessageRepr(message)
  if (userMessageRepr) return userMessageRepr

  // 2. JSON 형식 파싱 시도
  const jsonParsed = parseJSONMessage(message)
  if (jsonParsed) return jsonParsed

  // 3. 파싱 실패 시 원본 반환
  return {
    type: 'text',
    content: message,
  }
}

/**
 * 로그 메시지 파싱 (여러 블록 지원)
 *
 * 텍스트와 JSON이 혼합된 경우를 처리합니다.
 * 예: "텍스트 내용{"role": "assistant", ...}더 많은 텍스트"
 *
 * @param message - 파싱할 메시지
 * @param toolUseIdToNameGlobal - 전역 tool_use_id → tool_name 매핑 (선택)
 */
export function parseLogMessageBlocks(message: string, toolUseIdToNameGlobal?: Record<string, string>): ParsedLogBlocks {
  if (!message || typeof message !== 'string') {
    return {
      blocks: [{ type: 'text', content: message }],
      hasMultipleBlocks: false,
    }
  }

  // 1. UserMessage Python repr 파싱 시도 (단일 블록)
  const userMessageRepr = parseUserMessageRepr(message)
  if (userMessageRepr) {
    return {
      blocks: [userMessageRepr],
      hasMultipleBlocks: false,
    }
  }

  // 2. JSON 블록 추출 시도
  const extractedBlocks = extractJSONBlocks(message)

  // 추출된 블록이 없으면 전체를 텍스트로 처리
  if (extractedBlocks.length === 0) {
    return {
      blocks: [{ type: 'text', content: message }],
      hasMultipleBlocks: false,
    }
  }

  // 3. 각 블록 파싱
  const parsedBlocks: ParsedLogMessage[] = []
  // tool_use_id -> tool_name 매핑 (tool_result에서 도구 이름 표시용)
  const toolUseIdToName: Record<string, string> = {}

  for (const block of extractedBlocks) {
    if (block.type === 'json') {
      // JSON 블록 파싱
      const jsonParsed = parseJSONMessage(block.text)
      if (jsonParsed) {
        // tool_use 블록이면 tool_use_id와 도구 이름 매핑 저장
        if (jsonParsed.type === 'tool_use' && jsonParsed.toolUse) {
          try {
            const data = JSON.parse(block.text)
            if (data.role === 'assistant' && Array.isArray(data.content)) {
              for (const contentBlock of data.content) {
                if (contentBlock.type === 'tool_use' && contentBlock.id && contentBlock.name) {
                  toolUseIdToName[contentBlock.id] = contentBlock.name
                }
              }
            }
          } catch (e) {
            // JSON 파싱 실패 시 무시
          }
        }

        // tool_result 블록이면 매핑 테이블에서 도구 이름 찾기
        if (jsonParsed.type === 'tool_result' && jsonParsed.toolUse) {
          try {
            const data = JSON.parse(block.text)
            if (data.role === 'user' && Array.isArray(data.content)) {
              for (const contentBlock of data.content) {
                if (contentBlock.type === 'tool_result' && contentBlock.tool_use_id) {
                  // 로컬 매핑 테이블에서 먼저 찾기
                  let toolName = toolUseIdToName[contentBlock.tool_use_id]
                  // 없으면 전역 매핑 테이블에서 찾기
                  if (!toolName && toolUseIdToNameGlobal) {
                    toolName = toolUseIdToNameGlobal[contentBlock.tool_use_id]
                  }
                  if (toolName) {
                    jsonParsed.toolUse.toolName = toolName
                  }
                }
              }
            }
          } catch (e) {
            // JSON 파싱 실패 시 무시
          }
        }

        parsedBlocks.push(jsonParsed)
      } else {
        // JSON 파싱 실패 시 텍스트로 처리
        parsedBlocks.push({ type: 'text', content: block.text })
      }
    } else {
      // 텍스트 블록
      parsedBlocks.push({ type: 'text', content: block.text })
    }
  }

  return {
    blocks: parsedBlocks,
    hasMultipleBlocks: parsedBlocks.length > 1,
  }
}

/**
 * 툴 플로우 그룹화: tool_use와 tool_result를 하나로 묶음
 *
 * @param blocks - 파싱된 블록들
 * @returns 툴 플로우가 적용된 블록들
 */
export function groupToolFlows(blocks: ParsedLogMessage[]): ParsedLogMessage[] {
  const result: ParsedLogMessage[] = []
  const toolUseMap = new Map<string, { block: ParsedLogMessage; index: number }>()

  for (let i = 0; i < blocks.length; i++) {
    const block = blocks[i]

    if (block.type === 'tool_use' && block.toolUse) {
      // tool_use 블록 저장 (tool_use_id 추출 시도)
      const toolUseId = `${block.toolUse.toolName}_${i}` // 임시 ID
      toolUseMap.set(toolUseId, { block, index: i })
      // tool_use는 나중에 tool_result와 매칭되면 제거되므로 일단 추가하지 않음
      result.push(block)
    } else if (block.type === 'tool_result' && block.toolUse) {
      // tool_result 블록 발견 -> 이전 tool_use와 매칭 시도
      const toolName = block.toolUse.toolName

      // 가장 최근의 같은 이름을 가진 tool_use 찾기
      let matchedToolUse: ParsedLogMessage | null = null
      let matchedIndex = -1

      for (const [id, entry] of toolUseMap.entries()) {
        if (entry.block.toolUse?.toolName === toolName && entry.index < i) {
          if (matchedIndex === -1 || entry.index > matchedIndex) {
            matchedToolUse = entry.block
            matchedIndex = entry.index
          }
        }
      }

      if (matchedToolUse && matchedToolUse.toolUse) {
        // 매칭 성공 -> tool_flow 블록 생성
        const toolFlowBlock: ParsedLogMessage = {
          type: 'tool_flow',
          content: `${toolName} 실행`,
          toolFlow: {
            toolName,
            input: matchedToolUse.toolUse.input,
            output: block.toolUse.output || block.content,
            success: !block.content.toLowerCase().includes('error'),
          }
        }

        // 이전 tool_use 블록을 tool_flow로 교체
        const prevIndex = result.findIndex((b, idx) =>
          b.type === 'tool_use' &&
          b.toolUse?.toolName === toolName &&
          idx >= matchedIndex
        )

        if (prevIndex !== -1) {
          result[prevIndex] = toolFlowBlock
        } else {
          result.push(toolFlowBlock)
        }

        // 매칭된 tool_use 제거
        toolUseMap.delete(`${toolName}_${matchedIndex}`)
      } else {
        // 매칭 실패 -> tool_result 블록 그대로 추가
        result.push(block)
      }
    } else {
      // 다른 블록들은 그대로 추가
      result.push(block)
    }
  }

  return result
}
