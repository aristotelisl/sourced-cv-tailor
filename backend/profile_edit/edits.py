"""Check proposed profile edits against the user's answer, and apply them to profile.yaml's text.

The rule for the profile is the same as for CVs, one level up: nothing goes in that the
user didn't say. Every edit quotes the answer, and every technology and number it adds must
appear in the answer (or already be in the record it extends).
"""
import difflib
import hashlib
import re
from datetime import date

import yaml
from ruamel.yaml.comments import CommentedMap

from backend.models.profile_edit import ProfileEdit
from backend.profile import Record, profile_records
from backend.profile_edit import yaml_io
from backend.tailor.validate import flatten
from backend.tailor.vocab import mentions, split_skill, tech_vocabulary

ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
TARGET_KIND = {
    "add_experience_bullet": {"experience"},
    "add_project_fact": {"project"},
    "add_module": {"education"},
    "set_grade": {"education"},
    "add_stack": {"experience", "experience_bullet"},
    "verify": {"experience_bullet", "project_fact", "experience", "project", "education", "award"},
}
SKILL_LEVELS = ("strong", "listed")
# Words that don't identify a grade on their own: "First-Class Honours" needs "first" in the answer.
GRADE_FILLER = {"class", "honours", "hons", "with", "degree", "grade", "the", "and"}


def profile_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _norm(text: str) -> str:
    return " ".join(text.replace("’", "'").lower().split())


def validate_edits(edits: list[ProfileEdit], answer: str, profile: dict) -> list[str]:
    records = profile_records(profile)
    vocab = tech_vocabulary(profile)
    skills = profile.get("skills", {})
    problems: list[str] = []
    new_ids: set[str] = set()
    new_skills = {_norm(e.text) for e in edits if e.op == "add_skill"}

    for n, edit in enumerate(edits, 1):
        where = f"edit {n} ({edit.op})"
        if not edit.quote.strip() or _norm(edit.quote) not in _norm(answer):
            problems.append(f"{where}: the quote must be copied word for word from the answer")
        if edit.op != "verify" and not edit.text.strip():
            problems.append(f"{where}: text is empty")

        record = records.get(edit.target)
        if edit.op in TARGET_KIND:
            if record is None or record.kind not in TARGET_KIND[edit.op]:
                problems.append(f"{where}: target must be the id of a profile record of kind "
                                f"{' or '.join(sorted(TARGET_KIND[edit.op]))}, not '{edit.target}'")
                continue
        elif edit.op == "add_skill" and edit.target not in SKILL_LEVELS:
            problems.append(f"{where}: target must be 'strong' or 'listed'")
        elif edit.op == "set_skill_note" and not (_is_skill(edit.target, skills) or _norm(edit.target) in new_skills):
            problems.append(f"{where}: '{edit.target}' is not in skills.strong or skills.listed")

        if edit.op in ("add_experience_bullet", "add_project_fact"):
            if not edit.id or not ID_PATTERN.match(edit.id):
                problems.append(f"{where}: needs a new snake_case id")
            elif edit.id in records or edit.id in new_ids:
                problems.append(f"{where}: id '{edit.id}' already exists")
            else:
                new_ids.add(edit.id)
        elif edit.id:
            problems.append(f"{where}: only new bullets and facts take an id")

        if edit.op == "verify":
            if record is not None and record.verified:
                problems.append(f"{where}: '{edit.target}' is already verified")
            continue
        if edit.op in ("add_skill", "add_stack"):
            name = split_skill(edit.text)[0] if split_skill(edit.text) else edit.text
            if not mentions(answer, name, ignore_case=True):
                problems.append(f"{where}: '{name}' isn't mentioned in the answer")
            if edit.op == "add_skill" and edit.text in skills.get(edit.target, []):
                problems.append(f"{where}: '{edit.text}' is already in skills.{edit.target}")
            continue
        if edit.op == "set_grade" and not _grade_in_answer(edit.text, answer):
            problems.append(f"{where}: the grade '{edit.text}' isn't in the answer")
        problems += _check_terms(where, edit.text, answer, record, vocab)
    return problems


def _grade_in_answer(grade: str, answer: str) -> bool:
    words = [w for w in re.findall(r"[a-z0-9:.]+", grade.lower()) if w not in GRADE_FILLER]
    return bool(words) and any(re.search(rf"(?<![a-z0-9]){re.escape(w)}(?![a-z0-9])", answer.lower()) for w in words)


def _is_skill(name: str, skills: dict) -> bool:
    return any(_norm(name) == _norm(s) for level in SKILL_LEVELS for s in skills.get(level, []))


def _check_terms(where: str, text: str, answer: str, record: Record | None, vocab: list[str]) -> list[str]:
    """New text may only name technologies and numbers from the answer or the record it extends."""
    existing = flatten({k: v for k, v in record.data.items() if k in ("stack", "name", "context", "text")}) \
        if record else ""
    evidence = f"{answer}\n{existing}"
    problems = []
    for term in vocab:
        if mentions(text, term) and not mentions(evidence, term, ignore_case=True):
            problems.append(f"{where}: '{term}' isn't in the answer")
    for number in re.findall(r"\d+(?:[.,]\d+)*", text):
        if number not in evidence:
            problems.append(f"{where}: the number '{number}' isn't in the answer")
    return problems


def _find(doc: CommentedMap, rid: str) -> CommentedMap:
    for group, children in (("experience", "bullets"), ("education", None), ("projects", "facts"), ("awards", None)):
        for item in doc.get(group) or []:
            if item.get("id") == rid:
                return item
            for child in (item.get(children) or []) if children else []:
                if child.get("id") == rid:
                    return child
    raise KeyError(rid)


def _apply_one(doc: CommentedMap, edit: ProfileEdit, stamp: str) -> None:
    if edit.op == "add_experience_bullet":
        item = CommentedMap(id=edit.id, text=edit.text, verified=True)
        yaml_io.append_item(_find(doc, edit.target)["bullets"], item, stamp)
    elif edit.op == "add_project_fact":
        yaml_io.append_item(_find(doc, edit.target)["facts"], CommentedMap(id=edit.id, text=edit.text), stamp)
    elif edit.op == "add_skill":
        skills = doc["skills"]
        for group in ("strong", "listed", "not_claimed"):  # moving a skill takes it out of the other lists
            items = skills.get(group) or []
            for i in reversed(range(len(items))):
                if _norm(items[i]) == _norm(edit.text):
                    del items[i]
        skills[edit.target].append(edit.text)
    elif edit.op == "set_skill_note":
        skills = doc["skills"]
        if skills.get("notes") is None:
            yaml_io.set_key(skills, "notes", CommentedMap())
        notes = skills["notes"]
        key = next((k for k in notes if _norm(k) == _norm(edit.target)), edit.target)
        yaml_io.set_key(notes, key, edit.text)
    elif edit.op == "add_module":
        node = _find(doc, edit.target)
        if node.get("modules") is None:
            yaml_io.set_key(node, "modules", yaml_io.flow_seq([]))
        node["modules"].append(edit.text)
    elif edit.op == "add_stack":
        node = _find(doc, edit.target)
        if node.get("stack") is None:
            keys = list(node)
            after = keys.index("text") + 1 if "text" in keys else keys.index("end") + 1 if "end" in keys else len(keys)
            node.insert(after, "stack", yaml_io.flow_seq([]))
        if edit.text not in node["stack"]:
            node["stack"].append(edit.text)
    elif edit.op == "set_grade":
        node = _find(doc, edit.target)
        if "grade" in node:
            node["grade"] = edit.text
        else:  # right after the dates, where a reader looks for it
            keys = list(node)
            node.insert(keys.index("end") + 1 if "end" in keys else len(keys), "grade", edit.text)
        yaml_io.set_eol_comment(node, "grade", stamp)
    elif edit.op == "verify":
        node = _find(doc, edit.target)
        node["verified"] = True
        yaml_io.set_eol_comment(node, "verified", stamp.replace("added", "confirmed"))


def apply_edits(text: str, edits: list[ProfileEdit], today: date | None = None) -> str:
    stamp = f"added {(today or date.today()).isoformat()} (answer in the app)"
    doc = yaml_io.load(text)
    for edit in edits:
        _apply_one(doc, edit, stamp)
    new_text = yaml_io.dump(doc)
    profile_records(yaml.safe_load(new_text))  # still parses, no duplicate ids
    return new_text


def unified_diff(old: str, new: str) -> str:
    return "".join(difflib.unified_diff(old.splitlines(keepends=True), new.splitlines(keepends=True),
                                        "profile.yaml", "profile.yaml (proposed)", n=2))
