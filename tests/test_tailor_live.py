"""SPEC §8 acceptance tests against the real Claude API.

Opt in with CV_TAILOR_LIVE_TESTS=1 (each tailoring call takes ~1 minute and costs a few cents).
"""
import os
from pathlib import Path

import pytest

from backend.config import get_settings
from backend.llm import analyse_job
from backend.models import TailorRequest, TailoredCV
from backend.profile import load_profile
from backend.render import render_pdf
from backend.tailor.service import tailor
from backend.tailor.vocab import mentions

pytestmark = pytest.mark.skipif(
    os.environ.get("CV_TAILOR_LIVE_TESTS") != "1" or not get_settings().configured,
    reason="live LLM tests: set CV_TAILOR_LIVE_TESTS=1 and ANTHROPIC_API_KEY",
)

JOBS = Path(__file__).parent / "fixtures" / "jobs"


def cv_text(cv: TailoredCV) -> str:
    parts = []
    for s in cv.sections:
        parts += [f"{b.text} {b.tech or ''}" for e in s.entries for b in e.bullets]
        parts += [i for g in s.skills for i in g.items]
    return "\n".join(parts)


@pytest.fixture(scope="module")
def uk_backend():
    job = analyse_job((JOBS / "uk_backend_gbp.txt").read_text(encoding="utf-8"))
    return job, tailor(TailorRequest(job=job))


def test_backend_job_never_invents_kubernetes_or_aws(uk_backend):
    _, result = uk_backend
    text = cv_text(result.cv)
    gaps = " | ".join(result.cv.gap_report.must_have_missing + result.cv.gap_report.nice_to_have_missing)
    for term in ("Kubernetes", "AWS"):
        assert not mentions(text, term, ignore_case=True)
        assert mentions(gaps, term, ignore_case=True)


def test_uk_job_gets_presettled_suggestion(uk_backend):
    _, result = uk_backend
    assert [s.key for s in result.header_extra_suggestions] == ["uk_presettled"]


def test_backend_cv_leads_with_employment_and_fits_one_page(uk_backend):
    _, result = uk_backend
    assert result.cv.sections[0].title == "Employment"
    assert render_pdf(result.cv, load_profile()["person"]).fits


def test_inr_job_is_flagged_as_another_country():
    job = analyse_job((JOBS / "remote_frontend_inr.txt").read_text(encoding="utf-8"))
    result = tailor(TailorRequest(job=job))
    assert any("probably for another country" in f for f in result.cv.gap_report.flags)
    assert result.header_extra_suggestions == []


def test_cover_letter_claims_only_what_the_profile_backs(uk_backend):
    from backend.extras.service import generate
    from backend.models.extras import ExtraRequest
    job, result = uk_backend
    letter = generate(ExtraRequest(kind="cover_letter", job=job, cv=result.cv))
    claims = [s for p in letter.paragraphs for s in p.sentences if s.kind == "claim"]
    assert claims and all(s.sources for s in claims)
    for term in ("Kubernetes", "AWS"):
        assert not any(mentions(s.text, term, ignore_case=True) for s in claims)
    assert 150 <= len(letter.text.split()) <= 380
