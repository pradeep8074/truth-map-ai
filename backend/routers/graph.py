from fastapi import APIRouter, HTTPException, Depends
from backend.database import get_db
from backend.models import (
    EvidenceGraphResponse,
    EvidenceGraphStatusResponse,
)
from backend.services.graph_service import (
    build_evidence_graph_from_db,
    analyze_claim_requirement_relationships,
    get_evidence_graph_status,
)

router = APIRouter(
    prefix="/api/investigations/{investigation_id}/evidence-graph",
    tags=["evidence-graph"]
)


@router.get("", response_model=EvidenceGraphResponse)
@router.get("/", response_model=EvidenceGraphResponse, include_in_schema=False)
def get_evidence_graph(investigation_id: str):
    """
    Returns the full topological Evidence Dependency Graph for an investigation,
    connecting Decision Contract -> Requirements -> Evidence Requirements ->
    Atomic Claims -> Source Passages -> Source Documents.
    Includes any previously analyzed and persisted RELATES_TO edges.
    """
    with get_db() as conn:
        # Check if investigation exists
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM investigations WHERE id = ?;", (investigation_id,))
        if not cursor.fetchone():
            raise HTTPException(
                status_code=404,
                detail=f"Investigation '{investigation_id}' not found."
            )

        graph = build_evidence_graph_from_db(conn, investigation_id)
        return graph


@router.post("/analyze", response_model=EvidenceGraphResponse)
async def analyze_evidence_graph(investigation_id: str):
    """
    Analyzes candidate claim-to-requirement relationships using Gemini semantic reasoning.
    If Gemini is unavailable or errors, gracefully executes deterministic fallback analysis.
    Persists evaluated relationships in SQLite and returns the updated Evidence Graph.
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
            graph = await analyze_claim_requirement_relationships(conn, investigation_id)
            return graph
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Graph relevance analysis failed: {str(e)}"
            )


@router.get("/status", response_model=EvidenceGraphStatusResponse)
def get_graph_status(investigation_id: str):
    """
    Returns lightweight summary status metrics for the Evidence Graph,
    including node/edge counts, represented entities, processing mode, and analysis state.
    """
    with get_db() as conn:
        try:
            status = get_evidence_graph_status(conn, investigation_id)
            return status
        except ValueError as ve:
            raise HTTPException(status_code=404, detail=str(ve))
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to fetch evidence graph status: {str(e)}"
            )
