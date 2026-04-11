import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol, TypeVar

from pydantic import BaseModel

from app.llm.schemas import (
    PromptEnvelope,
    SpeechResponse,
    TargetedActionResponse,
    VoteResponse,
)

ResponseModelT = TypeVar("ResponseModelT", bound=BaseModel)


class JSONModeError(ValueError):
    """Raised when a provider response cannot be consumed as strict JSON."""


class LLMProvider(Protocol):
    def complete(
        self,
        *,
        prompt: PromptEnvelope,
        response_schema: type[BaseModel],
    ) -> str | Mapping[str, object]:
        """Return raw structured output from any LLM backend."""


@dataclass(slots=True, kw_only=True)
class JSONModeClient:
    provider: LLMProvider

    def request(
        self,
        *,
        prompt: PromptEnvelope,
        response_schema: type[ResponseModelT],
    ) -> ResponseModelT:
        raw_response = self.provider.complete(
            prompt=prompt,
            response_schema=response_schema,
        )
        payload = _coerce_payload(raw_response)
        return response_schema.model_validate(payload)

    def request_speech(self, *, prompt: PromptEnvelope) -> SpeechResponse:
        return self.request(prompt=prompt, response_schema=SpeechResponse)

    def request_vote(self, *, prompt: PromptEnvelope) -> VoteResponse:
        return self.request(prompt=prompt, response_schema=VoteResponse)

    def request_targeted_action(
        self,
        *,
        prompt: PromptEnvelope,
    ) -> TargetedActionResponse:
        return self.request(prompt=prompt, response_schema=TargetedActionResponse)


def _coerce_payload(raw_response: str | Mapping[str, object]) -> dict[str, object]:
    if isinstance(raw_response, Mapping):
        return dict(raw_response)

    if not isinstance(raw_response, str):
        raise JSONModeError("provider response must be a JSON string or mapping")

    response_text = raw_response.strip()
    if not response_text:
        raise JSONModeError("provider response must not be empty")

    try:
        payload = json.loads(response_text)
    except json.JSONDecodeError as exc:
        raise JSONModeError("provider response is not valid JSON") from exc

    if not isinstance(payload, dict):
        raise JSONModeError("provider response must decode to a JSON object")

    return payload
