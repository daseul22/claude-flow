"""
Merge 노드 실행기

Merge 노드 실행 로직을 담당합니다.
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


class MergeNodeExecutor(BaseNodeExecutor):
    """Merge 노드 실행기 (WorkflowConditionEvaluator에 위임)"""

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
        Merge 노드 실행

        Args:
            node: 실행할 노드
            node_outputs: 이전 노드 출력들
            node_inputs: 각 노드가 실제로 받을 입력 (사용 안 함)
            initial_input: 초기 입력 (사용 안 함)
            session_id: 세션 ID
            edges: 엣지 목록
            all_nodes: 모든 노드 목록 (사용 안 함)
            condition_evaluator: 조건 평가기 (merge 로직 포함)
            template_renderer: 템플릿 렌더러 (사용 안 함)

        Yields:
            WorkflowNodeExecutionEvent: 노드 실행 이벤트
        """
        start_time = time.time()
        node_id = node.id

        # 부모 노드 출력들 가져오기
        parent_nodes = self._get_parent_nodes(node_id, edges)
        parent_outputs_list = []
        for pid in parent_nodes:
            parent_outputs_list.append(node_outputs.get(pid, ""))

        node_data = node.data

        # 입력 요약
        input_summary = {f"parent_{i+1}": len(output) for i, output in enumerate(parent_outputs_list)}

        # node_start 이벤트
        yield WorkflowNodeExecutionEvent(
            event_type="node_start",
            node_id=node_id,
            data={
                "node_type": "merge",
                "input": "\n\n---\n\n".join(parent_outputs_list),
                "input_summary": input_summary,
                "merge_strategy": (
                    node_data.merge_strategy
                    if hasattr(node_data, "merge_strategy")
                    else node_data.get("merge_strategy")
                ),
            },
            timestamp=datetime.now().isoformat(),
        )

        try:
            # WorkflowConditionEvaluator의 execute_merge_node 호출
            merged_output = await condition_evaluator.execute_merge_node(
                node, node_outputs, edges, session_id
            )

            node_outputs[node_id] = merged_output
            elapsed_time = time.time() - start_time

            # node_complete 이벤트
            yield WorkflowNodeExecutionEvent(
                event_type="node_complete",
                node_id=node_id,
                data={
                    "node_type": "merge",
                    "output_length": len(merged_output),
                    "output": merged_output,
                },
                timestamp=datetime.now().isoformat(),
                elapsed_time=elapsed_time,
            )

            logger.info(f"[{session_id}] 병합 노드 완료: {node_id} (출력 길이: {len(merged_output)})")

        except Exception as e:
            error_msg = f"병합 노드 실행 실패: {str(e)}"
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
