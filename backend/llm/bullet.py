"""Rewrite one CV bullet: three validated alternatives (one retry with feedback if none pass)."""
from backend.llm import client
from backend.llm.tailor import DraftRejected, system_prompt
from backend.models import BulletDraft, BulletRequest, DraftBullet
from backend.profile import profile_records
from backend.tailor.validate import SECTION_OF_KIND, check_bullet
from backend.tailor.vocab import tech_vocabulary

MAX_ATTEMPTS = 2

REQUEST = """\
Rewrite one bullet of the candidate's tailored CV for this job. Same rules as tailoring: cite only this
entry's ids in `source`, and use no technology, number or claim that the cited sources don't state.
Reword, merge and reframe only. Don't add outcomes, benefits or purposes ("so that…", "improving…",
"keeping X simple") unless the cited sources say them.
<job_analysis>
{job}
</job_analysis>
<entry>{entry}</entry>
<bullet_to_replace>
{bullet}
</bullet_to_replace>
<other_bullets_in_entry>
{others}
</other_bullets_in_entry>
{hint}
Return three alternatives. Make them differ in which facts they lead with or how they are framed for
the job, and don't repeat what the other bullets already say. Keep each to one or two lines (about
20-30 words). Set `tech` only if the bullet being replaced has one."""


def _request(req: BulletRequest) -> str:
    return REQUEST.format(
        job=req.job.model_dump_json(indent=1),
        entry=req.entry,
        bullet=req.bullet.model_dump_json() if req.bullet else "(none: write a new bullet for this entry)",
        others="\n".join(b.model_dump_json() for b in req.others) or "(none)",
        hint=f"<hint_from_candidate>{req.hint}</hint_from_candidate>\n" if req.hint else "",
    )


def rewrite_bullet(req: BulletRequest, profile: dict, profile_yaml: str) -> list[DraftBullet]:
    records = profile_records(profile)
    entry = records.get(req.entry)
    if entry is None or entry.kind not in SECTION_OF_KIND:
        raise ValueError(f"'{req.entry}' is not an entry id in the profile")
    key = SECTION_OF_KIND[entry.kind]
    vocab = tech_vocabulary(profile)

    system = system_prompt(profile_yaml)  # same prefix as tailoring, so the cache is shared
    request = _request(req)
    user = request
    for attempt in range(1, MAX_ATTEMPTS + 1):
        draft = client.parse(system, user, BulletDraft, task="bullet", effort="medium")
        good, problems = [], []
        for n, option in enumerate(draft.options, 1):
            found = check_bullet(f"option {n}", option, key, entry, records, vocab)
            if found:
                problems += found
            else:
                good.append(option)
        if good:
            return good
        if attempt < MAX_ATTEMPTS:
            user = (f"{request}\n\nNone of your options passed the checks:\n"
                    + "\n".join(f"- {p}" for p in problems)
                    + "\nReturn corrected options. Remove anything the cited sources don't support.")
    raise DraftRejected(problems)
