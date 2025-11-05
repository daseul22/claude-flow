"""
Input 노드 실행기

Input 노드 실행 로직을 담당합니다.
"""

from datetime import datetime
from typing import Dict, Any, AsyncIterator, List

from src.infrastructure.logging import get_logger
from src.presentation.web.schemas.workflow import (
    WorkflowNode,
    WorkflowEdge,
    WorkflowNodeExecutionEvent,
    InputNodeData,
)
from .base import BaseNodeExecutor

logger = get_logger(__name__)


class InputNodeExecutor(BaseNodeExecutor):
    """Input 노드 실행기"""

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
        Input 노드 실행

        Args:
            node: 실행할 노드
            node_outputs: 이전 노드 출력들
            node_inputs: 각 노드가 실제로 받을 입력 (사용 안 함)
            initial_input: 초기 입력
            session_id: 세션 ID
            edges: 엣지 목록
            all_nodes: 모든 노드 목록
            condition_evaluator: 조건 평가기 (사용 안 함)
            template_renderer: 템플릿 렌더러 (사용 안 함)

        Yields:
            WorkflowNodeExecutionEvent: 노드 실행 이벤트
        """
        node_id = node.id

        # 입력 값 추출
        if isinstance(node.data, InputNodeData):
            input_value = node.data.initial_input
        elif isinstance(node.data, dict):
            input_value = node.data.get("initial_input", initial_input)
        else:
            input_value = initial_input

        # 노드 출력 저장
        node_outputs[node_id] = input_value

        # node_start 이벤트
        yield WorkflowNodeExecutionEvent(
            event_type="node_start",
            node_id=node_id,
            data={"agent_name": "Input"},
            timestamp=datetime.now().isoformat(),
        )

        # 입력 로그 이벤트
        yield WorkflowNodeExecutionEvent(
            event_type="node_output",
            node_id=node_id,
            data={"chunk": input_value, "log_type": "input"},
        )

        # 최종 출력 이벤트
        yield WorkflowNodeExecutionEvent(
            event_type="node_output",
            node_id=node_id,
            data={"chunk": input_value, "log_type": "output"},
        )

        # node_complete 이벤트
        yield WorkflowNodeExecutionEvent(
            event_type="node_complete",
            node_id=node_id,
            data={
                "node_type": "input",
                "agent_name": "Input",
                "output_length": len(input_value),
            },
            timestamp=datetime.now().isoformat(),
            elapsed_time=0.0,
        )

        logger.info(f"[{session_id}] Input 노드 완료: {node_id} (출력 길이: {len(input_value)})")
