import pytest
from fastapi.testclient import TestClient

from backend.extras.validate import assemble_text, validate_extra
from backend.llm import client as llm_client
from backend.main import app
from backend.models.extras import ExtraDraft, ExtraParagraph, ExtraSentence
from tests.test_analyse import SPEC_EXAMPLE
from tests.test_tailor import uk_backend_job

api = TestClient(app)


def claim(text: str, *sources: str) -> ExtraSentence:
    return ExtraSentence(text=text, kind="claim", sources=list(sources))


def other(text: str) -> ExtraSentence:
    return ExtraSentence(text=text, kind="other", sources=[])


def draft(*sentences: ExtraSentence, subject: str | None = "Application: Backend Engineer") -> ExtraDraft:
    return ExtraDraft(subject=subject, paragraphs=[ExtraParagraph(sentences=list(sentences))])


GOOD = draft(
    other("Dear hiring team,"),
    other("Your team builds the Python services behind a payments platform."),
    claim("At Lumora I designed and maintained modular Python microservices.", "lumora_microservices"),
    claim("I also built APIs in ASP.NET for a customer-support assistant.", "lumora_aspnet"),
    claim("I won 1st place and £1,000 at the Northgate Hackathon.", "hackathon"),
    claim("I work with PostgreSQL and Docker.", "skills"),
    other("Best regards, Jordan"),
)


def check(d: ExtraDraft, notes: str | None = None, job=None):
    return validate_extra(d, _profile(), job or uk_backend_job(), notes, None)


def _profile():
    from backend.profile import load_profile
    return load_profile()


def test_good_draft_passes():
    assert check(GOOD) == ([], [])


@pytest.mark.parametrize("sentence, expected", [
    (claim("I ran the services on Kubernetes.", "lumora_microservices"), "'Kubernetes'"),
    (claim("I cut latency by 40%.", "lumora_microservices"), "'40'"),
    (claim("I built a Redis cache.", "skills"), "'Redis'"),
    (claim("I built React dashboards.", "lumora_aspnet"), "'React'"),          # the candidate has React, but not in this source
    (claim("I built services.", "made_up_id"), "'made_up_id'"),
    (claim("I built services."), "no sources"),
    (claim("I was referred by Sam.", "notes"), "no notes"),
])
def test_bad_claims_are_rejected(sentence, expected):
    problems, _ = check(draft(sentence))
    assert any(expected in p for p in problems), problems


def test_other_sentences_may_name_the_jobs_stack_but_not_claim_it():
    ok, _ = check(draft(other("The role mentions Kubernetes and AWS.")))
    assert ok == []
    problems, _ = check(draft(other("I'm keen to learn Kubernetes.")))
    assert any("first person" in p and "Kubernetes" in p for p in problems)


def test_other_sentence_with_tech_outside_the_job_must_be_a_claim():
    problems, _ = check(draft(other("I love working with Django.")))
    assert any("'Django'" in p and "make it a claim" in p for p in problems)


def test_notes_can_back_a_claim():
    notes = "Sam Lee on the payments team said they'd refer me."
    assert check(draft(claim("Sam Lee on the payments team offered to refer me.", "notes")), notes=notes) == ([], [])


def test_unverified_sources_are_reported():
    _, unverified = check(draft(claim("I ramped up quickly on a large codebase.", "kestrel_rampup")))
    assert unverified == ["kestrel_rampup"]


def test_assemble_text_joins_sentences_and_paragraphs():
    d = ExtraDraft(subject=None, paragraphs=[ExtraParagraph(sentences=[other("Hi."), other("Thanks.")]),
                                             ExtraParagraph(sentences=[other("Bye.")])])
    assert assemble_text(d) == "Hi. Thanks.\n\nBye."


# --- API (LLM mocked) -----------------------------------------------------------

@pytest.fixture
def fake_llm(monkeypatch):
    calls = []

    def install(*drafts):
        queue = list(drafts)

        def parse(system, user, output, *, task, effort="medium"):
            calls.append(user)
            return queue.pop(0)
        monkeypatch.setattr(llm_client, "parse", parse)
        return calls
    return install


def new_application() -> int:
    return api.post("/api/applications", json={"job_text": "x" * 60, "analysis": SPEC_EXAMPLE}).json()["id"]


def test_generate_saves_with_the_application(fake_llm):
    fake_llm(GOOD)
    app_id = new_application()
    r = api.post("/api/extras", json={"kind": "cover_letter", "job": uk_backend_job().model_dump(),
                                      "application_id": app_id})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["text"].startswith("Dear hiring team, Your team builds")
    saved = api.get(f"/api/applications/{app_id}").json()["extras"]
    assert [(e["id"], e["kind"], e["text"]) for e in saved] == [(body["id"], "cover_letter", body["text"])]


def test_generate_without_application_is_not_saved(fake_llm):
    fake_llm(GOOD)
    r = api.post("/api/extras", json={"kind": "about_me", "job": uk_backend_job().model_dump()})
    assert r.status_code == 200 and r.json()["id"] is None


def test_retry_then_reject(fake_llm):
    bad = draft(claim("I deployed it all on AWS.", "lumora_microservices"))
    calls = fake_llm(bad, bad)
    r = api.post("/api/extras", json={"kind": "recruiter_message", "job": uk_backend_job().model_dump()})
    assert r.status_code == 422 and r.json()["detail"]["error"] == "draft_rejected"
    assert len(calls) == 2 and "'AWS'" in calls[1]


def test_cv_bullets_and_notes_reach_the_prompt(fake_llm, golden_json):
    calls = fake_llm(GOOD)
    api.post("/api/extras", json={"kind": "referral_message", "job": uk_backend_job().model_dump(), "cv": golden_json,
                                  "recipient": "Sam (engineer)", "notes": "Met Sam at a meetup"})
    assert "[lumora_flow_builder]" in calls[0] and "Recipient: Sam (engineer)" in calls[0]
    assert "<notes>\nMet Sam at a meetup\n</notes>" in calls[0]


def test_unknown_application_fails_before_calling_the_llm(fake_llm):
    calls = fake_llm()
    r = api.post("/api/extras", json={"kind": "about_me", "job": uk_backend_job().model_dump(), "application_id": 999})
    assert r.status_code == 404 and calls == []


def test_edit_and_delete_saved_extra(fake_llm):
    fake_llm(GOOD)
    app_id = new_application()
    extra_id = api.post("/api/extras", json={"kind": "cover_letter", "job": uk_backend_job().model_dump(),
                                             "application_id": app_id}).json()["id"]
    r = api.put(f"/api/extras/{extra_id}", json={"text": "My own words.", "subject": "Hi"})
    assert (r.json()["text"], r.json()["subject"]) == ("My own words.", "Hi")
    assert api.delete(f"/api/extras/{extra_id}").status_code == 204
    assert api.get(f"/api/applications/{app_id}").json()["extras"] == []
    assert api.put(f"/api/extras/{extra_id}", json={"text": "x"}).status_code == 404


# --- rewrite with feedback ---------------------------------------------------------

def test_rewrite_sends_current_text_and_feedback(fake_llm):
    calls = fake_llm(GOOD)
    r = api.post("/api/extras", json={"kind": "cover_letter", "job": uk_backend_job().model_dump(),
                                      "previous": "Dear team, my old letter.", "feedback": "Shorter, less formal"})
    assert r.status_code == 200, r.text
    assert "Revise this cover_letter" in calls[0]
    assert "<current_text>\nDear team, my old letter.\n</current_text>" in calls[0]
    assert "<feedback>\nShorter, less formal\n</feedback>" in calls[0]
    assert "don't cite `notes`" not in calls[0]


def test_facts_in_feedback_can_back_a_claim(fake_llm):
    sailing = draft(claim("I sailed competitively for 6 years.", "notes"))
    fake_llm(sailing)
    r = api.post("/api/extras", json={"kind": "about_me", "job": uk_backend_job().model_dump(),
                                      "previous": "Old text.", "feedback": "Mention that I sailed competitively for 6 years"})
    assert r.status_code == 200, r.text


def test_current_text_is_not_evidence(fake_llm):
    # A number that only appears in the previous text (e.g. typed by hand) can't be claimed.
    bad = draft(claim("I led a team of 9.", "lumora_microservices"))
    calls = fake_llm(bad, bad)
    r = api.post("/api/extras", json={"kind": "about_me", "job": uk_backend_job().model_dump(),
                                      "previous": "I led a team of 9.", "feedback": "Keep it short"})
    assert r.status_code == 422 and len(calls) == 2


# --- cover letter PDF ----------------------------------------------------------------

LETTER = "Dear hiring team,\n\nFirst paragraph & more.\n\nSecond paragraph.\n\nKind regards,\nJordan"


def test_letter_paragraphs_keep_line_breaks():
    from backend.render.letter import letter_paragraphs
    assert letter_paragraphs(LETTER + "\n\n\n") == [
        ["Dear hiring team,"], ["First paragraph & more."], ["Second paragraph."], ["Kind regards,", "Jordan"]]


def test_letter_html_has_cv_header_date_and_escaped_text(profile):
    from datetime import date
    from backend.models.extras import LetterPdfRequest
    from backend.render.letter import render_letter_html
    req = LetterPdfRequest(text=LETTER, subject="Application: Backend Engineer", hide_contact=["github"],
                           header_extras=["UK Pre-Settled Status"])
    html = render_letter_html(req, profile["person"], date(2026, 11, 9))
    assert "<h1>Jordan Avery</h1>" in html and "9 November 2026" in html
    assert "Application: Backend Engineer" in html and "First paragraph &amp; more." in html
    assert "<p>Kind regards,<br>Jordan</p>" in html
    assert "UK Pre-Settled Status" in html and profile["person"]["github"] not in html


def test_letter_pdf_endpoint():
    from io import BytesIO
    from pypdf import PdfReader
    r = api.post("/api/extras/letter-pdf", json={"text": LETTER, "subject": "Application: X", "filename": "Cover_Letter_Test"})
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/pdf"
    assert 'filename="Cover_Letter_Test.pdf"' in r.headers["content-disposition"]
    assert r.headers["x-page-count"] == "1" and len(PdfReader(BytesIO(r.content)).pages) == 1
    assert "Kind regards" in PdfReader(BytesIO(r.content)).pages[0].extract_text()


def test_letter_pdf_rejects_bad_filename():
    assert api.post("/api/extras/letter-pdf", json={"text": "x", "filename": "../evil"}).status_code == 422
