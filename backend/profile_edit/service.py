"""Propose profile edits from an answer (LLM), then apply them once the user has seen the diff."""
import os
from pathlib import Path

import yaml

from backend import paths
from backend.llm.answer import draft_edits
from backend.models.profile_edit import ProfileAnswerRequest, ProfileApplied, ProfileApplyRequest, ProfileProposal
from backend.profile_edit.edits import apply_edits, profile_hash, unified_diff, validate_edits


class ProfileChanged(Exception):
    """profile.yaml changed between the preview and the save."""


class EditsInvalid(ValueError):
    def __init__(self, problems: list[str]):
        super().__init__("The edits break the profile rules")
        self.problems = problems


def _path() -> Path:
    return paths.PROFILE_PATH  # looked up at call time so tests can point it at a copy


def propose(req: ProfileAnswerRequest) -> ProfileProposal:
    text = _path().read_text(encoding="utf-8")
    draft = draft_edits(req, yaml.safe_load(text), text)
    new_text = apply_edits(text, draft.edits)
    return ProfileProposal(edits=draft.edits, summary=draft.summary, diff=unified_diff(text, new_text),
                           base=profile_hash(text))


def apply(req: ProfileApplyRequest) -> ProfileApplied:
    path = _path()
    text = path.read_text(encoding="utf-8")
    if profile_hash(text) != req.base:
        raise ProfileChanged("profile.yaml changed since this preview; answer again to get a fresh diff")
    problems = validate_edits(req.edits, req.answer, yaml.safe_load(text))
    if problems:
        raise EditsInvalid(problems)
    new_text = apply_edits(text, req.edits)
    tmp = path.with_suffix(".yaml.tmp")
    tmp.write_text(new_text, encoding="utf-8", newline="\n")
    os.replace(tmp, path)
    return ProfileApplied(diff=unified_diff(text, new_text))
