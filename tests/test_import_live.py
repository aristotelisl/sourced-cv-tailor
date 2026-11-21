"""Real API call: read the fictional golden CV (rendered to PDF) into a profile.
Opt in with CV_TAILOR_LIVE_TESTS=1 (costs a few cents per run)."""
import os

import pytest
import yaml

from backend.config import get_settings
from backend.llm.import_cv import extract_profile
from backend.profile import profile_records
from backend.profile_import import build
from backend.profile_import.text import extract_text
from backend.render import render_pdf

pytestmark = pytest.mark.skipif(
    os.environ.get("CV_TAILOR_LIVE_TESTS") != "1" or not get_settings().configured,
    reason="live LLM tests: set CV_TAILOR_LIVE_TESTS=1 and ANTHROPIC_API_KEY",
)


def test_golden_cv_pdf_becomes_a_faithful_profile(golden, profile):
    text = extract_text("cv.pdf", render_pdf(golden, profile["person"]).pdf)
    draft, problems = extract_profile(text)
    data, flagged, warnings = build.resolve(draft, problems)
    result = yaml.safe_load(build.to_yaml(data, flagged, draft.questions))
    print("\n".join(warnings))

    profile_records(result)  # loads like any profile
    assert result["person"]["name"] == "Jordan Avery"
    assert {e["company"] for e in result["experience"]} >= {"Lumora", "Kestrel Software"}
    assert len(result["education"]) == 2
    bullets = [b for e in result["experience"] for b in e["bullets"]]
    assert len(bullets) >= 4
    # A clean, machine-made PDF should come through almost untouched.
    assert sum(1 for b in bullets if b.get("verified") is False) <= 1
    assert "Kubernetes" not in str(result) and "AWS" not in str(result)
