"""
워크플로우 조건 평가기

Condition 노드와 Merge 노드의 실행 로직을 담당합니다.
"""

from typing import Dict, Tuple, List
from src.presentation.web.schemas.workflow import (
    WorkflowNode,
    WorkflowEdge,
    ConditionNodeData,
    MergeNodeData,
)
from src.presentation.web.config import WorkflowConfig
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)


class WorkflowConditionEvaluator:
    """
    워크플로우 조건 평가기

    Condition 노드와 Merge 노드의 실행 로직을 담당합니다.

    Attributes:
        condition_iterations: Condition 노드 반복 횟수 추적 (세션별, 노드별)
    """

    def __init__(self, condition_iterations: Dict[str, Dict[str, int]]):
        """
        WorkflowConditionEvaluator 초기화

        Args:
            condition_iterations: Condition 노드 반복 횟수 추적 (참조)
        """
        self.condition_iterations = condition_iterations

    @staticmethod
    def _get_parent_nodes(node_id: str, edges: List[WorkflowEdge]) -> List[str]:
        """
        노드의 부모 노드 ID 목록 조회 (헬퍼 메서드)

        Args:
            node_id: 노드 ID
            edges: 엣지 목록

        Returns:
            List[str]: 부모 노드 ID 목록
        """
        return [edge.source for edge in edges if edge.target == node_id]

    async def evaluate_llm_condition(
        self,
        condition_prompt: str,
        input_text: str,
        session_id: str,
    ) -> Tuple[bool, str]:
        """
        LLM을 사용하여 조건 평가 (Haiku 모델 사용)

        Args:
            condition_prompt: LLM에게 전달할 조건 프롬프트
            input_text: 평가할 텍스트
            session_id: 세션 ID

        Returns:
            Tuple[bool, str]: (조건 결과, LLM 응답 이유)
        """
        from claude_agent_sdk import query, AssistantMessage, TextBlock
        from claude_agent_sdk.types import ClaudeAgentOptions

        logger.info(f"[{session_id}] LLM 조건 평가 시작 (Haiku 모델)")

        # Haiku 모델로 빠른 판단
        options = ClaudeAgentOptions(
            model=WorkflowConfig.HAIKU_MODEL,
            allowed_tools=[],  # 도구 사용 안함
            permission_mode="bypassPermissions",  # 자동 실행을 위해 승인 우회
        )

        # 입력 텍스트 길이 제한
        truncated_input = input_text[:WorkflowConfig.LLM_INPUT_LIMIT]
        if len(input_text) > WorkflowConfig.LLM_INPUT_LIMIT:
            logger.warning(
                f"[{session_id}] 입력 텍스트 길이 제한: "
                f"{len(input_text)} → {WorkflowConfig.LLM_INPUT_LIMIT} 문자"
            )

        # LLM에게 전달할 전체 프롬프트
        full_prompt = f"""다음 출력을 분석하여 조건을 평가해주세요.

<조건>
{condition_prompt}
</조건>

<평가 대상 출력>
{truncated_input}
</평가 대상 출력>

위 출력이 조건을 만족하는지 판단하여, 다음 형식으로 응답해주세요:

판단: [YES 또는 NO]
이유: [한 줄 설명]

예시:
판단: YES
이유: 테스트가 모두 통과했으며 에러가 없습니다.
"""

        try:
            # LLM 호출 (SDK 표준 방식)
            response_text = ""
            async for response in query(prompt=full_prompt, options=options):
                # AssistantMessage 처리 (SDK 표준 응답 타입)
                if isinstance(response, AssistantMessage):
                    if response.content:
                        for content_block in response.content:
                            # TextBlock에서 텍스트 추출
                            if isinstance(content_block, TextBlock):
                                response_text += content_block.text
                                logger.debug(
                                    f"[{session_id}] LLM 응답 수신 (TextBlock): "
                                    f"{len(content_block.text)} 문자"
                                )

            logger.debug(
                f"[{session_id}] LLM 전체 응답 ({len(response_text)} 문자): "
                f"{response_text[:WorkflowConfig.CONDITION_OUTPUT_LIMIT]}"
            )

            # 응답이 비어있는 경우
            if not response_text.strip():
                logger.warning(f"[{session_id}] LLM 응답이 비어있습니다")
                return False, "LLM 응답이 비어있습니다"

            # 응답 파싱
            lines = response_text.strip().split("\n")
            result = False
            reason = ""

            for line in lines:
                line = line.strip()
                if line.startswith("판단:"):
                    decision = line.replace("판단:", "").strip().upper()
                    result = decision in ["YES", "Y", "TRUE", "예", "네"]
                    logger.debug(f"[{session_id}] 판단 파싱: '{decision}' → {result}")
                elif line.startswith("이유:"):
                    reason = line.replace("이유:", "").strip()
                    logger.debug(f"[{session_id}] 이유 파싱: '{reason}'")

            # 파싱 실패 시 전체 응답 사용
            if not reason:
                reason = response_text[: WorkflowConfig.CONDITION_OUTPUT_LIMIT]
                logger.warning(f"[{session_id}] 응답 파싱 실패, 전체 응답 사용")

            logger.info(
                f"[{session_id}] LLM 조건 평가 완료: {result} (이유: {reason[:100]})"
            )

            return result, reason

        except Exception as e:
            logger.error(f"[{session_id}] LLM 조건 평가 실패: {e}", exc_info=True)
            # 에러 발생 시 안전하게 False 반환
            return False, f"LLM 평가 실패: {str(e)}"

    @staticmethod
    def evaluate_condition(condition_type: str, condition_value: str, input_text: str) -> bool:
        """
        조건 평가

        Args:
            condition_type: 조건 타입 ('contains', 'regex', 'length', 'custom')
            condition_value: 조건 값
            input_text: 평가할 텍스트

        Returns:
            bool: 조건이 True인지 여부
        """
        import re

        if condition_type == "contains":
            # 텍스트 포함 검사
            return condition_value in input_text

        elif condition_type == "regex":
            # 정규표현식 매칭
            try:
                pattern = re.compile(condition_value)
                return bool(pattern.search(input_text))
            except re.error as e:
                logger.error(f"정규표현식 오류: {e}")
                return False

        elif condition_type == "length":
            # 길이 비교 (예: ">100", "<=500", "==0")
            try:
                text_length = len(input_text)
                # condition_value를 파싱하여 비교
                if condition_value.startswith(">="):
                    threshold = int(condition_value[2:].strip())
                    return text_length >= threshold
                elif condition_value.startswith("<="):
                    threshold = int(condition_value[2:].strip())
                    return text_length <= threshold
                elif condition_value.startswith(">"):
                    threshold = int(condition_value[1:].strip())
                    return text_length > threshold
                elif condition_value.startswith("<"):
                    threshold = int(condition_value[1:].strip())
                    return text_length < threshold
                elif condition_value.startswith("=="):
                    threshold = int(condition_value[2:].strip())
                    return text_length == threshold
                else:
                    # 숫자만 있는 경우 == 로 간주
                    threshold = int(condition_value.strip())
                    return text_length == threshold
            except (ValueError, IndexError) as e:
                logger.error(f"길이 조건 파싱 오류: {e}")
                return False

        elif condition_type == "custom":
            # 커스텀 Python 표현식 평가
            try:
                # 안전한 평가를 위해 제한된 네임스페이스 사용
                namespace = {
                    "output": input_text,
                    "len": len,
                    "str": str,
                    "int": int,
                    "float": float,
                }
                result = eval(condition_value, {"__builtins__": {}}, namespace)
                return bool(result)
            except Exception as e:
                logger.error(f"커스텀 조건 평가 오류: {e}")
                return False

        else:
            logger.warning(f"알 수 없는 조건 타입: {condition_type}")
            return False

    async def execute_condition_node(
        self,
        node: WorkflowNode,
        node_outputs: Dict[str, str],
        edges: List[WorkflowEdge],
        session_id: str,
    ) -> Tuple[str, str]:
        """
        조건 분기 노드 실행 (반복 제한 포함)

        Args:
            node: 조건 노드
            node_outputs: 이전 노드 출력들
            edges: 엣지 목록 (분기 경로 확인용)
            session_id: 세션 ID

        Returns:
            Tuple[str, str]: (다음 실행할 노드 ID, 조건 평가 결과 텍스트)

        Raises:
            ValueError: 부모 노드가 없거나 분기 경로가 없는 경우
        """
        node_id = node.id
        node_data: ConditionNodeData = node.data  # type: ignore

        # 반복 횟수 증가
        if session_id not in self.condition_iterations:
            self.condition_iterations[session_id] = {}

        current_iteration = self.condition_iterations[session_id].get(node_id, 0) + 1
        self.condition_iterations[session_id][node_id] = current_iteration

        logger.info(
            f"[{session_id}] 조건 노드 실행: {node_id} "
            f"(타입: {node_data.condition_type}, 반복: {current_iteration}회)"
        )

        # 부모 노드 출력 가져오기
        parent_nodes = self._get_parent_nodes(node_id, edges)
        if not parent_nodes:
            raise ValueError(f"조건 노드 {node_id}에 부모 노드가 없습니다")

        # 첫 번째 부모 노드의 출력 사용
        parent_id = parent_nodes[0]
        parent_output = node_outputs.get(parent_id, "")

        # LLM 조건인 경우 비동기 평가
        llm_reason = ""
        if node_data.condition_type == "llm":
            condition_result, llm_reason = await self.evaluate_llm_condition(
                node_data.condition_value, parent_output, session_id
            )
        else:
            # 일반 조건 평가
            condition_result = self.evaluate_condition(
                node_data.condition_type, node_data.condition_value, parent_output
            )

        logger.info(f"[{session_id}] 조건 평가 결과: {condition_result} (입력 길이: {len(parent_output)})")

        # max_iterations 체크 (반복 제한)
        # max_iterations가 None인 경우 기본값 10 사용
        max_iterations = node_data.max_iterations if node_data.max_iterations is not None else 10

        if current_iteration >= max_iterations:
            logger.warning(
                f"[{session_id}] 조건 노드 {node_id}: "
                f"최대 반복 횟수 도달 ({current_iteration}/{max_iterations}). "
                f"강제로 true 경로로 이동합니다."
            )
            # 최대 반복 횟수 도달 시 강제로 true 경로로 이동
            condition_result = True
            llm_reason = f"최대 반복 횟수 도달 ({max_iterations}회)"

        # 분기 경로 결정 (엣지의 sourceHandle을 사용)
        next_node_id = None
        for edge in edges:
            if edge.source == node_id:
                if condition_result and edge.sourceHandle == "true":
                    next_node_id = edge.target
                    break
                elif not condition_result and edge.sourceHandle == "false":
                    next_node_id = edge.target
                    break

        if next_node_id is None:
            branch_type = "true" if condition_result else "false"
            raise ValueError(
                f"조건 노드 {node_id}의 {branch_type} 분기 경로가 없습니다. "
                f"sourceHandle이 '{branch_type}'인 엣지를 추가해주세요."
            )

        # 조건 결과를 텍스트로 변환
        result_text = f"조건 평가 결과: {condition_result}\n"
        result_text += f"반복 횟수: {current_iteration}/{max_iterations}"
        result_text += f"\n분기: {next_node_id}"

        if llm_reason:
            result_text += f"\nLLM 판단 이유: {llm_reason}"

        return next_node_id, result_text

    async def execute_merge_node(
        self,
        node: WorkflowNode,
        node_outputs: Dict[str, str],
        edges: List[WorkflowEdge],
        session_id: str,
    ) -> str:
        """
        병합 노드 실행

        Args:
            node: 병합 노드
            node_outputs: 이전 노드 출력들
            edges: 엣지 목록
            session_id: 세션 ID

        Returns:
            str: 병합된 출력
        """
        node_id = node.id
        node_data: MergeNodeData = node.data  # type: ignore

        logger.info(f"[{session_id}] 병합 노드 실행: {node_id} (전략: {node_data.merge_strategy})")

        # 부모 노드 출력들 수집 (순서 보장)
        parent_nodes = self._get_parent_nodes(node_id, edges)
        if not parent_nodes:
            raise ValueError(f"병합 노드 {node_id}에 부모 노드가 없습니다")

        # 부모 노드를 targetHandle 순서로 정렬 (input-1, input-2, ...)
        # targetHandle이 없으면 노드 ID 순서로 정렬
        parent_edges = [(edge, edge.source) for edge in edges if edge.target == node_id]

        # targetHandle에서 숫자 추출하여 정렬 (예: "input-1" → 1)
        def get_sort_key(edge_tuple):
            edge, source_id = edge_tuple
            if hasattr(edge, 'targetHandle') and edge.targetHandle:
                try:
                    # "input-N" 형식에서 N 추출
                    parts = edge.targetHandle.split('-')
                    if len(parts) >= 2 and parts[-1].isdigit():
                        return int(parts[-1])
                except (ValueError, AttributeError):
                    pass
            # targetHandle이 없거나 파싱 실패 시 source_id로 정렬
            return source_id

        sorted_edges = sorted(parent_edges, key=get_sort_key)
        parent_nodes = [source_id for _, source_id in sorted_edges]

        logger.debug(
            f"[{session_id}] 병합 노드 {node_id}: "
            f"부모 노드 순서 (정렬됨): {parent_nodes}"
        )

        parent_outputs = []
        for i, pid in enumerate(parent_nodes):
            if pid not in node_outputs:
                logger.warning(
                    f"[{session_id}] 병합 노드 {node_id}: "
                    f"부모 노드 '{pid}'의 출력이 없습니다. 빈 문자열을 사용합니다."
                )
            output = node_outputs.get(pid, "")
            parent_outputs.append(output)
            logger.debug(
                f"[{session_id}] branch_{i+1} (node: {pid}): {len(output)} 문자"
            )

        # 병합 전략에 따라 출력 생성
        if node_data.merge_strategy == "concatenate":
            # 모든 출력을 구분자로 결합
            merged_output = node_data.separator.join(parent_outputs)

        elif node_data.merge_strategy == "first":
            # 첫 번째 출력만 사용
            merged_output = parent_outputs[0] if parent_outputs else ""

        elif node_data.merge_strategy == "last":
            # 마지막 출력만 사용
            merged_output = parent_outputs[-1] if parent_outputs else ""

        elif node_data.merge_strategy == "custom":
            # 커스텀 템플릿 사용
            if node_data.custom_template:
                merged_output = node_data.custom_template

                # 템플릿 변수 치환 ({{branch_1}}, {{branch_2}}, ...)
                for i, output in enumerate(parent_outputs):
                    placeholder = f"{{{{branch_{i+1}}}}}"
                    merged_output = merged_output.replace(placeholder, output)
                    logger.debug(
                        f"[{session_id}] 템플릿 치환: {placeholder} → {len(output)} 문자"
                    )

                # 치환되지 않은 변수 확인 (디버깅용)
                import re
                unused_vars = re.findall(r'\{\{branch_\d+\}\}', merged_output)
                if unused_vars:
                    logger.warning(
                        f"[{session_id}] 병합 노드 {node_id}: "
                        f"사용되지 않은 템플릿 변수: {unused_vars} "
                        f"(부모 노드 개수: {len(parent_outputs)})"
                    )
            else:
                # 템플릿이 없으면 concatenate로 폴백
                logger.warning(
                    f"[{session_id}] 병합 노드 {node_id}: "
                    f"custom 전략이지만 템플릿이 없습니다. concatenate로 폴백합니다."
                )
                merged_output = node_data.separator.join(parent_outputs)

        else:
            logger.warning(f"알 수 없는 병합 전략: {node_data.merge_strategy}, concatenate로 폴백합니다")
            merged_output = node_data.separator.join(parent_outputs)

        logger.info(
            f"[{session_id}] 병합 노드 완료: {node_id} "
            f"(입력: {len(parent_outputs)}개, 출력 길이: {len(merged_output)})"
        )

        return merged_output
