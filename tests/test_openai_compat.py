"""The OpenAI-compatible provider, against a fake HTTP server (no network, no key)."""
import json

import httpx
import pytest

from backend.config import get_settings
from backend.llm import LLMError, LLMNotConfigured, client as llm_client, openai_compat
from backend.models import JobAnalysis
from backend.store.db import connect
from tests.test_analyse import SPEC_EXAMPLE

ANSWER = json.dumps(SPEC_EXAMPLE)


@pytest.fixture
def server(monkeypatch):
    """Point the provider at a fake server; queue (status, json) replies, inspect the requests."""
    monkeypatch.setenv("CV_TAILOR_PROVIDER", "openai")
    monkeypatch.setenv("CV_TAILOR_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.setenv("CV_TAILOR_MODEL", "llama-test")
    monkeypatch.delenv("CV_TAILOR_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    openai_compat._NO_JSON_SCHEMA.clear()
    requests, replies = [], []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        status, body = replies.pop(0)
        return httpx.Response(status, json=body)

    monkeypatch.setattr(openai_compat, "_http", lambda: httpx.Client(transport=httpx.MockTransport(handle)))

    def reply(*items):
        replies.extend(items)
        return requests
    return reply


def ok(content=ANSWER, finish="stop", usage=None, **message):
    return 200, {"model": "llama-test", "choices": [{"finish_reason": finish,
                                                     "message": {"content": content, **message}}],
                 "usage": usage or {"prompt_tokens": 1200, "completion_tokens": 300,
                                    "prompt_tokens_details": {"cached_tokens": 1000}}}


def call():
    return llm_client.parse("system prompt", "user prompt", JobAnalysis, task="analyse")


def test_request_asks_for_the_output_schema(server):
    requests = server(ok())
    assert call() == JobAnalysis.model_validate(SPEC_EXAMPLE)
    [request] = requests
    assert str(request.url) == "http://localhost:11434/v1/chat/completions"
    assert "authorization" not in request.headers  # local server, no key
    body = json.loads(request.content)
    assert body["model"] == "llama-test"
    assert [m["role"] for m in body["messages"]] == ["system", "user"]
    assert body["response_format"]["type"] == "json_schema"
    assert body["response_format"]["json_schema"]["schema"] == JobAnalysis.model_json_schema()


def test_api_key_is_sent_as_bearer(server, monkeypatch):
    monkeypatch.setenv("CV_TAILOR_API_KEY", "sk-test")
    requests = server(ok())
    call()
    [request] = requests
    assert request.headers["authorization"] == "Bearer sk-test"


def test_server_without_json_schema_falls_back_to_json_object(server):
    requests = server((400, {"error": {"message": "response_format json_schema is not supported"}}), ok(), ok())
    call()
    first, second = (json.loads(r.content) for r in requests)
    assert first["response_format"]["type"] == "json_schema"
    assert second["response_format"] == {"type": "json_object"}
    assert "JSON schema" in second["messages"][1]["content"]
    call()  # remembered: goes straight to json_object
    assert json.loads(requests[2].content)["response_format"] == {"type": "json_object"}


def test_code_fenced_json_is_accepted(server):
    server(ok(content=f"```json\n{ANSWER}\n```"))
    assert call().title == SPEC_EXAMPLE["title"]


@pytest.mark.parametrize("reply, error, message", [
    ((401, {"error": {"message": "bad key"}}), LLMNotConfigured, "rejected"),
    ((500, {"error": {"message": "overloaded"}}), LLMError, "500: overloaded"),
    (ok(finish="length"), LLMError, "cut off"),
    (ok(refusal="I can't help with that"), LLMError, "declined"),
    (ok(content='{"title": 3}'), LLMError, "did not match"),
])
def test_unusable_replies_raise(server, reply, error, message):
    server(reply)
    with pytest.raises(error, match=message):
        call()


def test_usage_is_recorded_without_a_price(server):
    server(ok())
    call()
    with connect() as conn:
        row = dict(conn.execute("SELECT * FROM llm_usage").fetchone())
    assert (row["model"], row["input_tokens"], row["cache_read_tokens"], row["output_tokens"]) == \
        ("llama-test", 200, 1000, 300)
    assert row["cost_usd"] is None


def test_other_providers_need_a_model(server, monkeypatch):
    monkeypatch.delenv("CV_TAILOR_MODEL")
    with pytest.raises(LLMNotConfigured, match="CV_TAILOR_MODEL"):
        call()


def test_hosted_provider_needs_a_key(monkeypatch):
    monkeypatch.setenv("CV_TAILOR_PROVIDER", "openai")
    monkeypatch.setenv("CV_TAILOR_MODEL", "gpt-test")
    for name in ("CV_TAILOR_BASE_URL", "CV_TAILOR_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    assert not get_settings().configured
    with pytest.raises(LLMNotConfigured, match="CV_TAILOR_API_KEY"):
        call()


def test_unknown_provider_is_reported(monkeypatch):
    monkeypatch.setenv("CV_TAILOR_PROVIDER", "mystery")
    with pytest.raises(LLMNotConfigured, match="CV_TAILOR_PROVIDER"):
        call()


def test_claude_stays_the_default(monkeypatch):
    monkeypatch.delenv("CV_TAILOR_PROVIDER", raising=False)
    monkeypatch.delenv("CV_TAILOR_MODEL", raising=False)
    monkeypatch.delenv("CV_TAILOR_MODEL_TAILOR", raising=False)
    settings = get_settings()
    assert settings.provider == "anthropic" and settings.model_for("tailor") == "claude-sonnet-5-5"
