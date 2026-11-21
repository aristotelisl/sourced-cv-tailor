"""First-run setup: reading a CV into a profile (nothing added on the way in), and saving it."""
import base64
import io
import zipfile

import pytest
import yaml
from fastapi.testclient import TestClient

from backend import paths
from backend.main import app
from backend.models.profile_import import (
    ImportedAward, ImportedEducation, ImportedExperience, ImportedItem, ImportedPerson, ImportedProfile,
    ImportedProject,
)
from backend.profile import profile_records
from backend.profile_import import build
from backend.profile_import.check import check_import
from backend.profile_import.text import UnreadableFile, extract_text

api = TestClient(app)

# A CV for the fictional Jordan Avery, as text pulled out of a PDF.
CV_TEXT = """\
Jordan Avery
Porto, Portugal | +44 7700 900123 | jordan.avery@example.com | github.com/jordan-avery-example

EMPLOYMENT
Software Developer, Lumora — Porto, Portugal                       Oct 2024 – Sep 2025
• Designed and implemented agentic AI workflows and RAG pipelines for Lumora's customer-support
  assistant, using LlamaIndex
• Built the company website using Next.js
Software Engineering Intern, Kestrel Software — Lisbon                Jul 2023 – Sep 2023
• Developed a dependency visualiser web application for a monorepo of 300 packages

EDUCATION
MSc Computer Science, Northgate University (Distinction)                   2025 – 2026
Modules: Software Engineering, AI and Machine Learning

PROJECTS
FlowBoard (MSc dissertation)
• Turns written requirements documents into editable process diagrams

AWARDS
Northgate Hackathon, 1st place (05/2026)

SKILLS
Python, TypeScript, React, Next.js, Docker, LlamaIndex
Languages: Portuguese (Native), English (Fluent)
"""


def item(id, text):
    return ImportedItem(id=id, text=text)


def good_draft(**changes) -> ImportedProfile:
    draft = ImportedProfile(
        person=ImportedPerson(name="Jordan Avery", location="Porto, Portugal", phone="+44 7700 900123",
                              email="jordan.avery@example.com", website="", linkedin="",
                              github="https://github.com/jordan-avery-example",
                              spoken_languages=["Portuguese (Native)", "English (Fluent)"]),
        education=[ImportedEducation(id="northgate_msc", degree="MSc Computer Science",
                                     institution="Northgate University", location="", start="2025", end="2026",
                                     grade="Distinction", dissertation="",
                                     modules=["Software Engineering", "AI and Machine Learning"])],
        experience=[
            ImportedExperience(id="lumora", title="Software Developer", company="Lumora", url="",
                               location="Porto, Portugal", start="10/2024", end="09/2025", is_internship=False,
                               stack=[], bullets=[
                                   item("lumora_agentic_rag", "Designed and implemented agentic AI workflows and "
                                        "RAG pipelines for Lumora's customer-support assistant, using LlamaIndex"),
                                   item("lumora_website", "Built the company website using Next.js")]),
            ImportedExperience(id="kestrel", title="Software Engineering Intern", company="Kestrel Software",
                               url="", location="Lisbon", start="07/2023", end="09/2023", is_internship=True,
                               stack=[], bullets=[item("kestrel_visualiser", "Developed a dependency visualiser web "
                                                       "application for a monorepo of 300 packages")]),
        ],
        projects=[ImportedProject(id="flowboard", name="FlowBoard", context="MSc dissertation", url="",
                                  year="", stack=[], facts=[item("flowboard_overview", "Turns written requirements "
                                                                   "documents into editable process diagrams")])],
        awards=[ImportedAward(id="hackathon", name="Northgate Hackathon", institution="", date="05/2026",
                              text="1st place")],
        skills=["Python", "TypeScript", "React", "Next.js", "Docker", "LlamaIndex"],
        questions=[],
    )
    return draft.model_copy(update=changes)


def with_bullet(draft: ImportedProfile, text: str) -> ImportedProfile:
    draft = draft.model_copy(deep=True)
    draft.experience[0].bullets[1].text = text
    return draft


@pytest.fixture
def profile_copy(tmp_path, monkeypatch):
    """Point the app at a copy of the sample profile, so nothing real is written."""
    copy = tmp_path / "profile.yaml"
    copy.write_text(paths.EXAMPLE_PROFILE_PATH.read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
    monkeypatch.setattr(paths, "PROFILE_PATH", copy)
    return copy


# --- checks against the CV ------------------------------------------------------------

def test_a_faithful_extraction_passes():
    assert check_import(good_draft(), CV_TEXT) == []


@pytest.mark.parametrize("bad, expect", [
    (lambda d: with_bullet(d, "Built the company website using Next.js, cutting load time by 40%"), "40"),
    (lambda d: with_bullet(d, "Built the company website using Next.js for 20 clients"), "20"),  # 2025 isn't 20
    (lambda d: with_bullet(d, "Built the company website using Next.js and GraphQL on Kubernetes"), "kubernetes"),
    (lambda d: d.model_copy(update={"skills": [*d.skills, "AWS"]}), "AWS"),
    (lambda d: d.model_copy(update={"person": d.person.model_copy(update={"linkedin": "https://linkedin.com/in/x"})}),
     "linkedin.com/in/x"),
    (lambda d: d.model_copy(update={"person": d.person.model_copy(update={"email": "j@example.org"})}),
     "j@example.org"),
])
def test_anything_not_in_the_cv_is_caught(bad, expect):
    problems = check_import(bad(good_draft()), CV_TEXT)
    assert len(problems) == 1 and expect in problems[0].message


def test_tidying_a_bullet_is_allowed():
    tidied = with_bullet(good_draft(), "Built the company website, using Next.js")
    assert check_import(tidied, CV_TEXT) == []


def test_untraceable_bullets_stay_but_unverified_and_unknown_skills_go():
    draft = with_bullet(good_draft(skills=["Python", "AWS"]), "Led a team of 5 engineers")
    data, flagged, warnings = build.resolve(draft, check_import(draft, CV_TEXT))
    profile = yaml.safe_load(build.to_yaml(data, flagged, ["Which year did FlowBoard finish?"]))

    bullets = profile["experience"][0]["bullets"]
    assert bullets[1] == {"id": "lumora_website", "text": "Led a team of 5 engineers", "verified": False}
    assert profile["skills"]["listed"] == ["Python"]
    assert "AWS" not in str(profile["skills"])
    assert profile["open_questions"] == ["Which year did FlowBoard finish?"]
    assert len(warnings) == 2 and any("Kept, marked unverified" in w for w in warnings)


def test_built_profile_has_the_shape_the_app_reads():
    data, flagged, _ = build.resolve(good_draft(), [])
    text = build.to_yaml(data, flagged, [])
    profile = yaml.safe_load(text)
    records = profile_records(profile)
    assert {"lumora", "lumora_website", "kestrel_visualiser", "northgate_msc", "flowboard", "flowboard_overview",
            "hackathon"} <= set(records)
    assert profile["experience"][1]["is_internship"] is True
    assert "is_internship" not in profile["experience"][0]
    # Skills used in a bullet count as strong; Python and Docker only appear in the skills list.
    assert profile["skills"]["strong"] == ["Next.js", "LlamaIndex"]
    assert profile["skills"]["listed"] == ["Python", "TypeScript", "React", "Docker"]
    assert "stack" not in profile["projects"][0]  # empty values are left out
    assert text.startswith("# Master profile")


def test_duplicate_and_odd_ids_are_fixed():
    draft = good_draft()
    draft.experience[1].id = "lumora"           # clashes with the first job
    draft.experience[1].bullets[0].id = "Visualiser!"
    data, flagged, _ = build.resolve(draft, [])
    profile = yaml.safe_load(build.to_yaml(data, flagged, []))
    assert profile["experience"][1]["id"] == "lumora_2"
    assert profile["experience"][1]["bullets"][0]["id"] == "lumora_2_visualiser"


# --- the import endpoint ----------------------------------------------------------------

def test_import_retries_once_with_the_problems(fake_llm):
    calls = fake_llm(with_bullet(good_draft(), "Built the website for 2 million users"), good_draft())
    res = api.post("/api/profile/import", json={"text": CV_TEXT})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["warnings"] == []
    assert body["counts"] == {"jobs": 2, "bullets": 3, "education": 1, "projects": 1, "awards": 1, "skills": 6}
    assert len(calls) == 2 and "the number 2 isn't in the CV" in calls[1]


def test_import_keeps_what_the_retry_still_gets_wrong_flagged(fake_llm):
    bad = with_bullet(good_draft(), "Built the website for 2 million users")
    fake_llm(bad, bad)
    body = api.post("/api/profile/import", json={"text": CV_TEXT}).json()
    assert "verified: false" in body["yaml"] and len(body["warnings"]) == 1


def test_import_of_a_docx(fake_llm):
    calls = fake_llm(good_draft())
    res = api.post("/api/profile/import", json={"filename": "cv.docx", "content_base64": base64.b64encode(
        docx(CV_TEXT.splitlines(), links=["https://linkedin.com/in/jordan-avery-example"])).decode()})
    assert res.status_code == 200, res.text
    assert "Software Developer, Lumora" in calls[0]
    assert "Links in the document:\nhttps://linkedin.com/in/jordan-avery-example" in calls[0]


@pytest.mark.parametrize("payload", [
    {},
    {"text": "too short"},
    {"filename": "cv.doc", "content_base64": base64.b64encode(b"x" * 100).decode()},
    {"filename": "cv.pdf", "content_base64": "not base64!"},
])
def test_unreadable_uploads_are_refused_before_any_model_call(payload, fake_llm):
    calls = fake_llm()
    res = api.post("/api/profile/import", json=payload)
    assert res.status_code == 422 and calls == []


def test_pdf_text_and_hidden_links(profile, golden):
    from backend.render import render_pdf
    pdf = render_pdf(golden, profile["person"]).pdf
    text = extract_text("cv.pdf", pdf)
    assert "Jordan Avery" in text


def test_scanned_pdf_says_to_paste_text():
    with pytest.raises(UnreadableFile, match="paste the text"):
        extract_text("cv.txt", b"   \n  ")


def docx(lines: list[str], links: list[str] = ()) -> bytes:
    w = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
    paras = "".join(f"<w:p><w:r><w:t xml:space=\"preserve\">{escape(line)}</w:t></w:r></w:p>" for line in lines)
    rels = "".join(f'<Relationship Id="r{i}" Type="hyperlink" Target="{url}" TargetMode="External"/>'
                   for i, url in enumerate(links))
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        z.writestr("word/document.xml", f"<w:document {w}><w:body>{paras}</w:body></w:document>")
        z.writestr("word/_rels/document.xml.rels",
                   f'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">{rels}'
                   "</Relationships>")
    return out.getvalue()


def escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# --- status, sample, save -----------------------------------------------------------------

def test_status_follows_the_profile(profile_copy):
    assert api.get("/api/profile/status").json() == {"state": "example", "name": "Jordan Avery"}
    profile_copy.unlink()
    assert api.get("/api/profile/status").json()["state"] == "missing"
    assert api.post("/api/profile/use-example").json()["state"] == "example"
    assert profile_copy.read_text(encoding="utf-8") == paths.EXAMPLE_PROFILE_PATH.read_text(encoding="utf-8")


def test_saving_over_the_sample_needs_no_backup_but_your_own_gets_one(profile_copy):
    data, flagged, _ = build.resolve(good_draft(person=good_draft().person.model_copy(update={"name": "Sam Lee"})), [])
    text = build.to_yaml(data, flagged, [])

    res = api.post("/api/profile/save", json={"yaml": text}).json()
    assert res == {"status": {"state": "own", "name": "Sam Lee"}, "backup": None}
    assert profile_copy.read_text(encoding="utf-8") == text

    res = api.post("/api/profile/save", json={"yaml": text.replace("Sam Lee", "Sam K. Lee")}).json()
    backups = list(profile_copy.parent.glob("profile.backup-*.yaml"))
    assert res["backup"] and len(backups) == 1 and "Sam Lee" in backups[0].read_text(encoding="utf-8")


@pytest.mark.parametrize("text, expect", [
    ("person: [", "Not valid YAML"),
    ("- a list", "mapping"),
    ("person: {location: Porto}", "person.name"),
    ("person: {name: A}\nexperience: [{title: Dev}]", "needs an id"),
    ("person: {name: A}\nawards: [{id: x, name: A}, {id: x, name: B}]", "duplicate id"),
    ("person: {name: A}\nawards: [{id: My Award, name: A}]", "valid id"),
])
def test_save_refuses_a_profile_the_app_cant_load(profile_copy, text, expect):
    before = profile_copy.read_text(encoding="utf-8")
    res = api.post("/api/profile/save", json={"yaml": text})
    assert res.status_code == 422 and expect in str(res.json()["detail"]["problems"])
    assert profile_copy.read_text(encoding="utf-8") == before
