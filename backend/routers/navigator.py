import json
import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from backend.database import get_db
from backend.models import (
    NavigatorQueueResponse,
    GapVerificationPlanModel,
    PlanGenerationRequest,
    PlanQueriesUpdateRequest,
    GapCandidateSourceModel,
    GapReassessmentModel,
    GapReassessmentCommitRequest,
    CandidateReviewRequest,
    ManualCandidateRequest,
    SourceImpactSummaryModel,
    InvestigationOrchestrationRunModel,
    OrchestrationAuditLogItemModel,
    StageExecutionRecord,
)
from backend.services.verification_planner import (
    get_gap_verification_queue,
    generate_verification_plan,
    update_verification_plan_queries,
    add_manual_candidate_source,
    review_candidate_source,
)
from backend.services.verification_evaluator import (
    evaluate_gap_reassessment,
    commit_gap_reassessment,
)
from backend.services.orchestrator_service import (
    orchestrate_source_integration,
    get_source_impact_summary,
)
from backend.services.search_adapter import (
    execute_search_discovery,
    SEARCH_PROVIDER,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Navigator & Orchestrator"])


@router.get(
    "/api/investigations/{investigation_id}/navigator/gaps/queue",
    response_model=NavigatorQueueResponse,
    summary="Get prioritized verification queue of unresolved gaps",
)
def get_navigator_queue_endpoint(investigation_id: str):
    with get_db() as db:
        try:
            queue = get_gap_verification_queue(db, investigation_id)
            is_active = bool(SEARCH_PROVIDER and SEARCH_PROVIDER != "none")
            return NavigatorQueueResponse(
                investigation_id=investigation_id,
                total_gaps=len(queue),
                search_provider=SEARCH_PROVIDER,
                search_provider_active=is_active,
                queue=queue,
            )
        except Exception as e:
            logger.error(f"Failed to fetch navigator queue: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to load verification queue: {str(e)}")


@router.post(
    "/api/investigations/{investigation_id}/navigator/gaps/{gap_id}/plan",
    response_model=GapVerificationPlanModel,
    summary="Formulate verification objective and search queries for a gap",
)
def generate_verification_plan_endpoint(
    investigation_id: str,
    gap_id: str,
    custom_instructions: Optional[str] = Query(None),
    body: Optional[PlanGenerationRequest] = None,
):
    with get_db() as db:
        try:
            instructions = (body.custom_instructions if body and body.custom_instructions else custom_instructions)
            manual_queries = body.manual_queries if body else None
            return generate_verification_plan(
                db, investigation_id, gap_id,
                custom_instructions=instructions,
                manual_queries=manual_queries
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"Failed to generate verification plan: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to generate plan: {str(e)}")


@router.get(
    "/api/investigations/{investigation_id}/navigator/plans/{plan_id}",
    response_model=GapVerificationPlanModel,
    summary="Fetch verification plan details including candidate sources",
)
def get_verification_plan_endpoint(
    investigation_id: str,
    plan_id: str,
):
    with get_db() as db:
        cursor = db.cursor()
        cursor.execute("""
            SELECT p.*, cr.title as requirement_title
            FROM gap_verification_plans p
            JOIN contract_requirements cr ON p.requirement_id = cr.id
            WHERE p.id = ? AND p.investigation_id = ?;
        """, (plan_id, investigation_id))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Verification plan not found")

        queries = json.loads(row["search_queries_json"])
        warning = row["missing_context_warning"] if "missing_context_warning" in row.keys() else None

        # Fetch candidates
        cursor.execute("""
            SELECT * FROM gap_candidate_sources
            WHERE plan_id = ?
            ORDER BY discovered_at DESC;
        """, (plan_id,))
        cand_rows = cursor.fetchall()
        candidates = [GapCandidateSourceModel(**dict(c)) for c in cand_rows]

        return GapVerificationPlanModel(
            id=row["id"],
            investigation_id=row["investigation_id"],
            gap_id=row["gap_id"],
            requirement_id=row["requirement_id"],
            requirement_title=row["requirement_title"],
            verification_objective=row["verification_objective"],
            required_evidence_type=row["required_evidence_type"],
            target_authority_tier=row["target_authority_tier"],
            search_queries=queries,
            search_provider_status=row["search_provider_status"],
            status=row["status"],
            missing_context_warning=warning,
            created_at=row["created_at"],
            candidates=candidates,
        )


@router.put(
    "/api/investigations/{investigation_id}/navigator/plans/{plan_id}/queries",
    response_model=GapVerificationPlanModel,
    summary="Update or manually provide verification queries for a plan",
)
def update_plan_queries_endpoint(
    investigation_id: str,
    plan_id: str,
    req: PlanQueriesUpdateRequest,
):
    with get_db() as db:
        try:
            return update_verification_plan_queries(db, plan_id, req.queries)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"Failed to update plan queries: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to update queries: {str(e)}")


@router.post(
    "/api/investigations/{investigation_id}/navigator/plans/{plan_id}/candidates/manual",
    response_model=GapCandidateSourceModel,
    summary="Submit a manually discovered candidate URL for triage",
)
def submit_manual_candidate_endpoint(
    investigation_id: str,
    plan_id: str,
    req: ManualCandidateRequest,
):
    with get_db() as db:
        try:
            return add_manual_candidate_source(db, plan_id, investigation_id, req.url, req.title, req.snippet)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"Failed to submit candidate: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to submit candidate: {str(e)}")


@router.post(
    "/api/investigations/{investigation_id}/navigator/plans/{plan_id}/discover",
    summary="Execute automated search discovery if configured, or report unavailable",
)
def execute_discovery_endpoint(
    investigation_id: str,
    plan_id: str,
    max_results: int = Query(5),
):
    with get_db() as db:
        cursor = db.cursor()
        cursor.execute("SELECT verification_objective, search_queries_json FROM gap_verification_plans WHERE id = ?;", (plan_id,))
        p_row = cursor.fetchone()
        if not p_row:
            raise HTTPException(status_code=404, detail="Plan not found")

        queries = json.loads(p_row["search_queries_json"])
        keywords = [w.strip('",.') for w in p_row["verification_objective"].split() if len(w) > 4][:5]

        discovery_result = execute_search_discovery(queries, keywords, max_results=max_results)
        return discovery_result


@router.post(
    "/api/investigations/{investigation_id}/navigator/candidates/{candidate_id}/review",
    response_model=GapCandidateSourceModel,
    summary="HITL Gate 1: Analyst approves or rejects a candidate source",
)
def review_candidate_endpoint(
    investigation_id: str,
    candidate_id: str,
    req: CandidateReviewRequest,
):
    with get_db() as db:
        try:
            return review_candidate_source(db, candidate_id, req.action, req.rejection_reason)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"Failed to review candidate: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to review candidate: {str(e)}")


@router.post(
    "/api/investigations/{investigation_id}/navigator/gaps/{gap_id}/evaluate",
    response_model=GapReassessmentModel,
    summary="Compute deterministic proposed gap reassessment (PROPOSAL ONLY)",
)
def evaluate_gap_endpoint(investigation_id: str, gap_id: str):
    with get_db() as db:
        try:
            return evaluate_gap_reassessment(db, investigation_id, gap_id)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"Failed to evaluate gap: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to evaluate gap: {str(e)}")


@router.post(
    "/api/investigations/{investigation_id}/navigator/reassessments/{reassessment_id}/commit",
    response_model=GapReassessmentModel,
    summary="HITL Gate 2: Analyst commits gap resolution or state transition",
)
def commit_reassessment_endpoint(
    investigation_id: str,
    reassessment_id: str,
    req: GapReassessmentCommitRequest,
):
    with get_db() as db:
        try:
            return commit_gap_reassessment(db, reassessment_id, req)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"Failed to commit reassessment: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to commit reassessment: {str(e)}")


@router.post(
    "/api/investigations/{investigation_id}/navigator/orchestrate/source/{source_id}",
    response_model=SourceImpactSummaryModel,
    summary="Workflow B: Execute Central Orchestrator across Components 02-09 for a newly integrated source",
)
def orchestrate_source_endpoint(
    investigation_id: str,
    source_id: str,
    trigger_workflow: str = Query("DIRECT_SOURCE_INTEGRATION"),
):
    with get_db() as db:
        try:
            return orchestrate_source_integration(db, investigation_id, source_id, trigger_workflow=trigger_workflow)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"Orchestration failed for source {source_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Orchestration failed: {str(e)}")


@router.get(
    "/api/investigations/{investigation_id}/navigator/sources/{source_id}/impact",
    response_model=SourceImpactSummaryModel,
    summary="Get Unified Source Impact Summary for an ingested source",
)
def get_source_impact_endpoint(investigation_id: str, source_id: str):
    with get_db() as db:
        try:
            summary = get_source_impact_summary(db, investigation_id, source_id)
            if not summary:
                # If not yet orchestrated, trigger orchestration dynamically
                summary = orchestrate_source_integration(db, investigation_id, source_id)
            return summary
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            logger.error(f"Failed to get source impact: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to get source impact: {str(e)}")


@router.get(
    "/api/investigations/{investigation_id}/navigator/orchestration/runs/{run_id}",
    response_model=InvestigationOrchestrationRunModel,
    summary="Get execution record of an orchestration run",
)
def get_orchestration_run_endpoint(investigation_id: str, run_id: str):
    with get_db() as db:
        cursor = db.cursor()
        cursor.execute("SELECT * FROM investigation_orchestration_runs WHERE id = ? AND investigation_id = ?;", (run_id, investigation_id))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Orchestration run not found")
        r = dict(row)
        stages_dict = json.loads(r["stages_execution_json"]) if r["stages_execution_json"] else {}
        stages = {k: StageExecutionRecord(**v) for k, v in stages_dict.items()}
        return InvestigationOrchestrationRunModel(
            id=r["id"],
            investigation_id=r["investigation_id"],
            source_id=r["source_id"],
            trigger_workflow=r["trigger_workflow"],
            status=r["status"],
            current_stage=r["current_stage"],
            failure_stage=r["failure_stage"],
            error_message=r["error_message"],
            stages_execution=stages,
            created_at=r["created_at"],
            updated_at=r["updated_at"],
        )


@router.get(
    "/api/investigations/{investigation_id}/navigator/audit-trail",
    response_model=List[OrchestrationAuditLogItemModel],
    summary="Get chronological orchestration and verification audit log",
)
def get_audit_trail_endpoint(investigation_id: str):
    with get_db() as db:
        cursor = db.cursor()
        cursor.execute("""
            SELECT * FROM orchestration_audit_log
            WHERE investigation_id = ?
            ORDER BY created_at DESC LIMIT 100;
        """, (investigation_id,))
        rows = cursor.fetchall()
        items = []
        for r in rows:
            items.append(OrchestrationAuditLogItemModel(
                id=r["id"],
                investigation_id=r["investigation_id"],
                orchestration_run_id=r["orchestration_run_id"],
                source_id=r["source_id"],
                event_type=r["event_type"],
                actor=r["actor"],
                details=json.loads(r["details_json"]) if r["details_json"] else {},
                created_at=r["created_at"],
            ))
        return items
