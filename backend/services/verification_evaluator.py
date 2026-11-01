import uuid
import datetime
import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from backend.models import (
    GapReassessmentModel,
    GapReassessmentCommitRequest,
)
from backend.services.search_adapter import classify_domain_authority

logger = logging.getLogger(__name__)


def evaluate_gap_reassessment(
    conn,
    investigation_id: str,
    gap_id: str,
    orchestration_run_id: Optional[str] = None
) -> GapReassessmentModel:
    """
    Computes a deterministic PROPOSED gap reassessment based on claims and sources
    linked to the gap's requirement.
    MANDATORY SAFEGUARD: Never automatically transitions a gap to RESOLVED.
    Stores the proposed state as PENDING_DECISION for analyst review.
    """
    cursor = conn.cursor()

    # 1. Fetch Gap and Requirement metadata
    cursor.execute("""
        SELECT 
            eg.id as gap_id,
            eg.requirement_id,
            eg.gap_description,
            eg.evidence_needed,
            cr.title as requirement_title,
            cr.priority,
            cr.verification_criteria,
            esa.coverage_status as previous_coverage_status
        FROM evidence_gaps eg
        JOIN contract_requirements cr ON eg.requirement_id = cr.id
        LEFT JOIN evidence_sufficiency_assessments esa 
            ON eg.requirement_id = esa.requirement_id AND eg.investigation_id = esa.investigation_id
        WHERE eg.id = ? AND eg.investigation_id = ?;
    """, (gap_id, investigation_id))
    row = cursor.fetchone()
    if not row:
        raise ValueError(f"Evidence gap {gap_id} not found in investigation {investigation_id}.")

    req_id = row["requirement_id"]
    priority = row["priority"]
    criteria = (row["verification_criteria"] or "").lower()
    previous_state = row["previous_coverage_status"] or "NO_EVIDENCE"

    # 2. Fetch all claims linked to this requirement via evidence_relationships or source
    cursor.execute("""
        SELECT DISTINCT c.id, c.claim_text, c.category, c.source_id, s.source_type, s.original_url
        FROM claims c
        JOIN evidence_relationships er ON c.id = er.claim_id
        JOIN sources s ON c.source_id = s.id
        WHERE er.requirement_id = ? AND c.investigation_id = ?;
    """, (req_id, investigation_id))
    claim_rows = cursor.fetchall()

    matched_claim_ids = [r["id"] for r in claim_rows]

    # 3. Check for active C05 conflicts involving matched claims
    has_critical_conflict = False
    if matched_claim_ids:
        placeholders = ",".join("?" for _ in matched_claim_ids)
        cursor.execute(f"""
            SELECT id, severity, resolution_status
            FROM evidence_conflicts
            WHERE investigation_id = ? 
              AND resolution_status = 'unresolved'
              AND (claim_a_id IN ({placeholders}) OR claim_b_id IN ({placeholders}));
        """, [investigation_id] + matched_claim_ids + matched_claim_ids)
        conflicts = cursor.fetchall()
        for cf in conflicts:
            if cf["severity"] in ("CRITICAL", "HIGH"):
                has_critical_conflict = True
                break

    # 4. Deterministic Scoring Heuristic
    if not matched_claim_ids:
        c_pred = 0.0
        e_score = 0.0
        proposed = "UNCHANGED"
    elif has_critical_conflict:
        c_pred = 20.0
        e_score = 15.0
        proposed = "WORSENED"
    else:
        # Evaluate predicate fulfillment (C_predicate)
        # Check keyword intersection between claims and verification criteria
        criteria_keywords = [w.strip('",.') for w in criteria.split() if len(w) > 4][:6]
        all_claim_text = " ".join(r["claim_text"].lower() for r in claim_rows)

        matches = sum(1 for kw in criteria_keywords if kw in all_claim_text)
        kw_ratio = matches / max(1, len(criteria_keywords))

        # Check statistical match if numbers are present
        has_stats = any(r["category"] == "statistical" for r in claim_rows)

        if kw_ratio >= 0.75 and (has_stats or "statistical" not in criteria):
            c_pred = 100.0
        elif kw_ratio >= 0.40:
            c_pred = 50.0
        else:
            c_pred = 20.0

        # Authority Tier Evaluation (T_auth)
        distinct_sources = {r["source_id"]: r["original_url"] for r in claim_rows}
        max_auth_weight = 0.25
        for url in distinct_sources.values():
            _, weight = classify_domain_authority(url or "")
            if weight > max_auth_weight:
                max_auth_weight = weight
        t_auth = max_auth_weight * 100.0

        # Freshness (T_freshness) - default 100 for newly ingested
        t_fresh = 100.0

        # Corroboration (I_corroboration)
        i_corrob = 100.0 if len(distinct_sources) >= 2 else 50.0

        # Composite Evidence Score
        e_score = round(0.35 * c_pred + 0.25 * t_auth + 0.20 * t_fresh + 0.20 * i_corrob, 1)

        # Deterministic Gating Rules
        if priority == "CRITICAL":
            if c_pred == 100.0 and e_score >= 80.0 and max_auth_weight >= 0.85:
                proposed = "RESOLVED"
            elif e_score >= 50.0:
                proposed = "PARTIALLY_ADDRESSED"
            else:
                proposed = "UNCHANGED"
        else:
            if c_pred >= 80.0 and e_score >= 70.0 and max_auth_weight >= 0.60:
                proposed = "RESOLVED"
            elif e_score >= 45.0:
                proposed = "PARTIALLY_ADDRESSED"
            else:
                proposed = "UNCHANGED"

    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    reassess_id = str(uuid.uuid4())

    cursor.execute("""
        INSERT INTO gap_reassessments (
            id, investigation_id, gap_id, orchestration_run_id, previous_state,
            proposed_resolution_state, analyst_decision, analyst_final_state,
            analyst_notes, reviewed_by, reviewed_at, matched_claim_ids_json,
            predicate_fulfillment_score, composite_evidence_score, is_analyst_override,
            created_at
        ) VALUES (?, ?, ?, ?, ?, ?, 'PENDING_DECISION', NULL, NULL, NULL, NULL, ?, ?, ?, 0, ?);
    """, (
        reassess_id, investigation_id, gap_id, orchestration_run_id, previous_state,
        proposed, json.dumps(matched_claim_ids), c_pred, e_score, now_iso
    ))

    conn.commit()

    return GapReassessmentModel(
        id=reassess_id,
        investigation_id=investigation_id,
        gap_id=gap_id,
        orchestration_run_id=orchestration_run_id,
        previous_state=previous_state,
        proposed_resolution_state=proposed,
        analyst_decision="PENDING_DECISION",
        analyst_final_state=None,
        analyst_notes=None,
        reviewed_by=None,
        reviewed_at=None,
        matched_claim_ids=matched_claim_ids,
        predicate_fulfillment_score=c_pred,
        composite_evidence_score=e_score,
        is_analyst_override=False,
        created_at=now_iso,
    )


def commit_gap_reassessment(
    conn,
    reassessment_id: str,
    req: GapReassessmentCommitRequest
) -> GapReassessmentModel:
    """
    HITL Gate 2: The ONLY mechanism permitted to commit a gap resolution or state transition.
    Updates the gap reassessment record with analyst decision, notes, and effective final state,
    and selectively updates Component 06 evidence sufficiency and gap records.
    """
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM gap_reassessments WHERE id = ?;", (reassessment_id,))
    row = cursor.fetchone()
    if not row:
        raise ValueError(f"Gap reassessment {reassessment_id} not found.")

    r = dict(row)
    gap_id = r["gap_id"]
    investigation_id = r["investigation_id"]
    proposed_state = r["proposed_resolution_state"]
    final_state = req.analyst_final_state.upper()
    decision = req.analyst_decision.upper()

    is_override = int(final_state != proposed_state)
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # 1. Update Gap Reassessment
    cursor.execute("""
        UPDATE gap_reassessments
        SET analyst_decision = ?,
            analyst_final_state = ?,
            analyst_notes = ?,
            reviewed_by = ?,
            reviewed_at = ?,
            is_analyst_override = ?
        WHERE id = ?;
    """, (decision, final_state, req.analyst_notes, req.analyst_id, now_iso, is_override, reassessment_id))

    # 2. Update Component 06 Sufficiency & Gaps accordingly
    cursor.execute("SELECT requirement_id FROM evidence_gaps WHERE id = ?;", (gap_id,))
    gap_row = cursor.fetchone()
    if gap_row:
        requirement_id = gap_row["requirement_id"]
        if final_state == "RESOLVED":
            # Upgrade coverage status in evidence_sufficiency_assessments
            cursor.execute("""
                UPDATE evidence_sufficiency_assessments
                SET coverage_status = 'SUFFICIENT', updated_at = ?
                WHERE investigation_id = ? AND requirement_id = ?;
            """, (now_iso, investigation_id, requirement_id))
            # Delete or close the specific gap
            cursor.execute("DELETE FROM evidence_gaps WHERE id = ?;", (gap_id,))
        elif final_state == "PARTIALLY_ADDRESSED":
            cursor.execute("""
                UPDATE evidence_sufficiency_assessments
                SET coverage_status = 'PARTIAL', updated_at = ?
                WHERE investigation_id = ? AND requirement_id = ?;
            """, (now_iso, investigation_id, requirement_id))
        elif final_state == "WORSENED":
            cursor.execute("""
                UPDATE evidence_sufficiency_assessments
                SET coverage_status = 'CONFLICTING', updated_at = ?
                WHERE investigation_id = ? AND requirement_id = ?;
            """, (now_iso, investigation_id, requirement_id))

    # 3. Log Audit Event
    cursor.execute("""
        INSERT INTO orchestration_audit_log (
            id, investigation_id, event_type, actor, details_json, created_at
        ) VALUES (?, ?, 'REASSESSMENT_COMMITTED', 'ANALYST', ?, ?);
    """, (
        str(uuid.uuid4()), investigation_id,
        json.dumps({
            "reassessment_id": reassessment_id,
            "gap_id": gap_id,
            "previous_state": r["previous_state"],
            "proposed_state": proposed_state,
            "final_state": final_state,
            "is_override": bool(is_override),
            "analyst_id": req.analyst_id,
            "notes": req.analyst_notes,
        }),
        now_iso
    ))

    conn.commit()

    r["analyst_decision"] = decision
    r["analyst_final_state"] = final_state
    r["analyst_notes"] = req.analyst_notes
    r["reviewed_by"] = req.analyst_id
    r["reviewed_at"] = now_iso
    r["is_analyst_override"] = bool(is_override)
    r["matched_claim_ids"] = json.loads(r["matched_claim_ids_json"]) if r["matched_claim_ids_json"] else []

    return GapReassessmentModel(**r)
