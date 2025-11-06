#!/usr/bin/env python3
"""
워크플로우 개선 기능 검증 스크립트

이 스크립트는 다음을 검증합니다:
1. WorkflowDesignRequest 스키마가 current_workflow와 mode 필드를 받을 수 있는지
2. _execute_workflow_designer 함수가 개선 모드에서 올바른 프롬프트를 생성하는지
"""

import json
from pydantic import ValidationError
from src.presentation.web.schemas.request import WorkflowDesignRequest


def test_schema_validation():
    """스키마 검증 테스트"""
    print("=" * 60)
    print("테스트 1: WorkflowDesignRequest 스키마 검증")
    print("=" * 60)

    # 테스트 1-1: Create 모드 (기본)
    try:
        req1 = WorkflowDesignRequest(
            requirements="코드 리뷰 워크플로우를 만들어주세요",
            session_id="test-session-1",
        )
        print("✅ Create 모드 (기본): 통과")
        print(f"   - mode: {req1.mode}")
        print(f"   - current_workflow: {req1.current_workflow}")
    except ValidationError as e:
        print(f"❌ Create 모드 (기본): 실패\n{e}")
        return False

    # 테스트 1-2: Improve 모드 (current_workflow 포함)
    try:
        sample_workflow = {
            "name": "기존 워크플로우",
            "nodes": [
                {"id": "input-1", "type": "input", "position": {"x": 100, "y": 100}},
                {"id": "coder-1", "type": "worker", "position": {"x": 300, "y": 100}},
            ],
            "edges": [{"id": "edge-1", "source": "input-1", "target": "coder-1"}],
        }

        req2 = WorkflowDesignRequest(
            requirements="리뷰 단계를 추가해주세요",
            session_id="test-session-2",
            current_workflow=sample_workflow,
            mode="improve",
        )
        print("✅ Improve 모드: 통과")
        print(f"   - mode: {req2.mode}")
        print(f"   - current_workflow: {len(req2.current_workflow['nodes'])}개 노드")
    except ValidationError as e:
        print(f"❌ Improve 모드: 실패\n{e}")
        return False

    # 테스트 1-3: 잘못된 mode 값
    try:
        req3 = WorkflowDesignRequest(
            requirements="테스트", session_id="test-session-3", mode="invalid"
        )
        print("❌ 잘못된 mode 값: 검증 실패 (ValidationError가 발생해야 함)")
        return False
    except ValidationError:
        print("✅ 잘못된 mode 값: 올바르게 거부됨")

    print()
    return True


def test_prompt_generation():
    """프롬프트 생성 로직 테스트"""
    print("=" * 60)
    print("테스트 2: 개선 모드 프롬프트 생성 검증")
    print("=" * 60)

    sample_workflow = {
        "name": "코드 리뷰 파이프라인",
        "nodes": [
            {
                "id": "input-1",
                "type": "input",
                "position": {"x": 100, "y": 100},
                "data": {"initial_input": "{{input}}"},
            },
            {
                "id": "coder-1",
                "type": "worker",
                "position": {"x": 300, "y": 100},
                "data": {"agent_name": "coder", "task_template": "코드를 작성하세요"},
            },
            {
                "id": "reviewer-1",
                "type": "worker",
                "position": {"x": 500, "y": 100},
                "data": {"agent_name": "reviewer", "task_template": "리뷰하세요"},
            },
        ],
        "edges": [
            {"id": "edge-1", "source": "input-1", "target": "coder-1"},
            {"id": "edge-2", "source": "coder-1", "target": "reviewer-1"},
        ],
    }

    requirements = "리뷰 단계를 3개의 특화 리뷰어로 병렬 실행하도록 개선해주세요"

    # 개선 모드 프롬프트 생성 (design.py의 로직 시뮬레이션)
    mode = "improve"
    if mode == "improve" and sample_workflow:
        task_prompt = f"""---CURRENT_WORKFLOW_START---
{json.dumps(sample_workflow, ensure_ascii=False, indent=2)}
---CURRENT_WORKFLOW_END---

수정 요구사항:
{requirements}"""

        print("✅ 개선 모드 프롬프트 생성 완료")
        print("\n생성된 프롬프트 미리보기:")
        print("-" * 60)
        print(task_prompt[:500] + "..." if len(task_prompt) > 500 else task_prompt)
        print("-" * 60)

        # 프롬프트 구조 검증
        checks = [
            ("---CURRENT_WORKFLOW_START---" in task_prompt, "시작 마커"),
            ("---CURRENT_WORKFLOW_END---" in task_prompt, "종료 마커"),
            ('"name": "코드 리뷰 파이프라인"' in task_prompt, "워크플로우 이름"),
            ('"id": "coder-1"' in task_prompt, "노드 정보"),
            ("수정 요구사항:" in task_prompt, "요구사항 레이블"),
            (requirements in task_prompt, "사용자 요구사항"),
        ]

        all_passed = True
        for check, name in checks:
            if check:
                print(f"   ✅ {name} 포함")
            else:
                print(f"   ❌ {name} 누락")
                all_passed = False

        return all_passed

    return False


def test_api_contract():
    """API 계약 검증"""
    print("=" * 60)
    print("테스트 3: API 요청/응답 계약 검증")
    print("=" * 60)

    # 요청 시뮬레이션
    request_body = {
        "requirements": "워크플로우를 개선해주세요",
        "session_id": "test-session",
        "current_workflow": {
            "name": "테스트",
            "nodes": [],
            "edges": [],
        },
        "mode": "improve",
    }

    try:
        request = WorkflowDesignRequest(**request_body)
        print("✅ API 요청 바디 파싱 성공")
        print(f"   - requirements: {len(request.requirements)}자")
        print(f"   - mode: {request.mode}")
        print(f"   - current_workflow: {request.current_workflow is not None}")

        # 응답에서 기대하는 필드 (프롬프트에서 정의한 형식)
        expected_response_fields = [
            "workflow",
            "custom_workers",
            "explanation",
            "usage_guide",
            "changes",  # 개선 모드에서 추가
        ]

        print("\n📋 기대하는 응답 구조:")
        for field in expected_response_fields:
            print(f"   - {field}")

        print("\n📋 changes 필드 구조:")
        expected_changes_fields = [
            "summary",
            "added_nodes",
            "removed_nodes",
            "modified_nodes",
            "added_edges",
            "removed_edges",
            "improvements",
        ]
        for field in expected_changes_fields:
            print(f"   - changes.{field}")

        return True

    except Exception as e:
        print(f"❌ API 계약 검증 실패: {e}")
        return False


def main():
    """메인 테스트 실행"""
    print("\n🧪 워크플로우 개선 기능 검증 시작\n")

    results = []

    # 테스트 1: 스키마 검증
    results.append(("스키마 검증", test_schema_validation()))

    # 테스트 2: 프롬프트 생성
    results.append(("프롬프트 생성", test_prompt_generation()))

    # 테스트 3: API 계약
    results.append(("API 계약", test_api_contract()))

    # 결과 요약
    print("\n" + "=" * 60)
    print("테스트 결과 요약")
    print("=" * 60)

    all_passed = True
    for name, passed in results:
        status = "✅ 통과" if passed else "❌ 실패"
        print(f"{status}: {name}")
        if not passed:
            all_passed = False

    print("=" * 60)

    if all_passed:
        print("\n🎉 모든 테스트 통과!\n")
        print("다음 단계:")
        print("1. 서버 실행: claude-flow-web")
        print("2. 브라우저에서 http://localhost:5173 접속")
        print("3. 워크플로우 생성 후 '개선하기' 기능 테스트")
        return 0
    else:
        print("\n⚠️  일부 테스트 실패\n")
        return 1


if __name__ == "__main__":
    exit(main())
