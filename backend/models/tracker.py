"""Application tracker contracts (SPEC §4.3): applications and the CV versions made for them."""
from datetime import date, datetime
from typing import Literal

from pydantic import Field

from backend.models.base import StrictModel
from backend.models.cv import TailoredCV
from backend.models.extras import Extra
from backend.models.job import JobAnalysis, Salary
from backend.models.tailor import HeaderExtraSuggestion, RequirementCoverage

Status = Literal["draft", "applied", "interview", "offer", "rejected", "on-hold"]


class Application(StrictModel):
    id: int
    company: str | None
    title: str
    url: str | None
    location: str | None
    salary: Salary | None
    status: Status
    applied_at: date | None
    cv_version_id: int | None = Field(description="The CV version sent (set when a PDF is exported)")
    notes: str
    contacts: str
    created_at: datetime
    updated_at: datetime


class ApplicationSummary(Application):
    version_count: int
    latest_version_id: int | None


class CvVersionSummary(StrictModel):
    id: int
    application_id: int
    label: str
    filename: str
    created_at: datetime


class CvVersion(CvVersionSummary):
    cv: TailoredCV
    coverage: list[RequirementCoverage]
    header_extra_suggestions: list[HeaderExtraSuggestion]


class ApplicationDetail(Application):
    job_text: str
    analysis: JobAnalysis
    versions: list[CvVersionSummary]
    extras: list[Extra]


class ApplicationCreate(StrictModel):
    job_text: str
    analysis: JobAnalysis
    url: str | None = None


class ApplicationUpdate(StrictModel):
    """Only the fields sent are changed."""
    status: Status | None = None
    applied_at: date | None = None
    notes: str | None = None
    contacts: str | None = None
    url: str | None = None
    company: str | None = None
    title: str | None = None
    location: str | None = None


class CvVersionCreate(StrictModel):
    label: str = Field(description="e.g. 'Tailored', 'Exported'")
    cv: TailoredCV
    coverage: list[RequirementCoverage] = []
    header_extra_suggestions: list[HeaderExtraSuggestion] = []
    mark_sent: bool = Field(False, description="Also make this the application's cv_version_id")
