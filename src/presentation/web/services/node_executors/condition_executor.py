"""
Condition 노드 실행기

Condition 노드 실행 로직을 담당합니다.
"""

import time
from datetime import datetime
from typing import Dict, Any, AsyncIterator, List

from src.infrastructure.logging import get_logger
from src.presentation.web.schemas.workflow import (
    WorkflowNode,
    WorkflowEdge,
    WorkflowNodeExecutionEvent,
)
from .base import BaseNodeExecutor

logger = get_logger(__name__)


class ConditionNodeExecutor(BaseNodeExecutor):
    """Condition 노드 실행기 (WorkflowConditionEvaluator에 위임)"""

    async def execute(
        self,
        node: WorkflowNode,
        node_outputs: Dict[str, str],
        node_inputs: Dict[str, str],
        initial_input: str,
        session_id: str,
        edges: List[WorkflowEdge],
        all_nodes: List[WorkflowNode],
        condition_evaluator: Any,
        template_renderer: Any,
    ) -> AsyncIterator[WorkflowNodeExecutionEvent]:
        """
        Condition 노드 실행

        Args:
            node: 실행할 노드
            node_outputs: 이전 노드 출력들
            node_inputs: 각 노드가 실제로 받을 입력 (사용 안 함)
            initial_input: 초기 입력 (사용 안 함)
            session_id: 세션 ID
            edges: 엣지 목록
            all_nodes: 모든 노드 목록 (사용 안 함)
            condition_evaluator: 조건 평가기
            template_renderer: 템플릿 렌더러 (사용 안 함)

        Yields:
            WorkflowNodeExecutionEvent: 노드 실행 이벤트
        """
        start_time = time.time()
        node_id = node.id

        # 부모 노드 출력 가져오기
        parent_nodes = self._get_parent_nodes(node_id, edges)
        parent_output = ""
        if parent_nodes:
            parent_id = parent_nodes[0]
            parent_output = node_outputs.get(parent_id, "")

            logger.info(
                f"[{session_id}] [{node_id}] 부모 노드 출력 확인:\n"
                f"  - 부모 노드 ID: {parent_id}\n"
                f"  - 출력 길이: {len(parent_output)}자\n"
                f"  - 출력 미리보기: {parent_output[:300] if parent_output else '(empty)'}"
            )
        else:
            logger.warning(f"[{session_id}] [{node_id}] 부모 노드가 없습니다!")

        node_data = node.data

        # 현재 반복 횟수 가져오기 (다음 실행 예정 횟수)
        current_iteration = 1
        if session_id in condition_evaluator.condition_iterations:
            current_iteration = condition_evaluator.condition_iterations[session_id].get(node_id, 0) + 1

        # max_iterations 가져오기
        max_iterations = node_data.max_iterations if hasattr(node_data, "max_iterations") else None

        # node_start 이벤트
        yield WorkflowNodeExecutionEvent(
            event_type="node_start",
            node_id=node_id,
            data={
                "node_type": "condition",
                "condition_type": (
                    node_data.condition_type
                    if hasattr(node_data, "condition_type")
                    else node_data.get("condition_type")
                ),
                "condition_value": (
                    node_data.condition_value
                    if hasattr(node_data, "condition_value")
                    else node_data.get("condition_value")
                ),
                "iteration": current_iteration,  # 반복 횟수 추가
                "max_iterations": max_iterations,  # 최대 반복 횟수 추가
            },
            timestamp=datetime.now().isoformat(),
        )

        # 입력 이벤트 (Worker와 동일)
        yield WorkflowNodeExecutionEvent(
            event_type="node_output",
            node_id=node_id,
            data={
                "chunk": parent_output,
                "chunk_type": "input",
            },
        )

        try:
            # WorkflowConditionEvaluator의 execute_condition_node_stream 호출 (스트리밍)
            next_node_id = None
            result_text = ""

            async for chunk, final_result in condition_evaluator.execute_condition_node_stream(
                node, node_outputs, edges, session_id
            ):
                if final_result:
                    # 최종 결과 수신
                    next_node_id, result_text = final_result
                elif chunk:
                    # 중간 출력 스트리밍 (LLM 평가 중)
                    yield WorkflowNodeExecutionEvent(
                        event_type="node_output",
                        node_id=node_id,
                        data={
                            "chunk": chunk,
                            "chunk_type": "text",
                        },
                    )
                    logger.debug(
                        f"[{session_id}] [{node_id}] LLM 조건 평가 중간 출력: {len(chunk)}자"
                    )

            # 부모 노드의 출력을 그대로 다음 노드로 전달 (평가 결과는 로그로만)
            node_outputs[node_id] = parent_output

            logger.info(
                f"[{session_id}] [{node_id}] 다음 노드로 전달할 값:\n"
                f"  - 대상 노드: {next_node_id}\n"
                f"  - 전달 값 길이: {len(parent_output)}자\n"
                f"  - 전달 값 미리보기: {parent_output[:300] if parent_output else '(empty)'}\n"
                f"  - 평가 결과 (로그용): {result_text[:200]}"
            )

            elapsed_time = time.time() - start_time

            # node_complete 이벤트
            yield WorkflowNodeExecutionEvent(
                event_type="node_complete",
                node_id=node_id,
                data={
                    "node_type": "condition",
                    "next_node": next_node_id,
                    "output": result_text,  # 로그에는 평가 결과 표시
                    "evaluation_result": result_text,  # 평가 결과 메타정보
                    "forwarded_output": parent_output[:200] if parent_output else "(empty)",  # 실제 전달값 미리보기
                },
                timestamp=datetime.now().isoformat(),
                elapsed_time=elapsed_time,
            )

            logger.info(
                f"[{session_id}] 조건 노드 완료: {node_id} → {next_node_id} "
                f"(부모 출력 {len(parent_output)}자를 그대로 전달)"
            )

        except Exception as e:
            error_msg = f"조건 노드 실행 실패: {str(e)}"
            logger.error(f"[{session_id}] {node_id}: {error_msg}", exc_info=True)

            elapsed_time = time.time() - start_time

            # node_error 이벤트
            yield WorkflowNodeExecutionEvent(
                event_type="node_error",
                node_id=node_id,
                data={"error": error_msg},
                timestamp=datetime.now().isoformat(),
                elapsed_time=elapsed_time,
            )

            raise
