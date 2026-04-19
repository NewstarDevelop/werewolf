import json
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
import logging

import httpx
from pydantic import BaseModel

from app.llm.client import JSONModeError, LLMProvider, ProviderRequestError
from app.llm.schemas import PromptEnvelope

DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"
DEFAULT_OPENAI_TIMEOUT_SECONDS = 30.0
_JSON_BLOCK_PATTERN = re.compile(r"```(?:json)?\s*(\{.*\})\s*```", re.DOTALL)
_API_KEY_ENV_VARS = ("OPENAI_API_KEY", "STITCH_API_KEY")
_MODEL_ENV_VARS = ("OPENAI_MODEL", "STITCH_MODEL")
_BASE_URL_ENV_VARS = ("OPENAI_BASE_URL", "STITCH_BASE_URL")
_TIMEOUT_ENV_VARS = ("OPENAI_TIMEOUT_SECONDS", "STITCH_TIMEOUT_SECONDS")
logger = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
class OpenAICompatibleSettings:
    api_key: str
    model: str
    base_url: str = DEFAULT_OPENAI_BASE_URL
    timeout_seconds: float = DEFAULT_OPENAI_TIMEOUT_SECONDS

    @property
    def chat_completions_url(self) -> str:
        normalized_base_url = self.base_url.rstrip("/")
        if normalized_base_url.endswith("/chat/completions"):
            return normalized_base_url
        return f"{normalized_base_url}/chat/completions"


@dataclass(slots=True, kw_only=True)
class OpenAICompatibleProvider(LLMProvider):
    settings: OpenAICompatibleSettings
    transport: httpx.BaseTransport | None = None

    def complete(
        self,
        *,
        prompt: PromptEnvelope,
        response_schema: type[BaseModel],
    ) -> str | Mapping[str, object]:
        request_body = {
            "model": self.settings.model,
            "messages": _build_messages(prompt=prompt, response_schema=response_schema),
            "response_format": {"type": "json_object"},
            "stream": False,
        }
        headers = {
            "Authorization": f"Bearer {self.settings.api_key}",
            "Content-Type": "application/json",
        }

        try:
            with httpx.Client(
                timeout=self.settings.timeout_seconds,
                transport=self.transport,
            ) as client:
                response = _post_chat_completion_with_compatibility_fallback(
                    client,
                    url=self.settings.chat_completions_url,
                    headers=headers,
                    request_body=request_body,
                )
        except httpx.TimeoutException as exc:
            raise TimeoutError("llm provider request timed out") from exc
        except httpx.HTTPStatusError as exc:
            body_preview = exc.response.text[:500]
            logger.warning(
                "llm provider http error status=%s body_preview=%r",
                exc.response.status_code,
                body_preview,
            )
            raise ProviderRequestError(
                "llm provider request failed",
                status_code=exc.response.status_code,
                retryable=_is_retryable_status_code(exc.response.status_code),
            ) from exc
        except httpx.HTTPError as exc:
            logger.warning("llm provider transport error type=%s message=%s", type(exc).__name__, exc)
            raise ProviderRequestError("llm provider request failed") from exc

        try:
            payload = response.json()
        except json.JSONDecodeError as exc:
            logger.warning(
                "llm provider returned non-json response body preview=%r",
                response.text[:500],
            )
            raise JSONModeError("llm provider response is not valid JSON") from exc

        content = _extract_message_content(payload)
        return _extract_json_payload(content)


def load_openai_compatible_settings_from_env() -> OpenAICompatibleSettings | None:
    api_key = _read_env_value(*_API_KEY_ENV_VARS)
    model = _read_env_value(*_MODEL_ENV_VARS)
    base_url = _read_env_value(*_BASE_URL_ENV_VARS)
    timeout_value = _read_env_value(*_TIMEOUT_ENV_VARS)

    if not any((api_key, model, base_url, timeout_value)):
        return None

    missing_variables: list[str] = []
    if not api_key:
        missing_variables.append(_format_env_aliases(*_API_KEY_ENV_VARS))
    if not model:
        missing_variables.append(_format_env_aliases(*_MODEL_ENV_VARS))
    if missing_variables:
        missing_names = ", ".join(missing_variables)
        raise ValueError(f"missing required environment variables: {missing_names}")

    timeout_seconds = DEFAULT_OPENAI_TIMEOUT_SECONDS
    if timeout_value:
        try:
            timeout_seconds = float(timeout_value)
        except ValueError as exc:
            raise ValueError(
                f"{_format_env_aliases(*_TIMEOUT_ENV_VARS)} must be a number",
            ) from exc
        if timeout_seconds <= 0:
            raise ValueError(
                f"{_format_env_aliases(*_TIMEOUT_ENV_VARS)} must be greater than 0",
            )

    return OpenAICompatibleSettings(
        api_key=api_key,
        model=model,
        base_url=base_url or DEFAULT_OPENAI_BASE_URL,
        timeout_seconds=timeout_seconds,
    )


def _read_env_value(*names: str) -> str:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


def _format_env_aliases(*names: str) -> str:
    return " or ".join(names)


def _build_messages(
    *,
    prompt: PromptEnvelope,
    response_schema: type[BaseModel],
) -> list[dict[str, str]]:
    schema_payload = response_schema.model_json_schema()
    schema_hint = json.dumps(
        {
            "type": schema_payload.get("type", "object"),
            "properties": schema_payload.get("properties", {}),
            "required": schema_payload.get("required", []),
        },
        ensure_ascii=False,
    )
    system_content = (
        f"{prompt.system_prompt}\n\n"
        "额外输出要求：你必须只返回一个合法 JSON 对象，不要输出 Markdown、代码块或任何额外说明。\n"
        f"返回结构必须满足以下 JSON Schema：{schema_hint}"
    )
    user_content = f"{prompt.context_prompt}\n\n{prompt.task_prompt}"
    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_content},
    ]


def _extract_message_content(payload: object) -> str:
    if not isinstance(payload, dict):
        raise JSONModeError("llm provider response payload must be an object")

    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise JSONModeError("llm provider response does not contain choices")

    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        raise JSONModeError("llm provider response choice must be an object")

    message = first_choice.get("message")
    if not isinstance(message, dict):
        raise JSONModeError("llm provider response does not contain a message")

    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        fragments = _extract_text_fragments(content)
        if fragments:
            return "\n".join(fragments)

    raise JSONModeError("llm provider response does not contain text content")


def _extract_text_fragments(content: list[object]) -> list[str]:
    fragments: list[str] = []
    for item in content:
        if not isinstance(item, dict):
            continue
        text = item.get("text")
        if isinstance(text, str):
            fragments.append(text)
    return fragments


def _extract_json_payload(content: str) -> dict[str, object]:
    candidates = [content.strip()]

    block_match = _JSON_BLOCK_PATTERN.search(content)
    if block_match is not None:
        candidates.append(block_match.group(1).strip())

    first_brace = content.find("{")
    last_brace = content.rfind("}")
    if first_brace != -1 and last_brace > first_brace:
        candidates.append(content[first_brace : last_brace + 1].strip())

    for candidate in candidates:
        if not candidate:
            continue
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload

    logger.warning(
        "llm provider message content is not valid json preview=%r",
        content[:500],
    )
    raise JSONModeError("llm provider content is not a valid JSON object")


def _post_chat_completion_with_compatibility_fallback(
    client: httpx.Client,
    *,
    url: str,
    headers: Mapping[str, str],
    request_body: dict[str, object],
) -> httpx.Response:
    try:
        response = client.post(url, headers=headers, json=request_body)
        response.raise_for_status()
        return response
    except httpx.HTTPStatusError as exc:
        if not _should_retry_without_response_format(exc.response, request_body):
            raise

        retry_body = dict(request_body)
        retry_body.pop("response_format", None)
        logger.warning(
            "openai-compatible provider rejected response_format, retrying without it status=%s",
            exc.response.status_code,
        )
        retry_response = client.post(url, headers=headers, json=retry_body)
        retry_response.raise_for_status()
        return retry_response


def _should_retry_without_response_format(
    response: httpx.Response,
    request_body: Mapping[str, object],
) -> bool:
    if "response_format" not in request_body:
        return False
    if response.status_code not in {400, 404, 422}:
        return False

    response_text = ""
    try:
        payload = response.json()
    except json.JSONDecodeError:
        response_text = response.text
    else:
        if isinstance(payload, dict):
            error_payload = payload.get("error")
            if isinstance(error_payload, dict):
                response_text = str(error_payload.get("message", ""))
            else:
                response_text = json.dumps(payload, ensure_ascii=False)
        else:
            response_text = json.dumps(payload, ensure_ascii=False)

    normalized_text = response_text.lower()
    return (
        "response_format" in normalized_text
        or "json_object" in normalized_text
        or "json mode" in normalized_text
    ) and (
        "unsupported" in normalized_text
        or "unknown" in normalized_text
        or "invalid" in normalized_text
        or "not support" in normalized_text
    )


def _is_retryable_status_code(status_code: int) -> bool:
    return status_code in {408, 409, 425, 429, 500, 502, 503, 504}
