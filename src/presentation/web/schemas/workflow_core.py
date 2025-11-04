"""
워크플로우 핵심 스키마

Workflow, WorkflowNode, WorkflowEdge 등 핵심 데이터 구조를 정의합니다.
"""

from typing import List, Dict, Any, Optional, Union
from pydantic import BaseModel, Field

from .workflow_nodes import (
    WorkerNodeData,
    InputNodeData,
    ConditionNodeData,
    MergeNodeData,
)


class WorkflowNode(BaseModel):
    """
    워크플로우 노드 (React Flow 호환 형식)

    Attributes:
        id: 노드 고유 ID
        type: 노드 타입 (worker, input, condition, merge)
        position: 캔버스 상의 위치 {x, y}
        data: 노드 데이터 (WorkerNodeData, InputNodeData, ConditionNodeData, MergeNodeData)
    """

    id: str = Field(..., description="노드 고유 ID")
    type: str = Field(default="worker", description="노드 타입 (worker, input, condition, merge)")
    position: Dict[str, float] = Field(..., description="캔버스 상의 위치", example={"x": 100, "y": 100})
    data: Union[
        WorkerNodeData, InputNodeData, ConditionNodeData, MergeNodeData, Dict[str, Any]
    ] = Field(..., description="노드 데이터 (타입에 따라 다름)")


class WorkflowEdge(BaseModel):
    """
    워크플로우 엣지 (노드 간 연결)

    Attributes:
        id: 엣지 고유 ID
        source: 시작 노드 ID
        target: 종료 노드 ID
        sourceHandle: 시작 핸들 ID (옵션)
        targetHandle: 종료 핸들 ID (옵션)
    """

    id: str = Field(..., description="엣지 고유 ID")
    source: str = Field(..., description="시작 노드 ID")
    target: str = Field(..., description="종료 노드 ID")
    sourceHandle: Optional[str] = Field(default=None, description="시작 핸들 ID")
    targetHandle: Optional[str] = Field(default=None, description="종료 핸들 ID")


class Workflow(BaseModel):
    """
    워크플로우 정의 (전체)

    Attributes:
        id: 워크플로우 고유 ID
        name: 워크플로우 이름
        description: 워크플로우 설명
        nodes: 노드 목록
        edges: 엣지 목록
        metadata: 추가 메타데이터 (옵션)
    """

    id: Optional[str] = Field(default=None, description="워크플로우 고유 ID")
    name: str = Field(..., description="워크플로우 이름")
    description: Optional[str] = Field(default=None, description="워크플로우 설명")
    nodes: List[WorkflowNode] = Field(..., description="노드 목록")
    edges: List[WorkflowEdge] = Field(..., description="엣지 목록")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="추가 메타데이터")
