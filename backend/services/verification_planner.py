import uuid
import datetime
import json
import logging
import re
from typing import Dict, Any, List, Optional
from backend.models import (
    GapVerificationPlanModel,
    GapCandidateSourceModel,
    GapQueueItemModel,
)
from backend.services.search_adapter import (
    classify_domain_authority,
    calculate_candidate_relevance,
    SEARCH_PROVIDER,
)
from backend.security import is_safe_url

logger = logging.getLogger(__name__)


def get_gap_verification_queue(conn, investigation_id: str) -> List[GapQueueItemModel]:
    """
    Retrieves all gaps for an investigation with requirement priority and projected DFI reduction,
    ordered by requirement priority (CRITICAL, HIGH, MEDIUM, LOW) and projected reduction descending.
    """
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            eg.id as gap_id,
            eg.requirement_id,
            cr.title as requirement_title,
            cr.priority,
            eg.gap_description,
            eg.why_it_matters,
            eg.evidence_needed,
            eg.suggested_source_type,
            esa.coverage_status as current_coverage_status
        FROM evidence_gaps eg
        JOIN contract_requirements cr ON eg.requirement_id = cr.id
        LEFT JOIN evidence_sufficiency_assessments esa 
            ON eg.requirement_id = esa.requirement_id AND eg.investigation_id = esa.investigation_id
        WHERE eg.investigation_id = ?
        ORDER BY 
            CASE cr.priority
                WHEN 'CRITICAL' THEN 1
                WHEN 'HIGH' THEN 2
                WHEN 'MEDIUM' THEN 3
                ELSE 4
            END ASC,
            eg.created_at ASC;
    """, (investigation_id,))

    rows = cursor.fetchall()
    queue: List[GapQueueItemModel] = []

    # Get projected reductions from C09 recommendations if available
    cursor.execute("""
        SELECT target_entity_id, projected_dfi_reduction
        FROM decision_fragility_recommendations
        WHERE investigation_id = ? AND recommendation_type IN ('FILL_CRITICAL_GAP', 'CORROBORATE_EVIDENCE');
    """, (investigation_id,))
    recs_map = {r["target_entity_id"]: r["projected_dfi_reduction"] for r in cursor.fetchall()}

    for r in rows:
        gap_id = r["gap_id"]
        req_id = r["requirement_id"]

        # Check existing plan
        cursor.execute("SELECT id, status FROM gap_verification_plans WHERE gap_id = ? ORDER BY created_at DESC LIMIT 1;", (gap_id,))
        plan_row = cursor.fetchone()
        active_plan_id = plan_row["id"] if plan_row else None

        # Check existing reassessment
        cursor.execute("SELECT id, analyst_decision, proposed_resolution_state FROM gap_reassessments WHERE gap_id = ? ORDER BY created_at DESC LIMIT 1;", (gap_id,))
        reassess_row = cursor.fetchone()
        latest_reassess_id = reassess_row["id"] if reassess_row else None

        # Compute verification state
        state = "OPEN"
        if reassess_row:
            decision = reassess_row["analyst_decision"]
            if decision == "APPROVED":
                state = reassess_row["proposed_resolution_state"]
            elif decision == "PENDING_DECISION":
                state = "REASSESSMENT_PROPOSED"
            else:
                state = "UNRESOLVED"
        elif plan_row:
            state = "VERIFICATION_PLANNED" if plan_row["status"] == "PLANNED" else "CANDIDATES_IDENTIFIED"

        proj_reduction = recs_map.get(req_id, 0.0)
        if proj_reduction == 0.0 and r["priority"] == "CRITICAL":
            proj_reduction = 5.0
        elif proj_reduction == 0.0 and r["priority"] == "HIGH":
            proj_reduction = 3.0

        queue.append(GapQueueItemModel(
            gap_id=gap_id,
            requirement_id=req_id,
            requirement_title=r["requirement_title"],
            priority=r["priority"],
            gap_description=r["gap_description"],
            why_it_matters=r["why_it_matters"],
            evidence_needed=r["evidence_needed"],
            suggested_source_type=r["suggested_source_type"] or "Empirical Evidence",
            current_coverage_status=r["current_coverage_status"] or "NO_EVIDENCE",
            projected_dfi_reduction=round(proj_reduction, 1),
            verification_state=state,
            active_plan_id=active_plan_id,
            latest_reassessment_id=latest_reassess_id,
        ))

    return queue


def extract_context_terms(text: str, max_words: int = 8) -> str:
    """Extracts salient non-stopword domain terms from text without templates."""
    if not text:
        return ""
    cleaned = re.sub(r'[^\w\s\-]', ' ', text)
    stopwords = {
        "a", "an", "the", "and", "or", "of", "in", "to", "for", "with", "on", "at", "by", "from",
        "is", "are", "was", "were", "be", "been", "being", "have", "has", "had", "do", "does", "did",
        "shall", "will", "should", "would", "may", "might", "must", "can", "could",
        "this", "that", "these", "those", "it", "its", "as", "if", "not", "no", "into", "onto",
        "about", "above", "below", "under", "over", "between", "through", "per", "via"
    }
    words = [w.strip() for w in cleaned.split() if w.strip().lower() not in stopwords]
    return " ".join(words[:max_words]).strip()


def generate_verification_plan(
    conn,
    investigation_id: str,
    gap_id: str,
    custom_instructions: Optional[str] = None,
    manual_queries: Optional[List[str]] = None
) -> GapVerificationPlanModel:
    """
    Formulates a targeted verification plan, objectives, and dynamically synthesized search queries
    strictly grounded in the actual investigation context (contract, requirement, criteria, gap, assumptions)
    or analyst manual queries.
    Never injects predefined templates, canned operators, or hardcoded queries.
    """
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            eg.id as gap_id,
            eg.requirement_id,
            eg.gap_description,
            eg.evidence_needed,
            eg.suggested_source_type,
            cr.title as requirement_title,
            cr.description as requirement_description,
            cr.priority,
            cr.verification_criteria,
            cr.requirement_type,
            dc.id as contract_id,
            dc.decision_objective,
            inv.research_question
        FROM evidence_gaps eg
        JOIN contract_requirements cr ON eg.requirement_id = cr.id
        JOIN decision_contracts dc ON dc.investigation_id = eg.investigation_id
        JOIN investigations inv ON inv.id = eg.investigation_id
        WHERE eg.id = ? AND eg.investigation_id = ?;
    """, (gap_id, investigation_id))

    row = cursor.fetchone()
    if not row:
        raise ValueError(f"Evidence gap {gap_id} not found in investigation {investigation_id}.")

    req_title = (row["requirement_title"] or "").strip()
    priority = (row["priority"] or "MEDIUM").strip().upper()
    evidence_needed = (row["evidence_needed"] or "").strip()
    gap_description = (row["gap_description"] or "").strip()
    criteria = (row["verification_criteria"] or "").strip()
    objective = (row["decision_objective"] or "").strip()
    research_q = (row["research_question"] or "").strip()
    contract_id = row["contract_id"]
    source_type = (row["suggested_source_type"] or "").strip()
    custom_inst = (custom_instructions or "").strip()

    # Target authority tier derived directly from requirement priority
    target_tier = "TIER_1" if priority == "CRITICAL" else "TIER_2" if priority == "HIGH" else "TIER_3"

    # Evidence type derived directly from the gap's actual suggested source type, requirement type, or criteria
    if source_type and source_type.lower() not in {"none", "unknown", "n/a"}:
        required_evidence_type = source_type
    elif row["requirement_type"]:
        required_evidence_type = f"{row['requirement_type'].capitalize()} Evidence"
    else:
        required_evidence_type = "Empirical Evidence"

    # Verification objective constructed dynamically from context
    verif_objective = (
        f"Verify requirement '{req_title}' to address gap: {evidence_needed or gap_description}."
        if (req_title and (evidence_needed or gap_description))
        else f"Verify empirical evidence for {req_title or objective or research_q}."
    )

    # Fetch linked assumptions for additional context if present
    cursor.execute("""
        SELECT description, validation_status
        FROM contract_assumptions
        WHERE contract_id = ?
        LIMIT 3;
    """, (contract_id,))
    assumptions = cursor.fetchall()

    queries: List[str] = []

    # 1. If explicit manual queries provided by analyst, use them directly
    if manual_queries:
        queries = [q.strip() for q in manual_queries if q and q.strip()]

    # 2. If no manual queries, check if context is sufficient for dynamic generation
    if not queries:
        has_substantive_context = bool(
            (req_title and len(req_title) > 2) or
            (evidence_needed and len(evidence_needed) > 2) or
            (criteria and len(criteria) > 2) or
            (gap_description and len(gap_description) > 2) or
            (custom_inst and len(custom_inst) > 2)
        )

        if not has_substantive_context:
            raise ValueError(
                "Cannot dynamically generate verification queries: Missing required investigation context. "
                "Neither requirement title, verification criteria, evidence needed, nor analyst instructions were provided. "
                "Please provide analyst instructions or enter queries manually."
            )

        core_subject = extract_context_terms(req_title, 6) or extract_context_terms(research_q, 6)
        core_evidence = extract_context_terms(evidence_needed, 8)
        core_criteria = extract_context_terms(criteria, 8)
        core_gap = extract_context_terms(gap_description, 8)
        core_objective = extract_context_terms(objective, 6)

        generated_queries = []

        # Query 1: Target Evidence Query (Subject + Evidence Needed)
        if core_subject and core_evidence:
            generated_queries.append(f"{core_subject} {core_evidence}".strip())
        elif core_evidence:
            generated_queries.append(core_evidence)

        # Query 2: Acceptance Standard Query (Subject + Verification Criteria, or Gap Description)
        if core_subject and core_criteria:
            q_crit = f"{core_subject} {core_criteria}".strip()
            if q_crit not in generated_queries:
                generated_queries.append(q_crit)
        elif core_subject and core_gap:
            q_gap = f"{core_subject} {core_gap}".strip()
            if q_gap not in generated_queries:
                generated_queries.append(q_gap)

        # Query 3: Contextual Objective Query (Objective + Subject + Evidence Needed)
        if core_objective and core_subject:
            q_obj = f"{core_objective} {core_subject} {core_evidence}".strip()
            if q_obj not in generated_queries:
                generated_queries.append(q_obj)

        # Query 4: Directive / Source-Specific Query
        if custom_inst:
            q_inst = f"{core_subject} {custom_inst}".strip()
            if q_inst not in generated_queries:
                generated_queries.append(q_inst)
        elif source_type and len(source_type) > 2 and source_type.lower() not in {"none", "unknown", "n/a", "empirical evidence"}:
            q_src = f"{core_subject} {source_type} {core_evidence}".strip()
            if q_src not in generated_queries:
                generated_queries.append(q_src)
        elif assumptions and len(assumptions) > 0:
            asm_terms = extract_context_terms(assumptions[0]["description"], 6)
            if asm_terms:
                q_asm = f"{core_subject} {asm_terms}".strip()
                if q_asm not in generated_queries:
                    generated_queries.append(q_asm)

        if not generated_queries and core_subject:
            generated_queries.append(core_subject)

        queries = generated_queries

    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    plan_id = str(uuid.uuid4())
    search_provider_status = "ACTIVE" if (SEARCH_PROVIDER and SEARCH_PROVIDER != "none") else "UNAVAILABLE"

    cursor.execute("""
        INSERT INTO gap_verification_plans (
            id, investigation_id, gap_id, requirement_id, verification_objective,
            required_evidence_type, target_authority_tier, search_queries_json,
            search_provider_status, status, missing_context_warning, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'PLANNED', NULL, ?);
    """, (
        plan_id, investigation_id, gap_id, row["requirement_id"], verif_objective,
        required_evidence_type, target_tier, json.dumps(queries),
        search_provider_status, now_iso
    ))

    # Log audit event
    cursor.execute("""
        INSERT INTO orchestration_audit_log (
            id, investigation_id, event_type, actor, details_json, created_at
        ) VALUES (?, ?, 'PLAN_GENERATED', 'SYSTEM_ORCHESTRATOR', ?, ?);
    """, (
        str(uuid.uuid4()), investigation_id,
        json.dumps({"plan_id": plan_id, "gap_id": gap_id, "queries_count": len(queries)}),
        now_iso
    ))

    conn.commit()

    return GapVerificationPlanModel(
        id=plan_id,
        investigation_id=investigation_id,
        gap_id=gap_id,
        requirement_id=row["requirement_id"],
        requirement_title=req_title,
        verification_objective=verif_objective,
        required_evidence_type=required_evidence_type,
        target_authority_tier=target_tier,
        search_queries=queries,
        search_provider_status=search_provider_status,
        status="PLANNED",
        missing_context_warning=None,
        created_at=now_iso,
    )


def update_verification_plan_queries(
    conn,
    plan_id: str,
    queries: List[str]
) -> GapVerificationPlanModel:
    """
    Allows the analyst to manually edit, replace, or add verification queries on a plan.
    Enforces that queries are non-empty strings.
    """
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM gap_verification_plans WHERE id = ?;", (plan_id,))
    p_row = cursor.fetchone()
    if not p_row:
        raise ValueError(f"Verification plan {plan_id} not found.")

    clean_queries = [q.strip() for q in queries if q and q.strip()]
    if not clean_queries:
        raise ValueError("At least one non-empty verification query must be provided.")

    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    cursor.execute("""
        UPDATE gap_verification_plans
        SET search_queries_json = ?, status = 'PLANNED', missing_context_warning = NULL
        WHERE id = ?;
    """, (json.dumps(clean_queries), plan_id))

    # Audit log
    cursor.execute("""
        INSERT INTO orchestration_audit_log (
            id, investigation_id, event_type, actor, details_json, created_at
        ) VALUES (?, ?, 'PLAN_QUERIES_UPDATED', 'ANALYST', ?, ?);
    """, (
        str(uuid.uuid4()), p_row["investigation_id"],
        json.dumps({"plan_id": plan_id, "queries_count": len(clean_queries), "queries": clean_queries}),
        now_iso
    ))
    conn.commit()

    cursor.execute("""
        SELECT p.*, cr.title as requirement_title
        FROM gap_verification_plans p
        JOIN contract_requirements cr ON p.requirement_id = cr.id
        WHERE p.id = ?;
    """, (plan_id,))
    upd = cursor.fetchone()

    return GapVerificationPlanModel(
        id=upd["id"],
        investigation_id=upd["investigation_id"],
        gap_id=upd["gap_id"],
        requirement_id=upd["requirement_id"],
        requirement_title=upd["requirement_title"],
        verification_objective=upd["verification_objective"],
        required_evidence_type=upd["required_evidence_type"],
        target_authority_tier=upd["target_authority_tier"],
        search_queries=clean_queries,
        search_provider_status=upd["search_provider_status"],
        status=upd["status"],
        missing_context_warning=None,
        created_at=upd["created_at"],
    )


def add_manual_candidate_source(
    conn,
    plan_id: str,
    investigation_id: str,
    url: str,
    title: Optional[str] = None,
    snippet: Optional[str] = None
) -> GapCandidateSourceModel:
    """
    Submits a manually discovered URL as a candidate source for triage.
    Validates SSRF boundaries, computes prototype relevance and authority tier,
    and inserts into gap_candidate_sources with PENDING_REVIEW status.
    """
    cursor = conn.cursor()

    # SSRF & URL Validation
    is_safe, reason = is_safe_url(url)
    if not is_safe:
        raise ValueError(f"Security validation rejected candidate URL '{url}': {reason}")

    # Fetch plan details for relevance keyword matching
    cursor.execute("""
        SELECT p.verification_objective, p.search_queries_json, eg.gap_description, eg.evidence_needed, cr.title as req_title
        FROM gap_verification_plans p
        JOIN evidence_gaps eg ON p.gap_id = eg.id
        JOIN contract_requirements cr ON eg.requirement_id = cr.id
        WHERE p.id = ?;
    """, (plan_id,))
    p_row = cursor.fetchone()
    if not p_row:
        raise ValueError(f"Verification plan {plan_id} does not exist.")

    obj_text = p_row["verification_objective"]
    stopwords = {"obtain", "verified", "empirical", "evidence", "substantiate", "specifically", "resolving", "about", "which", "there", "their", "under", "these", "requirement", "disclosure", "compliance", "filetype", "site"}
    text_corpus = f"{p_row['req_title']} {p_row['evidence_needed']} {p_row['gap_description']}".lower()
    raw_words = re.findall(r'[a-zA-Z0-9\-]{3,}', text_corpus)
    keywords = list(dict.fromkeys([w for w in raw_words if w not in stopwords]))

    import urllib.parse
    parsed = urllib.parse.urlparse(url)
    domain = (parsed.hostname or url).lower()

    clean_title = title or f"Document from {domain}"
    clean_snippet = snippet or f"Candidate resource retrieved from domain {domain} for verification objective: {obj_text[:80]}..."

    tier, weight = classify_domain_authority(url)
    rel_score, rel_rationale = calculate_candidate_relevance(clean_title, clean_snippet, keywords, weight)

    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    cand_id = str(uuid.uuid4())

    cursor.execute("""
        INSERT INTO gap_candidate_sources (
            id, plan_id, investigation_id, url, domain, title, snippet,
            authority_tier, relevance_score, discovery_mode, relevance_rationale,
            review_status, rejection_reason, discovered_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'MANUAL_ENTRY', ?, 'PENDING_REVIEW', NULL, ?)
        ON CONFLICT(plan_id, url) DO UPDATE SET
            title = excluded.title,
            snippet = excluded.snippet,
            relevance_score = excluded.relevance_score;
    """, (
        cand_id, plan_id, investigation_id, url, domain, clean_title, clean_snippet,
        tier, rel_score, rel_rationale, now_iso
    ))

    # Update plan status to DISCOVERED
    cursor.execute("UPDATE gap_verification_plans SET status = 'DISCOVERED' WHERE id = ?;", (plan_id,))

    conn.commit()

    return GapCandidateSourceModel(
        id=cand_id,
        plan_id=plan_id,
        investigation_id=investigation_id,
        url=url,
        domain=domain,
        title=clean_title,
        snippet=clean_snippet,
        authority_tier=tier,
        relevance_score=rel_score,
        discovery_mode="MANUAL_ENTRY",
        relevance_rationale=rel_rationale,
        review_status="PENDING_REVIEW",
        rejection_reason=None,
        discovered_at=now_iso,
    )


def review_candidate_source(
    conn,
    candidate_id: str,
    action: str,
    rejection_reason: Optional[str] = None
) -> GapCandidateSourceModel:
    """
    HITL Gate 1: Analyst approves or rejects a candidate source for ingestion.
    """
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM gap_candidate_sources WHERE id = ?;", (candidate_id,))
    row = cursor.fetchone()
    if not row:
        raise ValueError(f"Candidate source {candidate_id} not found.")

    r = dict(row)
    new_status = "APPROVED" if action.upper() == "APPROVE" else "REJECTED"

    cursor.execute("""
        UPDATE gap_candidate_sources
        SET review_status = ?, rejection_reason = ?
        WHERE id = ?;
    """, (new_status, rejection_reason if new_status == "REJECTED" else None, candidate_id))

    # Audit event
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    cursor.execute("""
        INSERT INTO orchestration_audit_log (
            id, investigation_id, event_type, actor, details_json, created_at
        ) VALUES (?, ?, ?, 'ANALYST', ?, ?);
    """, (
        str(uuid.uuid4()), r["investigation_id"],
        "SOURCE_APPROVED" if new_status == "APPROVED" else "SOURCE_REJECTED",
        json.dumps({"candidate_id": candidate_id, "url": r["url"], "action": new_status, "reason": rejection_reason}),
        now_iso
    ))

    conn.commit()

    r["review_status"] = new_status
    r["rejection_reason"] = rejection_reason if new_status == "REJECTED" else None
    return GapCandidateSourceModel(**r)
