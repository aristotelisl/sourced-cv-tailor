import pytest

from backend.models import TailoredCV
from backend.profile import check_sources, source_index
from tests.conftest import GOLDEN_FILES


def test_profile_ids_are_unique(profile):
    source_index(profile)  # raises on duplicates


def test_duplicate_id_is_an_error(profile):
    profile["awards"].append(dict(profile["awards"][0]))
    with pytest.raises(ValueError, match="duplicate id 'hackathon'"):
        source_index(profile)


@pytest.mark.parametrize("path", GOLDEN_FILES, ids=lambda p: p.name)
def test_golden_files_only_cite_the_profile(path, profile):
    cv = TailoredCV.model_validate_json(path.read_text(encoding="utf-8"))
    assert check_sources(cv, profile).unknown == []


def test_unknown_source_is_reported(golden, profile):
    golden.sections[0].entries[0].bullets[0].source = "lumora_kubernetes"
    assert check_sources(golden, profile).unknown == ["lumora_kubernetes"]


def test_each_part_of_a_merged_source_is_checked(golden, profile):
    golden.sections[0].entries[0].bullets[0].source = "lumora_aspnet+aws_lambda"
    assert check_sources(golden, profile).unknown == ["aws_lambda"]


def test_golden_example_uses_only_verified_sources(golden, profile):
    assert check_sources(golden, profile).unverified == []


def test_unverified_source_is_a_warning_not_an_error(golden, profile):
    golden.sections[0].entries[1].bullets[0].source = "kestrel_rampup"  # `verified: false` in the profile
    check = check_sources(golden, profile)
    assert check.ok
    assert check.unverified == ["kestrel_rampup"]
