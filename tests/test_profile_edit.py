"""Answering questions into profile.yaml: checks, comment-preserving edits, and the propose/apply API."""
from datetime import date

import pytest
import yaml
from fastapi.testclient import TestClient

from backend import paths
from backend.main import app
from backend.models.profile_edit import ProfileAnswerDraft, ProfileEdit
from backend.profile_edit import yaml_io
from backend.profile_edit.edits import apply_edits, profile_hash, validate_edits

api = TestClient(app)
TODAY = date(2026, 11, 18)
QUESTION = "Have you used Docker at Lumora?"
ANSWER = "Yes, we ran all the Python microservices in Docker containers at Lumora, about 12 of them."


def edit(op, target, text="", id=None, quote="Yes") -> ProfileEdit:
    return ProfileEdit(op=op, target=target, id=id, text=text, quote=quote)


@pytest.fixture
def profile_text() -> str:
    return paths.PROFILE_PATH.read_text(encoding="utf-8")


@pytest.fixture
def profile_copy(tmp_path, monkeypatch, profile_text):
    """Point the app at a copy of profile.yaml, so the real one is never written."""
    copy = tmp_path / "profile.yaml"
    copy.write_text(profile_text, encoding="utf-8", newline="\n")
    monkeypatch.setattr(paths, "PROFILE_PATH", copy)
    return copy


# --- round trip and applying ------------------------------------------------------

def test_unchanged_profile_round_trips_exactly(profile_text):
    assert yaml_io.dump(yaml_io.load(profile_text)) == profile_text


def changed_lines(old: str, new: str) -> tuple[list[str], list[str]]:
    a, b = old.splitlines(), new.splitlines()
    return [x for x in a if x not in b], [x for x in b if x not in a]


def test_new_bullet_goes_inside_the_job_and_keeps_comments(profile_text):
    new = apply_edits(profile_text, [edit("add_experience_bullet", "lumora", "Containerised the Python "
                                          "microservices with Docker", id="lumora_docker")], TODAY)
    removed, added = changed_lines(profile_text, new)
    assert removed == []
    assert added == ["      - id: lumora_docker",
                     "        text: Containerised the Python microservices with Docker",
                     "        verified: true # added 2026-11-18 (answer in the app)"]
    data = yaml.safe_load(new)
    assert data["experience"][0]["bullets"][-1]["id"] == "lumora_docker"
    # The blank line still separates the jobs, after the new bullet.
    assert "(answer in the app)\n\n  - id: kestrel" in new


def test_skill_confirmed_from_not_claimed_moves_out_of_it(profile_text):
    new = yaml.safe_load(apply_edits(profile_text, [edit("add_skill", "listed", "Go")], TODAY))
    assert "Go" in new["skills"]["listed"]
    assert "Go" not in new["skills"]["not_claimed"]


def test_skill_moved_from_listed_to_strong(profile_text):
    new = yaml.safe_load(apply_edits(profile_text, [edit("add_skill", "strong", "SQL")], TODAY))
    assert "SQL" in new["skills"]["strong"] and "SQL" not in new["skills"]["listed"]


def test_skill_note_is_added_before_the_next_comment(profile_text):
    new = apply_edits(profile_text, [edit("set_skill_note", "Docker", "Ran Lumora's microservices")], TODAY)
    assert "    Docker: Ran Lumora's microservices\n  # Never add these unless I confirm:" in new


def test_stack_module_and_verify(profile_text):
    new = apply_edits(profile_text, [
        edit("add_stack", "lumora_microservices", "Docker"),
        edit("add_module", "fernhill_bsc", "Statistics"),
        edit("verify", "kestrel_rampup"),
    ], TODAY)
    data = yaml.safe_load(new)
    assert data["experience"][0]["bullets"][3]["stack"] == ["Docker"]
    assert data["education"][1]["modules"][-1] == "Statistics"
    assert data["experience"][1]["bullets"][2]["verified"] is True
    assert "verified: true # confirmed 2026-11-18" in new
    assert "reasonable framing, but confirm" not in new


def test_grade_goes_after_the_dates_and_can_be_replaced(profile_text):
    new = apply_edits(profile_text, [edit("set_grade", "northgate_msc", "Merit")], TODAY)
    msc = yaml.safe_load(new)["education"][0]
    assert msc["grade"] == "Merit"
    assert list(msc).index("grade") == list(msc).index("end") + 1
    assert "grade: Merit # added 2026-11-18 (answer in the app)" in new
    newer = yaml.safe_load(apply_edits(new, [edit("set_grade", "northgate_msc", "Distinction")], TODAY))
    assert newer["education"][0]["grade"] == "Distinction"


# --- checks -----------------------------------------------------------------------

GRADE_ANSWER = "I got a distinction in my MSc and a first in my BSc"


@pytest.mark.parametrize("target, grade", [("northgate_msc", "Distinction"), ("fernhill_bsc", "First-Class Honours")])
def test_grade_from_the_answer_passes(profile, target, grade):
    assert validate_edits([edit("set_grade", target, grade, quote="I got a distinction")], GRADE_ANSWER, profile) == []


@pytest.mark.parametrize("bad, message", [
    (edit("set_grade", "northgate_msc", "Merit", quote="I got a distinction"), "isn't in the answer"),
    (edit("set_grade", "northgate_msc", "Honours", quote="I got a distinction"), "isn't in the answer"),
    (edit("set_grade", "northgate_msc", "Distinction (78%)", quote="I got a distinction"), "'78'"),
    (edit("set_grade", "lumora", "Distinction", quote="I got a distinction"), "of kind education"),
])
def test_unsupported_grades_are_rejected(profile, bad, message):
    problems = validate_edits([bad], GRADE_ANSWER, profile)
    assert any(message in p for p in problems), problems


def test_valid_edits_pass(profile):
    edits = [edit("add_experience_bullet", "lumora", "Ran 12 Python microservices in Docker containers",
                  id="lumora_docker", quote="we ran all the Python microservices in Docker containers"),
             edit("add_stack", "lumora", "Docker"), edit("set_skill_note", "Docker", "Lumora microservices")]
    assert validate_edits(edits, ANSWER, profile) == []


@pytest.mark.parametrize("bad, message", [
    (edit("add_skill", "listed", "Docker", quote="we used Docker"), "word for word"),
    (edit("add_experience_bullet", "lumora", "Deployed services to Kubernetes", id="lumora_k8s"), "'Kubernetes'"),
    (edit("add_experience_bullet", "lumora", "Ran 40 microservices", id="lumora_ms"), "'40'"),
    (edit("add_experience_bullet", "lumora", "Ran services", id="lumora_aspnet"), "already exists"),
    (edit("add_experience_bullet", "lumora", "Ran services", id="Bad-Id"), "snake_case"),
    (edit("add_experience_bullet", "kestrel_dag", "Ran services", id="x_y"), "of kind experience, not 'kestrel_dag'"),
    (edit("add_skill", "listed", "Rust"), "isn't mentioned in the answer"),
    (edit("add_skill", "expert", "Docker"), "'strong' or 'listed'"),
    (edit("set_skill_note", "Rust", "x"), "not in skills"),
    (edit("verify", "lumora_aspnet"), "already verified"),
])
def test_unsupported_edits_are_rejected(profile, bad, message):
    problems = validate_edits([bad], ANSWER, profile)
    assert any(message in p for p in problems), problems


def test_skill_in_the_answer_may_be_added_even_if_not_claimed(profile):
    assert validate_edits([edit("add_skill", "listed", "Go", quote="I wrote Go")], "I wrote Go at uni", profile) == []


# --- propose / apply API ----------------------------------------------------------

def docker_draft() -> ProfileAnswerDraft:
    return ProfileAnswerDraft(summary="Adds Docker to Lumora.", edits=[edit("add_stack", "lumora", "Docker",
                                                                           quote="Docker containers at Lumora")])


def test_propose_returns_a_diff_and_saves_nothing(fake_llm, profile_copy, profile_text):
    fake_llm(docker_draft())
    res = api.post("/api/profile/answer", json={"question": QUESTION, "answer": ANSWER})
    assert res.status_code == 200
    body = res.json()
    assert "+    stack: [Docker]" in body["diff"]
    assert body["base"] == profile_hash(profile_text)
    assert profile_copy.read_text(encoding="utf-8") == profile_text


def test_propose_retries_then_rejects(fake_llm, profile_copy):
    bad = ProfileAnswerDraft(summary="", edits=[edit("add_skill", "listed", "Rust")])
    calls = fake_llm(bad, bad)
    res = api.post("/api/profile/answer", json={"question": QUESTION, "answer": ANSWER})
    assert res.status_code == 422
    assert "isn't mentioned in the answer" in calls[1]


def test_apply_writes_the_previewed_edits(profile_copy, profile_text):
    req = {"question": QUESTION, "answer": ANSWER, "edits": [e.model_dump() for e in docker_draft().edits],
           "base": profile_hash(profile_text)}
    res = api.post("/api/profile/apply", json=req)
    assert res.status_code == 200
    saved = profile_copy.read_text(encoding="utf-8")
    assert yaml.safe_load(saved)["experience"][0]["stack"] == ["Docker"]
    assert "# Never add these unless I confirm:" in saved
    # Applying again against the old hash is refused: the file has changed.
    assert api.post("/api/profile/apply", json=req).status_code == 409


def test_apply_rechecks_the_edits(profile_copy, profile_text):
    req = {"question": QUESTION, "answer": ANSWER, "base": profile_hash(profile_text),
           "edits": [edit("add_skill", "strong", "Kubernetes", quote="Yes").model_dump()]}
    res = api.post("/api/profile/apply", json=req)
    assert res.status_code == 422
    assert profile_copy.read_text(encoding="utf-8") == profile_text
