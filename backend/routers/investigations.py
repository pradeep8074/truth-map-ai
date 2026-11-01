import uuid
import datetime
from typing import List
from fastapi import APIRouter, HTTPException, BackgroundTasks
from backend.database import get_db
from backend.models import (
    InvestigationCreateRequest,
    InvestigationCreateResponse,
    InvestigationResponse,
    SourceResponse,
    ClaimResponse,
    WorkspaceFreshnessSummary,
)
from backend.services.freshness_service import classify_source_freshness

router = APIRouter(prefix="/api/investigations", tags=["investigations"])


@router.post("", response_model=InvestigationCreateResponse, status_code=201)
async def create_investigation(
    payload: InvestigationCreateRequest,
    background_tasks: BackgroundTasks
):
    """
    Creates a new research investigation.
    Optionally ingests provided initial URLs in the background.
    """
    investigation_id = str(uuid.uuid4())
    created_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    status = "processing" if payload.urls else "ready"

    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO investigations (id, research_question, status, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (investigation_id, payload.research_question, status, created_at)
        )
        conn.commit()

    if payload.urls:
        from backend.routers.sources import ingest_urls_task
        background_tasks.add_task(ingest_urls_task, investigation_id, payload.urls)

    return InvestigationCreateResponse(
        investigation_id=investigation_id,
        status=status,
        message=f"Investigation created with {len(payload.urls)} initial URL(s) queued for ingestion."
    )


def _row_to_source_response(row) -> SourceResponse:
    row_keys = row.keys() if hasattr(row, "keys") else []
    pub_date = row["publication_date"] if "publication_date" in row_keys else None
    val_status = row["date_validation_status"] if "date_validation_status" in row_keys else "MISSING"
    
    classification = classify_source_freshness(pub_date, date_validation_status=val_status)
    freshness_status = row["freshness_status"] if ("freshness_status" in row_keys and row["freshness_status"]) else classification["status"]
    freshness_exp = row["freshness_explanation"] if ("freshness_explanation" in row_keys and row["freshness_explanation"]) else classification["explanation"]
    
    days_old = classification.get("days_old")
    if days_old is not None:
        try:
            days_old = int(days_old)
        except Exception:
            days_old = None

    return SourceResponse(
        id=row["id"],
        investigation_id=row["investigation_id"],
        source_type=row["source_type"],
        source_origin=row["source_origin"] if "source_origin" in row_keys else "UNKNOWN",
        original_url=row["original_url"],
        title=row["title"],
        publisher=row["publisher"],
        publication_date=pub_date,
        source_modified_date=row["source_modified_date"] if "source_modified_date" in row_keys else None,
        date_source=row["date_source"] if "date_source" in row_keys else None,
        date_extraction_method=row["date_extraction_method"] if "date_extraction_method" in row_keys else None,
        date_confidence=float(row["date_confidence"]) if ("date_confidence" in row_keys and row["date_confidence"] is not None) else 0.0,
        date_validation_status=row["date_validation_status"] if ("date_validation_status" in row_keys and row["date_validation_status"]) else "MISSING",
        freshness_status=freshness_status,
        freshness_explanation=freshness_exp or "",
        days_old=days_old,
        retrieved_at=row["retrieved_at"],
        content_hash=row["content_hash"],
        extraction_status=row["extraction_status"],
        passages_count=row["passages_count"] if "passages_count" in row_keys else 0,
        claims_count=row["claims_count"] if "claims_count" in row_keys else 0,
        error_message=row["error_message"] if "error_message" in row_keys else None,
    )


@router.get("/workspace/freshness-summary", response_model=WorkspaceFreshnessSummary)
async def get_workspace_freshness_summary():
    """Returns real date freshness metrics aggregated across the entire workspace."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, publication_date FROM sources")
        rows = cursor.fetchall()

    ref_now = datetime.datetime.now(datetime.timezone.utc)
    total = len(rows)
    dated = 0
    undated = 0
    potentially_outdated = 0
    requires_review = 0

    for r in rows:
        p_date = r["publication_date"]
        res = classify_source_freshness(p_date, reference_time=ref_now)
        st = res["status"]
        if st == "Undated Source":
            undated += 1
        elif st == "Potentially Outdated":
            dated += 1
            potentially_outdated += 1
        elif st == "Date Available":
            dated += 1
        else:
            if p_date and str(p_date).strip():
                dated += 1
            else:
                undated += 1
            requires_review += 1

    return WorkspaceFreshnessSummary(
        total_sources=total,
        dated_sources=dated,
        undated_sources=undated,
        potentially_outdated_sources=potentially_outdated,
        sources_requiring_review=requires_review,
        freshness_threshold_days=365,
        reference_date=ref_now.isoformat(),
    )


@router.get("/{investigation_id}/freshness-summary", response_model=WorkspaceFreshnessSummary)
async def get_investigation_freshness_summary(investigation_id: str):
    """Returns real date freshness metrics for sources within a specific investigation."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, publication_date FROM sources WHERE investigation_id = ?", (investigation_id,))
        rows = cursor.fetchall()

    ref_now = datetime.datetime.now(datetime.timezone.utc)
    total = len(rows)
    dated = 0
    undated = 0
    potentially_outdated = 0
    requires_review = 0

    for r in rows:
        p_date = r["publication_date"]
        res = classify_source_freshness(p_date, reference_time=ref_now)
        st = res["status"]
        if st == "Undated Source":
            undated += 1
        elif st == "Potentially Outdated":
            dated += 1
            potentially_outdated += 1
        elif st == "Date Available":
            dated += 1
        else:
            if p_date and str(p_date).strip():
                dated += 1
            else:
                undated += 1
            requires_review += 1

    return WorkspaceFreshnessSummary(
        total_sources=total,
        dated_sources=dated,
        undated_sources=undated,
        potentially_outdated_sources=potentially_outdated,
        sources_requiring_review=requires_review,
        freshness_threshold_days=365,
        reference_date=ref_now.isoformat(),
    )


@router.get("", response_model=List[InvestigationResponse])
async def list_investigations():
    """Lists all investigations with calculated source, claim, contract, and requirement totals."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                i.id,
                i.research_question,
                i.status,
                i.created_at,
                COUNT(DISTINCT s.id) AS sources_count,
                COUNT(DISTINCT c.id) AS claims_count,
                MAX(CASE WHEN dc.id IS NOT NULL THEN 1 ELSE 0 END) AS has_contract,
                COUNT(DISTINCT cr.id) AS requirements_count
            FROM investigations i
            LEFT JOIN sources s ON s.investigation_id = i.id
            LEFT JOIN claims c ON c.investigation_id = i.id
            LEFT JOIN decision_contracts dc ON dc.investigation_id = i.id
            LEFT JOIN contract_requirements cr ON cr.contract_id = dc.id AND cr.status != 'satisfied'
            GROUP BY i.id
            ORDER BY i.created_at DESC
        """)
        rows = cursor.fetchall()
        
        return [
            InvestigationResponse(
                id=row["id"],
                research_question=row["research_question"],
                status=row["status"],
                created_at=row["created_at"],
                sources_count=row["sources_count"],
                claims_count=row["claims_count"],
                requirements_count=row["requirements_count"],
                has_contract=bool(row["has_contract"]),
            )
            for row in rows
        ]


@router.get("/{investigation_id}", response_model=InvestigationResponse)
async def get_investigation(investigation_id: str):
    """Returns investigation details, status, associated sources, and requirement counts."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM investigations WHERE id = ?", (investigation_id,))
        inv_row = cursor.fetchone()
        if not inv_row:
            raise HTTPException(status_code=404, detail=f"Investigation '{investigation_id}' not found.")

        # Check contract and requirement counts
        cursor.execute("""
            SELECT 
                dc.id,
                COUNT(DISTINCT cr.id) AS req_count
            FROM decision_contracts dc
            LEFT JOIN contract_requirements cr ON cr.contract_id = dc.id AND cr.status != 'satisfied'
            WHERE dc.investigation_id = ?
            GROUP BY dc.id
        """, (investigation_id,))
        contract_info = cursor.fetchone()
        has_contract = contract_info is not None
        requirements_count = contract_info["req_count"] if contract_info else 0

        # Get sources
        cursor.execute("""
            SELECT 
                s.*,
                COUNT(DISTINCT p.id) AS passages_count,
                COUNT(DISTINCT c.id) AS claims_count
            FROM sources s
            LEFT JOIN passages p ON p.source_id = s.id
            LEFT JOIN claims c ON c.source_id = s.id
            WHERE s.investigation_id = ?
            GROUP BY s.id
            ORDER BY s.retrieved_at ASC
        """, (investigation_id,))
        source_rows = cursor.fetchall()

        sources = [_row_to_source_response(row) for row in source_rows]

        # Get total claims count
        cursor.execute("SELECT COUNT(*) FROM claims WHERE investigation_id = ?", (investigation_id,))
        total_claims = cursor.fetchone()[0]

        return InvestigationResponse(
            id=inv_row["id"],
            research_question=inv_row["research_question"],
            status=inv_row["status"],
            created_at=inv_row["created_at"],
            sources_count=len(sources),
            claims_count=total_claims,
            requirements_count=requirements_count,
            has_contract=has_contract,
            sources=sources,
        )


@router.get("/{investigation_id}/sources", response_model=List[SourceResponse])
async def get_investigation_sources(investigation_id: str):
    """Returns all ingested sources for an investigation."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                s.*,
                COUNT(DISTINCT p.id) AS passages_count,
                COUNT(DISTINCT c.id) AS claims_count
            FROM sources s
            LEFT JOIN passages p ON p.source_id = s.id
            LEFT JOIN claims c ON c.source_id = s.id
            WHERE s.investigation_id = ?
            GROUP BY s.id
            ORDER BY s.retrieved_at ASC
        """, (investigation_id,))
        rows = cursor.fetchall()

        return [_row_to_source_response(row) for row in rows]


@router.get("/{investigation_id}/claims", response_model=List[ClaimResponse])
async def get_investigation_claims(investigation_id: str):
    """Returns all extracted atomic claims for an investigation linked with provenance data."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                c.id,
                c.investigation_id,
                c.source_id,
                c.passage_id,
                c.claim_text,
                c.category,
                c.extraction_method,
                c.extraction_confidence,
                c.created_at,
                p.passage_text,
                p.page_number,
                s.title AS source_title,
                s.source_type
            FROM claims c
            JOIN passages p ON p.id = c.passage_id
            JOIN sources s ON s.id = c.source_id
            WHERE c.investigation_id = ?
            ORDER BY c.created_at ASC
        """, (investigation_id,))
        rows = cursor.fetchall()

        return [
            ClaimResponse(
                id=row["id"],
                investigation_id=row["investigation_id"],
                source_id=row["source_id"],
                passage_id=row["passage_id"],
                claim_text=row["claim_text"],
                category=row["category"] if "category" in row.keys() and row["category"] else "factual",
                extraction_method=row["extraction_method"],
                processing_mode="gemini" if "gemini" in (row["extraction_method"] or "").lower() else "fallback",
                extraction_confidence=row["extraction_confidence"],
                created_at=row["created_at"],
                passage_text=row["passage_text"],
                page_number=row["page_number"],
                source_title=row["source_title"],
                source_type=row["source_type"],
            )
            for row in rows
        ]
