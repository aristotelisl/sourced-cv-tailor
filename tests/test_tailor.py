import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.models import JobAnalysis, Salary, TailorDraft, TailorRequest
from backend.tailor import service
from backend.profile import Record
from backend.tailor.assemble import assemble, draft_from_cv, entry_header
from backend.tailor.rules import guaranteed_gaps, header_suggestions, professional_years, red_flags
from backend.tailor.validate import validate_draft
from backend.tailor.vocab import mentions

api = TestClient(app)


def make_job(**overrides) -> JobAnalysis:
    base = dict(company="Acme", title="Software Engineer", location="Porto, Portugal", remote="remote",
                salary=None, seniority="mid", years_required=None, must_have=[], nice_to_have=[], stack=[],
                right_to_work=None, keywords=[], role_family="frontend")
    return JobAnalysis.model_validate(base | overrides)


@pytest.fixture
def draft(golden) -> TailorDraft:
    return draft_from_cv(golden)


def first_bullet(draft: TailorDraft):
    return draft.employment[0].bullets[0]  # lumora_flow_builder


# --- vocabulary -----------------------------------------------------------------

@pytest.mark.parametrize("text, term, found", [
    ("Built it in JavaScript", "Java", False),
    ("PostgreSQL schema", "SQL", False),
    ("a go-to tool", "Go", False),
    ("services in Go", "Go", True),
    ("APIs in ASP.NET, and more", "ASP.NET", True),
    ("C# (ASP.NET) APIs", "C#", True),
    ("Next.js API routes", "Next.js", True),
])
def test_mentions(text, term, found):
    assert mentions(text, term) is found


# --- validation -----------------------------------------------------------------

def test_golden_draft_is_valid(draft, profile):
    assert validate_draft(draft, profile) == []


@pytest.mark.parametrize("addition, term", [
    (" on Kubernetes", "Kubernetes"),       # not_claimed
    (", cached in Redis", "Redis"),         # not in the profile at all
    (" with Express.js", "Express.js"),     # the candidate has it, but not in this bullet's sources
])
def test_technology_not_in_cited_sources_is_rejected(draft, profile, addition, term):
    first_bullet(draft).text += addition
    problems = validate_draft(draft, profile)
    assert any(f"'{term}'" in p for p in problems), problems


def test_invented_metric_is_rejected(draft, profile):
    first_bullet(draft).text += ", cutting build time by 40%"
    assert any("'40'" in p for p in validate_draft(draft, profile))


def test_stack_of_the_bullet_counts_as_evidence(draft, profile):
    first_bullet(draft).text = "Built a visual agent-builder dashboard in React and Vite"
    assert validate_draft(draft, profile) == []


def test_unconfirmed_details_are_not_evidence(draft, profile):
    first_bullet(draft).text = "Built a visual agent-builder canvas with React Flow"  # only in unconfirmed_details
    assert any("'React Flow'" in p for p in validate_draft(draft, profile))


@pytest.mark.parametrize("source, message", [
    ("lumora_kubernetes", "not in the profile"),
    ("kestrel_dag", "doesn't belong to 'lumora'"),
    ("lumora", "doesn't belong to 'lumora'"),
])
def test_bullet_must_cite_its_own_entry(draft, profile, source, message):
    first_bullet(draft).source = source
    assert any(message in p for p in validate_draft(draft, profile))


def test_project_bullets_must_cite_fact_ids(draft, profile):
    draft.project[0].bullets[1].source = "flowboard"
    assert any("fact ids" in p for p in validate_draft(draft, profile))


@pytest.mark.parametrize("item, message", [
    ("AWS", "not_claimed"), ("Python (Flask, Django)", "'Django' is not in the profile"), ("Rust", "not in the profile"),
])
def test_skills_must_come_from_the_profile(draft, profile, item, message):
    draft.skills[0].items.append(item)
    assert any(message in p for p in validate_draft(draft, profile))


def test_section_order_must_be_complete(draft, profile):
    draft.section_order = ["employment", "education", "skills"]
    assert any("section_order" in p for p in validate_draft(draft, profile))


def test_wrong_entry_kind_is_rejected(draft, profile):
    draft.employment[0].source = "northgate_msc"
    assert any("not a experience id" in p for p in validate_draft(draft, profile))


# --- assembly -------------------------------------------------------------------

def test_degree_grade_follows_the_degree(profile):
    edu = {**profile["education"][0], "degree": "MSc Computer Science", "grade": "Distinction"}
    with_grade = Record(id=edu["id"], kind="education", data=edu)
    without = Record(id=edu["id"], kind="education", data={k: v for k, v in edu.items() if k != "grade"})
    assert entry_header(with_grade, profile)["left"] == "MSc Computer Science (Distinction)"
    assert entry_header(without, profile)["left"] == "MSc Computer Science"


def test_assembly_rebuilds_the_golden_cv_from_the_profile(golden, draft, profile):
    for edu in profile["education"]:  # the golden CV predates degree grades
        edu.pop("grade", None)
    cv = assemble(draft, make_job(), profile, [])
    assert [s.model_dump() for s in cv.sections] == [s.model_dump() for s in golden.sections]
    assert cv.filename == "CV_Jordan_Avery_Frontend"


def test_headers_ignore_anything_the_llm_could_change(draft, profile):
    cv = assemble(draft, make_job(role_family="ai-engineer"), profile, ["UK Pre-Settled Status"])
    lumora = cv.sections[0].entries[0]
    assert (lumora.left, lumora.right) == ("Software Developer", "10/2024 - 09/2025")
    assert cv.header_extras == ["UK Pre-Settled Status"]
    assert cv.filename.endswith("_AI_Engineer")


# --- rules ----------------------------------------------------------------------

def test_uk_job_gets_presettled_suggestion(profile):
    [s] = header_suggestions(make_job(location="London, UK", remote="hybrid"), profile)
    assert s.key == "uk_presettled" and s.text == "UK Pre-Settled Status"


@pytest.mark.parametrize("location", ["Porto, Portugal", "Berlin, Germany", None])
def test_non_uk_job_gets_no_suggestion(profile, location):
    assert header_suggestions(make_job(location=location), profile) == []


def test_inr_salary_is_flagged(profile):
    job = make_job(salary=Salary(min=1_200_000, max=1_800_000, currency="INR", period="year"))
    assert any("probably for another country (India)" in f for f in red_flags(job, profile))


@pytest.mark.parametrize("currency", ["EUR", "GBP"])
def test_home_currencies_are_not_flagged(profile, currency):
    job = make_job(salary=Salary(min=40000, max=50000, currency=currency, period="year"))
    assert red_flags(job, profile) == []


def test_right_to_work_outside_uk_eu_is_flagged(profile):
    assert any("right to work" in f for f in red_flags(make_job(right_to_work="United States"), profile))
    assert red_flags(make_job(right_to_work="UK"), profile) == []


def test_onsite_abroad_is_flagged(profile):
    assert any("based there" in f for f in red_flags(make_job(location="London, UK", remote="on-site"), profile))


def test_without_preferences_location_checks_are_skipped(profile):
    del profile["preferences"]
    job = make_job(location="London, UK", remote="on-site", right_to_work="United States",
                   salary=Salary(min=1_200_000, max=1_800_000, currency="INR", period="year"))
    assert header_suggestions(job, profile) == []
    assert red_flags(job, profile) == []


def test_work_rights_labels_are_listed(profile):
    [flag] = red_flags(make_job(right_to_work="United States"), profile)
    assert flag.endswith("you have it in the UK (pre-settled) and the EU.")


def test_home_places_count_as_somewhere_you_can_work(profile):
    profile["preferences"]["work_rights"] = [{"label": "Canada", "places": ["Canada"]}]
    assert red_flags(make_job(right_to_work="Portugal"), profile) == []


def test_years_mismatch_is_flagged(profile):
    assert professional_years(profile) == 1.0
    assert any("3+ years" in f for f in red_flags(make_job(years_required="3+"), profile))
    assert red_flags(make_job(years_required="0-1"), profile) == []


def test_not_claimed_requirements_always_appear_as_gaps(golden, profile):
    job = make_job(must_have=["Python", "2+ years with AWS"], nice_to_have=["Kubernetes"], stack=["Go", "Python"])
    gaps = guaranteed_gaps(golden.gap_report.model_copy(update={"must_have_missing": [], "nice_to_have_missing": []}),
                           job, profile)
    assert gaps.must_have_missing == ["2+ years with AWS"]
    assert sorted(gaps.nice_to_have_missing) == ["Go", "Kubernetes"]


# --- service + API (LLM mocked) -------------------------------------------------

def uk_backend_job() -> JobAnalysis:
    return make_job(location="London, UK", remote="hybrid", role_family="backend",
                    salary=Salary(min=55000, max=70000, currency="GBP", period="year"),
                    must_have=["Python", "PostgreSQL"], nice_to_have=["Kubernetes", "AWS (ECS, Lambda)"],
                    stack=["Python", "PostgreSQL", "Kubernetes", "AWS"], right_to_work="UK")


def test_service_assembles_and_applies_rules(fake_llm, draft):
    draft.gap_report = draft.gap_report.model_copy(update={"must_have_missing": [], "nice_to_have_missing": []})
    fake_llm(draft)
    result = service.tailor(TailorRequest(job=uk_backend_job()))
    gaps = result.cv.gap_report
    assert [s.key for s in result.header_extra_suggestions] == ["uk_presettled"]
    assert result.cv.header_extras == []  # suggested, not applied: header extras are opt-in
    assert "Kubernetes" in gaps.nice_to_have_missing and "AWS (ECS, Lambda)" in gaps.nice_to_have_missing
    assert any("Hybrid in London" in f for f in gaps.flags)
    assert gaps.unverified_used == []
    assert result.cv.filename == "CV_Jordan_Avery_Backend"


def test_service_retries_once_with_the_problems(fake_llm, draft):
    bad = draft.model_copy(deep=True)
    bad.employment[0].bullets[0].text += " on Kubernetes"
    calls = fake_llm(bad, draft)
    service.tailor(TailorRequest(job=uk_backend_job()))
    assert len(calls) == 2
    assert "'Kubernetes'" in calls[1] and "<previous_draft>" in calls[1]


def test_api_rejects_a_draft_that_fails_twice(fake_llm, draft):
    bad = draft.model_copy(deep=True)
    bad.skills[0].items.append("AWS")
    fake_llm(bad, bad)
    r = api.post("/api/tailor", json={"job": uk_backend_job().model_dump()})
    assert r.status_code == 422
    assert r.json()["detail"]["error"] == "draft_rejected"
    assert any("AWS" in p for p in r.json()["detail"]["problems"])


def test_api_applies_requested_header_extras(fake_llm, draft):
    fake_llm(draft)
    r = api.post("/api/tailor", json={"job": uk_backend_job().model_dump(), "header_extras": ["uk_presettled"]})
    assert r.status_code == 200
    assert r.json()["cv"]["header_extras"] == ["UK Pre-Settled Status"]


@pytest.mark.parametrize("key", ["relocating", "made_up"])  # relocating is null in the profile
def test_api_rejects_unusable_header_extras(key):
    r = api.post("/api/tailor", json={"job": uk_backend_job().model_dump(), "header_extras": [key]})
    assert r.status_code == 422


# --- coverage -------------------------------------------------------------------

def test_not_claimed_requirement_is_never_covered(profile):
    from backend.models import RequirementCoverage
    from backend.tailor.rules import enforce_coverage
    items = [RequirementCoverage(requirement="AWS (ECS, Lambda)", kind="nice_to_have", status="partial", note="x"),
             RequirementCoverage(requirement="Python", kind="must_have", status="covered", note="Lumora")]
    out = enforce_coverage(items, profile)
    assert [(c.status, c.note) for c in out] == [("missing", "AWS is not claimed"), ("covered", "Lumora")]


def test_service_returns_enforced_coverage(fake_llm, draft):
    from backend.models import RequirementCoverage
    draft.coverage = [RequirementCoverage(requirement="Kubernetes", kind="nice_to_have", status="covered", note="?")]
    fake_llm(draft)
    [item] = service.tailor(TailorRequest(job=uk_backend_job())).coverage
    assert item.status == "missing"
