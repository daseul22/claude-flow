"""피드백 루프 취소 토큰"""

import asyncio
from typing import Optional, Callable


class CancellationToken:
    """취소 토큰 (사용자 중단 처리)"""

    def __init__(self):
        self._cancelled = False
        self._reason: Optional[str] = None
        self._on_cancel: Optional[Callable[[], None]] = None

    def cancel(self, reason: str = "사용자 요청"):
        """루프 취소"""
        self._cancelled = True
        self._reason = reason
        if self._on_cancel:
            self._on_cancel()

    def is_cancelled(self) -> bool:
        """취소 여부 확인"""
        return self._cancelled

    def throw_if_cancelled(self):
        """취소되었으면 예외 발생"""
        if self._cancelled:
            raise asyncio.CancelledError(self._reason or "Cancelled")

    def reset(self):
        """토큰 리셋"""
        self._cancelled = False
        self._reason = None

    def on_cancel(self, callback: Callable[[], None]):
        """취소 시 콜백 등록"""
        self._on_cancel = callback

    @property
    def reason(self) -> Optional[str]:
        """취소 이유"""
        return self._reason


# feedback_loop_improved.py에 통합 예시
"""
async def run_with_feedback(
    self,
    agent: AgentClient,
    initial_message: str,
    condition_prompt: str,
    cancellation_token: Optional[CancellationToken] = None,  # 추가
    ...
) -> AsyncIterator[str]:
    while self.current_iteration < self.max_iterations:
        # 취소 체크
        if cancellation_token and cancellation_token.is_cancelled():
            yield f"\n\n⚠️ 피드백 루프 중단: {cancellation_token.reason}\n"
            break

        self.current_iteration += 1
        # ... 기존 로직 ...

        # 에이전트 실행 중에도 취소 체크
        try:
            async for chunk in agent.send_message(...):
                if cancellation_token:
                    cancellation_token.throw_if_cancelled()
                output += chunk
                yield chunk
        except asyncio.CancelledError as e:
            yield f"\n\n⚠️ 실행 중단: {e}\n"
            break
"""


# TUI 통합 예시
"""
# app.py
class ClaudeFlowApp(App):
    def __init__(self, ...):
        self.cancellation_token = CancellationToken()

    def action_interrupt(self):
        '''Ctrl+C 단축키 처리'''
        if self.is_feedback_loop_running:
            # 피드백 루프 중단
            self.cancellation_token.cancel("사용자가 Ctrl+C를 눌렀습니다")
            self.chat_view.append_message(
                "system",
                "⚠️ 피드백 루프를 중단합니다..."
            )
        else:
            # 일반 중단 처리
            self.input_box.clear()

    async def run_feedback_loop(self, ...):
        self.is_feedback_loop_running = True
        self.cancellation_token.reset()

        try:
            async for chunk in self.feedback_loop.run_with_feedback(
                ...,
                cancellation_token=self.cancellation_token,
            ):
                yield chunk
        finally:
            self.is_feedback_loop_running = False
"""
