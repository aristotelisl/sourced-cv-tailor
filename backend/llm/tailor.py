"""Profile + job analysis → TailorDraft, validated against the profile (one retry with feedback)."""
from functools import lru_cache

from backend.llm import client
from backend.llm.client import LLMError
from backend.models import JobAnalysis, TailorDraft, TailoredCV
from backend.paths import EXAMPLE_CV_PATH
from backend.tailor.assemble import draft_from_cv
from backend.tailor.validate import validate_draft

MAX_ATTEMPTS = 2

INSTRUCTIONS = """\
You tailor a candidate's one-page CV to a job. You get their master profile (YAML) and a structured analysis
of the job, and you return a draft: which facts to use, how to phrase them, the section order, the
skills lines, and an honest gap report. Code builds the final CV from your draft, adding job titles,
company names, links and dates from the profile, so you only write the bullets.

## Never invent experience (most important rule)
- Every bullet must be backed by the profile entries it cites in `source`. Rephrase, reorder, shorten,
  merge and reframe freely, but do not add any technology, number, metric, responsibility, scope or
  outcome that the cited sources don't state. Code checks every technology name and number against
  the cited sources and rejects the draft if one isn't there.
- `unconfirmed`, `unconfirmed_details` and comments that say something is unknown or assumed are NOT
  facts. Never use them as claims.
- Never mention or list anything in `skills.not_claimed`. If the job needs it, it goes in the gap report.
- Bullets with `verified: false` may be used when they fit the job well, but prefer verified ones.
- If the job wants something the candidate doesn't have, don't stretch a bullet to imply it. Put it in the gap report.

## How to cite sources
- employment: one entry per job, `source` = the experience id (e.g. `acme`). Each bullet cites that
  job's bullet ids, `+`-joined when a bullet merges several (e.g. `acme_apis+acme_microservices`).
  A job's `stack` and a bullet's `stack` count as evidence for its bullets.
- project: `source` = the project id. Each bullet cites that project's fact ids. Its `stack`, `name`
  and `context` count as evidence. Put a short technology list in `tech` on the first bullet only.
- education and awards: each bullet cites the entry's own id. Education bullets are a
  "Dissertation: <title>" line (MSc only) and a "Relevant Modules: <modules>" line, modules ordered by
  relevance to the job.

## Tailoring heuristics
If the profile has `preferences.tailoring_notes`, follow them: they are the candidate's own rules for
section order, what to lead with and how long each section is, and they override the defaults below.
- Default section order: Employment, Education, Project, Awards, Skills. Put Education first for
  graduate and new-grad roles, or when the candidate has little professional experience.
- Lead each entry with the bullets that match the job's must-haves, stack and keywords; use the job's
  vocabulary where the facts allow it.
- No "Profile" or summary section. Don't write header lines; code handles those.

## Length: one A4 page
Roughly: 4-6 bullets for the most recent job, 2-3 for older jobs and internships, 3-5 for a project,
1-2 per degree, 1 per award, 4-5 skills lines. Bullets are one or two lines (about 20-30 words).
British English, plain hyphens, no em dashes, the same tone as the example.

## Skills
Labelled lines (e.g. Frontend, Backend & APIs, Data & Tools, AI, Other). Items are exact names from
`skills.strong`, `skills.listed` or `person.spoken_languages`; "Python (Flask, FastAPI)" style grouping
is fine when every name inside is one of those. Put the job's stack first when the candidate has it.
Spoken languages go last, under Other.

## Coverage
One item for every must_have and nice_to_have in the job analysis, with the requirement copied verbatim.
covered = the profile clearly shows it; partial = related or weaker evidence (e.g. fewer years than asked,
listed skill with no project behind it); missing = nothing in the profile. `note` says which evidence,
or what's missing, in a few words.

## Gap report
- must_have_missing / nice_to_have_missing: job requirements the profile doesn't support, phrased so
  the candidate can see the gap (e.g. "3+ years Node.js (have personal projects + internship)").
- questions: things to ask the candidate that could close a gap or make a bullet stronger.
- flags: anything about the job worth a second look (level mismatch, unusual requirements, domain).
  Code already flags salary currency, right to work, on-site/hybrid location and years of experience,
  and suggests header lines; don't repeat those.
- unverified_used: leave empty; code fills it in.

## Example
A tailored draft for one job (it may be for a different candidate from the profile below). It shows
the format and the level of rephrasing allowed. Never take facts from it, and don't copy its choices
blindly for other roles."""


@lru_cache
def _example() -> str:
    golden = TailoredCV.model_validate_json(
        EXAMPLE_CV_PATH.read_text(encoding="utf-8"))
    # The golden file has no coverage; leave the field out rather than show an empty list.
    return draft_from_cv(golden).model_dump_json(indent=1, exclude={"coverage"})


def system_prompt(profile_yaml: str) -> str:
    return f"{INSTRUCTIONS}\n<example_draft>\n{_example()}\n</example_draft>\n\n" \
           f"<profile>\n{profile_yaml}\n</profile>"


class DraftRejected(LLMError):
    def __init__(self, problems: list[str]):
        super().__init__(f"The tailored draft broke {len(problems)} profile rule(s)")
        self.problems = problems


def draft_cv(job: JobAnalysis, profile: dict, profile_yaml: str) -> TailorDraft:
    system = system_prompt(profile_yaml)
    request = f"Tailor the CV to this job.\n<job_analysis>\n{job.model_dump_json(indent=1)}\n</job_analysis>"
    user = request
    for attempt in range(1, MAX_ATTEMPTS + 1):
        draft = client.parse(system, user, TailorDraft, task="tailor", effort="high")
        problems = validate_draft(draft, profile)
        if not problems:
            return draft
        if attempt < MAX_ATTEMPTS:
            user = (f"{request}\n\nYour previous draft broke these rules:\n"
                    + "\n".join(f"- {p}" for p in problems)
                    + f"\n\n<previous_draft>\n{draft.model_dump_json(indent=1)}\n</previous_draft>\n"
                    "Return a corrected draft. Remove or rephrase anything the cited sources don't support.")
    raise DraftRejected(problems)
