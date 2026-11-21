"""Job analysis: what the LLM extracts from a job listing (SPEC §4.1).

Also used as the structured-output schema for the LLM call, so the field
descriptions double as extraction instructions.
"""
from typing import Literal

from pydantic import Field

from backend.models.base import StrictModel

RoleFamily = Literal["frontend", "fullstack", "backend", "ai-engineer", "data", "quant", "systems", "other"]
Remote = Literal["on-site", "hybrid", "remote", "unknown"]
Seniority = Literal["intern", "new-grad", "junior", "mid", "senior", "lead", "unknown"]


class Salary(StrictModel):
    min: float | None = Field(description="Lower bound as written, not converted")
    max: float | None = Field(description="Upper bound as written, not converted")
    currency: str = Field(description="ISO 4217 code of the currency the listing uses, e.g. EUR, GBP, INR")
    period: Literal["year", "month", "day", "hour"]


class JobAnalysis(StrictModel):
    company: str | None = Field(description="Hiring company; null if not named (e.g. an agency listing)")
    title: str
    location: str | None = Field(description="Location as stated, including any on-site percentage")
    remote: Remote
    salary: Salary | None = Field(description="Null when no figure is given (e.g. 'competitive')")
    seniority: Seniority
    years_required: str | None = Field(description="Experience asked for, as written, e.g. '0-1.5' or '3+'")
    must_have: list[str] = Field(description="Requirements the listing presents as required")
    nice_to_have: list[str] = Field(description="Requirements presented as optional, preferred or a bonus")
    stack: list[str] = Field(description="Languages, frameworks, tools and platforms the listing names")
    right_to_work: str | None = Field(description="Where the candidate must be allowed to work, e.g. 'UK', 'Spain (EU)'")
    keywords: list[str] = Field(description="Terms a recruiter or ATS would match a CV against")
    role_family: RoleFamily
