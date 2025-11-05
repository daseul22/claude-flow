#!/usr/bin/env python3
"""
동적 실행 엔진 테스트

기존 세션의 조건 분기 워크플로우를 사용하여 테스트합니다.
예상 동작:
- Input: 1
- Worker-1: 1 → 2 (add 1)
- Condition: 2 < 10 → False → worker-1로 분기 (피드백 루프)
- Worker-1: 2 → 3
- ... (반복)
- Worker-1: 9 → 10
- Condition: 10 >= 10 → True → worker-2로 분기
- Worker-2: 최종 메시지 출력
"""

import asyncio
import json
from pathlib import Path
from src.presentation.web.schemas.workflow import Workflow
from src.presentation.web.services.workflow_executor import WorkflowExecutor
from src.infrastructure.config import JsonConfigLoader
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)


async def test_condition_branching():
    """조건 분기 워크플로우 테스트"""

    # 세션 파일 로드
    session_path = Path.home() / ".claude-flow/web-sessions/831004db-4720-42aa-964b-5a374e2993f8.json"

    if not session_path.exists():
        print(f"❌ 세션 파일이 없습니다: {session_path}")
        return

    with open(session_path, "r", encoding="utf-8") as f:
        session_data = json.load(f)

    # 워크플로우 파싱
    workflow_dict = session_data["workflow"]
    workflow = Workflow(**workflow_dict)

    print("=" * 80)
    print("📋 워크플로우 테스트 시작")
    print("=" * 80)
    print(f"워크플로우: {workflow.name}")
    print(f"노드 수: {len(workflow.nodes)}")
    print(f"엣지 수: {len(workflow.edges)}")
    print(f"초기 입력: {session_data['initial_input']}")
    print()

    # 워크플로우 실행
    project_root = Path(__file__).parent  # claude-flow-web 디렉토리
    config_loader = JsonConfigLoader(project_root=project_root)
    executor = WorkflowExecutor(config_loader=config_loader, project_path=None)

    executed_nodes = []
    node_outputs = {}

    print("🚀 실행 시작...")
    print("-" * 80)

    try:
        async for event in executor.execute_workflow(
            workflow=workflow,
            initial_input=session_data["initial_input"],
            session_id="test-dynamic-execution",
            project_path=None
        ):
            event_type = event.event_type
            node_id = event.node_id

            if event_type == "node_start":
                agent_name = event.data.get("agent_name", node_id)
                print(f"\n▶️  [{agent_name}] 시작: {node_id}")
                executed_nodes.append(node_id)

            elif event_type == "node_output":
                chunk = event.data.get("chunk", "")
                chunk_type = event.data.get("chunk_type", "text")
                if chunk_type == "input":
                    print(f"  📥 입력: {chunk[:100]}")
                else:
                    print(f"  📤 출력: {chunk[:100]}")

            elif event_type == "node_complete":
                agent_name = event.data.get("agent_name", node_id)
                elapsed = event.elapsed_time or 0
                print(f"✅ [{agent_name}] 완료: {node_id} ({elapsed:.1f}s)")

                # Condition 노드인 경우 분기 정보 출력
                if "next_node" in event.data:
                    next_node = event.data["next_node"]
                    evaluation = event.data.get("evaluation_result", "")
                    print(f"  🔀 분기: {next_node}")
                    print(f"  📊 평가: {evaluation[:150]}")

            elif event_type == "workflow_complete":
                print("\n" + "=" * 80)
                print("✅ 워크플로우 완료")
                print("=" * 80)
                break

            elif event_type == "node_error":
                error = event.data.get("error", "Unknown error")
                print(f"❌ 에러: {node_id} - {error}")
                break

    except Exception as e:
        print(f"\n❌ 실행 중 예외 발생: {e}")
        import traceback
        traceback.print_exc()
        return False

    # 실행 결과 분석
    print("\n📊 실행 결과 분석")
    print("-" * 80)
    print(f"실행된 노드 순서: {' → '.join(executed_nodes)}")
    print(f"총 실행 노드 수: {len(executed_nodes)}")

    # 예상 동작 검증
    print("\n🔍 검증")
    print("-" * 80)

    # 1. Worker-1이 여러 번 실행되었는지 (피드백 루프)
    worker_1_count = executed_nodes.count("worker-1")
    print(f"1. Worker-1 실행 횟수: {worker_1_count}")
    if worker_1_count > 1:
        print("   ✅ 피드백 루프가 작동함 (worker-1이 여러 번 실행됨)")
    else:
        print("   ❌ 피드백 루프 미작동 (worker-1이 한 번만 실행됨)")

    # 2. Condition이 여러 번 실행되었는지
    condition_1_count = executed_nodes.count("condition-1")
    print(f"2. Condition-1 실행 횟수: {condition_1_count}")
    if condition_1_count > 1:
        print("   ✅ 조건 평가가 반복됨")
    else:
        print("   ❌ 조건 평가가 한 번만 실행됨")

    # 3. Worker-2가 마지막에 실행되었는지
    if "worker-2" in executed_nodes:
        worker_2_index = executed_nodes.index("worker-2")
        if worker_2_index == len(executed_nodes) - 1:
            print(f"3. Worker-2 실행 위치: 마지막")
            print("   ✅ True 분기가 올바르게 작동함 (10 이상일 때만 worker-2 실행)")
        else:
            print(f"3. Worker-2 실행 위치: {worker_2_index + 1}번째")
            print("   ❌ Worker-2가 중간에 실행됨 (잘못된 분기)")
    else:
        print("3. Worker-2 실행 안됨")
        print("   ❌ True 분기가 작동하지 않음")

    # 4. 실행 순서 패턴 검증
    expected_pattern = ["input-1"]
    # worker-1 → condition-1을 여러 번 반복 후 worker-2로 종료
    is_valid_pattern = True
    for i, node_id in enumerate(executed_nodes[1:], 1):  # input-1 다음부터
        if node_id == "worker-2":
            # worker-2는 마지막에만 등장해야 함
            if i != len(executed_nodes) - 1:
                is_valid_pattern = False
                print(f"   ❌ Worker-2가 {i}번째에 등장 (마지막이어야 함)")
        elif i < len(executed_nodes) - 1:  # 마지막이 아닌 경우
            # worker-1 → condition-1 패턴이어야 함
            if node_id == "worker-1":
                next_node = executed_nodes[i + 1] if i + 1 < len(executed_nodes) else None
                if next_node != "condition-1":
                    is_valid_pattern = False
                    print(f"   ❌ Worker-1 다음에 Condition-1이 와야 하는데 {next_node}가 옴")
            elif node_id == "condition-1":
                next_node = executed_nodes[i + 1] if i + 1 < len(executed_nodes) else None
                if next_node not in ["worker-1", "worker-2"]:
                    is_valid_pattern = False
                    print(f"   ❌ Condition-1 다음에 Worker-1 또는 Worker-2가 와야 하는데 {next_node}가 옴")

    if is_valid_pattern:
        print("4. 실행 순서 패턴: ✅ 올바름 (input → (worker-1 → condition-1)* → worker-2)")
    else:
        print("4. 실행 순서 패턴: ❌ 잘못됨")

    print("\n" + "=" * 80)

    # 최종 결과
    all_passed = (
        worker_1_count > 1 and
        condition_1_count > 1 and
        "worker-2" in executed_nodes and
        executed_nodes.index("worker-2") == len(executed_nodes) - 1 and
        is_valid_pattern
    )

    if all_passed:
        print("🎉 테스트 성공! 동적 실행 엔진이 올바르게 작동합니다.")
        return True
    else:
        print("❌ 테스트 실패. 일부 검증 항목이 실패했습니다.")
        return False


if __name__ == "__main__":
    result = asyncio.run(test_condition_branching())
    exit(0 if result else 1)
