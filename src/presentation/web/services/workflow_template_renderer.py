"""
워크플로우 템플릿 렌더러

노드의 작업 설명 템플릿을 렌더링하고 변수를 치환합니다.
"""

from typing import Dict
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)


class WorkflowTemplateRenderer:
    """
    워크플로우 템플릿 렌더러

    노드의 task_template에 포함된 변수를 실제 값으로 치환합니다.

    지원하는 변수:
    - {{input}}: 워크플로우의 초기 입력
    - {{node_<id>}}: 특정 노드의 출력
    - {{parent}}: 부모 노드의 출력 (부모가 1개인 경우만)
    """

    @staticmethod
    def render_task_template(
        template: str,
        node_id: str,
        node_outputs: Dict[str, str],
        node_inputs: Dict[str, str],
        initial_input: str,
    ) -> str:
        """
        작업 설명 템플릿 렌더링

        변수:
        - {{input}}: 초기 입력 (첫 번째 노드)
        - {{node_<id>}}: 특정 노드의 출력
        - {{parent}}: 부모 노드의 출력 (피드백 루프 지원)

        Args:
            template: 템플릿 문자열
            node_id: 현재 노드 ID
            node_outputs: 노드 ID → 출력 매핑
            node_inputs: 각 노드가 실제로 받을 입력 (피드백 루프 지원)
            initial_input: 초기 입력

        Returns:
            str: 렌더링된 작업 설명

        Examples:
            >>> renderer = WorkflowTemplateRenderer()
            >>> template = "Review this code: {{input}}"
            >>> renderer.render_task_template(template, "node_2", {}, {}, "print('hello')")
            "Review this code: print('hello')"

            >>> template = "Fix issues from: {{node_reviewer}}"
            >>> outputs = {"node_reviewer": "Found 3 bugs"}
            >>> renderer.render_task_template(template, "node_3", outputs, {}, "")
            "Fix issues from: Found 3 bugs"
        """
        result = template

        # {{input}} 치환
        result = result.replace("{{input}}", initial_input)

        # {{node_<id>}} 치환
        for nid, output in node_outputs.items():
            result = result.replace(f"{{{{node_{nid}}}}}", output)

        # {{parent}} 치환 - node_inputs 우선, 없으면 node_outputs 사용
        if "{{parent}}" in result:
            # 1. node_inputs에 현재 노드의 입력이 있으면 사용 (피드백 루프)
            if node_id in node_inputs:
                parent_output = node_inputs[node_id]
                logger.info(
                    f"노드 {node_id}: node_inputs에서 부모 출력 사용 "
                    f"(피드백 루프, 길이: {len(parent_output)}자)"
                )
                result = result.replace("{{parent}}", parent_output)
            else:
                # 2. node_outputs 사용 (기존 로직)
                parent_node_ids = list(node_outputs.keys())
                if len(parent_node_ids) == 1:
                    # 부모가 1개인 경우, 해당 노드의 출력 사용
                    result = result.replace("{{parent}}", node_outputs[parent_node_ids[0]])
                elif len(parent_node_ids) == 0:
                    # 부모가 없으면 빈 문자열로 치환
                    result = result.replace("{{parent}}", "")
                else:
                    # 부모가 여러 개인 경우, 경고 로그 및 첫 번째 부모 출력 사용
                    logger.warning(
                        f"노드 {node_id}에 부모가 {len(parent_node_ids)}개 있습니다. "
                        f"{{{{parent}}}} 변수는 부모가 1개인 경우만 지원합니다. "
                        f"첫 번째 부모의 출력을 사용합니다: {parent_node_ids[0]}"
                    )
                    result = result.replace("{{parent}}", node_outputs[parent_node_ids[0]])

        return result
