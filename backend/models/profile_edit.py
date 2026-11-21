"""Answering a gap-report question: the edits the LLM proposes to profile.yaml, and the API contracts.

The LLM never rewrites the YAML. It proposes a few typed edits, each quoting the words of
the user's answer that support it; code checks them and applies them, keeping comments.
"""
from typing import Literal

from pydantic import Field

from backend.models.base import StrictModel
from backend.models.job import JobAnalysis

EditOp = Literal["add_experience_bullet", "add_project_fact", "add_skill", "set_skill_note", "add_module",
                 "add_stack", "set_grade", "verify"]


class ProfileEdit(StrictModel):
    op: EditOp
    target: str = Field(description=(
        "add_experience_bullet: experience id. add_project_fact: project id. add_skill: 'strong' or 'listed'. "
        "set_skill_note: the skill name. add_module: education id. add_stack: experience id or experience "
        "bullet id. set_grade: education id. verify: the id of the bullet marked verified: false."))
    id: str | None = Field(description="New snake_case id, only for add_experience_bullet and add_project_fact")
    text: str = Field(description=(
        "The bullet or fact text, the skill name, the note, the module name, the technology or the grade. "
        "Empty for verify."))
    quote: str = Field(description="The exact words from the user's answer that support this edit, copied verbatim")


class ProfileAnswerDraft(StrictModel):
    edits: list[ProfileEdit]
    summary: str = Field(description="One or two sentences: what changes, or why nothing should change")


class ProfileAnswerRequest(StrictModel):
    question: str
    answer: str = Field(min_length=1)
    job: JobAnalysis | None = None


class ProfileProposal(StrictModel):
    edits: list[ProfileEdit]
    summary: str
    diff: str = Field(description="Unified diff of profile.yaml; empty when nothing changes")
    base: str = Field(description="Hash of profile.yaml the diff was made against")


class ProfileApplyRequest(StrictModel):
    question: str
    answer: str
    edits: list[ProfileEdit]
    base: str


class ProfileApplied(StrictModel):
    diff: str
