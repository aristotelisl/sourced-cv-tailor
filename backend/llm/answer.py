"""The user's answer to a gap-report question → a few typed edits to profile.yaml (one retry with feedback)."""
from backend.llm import client
from backend.llm.client import LLMError
from backend.models.profile_edit import ProfileAnswerDraft, ProfileAnswerRequest
from backend.profile_edit.edits import validate_edits

MAX_ATTEMPTS = 2

INSTRUCTIONS = """\
The candidate answered a question from a CV gap report. Turn the answer into a small set of edits to
their master profile (profile.yaml, below), which every future CV is built from. The candidate reviews
a diff before anything is saved.

## Only record what the candidate said (most important rule)
- Every edit must be backed by the answer. Don't add any technology, number, scope, responsibility or
  outcome that isn't in the candidate's words. Code checks that every technology and number in your text is in
  the answer (or already in the record you extend) and rejects the edits otherwise.
- Record vague answers vaguely. "Used it a bit at work" is a skill note, not an achievement bullet.
- `quote`: the words of the answer that support the edit, copied exactly (code checks this).
- If the answer is "no", "don't know", unclear, or adds nothing new, return no edits and say why in
  the summary.
- The summary is shown to the candidate: address them as "you".

## Choosing edits (the fewest that capture the answer)
- add_experience_bullet: a concrete thing the candidate did at a job. Write it as a CV-ready bullet in the style
  of that job's existing bullets (past tense, British English, plain hyphens, no em dashes). id:
  `<job id>_<short_name>`.
- add_project_fact: something about a project, as a terse note like the existing facts. id:
  `<prefix of the existing fact ids>_<short_name>`.
- add_skill: a technology the candidate says they have used. 'strong' only if the answer says it was used
  professionally or in a substantial project, otherwise 'listed'. Use the usual name of the
  technology. A skill moves out of not_claimed automatically when the candidate confirms it.
- set_skill_note: where and how the candidate used a skill, in a few words from the answer (replaces any
  existing note for that skill).
- add_stack: a technology used at a job generally (target the experience id) or for one existing
  bullet (target that bullet's id). That makes it evidence for those bullets.
- add_module: a university module (target the education id).
- set_grade: a degree's grade or classification as the candidate states it, e.g. "Distinction" or "First-Class
  Honours" (target the education id; replaces any existing grade). Only for a degree the answer gives a
  grade for; never infer one.
- verify: the candidate confirms a bullet that is marked `verified: false` (target its id, empty text).
- Don't duplicate what the profile already says, and don't reuse existing ids."""


def system_prompt(profile_yaml: str) -> str:
    return f"{INSTRUCTIONS}\n\n<profile>\n{profile_yaml}\n</profile>"


class EditsRejected(LLMError):
    def __init__(self, problems: list[str]):
        super().__init__(f"The proposed profile edits broke {len(problems)} rule(s)")
        self.problems = problems


def draft_edits(req: ProfileAnswerRequest, profile: dict, profile_yaml: str) -> ProfileAnswerDraft:
    system = system_prompt(profile_yaml)
    job = f"\n<job>{req.job.title} at {req.job.company or 'an unnamed company'}</job>" if req.job else ""
    request = f"<question>{req.question}</question>{job}\n<answer>{req.answer}</answer>"
    user = request
    for attempt in range(1, MAX_ATTEMPTS + 1):
        draft = client.parse(system, user, ProfileAnswerDraft, task="answer", effort="medium")
        problems = validate_edits(draft.edits, req.answer, profile)
        if not problems:
            return draft
        if attempt < MAX_ATTEMPTS:
            user = (f"{request}\n\nYour previous edits broke these rules:\n"
                    + "\n".join(f"- {p}" for p in problems)
                    + f"\n\n<previous_edits>\n{draft.model_dump_json(indent=1)}\n</previous_edits>\n"
                    "Return corrected edits. Drop anything the answer doesn't support.")
    raise EditsRejected(problems)
