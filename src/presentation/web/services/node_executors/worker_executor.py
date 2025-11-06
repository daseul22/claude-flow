"""
Worker 노드 실행기

Worker 노드 실행 및 추가 프롬프트 로직을 담당합니다.
"""

import asyncio
import time
from dataclasses import replace
from datetime import datetime
from typing import Dict, Any, AsyncIterator, List, Optional

from src.infrastructure.claude.worker_client import WorkerAgent
from src.infrastructure.logging import get_logger
from src.presentation.web.schemas.workflow import (
    WorkflowNode,
    WorkflowEdge,
    WorkflowNodeExecutionEvent,
    WorkerNodeData,
    TokenUsage,
)
from src.presentation.web.schemas.workflow_nodes import OutputExtractionConfig
from src.presentation.web.services.workflow_utils import (
    extract_text_from_worker_output,
    extract_text_with_strategy,
    classify_chunk_type,
)
from .base import BaseNodeExecutor

logger = get_logger(__name__)


class WorkerNodeExecutor(BaseNodeExecutor):
    """Worker 노드 실행기"""

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
        executed_nodes: set[str] | None = None,
    ) -> AsyncIterator[WorkflowNodeExecutionEvent]:
        """
        Worker 노드 실행

        Args:
            node: 실행할 노드
            node_outputs: 이전 노드 출력들
            node_inputs: 각 노드가 실제로 받을 입력 (피드백 루프 지원)
            initial_input: 초기 입력
            session_id: 세션 ID
            edges: 엣지 목록
            all_nodes: 모든 노드 목록
            condition_evaluator: 조건 평가기 (사용 안 함)
            template_renderer: 템플릿 렌더러
            executed_nodes: 실행 완료된 노드 집합 (사용 안 함)

        Yields:
            WorkflowNodeExecutionEvent: 노드 실행 이벤트
        """
        node_id = node.id
        start_time = time.time()

        # 1. 노드 데이터 파싱
        (
            agent_name,
            task_template,
            allowed_tools_override,
            thinking_override,
            output_extraction,
        ) = self._parse_worker_node_data(node, session_id)

        # 2. Agent 설정 준비 (오버라이드 적용)
        agent_config = self._prepare_worker_agent_config(
            agent_name, allowed_tools_override, thinking_override, node_id, session_id
        )

        # 3. 작업 템플릿 렌더링 (node_inputs 전달)
        task_description = self._render_worker_task(
            task_template, node_id, node_outputs, node_inputs, initial_input, edges, template_renderer
        )

        # node_start 이벤트
        start_event = WorkflowNodeExecutionEvent(
            event_type="node_start",
            node_id=node_id,
            data={"agent_name": agent_name},
            timestamp=datetime.now().isoformat(),
        )
        logger.info(
            f"[{session_id}] 🟢 이벤트 생성: node_start (node: {node_id}, agent: {agent_name})"
        )
        yield start_event

        # 입력 이벤트
        input_event = WorkflowNodeExecutionEvent(
            event_type="node_output",
            node_id=node_id,
            data={"chunk": task_description, "chunk_type": "input"},
        )
        logger.debug(f"[{session_id}] 📥 이벤트 생성: node_input (node: {node_id})")
        yield input_event

        try:
            logger.info(
                f"[{session_id}] 노드 실행: {node_id} ({agent_name}) "
                f"- 작업 길이: {len(task_description)}"
            )

            # 노드별 세션 관리
            previous_session_id = self.node_sessions.get(node_id)
            if previous_session_id:
                logger.info(
                    f"[{session_id}] 노드 {node_id}: 이전 세션 재개 "
                    f"(세션: {previous_session_id[:8]}...)"
                )
            else:
                logger.info(f"[{session_id}] 노드 {node_id}: 새 세션 시작")

            worker = WorkerAgent(config=agent_config, project_dir=self.project_path)
            node_output_chunks = []
            node_token_usage: Optional[TokenUsage] = None

            def usage_callback(usage_info: Dict[str, Any]):
                nonlocal node_token_usage
                node_token_usage = TokenUsage(
                    input_tokens=usage_info.get("input_tokens", 0),
                    output_tokens=usage_info.get("output_tokens", 0),
                    total_tokens=usage_info.get("total_tokens", 0),
                )
                logger.debug(
                    f"[{session_id}] 💰 토큰 사용량: {node_token_usage.total_tokens} "
                    f"(입력: {node_token_usage.input_tokens}, 출력: {node_token_usage.output_tokens})"
                )

            # 사용자 입력 콜백
            async def user_input_callback_impl(question: str) -> str:
                logger.info(f"[{session_id}] 💬 사용자 입력 대기: {question[:100]}...")
                user_queue = self.user_input_queues.get(session_id)
                if not user_queue:
                    logger.error(f"[{session_id}] 사용자 입력 Queue를 찾을 수 없음")
                    raise ValueError(f"세션 {session_id}의 사용자 입력 Queue를 찾을 수 없습니다")
                answer = await user_queue.get()
                logger.info(f"[{session_id}] ✅ 사용자 답변 수신: {answer[:100]}...")
                return answer

            # SDK 세션 ID 콜백 (ResultMessage에서 추출 시 호출됨)
            session_event_sent = [False]  # 이벤트 전송 플래그 (중복 방지)

            def session_id_callback_impl(sdk_session_id: str) -> None:
                """SDK 세션 ID 저장 및 이벤트 전송 (ResultMessage 수신 시)"""
                logger.info(
                    f"[{session_id}] ⚡ SDK 세션 ID 획득: {sdk_session_id[:8]}... "
                    f"(노드 {node_id}, ResultMessage에서 추출)"
                )
                # 세션 저장
                self._save_worker_node_session(node_id, agent_name, sdk_session_id, session_id)
                # 이벤트 전송 플래그 설정 (다음 청크에서 전송)
                session_event_sent[0] = False

            # Worker 실행
            async for chunk in worker.execute_task(
                task_description,
                usage_callback=usage_callback,
                resume_session_id=previous_session_id,
                user_input_callback=user_input_callback_impl,
                session_id_callback=session_id_callback_impl,
            ):
                # 취소 플래그 체크
                self._check_cancellation(session_id)

                # 새 세션 생성 시 프론트엔드로 이벤트 전송 (최초 1회)
                if not session_event_sent[0] and not previous_session_id:
                    current_sdk_session = self.node_sessions.get(node_id)
                    if current_sdk_session:
                        session_event = WorkflowNodeExecutionEvent(
                            event_type="node_session_created",
                            node_id=node_id,
                            data={
                                "session_id": current_sdk_session,
                                "agent_name": agent_name,
                                "created_at": datetime.now().isoformat(),
                            },
                        )
                        logger.info(
                            f"[{session_id}] 📡 이벤트 전송: node_session_created "
                            f"(node: {node_id}, sdk_session: {current_sdk_session[:8]}...)"
                        )
                        yield session_event
                        session_event_sent[0] = True

                # 특수 이벤트 마커 감지
                if chunk.startswith("@EVENT:user_input_request:"):
                    import json

                    json_str = chunk[len("@EVENT:user_input_request:") :]
                    event_data = json.loads(json_str)
                    question = event_data.get("question", "")

                    user_input_event = WorkflowNodeExecutionEvent(
                        event_type="user_input_request",
                        node_id=node_id,
                        data={"question": question, "session_id": session_id},
                    )
                    logger.info(
                        f"[{session_id}] 💬 이벤트 생성: user_input_request (node: {node_id})"
                    )
                    yield user_input_event
                    continue

                node_output_chunks.append(chunk)

                # 청크 타입 분류
                chunk_type = classify_chunk_type(chunk)

                output_event = WorkflowNodeExecutionEvent(
                    event_type="node_output",
                    node_id=node_id,
                    data={"chunk": chunk, "chunk_type": chunk_type},
                )
                logger.debug(
                    f"[{session_id}] 📝 이벤트 생성: node_output (node: {node_id}, "
                    f"type: {chunk_type}, chunk: {len(chunk)}자)"
                )
                yield output_event

            # 최종 텍스트 추출 (출력 추출 전략 적용)
            full_output = "".join(node_output_chunks)
            final_text = extract_text_with_strategy(full_output, output_extraction)
            node_outputs[node_id] = final_text

            # 출력 추출 전략 로깅
            if output_extraction:
                logger.info(
                    f"[{session_id}] 노드 출력 처리 완료: {node_id} "
                    f"(전체: {len(full_output)}자, 최종 텍스트: {len(final_text)}자, "
                    f"추출 전략: {output_extraction.strategy})"
                )
            else:
                logger.info(
                    f"[{session_id}] 노드 출력 처리 완료: {node_id} "
                    f"(전체: {len(full_output)}자, 최종 텍스트: {len(final_text)}자)"
                )

            # SDK 세션 ID 저장
            if worker.last_session_id:
                self._save_worker_node_session(
                    node_id, agent_name, worker.last_session_id, session_id
                )
            else:
                logger.warning(
                    f"[{session_id}] ⚠️  노드 {node_id}: SDK 세션 ID를 받지 못함. "
                    f"추가 프롬프트 기능을 사용할 수 없습니다."
                )

            elapsed_time = time.time() - start_time

            complete_event = WorkflowNodeExecutionEvent(
                event_type="node_complete",
                node_id=node_id,
                data={"agent_name": agent_name, "output_length": len(final_text)},
                timestamp=datetime.now().isoformat(),
                elapsed_time=elapsed_time,
                token_usage=node_token_usage,
            )
            logger.info(
                f"[{session_id}] ✅ 이벤트 생성: node_complete (node: {node_id}, agent: {agent_name})"
            )
            yield complete_event

            logger.info(
                f"[{session_id}] 노드 완료: {node_id} ({agent_name}) - 출력 길이: {len(final_text)}"
            )

        except Exception as e:
            error_msg = f"노드 실행 실패: {str(e)}"
            logger.error(f"[{session_id}] {node_id}: {error_msg}", exc_info=True)

            elapsed_time = time.time() - start_time

            error_event = WorkflowNodeExecutionEvent(
                event_type="node_error",
                node_id=node_id,
                data={"error": error_msg},
                timestamp=datetime.now().isoformat(),
                elapsed_time=elapsed_time,
            )
            logger.error(f"[{session_id}] 🔴 이벤트 생성: node_error (node: {node_id})")
            yield error_event

            raise

    async def execute_continue(
        self,
        node_id: str,
        additional_prompt: str,
    ) -> AsyncIterator[WorkflowNodeExecutionEvent]:
        """
        Worker 노드에 추가 프롬프트를 전송하여 대화 계속

        Args:
            node_id: 실행할 노드 ID
            additional_prompt: 추가 프롬프트

        Yields:
            WorkflowNodeExecutionEvent: 노드 실행 이벤트

        Raises:
            ValueError: 노드를 찾을 수 없거나 이전 세션이 없는 경우
        """
        logger.info(
            f"[DEBUG] 추가 대화 요청: node_id={node_id}\n"
            f"[DEBUG] 저장된 노드 세션 목록: {list(self.node_sessions.keys())}\n"
            f"[DEBUG] 저장된 agent_name 목록: {list(self.node_agent_names.keys())}"
        )

        # 노드의 이전 세션 ID 확인
        previous_session_id = self.node_sessions.get(node_id)
        if not previous_session_id:
            available_nodes = ", ".join(self.node_sessions.keys()) if self.node_sessions else "(없음)"
            raise ValueError(
                f"노드 {node_id}의 이전 세션을 찾을 수 없습니다.\n"
                f"사용 가능한 노드: {available_nodes}\n"
                f"먼저 워크플로우를 실행해주세요."
            )

        # 노드의 agent_name 확인
        agent_name = self.node_agent_names.get(node_id)
        if not agent_name:
            available_agents = (
                ", ".join(self.node_agent_names.keys()) if self.node_agent_names else "(없음)"
            )
            raise ValueError(
                f"노드 {node_id}의 Agent 정보를 찾을 수 없습니다.\n"
                f"사용 가능한 노드: {available_agents}"
            )

        logger.info(
            f"노드 {node_id} 추가 대화 시작: {agent_name} (이전 세션: {previous_session_id[:8]}...)"
        )

        # Agent 설정 조회
        agent_config = self._get_agent_config(agent_name)

        # node_start 이벤트
        yield WorkflowNodeExecutionEvent(
            event_type="node_start",
            node_id=node_id,
            data={"additional_prompt": True, "agent_name": agent_name},
            timestamp=datetime.now().isoformat(),
        )

        # Worker 실행
        try:
            worker = WorkerAgent(config=agent_config, project_dir=self.project_path)
            node_output_chunks = []
            node_token_usage: Optional[TokenUsage] = None

            def usage_callback(usage_info: Dict[str, Any]):
                nonlocal node_token_usage
                node_token_usage = TokenUsage(
                    input_tokens=usage_info.get("input_tokens", 0),
                    output_tokens=usage_info.get("output_tokens", 0),
                    total_tokens=usage_info.get("total_tokens", 0),
                )
                logger.debug(
                    f"💰 토큰 사용량: {node_token_usage.total_tokens} "
                    f"(입력: {node_token_usage.input_tokens}, 출력: {node_token_usage.output_tokens})"
                )

            # SDK 세션 ID 콜백 (추가 프롬프트 실행 시에도 즉시 저장)
            def session_id_callback_impl(sdk_session_id: str) -> None:
                logger.info(
                    f"⚡ SDK 세션 ID 조기 획득 (추가 프롬프트): {sdk_session_id[:8]}... "
                    f"(노드 {node_id})"
                )
                # 즉시 업데이트 (메모리)
                self.node_sessions[node_id] = sdk_session_id

                # 디스크 동기화 (콜백 호출)
                if self.on_node_session_update:
                    self.on_node_session_update(node_id, sdk_session_id)

                if node_id in self.node_session_history:
                    existing_session = next(
                        (
                            s
                            for s in self.node_session_history[node_id]
                            if s["session_id"] == sdk_session_id
                        ),
                        None,
                    )
                    if existing_session:
                        existing_session["last_used_at"] = datetime.now().isoformat()

            async for chunk in worker.execute_task(
                additional_prompt,
                usage_callback=usage_callback,
                resume_session_id=previous_session_id,
                user_input_callback=None,
                session_id_callback=session_id_callback_impl,
            ):
                node_output_chunks.append(chunk)

                chunk_type = classify_chunk_type(chunk)

                output_event = WorkflowNodeExecutionEvent(
                    event_type="node_output",
                    node_id=node_id,
                    data={"chunk": chunk, "chunk_type": chunk_type},
                )
                logger.debug(f"📝 이벤트 생성: node_output (node: {node_id}, type: {chunk_type})")
                yield output_event

            # 최종 텍스트 추출 (추가 프롬프트 실행 시에는 기본 전략 사용)
            full_output = "".join(node_output_chunks)
            final_text = extract_text_with_strategy(full_output, extraction_config=None)

            logger.info(
                f"노드 출력 처리 완료: {node_id} "
                f"(전체: {len(full_output)}자, 최종 텍스트: {len(final_text)}자)"
            )

            # SDK 세션 ID 업데이트
            if worker.last_session_id:
                # 메모리 업데이트
                self.node_sessions[node_id] = worker.last_session_id

                # 디스크 동기화 (콜백 호출)
                if self.on_node_session_update:
                    self.on_node_session_update(node_id, worker.last_session_id)

                if node_id in self.node_session_history:
                    existing_session = next(
                        (
                            s
                            for s in self.node_session_history[node_id]
                            if s["session_id"] == worker.last_session_id
                        ),
                        None,
                    )
                    if existing_session:
                        existing_session["last_used_at"] = datetime.now().isoformat()

                logger.info(f"노드 세션 업데이트: {node_id} → SDK 세션 {worker.last_session_id[:8]}...")

            # node_complete 이벤트
            complete_event = WorkflowNodeExecutionEvent(
                event_type="node_complete",
                node_id=node_id,
                data={"agent_name": agent_name, "output_length": len(final_text)},
                timestamp=datetime.now().isoformat(),
                token_usage=node_token_usage,
            )
            logger.info(f"✅ 이벤트 생성: node_complete (node: {node_id}, agent: {agent_name})")
            yield complete_event

            logger.info(f"노드 추가 대화 완료: {node_id} ({agent_name}) - 출력 길이: {len(final_text)}")

        except Exception as e:
            logger.error(f"노드 {node_id} 추가 대화 실패: {e}", exc_info=True)
            yield WorkflowNodeExecutionEvent(
                event_type="node_error",
                node_id=node_id,
                data={"error": str(e)},
                timestamp=datetime.now().isoformat(),
            )

    # ========================================================================
    # 헬퍼 메서드
    # ========================================================================

    def _parse_worker_node_data(
        self, node: WorkflowNode, session_id: str
    ) -> tuple[str, str, Optional[List[str]], Optional[str], Optional[OutputExtractionConfig]]:
        """
        Worker 노드 데이터 파싱

        Args:
            node: 워크플로우 노드
            session_id: 세션 ID

        Returns:
            tuple: (agent_name, task_template, allowed_tools_override, thinking_override, output_extraction)

        Raises:
            ValueError: 필수 필드가 누락된 경우
        """
        node_id = node.id

        if isinstance(node.data, dict):
            agent_name = node.data.get("agent_name")
            task_template = node.data.get("task_template")
            allowed_tools_override = node.data.get("allowed_tools")
            thinking_override = node.data.get("thinking")
            output_extraction_dict = node.data.get("output_extraction")

            # dict를 OutputExtractionConfig로 변환 (옵션)
            output_extraction = None
            if output_extraction_dict:
                output_extraction = OutputExtractionConfig(**output_extraction_dict)

            if not agent_name:
                raise ValueError(f"노드 {node_id}: agent_name이 지정되지 않았습니다")
            if not task_template:
                raise ValueError(f"노드 {node_id}: task_template이 지정되지 않았습니다")
        else:
            node_data: WorkerNodeData = node.data
            agent_name = node_data.agent_name
            task_template = node_data.task_template
            allowed_tools_override = node_data.allowed_tools
            thinking_override = node_data.thinking
            output_extraction = node_data.output_extraction

        return agent_name, task_template, allowed_tools_override, thinking_override, output_extraction

    def _prepare_worker_agent_config(
        self,
        agent_name: str,
        allowed_tools_override: Optional[List[str]],
        thinking_override: Optional[str],
        node_id: str,
        session_id: str,
    ):
        """
        Worker Agent 설정 준비

        Args:
            agent_name: Agent 이름
            allowed_tools_override: 도구 오버라이드
            thinking_override: Thinking 모드 오버라이드
            node_id: 노드 ID
            session_id: 세션 ID

        Returns:
            AgentConfig: 준비된 Agent 설정
        """
        agent_config = self._get_agent_config(agent_name)

        if allowed_tools_override is not None:
            agent_config = replace(agent_config, allowed_tools=allowed_tools_override)
            logger.info(
                f"[{session_id}] 노드 {node_id}: allowed_tools 오버라이드 "
                f"({len(allowed_tools_override)}개 도구)"
            )

        if thinking_override is not None:
            agent_config = replace(agent_config, thinking=thinking_override)
            logger.info(
                f"[{session_id}] 노드 {node_id}: thinking 모드 오버라이드 "
                f"(thinking={thinking_override})"
            )

        return agent_config

    def _render_worker_task(
        self,
        task_template: str,
        node_id: str,
        node_outputs: Dict[str, str],
        node_inputs: Dict[str, str],
        initial_input: str,
        edges: List[WorkflowEdge],
        template_renderer: Any,
    ) -> str:
        """
        Worker 작업 템플릿 렌더링

        Args:
            task_template: 작업 템플릿
            node_id: 노드 ID
            node_outputs: 노드 출력 매핑
            node_inputs: 각 노드가 실제로 받을 입력 (피드백 루프 지원)
            initial_input: 초기 입력
            edges: 엣지 목록
            template_renderer: 템플릿 렌더러

        Returns:
            str: 렌더링된 작업 설명
        """
        parent_nodes = self._get_parent_nodes(node_id, edges)
        parent_outputs = {pid: node_outputs[pid] for pid in parent_nodes if pid in node_outputs}

        return template_renderer.render_task_template(
            template=task_template,
            node_id=node_id,
            node_outputs=parent_outputs,
            node_inputs=node_inputs,
            initial_input=initial_input,
        )

    def _save_worker_node_session(
        self, node_id: str, agent_name: str, worker_session_id: str, session_id: str
    ) -> None:
        """
        Worker 노드의 SDK 세션 저장

        Args:
            node_id: 노드 ID
            agent_name: Agent 이름
            worker_session_id: Worker SDK 세션 ID
            session_id: 워크플로우 세션 ID
        """
        # 메모리 업데이트
        self.node_sessions[node_id] = worker_session_id
        self.node_agent_names[node_id] = agent_name

        # 디스크 동기화 (콜백 호출)
        if self.on_node_session_update:
            self.on_node_session_update(node_id, worker_session_id)

        if node_id not in self.node_session_history:
            self.node_session_history[node_id] = []

        existing_session = next(
            (
                s
                for s in self.node_session_history[node_id]
                if s["session_id"] == worker_session_id
            ),
            None,
        )

        if existing_session:
            existing_session["last_used_at"] = datetime.now().isoformat()
        else:
            self.node_session_history[node_id].append(
                {
                    "session_id": worker_session_id,
                    "agent_name": agent_name,
                    "created_at": datetime.now().isoformat(),
                    "last_used_at": datetime.now().isoformat(),
                }
            )

        logger.info(
            f"[{session_id}] ✓ 노드 세션 저장 완료: {node_id} ({agent_name}) → "
            f"SDK 세션 {worker_session_id[:8]}... "
            f"(총 {len(self.node_sessions)}개 노드, "
            f"이력: {len(self.node_session_history.get(node_id, []))}개)"
        )
