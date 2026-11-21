"""POST /api/analyse: job listing text → job analysis."""
from fastapi import APIRouter, HTTPException
from pydantic import Field

from backend.llm import LLMError, LLMNotConfigured, analyse_job
from backend.models import JobAnalysis
from backend.models.base import StrictModel

router = APIRouter(prefix="/api", tags=["analyse"])


class AnalyseRequest(StrictModel):
    text: str = Field(min_length=50, max_length=50_000, description="The job listing, pasted as text")


@router.post("/analyse")
def analyse(req: AnalyseRequest) -> JobAnalysis:
    try:
        return analyse_job(req.text)
    except LLMNotConfigured as e:
        raise HTTPException(503, {"error": "llm_not_configured", "message": str(e)}) from e
    except LLMError as e:
        raise HTTPException(502, {"error": "llm_failed", "message": str(e)}) from e
