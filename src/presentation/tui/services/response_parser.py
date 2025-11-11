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
        """ThinkingBlock 포맷팅 (Claude Code 스타일)

        Args:
            thinking: Thinking 내용
            show_full: True면 전체 표시, False면 요약만 표시
        """
        if show_full:
            # 전체 표시 (구분선 포함)
            text = Text()
            text.append("╭─ ", style="dim blue")
            text.append("Thinking", style="bold cyan italic")
            text.append(" ─────────────────────────────────\n", style="dim blue")

            # Thinking 내용 (들여쓰기)
            for line in thinking.split('\n'):
                text.append("│ ", style="dim blue")
                text.append(f"{line}\n", style="dim italic")

            text.append("╰────────────────────────────────────────────────", style="dim blue")
            return text
        else:
            # 요약만 표시 (Claude Code 스타일)
            text = Text()
            text.append("", style="dim cyan")

            thinking_lines = thinking.count('\n') + 1
            thinking_words = len(thinking.split())

            text.append(f"Thinking... ", style="dim cyan italic")
            text.append(f"({thinking_lines} lines, {thinking_words} words)", style="dim")

            return text

    @staticmethod
    def format_tool_use(tool_name: str, tool_input: Dict[str, Any]) -> Text:
        """ToolUse 포맷팅 (Claude Code 스타일: 간결하게)"""
        text = Text()

        # 도구명 표시 (대문자)
        tool_display = tool_name.capitalize()

        # 도구별 색상 설정
        tool_colors = {
            "read": "cyan",
            "write": "green",
            "edit": "yellow",
            "bash": "magenta",
            "glob": "blue",
            "grep": "blue",
        }
        color = tool_colors.get(tool_name.lower(), "white")

        text.append(f"{tool_display}", style=f"bold {color}")

        # 중요한 인자만 간결하게 표시 (Claude Code 스타일)
        if tool_input:
            # 파일 경로 표시
            if "file_path" in tool_input:
                path = str(tool_input["file_path"])
                if len(path) > 60:
                    # 경로 축약 (앞부분 생략)
                    path = "..." + path[-57:]
                text.append(f" {path}", style="dim")

            # 명령어 표시 (Bash)
            elif "command" in tool_input:
                cmd = str(tool_input["command"])
                if len(cmd) > 60:
                    cmd = cmd[:60] + "..."
                text.append(f" {cmd}", style="dim")

            # 패턴 표시 (Glob, Grep)
            elif "pattern" in tool_input:
                pattern = str(tool_input["pattern"])
                if len(pattern) > 50:
                    pattern = pattern[:50] + "..."
                text.append(f" {pattern}", style="dim")

            # 경로 표시 (일반)
            elif "path" in tool_input:
                path = str(tool_input["path"])
                if len(path) > 60:
                    path = "..." + path[-57:]
                text.append(f" {path}", style="dim")

            # 기타 첫 번째 인자
            else:
                key, value = list(tool_input.items())[0]
                value_str = str(value)
                if len(value_str) > 50:
                    value_str = value_str[:50] + "..."
                text.append(f" {value_str}", style="dim")

        return text

    @staticmethod
    def format_tool_result(tool_use_id: str, content: str) -> Text:
        """ToolResult 포맷팅 (Claude Code 스타일: 최소화)"""
        text = Text()

        # 에러 여부 확인
        is_error = "error" in content.lower()[:50] or "exception" in content.lower()[:50]

        if is_error:
            text.append("✗ ", style="red")
            # 에러 메시지 간략 표시
            error_preview = content[:80]
            if len(content) > 80:
                error_preview += "..."
            text.append(f"{error_preview}", style="dim red")
        else:
            text.append("✓", style="dim green")
            # 성공 시 간결하게 표시 (Claude Code 스타일)
            # 결과 크기 표시
            lines = content.count('\n') + 1
            chars = len(content)
            if chars > 500:
                text.append(f" ({lines} lines, {chars:,} chars)", style="dim")

        return text

    @staticmethod
    def format_todo_list(todos: list[Dict[str, Any]]) -> Text:
        """TodoWrite 투두 리스트 포맷팅 (Claude Code 스타일)

        Args:
            todos: TodoWrite 도구의 todos 배열
                [{"content": "...", "status": "pending", "activeForm": "..."}, ...]
        """
        text = Text()

        # 헤더
        text.append("📋 ", style="")
        text.append("Tasks", style="bold cyan")
        text.append("\n", style="")

        # 상태별 카운트
        status_count = {"pending": 0, "in_progress": 0, "completed": 0}
        for todo in todos:
            status = todo.get("status", "pending")
            status_count[status] += 1

        # 카운트 표시
        text.append(
            f"  {status_count['completed']}/{len(todos)} completed",
            style="dim"
        )
        text.append("\n\n", style="")

        # 투두 항목들
        for i, todo in enumerate(todos, 1):
            status = todo.get("status", "pending")
            content = todo.get("content", "")

            # 상태 이모지
            if status == "completed":
                emoji = "✓"
                style = "green"
            elif status == "in_progress":
                emoji = "●"
                style = "yellow"
            else:  # pending
                emoji = "○"
                style = "dim"

            # 항목 표시
            text.append(f"  {emoji} ", style=style)
            text.append(f"{content}", style=style if status != "completed" else "dim green")
            text.append("\n", style="")

        return text

    @staticmethod
    def should_display_block(block_type: str) -> bool:
        """블록을 화면에 표시할지 결정"""
        # TextBlock은 일반 텍스트로 표시됨
        # ThinkingBlock, ToolUseBlock, ToolResultBlock은 포맷팅해서 표시
        display_types = {"thinking", "tool_use", "tool_result"}
        return block_type in display_types

