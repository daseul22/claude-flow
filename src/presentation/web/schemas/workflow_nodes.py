"""
워크플로우 노드 데이터 스키마

각 노드 타입별 데이터 구조를 정의합니다.
"""

from typing import List, Dict, Any, Optional, Union
from pydantic import BaseModel, Field


class WorkerNodeData(BaseModel):
    """
    Worker 노드의 데이터 (개별 Worker Agent)

    Attributes:
        agent_name: Worker Agent 이름 (planner, coder, reviewer 등)
        task_template: 작업 설명 템플릿 ({{input}} 등의 변수 지원)
        allowed_tools: 사용 가능한 도구 목록 (옵션, 미지정 시 기본 설정 사용)
        thinking: Thinking 모드 활성화 여부 (ultrathink 프롬프트 추가, 옵션)
        parallel_execution: 자식 노드를 병렬로 실행할지 여부 (기본: false)
        config: 추가 설정 (옵션)
    """

    agent_name: str = Field(..., description="Worker Agent 이름")
    task_template: str = Field(..., description="작업 설명 템플릿 ({{input}}, {{node_id}} 등 변수 지원)")
    allowed_tools: Optional[List[str]] = Field(
        default=None, description="사용 가능한 도구 목록 (옵션, 미지정 시 agent_config.json의 기본값 사용)"
    )
    thinking: Optional[bool] = Field(
        default=None, description="Thinking 모드 활성화 여부 (ultrathink 프롬프트 추가, 옵션)"
    )
    parallel_execution: Optional[bool] = Field(
        default=False, description="자식 노드를 병렬로 실행할지 여부 (기본: false)"
    )
    config: Optional[Dict[str, Any]] = Field(default=None, description="추가 설정 (옵션)")


class InputNodeData(BaseModel):
    """
    Input 노드의 데이터 (워크플로우 시작점)

    Input 노드는 워크플로우의 시작점으로, 초기 입력을 저장하고
    연결된 노드로 전달합니다.

    Attributes:
        initial_input: 초기 입력 텍스트
        parallel_execution: 자식 노드를 병렬로 실행할지 여부 (기본: false)
    """

    initial_input: str = Field(..., description="워크플로우 초기 입력 텍스트")
    parallel_execution: Optional[bool] = Field(
        default=False, description="자식 노드를 병렬로 실행할지 여부 (기본: false)"
    )


class ConditionNodeData(BaseModel):
    """
    조건 분기 노드의 데이터

    조건 분기 노드는 이전 노드의 출력을 평가하여 True/False 경로로 분기합니다.
    반복 기능을 활성화하면 false 경로가 순환을 만들 때 최대 반복 횟수를 제한합니다.

    Attributes:
        condition_type: 조건 타입 ('contains', 'regex', 'length', 'custom', 'llm')
        condition_value: 조건 값 (예: 'success', '\\d{3}', '100', 'len(output) > 0')
        true_branch_id: True 경로 노드 ID
        false_branch_id: False 경로 노드 ID (옵션)
        max_iterations: 최대 반복 횟수 (옵션, 피드백 루프 제한용)
        parallel_execution: 자식 노드를 병렬로 실행할지 여부 (기본: false)
    """

    condition_type: str = Field(..., description="조건 타입 (contains, regex, length, custom, llm)")
    condition_value: str = Field(..., description="조건 값 (타입에 따라 다름)")
    true_branch_id: Optional[str] = Field(
        default=None, description="True 경로 노드 ID (동적으로 엣지로 관리될 수 있음)"
    )
    false_branch_id: Optional[str] = Field(
        default=None, description="False 경로 노드 ID (동적으로 엣지로 관리될 수 있음)"
    )
    max_iterations: Optional[int] = Field(
        default=None, description="최대 반복 횟수 (None이면 반복 안함, 피드백 루프에서 무한 반복 방지)"
    )
    parallel_execution: Optional[bool] = Field(
        default=False, description="자식 노드를 병렬로 실행할지 여부 (기본: false)"
    )


class MergeNodeData(BaseModel):
    """
    병합 노드의 데이터

    병합 노드는 여러 분기의 출력을 하나로 통합합니다.

    Attributes:
        merge_strategy: 병합 전략 ('concatenate', 'first', 'last', 'custom')
        separator: 결합 시 사용할 구분자 (concatenate 전략 시)
        custom_template: 커스텀 병합 템플릿 (옵션)
        parallel_execution: 자식 노드를 병렬로 실행할지 여부 (기본: false)
    """

    merge_strategy: str = Field(
        default="concatenate", description="병합 전략 (concatenate, first, last, custom)"
    )
    separator: str = Field(default="\n\n---\n\n", description="결합 시 사용할 구분자 (concatenate 전략 시)")
    custom_template: Optional[str] = Field(
        default=None, description="커스텀 병합 템플릿 ({{branch_1}}, {{branch_2}} 등)"
    )
    parallel_execution: Optional[bool] = Field(
        default=False, description="자식 노드를 병렬로 실행할지 여부 (기본: false)"
    )


# Union 타입으로 모든 노드 타입 포함
WorkflowNodeData = Union[WorkerNodeData, InputNodeData, ConditionNodeData, MergeNodeData]
