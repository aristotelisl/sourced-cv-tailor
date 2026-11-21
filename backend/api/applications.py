"""Application tracker: /api/applications and /api/versions."""
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from backend.api.render import load_and_check, pdf_response
from backend.models.tracker import (
    ApplicationCreate, ApplicationDetail, ApplicationSummary, ApplicationUpdate, CvVersion, CvVersionCreate,
)
from backend.store import applications as store
from backend.store.applications import NotFound

router = APIRouter(prefix="/api", tags=["tracker"])


def _not_found(e: NotFound) -> HTTPException:
    return HTTPException(404, {"error": "not_found", "message": str(e)})


@router.get("/applications")
def list_applications() -> list[ApplicationSummary]:
    return store.list_applications()


@router.post("/applications", status_code=201)
def create_application(data: ApplicationCreate) -> ApplicationDetail:
    return store.create_application(data)


@router.get("/applications/{application_id}")
def get_application(application_id: int) -> ApplicationDetail:
    try:
        return store.get_application(application_id)
    except NotFound as e:
        raise _not_found(e) from e


@router.patch("/applications/{application_id}")
def update_application(application_id: int, update: ApplicationUpdate) -> ApplicationDetail:
    try:
        return store.update_application(application_id, update)
    except NotFound as e:
        raise _not_found(e) from e


@router.delete("/applications/{application_id}", status_code=204)
def delete_application(application_id: int) -> Response:
    try:
        store.delete_application(application_id)
    except NotFound as e:
        raise _not_found(e) from e
    return Response(status_code=204)


@router.post("/applications/{application_id}/versions", status_code=201)
def add_version(application_id: int, data: CvVersionCreate) -> CvVersion:
    load_and_check(data.cv)  # never store a CV that cites ids missing from the profile
    try:
        return store.add_version(application_id, data)
    except NotFound as e:
        raise _not_found(e) from e


@router.get("/versions/{version_id}")
def get_version(version_id: int) -> CvVersion:
    try:
        return store.get_version(version_id)
    except NotFound as e:
        raise _not_found(e) from e


@router.get("/versions/{version_id}/pdf", response_class=Response,
            responses={200: {"content": {"application/pdf": {}}}})
def version_pdf(version_id: int) -> Response:
    """Re-render a saved version with the current template and profile header."""
    return pdf_response(get_version(version_id).cv)
