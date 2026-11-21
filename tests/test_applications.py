from datetime import date
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader

from backend.main import app
from backend.models import TailoredCV
from tests.test_analyse import SPEC_EXAMPLE

client = TestClient(app)
JOB_TEXT = "Software Engineer, New Grad - Frontend at Stripe. " * 3


def create() -> dict:
    r = client.post("/api/applications", json={"job_text": JOB_TEXT, "analysis": SPEC_EXAMPLE, "url": "https://x.test"})
    assert r.status_code == 201
    return r.json()


def add_version(app_id: int, cv: dict, **extra) -> dict:
    r = client.post(f"/api/applications/{app_id}/versions", json={"label": "Tailored", "cv": cv, **extra})
    assert r.status_code == 201, r.text
    return r.json()


def test_create_copies_job_fields_from_the_analysis():
    a = create()
    assert (a["company"], a["title"], a["location"]) == ("Stripe", SPEC_EXAMPLE["title"], SPEC_EXAMPLE["location"])
    assert a["salary"] == SPEC_EXAMPLE["salary"] | {"min": 46200.0, "max": 69400.0}
    assert (a["status"], a["applied_at"], a["cv_version_id"], a["versions"]) == ("draft", None, None, [])
    assert a["analysis"]["role_family"] == "frontend" and a["job_text"] == JOB_TEXT


def test_list_shows_version_counts(golden_json):
    a, b = create(), create()
    v = add_version(a["id"], golden_json)
    rows = {r["id"]: r for r in client.get("/api/applications").json()}
    assert (rows[a["id"]]["version_count"], rows[a["id"]]["latest_version_id"]) == (1, v["id"])
    assert (rows[b["id"]]["version_count"], rows[b["id"]]["latest_version_id"]) == (0, None)


def test_version_round_trips_the_cv(golden_json):
    a = create()
    coverage = [{"requirement": "CS degree", "kind": "must_have", "status": "covered", "note": "MSc"}]
    v = add_version(a["id"], golden_json, coverage=coverage)
    stored = client.get(f"/api/versions/{v['id']}").json()
    assert TailoredCV.model_validate(stored["cv"]) == TailoredCV.model_validate(golden_json)
    assert stored["coverage"] == coverage
    assert stored["filename"] == "CV_Jordan_Avery_Frontend"


def test_identical_cv_is_not_saved_twice(golden_json):
    a = create()
    first = add_version(a["id"], golden_json)
    again = add_version(a["id"], golden_json, label="Exported", mark_sent=True)
    assert again["id"] == first["id"]
    golden_json["sections"][0]["entries"][0]["bullets"].pop()
    edited = add_version(a["id"], golden_json, label="Exported")
    assert edited["id"] != first["id"]
    assert len(client.get(f"/api/applications/{a['id']}").json()["versions"]) == 2


def test_mark_sent_sets_the_applications_cv_version(golden_json):
    a = create()
    add_version(a["id"], golden_json)
    golden_json["header_extras"] = ["UK Pre-Settled Status"]
    sent = add_version(a["id"], golden_json, label="Exported", mark_sent=True)
    assert client.get(f"/api/applications/{a['id']}").json()["cv_version_id"] == sent["id"]


def test_version_with_unknown_source_is_rejected(golden_json):
    a = create()
    golden_json["sections"][0]["entries"][0]["bullets"][0]["source"] = "made_up"
    r = client.post(f"/api/applications/{a['id']}/versions", json={"label": "x", "cv": golden_json})
    assert r.status_code == 422 and r.json()["detail"]["unknown"] == ["made_up"]


def test_status_applied_records_today_once():
    a = create()
    r = client.patch(f"/api/applications/{a['id']}", json={"status": "applied", "notes": "Sent via referral"})
    assert (r.json()["status"], r.json()["applied_at"], r.json()["notes"]) == ("applied", date.today().isoformat(),
                                                                              "Sent via referral")
    r = client.patch(f"/api/applications/{a['id']}", json={"applied_at": "2026-11-01"})
    r = client.patch(f"/api/applications/{a['id']}", json={"status": "interview"})
    assert (r.json()["status"], r.json()["applied_at"]) == ("interview", "2026-11-01")


def test_invalid_status_is_rejected():
    a = create()
    assert client.patch(f"/api/applications/{a['id']}", json={"status": "ghosted"}).status_code == 422


def test_delete_removes_versions_too(golden_json):
    a = create()
    v = add_version(a["id"], golden_json)
    assert client.delete(f"/api/applications/{a['id']}").status_code == 204
    assert client.get(f"/api/applications/{a['id']}").status_code == 404
    assert client.get(f"/api/versions/{v['id']}").status_code == 404


@pytest.mark.parametrize("method, path", [
    ("get", "/api/applications/999"), ("patch", "/api/applications/999"), ("delete", "/api/applications/999"),
    ("get", "/api/versions/999"), ("get", "/api/versions/999/pdf"),
])
def test_missing_ids_are_404(method, path):
    kwargs = {"json": {}} if method == "patch" else {}
    assert getattr(client, method)(path, **kwargs).status_code == 404


def test_saved_version_re_renders_to_pdf(golden_json):
    a = create()
    v = add_version(a["id"], golden_json)
    r = client.get(f"/api/versions/{v['id']}/pdf")
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf"
    assert len(PdfReader(BytesIO(r.content)).pages) == 1
