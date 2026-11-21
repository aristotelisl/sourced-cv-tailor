"""The Profile page: is there a profile of your own yet, read a CV into one, view, check and save it."""
import base64
import binascii
import os
import shutil
from datetime import datetime
from pathlib import Path

import yaml

from backend import paths
from backend.llm.import_cv import extract_profile
from backend.models.profile_import import (
    ProfileCheckRequest, ProfileCheckResult, ProfileImportRequest, ProfileImportResult, ProfileSaveRequest,
    ProfileSaveResult, ProfileStatus, ProfileView,
)
from backend.profile import profile_records
from backend.profile_edit.edits import ID_PATTERN, profile_hash
from backend.profile_import import build
from backend.profile_import.text import UnreadableFile, clean, extract_text
from backend.profile_import.view import profile_view


class ProfileChanged(Exception):
    """profile.yaml changed since the page loaded it (e.g. a gap-report answer was saved meanwhile)."""


class InvalidProfile(ValueError):
    def __init__(self, problems: list[str]):
        super().__init__("That profile can't be saved")
        self.problems = problems


def _path() -> Path:
    return paths.PROFILE_PATH  # looked up at call time so tests can point it at a copy


def _name(path: Path) -> str | None:
    try:
        return (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("person", {}).get("name")
    except (yaml.YAMLError, AttributeError, OSError):
        return None


def status() -> ProfileStatus:
    path = _path()
    if not path.exists():
        return ProfileStatus(state="missing", name=None)
    name = _name(path)
    # Still the fictional sample person: the user hasn't made it their own yet.
    is_example = name is not None and name == _name(paths.EXAMPLE_PROFILE_PATH)
    return ProfileStatus(state="example" if is_example else "own", name=name)


def use_example() -> ProfileStatus:
    path = _path()
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(paths.EXAMPLE_PROFILE_PATH, path)
    return status()


def import_cv(req: ProfileImportRequest) -> ProfileImportResult:
    if req.text and req.text.strip():
        text = clean(req.text)
    elif req.content_base64:
        try:
            data = base64.b64decode(req.content_base64, validate=True)
        except (binascii.Error, ValueError) as e:
            raise UnreadableFile("The upload was damaged; try again") from e
        text = extract_text(req.filename or "", data)
    else:
        raise UnreadableFile("Upload a CV or paste its text")
    draft, problems = extract_profile(text)
    data, flagged, warnings = build.resolve(draft, problems)
    return ProfileImportResult(yaml=build.to_yaml(data, flagged, draft.questions), warnings=warnings,
                               counts=build.counts(data))


def check_profile(text: str) -> list[str]:
    """Enough to be sure the rest of the app can load it."""
    try:
        profile = yaml.safe_load(text)
    except yaml.YAMLError as e:
        return [f"Not valid YAML: {e}".splitlines()[0]]
    if not isinstance(profile, dict):
        return ["The profile must be a YAML mapping (person:, experience:, ...)"]
    problems = []
    if not isinstance(profile.get("person"), dict) or not profile["person"].get("name"):
        problems.append("person.name is missing")
    try:
        records = profile_records(profile)
    except (KeyError, TypeError, AttributeError) as e:
        return problems + [f"Every job, degree, project, award, bullet and fact needs an id ({e})"]
    except ValueError as e:
        return problems + [str(e)]
    problems += [f"'{rid}' isn't a valid id (use lowercase letters, digits and _)"
                 for rid in records if not ID_PATTERN.match(str(rid))]
    return problems


def view() -> ProfileView:
    return profile_view(_path().read_text(encoding="utf-8"))


def check(req: ProfileCheckRequest) -> ProfileCheckResult:
    problems = check_profile(req.yaml)
    if problems:
        return ProfileCheckResult(problems=problems, missing_cited=[])
    ids = set(profile_records(yaml.safe_load(req.yaml)))
    return ProfileCheckResult(problems=[], missing_cited=[i for i in dict.fromkeys(req.cited) if i not in ids])


def save(req: ProfileSaveRequest) -> ProfileSaveResult:
    if problems := check_profile(req.yaml):
        raise InvalidProfile(problems)
    path = _path()
    if req.base is not None and (not path.exists() or profile_hash(path.read_text(encoding="utf-8")) != req.base):
        raise ProfileChanged("Your profile changed since you opened it (maybe an answer was saved in another tab). "
                             "Copy your edits, reload the page and make them again.")
    backup = None
    if req.backup and path.exists() and status().state == "own":
        # Never lose a profile someone has worked on: keep a copy next to it (git-ignored).
        backup_path = path.with_name(f"profile.backup-{datetime.now():%Y%m%d-%H%M%S}.yaml")
        shutil.copyfile(path, backup_path)
        backup = str(backup_path.relative_to(paths.ROOT) if backup_path.is_relative_to(paths.ROOT) else backup_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".yaml.tmp")
    tmp.write_text(req.yaml.replace("\r\n", "\n"), encoding="utf-8", newline="\n")
    os.replace(tmp, path)
    return ProfileSaveResult(status=status(), backup=backup)
