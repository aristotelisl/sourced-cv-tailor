"""Any OpenAI-compatible chat completions API: OpenAI, Gemini, OpenRouter, Groq, Ollama, LM Studio...

Plain HTTP (httpx), so there's no extra SDK. The request asks for JSON matching the output
model's schema (`response_format: json_schema`); servers that don't support that get
`json_object` with the schema in the message instead. Pydantic validates the answer, and the
callers' no-invention checks and retries run exactly as with Claude.
"""
import json
import re
from functools import lru_cache
from types import SimpleNamespace
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from backend.config import Settings, Task
from backend.llm import usage
from backend.llm.client import LLMError, LLMNotConfigured

T = TypeVar("T", bound=BaseModel)

DEFAULT_BASE_URL = "https://api.openai.com/v1"
# Local models can be slow on a long CV prompt.
TIMEOUT = httpx.Timeout(600.0, connect=10.0)
# (base_url, model) pairs that rejected json_schema; they get json_object from then on.
_NO_JSON_SCHEMA: set[tuple[str, str]] = set()
_FENCE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL)


@lru_cache
def _http() -> httpx.Client:
    return httpx.Client(timeout=TIMEOUT)


def _schema_instruction(output: type[BaseModel]) -> str:
    return ("\n\nReply with only a JSON object (no prose, no code fence) matching this JSON schema:\n"
            + json.dumps(output.model_json_schema()))


def _body(model: str, system: str, user: str, output: type[BaseModel], json_schema: bool) -> dict:
    if json_schema:
        response_format = {"type": "json_schema",
                           "json_schema": {"name": output.__name__, "schema": output.model_json_schema()}}
    else:
        response_format = {"type": "json_object"}
        user += _schema_instruction(output)
    # The system prompt (instructions + profile) comes first and is the same across requests,
    # so providers with automatic prefix caching reuse it.
    return {"model": model, "response_format": response_format,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}


def _post(settings: Settings, body: dict) -> httpx.Response:
    base = (settings.base_url or DEFAULT_BASE_URL).rstrip("/")
    headers = {"Authorization": f"Bearer {settings.api_key}"} if settings.api_key else {}
    try:
        return _http().post(f"{base}/chat/completions", json=body, headers=headers)
    except httpx.TimeoutException as e:
        raise LLMError(f"The model at {base} timed out") from e
    except httpx.HTTPError as e:
        raise LLMError(f"Could not reach {base}") from e


def _error_message(response: httpx.Response) -> str:
    try:
        error = response.json().get("error")
        return error.get("message", str(error)) if isinstance(error, dict) else str(error or response.text)
    except ValueError:
        return response.text[:300]


def _rejects_json_schema(response: httpx.Response) -> bool:
    return response.status_code in (400, 422) and any(
        s in _error_message(response).lower() for s in ("response_format", "json_schema", "schema"))


def _usage(data: dict) -> SimpleNamespace:
    """Map OpenAI-style token counts onto the fields usage.record() reads."""
    u = data.get("usage") or {}
    cached = (u.get("prompt_tokens_details") or {}).get("cached_tokens") or 0
    return SimpleNamespace(input_tokens=max((u.get("prompt_tokens") or 0) - cached, 0),
                           output_tokens=u.get("completion_tokens") or 0,
                           cache_read_input_tokens=cached, cache_creation_input_tokens=0)


def parse(settings: Settings, model: str, system: str, user: str, output: type[T], *,
          task: Task, effort: str) -> T:
    key = (settings.base_url or DEFAULT_BASE_URL, model)
    json_schema = key not in _NO_JSON_SCHEMA
    response = _post(settings, _body(model, system, user, output, json_schema))
    if json_schema and _rejects_json_schema(response):
        _NO_JSON_SCHEMA.add(key)
        response = _post(settings, _body(model, system, user, output, json_schema=False))

    if response.status_code in (401, 403):
        raise LLMNotConfigured(f"The API key was rejected ({response.status_code}): {_error_message(response)}")
    if response.status_code >= 400:
        raise LLMError(f"Model API error {response.status_code}: {_error_message(response)}")
    try:
        data = response.json()
        choice = data["choices"][0]
    except (ValueError, KeyError, IndexError, TypeError) as e:
        raise LLMError("The model API returned an unexpected response") from e

    # `effort` is Claude's setting; it's logged for comparison but not sent.
    usage.record(task, data.get("model") or model, effort, _usage(data))

    message = choice.get("message") or {}
    if message.get("refusal") or choice.get("finish_reason") == "content_filter":
        raise LLMError("The model declined this request")
    if choice.get("finish_reason") == "length":
        raise LLMError("The model's response was cut off (too long for its output limit)")
    text = (message.get("content") or "").strip()
    fenced = _FENCE.match(text)
    try:
        return output.model_validate_json(fenced.group(1) if fenced else text)
    except ValidationError as e:
        raise LLMError("The model's response did not match the expected schema") from e
