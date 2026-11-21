import re
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader

from backend.main import app
from backend.models import TailoredCV
from backend.render import render_html, render_pdf
from tests.conftest import GOLDEN_FILES

client = TestClient(app)


def section_titles(html: str) -> list[str]:
    return re.findall(r"<h2>(.*?)</h2>", html)


def test_html_has_header_and_sections_in_order(golden, profile):
    html = render_html(golden, profile["person"])
    assert "Jordan Avery" in html
    assert section_titles(html) == ["Employment", "Education", "Selected Project", "Awards", "Skills"]


def head_left(html: str) -> str:
    return re.search(r'<div class="l">(.*?)</div>', html).group(1)


def test_header_shows_all_contact_details_by_default(golden, profile):
    html = render_html(golden, profile["person"])
    p = profile["person"]
    assert head_left(html) == f"{p['location']}<br>{p['phone']}"
    for link in ("website", "linkedin", "github"):
        assert f'href="{p[link]}"' in html


def test_header_hides_chosen_contact_details(golden, profile):
    golden.hide_contact = ["phone", "github", "linkedin"]
    golden.header_extras = ["UK Pre-Settled Status"]
    html = render_html(golden, profile["person"])
    p = profile["person"]
    assert head_left(html) == f"{p['location']}<br>UK Pre-Settled Status"
    assert p["github"] not in html and p["linkedin"] not in html
    assert f'href="{p["website"]}"' in html and p["email"] in html


def test_header_with_location_and_phone_hidden_has_no_stray_breaks(golden, profile):
    golden.hide_contact = ["location", "phone"]
    assert head_left(render_html(golden, profile["person"])) == ""


def test_unknown_contact_field_is_rejected(golden_json):
    r = client.post("/api/render/html", json={**golden_json, "hide_contact": ["email"]})
    assert r.status_code == 422


def test_fit_layout_overrides_defaults(golden, profile):
    html = render_html(golden, profile["person"], {"font_pt": 9.8})
    assert "font-size: 9.8pt" in html


def test_text_is_escaped(golden, profile):
    golden.sections[0].entries[0].bullets[0].text = "<script>alert(1)</script>"
    assert "<script>alert" not in render_html(golden, profile["person"])


@pytest.mark.parametrize("path", GOLDEN_FILES, ids=lambda p: p.name)
def test_golden_files_render_to_one_page(path, profile):
    cv = TailoredCV.model_validate_json(path.read_text(encoding="utf-8"))
    result = render_pdf(cv, profile["person"])
    assert result.fits
    assert len(PdfReader(BytesIO(result.pdf)).pages) == 1


def test_overflow_is_reported(golden, profile):
    employment = golden.sections[0].entries[0]
    employment.bullets = employment.bullets * 8
    result = render_pdf(golden, profile["person"])
    assert not result.fits
    assert result.pages > 1
    assert result.fit_step == 4  # tried every step


# --- API ---------------------------------------------------------------------

def test_api_html(golden_json):
    r = client.post("/api/render/html", json=golden_json)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    assert r.headers["x-unverified-sources"] == ""
    assert section_titles(r.text)[0] == "Employment"


def test_api_reports_unverified_sources(golden_json):
    golden_json["sections"][0]["entries"][1]["bullets"][0]["source"] = "kestrel_rampup"
    r = client.post("/api/render/html", json=golden_json)
    assert r.status_code == 200
    assert r.headers["x-unverified-sources"] == "kestrel_rampup"


def test_api_pdf(golden_json):
    r = client.post("/api/render/pdf", json=golden_json)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.headers["x-page-count"] == "1"
    assert 'filename="CV_Jordan_Avery_Frontend.pdf"' in r.headers["content-disposition"]
    assert len(PdfReader(BytesIO(r.content)).pages) == 1


@pytest.mark.parametrize("endpoint", ["/api/render/html", "/api/render/pdf"])
def test_api_rejects_unknown_source_before_rendering(golden_json, endpoint):
    golden_json["sections"][0]["entries"][0]["bullets"][0]["source"] = "lumora_kubernetes"
    r = client.post(endpoint, json=golden_json)
    assert r.status_code == 422
    assert r.json()["detail"]["unknown"] == ["lumora_kubernetes"]


def test_api_rejects_invalid_json_shape(golden_json):
    del golden_json["sections"]
    assert client.post("/api/render/html", json=golden_json).status_code == 422


def test_api_reports_overflow(golden_json):
    entry = golden_json["sections"][0]["entries"][0]
    entry["bullets"] = entry["bullets"] * 8
    r = client.post("/api/render/pdf", json=golden_json)
    assert r.status_code == 422
    assert r.json()["detail"]["error"] == "overflow"


def test_api_check_reports_fit(golden_json):
    r = client.post("/api/render/check", json=golden_json)
    assert r.status_code == 200
    assert r.json() == {"pages": 1, "fit_step": 0, "fits": True, "unverified": []}


def test_api_profile_summary_hides_empty_extras():
    r = client.get("/api/profile")
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "Jordan Avery"
    assert set(body["contact"]) == {"location", "phone", "website", "linkedin", "github"}
    assert body["header_extras"] == {"uk_presettled": "UK Pre-Settled Status", "eu_citizen": "EU Citizen (Portugal)"}
