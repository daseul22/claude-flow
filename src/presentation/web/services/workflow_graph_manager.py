"""
워크플로우 그래프 관리자

워크플로우의 노드 그래프 구조를 관리하고, 실행 순서를 결정합니다.
"""

from typing import List, Dict, Set
from collections import deque

from src.presentation.web.schemas.workflow import WorkflowNode, WorkflowEdge
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)


class WorkflowGraphManager:
    """
    워크플로우 그래프 관리자

    워크플로우의 노드와 엣지를 분석하여 실행 순서를 결정하고,
    병렬 실행 그룹을 계산합니다.

    Attributes:
        nodes: 워크플로우 노드 목록
        edges: 워크플로우 엣지 목록
    """

    def __init__(self, nodes: List[WorkflowNode], edges: List[WorkflowEdge]):
        """
        WorkflowGraphManager 초기화

        Args:
            nodes: 워크플로우 노드 목록
            edges: 워크플로우 엣지 목록
        """
        self.nodes = nodes
        self.edges = edges
        self.node_map = {node.id: node for node in nodes}

    def get_parent_nodes(self, node_id: str) -> List[str]:
        """
        노드의 부모 노드 ID 목록 조회

        Args:
            node_id: 노드 ID

        Returns:
            List[str]: 부모 노드 ID 목록
        """
        return [edge.source for edge in self.edges if edge.target == node_id]

    def get_child_nodes(self, node_id: str) -> List[str]:
        """
        노드의 자식 노드 ID 목록 조회

        Args:
            node_id: 노드 ID

        Returns:
            List[str]: 자식 노드 ID 목록
        """
        return [edge.target for edge in self.edges if edge.source == node_id]

    def check_parallel_execution(self, node: WorkflowNode) -> bool:
        """
        노드의 parallel_execution 플래그 확인

        Args:
            node: 워크플로우 노드

        Returns:
            bool: 병렬 실행 여부
        """
        if isinstance(node.data, dict):
            return node.data.get("parallel_execution", False)
        else:
            return getattr(node.data, "parallel_execution", False)

    def topological_sort(self, start_node_id: str | None = None) -> List[WorkflowNode]:
        """
        워크플로우 노드 위상 정렬 (Topological Sort)

        Args:
            start_node_id: 시작 노드 ID (옵션, 지정 시 해당 Input 노드만 시작점으로 사용)

        Returns:
            List[WorkflowNode]: 실행 순서대로 정렬된 노드 목록

        Raises:
            ValueError: 순환 참조가 있거나 Input 노드가 없는 경우
        """
        # 유효하지 않은 엣지 필터링 (존재하지 않는 노드를 참조하는 엣지 제거)
        valid_edges = []
        for edge in self.edges:
            if edge.source not in self.node_map:
                logger.warning(
                    f"엣지 {edge.id}: source 노드 '{edge.source}'가 존재하지 않습니다. " f"엣지를 무시합니다."
                )
                continue
            if edge.target not in self.node_map:
                logger.warning(
                    f"엣지 {edge.id}: target 노드 '{edge.target}'가 존재하지 않습니다. " f"엣지를 무시합니다."
                )
                continue
            valid_edges.append(edge)

        # Input 노드 찾기 (시작점)
        input_nodes = [node for node in self.nodes if node.type == "input"]
        if not input_nodes:
            raise ValueError("워크플로우에 Input 노드가 없습니다. Input 노드에서 시작해야 합니다.")

        # start_node_id가 지정된 경우 해당 노드만 시작점으로 사용
        if start_node_id:
            start_node = self.node_map.get(start_node_id)
            if not start_node:
                raise ValueError(f"지정된 시작 노드를 찾을 수 없습니다: {start_node_id}")
            if start_node.type != "input":
                raise ValueError(
                    f"시작 노드는 Input 노드여야 합니다: {start_node_id} " f"(타입: {start_node.type})"
                )
            input_node_ids = [start_node_id]
            logger.info(f"특정 Input 노드에서 시작: {start_node_id}")
        else:
            # start_node_id가 없으면 모든 Input 노드를 시작점으로 사용 (기존 동작)
            input_node_ids = [node.id for node in input_nodes]
            logger.info(f"모든 Input 노드에서 시작: {input_node_ids}")

        # Condition 노드의 max_iterations가 설정된 경우 피드백 루프 허용
        condition_nodes_with_iterations = self._identify_feedback_loop_nodes()

        # 백엣지 식별 (DFS로 순환 경로 파악)
        back_edges = self._identify_back_edges(
            input_node_ids, valid_edges, condition_nodes_with_iterations
        )

        # 인접 리스트 구축 (백엣지 제외)
        adjacency, in_degree = self._build_adjacency_list(valid_edges, back_edges)

        # Input 노드에서 도달 가능한 노드만 필터링 (BFS)
        reachable_nodes = self._find_reachable_nodes(input_node_ids, adjacency)

        # 도달 불가능한 노드 경고
        unreachable_nodes = [node.id for node in self.nodes if node.id not in reachable_nodes]
        if unreachable_nodes:
            logger.warning(
                f"Input 노드에서 도달할 수 없는 노드가 있습니다: {unreachable_nodes}. " "이 노드들은 실행되지 않습니다."
            )

        # 위상 정렬 수행
        sorted_nodes = self._perform_topological_sort(
            input_node_ids, reachable_nodes, valid_edges, back_edges
        )

        return sorted_nodes

    def compute_execution_groups(
        self, sorted_nodes: List[WorkflowNode]
    ) -> List[List[WorkflowNode]]:
        """
        병렬 실행 그룹 계산

        parallel_execution=True인 노드의 자식 노드들을 병렬 그룹으로 묶습니다.

        Args:
            sorted_nodes: 위상 정렬된 노드 목록

        Returns:
            List[List[WorkflowNode]]: 실행 그룹 목록 (각 그룹은 병렬 실행)
        """
        node_map = {node.id: node for node in sorted_nodes}
        processed = set()
        execution_groups = []

        for node in sorted_nodes:
            if node.id in processed:
                continue

            # parallel_execution 플래그 확인
            if self.check_parallel_execution(node):
                # 자식 노드들을 병렬 그룹으로 묶음
                child_ids = self.get_child_nodes(node.id)
                parallel_group = []

                for child_id in child_ids:
                    if child_id in node_map and child_id not in processed:
                        parallel_group.append(node_map[child_id])
                        processed.add(child_id)

                # 현재 노드는 단독 실행
                execution_groups.append([node])
                processed.add(node.id)

                # 자식 노드들은 병렬 실행
                if parallel_group:
                    execution_groups.append(parallel_group)
            else:
                # 단독 실행
                execution_groups.append([node])
                processed.add(node.id)

        return execution_groups

    # ========================================
    # Private Helper Methods
    # ========================================

    def _identify_feedback_loop_nodes(self) -> Set[str]:
        """
        피드백 루프 제어 노드 식별 (max_iterations가 설정된 Condition 노드)

        Returns:
            Set[str]: 피드백 루프 제어 노드 ID 집합
        """
        condition_nodes_with_iterations = set()

        for node in self.nodes:
            if node.type == "condition":
                max_iterations = None
                if hasattr(node.data, "max_iterations"):
                    max_iterations = node.data.max_iterations
                elif isinstance(node.data, dict):
                    max_iterations = node.data.get("max_iterations")

                if max_iterations is not None:
                    condition_nodes_with_iterations.add(node.id)
                    logger.info(f"Condition 노드 발견 (max_iterations={max_iterations}): {node.id}")
                else:
                    logger.debug(f"Condition 노드 발견 (max_iterations 없음): {node.id}")

        logger.info(
            f"피드백 루프 제어 노드 총 {len(condition_nodes_with_iterations)}개: "
            f"{condition_nodes_with_iterations}"
        )

        return condition_nodes_with_iterations

    def _identify_back_edges(
        self,
        input_node_ids: List[str],
        valid_edges: List[WorkflowEdge],
        condition_nodes_with_iterations: Set[str],
    ) -> Set[tuple[str, str]]:
        """
        백엣지 식별 (DFS로 순환 경로 파악)

        Args:
            input_node_ids: Input 노드 ID 목록
            valid_edges: 유효한 엣지 목록
            condition_nodes_with_iterations: 피드백 루프 제어 노드 집합

        Returns:
            Set[tuple[str, str]]: 백엣지 집합 (source, target)
        """
        back_edges = set()
        visited_dfs = set()
        rec_stack = set()

        def dfs(node_id: str, path: List[str]):
            """DFS로 백엣지 식별"""
            visited_dfs.add(node_id)
            rec_stack.add(node_id)
            path.append(node_id)

            for edge in valid_edges:
                if edge.source == node_id:
                    target = edge.target

                    # 이미 방문 스택에 있으면 백엣지 (순환)
                    if target in rec_stack:
                        logger.debug(f"🔄 백엣지 발견: {node_id} → {target}")

                        # 순환 경로 추출 (target부터 현재 노드까지)
                        try:
                            cycle_start_idx = path.index(target)
                            cycle_path = path[cycle_start_idx:] + [target]
                            logger.debug(f"   순환 경로: {' → '.join(cycle_path)}")
                        except ValueError:
                            logger.error(f"   ❌ 순환 경로 추출 실패: target={target}, path={path}")
                            continue

                        # 순환 경로에 max_iterations가 설정된 Condition 노드가 있는지 확인
                        has_condition_with_iterations = any(
                            node_id in condition_nodes_with_iterations for node_id in cycle_path
                        )
                        logger.debug(f"   Condition 노드 포함 여부: {has_condition_with_iterations}")

                        if has_condition_with_iterations:
                            # 피드백 루프 허용: 백엣지로 표시
                            back_edges.add((edge.source, edge.target))
                            logger.info(
                                f"✅ 피드백 루프 감지 (허용): {edge.source} → {edge.target} "
                                f"(순환 경로: {' → '.join(cycle_path)})"
                            )
                        else:
                            # max_iterations 없는 순환: 검증 단계에서 에러 발생
                            logger.warning(
                                f"⚠️ 무제한 순환 감지: {edge.source} → {edge.target} "
                                f"(순환 경로: {' → '.join(cycle_path)}). "
                                f"Condition 노드에 max_iterations를 설정하세요."
                            )
                    elif target not in visited_dfs:
                        dfs(target, path.copy())

            rec_stack.remove(node_id)

        # 모든 Input 노드에서 DFS 시작하여 백엣지 식별
        for input_id in input_node_ids:
            if input_id not in visited_dfs:
                dfs(input_id, [])

        logger.info(f"백엣지 식별 완료: 총 {len(back_edges)}개 발견")
        if back_edges:
            for source, target in back_edges:
                logger.info(f"  - {source} → {target}")
        else:
            logger.info("  (백엣지 없음)")

        return back_edges

    def _build_adjacency_list(
        self, valid_edges: List[WorkflowEdge], back_edges: Set[tuple[str, str]]
    ) -> tuple[Dict[str, List[str]], Dict[str, int]]:
        """
        인접 리스트 구축 (백엣지 제외)

        Args:
            valid_edges: 유효한 엣지 목록
            back_edges: 백엣지 집합

        Returns:
            tuple: (인접 리스트, 진입 차수 맵)
        """
        adjacency: Dict[str, List[str]] = {node.id: [] for node in self.nodes}
        in_degree: Dict[str, int] = {node.id: 0 for node in self.nodes}

        for edge in valid_edges:
            # 백엣지는 위상 정렬에서 제외 (피드백 루프)
            if (edge.source, edge.target) not in back_edges:
                adjacency[edge.source].append(edge.target)
                in_degree[edge.target] += 1
            else:
                logger.debug(f"백엣지 제외 (위상 정렬): {edge.source} → {edge.target}")

        # 디버깅: 인접 리스트 출력
        logger.debug("위상 정렬용 인접 리스트:")
        for node_id, children in adjacency.items():
            if children:
                logger.debug(f"  {node_id} → {children}")

        return adjacency, in_degree

    def _find_reachable_nodes(
        self, input_node_ids: List[str], adjacency: Dict[str, List[str]]
    ) -> Set[str]:
        """
        Input 노드에서 도달 가능한 노드 찾기 (BFS)

        Args:
            input_node_ids: Input 노드 ID 목록
            adjacency: 인접 리스트

        Returns:
            Set[str]: 도달 가능한 노드 ID 집합
        """
        reachable_nodes = set(input_node_ids)
        bfs_queue = deque(input_node_ids)

        while bfs_queue:
            current_id = bfs_queue.popleft()
            for child_id in adjacency[current_id]:
                if child_id not in reachable_nodes:
                    reachable_nodes.add(child_id)
                    bfs_queue.append(child_id)

        return reachable_nodes

    def _perform_topological_sort(
        self,
        input_node_ids: List[str],
        reachable_nodes: Set[str],
        valid_edges: List[WorkflowEdge],
        back_edges: Set[tuple[str, str]],
    ) -> List[WorkflowNode]:
        """
        위상 정렬 수행

        Args:
            input_node_ids: Input 노드 ID 목록
            reachable_nodes: 도달 가능한 노드 집합
            valid_edges: 유효한 엣지 목록
            back_edges: 백엣지 집합

        Returns:
            List[WorkflowNode]: 정렬된 노드 목록

        Raises:
            ValueError: 순환 참조가 있거나 교착 상태인 경우
        """
        # 인접 리스트 재구축 (정렬 실행용)
        adjacency, _ = self._build_adjacency_list(valid_edges, back_edges)

        queue = deque(input_node_ids)
        sorted_nodes = []
        visited = set()

        # 무한 루프 방지: 최대 반복 횟수
        max_iterations = len(reachable_nodes) * len(reachable_nodes)
        iteration_count = 0
        stuck_counter: Dict[str, int] = {}  # 각 노드가 큐에 추가된 횟수

        while queue:
            iteration_count += 1
            if iteration_count > max_iterations:
                stuck_nodes = [nid for nid, count in stuck_counter.items() if count > 5]
                raise ValueError(
                    f"위상 정렬 중 무한 루프 감지. 교착 상태 노드: {stuck_nodes}. "
                    f"Condition 노드 + max_iterations를 통한 피드백 루프가 아닌 "
                    f"실제 순환 참조가 있을 수 있습니다."
                )

            node_id = queue.popleft()

            if node_id in visited:
                continue

            # 도달 불가능한 노드는 건너뜀
            if node_id not in reachable_nodes:
                continue

            # 모든 부모 노드가 처리되었는지 확인 (백엣지 제외)
            parents_ready = True
            for edge in valid_edges:
                # 백엣지는 부모 의존성 체크에서 제외 (피드백 루프)
                if (edge.source, edge.target) in back_edges:
                    continue

                if edge.target == node_id and edge.source in reachable_nodes:
                    if edge.source not in visited:
                        parents_ready = False
                        break

            if not parents_ready:
                # 부모 노드가 아직 처리되지 않았으면 큐 뒤로
                stuck_counter[node_id] = stuck_counter.get(node_id, 0) + 1
                queue.append(node_id)
                continue

            visited.add(node_id)
            sorted_nodes.append(self.node_map[node_id])

            # 자식 노드를 큐에 추가
            for child_id in adjacency[node_id]:
                if child_id not in visited and child_id in reachable_nodes:
                    queue.append(child_id)

        # 순환 참조 검사 (도달 가능한 노드 기준)
        if len(sorted_nodes) != len(reachable_nodes):
            unvisited = [nid for nid in reachable_nodes if nid not in visited]
            raise ValueError(f"워크플로우에 순환 참조가 있습니다. 방문하지 못한 노드: {unvisited}")

        return sorted_nodes
