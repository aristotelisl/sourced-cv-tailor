"""Load data/profile.yaml and check that a CV only cites ids that exist in it."""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import yaml

from backend.models import TailoredCV
from backend.paths import PROFILE_PATH

Kind = Literal["experience", "experience_bullet", "education", "project", "project_fact", "award"]


def load_profile(path: Path = PROFILE_PATH) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"{path} not found: copy examples/profile.example.yaml there and fill in your own facts")
    return yaml.safe_load(path.read_text(encoding="utf-8"))


@dataclass
class Record:
    """Anything in the profile a CV can cite."""
    id: str
    kind: Kind
    data: dict
    parent: str | None = None  # the experience or project a bullet/fact belongs to

    @property
    def verified(self) -> bool:
        return self.data.get("verified") is not False


def profile_records(profile: dict) -> dict[str, Record]:
    records: dict[str, Record] = {}

    def add(record: Record) -> None:
        if record.id in records:
            raise ValueError(f"duplicate id '{record.id}' in profile.yaml")
        records[record.id] = record

    for exp in profile.get("experience", []):
        add(Record(exp["id"], "experience", exp))
        for b in exp.get("bullets", []):
            add(Record(b["id"], "experience_bullet", b, parent=exp["id"]))
    for edu in profile.get("education", []):
        add(Record(edu["id"], "education", edu))
    for project in profile.get("projects", []):
        add(Record(project["id"], "project", project))
        for fact in project.get("facts", []):
            add(Record(fact["id"], "project_fact", fact, parent=project["id"]))
    for award in profile.get("awards", []):
        add(Record(award["id"], "award", award))
    return records


def source_index(profile: dict) -> dict[str, bool]:
    """Map every id a CV may cite to whether it is verified."""
    return {rid: r.verified for rid, r in profile_records(profile).items()}


@dataclass
class SourceCheck:
    unknown: list[str] = field(default_factory=list)     # not in the profile: reject
    unverified: list[str] = field(default_factory=list)  # `verified: false`: warn

    @property
    def ok(self) -> bool:
        return not self.unknown


def check_sources(cv: TailoredCV, profile: dict) -> SourceCheck:
    index = source_index(profile)
    check = SourceCheck()
    for section in cv.sections:
        for entry in section.entries:
            for ref in [entry.source, *(b.source for b in entry.bullets)]:
                for part in ref.split("+"):
                    if part not in index:
                        _add_once(check.unknown, part)
                    elif not index[part]:
                        _add_once(check.unverified, part)
    return check


def _add_once(items: list[str], item: str) -> None:
    if item not in items:
        items.append(item)
