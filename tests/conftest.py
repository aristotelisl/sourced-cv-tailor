import json
import os
from pathlib import Path

# Tests run against the fictional example profile, never your real data/profile.yaml.
# (Set before importing backend: backend.paths reads it at import time.)
os.environ["CV_TAILOR_PROFILE"] = str(Path(__file__).resolve().parent.parent / "examples" / "profile.example.yaml")

import pytest  # noqa: E402

from backend.llm import client as llm_client  # noqa: E402
from backend.models import TailoredCV  # noqa: E402
from backend.paths import EXAMPLES_DIR  # noqa: E402
from backend.profile import load_profile  # noqa: E402

GOLDEN_FILES = sorted(EXAMPLES_DIR.glob("*.tailored.json"))


@pytest.fixture
def profile() -> dict:
    return load_profile()


@pytest.fixture
def golden_json() -> dict:
    return json.loads((EXAMPLES_DIR / "example_frontend.tailored.json").read_text(encoding="utf-8"))


@pytest.fixture
def golden(golden_json) -> TailoredCV:
    return TailoredCV.model_validate(golden_json)


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Every test gets its own empty SQLite file; the real data/cv_tailor.db is never touched."""
    monkeypatch.setenv("CV_TAILOR_DB", str(tmp_path / "test.db"))


@pytest.fixture(autouse=True)
def default_provider(monkeypatch):
    """Unit tests assume the Claude provider, whatever the developer's .env says."""
    if os.environ.get("CV_TAILOR_LIVE_TESTS") != "1":
        for name in ("CV_TAILOR_PROVIDER", "CV_TAILOR_BASE_URL", "CV_TAILOR_API_KEY"):
            monkeypatch.delenv(name, raising=False)


@pytest.fixture
def fake_llm(monkeypatch):
    """Replace the Claude call with a queue of drafts."""
    calls = []

    def install(*drafts):
        queue = list(drafts)

        def parse(system, user, output, *, task, effort="medium"):
            calls.append(user)
            return queue.pop(0)
        monkeypatch.setattr(llm_client, "parse", parse)
        return calls
    return install
