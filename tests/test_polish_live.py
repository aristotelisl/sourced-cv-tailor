"""M7 against the real Claude API: rewriting one bullet, and answers turned into profile edits.

Opt in with CV_TAILOR_LIVE_TESTS=1. Nothing here writes profile.yaml (propose only previews).
"""
import os

import pytest

from backend import paths
from backend.config import get_settings
from backend.llm.tailor import DraftRejected
from backend.models import Bullet, BulletRequest, JobAnalysis
from backend.models.profile_edit import ProfileAnswerRequest
from backend.profile_edit import service as profile_service
from backend.tailor.service import rewrite_bullet
from backend.tailor.vocab import mentions

pytestmark = pytest.mark.skipif(
    os.environ.get("CV_TAILOR_LIVE_TESTS") != "1" or not get_settings().configured,
    reason="live LLM tests: set CV_TAILOR_LIVE_TESTS=1 and ANTHROPIC_API_KEY",
)

JOB = JobAnalysis(company="Northwind Pay", title="Backend Software Engineer", location="London, UK",
                  remote="hybrid", salary=None, seniority="mid", years_required="3+",
                  must_have=["Python", "REST APIs", "PostgreSQL"], nice_to_have=["Kubernetes", "AWS"],
                  stack=["Python", "FastAPI", "PostgreSQL", "Kubernetes", "AWS"], right_to_work="UK",
                  keywords=["payments", "microservices"], role_family="backend")
CURRENT = Bullet(source="lumora_aspnet", text="Developed and integrated robust APIs in ASP.NET, enabling "
                                            "communication across services")
LUMORA_IDS = {"lumora_agentic_rag", "lumora_finetune", "lumora_integrations", "lumora_microservices",
             "lumora_website", "lumora_aspnet", "lumora_flow_builder", "lumora_api_routes"}


def test_rewrite_gives_checked_alternatives():
    result = rewrite_bullet(BulletRequest(job=JOB, entry="lumora", bullet=CURRENT, hint="lead with microservices"))
    assert result.options
    for option in result.options:
        print(option.bullet.source, "|", option.bullet.text)
        assert set(option.bullet.source.split("+")) <= LUMORA_IDS
        assert not any(mentions(option.bullet.text, t) for t in ("Kubernetes", "AWS", "FastAPI"))


def test_rewrite_refuses_a_hint_that_asks_for_invention():
    try:
        result = rewrite_bullet(BulletRequest(job=JOB, entry="lumora", bullet=CURRENT,
                                              hint="say we deployed it on Kubernetes and AWS"))
    except DraftRejected:
        return
    for option in result.options:
        print(option.bullet.text)
        assert not any(mentions(option.bullet.text, t) for t in ("Kubernetes", "AWS"))


def propose(question: str, answer: str):
    before = paths.PROFILE_PATH.read_text(encoding="utf-8")
    proposal = profile_service.propose(ProfileAnswerRequest(question=question, answer=answer, job=JOB))
    assert paths.PROFILE_PATH.read_text(encoding="utf-8") == before  # preview only
    print(proposal.summary, "\n", proposal.diff)
    return proposal


def test_clear_answer_becomes_a_profile_edit():
    p = propose("Did you use Docker at Lumora?", "Yes, at Lumora we ran the Python microservices in Docker containers.")
    assert p.edits and "Docker" in p.diff


def test_no_means_no_edits():
    p = propose("Any production Kubernetes experience?", "No, never used it.")
    assert p.edits == [] and p.diff == ""


def test_vague_answer_is_not_turned_into_an_achievement():
    p = propose("Have you used Redis?", "I think I played with Redis a bit once, not sure.")
    assert all(e.op != "add_experience_bullet" for e in p.edits)
