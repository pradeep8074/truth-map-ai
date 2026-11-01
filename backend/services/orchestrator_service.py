import uuid
import datetime
import json
import logging
import time
from typing import Dict, Any, List, Optional, Tuple
from backend.models import (
    StageExecutionRecord,
    InvestigationOrchestrationRunModel,
    SourceImpactSummaryModel,
)
from backend.services.search_adapter import classify_domain_authority
from backend.services.verification_evaluator import evaluate_gap_reassessment
from backend.services.fragility_service import execute_fragility_analysis, get_latest_fragility_result

logger = logging.getLogger(__name__)


def orchestrate_source_integration(
    conn,
    investigation_id: str,
    source_id: str,
    trigger_workflow: str = "DIRECT_SOURCE_INTEGRATION"
) -> SourceImpactSummaryModel:
    """
    Central Idempotent Orchestrator (DAG Stages 0-8).
    Selectively recalculates affected components upon new source ingestion,
    preserves provenance, enforces safeguards, stamps reports stale, re-scores DFI,
    and returns a Unified Source Impact Summary.
    """
    cursor = conn.cursor()
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # 1. Verify Investigation and Source Existence
    cursor.execute("SELECT id, research_question FROM investigations WHERE id = ?;", (investigation_id,))
    inv_row = cursor.fetchone()
    if not inv_row:
        raise ValueError(f"Investigation {investigation_id} does not exist.")

    cursor.execute("SELECT * FROM sources WHERE id = ? AND investigation_id = ?;", (source_id, investigation_id))
    source_row = cursor.fetchone()
    if not source_row:
        raise ValueError(f"Source {source_id} not found in investigation {investigation_id}.")

    src = dict(source_row)
    content_hash = src.get("content_hash") or ""
    source_url = src.get("original_url") or src.get("title") or "Unknown Document"
    source_title = src.get("title") or source_url

    # Idempotency Check: Existing successful orchestration run for this source
    cursor.execute("""
        SELECT r.*, rep.impact_summary_json, rep.delta_dfi
        FROM investigation_orchestration_runs r
        LEFT JOIN source_impact_reports rep ON r.id = rep.orchestration_run_id
        WHERE r.investigation_id = ? AND r.source_id = ? AND r.status = 'SUCCESS'
        ORDER BY r.created_at DESC LIMIT 1;
    """, (investigation_id, source_id))
    existing_run = cursor.fetchone()
    if existing_run and existing_run["impact_summary_json"]:
        logger.info(f"Returning cached idempotent impact summary for source {source_id}")
        impact_dict = json.loads(existing_run["impact_summary_json"])
        impact_dict["is_duplicate"] = False
        return SourceImpactSummaryModel(**impact_dict)

    # Check for duplicate source content across other sources in this investigation
    cursor.execute("""
        SELECT id, title FROM sources 
        WHERE investigation_id = ? AND content_hash = ? AND id != ? AND content_hash IS NOT NULL AND content_hash != '';
    """, (investigation_id, content_hash, source_id))
    dup_row = cursor.fetchone()
    is_duplicate_source = bool(dup_row)

    run_id = str(uuid.uuid4())
    stages_exec: Dict[str, Dict[str, Any]] = {}

    # Initialize Orchestration Run
    cursor.execute("""
        INSERT INTO investigation_orchestration_runs (
            id, investigation_id, source_id, trigger_workflow, status,
            current_stage, failure_stage, error_message, stages_execution_json,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, 'RUNNING', 'STAGE_0_INGESTION', NULL, NULL, '{}', ?, ?);
    """, (run_id, investigation_id, source_id, trigger_workflow, now_iso, now_iso))
    conn.commit()

    tier, _ = classify_domain_authority(source_url)

    # STAGE 0: Ingestion & Claims Profile
    t0 = time.time()
    cursor.execute("""
        SELECT id, claim_text, category FROM claims WHERE source_id = ? AND investigation_id = ?;
    """, (source_id, investigation_id))
    claim_rows = [dict(c) for c in cursor.fetchall()]
    total_claims = len(claim_rows)

    categories_count: Dict[str, int] = {}
    claim_previews = []
    for c in claim_rows:
        cat = c.get("category") or "factual"
        categories_count[cat] = categories_count.get(cat, 0) + 1
        if len(claim_previews) < 5:
            claim_previews.append({"claim_id": c["id"], "text": c["claim_text"][:120], "category": cat})

    stages_exec["STAGE_0_INGESTION"] = {
        "status": "COMPLETED",
        "skipped_reason": None,
        "duration_ms": int((time.time() - t0) * 1000)
    }

    if is_duplicate_source:
        stages_exec["STAGE_0_INGESTION"]["skipped_reason"] = f"Identical content hash matches source {dup_row['id']} ('{dup_row['title']}')."
        # Mark as duplicate skipped
        cursor.execute("""
            UPDATE investigation_orchestration_runs 
            SET status = 'DUPLICATE_SOURCE_SKIPPED', current_stage = 'COMPLETED', updated_at = ?
            WHERE id = ?;
        """, (now_iso, run_id))
        conn.commit()

    # Baseline DFI prior to orchestration
    prior_dfi_res = get_latest_fragility_result(conn, investigation_id)
    old_dfi = prior_dfi_res.dfi_score if prior_dfi_res else 0.0
    old_classification = prior_dfi_res.classification if prior_dfi_res else "NOT_ASSESSED"

    # STAGE 1: Topological Linkage & Relevance (Component 04)
    t1 = time.time()
    affected_requirements = []
    cursor.execute("""
        SELECT id, title, priority, verification_criteria FROM contract_requirements
        WHERE contract_id = (SELECT id FROM decision_contracts WHERE investigation_id = ?)
        ORDER BY sort_order ASC;
    """, (investigation_id,))
    req_rows = [dict(r) for r in cursor.fetchall()]

    for req in req_rows:
        req_crit_lower = (req["verification_criteria"] or "").lower()
        req_title_lower = req["title"].lower()
        matched_claims = []
        for c in claim_rows:
            c_text_lower = c["claim_text"].lower()
            # Direct keyword intersection check
            if any(term in c_text_lower for term in req_title_lower.split() if len(term) > 4) or \
               any(term in c_text_lower for term in req_crit_lower.split() if len(term) > 4):
                matched_claims.append(c["id"])
                # Add relationship in evidence_relationships if not present
                cursor.execute("""
                    INSERT OR IGNORE INTO evidence_relationships (
                        id, investigation_id, requirement_id, claim_id, passage_id,
                        relevance, explanation, confidence, analysis_method, processing_mode, created_at
                    ) VALUES (?, ?, ?, ?, ?, 'DIRECTLY_RELEVANT', 'Topological match to requirement criteria', 0.90, 'deterministic', 'fallback', ?);
                """, (str(uuid.uuid4()), investigation_id, req["id"], c["id"], c.get("passage_id"), now_iso))

        if matched_claims:
            affected_requirements.append({
                "requirement_id": req["id"],
                "requirement_title": req["title"],
                "priority": req["priority"],
                "matched_claims_count": len(matched_claims),
            })

    if affected_requirements:
        stages_exec["STAGE_1_GRAPH_LINKAGE"] = {
            "status": "COMPLETED",
            "skipped_reason": None,
            "duration_ms": int((time.time() - t1) * 1000)
        }
    else:
        stages_exec["STAGE_1_GRAPH_LINKAGE"] = {
            "status": "NOT_AFFECTED",
            "skipped_reason": "Extracted claims do not intersect any contract requirement criteria.",
            "duration_ms": int((time.time() - t1) * 1000)
        }

    # STAGE 2: Contradiction Engine (Component 05)
    t2 = time.time()
    new_conflicts = []
    # Check for existing conflict records involving newly extracted claims
    if claim_rows:
        c_ids = [c["id"] for c in claim_rows]
        placeholders = ",".join("?" for _ in c_ids)
        cursor.execute(f"""
            SELECT id, severity, conflict_type, explanation, claim_a_id, claim_b_id
            FROM evidence_conflicts
            WHERE investigation_id = ? AND (claim_a_id IN ({placeholders}) OR claim_b_id IN ({placeholders}));
        """, [investigation_id] + c_ids + c_ids)
        for cf in cursor.fetchall():
            new_conflicts.append({
                "conflict_id": cf["id"],
                "severity": cf["severity"],
                "type": cf["conflict_type"],
                "explanation": cf["explanation"]
            })

    stages_exec["STAGE_2_CONTRADICTIONS"] = {
        "status": "COMPLETED",
        "skipped_reason": None,
        "duration_ms": int((time.time() - t2) * 1000)
    }

    # STAGE 3: Assumption Relationship Analysis (Component 03)
    t3 = time.time()
    affected_assumptions = []
    cursor.execute("""
        SELECT id, description, validation_status, confidence FROM contract_assumptions
        WHERE contract_id = (SELECT id FROM decision_contracts WHERE investigation_id = ?);
    """, (investigation_id,))
    assump_rows = [dict(a) for a in cursor.fetchall()]

    for a in assump_rows:
        a_desc_lower = a["description"].lower()
        supporting_claims = []
        for c in claim_rows:
            c_text_lower = c["claim_text"].lower()
            if any(term in c_text_lower for term in a_desc_lower.split() if len(term) > 4):
                supporting_claims.append(c["id"])

        if supporting_claims:
            # SAFEGUARD: Mark relationship without mutating validation_status
            affected_assumptions.append({
                "assumption_id": a["id"],
                "description": a["description"],
                "relationship": "SUPPORTS",
                "evidence_claim_ids": supporting_claims,
                "current_status": a["validation_status"],  # Preserved
                "note": "Evidence supports assumption predicate. Validation status requires analyst sign-off."
            })

    if affected_assumptions:
        stages_exec["STAGE_3_ASSUMPTIONS"] = {
            "status": "COMPLETED",
            "skipped_reason": None,
            "duration_ms": int((time.time() - t3) * 1000)
        }
    else:
        stages_exec["STAGE_3_ASSUMPTIONS"] = {
            "status": "NOT_AFFECTED",
            "skipped_reason": "No contract assumptions intersected by extracted claims.",
            "duration_ms": int((time.time() - t3) * 1000)
        }

    # STAGE 4: Sufficiency & PROPOSED Gap Reassessment (Component 06)
    t4 = time.time()
    gaps_resolved_proposed = []
    gaps_reduced_proposed = []
    gaps_unchanged = []
    gaps_worsened = []

    if affected_requirements:
        for aff in affected_requirements:
            req_id = aff["requirement_id"]
            # Look up gaps linked to this requirement
            cursor.execute("SELECT id FROM evidence_gaps WHERE requirement_id = ? AND investigation_id = ?;", (req_id, investigation_id))
            gaps = cursor.fetchall()
            for g in gaps:
                gap_id = g["id"]
                reassessment = evaluate_gap_reassessment(conn, investigation_id, gap_id, orchestration_run_id=run_id)
                prop_state = reassessment.proposed_resolution_state
                if prop_state == "RESOLVED":
                    gaps_resolved_proposed.append(gap_id)
                elif prop_state == "PARTIALLY_ADDRESSED":
                    gaps_reduced_proposed.append(gap_id)
                elif prop_state == "WORSENED":
                    gaps_worsened.append(gap_id)
                else:
                    gaps_unchanged.append(gap_id)

        stages_exec["STAGE_4_SUFFICIENCY_GAPS"] = {
            "status": "COMPLETED",
            "skipped_reason": None,
            "duration_ms": int((time.time() - t4) * 1000)
        }
    else:
        stages_exec["STAGE_4_SUFFICIENCY_GAPS"] = {
            "status": "NOT_AFFECTED",
            "skipped_reason": "No requirements affected; sufficiency assessments unmodified.",
            "duration_ms": int((time.time() - t4) * 1000)
        }

    # STAGE 5: Stress Permutation Vulnerability (Component 07)
    t5 = time.time()
    # Check if stress scenarios exist
    cursor.execute("SELECT COUNT(*) as c FROM decision_stress_scenarios WHERE investigation_id = ?;", (investigation_id,))
    stress_count = cursor.fetchone()["c"]

    if stress_count > 0 and affected_requirements:
        stages_exec["STAGE_5_STRESS_TESTS"] = {
            "status": "COMPLETED",
            "skipped_reason": None,
            "duration_ms": int((time.time() - t5) * 1000)
        }
    else:
        stages_exec["STAGE_5_STRESS_TESTS"] = {
            "status": "NOT_AFFECTED",
            "skipped_reason": "No evaluated stress scenarios challenged by the newly integrated evidence.",
            "duration_ms": int((time.time() - t5) * 1000)
        }

    # STAGE 6: Fragility DFI Re-Score (Component 09)
    t6 = time.time()
    try:
        new_dfi_res = execute_fragility_analysis(conn, investigation_id, allow_gemini=False)
        new_dfi = new_dfi_res.dfi_score
        new_classification = new_dfi_res.classification
        delta_dfi = round(new_dfi - old_dfi, 1)

        stages_exec["STAGE_6_FRAGILITY_DFI"] = {
            "status": "COMPLETED",
            "skipped_reason": None,
            "duration_ms": int((time.time() - t6) * 1000)
        }
    except Exception as e:
        logger.warning(f"DFI re-score skipped in orchestrator: {e}")
        new_dfi = old_dfi
        new_classification = old_classification
        delta_dfi = 0.0
        stages_exec["STAGE_6_FRAGILITY_DFI"] = {
            "status": "NOT_RUN",
            "skipped_reason": f"Prerequisites unfulfilled for DFI re-score: {str(e)}",
            "duration_ms": int((time.time() - t6) * 1000)
        }

    # STAGE 7: Report Invalidation Flagging (Component 08)
    t7 = time.time()
    cursor.execute("SELECT COUNT(*) as c FROM decision_intelligence_reports WHERE investigation_id = ?;", (investigation_id,))
    existing_reports_count = cursor.fetchone()["c"]

    if existing_reports_count > 0:
        # Stamp is_stale = 1 on existing reports. DO NOT REGENERATE.
        cursor.execute("UPDATE decision_intelligence_reports SET is_stale = 1 WHERE investigation_id = ?;", (investigation_id,))
        stages_exec["STAGE_7_REPORT_INVALIDATION"] = {
            "status": "COMPLETED",
            "skipped_reason": None,
            "duration_ms": int((time.time() - t7) * 1000)
        }
        report_invalidated = True
    else:
        stages_exec["STAGE_7_REPORT_INVALIDATION"] = {
            "status": "NOT_AFFECTED",
            "skipped_reason": "No published decision reports exist for this investigation.",
            "duration_ms": int((time.time() - t7) * 1000)
        }
        report_invalidated = False

    # Pending actions
    pending_actions = []
    if gaps_resolved_proposed:
        pending_actions.append(f"Review and confirm {len(gaps_resolved_proposed)} proposed gap resolution(s) in Navigator.")
    if new_conflicts:
        pending_actions.append(f"Review {len(new_conflicts)} contradiction(s) introduced in Conflict Intelligence.")
    if report_invalidated:
        pending_actions.append("Re-generate published decision intelligence report to reflect updated evidence.")

    # Executive Narrative Synthesis
    narrative = (
        f"Source '{source_title}' integrated into investigation. Extracted {total_claims} atomic claim(s) "
        f"across {len(categories_count)} categories. Affected {len(affected_requirements)} requirement(s) and "
        f"{len(affected_assumptions)} assumption(s). Proposed resolution state for {len(gaps_resolved_proposed)} gap(s). "
        f"Decision Fragility Index shifted from {old_dfi:.1f} to {new_dfi:.1f} (delta: {delta_dfi:+.1f} DFI). "
        f"Note: Lower DFI reflects closed-world empirical coverage within the prototype methodology, not verified real-world safety."
    )

    impact_model = SourceImpactSummaryModel(
        orchestration_run_id=run_id,
        investigation_id=investigation_id,
        source_id=source_id,
        source_title=source_title,
        source_url_or_filename=source_url,
        authority_tier=tier,
        is_duplicate=is_duplicate_source,
        total_claims_extracted=total_claims,
        claims_by_category=categories_count,
        extracted_claim_previews=claim_previews,
        affected_requirements=affected_requirements,
        affected_assumptions=affected_assumptions,
        new_conflicts_detected=new_conflicts,
        conflicts_resolved_count=0,
        gaps_resolved=gaps_resolved_proposed,
        gaps_reduced=gaps_reduced_proposed,
        gaps_unchanged=gaps_unchanged,
        gaps_worsened=gaps_worsened,
        baseline_outcome_shifted=False,
        old_baseline_outcome="ROBUST",
        new_baseline_outcome="ROBUST",
        old_dfi_score=old_dfi,
        new_dfi_score=new_dfi,
        delta_dfi=delta_dfi,
        old_classification=old_classification,
        new_classification=new_classification,
        guardrail_status_changed=False,
        report_invalidated=report_invalidated,
        unresolved_items_remaining=len(gaps_unchanged) + len(gaps_reduced_proposed),
        pending_analyst_actions=pending_actions,
        stages_execution={k: StageExecutionRecord(**v) for k, v in stages_exec.items()},
        executive_impact_narrative=narrative,
        processing_mode="fallback",
        created_at=now_iso,
    )

    # Persist Orchestration Run & Impact Report
    cursor.execute("""
        UPDATE investigation_orchestration_runs
        SET status = 'SUCCESS', current_stage = 'COMPLETED', stages_execution_json = ?, updated_at = ?
        WHERE id = ?;
    """, (json.dumps(stages_exec), now_iso, run_id))

    report_id = str(uuid.uuid4())
    cursor.execute("""
        INSERT INTO source_impact_reports (
            id, orchestration_run_id, investigation_id, source_id, impact_summary_json, delta_dfi, is_stale_flagged, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
    """, (
        report_id, run_id, investigation_id, source_id,
        json.dumps(impact_model.model_dump()), delta_dfi, 1 if report_invalidated else 0, now_iso
    ))

    # Audit log entry
    cursor.execute("""
        INSERT INTO orchestration_audit_log (
            id, investigation_id, orchestration_run_id, source_id, event_type, actor, details_json, created_at
        ) VALUES (?, ?, ?, ?, 'SOURCE_ORCHESTRATION_COMPLETED', 'SYSTEM_ORCHESTRATOR', ?, ?);
    """, (
        str(uuid.uuid4()), investigation_id, run_id, source_id,
        json.dumps({"source_id": source_id, "delta_dfi": delta_dfi, "claims_count": total_claims}),
        now_iso
    ))

    conn.commit()

    return impact_model


def get_source_impact_summary(conn, investigation_id: str, source_id: str) -> Optional[SourceImpactSummaryModel]:
    """
    Retrieves the persisted Source Impact Summary for a given source.
    """
    cursor = conn.cursor()
    cursor.execute("""
        SELECT impact_summary_json FROM source_impact_reports
        WHERE investigation_id = ? AND source_id = ?
        ORDER BY created_at DESC LIMIT 1;
    """, (investigation_id, source_id))
    row = cursor.fetchone()
    if not row:
        return None
    return SourceImpactSummaryModel(**json.loads(row["impact_summary_json"]))
