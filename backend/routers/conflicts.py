import logging
from fastapi import APIRouter, HTTPException, Depends
from backend.database import get_db
from backend.models import (
    ConflictListResponse,
    ConflictStatusResponse,
    ConflictItemModel,
    ConflictResolutionUpdateRequest,
)
from backend.services.conflict_service import (
    get_investigation_conflicts,
    analyze_investigation_conflicts,
    get_conflict_status,
    update_conflict_resolution,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/investigations/{investigation_id}/conflicts",
    tags=["conflicts"]
)


@router.get("", response_model=ConflictListResponse)
@router.get("/", response_model=ConflictListResponse, include_in_schema=False)
def get_conflicts(investigation_id: str):
    """
    Returns all detected evidence conflicts and contradictions for an investigation,
    complete with forensic provenance, severity metrics, and resolution statuses.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM investigations WHERE id = ?;", (investigation_id,))
        if not cursor.fetchone():
            raise HTTPException(
                status_code=404,
                detail=f"Investigation '{investigation_id}' not found."
            )

        conflicts = get_investigation_conflicts(conn, investigation_id)
        return conflicts


@router.post("/analyze", response_model=ConflictListResponse)
async def analyze_conflicts(investigation_id: str):
    """
    Runs the Evidence Contradiction & Conflict Detection Engine.
    Uses Gemini LLM for structured semantic contradiction analysis when available,
    with an automatic deterministic numerical and polar disparity fallback.
    Persists findings into SQLite and returns the complete conflict list and summary.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM investigations WHERE id = ?;", (investigation_id,))
        if not cursor.fetchone():
            raise HTTPException(
                status_code=404,
                detail=f"Investigation '{investigation_id}' not found."
            )

        try:
            result = await analyze_investigation_conflicts(conn, investigation_id)
            return result
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            logger.error("Failed to execute conflict analysis: %s", e, exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Error analyzing evidence conflicts: {str(e)}"
            )


@router.get("/status", response_model=ConflictStatusResponse)
def get_status(investigation_id: str):
    """
    Returns lightweight summary statistics of conflicts and analysis status
    for dashboard badges and status indicators.
    """
    with get_db() as conn:
        try:
            status = get_conflict_status(conn, investigation_id)
            return status
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))


@router.patch("/{conflict_id}", response_model=ConflictItemModel)
def update_conflict_status(
    investigation_id: str,
    conflict_id: str,
    payload: ConflictResolutionUpdateRequest,
):
    """
    Updates the resolution status ('unresolved', 'under_review', 'resolved')
    and reviewer forensic notes for a specific conflict finding.
    Does NOT alter original source evidence or delete conflict records.
    """
    with get_db() as conn:
        try:
            updated = update_conflict_resolution(
                conn,
                investigation_id=investigation_id,
                conflict_id=conflict_id,
                resolution_status=payload.resolution_status,
                reviewer_notes=payload.reviewer_notes,
            )
            return updated
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            logger.error("Failed to update conflict resolution: %s", e, exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))
