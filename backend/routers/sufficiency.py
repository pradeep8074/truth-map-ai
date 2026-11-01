import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from backend.database import get_db
from backend.models import (
    SufficiencyResponse,
    SufficiencyStatusResponse,
    RequirementSufficiencyAssessment,
)
from backend.services.sufficiency_service import (
    get_investigation_sufficiency,
    analyze_investigation_sufficiency,
    get_requirement_sufficiency_detail,
    get_sufficiency_status,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["sufficiency"])


def _resolve_investigation_id(conn, investigation_id: Optional[str] = None) -> str:
    """Helper to resolve explicitly passed or default latest investigation ID."""
    cursor = conn.cursor()
    if investigation_id:
        cursor.execute("SELECT id FROM investigations WHERE id = ?;", (investigation_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Investigation '{investigation_id}' not found.")
        return investigation_id

    # Fallback to most recent investigation
    cursor.execute("SELECT id FROM investigations ORDER BY created_at DESC LIMIT 1;")
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="No investigations exist yet. Create an investigation first.")
    return row["id"]


# ==========================================
# 1. Investigation-Scoped Routes
# ==========================================

@router.get(
    "/api/investigations/{investigation_id}/sufficiency",
    response_model=SufficiencyResponse,
)
def get_sufficiency_for_investigation(investigation_id: str):
    """
    Returns the evidence sufficiency assessment and identified gaps
    for all requirements in an investigation's Decision Contract.
    """
    with get_db() as conn:
        _resolve_investigation_id(conn, investigation_id)
        return get_investigation_sufficiency(conn, investigation_id)


@router.post(
    "/api/investigations/{investigation_id}/sufficiency/analyze",
    response_model=SufficiencyResponse,
)
async def analyze_sufficiency_for_investigation(investigation_id: str):
    """
    Runs the Evidence Sufficiency & Gap Analysis Engine.
    Evaluates evidence coverage per requirement against Decision Contract criteria,
    incorporates Component 05 conflict records, invokes Gemini structured reasoning
    when available, and persists assessments and gap recommendations in SQLite.
    """
    with get_db() as conn:
        _resolve_investigation_id(conn, investigation_id)
        try:
            return await analyze_investigation_sufficiency(conn, investigation_id)
        except ValueError as ve:
            raise HTTPException(status_code=400, detail=str(ve))
        except Exception as e:
            logger.error("Failed to execute sufficiency analysis: %s", e, exc_info=True)
            raise HTTPException(status_code=500, detail=f"Sufficiency analysis failed: {str(e)}")


@router.get(
    "/api/investigations/{investigation_id}/sufficiency/status",
    response_model=SufficiencyStatusResponse,
)
def get_sufficiency_status_for_investigation(investigation_id: str):
    """
    Returns lightweight sufficiency statistics and latest audit run status.
    """
    with get_db() as conn:
        _resolve_investigation_id(conn, investigation_id)
        return get_sufficiency_status(conn, investigation_id)


@router.get(
    "/api/investigations/{investigation_id}/sufficiency/requirements/{requirement_id}",
    response_model=RequirementSufficiencyAssessment,
)
def get_requirement_detail_for_investigation(investigation_id: str, requirement_id: str):
    """
    Returns the detailed sufficiency assessment, linked evidence claims with provenance,
    contested conflicts, and actionable evidence gaps for a single requirement.
    """
    with get_db() as conn:
        _resolve_investigation_id(conn, investigation_id)
        try:
            return get_requirement_sufficiency_detail(conn, investigation_id, requirement_id)
        except ValueError as ve:
            raise HTTPException(status_code=404, detail=str(ve))


# ==========================================
# 2. Top-Level Convenience Routes (as requested in Prompt Section 7)
# ==========================================

@router.get("/api/sufficiency", response_model=SufficiencyResponse)
def get_sufficiency_top_level(investigation_id: Optional[str] = Query(None)):
    """Convenience endpoint resolving to the active or latest investigation."""
    with get_db() as conn:
        inv_id = _resolve_investigation_id(conn, investigation_id)
        return get_investigation_sufficiency(conn, inv_id)


@router.post("/api/sufficiency/analyze", response_model=SufficiencyResponse)
async def analyze_sufficiency_top_level(investigation_id: Optional[str] = Query(None)):
    """Runs sufficiency analysis on the active or latest investigation."""
    with get_db() as conn:
        inv_id = _resolve_investigation_id(conn, investigation_id)
        try:
            return await analyze_investigation_sufficiency(conn, inv_id)
        except ValueError as ve:
            raise HTTPException(status_code=400, detail=str(ve))
        except Exception as e:
            logger.error("Failed to execute sufficiency analysis: %s", e, exc_info=True)
            raise HTTPException(status_code=500, detail=f"Sufficiency analysis failed: {str(e)}")


@router.get("/api/sufficiency/status", response_model=SufficiencyStatusResponse)
def get_sufficiency_status_top_level(investigation_id: Optional[str] = Query(None)):
    """Returns lightweight sufficiency metrics for the active or latest investigation."""
    with get_db() as conn:
        inv_id = _resolve_investigation_id(conn, investigation_id)
        return get_sufficiency_status(conn, inv_id)


@router.get(
    "/api/sufficiency/requirements/{requirement_id}",
    response_model=RequirementSufficiencyAssessment,
)
def get_requirement_detail_top_level(requirement_id: str, investigation_id: Optional[str] = Query(None)):
    """Returns the detailed assessment and gaps for a specific requirement."""
    with get_db() as conn:
        inv_id = _resolve_investigation_id(conn, investigation_id)
        try:
            return get_requirement_sufficiency_detail(conn, inv_id, requirement_id)
        except ValueError as ve:
            raise HTTPException(status_code=404, detail=str(ve))
