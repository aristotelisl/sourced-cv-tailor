"""Real Claude API calls. Opt in with CV_TAILOR_LIVE_TESTS=1 (costs a few cents per run)."""
import os
from pathlib import Path

import pytest

from backend.config import get_settings
from backend.llm import analyse_job

pytestmark = pytest.mark.skipif(
    os.environ.get("CV_TAILOR_LIVE_TESTS") != "1" or not get_settings().configured,
    reason="live LLM tests: set CV_TAILOR_LIVE_TESTS=1 and ANTHROPIC_API_KEY",
)

JOBS = Path(__file__).parent / "fixtures" / "jobs"


def lower(items: list[str]) -> str:
    return " | ".join(items).lower()


def test_uk_backend_listing():
    job = analyse_job((JOBS / "uk_backend_gbp.txt").read_text(encoding="utf-8"))
    assert job.role_family == "backend"
    assert job.remote == "hybrid"
    assert job.salary and job.salary.currency == "GBP" and job.salary.min == 55000
    assert job.right_to_work and "uk" in job.right_to_work.lower()
    assert "kubernetes" in lower(job.nice_to_have)
    assert "kubernetes" not in lower(job.must_have)
    assert "postgresql" in lower(job.stack)


def test_inr_salary_is_kept_in_inr():
    job = analyse_job((JOBS / "remote_frontend_inr.txt").read_text(encoding="utf-8"))
    assert job.role_family == "frontend"
    assert job.remote == "remote"
    assert job.salary and job.salary.currency == "INR" and job.salary.min == 1_200_000
    assert job.right_to_work is None
