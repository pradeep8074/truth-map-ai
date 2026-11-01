import re
import uuid
import json
import datetime
import logging
from typing import Dict, Any, List, Optional, Set, Tuple

from backend.config import GEMINI_API_KEY, GEMINI_MODEL
from backend.models import (
    EvidenceGapModel,
    SupportingClaimInfo,
    RelatedConflictInfo,
    RequirementSufficiencyAssessment,
    SufficiencySummaryModel,
    SufficiencyResponse,
    SufficiencyStatusResponse,
    GeminiSufficiencyPayload,
    GeminiRequirementSufficiencyItem,
    GeminiSufficiencyGapItem,
)

logger = logging.getLogger(__name__)

STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "if", "because", "as", "what",
    "which", "this", "that", "these", "those", "then", "just", "so", "than",
    "such", "both", "through", "about", "for", "is", "of", "while", "during",
    "to", "from", "in", "out", "on", "off", "again", "further", "then", "once",
    "here", "there", "when", "where", "why", "how", "all", "any", "both",
    "each", "few", "more", "most", "other", "some", "such", "no", "nor", "not",
    "only", "own", "same", "too", "very", "can", "will", "should",
    "now", "be", "been", "being", "have", "has", "had", "do", "does", "did",
}


def extract_keywords(text: str) -> Set[str]:
    """Tokenizes and returns lowercase non-stopwords of length > 2."""
    words = re.findall(r"[a-zA-Z0-9%]+", (text or "").lower())
    return {w for w in words if w not in STOPWORDS and len(w) > 2}


def evaluate_deterministic_relevance(req_text: str, claim_text: str) -> str:
    """Heuristic relevance classifier if graph relationships are uncomputed."""
    req_kw = extract_keywords(req_text)
    clm_kw = extract_keywords(claim_text)
    overlap = req_kw.intersection(clm_kw)
    if len(overlap) >= 3:
        return "DIRECTLY_RELEVANT"
    elif len(overlap) >= 1:
        return "PARTIALLY_RELEVANT"
    return "NOT_RELEVANT"


def evaluate_deterministic_sufficiency(
    req: Dict[str, Any],
    linked_claims: List[Any],
    related_conflicts: List[Any],
) -> Tuple[str, str, str, str, str, float, List[Dict[str, Any]]]:
    """
    Deterministic rule-based sufficiency evaluation:
    Returns (coverage_status, assessment_summary, limitations, missing_info, recommended_action, confidence, gaps).
    Handles both SupportingClaimInfo/RelatedConflictInfo models and dictionary objects.
    """
    def _get_field(obj: Any, key: str, default: Any = None) -> Any:
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)

    unresolved_conflicts = [c for c in related_conflicts if bool(_get_field(c, "is_unresolved", False))]
    distinct_sources = list({
        _get_field(c, "source_title")
        for c in linked_claims
        if _get_field(c, "source_title")
    })
    directly_relevant = [
        c for c in linked_claims
        if _get_field(c, "relevance") == "DIRECTLY_RELEVANT"
    ]

    # 1. No evidence found
    if not linked_claims:
        status = "NO_EVIDENCE"
        summary = f"No evidence found. Ingested sources contain zero claims or passages addressing '{req['title']}'."
        limitations = "Complete evidentiary void. Relying on this requirement without empirical support introduces high decision risk."
        missing_info = f"Empirical data, operational documentation, or baseline measurements satisfying verification criteria: {req.get('verification_criteria') or 'Required'}"
        action = f"Ingest targeted primary sources or regulatory filings directly testing '{req['title']}'."
        confidence = 1.0
        gaps = [{
            "gap_description": f"Complete lack of evidentiary support for '{req['title']}'.",
            "why_it_matters": f"The decision contract designates '{req['title']}' as {req.get('priority', 'HIGH')} priority, but no extracted claims substantiate it.",
            "evidence_needed": f"Empirical verification satisfying criteria: {req.get('verification_criteria', 'Primary documentation')}",
            "suggested_source_type": "Authoritative Audit / Regulatory Filing",
            "priority": "HIGH" if req.get("priority", "").upper() in {"CRITICAL", "HIGH"} else "MEDIUM",
        }]
        return status, summary, limitations, missing_info, action, confidence, gaps

    # 2. Material unresolved conflict exists
    if unresolved_conflicts:
        status = "CONFLICTING"
        summary = f"Evidentiary basis is contested by {len(unresolved_conflicts)} active unresolved conflict(s) directly challenging supporting claims."
        limitations = "Opposing sources provide contradictory factual, numerical, or causal findings regarding key metrics."
        missing_info = "Reconciliation of opposing research methodologies or third-party primary verification to resolve conflicting claims."
        action = "Cross-examine the conflicting claims in the Conflict Intelligence module to resolve factual discrepancies before relying on this requirement."
        confidence = 0.90
        gaps = [{
            "gap_description": f"Unresolved evidence contradiction regarding '{req['title']}'.",
            "why_it_matters": "Contradictory evidence creates decision instability; relying on contested claims risks incorrect decisions.",
            "evidence_needed": "Independent third-party empirical corroboration or standardized accounting audits to arbitrate between the conflicting sources.",
            "suggested_source_type": "Independent Regulatory Audit",
            "priority": "HIGH",
        }]
        return status, summary, limitations, missing_info, action, confidence, gaps

    # 3. Multiple directly relevant claims from multiple distinct sources
    def _extract_conf(c: Any) -> float:
        val = _get_field(c, "extraction_confidence")
        if val is None:
            val = _get_field(c, "confidence")
        try:
            return float(val) if val is not None else 0.8
        except (ValueError, TypeError):
            return 0.8

    avg_conf = sum(_extract_conf(c) for c in linked_claims) / len(linked_claims) if linked_claims else 0.8
    if len(directly_relevant) >= 2 and len(distinct_sources) >= 2 and avg_conf >= 0.80:
        status = "SUFFICIENT"
        summary = f"Adequately corroborated by {len(linked_claims)} claim(s) across {len(distinct_sources)} independent sources with no unresolved contradictions."
        limitations = "Ongoing validity assumes underlying source measurements remain current and methods remain stable."
        missing_info = "No critical evidentiary gaps identified for current decision phase."
        action = "Requirement is satisfied for current decision phase; proceed to fragility stress testing."
        confidence = round(min(0.95, avg_conf), 2)
        gaps = []
        return status, summary, limitations, missing_info, action, confidence, gaps

    # 4. Partial evidence: at least one directly relevant claim or multiple partial claims
    if len(directly_relevant) >= 1 or len(linked_claims) >= 2:
        status = "PARTIAL"
        summary = f"Partial coverage. Evidence exists ({len(linked_claims)} claim(s)), but lacks multi-source corroboration or comprehensive scope across all verification dimensions."
        src_label = distinct_sources[0] if distinct_sources else "Single source"
        limitations = f"Supported predominantly by '{src_label}', posing a single-source dependency bias."
        missing_info = f"Independent secondary corroboration and empirical metrics satisfying: {req.get('verification_criteria', 'Comprehensive proof')}"
        action = f"Ingest independent external sources to confirm single-source assertions regarding '{req['title']}'."
        confidence = round(min(0.85, avg_conf), 2)
        gaps = [{
            "gap_description": f"Lack of independent multi-source corroboration for '{req['title']}'.",
            "why_it_matters": "Findings from a single reporting body cannot be independently verified, leaving the requirement vulnerable to source bias.",
            "evidence_needed": f"Secondary independent study or audit confirming: {req.get('verification_criteria', 'Key metrics')}",
            "suggested_source_type": "Independent Academic / Industry Study",
            "priority": "MEDIUM",
        }]
        return status, summary, limitations, missing_info, action, confidence, gaps

    # 5. Insufficient evidence: only contextual or weak claims
    status = "INSUFFICIENT"
    summary = f"Insufficient evidence. Available claims provide only tangential or contextual background without direct empirical proof of '{req['title']}'."
    limitations = "Linked claims do not satisfy the specific verification criteria set out in the decision contract."
    missing_info = f"Direct empirical measurements or verified filings testing: {req.get('verification_criteria', 'Direct proof')}"
    action = f"Ingest targeted evidence directly testing '{req['title']}' rather than tangential domain background."
    confidence = 0.80
    gaps = [{
        "gap_description": f"Evidence is tangential and fails to satisfy verification criteria for '{req['title']}'.",
        "why_it_matters": "Contextual evidence provides background context but does not substantiate the requirement's operational criteria.",
        "evidence_needed": f"Direct measurements satisfying verification criteria: {req.get('verification_criteria', 'Empirical data')}",
        "suggested_source_type": "Official Verification Report / Operating Data",
        "priority": "HIGH",
    }]
    return status, summary, limitations, missing_info, action, confidence, gaps


def get_investigation_sufficiency(conn, investigation_id: str) -> SufficiencyResponse:
    """
    Retrieves the persisted sufficiency assessments, evidence gaps,
    and summary metrics for an investigation.
    """
    cursor = conn.cursor()

    # 1. Fetch Contract
    cursor.execute("""
        SELECT id, decision_objective FROM decision_contracts WHERE investigation_id = ?;
    """, (investigation_id,))
    contract_row = cursor.fetchone()
    contract_id = contract_row["id"] if contract_row else None
    decision_objective = contract_row["decision_objective"] if contract_row else None

    # 2. Fetch Requirements
    cursor.execute("""
        SELECT id, title, description, requirement_type, priority, verification_criteria, status, sort_order
        FROM contract_requirements
        WHERE contract_id = ?
        ORDER BY sort_order ASC;
    """, (contract_id,) if contract_id else ("__none__",))
    req_rows = [dict(r) for r in cursor.fetchall()]

    if not req_rows:
        return SufficiencyResponse(
            investigation_id=investigation_id,
            contract_id=contract_id,
            decision_objective=decision_objective,
            assessments=[],
            summary=SufficiencySummaryModel(),
            processing_mode="pending",
        )

    # 3. Fetch Sufficiency Assessments
    cursor.execute("""
        SELECT * FROM evidence_sufficiency_assessments
        WHERE investigation_id = ?;
    """, (investigation_id,))
    assessment_map = {r["requirement_id"]: dict(r) for r in cursor.fetchall()}

    # 4. Fetch Evidence Gaps
    cursor.execute("""
        SELECT * FROM evidence_gaps
        WHERE investigation_id = ?;
    """, (investigation_id,))
    gaps_by_req: Dict[str, List[EvidenceGapModel]] = {}
    for g in cursor.fetchall():
        gap_obj = EvidenceGapModel(
            id=g["id"],
            investigation_id=g["investigation_id"],
            requirement_id=g["requirement_id"],
            assessment_id=g["assessment_id"],
            gap_description=g["gap_description"],
            why_it_matters=g["why_it_matters"],
            evidence_needed=g["evidence_needed"],
            suggested_source_type=g["suggested_source_type"],
            priority=g["priority"],
            created_at=g["created_at"],
        )
        gaps_by_req.setdefault(g["requirement_id"], []).append(gap_obj)

    # 5. Fetch Linked Claims with provenance for each requirement
    claims_query = """
        SELECT
            r.requirement_id, r.relevance, r.explanation AS relevance_explanation,
            c.id AS claim_id, c.claim_text, c.category, c.extraction_confidence,
            s.id AS source_id, s.title AS source_title, s.source_type, s.original_url,
            p.id AS passage_id, p.passage_text, p.page_number, p.sha256_hash
        FROM evidence_relationships r
        JOIN claims c ON r.claim_id = c.id
        LEFT JOIN sources s ON c.source_id = s.id
        LEFT JOIN passages p ON c.passage_id = p.id
        WHERE r.investigation_id = ? AND r.relevance IN ('DIRECTLY_RELEVANT', 'PARTIALLY_RELEVANT', 'CONTEXTUAL');
    """
    cursor.execute(claims_query, (investigation_id,))
    claims_by_req: Dict[str, List[SupportingClaimInfo]] = {}
    for row in cursor.fetchall():
        c_info = SupportingClaimInfo(
            claim_id=row["claim_id"],
            claim_text=row["claim_text"],
            category=row["category"],
            relevance=row["relevance"],
            relevance_explanation=row["relevance_explanation"],
            extraction_confidence=row["extraction_confidence"] or 0.85,
            source_id=row["source_id"],
            source_title=row["source_title"],
            source_type=row["source_type"],
            source_url=row["original_url"],
            passage_id=row["passage_id"],
            passage_text=row["passage_text"],
            page_number=row["page_number"],
            sha256_hash=row["sha256_hash"],
        )
        claims_by_req.setdefault(row["requirement_id"], []).append(c_info)

    # 6. Fetch Conflicts
    cursor.execute("""
        SELECT
            ec.id AS conflict_id, ec.claim_a_id, ec.claim_b_id, ec.conflict_type,
            ec.severity, ec.explanation, ec.resolution_status,
            ca.claim_text AS claim_a_text, cb.claim_text AS claim_b_text
        FROM evidence_conflicts ec
        LEFT JOIN claims ca ON ec.claim_a_id = ca.id
        LEFT JOIN claims cb ON ec.claim_b_id = cb.id
        WHERE ec.investigation_id = ?;
    """, (investigation_id,))
    conflicts_rows = [dict(r) for r in cursor.fetchall()]

    assessments: List[RequirementSufficiencyAssessment] = []
    sufficient_cnt = 0
    partial_cnt = 0
    insufficient_cnt = 0
    no_ev_cnt = 0
    conflicting_cnt = 0
    total_gaps = 0
    high_gaps = 0
    med_gaps = 0
    low_gaps = 0

    processing_mode = "pending"
    last_analyzed_at = None

    for req in req_rows:
        rid = req["id"]
        linked_claims = claims_by_req.get(rid, [])
        linked_claim_ids = {c.claim_id for c in linked_claims}

        # Identify conflicts that involve any of these claims
        req_conflicts: List[RelatedConflictInfo] = []
        for conf in conflicts_rows:
            ca_id = conf["claim_a_id"]
            cb_id = conf["claim_b_id"]
            if ca_id in linked_claim_ids or cb_id in linked_claim_ids:
                opp_text = conf["claim_b_text"] if ca_id in linked_claim_ids else conf["claim_a_text"]
                is_unresolved = (conf["resolution_status"] != "resolved")
                req_conflicts.append(RelatedConflictInfo(
                    conflict_id=conf["conflict_id"],
                    claim_a_id=ca_id,
                    claim_b_id=cb_id,
                    opposing_claim_text=opp_text or "",
                    conflict_type=conf["conflict_type"],
                    severity=conf["severity"],
                    explanation=conf["explanation"],
                    resolution_status=conf["resolution_status"],
                    is_unresolved=is_unresolved,
                ))

        unres_count = sum(1 for c in req_conflicts if c.is_unresolved)
        gaps_list = gaps_by_req.get(rid, [])

        if rid in assessment_map:
            asm = assessment_map[rid]
            cov_status = asm["coverage_status"]
            summary_text = asm["assessment_summary"]
            limitations = asm["limitations"]
            missing_info = asm["missing_information"]
            action = asm["recommended_action"]
            confidence = asm["confidence"]
            method = asm["analysis_method"]
            mode = asm["processing_mode"]
            analyzed_at = asm["updated_at"]
            processing_mode = mode
            last_analyzed_at = analyzed_at
        else:
            # Deterministic fallback default on read if not yet analyzed
            status_calc, sum_calc, lim_calc, miss_calc, act_calc, conf_calc, gen_gaps = evaluate_deterministic_sufficiency(
                req, linked_claims, req_conflicts
            )
            cov_status = status_calc
            summary_text = sum_calc
            limitations = lim_calc
            missing_info = miss_calc
            action = act_calc
            confidence = conf_calc
            method = "deterministic_rule_engine"
            mode = "fallback"
            analyzed_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
            if not gaps_list:
                gaps_list = [
                    EvidenceGapModel(
                        id=f"gap_preview_{idx}",
                        investigation_id=investigation_id,
                        requirement_id=rid,
                        gap_description=g["gap_description"],
                        why_it_matters=g["why_it_matters"],
                        evidence_needed=g["evidence_needed"],
                        suggested_source_type=g.get("suggested_source_type", "Authoritative Audit"),
                        priority=g.get("priority", "HIGH"),
                        created_at=analyzed_at,
                    )
                    for idx, g in enumerate(gen_gaps)
                ]

        # Tally counts
        if cov_status == "SUFFICIENT":
            sufficient_cnt += 1
        elif cov_status == "PARTIAL":
            partial_cnt += 1
        elif cov_status == "INSUFFICIENT":
            insufficient_cnt += 1
        elif cov_status == "NO_EVIDENCE":
            no_ev_cnt += 1
        elif cov_status == "CONFLICTING":
            conflicting_cnt += 1

        for g in gaps_list:
            total_gaps += 1
            p = g.priority.upper()
            if p == "HIGH":
                high_gaps += 1
            elif p == "MEDIUM":
                med_gaps += 1
            else:
                low_gaps += 1

        assessments.append(RequirementSufficiencyAssessment(
            requirement_id=rid,
            investigation_id=investigation_id,
            requirement_title=req["title"],
            requirement_description=req["description"],
            requirement_type=req["requirement_type"],
            priority=req["priority"],
            verification_criteria=req["verification_criteria"],
            coverage_status=cov_status,
            assessment_summary=summary_text,
            supporting_claims=linked_claims,
            supporting_claim_ids=[c.claim_id for c in linked_claims],
            supporting_passage_ids=list({c.passage_id for c in linked_claims if c.passage_id}),
            source_ids=list({c.source_id for c in linked_claims if c.source_id}),
            related_conflicts=req_conflicts,
            related_conflict_ids=[c.conflict_id for c in req_conflicts],
            unresolved_conflict_count=unres_count,
            limitations=limitations,
            missing_information=missing_info,
            recommended_action=action,
            gaps=gaps_list,
            confidence=confidence,
            analysis_method=method,
            processing_mode=mode,
            analyzed_at=analyzed_at,
        ))

    # Check latest audit run for authoritative processing mode and timestamp
    cursor.execute("""
        SELECT processing_mode, analysis_status, created_at
        FROM evidence_sufficiency_runs
        WHERE investigation_id = ?
        ORDER BY created_at DESC LIMIT 1;
    """, (investigation_id,))
    run_row = cursor.fetchone()
    if run_row:
        processing_mode = run_row["processing_mode"]
        last_analyzed_at = run_row["created_at"]

    total_reqs = len(req_rows)
    coverage_ratio = round((sufficient_cnt * 1.0 + partial_cnt * 0.5) / max(total_reqs, 1), 2)
    coverage_expl = (
        f"Coverage ratio is computed as (Sufficient + 0.5 * Partial) / {total_reqs} total requirements. "
        "This metric reflects evidentiary coverage completeness, NOT overall decision correctness."
    )

    summary_obj = SufficiencySummaryModel(
        total_requirements=total_reqs,
        sufficient_count=sufficient_cnt,
        partial_count=partial_cnt,
        insufficient_count=insufficient_cnt,
        no_evidence_count=no_ev_cnt,
        conflicting_count=conflicting_cnt,
        total_gaps=total_gaps,
        high_priority_gaps=high_gaps,
        medium_priority_gaps=med_gaps,
        low_priority_gaps=low_gaps,
        overall_coverage_ratio=coverage_ratio,
        coverage_explanation=coverage_expl,
    )

    return SufficiencyResponse(
        investigation_id=investigation_id,
        contract_id=contract_id,
        decision_objective=decision_objective,
        assessments=assessments,
        summary=summary_obj,
        processing_mode=processing_mode,
        last_analyzed_at=last_analyzed_at,
    )


async def analyze_investigation_sufficiency(conn, investigation_id: str) -> SufficiencyResponse:
    """
    Orchestrates the Evidence Sufficiency & Gap Analysis pipeline:
    1. Pre-analysis & evidence bundling per requirement.
    2. Conflict-aware checks (integrates Component 05).
    3. Gemini LLM structured reasoning with multi-model fallback.
    4. Deterministic fallback if Gemini is unavailable or fails.
    5. Persistence in SQLite (evidence_sufficiency_assessments, evidence_gaps, evidence_sufficiency_runs).
    6. Returns the complete updated SufficiencyResponse.
    """
    cursor = conn.cursor()

    # Verify investigation exists
    cursor.execute("SELECT id, research_question FROM investigations WHERE id = ?;", (investigation_id,))
    inv = cursor.fetchone()
    if not inv:
        raise ValueError(f"Investigation '{investigation_id}' not found")

    # Fetch Decision Contract
    cursor.execute("SELECT id, decision_objective FROM decision_contracts WHERE investigation_id = ?;", (investigation_id,))
    c_row = cursor.fetchone()
    if not c_row:
        raise ValueError(f"Decision Contract not found for investigation '{investigation_id}'. Compile a contract in Component 03 first.")

    contract_id = c_row["id"]
    decision_objective = c_row["decision_objective"]

    # Fetch Requirements
    cursor.execute("""
        SELECT id, title, description, requirement_type, priority, verification_criteria, sort_order
        FROM contract_requirements
        WHERE contract_id = ?
        ORDER BY sort_order ASC;
    """, (contract_id,))
    requirements = [dict(r) for r in cursor.fetchall()]

    if not requirements:
        raise ValueError(f"No requirements found in Decision Contract '{contract_id}'.")

    # Fetch all Claims for this investigation
    claims_query = """
        SELECT
            c.id, c.claim_text, c.category, c.extraction_confidence,
            s.id AS source_id, s.title AS source_title, s.source_type, s.original_url,
            p.id AS passage_id, p.passage_text, p.page_number, p.sha256_hash
        FROM claims c
        LEFT JOIN sources s ON c.source_id = s.id
        LEFT JOIN passages p ON c.passage_id = p.id
        WHERE c.investigation_id = ?;
    """
    cursor.execute(claims_query, (investigation_id,))
    all_claims = [dict(r) for r in cursor.fetchall()]

    # Fetch existing graph relationships
    cursor.execute("""
        SELECT requirement_id, claim_id, relevance, explanation
        FROM evidence_relationships
        WHERE investigation_id = ?;
    """, (investigation_id,))
    existing_rels = [dict(r) for r in cursor.fetchall()]

    # Map claims to requirements
    req_claim_map: Dict[str, List[Dict[str, Any]]] = {}
    rel_lookup = {(r["requirement_id"], r["claim_id"]): r for r in existing_rels}

    for req in requirements:
        rid = req["id"]
        linked = []
        for clm in all_claims:
            cid = clm["id"]
            rel_entry = rel_lookup.get((rid, cid))
            if rel_entry and rel_entry["relevance"] in {"DIRECTLY_RELEVANT", "PARTIALLY_RELEVANT", "CONTEXTUAL"}:
                c_copy = dict(clm)
                c_copy["relevance"] = rel_entry["relevance"]
                c_copy["relevance_explanation"] = rel_entry.get("explanation", "")
                linked.append(c_copy)
            elif not existing_rels:
                # If relationships uncomputed, evaluate deterministic keyword relevance
                rel_eval = evaluate_deterministic_relevance(
                    f"{req['title']} {req['description']} {req['verification_criteria']}",
                    clm["claim_text"]
                )
                if rel_eval in {"DIRECTLY_RELEVANT", "PARTIALLY_RELEVANT"}:
                    c_copy = dict(clm)
                    c_copy["relevance"] = rel_eval
                    c_copy["relevance_explanation"] = "Identified via deterministic keyword overlap."
                    linked.append(c_copy)

        req_claim_map[rid] = linked

    # Fetch existing Conflicts from Component 05
    cursor.execute("""
        SELECT
            ec.id AS conflict_id, ec.claim_a_id, ec.claim_b_id, ec.conflict_type,
            ec.severity, ec.explanation, ec.resolution_status,
            ca.claim_text AS claim_a_text, cb.claim_text AS claim_b_text
        FROM evidence_conflicts ec
        LEFT JOIN claims ca ON ec.claim_a_id = ca.id
        LEFT JOIN claims cb ON ec.claim_b_id = cb.id
        WHERE ec.investigation_id = ?;
    """, (investigation_id,))
    all_conflicts = [dict(r) for r in cursor.fetchall()]

    # Associate conflicts per requirement
    req_conflict_map: Dict[str, List[RelatedConflictInfo]] = {}
    for req in requirements:
        rid = req["id"]
        claim_ids = {c["id"] for c in req_claim_map.get(rid, [])}
        conf_list = []
        for conf in all_conflicts:
            if conf["claim_a_id"] in claim_ids or conf["claim_b_id"] in claim_ids:
                opp_text = conf["claim_b_text"] if conf["claim_a_id"] in claim_ids else conf["claim_a_text"]
                is_unres = (conf["resolution_status"] != "resolved")
                conf_list.append(RelatedConflictInfo(
                    conflict_id=conf["conflict_id"],
                    claim_a_id=conf["claim_a_id"],
                    claim_b_id=conf["claim_b_id"],
                    opposing_claim_text=opp_text or "",
                    conflict_type=conf["conflict_type"],
                    severity=conf["severity"],
                    explanation=conf["explanation"],
                    resolution_status=conf["resolution_status"],
                    is_unresolved=is_unres,
                ))
        req_conflict_map[rid] = conf_list

    # Execution State
    evaluations: List[Dict[str, Any]] = []
    gemini_completed = False
    processing_mode = "fallback"
    analysis_method = "deterministic_rule_engine"

    # Attempt Gemini LLM Analysis
    if GEMINI_API_KEY:
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=GEMINI_API_KEY)

            # Build compact prompt representing each requirement and its evidence bundle
            prompt_bundle = []
            for req in requirements:
                rid = req["id"]
                linked = req_claim_map.get(rid, [])
                confs = req_conflict_map.get(rid, [])
                unresolved_cnt = sum(1 for c in confs if c.is_unresolved)

                prompt_bundle.append({
                    "requirement_id": rid,
                    "title": req["title"],
                    "description": req["description"],
                    "priority": req["priority"],
                    "verification_criteria": req["verification_criteria"],
                    "unresolved_conflicts_count": unresolved_cnt,
                    "conflicts": [
                        {
                            "conflict_id": c.conflict_id,
                            "type": c.conflict_type,
                            "severity": c.severity,
                            "explanation": c.explanation,
                            "status": c.resolution_status
                        }
                        for c in confs
                    ],
                    "evidence_claims": [
                        {
                            "claim_id": c["id"],
                            "claim_text": c["claim_text"],
                            "relevance": c.get("relevance", "PARTIALLY_RELEVANT"),
                            "source": c.get("source_title", "Unknown Source"),
                            "excerpt": (c.get("passage_text") or "")[:250],
                        }
                        for c in linked
                    ]
                })

            prompt = (
                "You are an elite forensic evidence-intelligence auditor evaluating Evidence Sufficiency & Gap Analysis.\n\n"
                f"DECISION OBJECTIVE:\n\"{decision_objective}\"\n\n"
                "INSTRUCTIONS:\n"
                "1. For each requirement, evaluate whether the available evidence adequately substantiates it.\n"
                "2. ASSIGN ONE COVERAGE STATUS:\n"
                "   - SUFFICIENT: Evidence is directly relevant, corroborated, credible, and free of material unresolved conflicts.\n"
                "   - PARTIAL: Evidence exists but is single-source, incomplete, or leaves important aspects unaddressed.\n"
                "   - INSUFFICIENT: Evidence exists but is tangential, weak, or fails to meet the verification criteria.\n"
                "   - NO_EVIDENCE: Zero meaningful claims or passages support this requirement.\n"
                "   - CONFLICTING: Unresolved factual or numerical conflicts directly compromise the supporting evidence.\n"
                "3. MANDATORY HONESTY RULES:\n"
                "   - If 'evidence_claims' is empty, you MUST return 'NO_EVIDENCE'. Do NOT invent evidence.\n"
                "   - If 'unresolved_conflicts_count' > 0, you MUST return 'CONFLICTING' or explain why the conflict does not undermine sufficiency.\n"
                "   - Do NOT classify as SUFFICIENT solely because claims exist.\n"
                "4. FOR EACH REQUIREMENT PROVIDE:\n"
                "   - coverage_status (SUFFICIENT, PARTIAL, INSUFFICIENT, NO_EVIDENCE, CONFLICTING)\n"
                "   - assessment_summary (Concise forensic evaluation)\n"
                "   - limitations (Weaknesses, biases, single-source dependency)\n"
                "   - missing_information (Key unanswered questions or data gaps)\n"
                "   - recommended_action (Next empirical steps to substantiate)\n"
                "   - confidence (0.0 to 1.0)\n"
                "   - gaps: Array of 1-3 concrete evidence gaps, each with: gap_description, why_it_matters, evidence_needed, suggested_source_type, priority (HIGH, MEDIUM, LOW)\n\n"
                f"REQUIREMENTS AND EVIDENCE BUNDLE:\n{json.dumps(prompt_bundle, separators=(',', ':'))}\n\n"
                "Return ONLY a valid JSON object matching:\n"
                "{\n"
                "  \"assessments\": [\n"
                "    {\n"
                "      \"requirement_id\": \"...\",\n"
                "      \"coverage_status\": \"PARTIAL\",\n"
                "      \"assessment_summary\": \"...\",\n"
                "      \"limitations\": \"...\",\n"
                "      \"missing_information\": \"...\",\n"
                "      \"recommended_action\": \"...\",\n"
                "      \"confidence\": 0.85,\n"
                "      \"gaps\": [\n"
                "        {\n"
                "          \"gap_description\": \"...\",\n"
                "          \"why_it_matters\": \"...\",\n"
                "          \"evidence_needed\": \"...\",\n"
                "          \"suggested_source_type\": \"...\",\n"
                "          \"priority\": \"HIGH\"\n"
                "        }\n"
                "      ]\n"
                "    }\n"
                "  ]\n"
                "}"
            )

            candidate_models = [GEMINI_MODEL]
            for fb_m in ["gemini-flash-lite-latest", "gemini-3.5-flash-lite", "gemini-3-flash-preview"]:
                if fb_m not in candidate_models:
                    candidate_models.append(fb_m)

            response = None
            used_model = None

            for model_cand in candidate_models:
                try:
                    res = client.models.generate_content(
                        model=model_cand,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            temperature=0.1,
                            max_output_tokens=6000,
                        )
                    )
                    if res and res.text:
                        response = res
                        used_model = model_cand
                        break
                except Exception as m_err:
                    err_str = str(m_err)
                    logger.warning("Gemini model '%s' failed for sufficiency: %s. Trying next candidate.", model_cand, err_str)
                    if "RESOURCE_EXHAUSTED" in err_str or "429" in err_str:
                        logger.info("Quota exhausted or rate limit hit. Immediately using deterministic sufficiency fallback.")
                        break

            if response and response.text:
                raw_json = json.loads(response.text)
                items = raw_json.get("assessments", []) if isinstance(raw_json, dict) else (raw_json if isinstance(raw_json, list) else [])
                gemini_map = {}
                for it in items:
                    if isinstance(it, dict) and "requirement_id" in it:
                        gemini_map[it["requirement_id"]] = it

                req_id_set = {r["id"] for r in requirements}
                parsed_evals = []

                for req in requirements:
                    rid = req["id"]
                    linked_c = req_claim_map.get(rid, [])
                    confs = req_conflict_map.get(rid, [])
                    unresolved_cnt = sum(1 for c in confs if c.is_unresolved)

                    if rid in gemini_map:
                        g_item = gemini_map[rid]
                        cov_st = (g_item.get("coverage_status") or "INSUFFICIENT").upper().strip()
                        valid_statuses = {"SUFFICIENT", "PARTIAL", "INSUFFICIENT", "NO_EVIDENCE", "CONFLICTING"}
                        if cov_st not in valid_statuses:
                            cov_st = "INSUFFICIENT"

                        # Enforce honesty invariants
                        if not linked_c:
                            cov_st = "NO_EVIDENCE"
                        elif unresolved_cnt > 0 and cov_st == "SUFFICIENT":
                            cov_st = "CONFLICTING"

                        try:
                            conf_score = round(float(g_item.get("confidence", 0.85)), 2)
                        except (TypeError, ValueError):
                            conf_score = 0.85

                        # Parse gaps
                        g_gaps = []
                        raw_gaps = g_item.get("gaps", [])
                        if isinstance(raw_gaps, list):
                            for rg in raw_gaps:
                                if isinstance(rg, dict):
                                    g_gaps.append({
                                        "gap_description": rg.get("gap_description") or f"Information gap in {req['title']}",
                                        "why_it_matters": rg.get("why_it_matters") or "Crucial to decision stability.",
                                        "evidence_needed": rg.get("evidence_needed") or "Direct empirical verification.",
                                        "suggested_source_type": rg.get("suggested_source_type") or "Authoritative Audit / Regulatory Filing",
                                        "priority": (rg.get("priority") or "HIGH").upper(),
                                    })

                        parsed_evals.append({
                            "requirement": req,
                            "coverage_status": cov_st,
                            "assessment_summary": g_item.get("assessment_summary") or "Gemini completed sufficiency audit.",
                            "limitations": g_item.get("limitations") or "",
                            "missing_information": g_item.get("missing_information") or "",
                            "recommended_action": g_item.get("recommended_action") or "Obtain independent secondary documentation.",
                            "confidence": conf_score,
                            "gaps": g_gaps,
                        })
                    else:
                        # Fallback for missing requirement in Gemini output
                        st_f, sum_f, lim_f, mis_f, act_f, conf_f, gaps_f = evaluate_deterministic_sufficiency(
                            req, linked_c, confs
                        )
                        parsed_evals.append({
                            "requirement": req,
                            "coverage_status": st_f,
                            "assessment_summary": sum_f,
                            "limitations": lim_f,
                            "missing_information": mis_f,
                            "recommended_action": act_f,
                            "confidence": conf_f,
                            "gaps": gaps_f,
                        })

                if len(parsed_evals) == len(requirements):
                    evaluations = parsed_evals
                    gemini_completed = True
                    processing_mode = "gemini"
                    analysis_method = f"gemini_sufficiency_engine:{used_model}"

        except Exception as e:
            logger.warning("Gemini sufficiency analysis failed: %s. Executing deterministic fallback.", e, exc_info=True)
            gemini_completed = False

    # Execute deterministic fallback if Gemini was skipped or failed
    if not gemini_completed:
        processing_mode = "fallback"
        analysis_method = "deterministic_rule_engine"
        evaluations = []

        for req in requirements:
            rid = req["id"]
            linked_c = req_claim_map.get(rid, [])
            confs = req_conflict_map.get(rid, [])
            st_f, sum_f, lim_f, mis_f, act_f, conf_f, gaps_f = evaluate_deterministic_sufficiency(
                req, linked_c, confs
            )
            evaluations.append({
                "requirement": req,
                "coverage_status": st_f,
                "assessment_summary": sum_f,
                "limitations": lim_f,
                "missing_information": mis_f,
                "recommended_action": act_f,
                "confidence": conf_f,
                "gaps": gaps_f,
            })

    # Persist results in SQLite
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # Clear previous assessments and gaps for this investigation (idempotent overwrite)
    cursor.execute("DELETE FROM evidence_gaps WHERE investigation_id = ?;", (investigation_id,))
    cursor.execute("DELETE FROM evidence_sufficiency_assessments WHERE investigation_id = ?;", (investigation_id,))

    sufficient_cnt = 0
    partial_cnt = 0
    insufficient_cnt = 0
    no_ev_cnt = 0
    conflicting_cnt = 0
    total_gaps_cnt = 0

    for ev in evaluations:
        req = ev["requirement"]
        rid = req["id"]
        asm_id = f"suff_{uuid.uuid4().hex[:12]}"

        st = ev["coverage_status"]
        if st == "SUFFICIENT":
            sufficient_cnt += 1
        elif st == "PARTIAL":
            partial_cnt += 1
        elif st == "INSUFFICIENT":
            insufficient_cnt += 1
        elif st == "NO_EVIDENCE":
            no_ev_cnt += 1
        elif st == "CONFLICTING":
            conflicting_cnt += 1

        cursor.execute("""
            INSERT INTO evidence_sufficiency_assessments (
                id, investigation_id, requirement_id, coverage_status,
                assessment_summary, limitations, missing_information,
                recommended_action, confidence, analysis_method,
                processing_mode, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            asm_id, investigation_id, rid, st,
            ev["assessment_summary"], ev["limitations"], ev["missing_information"],
            ev["recommended_action"], ev["confidence"], analysis_method,
            processing_mode, now, now
        ))

        for g in ev["gaps"]:
            gap_id = f"gap_{uuid.uuid4().hex[:12]}"
            total_gaps_cnt += 1
            cursor.execute("""
                INSERT INTO evidence_gaps (
                    id, investigation_id, requirement_id, assessment_id,
                    gap_description, why_it_matters, evidence_needed,
                    suggested_source_type, priority, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                gap_id, investigation_id, rid, asm_id,
                g["gap_description"], g["why_it_matters"], g["evidence_needed"],
                g.get("suggested_source_type", "Authoritative Audit / Regulatory Filing"),
                g.get("priority", "HIGH"), now
            ))

    # Record Audit Run
    run_id = f"suff_run_{uuid.uuid4().hex[:12]}"
    cursor.execute("""
        INSERT INTO evidence_sufficiency_runs (
            id, investigation_id, processing_mode, analysis_status,
            requirements_count, sufficient_count, partial_count,
            insufficient_count, no_evidence_count, conflicting_count,
            gaps_count, created_at
        ) VALUES (?, ?, ?, 'completed', ?, ?, ?, ?, ?, ?, ?, ?);
    """, (
        run_id, investigation_id, processing_mode, len(requirements),
        sufficient_cnt, partial_cnt, insufficient_cnt, no_ev_cnt,
        conflicting_cnt, total_gaps_cnt, now
    ))

    conn.commit()

    # Return refreshed SufficiencyResponse
    return get_investigation_sufficiency(conn, investigation_id)


def get_requirement_sufficiency_detail(
    conn, investigation_id: str, requirement_id: str
) -> RequirementSufficiencyAssessment:
    """Retrieves full assessment and gaps for a single requirement."""
    full_resp = get_investigation_sufficiency(conn, investigation_id)
    for asm in full_resp.assessments:
        if asm.requirement_id == requirement_id:
            return asm
    raise ValueError(f"Requirement '{requirement_id}' not found in investigation '{investigation_id}'")


def get_sufficiency_status(conn, investigation_id: str) -> SufficiencyStatusResponse:
    """Lightweight summary status for header badges and overview cards."""
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM investigations WHERE id = ?;", (investigation_id,))
    if not cursor.fetchone():
        raise ValueError(f"Investigation '{investigation_id}' not found")

    cursor.execute("""
        SELECT
            COUNT(*),
            SUM(CASE WHEN coverage_status = 'SUFFICIENT' THEN 1 ELSE 0 END),
            SUM(CASE WHEN coverage_status = 'PARTIAL' THEN 1 ELSE 0 END),
            SUM(CASE WHEN coverage_status = 'INSUFFICIENT' THEN 1 ELSE 0 END),
            SUM(CASE WHEN coverage_status = 'NO_EVIDENCE' THEN 1 ELSE 0 END),
            SUM(CASE WHEN coverage_status = 'CONFLICTING' THEN 1 ELSE 0 END)
        FROM evidence_sufficiency_assessments
        WHERE investigation_id = ?;
    """, (investigation_id,))
    stats = cursor.fetchone()

    total_reqs = stats[0] or 0
    suff_cnt = stats[1] or 0
    part_cnt = stats[2] or 0
    insuff_cnt = stats[3] or 0
    no_ev_cnt = stats[4] or 0
    conf_cnt = stats[5] or 0

    cursor.execute("SELECT COUNT(*) FROM evidence_gaps WHERE investigation_id = ?;", (investigation_id,))
    gaps_cnt = cursor.fetchone()[0] or 0

    cursor.execute("""
        SELECT processing_mode, analysis_status, created_at
        FROM evidence_sufficiency_runs
        WHERE investigation_id = ?
        ORDER BY created_at DESC LIMIT 1;
    """, (investigation_id,))
    run_row = cursor.fetchone()

    processing_mode = run_row["processing_mode"] if run_row else "pending"
    last_status = run_row["analysis_status"] if run_row else "none"
    last_analyzed = run_row["created_at"] if run_row else None

    return SufficiencyStatusResponse(
        investigation_id=investigation_id,
        total_requirements=total_reqs,
        sufficient_count=suff_cnt,
        partial_count=part_cnt,
        insufficient_count=insuff_cnt,
        no_evidence_count=no_ev_cnt,
        conflicting_count=conf_cnt,
        total_gaps=gaps_cnt,
        processing_mode=processing_mode,
        last_analysis_status=last_status,
        last_analyzed_at=last_analyzed,
    )
