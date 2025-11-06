"""
여러 Input 노드 병렬 실행 테스트

테스트 시나리오:
- Input 노드 3개 (각각 다른 입력)
- 각 Input → Worker 노드 연결
- 워크플로우 실행 → 3개 Input이 병렬로 실행되는지 확인
"""

import asyncio
import sys
import os

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from presentation.web.schemas.workflow_schemas import (
    Workflow,
    WorkflowNode,
    WorkflowEdge,
    InputNodeData,
    WorkerNodeData,
)
from presentation.web.services.workflow_executor import WorkflowExecutor


async def test_parallel_inputs():
    """여러 Input 노드 병렬 실행 테스트"""

    # 워크플로우 정의
    workflow = Workflow(
        name="병렬 Input 테스트",
        nodes=[
            # Input 노드 3개
            WorkflowNode(
                id="input-1",
                type="input",
                position={"x": 100, "y": 100},
                data=InputNodeData(
                    label="Input 1",
                    input_text="첫 번째 입력"
                )
            ),
            WorkflowNode(
                id="input-2",
                type="input",
                position={"x": 100, "y": 200},
                data=InputNodeData(
                    label="Input 2",
                    input_text="두 번째 입력"
                )
            ),
            WorkflowNode(
                id="input-3",
                type="input",
                position={"x": 100, "y": 300},
                data=InputNodeData(
                    label="Input 3",
                    input_text="세 번째 입력"
                )
            ),
            # Worker 노드 3개 (Echo 역할 - 입력을 그대로 반환)
            WorkflowNode(
                id="worker-1",
                type="worker",
                position={"x": 400, "y": 100},
                data=WorkerNodeData(
                    label="Worker 1",
                    agent_name="local",
                    task_template="입력: {{input}}",
                    allowed_tools=[],
                    thinking=False
                )
            ),
            WorkflowNode(
                id="worker-2",
                type="worker",
                position={"x": 400, "y": 200},
                data=WorkerNodeData(
                    label="Worker 2",
                    agent_name="local",
                    task_template="입력: {{input}}",
                    allowed_tools=[],
                    thinking=False
                )
            ),
            WorkflowNode(
                id="worker-3",
                type="worker",
                position={"x": 400, "y": 300},
                data=WorkerNodeData(
                    label="Worker 3",
                    agent_name="local",
                    task_template="입력: {{input}}",
                    allowed_tools=[],
                    thinking=False
                )
            ),
        ],
        edges=[
            # Input → Worker 연결
            WorkflowEdge(id="e1", source="input-1", target="worker-1"),
            WorkflowEdge(id="e2", source="input-2", target="worker-2"),
            WorkflowEdge(id="e3", source="input-3", target="worker-3"),
        ]
    )

    # WorkflowExecutor 생성
    project_path = os.getcwd()
    executor = WorkflowExecutor(project_path=project_path)

    # 세션 ID 생성
    import uuid
    session_id = str(uuid.uuid4())

    print("=" * 60)
    print("여러 Input 노드 병렬 실행 테스트")
    print("=" * 60)
    print(f"워크플로우: {workflow.name}")
    print(f"Input 노드: 3개")
    print(f"Worker 노드: 3개")
    print(f"세션 ID: {session_id}")
    print("=" * 60)
    print()

    # 워크플로우 실행
    start_times = {}
    complete_times = {}

    try:
        async for event in executor.execute_workflow(
            workflow=workflow,
            initial_input="",
            session_id=session_id,
            project_path=project_path
        ):
            event_type = event.event_type
            node_id = event.node_id
            timestamp = event.timestamp

            if event_type == "node_start":
                start_times[node_id] = timestamp
                node_type = event.data.get("node_type", "unknown")
                label = event.data.get("label", node_id)
                print(f"[{timestamp}] ▶ 시작: {label} ({node_type})")

            elif event_type == "node_output":
                chunk = event.data.get("chunk", "")
                chunk_type = event.data.get("chunk_type", "text")
                if chunk and chunk_type == "text":
                    # 텍스트 출력만 표시 (너무 길면 생략)
                    display_chunk = chunk[:100] + "..." if len(chunk) > 100 else chunk
                    print(f"  📝 출력: {display_chunk}")

            elif event_type == "node_complete":
                complete_times[node_id] = timestamp
                output = event.data.get("output", "")
                display_output = output[:100] + "..." if len(output) > 100 else output
                print(f"[{timestamp}] ✅ 완료: {node_id}")
                print(f"  출력: {display_output}")
                print()

            elif event_type == "workflow_complete":
                print("=" * 60)
                print("✅ 워크플로우 실행 완료!")
                print("=" * 60)

            elif event_type == "workflow_error":
                error = event.data.get("error", "Unknown error")
                print(f"❌ 에러: {error}")

        # 실행 시간 분석
        print()
        print("=" * 60)
        print("실행 시간 분석")
        print("=" * 60)

        input_nodes = ["input-1", "input-2", "input-3"]
        input_start_times = [start_times.get(nid) for nid in input_nodes if nid in start_times]

        if len(input_start_times) == 3:
            # 모든 Input 노드가 실행되었는지 확인
            print(f"✅ Input 노드 3개 모두 실행됨")

            # 시작 시간이 거의 같은지 확인 (병렬 실행 증거)
            from datetime import datetime
            parsed_times = [datetime.fromisoformat(t) for t in input_start_times]
            time_diffs = [
                abs((parsed_times[1] - parsed_times[0]).total_seconds()),
                abs((parsed_times[2] - parsed_times[1]).total_seconds())
            ]
            max_diff = max(time_diffs)

            print(f"Input 노드 시작 시간 차이: {max_diff:.3f}초")

            if max_diff < 1.0:
                print("✅ 병렬 실행 확인됨 (시작 시간 차이 < 1초)")
            else:
                print("⚠️ 순차 실행 의심 (시작 시간 차이 >= 1초)")
        else:
            print(f"⚠️ 실행된 Input 노드: {len(input_start_times)}개 (예상: 3개)")

        print("=" * 60)

    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

    return True


if __name__ == "__main__":
    success = asyncio.run(test_parallel_inputs())
    sys.exit(0 if success else 1)
