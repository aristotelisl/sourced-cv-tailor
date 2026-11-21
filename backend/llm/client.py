"""The one place that calls a model: a structured-output request validated by Pydantic.

`parse()` sends the request to the provider in .env (CV_TAILOR_PROVIDER): the Claude API
(default) or any OpenAI-compatible API (see backend/llm/openai_compat.py). Everything above
this module is provider-agnostic, and the no-invention checks run on every answer either way.
"""
from functools import lru_cache
from typing import Literal, TypeVar

import anthropic
from pydantic import BaseModel

from backend.config import PROVIDERS, Settings, Task, get_settings
from backend.llm import usage

T = TypeVar("T", bound=BaseModel)
Effort = Literal["low", "medium", "high", "xhigh", "max"]

# Models that accept server-side refusal fallbacks (Haiku 5.5 has none and would reject the field).
FALLBACK_MODELS = {"claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5", "claude-fable-5-1", "claude-fable-5-2"}


class LLMError(Exception):
    """The model call failed or returned something unusable."""


class LLMNotConfigured(LLMError):
    """No API key, model or provider set up in .env."""


def parse(system: str, user: str, output: type[T], *, task: Task, effort: Effort = "medium") -> T:
    """Ask the model configured for `task` for a response matching `output`, validated."""
    settings = get_settings()
    if settings.provider not in PROVIDERS:
        raise LLMNotConfigured(f"CV_TAILOR_PROVIDER must be one of {', '.join(PROVIDERS)}, "
                               f"not '{settings.provider}'")
    if not settings.configured:
        raise LLMNotConfigured("ANTHROPIC_API_KEY is not set in .env" if settings.provider == "anthropic"
                               else "Set CV_TAILOR_API_KEY (or CV_TAILOR_BASE_URL for a local server) in .env")
    model = settings.model_for(task)
    if not model:
        raise LLMNotConfigured(f"No model for '{task}': set CV_TAILOR_MODEL in .env")
    if settings.provider == "openai":
        from backend.llm import openai_compat  # noqa: PLC0415 (keeps the import cycle-free)
        return openai_compat.parse(settings, model, system, user, output, task=task, effort=effort)
    return _parse_anthropic(settings, model, system, user, output, task=task, effort=effort)


@lru_cache
def _client(api_key: str) -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=api_key)


def _parse_anthropic(settings: Settings, model: str, system: str, user: str, output: type[T], *,
                     task: Task, effort: Effort) -> T:
    extra = {}
    if model in FALLBACK_MODELS:
        # If a safety classifier declines, the API retries on a fallback model in the same call.
        extra = {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"}
    try:
        response = _client(settings.api_key).beta.messages.parse(
            model=model,
            max_tokens=16000,
            # Cached: the system prompt (instructions + profile) is the same across requests.
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user}],
            output_format=output,
            output_config={"effort": effort},
            **extra,
        )
    except anthropic.AuthenticationError as e:
        raise LLMNotConfigured("ANTHROPIC_API_KEY was rejected") from e
    except anthropic.APIStatusError as e:
        raise LLMError(f"Claude API error {e.status_code}: {e.message}") from e
    except anthropic.APIConnectionError as e:
        raise LLMError("Could not reach the Claude API") from e

    # Billed even when the answer turns out unusable, so record before checking it.
    usage.record(task, getattr(response, "model", None) or model, effort, getattr(response, "usage", None))

    if response.stop_reason == "refusal":
        raise LLMError("Claude declined this request")
    if response.stop_reason == "max_tokens":
        raise LLMError("Claude's response was cut off (max_tokens)")
    if response.parsed_output is None:
        raise LLMError("Claude's response did not match the expected schema")
    return response.parsed_output
