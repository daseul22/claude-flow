/**
 * Claude Agent SDK 메시지 파서
 *
 * Worker 출력에서 UserMessage, AssistantMessage, ToolResultBlock 등을
 * 파싱하여 보기 좋은 형식으로 변환합니다.
 *
 * 참고: https://docs.claude.com/en/api/agent-sdk/python
 */

/**
 * ToolResultBlock 파싱 및 포맷팅
 *
 * 예시 입력:
 * ToolResultBlock(tool_use_id='toolu_123', content='Success', is_error=None)
 *
 * 예시 출력:
 * ✅ Tool Result: Success
 */
function parseToolResultBlock(text: string): string | null {
  const regex = /ToolResultBlock\(tool_use_id='([^']+)',\s*content='([^']*)'(?:,\s*is_error=(\w+))?\)/g
  const matches = [...text.matchAll(regex)]

  if (matches.length === 0) return null

  return matches
    .map((match) => {
      const [, toolId, content, isError] = match
      const icon = isError === 'True' ? '❌' : '✅'
      const shortId = toolId.substring(0, 12)
      return `${icon} Tool Result [${shortId}]: ${content || '(empty)'}`
    })
    .join('\n')
}

/**
 * ToolUseBlock 파싱 및 포맷팅
 *
 * 예시 입력:
 * ToolUseBlock(id='toolu_123', name='read', input={'file_path': '/path/to/file'})
 *
 * 예시 출력:
 * 🔧 Tool: read
 *    file_path: /path/to/file
 */
function parseToolUseBlock(text: string): string | null {
  const regex = /ToolUseBlock\(id='([^']+)',\s*name='([^']+)',\s*input=(\{[^}]+\})\)/g
  const matches = [...text.matchAll(regex)]

  if (matches.length === 0) return null

  return matches
    .map((match) => {
      const [, toolId, toolName, inputStr] = match
      const shortId = toolId.substring(0, 12)

      // input 파싱 (간단한 dict 파싱)
      const inputPairs = inputStr
        .replace(/[{}]/g, '')
        .split(',')
        .map((pair) => pair.trim())
        .filter((pair) => pair.length > 0)
        .map((pair) => {
          const [key, value] = pair.split(':').map((s) => s.trim())
          return `   ${key}: ${value?.replace(/'/g, '')}`
        })

      return `🔧 Tool: ${toolName} [${shortId}]\n${inputPairs.join('\n')}`
    })
    .join('\n')
}

/**
 * TextBlock 파싱 및 포맷팅
 *
 * 예시 입력:
 * TextBlock(text='Hello world')
 *
 * 예시 출력:
 * Hello world
 */
function parseTextBlock(text: string): string | null {
  const regex = /TextBlock\(text='([^']*)'\)/g
  const matches = [...text.matchAll(regex)]

  if (matches.length === 0) return null

  return matches.map((match) => match[1]).join('\n')
}

/**
 * ThinkingBlock 파싱 및 포맷팅
 *
 * 예시 입력:
 * ThinkingBlock(thinking='I need to analyze...', signature='...')
 *
 * 예시 출력:
 * 💭 Thinking: I need to analyze...
 */
function parseThinkingBlock(text: string): string | null {
  const regex = /ThinkingBlock\(thinking='([^']*)'(?:,\s*signature='[^']*')?\)/g
  const matches = [...text.matchAll(regex)]

  if (matches.length === 0) return null

  return matches.map((match) => `💭 Thinking: ${match[1]}`).join('\n')
}

/**
 * UserMessage 파싱 및 포맷팅
 *
 * 예시 입력:
 * UserMessage(content=[ToolResultBlock(...), ToolResultBlock(...)], parent_tool_use_id=None)
 *
 * 예시 출력:
 * 📨 User Message:
 *    ✅ Tool Result [...]: ...
 *    ✅ Tool Result [...]: ...
 */
function parseUserMessage(text: string): string | null {
  const regex = /UserMessage\(content=\[(.*?)\](?:,\s*parent_tool_use_id=\w+)?\)/g
  const matches = [...text.matchAll(regex)]

  if (matches.length === 0) return null

  return matches
    .map((match) => {
      const contentStr = match[1]

      // content 내부의 ToolResultBlock 파싱
      const toolResults = parseToolResultBlock(contentStr)
      if (toolResults) {
        return `📨 User Message:\n${toolResults
          .split('\n')
          .map((line) => '   ' + line)
          .join('\n')}`
      }

      return `📨 User Message: ${contentStr.substring(0, 100)}...`
    })
    .join('\n')
}

/**
 * AssistantMessage 파싱 및 포맷팅
 *
 * 예시 입력:
 * AssistantMessage(content=[TextBlock(...), ToolUseBlock(...)])
 *
 * 예시 출력:
 * 🤖 Assistant:
 *    (파싱된 content)
 */
function parseAssistantMessage(text: string): string | null {
  const regex = /AssistantMessage\(content=\[(.*?)\](?:,\s*model='[^']*')?\)/g
  const matches = [...text.matchAll(regex)]

  if (matches.length === 0) return null

  return matches
    .map((match) => {
      const contentStr = match[1]

      // content 내부의 블록들 파싱
      const textBlocks = parseTextBlock(contentStr)
      const toolUseBlocks = parseToolUseBlock(contentStr)
      const thinkingBlocks = parseThinkingBlock(contentStr)

      const parts = [textBlocks, toolUseBlocks, thinkingBlocks].filter(Boolean)

      if (parts.length > 0) {
        return `🤖 Assistant:\n${parts
          .join('\n')
          .split('\n')
          .map((line) => '   ' + line)
          .join('\n')}`
      }

      return `🤖 Assistant: ${contentStr.substring(0, 100)}...`
    })
    .join('\n')
}

/**
 * JSON 형태의 Claude 메시지 블록 타입
 */
export interface JsonThinkingBlock {
  type: 'thinking'
  thinking: string
}

export interface JsonTextBlock {
  type: 'text'
  text: string
}

export interface JsonToolUseBlock {
  type: 'tool_use'
  id: string
  name: string
  input: Record<string, unknown>
}

export interface JsonToolResultBlock {
  type: 'tool_result'
  tool_use_id: string
  content: string | unknown[]
  is_error?: boolean
}

export type JsonContentBlock = JsonThinkingBlock | JsonTextBlock | JsonToolUseBlock | JsonToolResultBlock

export interface JsonMessage {
  role: 'user' | 'assistant'
  content: JsonContentBlock[]
  model?: string
}

/**
 * JSON 형태의 Claude 메시지 파싱
 *
 * @param text - JSON 문자열
 * @returns 파싱된 메시지 또는 null
 */
function parseJsonMessage(text: string): ParsedMessage | null {
  try {
    const trimmed = text.trim()
    if (!trimmed.startsWith('{') || !trimmed.includes('"role"')) {
      return null
    }

    const msg: JsonMessage = JSON.parse(trimmed)

    if (!msg.role || !Array.isArray(msg.content)) {
      return null
    }

    // content 블록들을 파싱
    const formattedBlocks: string[] = []
    let hasThinking = false
    let hasText = false
    let blockTypes: Set<string> = new Set()

    for (const block of msg.content) {
      if (!block || typeof block !== 'object' || !('type' in block)) {
        continue
      }

      blockTypes.add(block.type)

      switch (block.type) {
        case 'thinking':
          hasThinking = true
          const thinkingBlock = block as JsonThinkingBlock
          formattedBlocks.push(`💭 사고 과정:\n${thinkingBlock.thinking}`)
          break

        case 'text':
          hasText = true
          const textBlock = block as JsonTextBlock
          formattedBlocks.push(textBlock.text)
          break

        case 'tool_use':
          const toolUseBlock = block as JsonToolUseBlock
          const inputStr = JSON.stringify(toolUseBlock.input, null, 2)
            .split('\n')
            .map((line, i) => i === 0 ? line : '   ' + line)
            .join('\n')
          formattedBlocks.push(
            `🔧 도구 호출: ${toolUseBlock.name}\n` +
            `   ID: ${toolUseBlock.id.substring(0, 12)}...\n` +
            `   매개변수:\n${inputStr}`
          )
          break

        case 'tool_result':
          const toolResultBlock = block as JsonToolResultBlock
          const icon = toolResultBlock.is_error ? '❌' : '✅'
          const content = typeof toolResultBlock.content === 'string'
            ? toolResultBlock.content
            : JSON.stringify(toolResultBlock.content, null, 2)
          formattedBlocks.push(
            `${icon} 도구 실행 결과 [${toolResultBlock.tool_use_id.substring(0, 12)}...]\n${content}`
          )
          break
      }
    }

    if (formattedBlocks.length === 0) {
      return null
    }

    // role prefix는 텍스트가 있고 도구 호출/결과가 아닌 경우에만 표시
    const needsRolePrefix = hasText && !blockTypes.has('tool_use') && !blockTypes.has('tool_result')
    const rolePrefix = needsRolePrefix
      ? (msg.role === 'assistant' ? '🤖 Assistant' : '📨 User')
      : ''

    const content = rolePrefix
      ? `${rolePrefix}:\n${formattedBlocks.join('\n\n')}`
      : formattedBlocks.join('\n\n')

    // 타입 결정: 우선순위 thinking > tool_use > tool_result > text
    let messageType: 'user' | 'assistant' | 'tool_result' | 'tool_use' | 'text' | 'thinking' | 'raw' = msg.role
    if (hasThinking) {
      messageType = 'thinking'
    } else if (blockTypes.has('tool_use') && !hasText) {
      messageType = 'tool_use'
    } else if (blockTypes.has('tool_result') && !hasText) {
      messageType = 'tool_result'
    }

    return {
      type: messageType,
      content,
      isCollapsible: hasThinking || formattedBlocks.length > 3
    }
  } catch (e) {
    return null
  }
}

/**
 * 메시지 타입 감지
 */
export interface ParsedMessage {
  type: 'user' | 'assistant' | 'tool_result' | 'tool_use' | 'text' | 'thinking' | 'raw'
  content: string
  isCollapsible: boolean
}

/**
 * Claude Agent SDK 메시지 파싱 (메인 함수)
 *
 * Worker 출력 텍스트에서 SDK 메시지 타입을 감지하고 보기 좋게 변환합니다.
 *
 * @param text - Worker 출력 텍스트
 * @returns 파싱된 메시지 객체
 */
export function parseClaudeMessage(text: string): ParsedMessage {
  if (!text || typeof text !== 'string') {
    return { type: 'raw', content: text, isCollapsible: false }
  }

  // JSON 형태 메시지 파싱 시도 (우선순위 높음)
  const jsonMsg = parseJsonMessage(text)
  if (jsonMsg) {
    return jsonMsg
  }

  // UserMessage 파싱 시도 (접을 수 있음)
  const userMsg = parseUserMessage(text)
  if (userMsg) {
    return { type: 'user', content: userMsg, isCollapsible: true }
  }

  // AssistantMessage 파싱 시도
  const assistantMsg = parseAssistantMessage(text)
  if (assistantMsg) {
    return { type: 'assistant', content: assistantMsg, isCollapsible: false }
  }

  // 개별 블록 파싱 시도
  const toolResult = parseToolResultBlock(text)
  if (toolResult) {
    return { type: 'tool_result', content: toolResult, isCollapsible: true }
  }

  const toolUse = parseToolUseBlock(text)
  if (toolUse) {
    return { type: 'tool_use', content: toolUse, isCollapsible: false }
  }

  const textBlock = parseTextBlock(text)
  if (textBlock) {
    return { type: 'text', content: textBlock, isCollapsible: false }
  }

  const thinkingBlock = parseThinkingBlock(text)
  if (thinkingBlock) {
    return { type: 'thinking', content: thinkingBlock, isCollapsible: false }
  }

  // 파싱 실패 시 원본 반환
  return { type: 'raw', content: text, isCollapsible: false }
}
