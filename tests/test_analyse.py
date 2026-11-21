from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend.api import analyse as analyse_api
from backend.llm import LLMError, LLMNotConfigured, client as llm_client
from backend.main import app
from backend.models import JobAnalysis

client = TestClient(app)

# The example from SPEC §4.1: the contract must accept it as-is.
SPEC_EXAMPLE = {
    "company": "Stripe", "title": "Software Engineer, New Grad - Frontend",
    "location": "Barcelona, on-site 50%", "remote": "hybrid",
    "salary": {"min": 46200, "max": 69400, "currency": "EUR", "period": "year"},
    "seniority": "new-grad", "years_required": "0-1.5",
    "must_have": ["CS degree", "programming experience", "multi-person projects", "AI tools with critical review"],
    "nice_to_have": ["frontend specialisation", "code review", "large codebases"],
    "stack": ["Java", "Ruby", "JavaScript", "Scala", "Go"],
    "right_to_work": "Spain (EU)",
    "keywords": ["frontend", "React", "large codebases", "AI-assisted development"],
    "role_family": "frontend",
}
LISTING = "We are hiring a frontend engineer to build dashboards in React and TypeScript. " * 3


def test_spec_example_validates():
    JobAnalysis.model_validate(SPEC_EXAMPLE)


def test_unknown_role_family_is_rejected():
    with pytest.raises(ValueError):
        JobAnalysis.model_validate({**SPEC_EXAMPLE, "role_family": "devops"})


# --- API (LLM mocked) ----------------------------------------------------------

def test_api_returns_analysis(monkeypatch):
    seen = {}

    def fake(text):
        seen["text"] = text
        return JobAnalysis.model_validate(SPEC_EXAMPLE)

    monkeypatch.setattr(analyse_api, "analyse_job", fake)
    r = client.post("/api/analyse", json={"text": LISTING})
    assert r.status_code == 200
    assert r.json() == SPEC_EXAMPLE
    assert seen["text"] == LISTING


def test_api_rejects_tiny_input():
    assert client.post("/api/analyse", json={"text": "React dev"}).status_code == 422


@pytest.mark.parametrize("error, status", [(LLMNotConfigured("no key"), 503), (LLMError("boom"), 502)])
def test_api_maps_llm_errors(monkeypatch, error, status):
    def fail(text):
        raise error

    monkeypatch.setattr(analyse_api, "analyse_job", fail)
    r = client.post("/api/analyse", json={"text": LISTING})
    assert r.status_code == status
    assert r.json()["detail"]["message"] == str(error)


# --- LLM client (SDK mocked) ---------------------------------------------------

class FakeAnthropic:
    def __init__(self, response):
        self.calls = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(parse=self._parse))
        self._response = response

    def _parse(self, **kwargs):
        self.calls.append(kwargs)
        return self._response


@pytest.fixture
def fake_sdk(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    def install(stop_reason="end_turn", parsed=None):
        fake = FakeAnthropic(SimpleNamespace(stop_reason=stop_reason, parsed_output=parsed))
        monkeypatch.setattr(llm_client, "_client", lambda key: fake)
        return fake

    return install


def test_parse_returns_validated_output(fake_sdk):
    expected = JobAnalysis.model_validate(SPEC_EXAMPLE)
    fake = fake_sdk(parsed=expected)
    assert llm_client.parse("sys", "user", JobAnalysis, task="analyse") is expected
    call = fake.calls[0]
    assert call["output_format"] is JobAnalysis


@pytest.mark.parametrize("stop_reason, parsed, message", [
    ("refusal", None, "declined"),
    ("max_tokens", None, "cut off"),
    ("end_turn", None, "did not match"),
])
def test_parse_raises_on_unusable_response(fake_sdk, stop_reason, parsed, message):
    fake_sdk(stop_reason=stop_reason, parsed=parsed)
    with pytest.raises(LLMError, match=message):
        llm_client.parse("sys", "user", JobAnalysis, task="analyse")


def test_parse_without_key_is_not_configured(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(LLMNotConfigured):
        llm_client.parse("sys", "user", JobAnalysis, task="analyse")
