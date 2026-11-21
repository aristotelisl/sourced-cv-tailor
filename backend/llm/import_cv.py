"""Read an uploaded CV into a first profile (one retry with the checker's feedback)."""
from backend.llm import client
from backend.models.profile_import import ImportedProfile
from backend.profile_import.check import Problem, check_import, describe

MAX_ATTEMPTS = 2

INSTRUCTIONS = """\
You are setting up a candidate's master profile from their own CV. Every future CV the app makes
is built only from this profile, so it must hold exactly what the CV says, nothing more.

## Copy, don't write (most important rule)
- Copy every bullet, name, title, date and skill from the CV. Keep the CV's own wording for
  bullets: fix only line breaks, hyphenation and stray symbols from the PDF. Don't improve, merge,
  shorten or expand them, and don't add any technology, number, scope or outcome.
- Code checks every value against the CV text and rejects anything it can't find there.
- Leave a field null (or a list empty) when the CV doesn't say it. Never guess a location, a
  date, a URL or a grade.
- If something is unclear (e.g. which job a bullet belongs to, an unreadable date, a two-column
  layout that jumbled lines), make your best reading and add a short question to `questions`,
  addressed to the candidate as "you".

## Where things go
- experience: jobs and internships (is_internship true for internships and placements), one
  bullet per CV bullet, in the CV's order. `stack`: technologies the CV names for the job outside
  its bullets (e.g. a "Tech:" line), else empty.
- education: degrees and qualifications. `modules`: only modules or courses the CV lists.
  `dissertation`: the dissertation or thesis title, if given.
- projects: personal, university or open-source projects, with each bullet as a fact.
- awards: prizes, scholarships, hackathon results, certifications.
- skills: every skill and technology in the CV's skills section, one name per item, as written
  (split "Python/Django" into "Python" and "Django"). Spoken languages go in person.spoken_languages.
- Dates: MM/YYYY when the CV gives a month (Oct 2024 -> 10/2024), YYYY when it gives only a
  year, "Present" for ongoing.
- Links: the CV text may end with "Links in the document"; use them for website, linkedin,
  github and job or project urls when it's clear which is which.
- ids: short snake_case, unique: a job is its company (acme), a degree its institution and level
  (leeds_bsc), a bullet its job id plus a few words (acme_payments_api)."""


def _feedback(problems: list[Problem], draft: ImportedProfile) -> str:
    lines = [f"- {describe(p.path, draft)}: {p.message}" for p in problems]
    return ("Your previous extraction has values that aren't in the CV:\n" + "\n".join(lines) +
            "\n\nExtract again. Copy those values exactly as the CV writes them, or leave them out "
            "if the CV doesn't say them.")


def extract_profile(cv_text: str) -> tuple[ImportedProfile, list[Problem]]:
    """The best extraction and whatever the checks still object to after the retry."""
    request = f"<cv>\n{cv_text}\n</cv>"
    user = request
    for attempt in range(1, MAX_ATTEMPTS + 1):
        draft = client.parse(INSTRUCTIONS, user, ImportedProfile, task="import", effort="medium")
        problems = check_import(draft, cv_text)
        if not problems or attempt == MAX_ATTEMPTS:
            return draft, problems
        user = f"{request}\n\n{_feedback(problems, draft)}"
    raise AssertionError("unreachable")
