"""Tailoring contracts: the LLM's draft, and the /api/tailor request and response.

The LLM only writes a draft (which facts to use, how to phrase them, section order,
skills, gaps). Entry headers, dates, links and the contact header come from
profile.yaml in code, so they can't be invented.
"""
from typing import Literal

from pydantic import Field

from backend.models.base import StrictModel
from backend.models.cv import Bullet, GapReport, SkillGroup, TailoredCV
from backend.models.job import JobAnalysis

SectionKey = Literal["employment", "education", "project", "awards", "skills"]


class DraftBullet(StrictModel):
    source: str = Field(description="Profile id(s) this bullet is based on, '+'-joined when it merges several")
    text: str
    tech: str | None = Field(
        description="Optional comma-separated technologies shown in italics after the bullet. "
                    "Only technologies from the cited sources or the project's stack.")


class DraftEntry(StrictModel):
    source: str = Field(description="Profile id of the job, degree, project or award")
    bullets: list[DraftBullet]


class RequirementCoverage(StrictModel):
    requirement: str = Field(description="The job's must_have or nice_to_have item, verbatim")
    kind: Literal["must_have", "nice_to_have"]
    status: Literal["covered", "partial", "missing"] = Field(
        description="covered: the profile clearly shows it; partial: related or weaker evidence; missing: nothing")
    note: str = Field(description="One short line: the evidence, or what's missing")


class TailorDraft(StrictModel):
    coverage: list[RequirementCoverage] = Field(description="One item per must_have and nice_to_have of the job")
    section_order: list[SectionKey] = Field(description="All five sections, each once, in display order")
    employment: list[DraftEntry]
    education: list[DraftEntry]
    project: list[DraftEntry]
    awards: list[DraftEntry]
    skills: list[SkillGroup]
    gap_report: GapReport


class TailorRequest(StrictModel):
    job: JobAnalysis
    header_extras: list[str] = Field(
        [], description="Keys of person.header_extras to show, e.g. ['uk_presettled']. Opt-in only.")


class HeaderExtraSuggestion(StrictModel):
    key: str
    text: str
    reason: str


class TailorResult(StrictModel):
    cv: TailoredCV
    coverage: list[RequirementCoverage]
    header_extra_suggestions: list[HeaderExtraSuggestion]


class BulletRequest(StrictModel):
    """Rewrite one bullet of an entry (or write a new one when `bullet` is null)."""
    job: JobAnalysis
    entry: str = Field(description="Profile id of the entry the bullet belongs to")
    bullet: Bullet | None = None
    others: list[Bullet] = Field([], description="The entry's other bullets, so the new one doesn't repeat them")
    hint: str | None = Field(None, description="What the user wants from the new wording, e.g. 'shorter'")


class BulletDraft(StrictModel):
    options: list[DraftBullet] = Field(description="Three alternatives, each a complete bullet")


class BulletOption(StrictModel):
    bullet: Bullet
    unverified: list[str] = Field(description="Cited ids marked verified: false in the profile")


class BulletResult(StrictModel):
    options: list[BulletOption]
