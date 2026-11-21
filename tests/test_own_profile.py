"""Your own data/profile.yaml (git-ignored): checked when it exists, skipped otherwise.

The rest of the suite runs against the fictional examples/profile.example.yaml.
"""
import pytest

from backend.models import TailoredCV
from backend.paths import ROOT
from backend.profile import check_sources, load_profile, source_index
from backend.profile_edit import yaml_io

OWN_PROFILE = ROOT / "data" / "profile.yaml"
OWN_EXAMPLE = ROOT / "data" / "example.tailored.json"

pytestmark = pytest.mark.skipif(not OWN_PROFILE.exists(), reason="no data/profile.yaml")


def test_own_profile_loads_with_unique_ids():
    source_index(load_profile(OWN_PROFILE))


def test_own_profile_round_trips_for_in_app_edits():
    text = OWN_PROFILE.read_text(encoding="utf-8")
    assert yaml_io.dump(yaml_io.load(text)) == text


@pytest.mark.skipif(not OWN_EXAMPLE.exists(), reason="no data/example.tailored.json")
def test_own_example_only_cites_own_profile():
    cv = TailoredCV.model_validate_json(OWN_EXAMPLE.read_text(encoding="utf-8"))
    assert check_sources(cv, load_profile(OWN_PROFILE)).unknown == []
