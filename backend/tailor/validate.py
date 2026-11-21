"""Check an LLM draft against profile.yaml before it becomes a CV.

Each problem is a plain sentence, because the list goes back to the LLM for one
retry and, if that fails too, to the user.
"""
import re

from backend.models import DraftBullet, TailorDraft
from backend.profile import Record, profile_records
from backend.tailor.vocab import mentions, split_skill, tech_vocabulary

SECTION_KEYS = ("employment", "education", "project", "awards", "skills")
ENTRY_KIND = {"employment": "experience", "education": "education", "project": "project", "awards": "award"}
SECTION_OF_KIND = {kind: key for key, kind in ENTRY_KIND.items()}

# Keys that describe what is NOT confirmed (or are metadata), so they never back up a claim.
NOT_EVIDENCE = {"id", "tags", "verified", "unconfirmed", "unconfirmed_details", "bullets", "facts",
                 "built_with_ai_coding_agents"}


def validate_draft(draft: TailorDraft, profile: dict) -> list[str]:
    records = profile_records(profile)
    vocab = tech_vocabulary(profile)
    problems: list[str] = []

    if sorted(draft.section_order) != sorted(SECTION_KEYS):
        problems.append(f"section_order must contain each of {', '.join(SECTION_KEYS)} exactly once")

    for key, kind in ENTRY_KIND.items():
        seen: set[str] = set()
        for entry in getattr(draft, key):
            record = records.get(entry.source)
            if record is None or record.kind != kind:
                problems.append(f"{key}: '{entry.source}' is not a {kind} id in the profile")
                continue
            if entry.source in seen:
                problems.append(f"{key}: '{entry.source}' appears twice")
            seen.add(entry.source)
            for n, bullet in enumerate(entry.bullets, 1):
                where = f"{key} '{entry.source}' bullet {n}"
                problems += check_bullet(where, bullet, key, record, records, vocab)

    problems += _check_skills(draft, profile)
    return problems


def check_bullet(where: str, bullet: DraftBullet, key: str, entry: Record,
                  records: dict[str, Record], vocab: list[str]) -> list[str]:
    problems = []
    cited = []
    for part in bullet.source.split("+"):
        record = records.get(part)
        if record is None:
            problems.append(f"{where} cites '{part}', which is not in the profile")
        elif not _belongs(record, key, entry.id):
            problems.append(f"{where} cites '{part}', which doesn't belong to '{entry.id}'" + _hint(key))
        else:
            cited.append(record)
    if problems:
        return problems

    evidence = evidence_text(cited, entry)
    text = f"{bullet.text}\n{bullet.tech or ''}"
    for term in vocab:
        if mentions(text, term) and not mentions(evidence, term, ignore_case=True):
            problems.append(f"{where} mentions '{term}', which isn't in the sources it cites")
    for number in re.findall(r"\d+(?:[.,]\d+)*", text):
        if number not in evidence:
            problems.append(f"{where} contains the number '{number}', which isn't in the sources it cites")
    return problems


def _belongs(record: Record, key: str, entry_id: str) -> bool:
    if key in ("employment", "project"):
        child_kind = "experience_bullet" if key == "employment" else "project_fact"
        return record.kind == child_kind and record.parent == entry_id
    return record.id == entry_id


def _hint(key: str) -> str:
    return {
        "employment": " (cite that job's bullet ids)",
        "project": " (cite that project's fact ids)",
    }.get(key, " (cite the entry's own id)")


def evidence_text(cited: list[Record], entry: Record) -> str:
    """Everything a bullet may draw on: the records it cites plus its entry's stack/context."""
    parts = [flatten(r.data) for r in cited]
    parts.append(flatten({k: v for k, v in entry.data.items() if k in ("stack", "name", "context")}))
    return "\n".join(parts)


def flatten(value) -> str:
    if isinstance(value, dict):
        return "\n".join(flatten(v) for k, v in value.items() if k not in NOT_EVIDENCE)
    if isinstance(value, list):
        return "\n".join(flatten(v) for v in value)
    return "" if value is None else str(value)


def _check_skills(draft: TailorDraft, profile: dict) -> list[str]:
    skills = profile.get("skills", {})
    known = {t.lower() for item in [*skills.get("strong", []), *skills.get("listed", []),
                                    *profile["person"].get("spoken_languages", [])]
             for t in [item, *split_skill(item)]}
    not_claimed = {t.lower() for item in skills.get("not_claimed", []) for t in split_skill(item)}
    problems = []
    for group in draft.skills:
        for item in group.items:
            for token in split_skill(item):
                if token.lower() in not_claimed:
                    problems.append(f"skills '{group.label}': '{token}' is in not_claimed and must never be listed")
                elif token.lower() not in known:
                    problems.append(f"skills '{group.label}': '{token}' is not in the profile's skills "
                                    "(use the exact names from strong, listed or spoken_languages)")
    return problems
