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

        node_data = node.data

        # node_start 이벤트
        yield WorkflowNodeExecutionEvent(
            event_type="node_start",
            node_id=node_id,
            data={
                "node_type": "condition",
                "input": parent_output,
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
            },
            timestamp=datetime.now().isoformat(),
        )

        try:
            # WorkflowConditionEvaluator의 execute_condition_node 호출
            next_node_id, result_text = await condition_evaluator.execute_condition_node(
                node, node_outputs, edges, session_id
            )

            node_outputs[node_id] = result_text
            elapsed_time = time.time() - start_time

            # node_complete 이벤트
            yield WorkflowNodeExecutionEvent(
                event_type="node_complete",
                node_id=node_id,
                data={
                    "node_type": "condition",
                    "next_node": next_node_id,
                    "output": result_text,
                },
                timestamp=datetime.now().isoformat(),
                elapsed_time=elapsed_time,
            )

            logger.info(f"[{session_id}] 조건 노드 완료: {node_id} → {next_node_id}")

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
