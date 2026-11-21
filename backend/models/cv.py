"""Tailored CV: the output of the LLM tailoring step and the input of the renderer (SPEC §4.2).

Every model forbids unknown keys, so a typo or an LLM inventing a field fails
validation instead of silently disappearing from the CV.
"""
from typing import Literal

from pydantic import Field

from backend.models.base import StrictModel as _Model


ContactField = Literal["location", "phone", "website", "linkedin", "github"]


class Bullet(_Model):
    text: str
    source: str = Field(description="Profile id this bullet comes from; '+'-joined when merged")
    tech: str | None = Field(None, description="Optional italic tech list shown after the text")


class Entry(_Model):
    source: str = Field(description="Profile id of the job, degree, project or award")
    left: str
    left_url: str | None = None
    # Middle column: either plain `middle`, or `middle_prefix` + link + `middle_suffix`.
    middle: str | None = None
    middle_prefix: str | None = None
    middle_url: str | None = None
    middle_link_text: str | None = None
    middle_suffix: str | None = None
    right: str | None = None
    bullets: list[Bullet] = []


class SkillGroup(_Model):
    label: str
    items: list[str]


class Section(_Model):
    title: str
    entries: list[Entry] = []
    skills: list[SkillGroup] = []


class Layout(_Model):
    """Overrides for the template's layout defaults. Values go straight into CSS, hence the patterns."""
    font_pt: float | None = Field(None, ge=8, le=12)
    line_height: float | None = Field(None, ge=1.0, le=1.6)
    section_gap: str | None = Field(None, pattern=r"^\d+(\.\d+)?(px|mm|pt)$")
    margin_mm: str | None = Field(None, pattern=r"^\d+(\.\d+)?mm( \d+(\.\d+)?mm){0,3}$")


class GapReport(_Model):
    must_have_missing: list[str] = []
    nice_to_have_missing: list[str] = []
    unverified_used: list[str] = []
    questions: list[str] = []
    flags: list[str] = []


class JobRef(_Model):
    company: str | None = None
    title: str | None = None
    location: str | None = None


class TailoredCV(_Model):
    comment: str | None = Field(None, alias="_comment", description="Free-text note, ignored by the renderer")
    job: JobRef | None = None
    filename: str = Field("CV", pattern=r"^[\w.-]+$", description="PDF file name without extension")
    header_extras: list[str] = []
    hide_contact: list[ContactField] = Field(
        [], description="Profile contact details to leave out of this CV's header (all shown by default)")
    layout: Layout = Layout()
    sections: list[Section]
    gap_report: GapReport = GapReport()
