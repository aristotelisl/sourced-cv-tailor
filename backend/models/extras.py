"""Application extras (SPEC §1.7, M6): cover letter, about-me blurb, recruiter and referral messages.

The LLM writes sentence by sentence and labels every claim with its sources, so the
no-invention rule can be checked in code just like CV bullets.
"""
from datetime import datetime
from typing import Literal

from pydantic import Field

from backend.models.base import StrictModel
from backend.models.cv import ContactField, TailoredCV
from backend.models.job import JobAnalysis

ExtraKind = Literal["cover_letter", "about_me", "recruiter_message", "referral_message"]


class ExtraSentence(StrictModel):
    text: str
    kind: Literal["claim", "other"] = Field(
        description="claim: says something the candidate did, has, knows or achieved. "
                    "other: greeting, interest in the company or role, a request, a sign-off.")
    sources: list[str] = Field(
        description="For claims: profile ids backing it (bullet, fact or entry ids), 'skills' for the skills "
                    "list, 'notes' for the user's notes. Empty for other sentences.")


class ExtraParagraph(StrictModel):
    sentences: list[ExtraSentence]


class ExtraDraft(StrictModel):
    subject: str | None = Field(description="Subject line for messages and emails; null for the about-me blurb")
    paragraphs: list[ExtraParagraph]


class ExtraRequest(StrictModel):
    kind: ExtraKind
    job: JobAnalysis
    cv: TailoredCV | None = Field(None, description="The tailored CV, so the text stays consistent with it")
    recipient: str | None = Field(None, description="Who it's addressed to, e.g. 'Maria (recruiter)'")
    notes: str | None = Field(None, max_length=4000,
                              description="Extra context from the user: why this company, where they heard of it, a referrer")
    application_id: int | None = Field(None, description="Save the result with this tracker application")
    previous: str | None = Field(None, max_length=8000,
                                 description="Rewrite: the current text (as the user last edited it) to revise")
    feedback: str | None = Field(None, max_length=2000,
                                 description="Rewrite: what the user wants changed. Facts in it count as their notes")


class Extra(StrictModel):
    id: int | None = Field(description="Saved extra id; null when not saved")
    kind: ExtraKind
    subject: str | None
    text: str
    unverified_used: list[str]
    created_at: datetime | None = None


class ExtraResult(Extra):
    paragraphs: list[ExtraParagraph]


class ExtraUpdate(StrictModel):
    text: str
    subject: str | None = None


class LetterPdfRequest(StrictModel):
    """A cover letter as the user last edited it, to print with the same header as the CV."""
    text: str = Field(min_length=1, max_length=8000, description="Paragraphs separated by blank lines")
    subject: str | None = None
    filename: str = Field("Cover_Letter", pattern=r"^[\w.-]+$", description="PDF file name without extension")
    hide_contact: list[ContactField] = []
    header_extras: list[str] = []
