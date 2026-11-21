"""POST /api/tailor: job analysis → tailored CV + gap report. POST /api/tailor/bullet: rewrite one bullet."""
from collections.abc import Callable
from typing import TypeVar

from fastapi import APIRouter, HTTPException

from backend.llm import LLMError, LLMNotConfigured
from backend.llm.tailor import DraftRejected
from backend.models import BulletRequest, BulletResult, TailorRequest, TailorResult
from backend.tailor import service

router = APIRouter(prefix="/api", tags=["tailor"])
T = TypeVar("T")


def _call(fn: Callable[[], T]) -> T:
    try:
        return fn()
    except ValueError as e:
        raise HTTPException(422, {"error": "invalid_request", "message": str(e)}) from e
    except DraftRejected as e:
        raise HTTPException(422, {"error": "draft_rejected", "message": str(e), "problems": e.problems}) from e
    except LLMNotConfigured as e:
        raise HTTPException(503, {"error": "llm_not_configured", "message": str(e)}) from e
    except LLMError as e:
        raise HTTPException(502, {"error": "llm_failed", "message": str(e)}) from e


@router.post("/tailor")
def tailor(req: TailorRequest) -> TailorResult:
    return _call(lambda: service.tailor(req))


@router.post("/tailor/bullet")
def rewrite_bullet(req: BulletRequest) -> BulletResult:
    return _call(lambda: service.rewrite_bullet(req))
