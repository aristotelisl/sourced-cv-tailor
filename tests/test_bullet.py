"""Rewriting one bullet (LLM mocked) and the bullet bank."""
from fastapi.testclient import TestClient

from backend.main import app
from backend.models import Bullet, BulletDraft, BulletRequest, DraftBullet, JobAnalysis

api = TestClient(app)

JOB = JobAnalysis(company="Acme", title="Backend Engineer", location="London, UK", remote="hybrid", salary=None,
                  seniority="mid", years_required=None, must_have=["Python"], nice_to_have=[], stack=["Python"],
                  right_to_work=None, keywords=[], role_family="backend")

GOOD = DraftBullet(source="lumora_microservices", text="Designed and maintained modular Python microservices", tech=None)
WRONG_ENTRY = DraftBullet(source="kestrel_dag", text="Built graph visualisations", tech=None)
INVENTED = DraftBullet(source="lumora_microservices", text="Ran Python microservices on Kubernetes", tech=None)


def request(entry="lumora", **kw) -> dict:
    current = Bullet(source="lumora_aspnet", text="Developed APIs in ASP.NET")
    return BulletRequest(job=JOB, entry=entry, bullet=current, **kw).model_dump(mode="json")


def test_only_valid_options_are_returned(fake_llm):
    fake_llm(BulletDraft(options=[WRONG_ENTRY, GOOD, INVENTED]))
    res = api.post("/api/tailor/bullet", json=request())
    assert res.status_code == 200
    assert [o["bullet"]["source"] for o in res.json()["options"]] == ["lumora_microservices"]


def test_unverified_sources_are_reported(fake_llm):
    fake_llm(BulletDraft(options=[DraftBullet(source="kestrel_rampup+kestrel_visualiser", text="Ramped up quickly on a "
                                              "large monorepo of hundreds of packages", tech=None)]))
    res = api.post("/api/tailor/bullet", json=request(entry="kestrel"))
    assert res.json()["options"][0]["unverified"] == ["kestrel_rampup"]


def test_retries_once_with_the_problems_when_nothing_passes(fake_llm):
    calls = fake_llm(BulletDraft(options=[INVENTED]), BulletDraft(options=[GOOD]))
    res = api.post("/api/tailor/bullet", json=request(hint="lead with microservices"))
    assert res.status_code == 200
    assert "lead with microservices" in calls[0]
    assert "'Kubernetes'" in calls[1]


def test_rejected_after_two_failures(fake_llm):
    fake_llm(BulletDraft(options=[INVENTED]), BulletDraft(options=[WRONG_ENTRY]))
    res = api.post("/api/tailor/bullet", json=request())
    assert res.status_code == 422
    assert res.json()["detail"]["error"] == "draft_rejected"


def test_unknown_entry_is_rejected(fake_llm):
    fake_llm()
    res = api.post("/api/tailor/bullet", json=request(entry="lumora_aspnet"))  # a bullet id, not an entry
    assert res.status_code == 422


def test_bank_lists_job_bullets_and_project_facts(profile):
    bank = api.get("/api/profile/bank").json()
    assert set(bank) == {"lumora", "kestrel", "flowboard"}
    assert {"id": "kestrel_rampup", "text": profile["experience"][1]["bullets"][2]["text"], "verified": False} \
        in bank["kestrel"]
    assert len(bank["flowboard"]) == len(profile["projects"][0]["facts"])
