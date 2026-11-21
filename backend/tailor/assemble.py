"""Draft + profile → TailoredCV. Headers, links and dates always come from the profile."""
from backend.models import Bullet, Entry, JobAnalysis, JobRef, Section, TailorDraft, TailoredCV
from backend.models.tailor import DraftBullet, DraftEntry
from backend.profile import Record, profile_records

TITLES = {"employment": "Employment", "education": "Education", "project": "Selected Project",
          "awards": "Awards", "skills": "Skills"}
FILENAME_SUFFIX = {"frontend": "Frontend", "fullstack": "Fullstack", "backend": "Backend",
                   "ai-engineer": "AI_Engineer", "data": "Data", "quant": "Quant", "systems": "Systems"}


def header_extra_texts(profile: dict, keys: list[str]) -> list[str]:
    extras = profile["person"].get("header_extras") or {}
    unknown = [k for k in keys if not extras.get(k)]
    if unknown:
        raise ValueError(f"Unknown or empty header extras: {', '.join(unknown)}")
    return [extras[k] for k in keys]


def entry_header(record: Record, profile: dict) -> dict:
    d = record.data
    if record.kind == "experience":
        header = {"left": d["title"], "right": f"{d['start']} - {d['end']}"}
        if d.get("url"):
            return header | {"middle_url": d["url"], "middle_link_text": d["company"],
                             "middle_suffix": f" - {d['location']}"}
        return header | {"middle": f"{d['company']} - {d['location']}"}
    if record.kind == "education":
        degree = f"{d['degree']} ({d['grade']})" if d.get("grade") else d["degree"]
        return {"left": degree, "middle": d["institution"], "right": f"{d['start']} - {d['end']}"}
    if record.kind == "project":
        return {"left": d["name"], "right": str(d["year"]), **_project_middle(d.get("context") or "", profile)}
    if record.kind == "award":
        header = {"left": d["name"], "middle": d["institution"], "right": d["date"]}
        return header | ({"left_url": d["url"]} if d.get("url") else {})
    raise ValueError(f"'{record.id}' is not an entry id")


def _project_middle(context: str, profile: dict) -> dict:
    """'Industry project with Acme' → link 'Acme' to the partner's URL from the education section."""
    for edu in profile.get("education", []):
        partner = edu.get("dissertation_partner") or {}
        name = partner.get("name")
        if name and partner.get("url") and context.endswith(name):
            return {"middle_prefix": context[: -len(name)], "middle_url": partner["url"], "middle_link_text": name}
    return {"middle": context} if context else {}


def assemble(draft: TailorDraft, job: JobAnalysis, profile: dict, header_extras: list[str]) -> TailoredCV:
    records = profile_records(profile)
    sections = []
    for key in draft.section_order:
        if key == "skills":
            sections.append(Section(title=TITLES[key], skills=draft.skills))
            continue
        draft_entries: list[DraftEntry] = getattr(draft, key)
        if not draft_entries:
            continue
        entries = [
            Entry(source=e.source, **entry_header(records[e.source], profile),
                  bullets=[Bullet(source=b.source, text=b.text, tech=b.tech) for b in e.bullets])
            for e in draft_entries
        ]
        title = "Selected Projects" if key == "project" and len(entries) > 1 else TITLES[key]
        sections.append(Section(title=title, entries=entries))

    name = profile["person"]["name"].replace(" ", "_")
    suffix = FILENAME_SUFFIX.get(job.role_family)
    return TailoredCV(
        job=JobRef(company=job.company, title=job.title, location=job.location),
        filename=f"CV_{name}_{suffix}" if suffix else f"CV_{name}",
        header_extras=header_extras,
        sections=sections,
        gap_report=draft.gap_report,
    )


def draft_from_cv(cv: TailoredCV) -> TailorDraft:
    """The reverse of assemble(): used to show the LLM a golden CV in draft form."""
    keys = {title: key for key, title in TITLES.items()} | {"Selected Projects": "project"}
    by_key: dict[str, list[DraftEntry]] = {k: [] for k in TITLES}
    skills = []
    order = []
    for section in cv.sections:
        key = keys[section.title]
        order.append(key)
        skills += section.skills
        by_key[key] += [
            DraftEntry(source=e.source, bullets=[DraftBullet(source=b.source, text=b.text, tech=b.tech)
                                                 for b in e.bullets])
            for e in section.entries
        ]
    return TailorDraft(coverage=[], section_order=order, employment=by_key["employment"], education=by_key["education"],
                       project=by_key["project"], awards=by_key["awards"], skills=skills,
                       gap_report=cv.gap_report)
