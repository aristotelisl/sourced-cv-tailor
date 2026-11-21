"""Per-task model choice, refusal fallbacks only where supported, and cost logging."""
from types import SimpleNamespace

import pytest

from backend.config import DEFAULT_MODELS, get_settings
from backend.llm import client as llm_client
from backend.llm.usage import cost_usd
from backend.models import JobAnalysis
from backend.store.db import connect
from tests.test_analyse import SPEC_EXAMPLE


@pytest.fixture(autouse=True)
def default_models(monkeypatch):
    """Ignore any model overrides in the developer's .env."""
    monkeypatch.delenv("CV_TAILOR_MODEL", raising=False)
    for task in DEFAULT_MODELS:
        monkeypatch.delenv(f"CV_TAILOR_MODEL_{task.upper()}", raising=False)


def usage(input_tokens=0, output_tokens=0, cache_read=0, cache_write=0):
    return SimpleNamespace(
        input_tokens=input_tokens, output_tokens=output_tokens,
        cache_read_input_tokens=cache_read, cache_creation_input_tokens=cache_write,
    )


@pytest.fixture
def fake_sdk(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    calls = []

    def _parse(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            stop_reason="end_turn", parsed_output=JobAnalysis.model_validate(SPEC_EXAMPLE),
            model=kwargs["model"], usage=usage(1000, 2000, 3000, 4000),
        )

    fake = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(parse=_parse)))
    monkeypatch.setattr(llm_client, "_client", lambda key: fake)
    return calls


def test_default_models_are_haiku_for_simple_steps_and_sonnet_for_writing():
    models = get_settings().models
    assert models["analyse"] == models["bullet"] == models["answer"] == "claude-haiku-5-5"
    assert models["tailor"] == models["extras"] == "claude-sonnet-5-5"


def test_env_overrides_one_task_or_all(monkeypatch):
    monkeypatch.setenv("CV_TAILOR_MODEL", "claude-opus-5-5")
    monkeypatch.setenv("CV_TAILOR_MODEL_ANALYSE", "claude-haiku-5-5")
    models = get_settings().models
    assert models["analyse"] == "claude-haiku-5-5"
    assert models["tailor"] == "claude-opus-5-5"


def test_haiku_call_sends_no_fallbacks(fake_sdk):
    llm_client.parse("sys", "user", JobAnalysis, task="analyse")
    assert fake_sdk[0]["model"] == "claude-haiku-5-5"
    assert "fallbacks" not in fake_sdk[0] and "betas" not in fake_sdk[0]


def test_sonnet_call_keeps_fallbacks(fake_sdk):
    llm_client.parse("sys", "user", JobAnalysis, task="tailor", effort="high")
    assert fake_sdk[0]["model"] == "claude-sonnet-5-5"
    assert fake_sdk[0]["fallbacks"] == "default"


def test_each_call_is_stored_with_its_cost(fake_sdk):
    llm_client.parse("sys", "user", JobAnalysis, task="tailor", effort="high")
    with connect() as conn:
        rows = [dict(r) for r in conn.execute("SELECT * FROM llm_usage")]
    assert len(rows) == 1
    row = rows[0]
    assert (row["task"], row["model"], row["effort"]) == ("tailor", "claude-sonnet-5-5", "high")
    assert (row["input_tokens"], row["output_tokens"]) == (1000, 2000)
    assert (row["cache_read_tokens"], row["cache_write_tokens"]) == (3000, 4000)
    # Sonnet 5.5: 1000*$2 + 2000*$10 + 3000*$0.10 + 4000*$2.50, per million tokens
    assert row["cost_usd"] == pytest.approx(0.0323)


def test_cost_examples():
    assert cost_usd("claude-opus-5-5", usage(1_000_000, 1_000_000)) == pytest.approx(24.0)
    assert cost_usd("claude-haiku-5-5", usage(10_000, 1_000)) == pytest.approx(0.0015)
    # Over 100K prompt tokens Haiku 5.5 switches to its higher rate card.
    assert cost_usd("claude-haiku-5-5", usage(200_000, 0)) == pytest.approx(0.10)
    assert cost_usd("some-unknown-model", usage(1, 1)) is None


def test_bookkeeping_failure_does_not_lose_the_answer(fake_sdk, monkeypatch):
    def broken():
        raise RuntimeError("disk full")
    monkeypatch.setattr("backend.llm.usage.connect", broken)
    assert llm_client.parse("sys", "user", JobAnalysis, task="analyse").title
