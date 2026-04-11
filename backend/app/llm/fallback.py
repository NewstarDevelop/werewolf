from collections.abc import Callable, Collection
from dataclasses import dataclass
from typing import TypeVar

from pydantic import ValidationError

from app.llm.client import JSONModeClient, JSONModeError
from app.llm.schemas import (
    PromptEnvelope,
    SpeechResponse,
    TargetedActionResponse,
    VoteResponse,
)

ResponseModelT = TypeVar(
    "ResponseModelT",
    SpeechResponse,
    VoteResponse,
    TargetedActionResponse,
)

class IllegalTargetError(ValueError):
    """Raised when an LLM response points at an illegal target."""


@dataclass(slots=True, kw_only=True)
class FallbackLLMClient:
    client: JSONModeClient
    max_retries: int = 2

    def request_speech(self, *, prompt: PromptEnvelope) -> SpeechResponse:
        return self._request_with_fallback(
            prompt=prompt,
            request_fn=self.client.request_speech,
            fallback_factory=default_speech_response,
        )

    def request_vote(
        self,
        *,
        prompt: PromptEnvelope,
        allowed_targets: Collection[int],
    ) -> VoteResponse:
        return self._request_with_fallback(
            prompt=prompt,
            request_fn=self.client.request_vote,
            validator=lambda response: validate_vote_target(
                response,
                allowed_targets=allowed_targets,
            ),
            fallback_factory=default_vote_response,
        )

    def request_targeted_action(
        self,
        *,
        prompt: PromptEnvelope,
        allowed_targets: Collection[int],
    ) -> TargetedActionResponse:
        return self._request_with_fallback(
            prompt=prompt,
            request_fn=self.client.request_targeted_action,
            validator=lambda response: validate_targeted_action(
                response,
                allowed_targets=allowed_targets,
            ),
            fallback_factory=default_targeted_action_response,
        )

    def _request_with_fallback(
        self,
        *,
        prompt: PromptEnvelope,
        request_fn: Callable[..., ResponseModelT],
        fallback_factory: Callable[[], ResponseModelT],
        validator: Callable[[ResponseModelT], None] | None = None,
    ) -> ResponseModelT:
        current_prompt = prompt

        for attempt in range(self.max_retries + 1):
            try:
                response = request_fn(prompt=current_prompt)
                if validator is not None:
                    validator(response)
                return response
            except (TimeoutError, JSONModeError, ValidationError, IllegalTargetError) as exc:
                if attempt == self.max_retries:
                    return fallback_factory()
                current_prompt = append_retry_feedback(current_prompt, message=_feedback_for_error(exc))

        return fallback_factory()


def validate_vote_target(
    response: VoteResponse,
    *,
    allowed_targets: Collection[int],
) -> None:
    if response.vote_target == 0:
        return
    if response.vote_target not in set(allowed_targets):
        raise IllegalTargetError(
            f"注意：你刚才选择的目标非法，投票只能在 {sorted(allowed_targets)} 中选择，或输出 0 弃票。"
        )


def validate_targeted_action(
    response: TargetedActionResponse,
    *,
    allowed_targets: Collection[int],
) -> None:
    if response.target is None:
        return
    if response.target not in set(allowed_targets):
        raise IllegalTargetError(
            f"注意：你刚才选择的目标非法，只能在 {sorted(allowed_targets)} 中选择。"
        )


def append_retry_feedback(prompt: PromptEnvelope, *, message: str) -> PromptEnvelope:
    return PromptEnvelope(
        system_prompt=prompt.system_prompt,
        context_prompt=prompt.context_prompt,
        task_prompt=f"{prompt.task_prompt}\n\n{message}",
    )


def default_speech_response() -> SpeechResponse:
    return SpeechResponse(
        inner_thought="本轮兜底发言。",
        speech_text="我没什么线索，过。",
    )


def default_vote_response() -> VoteResponse:
    return VoteResponse(
        inner_thought="本轮兜底弃票。",
        vote_target=0,
    )


def default_targeted_action_response() -> TargetedActionResponse:
    return TargetedActionResponse(
        inner_thought="本轮放弃行动。",
        target=None,
        use_antidote=False,
        use_poison=False,
    )


def _feedback_for_error(exc: Exception) -> str:
    if isinstance(exc, IllegalTargetError):
        return str(exc)
    if isinstance(exc, TimeoutError):
        return "注意：你上一次响应超时，请立即给出结果。"
    return "注意：你上一次输出不是合法 JSON 对象或字段不符合要求，请严格返回可解析的 JSON 对象。"
