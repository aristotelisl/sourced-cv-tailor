"""Profile endpoints: first-run setup, a summary for the UI, the bullet bank, and answering questions into profile.yaml."""
from fastapi import APIRouter, HTTPException

from backend.llm import LLMError, LLMNotConfigured
from backend.llm.answer import EditsRejected
from backend.models.base import StrictModel
from backend.models.profile_edit import ProfileAnswerRequest, ProfileApplied, ProfileApplyRequest, ProfileProposal
from backend.models.profile_import import (
    ProfileCheckRequest, ProfileCheckResult, ProfileImportRequest, ProfileImportResult, ProfileSaveRequest,
    ProfileSaveResult, ProfileStatus, ProfileView,
)
from backend.profile import load_profile, profile_records
from backend.profile_edit import service
from backend.profile_edit.service import EditsInvalid, ProfileChanged
from backend.profile_import import service as setup
from backend.profile_import.service import InvalidProfile, ProfileChanged as ProfileFileChanged
from backend.profile_import.text import UnreadableFile

router = APIRouter(prefix="/api", tags=["profile"])


class ProfileSummary(StrictModel):
    name: str
    contact: dict[str, str]  # location/phone/website/linkedin/github -> value, as shown in the header
    header_extras: dict[str, str]  # key -> header line; empty ones are left out


class BankItem(StrictModel):
    id: str
    text: str
    verified: bool


@router.get("/profile/status")
def profile_status() -> ProfileStatus:
    """Whether there's a profile of your own yet (the app shows the setup page until there is)."""
    return setup.status()


@router.post("/profile/use-example")
def use_example_profile() -> ProfileStatus:
    """Explore with the fictional sample profile (copied to profile.yaml if there's none)."""
    return setup.use_example()


@router.post("/profile/import")
def import_cv(req: ProfileImportRequest) -> ProfileImportResult:
    """Read an uploaded CV into a proposed profile.yaml. Nothing is saved."""
    try:
        return setup.import_cv(req)
    except UnreadableFile as e:
        raise HTTPException(422, {"error": "unreadable_file", "message": str(e)}) from e
    except LLMNotConfigured as e:
        raise HTTPException(503, {"error": "llm_not_configured", "message": str(e)}) from e
    except LLMError as e:
        raise HTTPException(502, {"error": "llm_failed", "message": str(e)}) from e


@router.get("/profile/view")
def view_profile() -> ProfileView:
    """The whole profile, laid out for the Profile page, plus its YAML for editing."""
    return setup.view()


@router.post("/profile/check")
def check_profile(req: ProfileCheckRequest) -> ProfileCheckResult:
    """Can this YAML be saved, and which ids of the open CV would it remove? Nothing is saved."""
    return setup.check(req)


@router.post("/profile/save")
def save_profile(req: ProfileSaveRequest) -> ProfileSaveResult:
    """Save a whole profile.yaml (from setup, or edited on the Profile page)."""
    try:
        return setup.save(req)
    except InvalidProfile as e:
        raise HTTPException(422, {"error": "invalid_profile", "message": str(e), "problems": e.problems}) from e
    except ProfileFileChanged as e:
        raise HTTPException(409, {"error": "profile_changed", "message": str(e)}) from e


@router.get("/profile")
def profile_summary() -> ProfileSummary:
    person = load_profile()["person"]
    extras = {k: v for k, v in (person.get("header_extras") or {}).items() if v}
    contact = {k: str(person[k]) for k in ("location", "phone", "website", "linkedin", "github") if person.get(k)}
    return ProfileSummary(name=person["name"], contact=contact, header_extras=extras)


@router.get("/profile/bank")
def bullet_bank() -> dict[str, list[BankItem]]:
    """Every job bullet and project fact in the profile, by entry id: what a CV bullet can be swapped for."""
    bank: dict[str, list[BankItem]] = {}
    for record in profile_records(load_profile()).values():
        if record.kind in ("experience_bullet", "project_fact") and record.parent:
            bank.setdefault(record.parent, []).append(
                BankItem(id=record.id, text=record.data["text"], verified=record.verified))
    return bank


@router.post("/profile/answer")
def answer_question(req: ProfileAnswerRequest) -> ProfileProposal:
    """Turn an answer into proposed profile edits and a diff. Nothing is saved."""
    try:
        return service.propose(req)
    except EditsRejected as e:
        raise HTTPException(422, {"error": "edits_rejected", "message": str(e), "problems": e.problems}) from e
    except LLMNotConfigured as e:
        raise HTTPException(503, {"error": "llm_not_configured", "message": str(e)}) from e
    except LLMError as e:
        raise HTTPException(502, {"error": "llm_failed", "message": str(e)}) from e


@router.post("/profile/apply")
def apply_edits(req: ProfileApplyRequest) -> ProfileApplied:
    """Save previewed edits to profile.yaml (re-checked; refused if the file changed since the preview)."""
    try:
        return service.apply(req)
    except ProfileChanged as e:
        raise HTTPException(409, {"error": "profile_changed", "message": str(e)}) from e
    except EditsInvalid as e:
        raise HTTPException(422, {"error": "edits_invalid", "message": str(e), "problems": e.problems}) from e
