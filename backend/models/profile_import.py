"""Setting up a first profile: reading an uploaded CV into profile.yaml, or starting from the sample."""
from typing import Literal

from pydantic import Field

from backend.models.base import StrictModel

# --- What the model extracts from a CV (structured output) -------------------------------
# No nullable fields: each one multiplies the grammar the API compiles for structured outputs,
# and ~20 of them make it refuse the schema ("compiled grammar is too large"). Empty string = not given.


class ImportedItem(StrictModel):
    id: str = Field(description="snake_case, prefixed with the parent's id, e.g. acme_payments")
    text: str = Field(description="The bullet as written in the CV")


class ImportedPerson(StrictModel):
    name: str
    location: str = Field(description="Empty if not in the CV")
    phone: str = Field(description="Empty if not in the CV")
    email: str = Field(description="Empty if not in the CV")
    website: str = Field(description="Empty if not in the CV")
    linkedin: str = Field(description="Empty if not in the CV")
    github: str = Field(description="Empty if not in the CV")
    spoken_languages: list[str] = Field(description="As written, e.g. 'Spanish (Native)'")


class ImportedEducation(StrictModel):
    id: str = Field(description="snake_case, e.g. leeds_bsc")
    degree: str
    institution: str
    location: str = Field(description="Empty if not in the CV")
    start: str = Field(description="Empty if not given. MM/YYYY, or YYYY if the CV gives only a year")
    end: str = Field(description="Empty if not given. MM/YYYY, YYYY, or 'Present'")
    grade: str = Field(description="Empty if not in the CV")
    dissertation: str = Field(description="Empty if not in the CV")
    modules: list[str]


class ImportedExperience(StrictModel):
    id: str = Field(description="snake_case company name, e.g. acme")
    title: str
    company: str
    url: str = Field(description="Empty if not in the CV")
    location: str = Field(description="Empty if not in the CV")
    start: str = Field(description="Empty if not given. MM/YYYY, or YYYY if the CV gives only a year")
    end: str = Field(description="Empty if not given. MM/YYYY, YYYY, or 'Present'")
    is_internship: bool
    stack: list[str] = Field(description="Technologies the CV names for this job outside its bullets")
    bullets: list[ImportedItem]


class ImportedProject(StrictModel):
    id: str
    name: str
    context: str = Field(description="Empty if not given. e.g. 'MSc dissertation' or 'Personal project'")
    url: str = Field(description="Empty if not in the CV")
    year: str = Field(description="Empty if not in the CV")
    stack: list[str]
    facts: list[ImportedItem]


class ImportedAward(StrictModel):
    id: str
    name: str
    institution: str = Field(description="Empty if not in the CV")
    date: str = Field(description="Empty if not in the CV")
    text: str = Field(description="Empty if not in the CV")


class ImportedProfile(StrictModel):
    person: ImportedPerson
    education: list[ImportedEducation]
    experience: list[ImportedExperience]
    projects: list[ImportedProject]
    awards: list[ImportedAward]
    skills: list[str] = Field(description="Every skill and technology the CV lists, one name per item")
    questions: list[str] = Field(description="Anything unclear in the CV that the candidate should check")


# --- API ---------------------------------------------------------------------------------

ProfileState = Literal["missing", "example", "own"]


class ProfileStatus(StrictModel):
    state: ProfileState  # no profile.yaml / the fictional sample / the user's own
    name: str | None


class ProfileImportRequest(StrictModel):
    """A CV file (base64) or pasted text: exactly one of them."""
    filename: str | None = None
    content_base64: str | None = None
    text: str | None = None


class ProfileImportResult(StrictModel):
    yaml: str            # the proposed profile.yaml: nothing is saved yet
    warnings: list[str]  # what was dropped or needs checking
    counts: dict[str, int]  # jobs/bullets/education/projects/awards/skills, for the summary line


class ProfileSaveRequest(StrictModel):
    yaml: str


class ProfileSaveResult(StrictModel):
    status: ProfileStatus
    backup: str | None  # where the previous profile was copied, if there was one of your own
