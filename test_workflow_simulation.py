#!/usr/bin/env python3
"""
워크플로우 시뮬레이션 테스트

현재 저장된 워크플로우를 로드하여 구조를 검증합니다.
"""

import json
from pathlib import Path
from collections import defaultdict


def main():
    """메인 시뮬레이션 함수"""

    # 1. 워크플로우 로드
    workflow_path = Path("/Users/simdaseul/dallem-repo/claude-flow-web/.claude-flow/workflows/test.json")
    print(f"워크플로우 로드: {workflow_path}")

    with open(workflow_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    workflow_data = data["workflow"]
    nodes = workflow_data["nodes"]
    edges = workflow_data["edges"]

    print(f"\n✅ 워크플로우 로드 완료: {workflow_data['name']}")
    print(f"   노드 수: {len(nodes)}")
    print(f"   엣지 수: {len(edges)}")

    # 2. 노드 타입별 개수 확인
    node_types = defaultdict(int)
    for node in nodes:
        node_type = node["type"]
        node_types[node_type] += 1

    print("\n📊 노드 타입별 개수:")
    for node_type, count in node_types.items():
        print(f"   {node_type}: {count}개")

    # 3. 조건 노드 상세 확인
    print("\n🔀 조건 노드 검증:")
    for node in nodes:
        if node["type"] == "condition":
            node_data = node["data"]
            print(f"   노드: {node['id']}")
            print(f"     타입: {node_data['condition_type']}")
            print(f"     max_iterations: {node_data.get('max_iterations', 'None')}")

            # true/false 경로 확인
            true_edges = [e["target"] for e in edges if e["source"] == node["id"] and e.get("sourceHandle") == "true"]
            false_edges = [e["target"] for e in edges if e["source"] == node["id"] and e.get("sourceHandle") == "false"]

            print(f"     true 경로: {true_edges}")
            print(f"     false 경로: {false_edges}")

    # 4. 병렬 실행 노드 확인
    print("\n⚡ 병렬 실행 검증:")
    for edge in edges:
        if edge["source"] == "condition-2" and edge.get("sourceHandle") == "true":
            print(f"   Condition-2 → True 경로: {edge['target']}")

    # 5. 피드백 루프 확인
    print("\n🔄 피드백 루프 검증:")
    for edge in edges:
        if edge["source"] == "condition-2" and edge["target"] == "bug-fixer-1" and edge.get("sourceHandle") == "false":
            print(f"   발견: {edge['source']} → {edge['target']} (피드백 루프)")

    # 6. Merge 노드 확인
    print("\n🔗 Merge 노드 검증:")
    for node in nodes:
        if node["type"] == "merge":
            parents = [e["source"] for e in edges if e["target"] == node["id"]]
            print(f"   노드: {node['id']}")
            print(f"     병합 전략: {node['data']['merge_strategy']}")
            print(f"     부모 노드: {parents}")

    # 7. 실행 순서 예측
    print("\n📋 실행 순서 예측:")
    input_nodes = [n for n in nodes if n["type"] == "input"]
    if input_nodes:
        start_id = input_nodes[0]["id"]
        print(f"   1. {start_id} (Input)")

        # 첫 번째 자식 찾기
        next_nodes = [e["target"] for e in edges if e["source"] == start_id]
        if next_nodes:
            print(f"   2. {next_nodes[0]} (Worker)")

    print("\n✅ 워크플로우 구조 검증 완료!")
    print("\n⚠️  참고: 실제 실행은 Claude SDK 호출로 비용이 발생합니다.")
    print("   웹 UI에서 실행하여 로그/세션 저장을 테스트하세요.")
    print("\n🧪 테스트할 기능:")
    print("   - LLM 조건 평가 (Condition-1, Condition-2)")
    print("   - 피드백 루프 (Condition-2 → Bug Fixer)")
    print("   - 병렬 실행 (Security + Code Reviewer)")
    print("   - Merge 노드 (두 리뷰 병합)")
    print("   - 로그 저장 (~/.claude-flow/claude-flow-web/logs/)")
    print("   - 세션 저장 (~/.claude-flow/claude-flow-web/web-sessions/)")


if __name__ == "__main__":
    main()
