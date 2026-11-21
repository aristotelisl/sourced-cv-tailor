"""Turn a checked extraction into profile.yaml text, in the same shape as examples/profile.example.yaml.

What the checks couldn't trace to the CV is handled here, after the model's retry:
- a bullet or fact is kept but marked `verified: false`, so the app shows it with a warning
  and never uses it silently;
- a skill, technology, module or link is dropped;
- any other field is kept as it is (a name or title) and listed as a warning to check.
"""
import re

import yaml
from ruamel.yaml.comments import CommentedMap, CommentedSeq

from backend.models.profile_import import ImportedProfile
from backend.profile import profile_records
from backend.profile_edit import yaml_io
from backend.profile_import.check import Problem, describe
from backend.tailor.vocab import mentions, split_skill

HEADER = """\
# Master profile: the single source of truth for every CV.
# Created from your uploaded CV. Check it, then add anything your CV leaves out: more bullets per
# job than fit on one page, technologies you used, numbers. The app picks the best ones per job.
#
# Rule: a tailored CV may only use facts from this file. Bullets marked `verified: false` couldn't
# be matched to your CV word for word: fix or confirm them (set `verified: true`), or delete them.
# See examples/profile.example.yaml for every option, including `preferences` (how the app tailors for you).

"""
DROP_IN_LISTS = {"skills", "stack", "modules", "spoken_languages"}
OPTIONAL = {"location", "phone", "email", "website", "linkedin", "github", "url", "start", "end", "grade",
            "dissertation", "context", "year", "date", "text", "institution"}


def _slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return slug if slug and slug[0].isalpha() else f"x_{slug}"


class _Ids:
    def __init__(self):
        self.used: set[str] = set()

    def take(self, wanted: str, prefix: str = "") -> str:
        base = _slug(wanted)
        if prefix and not base.startswith(f"{prefix}_"):
            base = f"{prefix}_{base}"
        rid, n = base, 2
        while rid in self.used:
            rid, n = f"{base}_{n}", n + 1
        self.used.add(rid)
        return rid


def resolve(draft: ImportedProfile, problems: list[Problem]) -> tuple[dict, dict[tuple, str], list[str]]:
    """Apply the fallbacks above. Returns the data, the unverified items (path -> why), and warnings."""
    data = draft.model_dump()
    flagged: dict[tuple, str] = {}
    warnings: list[str] = []
    drops: list[tuple] = []
    for problem in problems:
        path, where = problem.path, describe(problem.path, draft)
        if path[-1] == "text" and len(path) > 3 and path[2] in ("bullets", "facts"):
            flagged[path[:-1]] = problem.message
            warnings.append(f"{where}: {problem.message}. Kept, marked unverified.")
        elif isinstance(path[-1], int) and path[-2] in DROP_IN_LISTS:
            drops.append(path)
            warnings.append(f"{where}: {problem.message}. Left out.")
        elif path[-1] in OPTIONAL:
            _set(data, path, None)
            warnings.append(f"{where}: {problem.message}. Left out.")
        else:
            warnings.append(f"{where}: {problem.message}. Please check it.")
    for path in sorted(drops, key=lambda p: p[-1], reverse=True):  # later items first, so indexes hold
        _get(data, path[:-1]).pop(path[-1])
    return data, flagged, warnings


def _get(data, path):
    for key in path:
        data = data[key]
    return data


def _set(data, path, value):
    _get(data, path[:-1])[path[-1]] = value


def _map(pairs: dict) -> CommentedMap:
    """Leave out empty values, so the YAML only shows what the CV gave."""
    return CommentedMap((k, v) for k, v in pairs.items() if v not in (None, "", [], False))


def to_yaml(data: dict, flagged: dict[tuple, str], questions: list[str]) -> str:
    ids = _Ids()
    doc = CommentedMap()
    p = data["person"]
    doc["person"] = _map({k: p[k] for k in ("name", "location", "phone", "email", "website", "linkedin", "github")}
                         | {"spoken_languages": yaml_io.flow_seq(p["spoken_languages"]) or None})

    doc["education"] = CommentedSeq()
    for edu in data["education"]:
        doc["education"].append(_map({
            "id": ids.take(edu["id"] or edu["institution"]), "degree": edu["degree"],
            "institution": edu["institution"], "location": edu["location"], "start": edu["start"],
            "end": edu["end"], "grade": edu["grade"], "dissertation": edu["dissertation"],
            "modules": yaml_io.flow_seq(edu["modules"]) or None,
        }))

    doc["experience"] = CommentedSeq()
    used_text: list[str] = []
    for i, exp in enumerate(data["experience"]):
        rid = ids.take(exp["id"] or exp["company"])
        bullets = CommentedSeq()
        for j, b in enumerate(exp["bullets"]):
            bullets.append(_item(ids, rid, b, flagged.get(("experience", i, "bullets", j))))
            used_text.append(b["text"])
        doc["experience"].append(_map({
            "id": rid, "title": exp["title"], "company": exp["company"], "url": exp["url"],
            "location": exp["location"], "start": exp["start"], "end": exp["end"],
            "is_internship": exp["is_internship"], "stack": yaml_io.flow_seq(exp["stack"]) or None,
            "bullets": bullets,
        }))
        used_text.extend(exp["stack"])

    doc["projects"] = CommentedSeq()
    for i, project in enumerate(data["projects"]):
        rid = ids.take(project["id"] or project["name"])
        facts = CommentedSeq(_item(ids, rid, f, flagged.get(("projects", i, "facts", j)))
                             for j, f in enumerate(project["facts"]))
        used_text += [f["text"] for f in project["facts"]] + project["stack"]
        stack = CommentedMap(tools=yaml_io.flow_seq(project["stack"])) if project["stack"] else None
        doc["projects"].append(_map({
            "id": rid, "name": project["name"], "context": project["context"], "url": project["url"],
            "year": project["year"], "stack": stack, "facts": facts,
        }))

    doc["awards"] = CommentedSeq(_map({
        "id": ids.take(a["id"] or a["name"]), "name": a["name"], "institution": a["institution"],
        "date": a["date"], "text": a["text"],
    }) for a in data["awards"])

    # A skill used in a job or project is 'strong'; one only listed on the CV is 'listed'.
    evidence = "\n".join(used_text)
    skills = list(dict.fromkeys(data["skills"]))
    strong = [s for s in skills if any(mentions(evidence, t, ignore_case=True) for t in split_skill(s))]
    doc["skills"] = CommentedMap(
        strong=yaml_io.flow_seq(strong),
        listed=yaml_io.flow_seq([s for s in skills if s not in strong]),
        not_claimed=yaml_io.flow_seq([]),
    )
    doc.yaml_set_comment_before_after_key(
        "skills", before="\nstrong = used in a job or project on your CV; listed = on your CV, depth unknown.\n"
                         "not_claimed: skills the app must never add, even if a job asks for them.")
    doc["open_questions"] = CommentedSeq(questions)
    doc["preferences"] = CommentedMap()
    doc.yaml_set_comment_before_after_key(
        "preferences", before="\nHow the app tailors for you (home places, right to work, salary currencies,\n"
                              "tailoring notes...). Copy the keys you want from examples/profile.example.yaml.")

    text = HEADER + yaml_io.dump(doc)
    profile_records(yaml.safe_load(text))  # parses, ids unique
    return text


def _item(ids: _Ids, parent: str, item: dict, problem: str | None) -> CommentedMap:
    node = CommentedMap(id=ids.take(item["id"] or item["text"][:30], prefix=parent), text=item["text"])
    if problem:
        node["verified"] = False
        node.yaml_add_eol_comment(f"# check: {problem}", "verified")
    return node


def counts(data: dict) -> dict[str, int]:
    return {
        "jobs": len(data["experience"]),
        "bullets": sum(len(e["bullets"]) for e in data["experience"]),
        "education": len(data["education"]),
        "projects": len(data["projects"]),
        "awards": len(data["awards"]),
        "skills": len(data["skills"]),
    }
