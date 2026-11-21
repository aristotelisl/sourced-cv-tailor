"""POST /api/extras (generate or rewrite), PUT/DELETE /api/extras/{id} (the user's edits), POST /api/extras/letter-pdf."""
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from backend.extras import service
from backend.llm import LLMError, LLMNotConfigured
from backend.llm.tailor import DraftRejected
from backend.models.extras import Extra, ExtraRequest, ExtraResult, ExtraUpdate, LetterPdfRequest
from backend.profile import load_profile
from backend.render.letter import render_letter_pdf
from backend.store import extras as store
from backend.store.applications import NotFound

router = APIRouter(prefix="/api", tags=["extras"])


@router.post("/extras")
def generate_extra(req: ExtraRequest) -> ExtraResult:
    try:
        return service.generate(req)
    except NotFound as e:
        raise HTTPException(404, {"error": "not_found", "message": str(e)}) from e
    except DraftRejected as e:
        raise HTTPException(422, {"error": "draft_rejected", "message": str(e), "problems": e.problems}) from e
    except LLMNotConfigured as e:
        raise HTTPException(503, {"error": "llm_not_configured", "message": str(e)}) from e
    except LLMError as e:
        raise HTTPException(502, {"error": "llm_failed", "message": str(e)}) from e


@router.put("/extras/{extra_id}")
def update_extra(extra_id: int, update: ExtraUpdate) -> Extra:
    try:
        return store.update_extra(extra_id, update)
    except NotFound as e:
        raise HTTPException(404, {"error": "not_found", "message": str(e)}) from e


@router.delete("/extras/{extra_id}", status_code=204)
def delete_extra(extra_id: int) -> Response:
    try:
        store.delete_extra(extra_id)
    except NotFound as e:
        raise HTTPException(404, {"error": "not_found", "message": str(e)}) from e
    return Response(status_code=204)


@router.post("/extras/letter-pdf", response_class=Response, responses={200: {"content": {"application/pdf": {}}}})
def letter_pdf(req: LetterPdfRequest) -> Response:
    """The cover letter as a PDF. The text is the user's (as edited), so it's printed as-is."""
    pdf, pages = render_letter_pdf(req, load_profile()["person"])
    return Response(pdf, media_type="application/pdf", headers={
        "Content-Disposition": f'attachment; filename="{req.filename}.pdf"',
        "X-Page-Count": str(pages),
    })
