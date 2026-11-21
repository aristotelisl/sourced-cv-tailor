"""Check an extras draft (cover letter etc.) against profile.yaml, sentence by sentence."""
import re

from backend.models import JobAnalysis
from backend.models.extras import ExtraDraft
from backend.profile import Record, profile_records
from backend.tailor.validate import flatten
from backend.tailor.vocab import mentions, split_skill, tech_vocabulary

FIRST_PERSON = re.compile(r"\b(I|I'm|I've|I'd|me|my|mine)\b")


def _numbers(text: str) -> list[str]:
    return re.findall(r"\d+(?:[.,]\d+)*", text)


def source_evidence(source: str, records: dict[str, Record], profile: dict, notes: str | None) -> str | None:
    """What a claim citing `source` may draw on; None if the id doesn't exist."""
    if source == "skills":
        skills = profile.get("skills", {})
        return "\n".join([*skills.get("strong", []), *skills.get("listed", []),
                          *profile["person"].get("spoken_languages", [])])
    if source == "notes":
        return notes or None
    record = records.get(source)
    if record is None:
        return None
    parts = [flatten(record.data)]
    if record.parent:
        parent = records[record.parent].data
        parts.append(flatten({k: v for k, v in parent.items() if k in ("stack", "name", "context", "title", "company")}))
    return "\n".join(parts)


def validate_extra(draft: ExtraDraft, profile: dict, job: JobAnalysis, notes: str | None,
                   recipient: str | None) -> tuple[list[str], list[str]]:
    """Return (problems, unverified source ids used)."""
    records = profile_records(profile)
    vocab = tech_vocabulary(profile)
    skills = profile.get("skills", {})
    have = {t.lower() for item in [*skills.get("strong", []), *skills.get("listed", [])] for t in split_skill(item)}
    person = profile["person"]
    # "Other" sentences may refer to the job and address people, but not make claims.
    context = "\n".join([job.model_dump_json(), recipient or "", flatten({k: v for k, v in person.items()
                                                                         if k != "header_extras"})])
    problems: list[str] = []
    unverified: list[str] = []
    if draft.subject:
        problems += [f"subject mentions '{t}', which isn't in the job or the profile"
                     for t in vocab if mentions(draft.subject, t) and not mentions(context, t, ignore_case=True)
                     and t.lower() not in have]

    for p, paragraph in enumerate(draft.paragraphs, 1):
        for s, sentence in enumerate(paragraph.sentences, 1):
            where = f"paragraph {p} sentence {s} (\"{sentence.text[:60]}…\")"
            text = sentence.text
            if sentence.kind == "claim":
                if not sentence.sources:
                    problems.append(f"{where} is a claim with no sources")
                    continue
                evidence = []
                for source in sentence.sources:
                    found = source_evidence(source, records, profile, notes)
                    if found is None:
                        problems.append(f"{where} cites '{source}', which is not in the profile"
                                        + (" (there are no notes)" if source == "notes" else ""))
                    else:
                        evidence.append(found)
                        if source in records and not records[source].verified and source not in unverified:
                            unverified.append(source)
                allowed = "\n".join(evidence)
                problems += [f"{where} mentions '{t}', which isn't in the sources it cites"
                             for t in vocab if mentions(text, t) and not mentions(allowed, t, ignore_case=True)]
                problems += [f"{where} contains the number '{n}', which isn't in the sources it cites"
                             for n in _numbers(text) if n not in allowed]
            else:
                for t in vocab:
                    if not mentions(text, t):
                        continue
                    if not mentions(context, t, ignore_case=True):
                        problems.append(f"{where} mentions '{t}', which isn't in the job; if it's about the candidate, "
                                        "make it a claim with sources")
                    elif t.lower() not in have and FIRST_PERSON.search(text):
                        problems.append(f"{where} talks about '{t}' in the first person, but it isn't one of "
                                        "the candidate's skills; leave it out")
                problems += [f"{where} contains the number '{n}', which isn't in the job; if it's about the candidate, "
                             "make it a claim with sources" for n in _numbers(text) if n not in context]
    return problems, unverified


def assemble_text(draft: ExtraDraft) -> str:
    return "\n\n".join(" ".join(s.text.strip() for s in p.sentences) for p in draft.paragraphs)
