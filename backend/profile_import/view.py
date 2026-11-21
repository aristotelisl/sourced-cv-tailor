"""profile.yaml as the Profile page shows it: entries with their bullets, flags and where they came from."""
import re

import yaml

from backend.models.profile_import import ProfileView, ViewEntry, ViewItem
from backend.profile_edit.edits import profile_hash

# Gap-report answers stamp what they add or confirm (see backend/profile_edit/edits.py).
STAMP = re.compile(r"#.*?\b((?:added|confirmed) \d{4}-\d{2}-\d{2}) \(answer in the app\)")
ID_LINE = re.compile(r"^\s*-?\s*id:\s*['\"]?([\w-]+)")


def answer_stamps(text: str) -> dict[str, str]:
    """id -> 'added 2026-11-21', for records a gap-report answer added or changed.

    A stamp is a comment on some line of the record, so it belongs to the last id above it."""
    stamps: dict[str, str] = {}
    current = None
    for line in text.splitlines():
        if m := ID_LINE.match(line):
            current = m.group(1)
        if current and (m := STAMP.search(line)):
            stamps[current] = m.group(1)
    return stamps


def _s(value) -> str:
    return "" if value is None else str(value)


def _dates(item: dict, *keys: str) -> str:
    values = [_s(item.get(k)) for k in keys if item.get(k) not in (None, "")]
    return " - ".join(values)


def _join(values) -> str:
    return ", ".join(_s(v) for v in values or [])


def _items(entry: dict, key: str, stamps: dict[str, str]) -> list[ViewItem]:
    return [ViewItem(id=_s(b.get("id")), text=_s(b.get("text")), verified=b.get("verified") is not False,
                     added=stamps.get(_s(b.get("id"))))
            for b in entry.get(key) or [] if isinstance(b, dict)]


def _entry(item: dict, heading: str, subheading: str, dates: str, details: list[str], items: list[ViewItem],
           stamps: dict[str, str]) -> ViewEntry:
    rid = _s(item.get("id"))
    return ViewEntry(id=rid, heading=heading, subheading=subheading, dates=dates,
                     details=[d for d in details if d], items=items,
                     verified=item.get("verified") is not False, added=stamps.get(rid))


def profile_view(text: str) -> ProfileView:
    profile = yaml.safe_load(text) or {}
    stamps = answer_stamps(text)
    person = profile.get("person") or {}
    contact = [_s(person[k]) for k in ("location", "phone", "email", "website", "linkedin", "github")
               if person.get(k)]

    experience = [_entry(
        e, _s(e.get("title")), _s(e.get("company")) + (" (internship)" if e.get("is_internship") else ""),
        _dates(e, "start", "end"),
        [_s(e.get("location")), f"Stack: {_join(e['stack'])}" if e.get("stack") else ""],
        _items(e, "bullets", stamps), stamps) for e in profile.get("experience") or []]

    education = [_entry(
        e, _s(e.get("degree")), _s(e.get("institution")), _dates(e, "start", "end"),
        [f"Grade: {e['grade']}" if e.get("grade") else "",
         f"Dissertation: {e['dissertation']}" if e.get("dissertation") else "",
         f"Modules: {_join(e['modules'])}" if e.get("modules") else ""],
        [], stamps) for e in profile.get("education") or []]

    projects = []
    for p in profile.get("projects") or []:
        stack = p.get("stack") or {}
        tools = [t for group in stack.values() for t in group or []] if isinstance(stack, dict) else stack
        projects.append(_entry(p, _s(p.get("name")), _s(p.get("context")), _s(p.get("year")),
                               [f"Stack: {_join(tools)}" if tools else "", _s(p.get("url"))],
                               _items(p, "facts", stamps), stamps))

    awards = [_entry(a, _s(a.get("name")), _s(a.get("institution")), _s(a.get("date")), [_s(a.get("text"))],
                     [], stamps) for a in profile.get("awards") or []]

    skills = profile.get("skills") or {}
    return ProfileView(
        yaml=text, base=profile_hash(text), name=_s(person.get("name")), contact=contact,
        experience=experience, education=education, projects=projects, awards=awards,
        skills={k: [_s(s) for s in skills.get(k) or []] for k in ("strong", "listed", "not_claimed")},
        open_questions=[_s(q) for q in profile.get("open_questions") or []],
    )
