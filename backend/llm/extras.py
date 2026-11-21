"""Cover letters, about-me blurbs and messages, checked sentence by sentence (one retry with feedback)."""
from backend.extras.validate import validate_extra
from backend.llm import client
from backend.llm.tailor import DraftRejected
from backend.models import JobAnalysis, TailoredCV
from backend.models.extras import ExtraDraft, ExtraKind

MAX_ATTEMPTS = 2

INSTRUCTIONS = """\
You write short application texts for a job candidate, in their voice: cover letters, an about-me blurb
and messages to recruiters or contacts. You get the candidate's master profile (YAML), the job analysis,
optionally the CV tailored for the job, and optionally notes from the candidate.

## Never invent experience (most important rule)
- Write sentence by sentence. Label each one:
  - claim: anything about what the candidate did, has, knows, studied or achieved. List the profile ids that back it
    in `sources`: bullet ids, project fact ids, entry ids (job, degree, project, award), `skills` for the
    skills list, or `notes` for something the candidate wrote in the notes.
  - other: greetings, why the company or role is interesting, a request, a sign-off. No facts about the candidate.
- A claim may only state what its sources say. Code checks every technology name and number in a claim
  against its sources and rejects the text if one isn't there.
- Never mention anything in `skills.not_claimed`, `unconfirmed` or `unconfirmed_details` as something the
  candidate has. Don't talk about technologies they lack at all, even as "keen to learn": leave gaps out.
- Keep claims and references to the job in separate sentences when a sentence would mix them
  (e.g. "Your team builds payment services in Python." then a claim citing the candidate's Python work).
- Don't invent anything about the company beyond the job analysis and the candidate's notes.

## Style
British English, plain hyphens, no em dashes. Warm, direct and specific; no clichés ("I am writing to
express my interest", "passionate", "fast-paced environment"), no flattery, no exclamation marks.
Lead with the 2-3 strongest matches for this job.
- The greeting ("Dear …," / "Hi …,") is a paragraph of its own.
- The sign-off is the last paragraph, one sentence with a line break: `preferences.sign_off`
  from the profile if it is set, otherwise "Kind regards,\\n<first name>".
- Don't say the candidate has already applied, spoken to anyone or been referred unless the notes say so.

## Kinds
- cover_letter: 3-4 short paragraphs, 220-320 words. Greeting ("Dear <recipient>," or "Dear hiring team,"),
  why this role, the strongest matching evidence, a short close. `subject` is "Application: <job title>".
- about_me: the "tell us about yourself" answer for a form or interview, first person, 100-150 words,
  one or two paragraphs, no greeting or sign-off. `subject` is null.
- recruiter_message: a LinkedIn or email message to a recruiter about this role, 60-110 words, one
  greeting line, a short pitch, a clear ask (a chat or the right application route). `subject` is a short
  email subject.
- referral_message: a message to a contact at the company asking whether they would refer the candidate,
  70-120 words, friendly, with the role title and why the candidate fits, and an easy way to say no. `subject` is a short
  email subject.
"""


def system_prompt(profile_yaml: str) -> str:
    return f"{INSTRUCTIONS}\n<profile>\n{profile_yaml}\n</profile>"


def evidence_notes(notes: str | None, feedback: str | None) -> str | None:
    """Notes a claim may cite as `notes`: the candidate's notes plus any facts in the rewrite feedback (both their words)."""
    return "\n".join(x for x in (notes, feedback) if x and x.strip()) or None


def user_prompt(kind: ExtraKind, job: JobAnalysis, cv: TailoredCV | None, recipient: str | None,
                notes: str | None, previous: str | None = None, feedback: str | None = None) -> str:
    task = f"Write a {kind}."
    if previous:
        task = (f"Revise this {kind} following the candidate's feedback. Change what the feedback asks for and keep the "
                "rest close to the current text, unless the rules require a change. The current text is not "
                "evidence: every claim still needs sources from the profile, the CV bullets or the notes."
                f"\n<current_text>\n{previous}\n</current_text>")
        if feedback:
            task += (f"\n<feedback>\n{feedback}\n</feedback>\nFacts the candidate states in the feedback count as notes: "
                     "cite them as `notes`.")
    parts = [task, f"<job_analysis>\n{job.model_dump_json(indent=1)}\n</job_analysis>"]
    if cv:
        bullets = [f"- [{b.source}] {b.text}" for s in cv.sections for e in s.entries for b in e.bullets]
        parts.append("The CV sent with it leads with these bullets (cite the ids in brackets):\n"
                     f"<cv_bullets>\n" + "\n".join(bullets) + "\n</cv_bullets>")
    if recipient:
        parts.append(f"Recipient: {recipient}")
    if notes:
        parts.append(f"<notes>\n{notes}\n</notes>")
    elif not feedback:
        parts.append("There are no notes from the candidate; don't cite `notes`.")
    return "\n\n".join(parts)


def draft_extra(kind: ExtraKind, job: JobAnalysis, cv: TailoredCV | None, recipient: str | None,
                notes: str | None, profile: dict, profile_yaml: str, previous: str | None = None,
                feedback: str | None = None) -> tuple[ExtraDraft, list[str]]:
    """Return a validated draft and the unverified sources it uses. With `previous`, revise that text."""
    system = system_prompt(profile_yaml)
    request = user_prompt(kind, job, cv, recipient, notes, previous, feedback)
    notes = evidence_notes(notes, feedback)
    user = request
    for attempt in range(1, MAX_ATTEMPTS + 1):
        draft = client.parse(system, user, ExtraDraft, task="extras", effort="high")
        problems, unverified = validate_extra(draft, profile, job, notes, recipient)
        if not problems:
            return draft, unverified
        if attempt < MAX_ATTEMPTS:
            user = (f"{request}\n\nYour previous draft broke these rules:\n"
                    + "\n".join(f"- {p}" for p in problems)
                    + f"\n\n<previous_draft>\n{draft.model_dump_json(indent=1)}\n</previous_draft>\n"
                    "Return a corrected draft. Remove or rephrase anything the cited sources don't support.")
    raise DraftRejected(problems)
