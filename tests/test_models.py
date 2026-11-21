import pytest
from pydantic import ValidationError

from backend.models import TailoredCV
from tests.conftest import GOLDEN_FILES


@pytest.mark.parametrize("path", GOLDEN_FILES, ids=lambda p: p.name)
def test_golden_files_validate(path):
    TailoredCV.model_validate_json(path.read_text(encoding="utf-8"))


def test_bullet_without_source_is_rejected(golden_json):
    del golden_json["sections"][0]["entries"][0]["bullets"][0]["source"]
    with pytest.raises(ValidationError, match="source"):
        TailoredCV.model_validate(golden_json)


def test_unknown_field_is_rejected(golden_json):
    golden_json["sections"][0]["entries"][0]["bullets"][0]["metric"] = "40% faster"
    with pytest.raises(ValidationError, match="metric"):
        TailoredCV.model_validate(golden_json)


@pytest.mark.parametrize("filename", ["../evil", "my cv", "a/b"])
def test_unsafe_filename_is_rejected(golden_json, filename):
    golden_json["filename"] = filename
    with pytest.raises(ValidationError):
        TailoredCV.model_validate(golden_json)


def test_layout_values_cannot_inject_css(golden_json):
    golden_json["layout"] = {"section_gap": "9px; } body { display: none"}
    with pytest.raises(ValidationError):
        TailoredCV.model_validate(golden_json)
