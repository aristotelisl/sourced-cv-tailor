"""Generate an extra (cover letter etc.), validated against the profile, optionally saved with its application."""
from backend.extras.validate import assemble_text
from backend.llm.extras import draft_extra
from backend.models.extras import ExtraRequest, ExtraResult
from backend.paths import PROFILE_PATH
from backend.profile import load_profile
from backend.store import extras as store
from backend.store.applications import get_application


def generate(req: ExtraRequest) -> ExtraResult:
    if req.application_id is not None:
        get_application(req.application_id)  # NotFound before spending an LLM call
    profile = load_profile()
    draft, unverified = draft_extra(req.kind, req.job, req.cv, req.recipient, req.notes, profile,
                                    PROFILE_PATH.read_text(encoding="utf-8"), req.previous, req.feedback)
    text = assemble_text(draft)
    saved = None
    if req.application_id is not None:
        saved = store.save_extra(req.application_id, req.kind, draft.subject, text, unverified)
    return ExtraResult(id=saved.id if saved else None, kind=req.kind, subject=draft.subject, text=text,
                       unverified_used=unverified, created_at=saved.created_at if saved else None,
                       paragraphs=draft.paragraphs)
