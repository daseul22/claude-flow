"""SDK 응답 파서"""

import json
from typing import Dict, Any, Optional
from rich.text import Text
from rich.panel import Panel
from rich.syntax import Syntax


class ResponseParser:
    """SDK 응답 블록 파서"""

    @staticmethod
    def parse_chunk(chunk: str) -> Dict[str, Any]:
        """청크 파싱 (JSON 또는 일반 텍스트)"""
        # JSON 형식인지 확인
        if chunk.strip().startswith("{") and "\"role\":" in chunk:
            try:
                return {"type": "json", "data": json.loads(chunk)}
            except json.JSONDecodeError:
                pass

        # 일반 텍스트
        return {"type": "text", "data": chunk}

    @staticmethod
    def format_thinking_block(thinking: str, show_full: bool = False) -> Text:
        """ThinkingBlock 포맷팅

        Args:
            thinking: Thinking 내용
            show_full: True면 전체 표시, False면 요약만 표시
        """
        text = Text()
        text.append("💭 ", style="dim cyan")

        if show_full:
            # 전체 표시
            text.append("Thinking", style="bold cyan italic")
            text.append(f"\n{thinking}", style="dim italic")
        else:
            # 요약만 표시 (Claude Code 스타일)
            thinking_lines = thinking.count('\n') + 1
            thinking_chars = len(thinking)
            # 시간 추정 (대략 100자/초로 가정)
            estimated_time = thinking_chars / 100

            text.append(f"Thinking... {estimated_time:.1f}s", style="bold cyan italic")
            text.append(f" ({thinking_lines} lines, {thinking_chars} chars)", style="dim")

        return text

    @staticmethod
    def format_tool_use(tool_name: str, tool_input: Dict[str, Any]) -> Text:
        """ToolUse 포맷팅"""
        text = Text()
        text.append("🔧 ", style="magenta")
        text.append(f"Tool: {tool_name}", style="bold magenta")
        
        # 도구 인자 표시 (간단히)
        if tool_input:
            text.append("\n  ", style="dim")
            # 중요한 인자만 표시
            important_keys = ["file_path", "path", "command", "pattern", "query"]
            shown = False
            for key in important_keys:
                if key in tool_input:
                    value = str(tool_input[key])
                    if len(value) > 50:
                        value = value[:50] + "..."
                    text.append(f"{key}: {value}", style="dim")
                    shown = True
                    break
            
            if not shown and tool_input:
                # 첫 번째 키/값 표시
                key, value = list(tool_input.items())[0]
                value_str = str(value)
                if len(value_str) > 50:
                    value_str = value_str[:50] + "..."
                text.append(f"{key}: {value_str}", style="dim")

        return text

    @staticmethod
    def format_tool_result(tool_use_id: str, content: str) -> Text:
        """ToolResult 포맷팅"""
        text = Text()
        text.append("✓ ", style="green")
        text.append("Tool Result", style="bold green dim")
        
        # 결과 미리보기
        preview = content[:100]
        if len(content) > 100:
            preview += "..."
        text.append(f"\n  {preview}", style="dim")
        
        return text

    @staticmethod
    def should_display_block(block_type: str) -> bool:
        """블록을 화면에 표시할지 결정"""
        # TextBlock은 일반 텍스트로 표시됨
        # ThinkingBlock, ToolUseBlock, ToolResultBlock은 포맷팅해서 표시
        display_types = {"thinking", "tool_use", "tool_result"}
        return block_type in display_types

