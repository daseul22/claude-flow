"""
워크플로우 공통 유틸리티 함수

워크플로우 실행기 및 노드 실행기에서 공통으로 사용하는 함수들을 모아둔 모듈입니다.
"""

import json
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)


def extract_text_from_worker_output(output: str) -> str:
    """
    Worker 출력에서 최종 텍스트만 추출

    Worker 출력은 thinking, tool_use, tool_result, text 블록을 포함할 수 있습니다.
    이 함수는 type="text"인 블록만 추출하여 반환합니다.

    Args:
        output: Worker의 전체 출력

    Returns:
        str: 최종 텍스트만 추출된 결과
    """
    text_parts = []

    # {"role": "assistant"로 시작하는 JSON 객체 찾기 (중괄호 카운팅)
    start_pattern = '{"role":'
    idx = 0

    while idx < len(output):
        # {"role": 패턴 찾기
        start_idx = output.find(start_pattern, idx)
        if start_idx == -1:
            break

        # 중괄호 카운팅으로 완전한 JSON 객체 추출
        brace_count = 0
        in_string = False
        escape_next = False
        end_idx = start_idx

        for i in range(start_idx, len(output)):
            char = output[i]

            if escape_next:
                escape_next = False
                continue

            if char == "\\":
                escape_next = True
                continue

            if char == '"' and not escape_next:
                in_string = not in_string
                continue

            if not in_string:
                if char == "{":
                    brace_count += 1
                elif char == "}":
                    brace_count -= 1
                    if brace_count == 0:
                        end_idx = i + 1
                        break

        # 완전한 JSON 객체 추출 시도
        if end_idx > start_idx:
            try:
                json_str = output[start_idx:end_idx]
                data = json.loads(json_str)

                # content 배열에서 type="text"인 블록만 추출
                if isinstance(data.get("content"), list):
                    for block in data["content"]:
                        if isinstance(block, dict) and block.get("type") == "text":
                            text_parts.append(block.get("text", ""))

            except json.JSONDecodeError as e:
                logger.debug(f"JSON 파싱 실패 (위치: {start_idx}-{end_idx}): {e}")

            idx = end_idx
        else:
            idx = start_idx + len(start_pattern)

    # 텍스트 블록을 찾았으면 조합하여 반환
    if text_parts:
        result = "\n".join(text_parts).strip()
        logger.debug(f"텍스트 추출 성공: {len(text_parts)}개 블록, {len(result)}자")
        return result

    # JSON 파싱 실패 시 전체 출력 반환 (안전장치)
    logger.warning("텍스트 블록을 찾을 수 없어 전체 출력 반환")
    return output


def classify_chunk_type(chunk: str) -> str:
    """
    Worker 출력 청크의 타입을 분류합니다.

    Args:
        chunk: 출력 청크

    Returns:
        str: "thinking", "tool", "text" 중 하나
    """
    # JSON 블록인지 확인
    if chunk.strip().startswith('{"role":'):
        try:
            data = json.loads(chunk)
            if isinstance(data.get("content"), list):
                for block in data["content"]:
                    if isinstance(block, dict):
                        block_type = block.get("type", "")
                        if block_type in ("thinking", "tool_use", "tool_result"):
                            return "thinking" if block_type == "thinking" else "tool"
                        elif block_type == "text":
                            return "text"
        except json.JSONDecodeError:
            pass

    # 기본적으로 text로 간주
    return "text"
