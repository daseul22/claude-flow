"""응답 처리 전략"""

from abc import ABC, abstractmethod
from typing import Callable
from textual.worker import Worker

from .agent_client import AgentClient
from .feedback_loop import FeedbackLoop
from .response_handler import ResponseCallbackHandler, FeedbackLoopCallbackHandler
from ..components.chat_view import ChatView


class ResponseStrategy(ABC):
    """응답 처리 전략 추상 클래스"""

    @abstractmethod
    async def execute(
        self,
        agent: AgentClient,
        message: str,
        handler: ResponseCallbackHandler,
        worker: Worker,
        should_stop_flag: Callable[[], bool],
    ) -> str:
        """
        응답 실행

        Args:
            agent: 에이전트 클라이언트
            message: 사용자 메시지
            handler: 콜백 핸들러
            worker: Textual Worker (취소 체크용)
            should_stop_flag: 중단 플래그 확인 함수

        Returns:
            최종 응답 텍스트
        """
        pass

    def _should_cancel(self, worker: Worker, should_stop_flag: Callable[[], bool]) -> bool:
        """Worker 취소 여부 확인"""
        return worker.is_cancelled or should_stop_flag()


class NormalResponseStrategy(ResponseStrategy):
    """일반 응답 전략"""

    async def execute(
        self,
        agent: AgentClient,
        message: str,
        handler: ResponseCallbackHandler,
        worker: Worker,
        should_stop_flag: Callable[[], bool],
    ) -> str:
        """일반 응답 실행 (피드백 루프 없음)"""
        response_text = ""

        async for chunk in agent.send_message(
            message,
            on_thinking=handler.on_thinking,
            on_tool_use=handler.on_tool_use,
            on_tool_result=handler.on_tool_result,
        ):
            # Worker 취소 체크
            if self._should_cancel(worker, should_stop_flag):
                return response_text

            response_text += chunk
            handler.chat_view.write_wrapped(chunk)

        return response_text


class FeedbackLoopResponseStrategy(ResponseStrategy):
    """피드백 루프 응답 전략"""

    def __init__(
        self,
        feedback_loop: FeedbackLoop,
        condition_prompt: str,
        feedback_input: str,
        max_iterations: int,
    ):
        """
        Args:
            feedback_loop: 피드백 루프 인스턴스
            condition_prompt: 조건 프롬프트
            feedback_input: 피드백 입력
            max_iterations: 최대 반복 횟수
        """
        self.feedback_loop = feedback_loop
        self.condition_prompt = condition_prompt
        self.feedback_input = feedback_input
        self.max_iterations = max_iterations

    async def execute(
        self,
        agent: AgentClient,
        message: str,
        handler: ResponseCallbackHandler,
        worker: Worker,
        should_stop_flag: Callable[[], bool],
    ) -> str:
        """피드백 루프 응답 실행"""
        # 핸들러가 FeedbackLoopCallbackHandler인지 확인
        if not isinstance(handler, FeedbackLoopCallbackHandler):
            raise TypeError("FeedbackLoopResponseStrategy requires FeedbackLoopCallbackHandler")

        response_text = ""

        # 피드백 루프 활성화 알림
        handler.chat_view.add_system_message(
            f"🔁 피드백 루프 활성화 (최대 {self.max_iterations}회)",
            style="yellow",
        )

        async for chunk in self.feedback_loop.run_with_feedback(
            agent=agent,
            initial_message=message,
            condition_prompt=self.condition_prompt,
            feedback_input=self.feedback_input,
            on_iteration=self._create_iteration_callback(handler.chat_view),
            on_thinking=handler.on_thinking,
            on_tool_use=handler.on_tool_use,
            on_eval_start=handler.on_eval_start,
            on_eval_output=handler.on_eval_output,
            on_eval_result=handler.on_eval_result,
        ):
            # Worker 취소 체크
            if self._should_cancel(worker, should_stop_flag):
                return response_text

            response_text += chunk
            handler.chat_view.write_wrapped(chunk)

        return response_text

    def _create_iteration_callback(self, chat_view: ChatView) -> Callable[[int, str], None]:
        """반복 콜백 생성"""

        def on_iteration(iter_num: int, status: str):
            chat_view.add_system_message(f"🔄 반복 {iter_num}: {status}", style="dim")

        return on_iteration
