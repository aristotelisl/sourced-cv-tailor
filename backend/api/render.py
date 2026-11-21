"""POST /api/render/html (live preview) and /api/render/pdf (export)."""
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, Response

from backend.models import TailoredCV
from backend.models.base import StrictModel
from backend.profile import SourceCheck, check_sources, load_profile
from backend.render import render_html, render_pdf

router = APIRouter(prefix="/api/render", tags=["render"])


def load_and_check(cv: TailoredCV) -> tuple[dict, SourceCheck]:
    """Reject the CV if it cites anything that isn't in profile.yaml."""
    profile = load_profile()
    check = check_sources(cv, profile)
    if not check.ok:
        raise HTTPException(422, {
            "error": "unknown_source",
            "message": "These sources are not in profile.yaml: " + ", ".join(check.unknown),
            "unknown": check.unknown,
        })
    return profile, check


def _warning_headers(check: SourceCheck) -> dict[str, str]:
    return {"X-Unverified-Sources": ",".join(check.unverified)}


@router.post("/html", response_class=HTMLResponse)
def render_html_endpoint(cv: TailoredCV) -> HTMLResponse:
    profile, check = load_and_check(cv)
    return HTMLResponse(render_html(cv, profile["person"]), headers=_warning_headers(check))


class FitCheck(StrictModel):
    pages: int
    fit_step: int
    fits: bool
    unverified: list[str]


@router.post("/check")
def check_fit(cv: TailoredCV) -> FitCheck:
    """Page count for the live editor, without sending the PDF back."""
    profile, check = load_and_check(cv)
    result = render_pdf(cv, profile["person"])
    return FitCheck(pages=result.pages, fit_step=result.fit_step, fits=result.fits, unverified=check.unverified)


@router.post("/pdf", response_class=Response, responses={200: {"content": {"application/pdf": {}}}})
def render_pdf_endpoint(cv: TailoredCV) -> Response:
    return pdf_response(cv)


def pdf_response(cv: TailoredCV) -> Response:
    """Checked, one-page PDF download (also used to re-render saved versions)."""
    profile, check = load_and_check(cv)
    result = render_pdf(cv, profile["person"])
    if not result.fits:
        raise HTTPException(422, {
            "error": "overflow",
            "message": f"The CV is {result.pages} pages even at the tightest layout. Cut a bullet.",
            "pages": result.pages,
        })
    return Response(result.pdf, media_type="application/pdf", headers={
        "Content-Disposition": f'attachment; filename="{cv.filename}.pdf"',
        "X-Page-Count": str(result.pages),
        "X-Fit-Step": str(result.fit_step),
        **_warning_headers(check),
    })
