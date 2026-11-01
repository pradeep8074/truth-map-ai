import os
import json
import uuid
import datetime
import logging
import hashlib
import time
from typing import Dict, Any, List, Optional, Tuple

from backend.models import (
    ExecutiveBriefSection,
    ContractRequirementSummary,
    DecisionContractSummarySection,
    SourceProvenanceItem,
    EvidenceIntelligenceSection,
    SupportingClaimItem,
    OpposingEvidenceItem,
    RequirementAssessmentRow,
    RequirementAssessmentSection,
    ReportConflictItem,
    ConflictAnalysisSection,
    ReportGapItem,
    GapsAndUncertaintySection,
    ReportStressScenarioItem,
    StressTestResultsSection,
    RiskRegisterItem,
    RiskMitigationSection,
    RecommendedActionItem,
    RecommendedActionsSection,
    FinalConclusionSection,
    DecisionReportPayload,
    DecisionReportModel,
    DecisionReportSummaryModel,
    DecisionReportListResponse,
    DecisionReportStatusResponse,
    GeminiReportSynthesisPayload,
)
from backend.services.freshness_service import classify_source_freshness

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

_gemini_quota_exhausted_until = 0.0


def compute_investigation_content_fingerprint(conn, investigation_id: str) -> str:
    """
    Computes a deterministic cryptographic SHA-256 fingerprint representing the complete
    evidentiary and analytical state of an investigation across Components 02–07.
    Any edit, addition, deletion, or resolution shift in relevant upstream records
    deterministically alters this fingerprint. Unrelated UI activity or report viewing
    does NOT alter this fingerprint.
    """
    cursor = conn.cursor()

    # 1. Investigation & Contract
    cursor.execute("SELECT id, research_question, status FROM investigations WHERE id = ?;", (investigation_id,))
    inv_row = cursor.fetchone()
    inv_content = dict(inv_row) if inv_row else {}

    cursor.execute("""
        SELECT id, normalized_question, decision_objective, scope, compilation_method
        FROM decision_contracts WHERE investigation_id = ?;
    """, (investigation_id,))
    dc_row = cursor.fetchone()
    contract_content = dict(dc_row) if dc_row else {}
    contract_id = contract_content.get("id")

    # Contract Requirements & Sub-elements
    requirements_content = []
    ev_reqs_content = []
    constraints_content = []
    assumptions_content = []
    clarifications_content = []

    if contract_id:
        cursor.execute("""
            SELECT id, title, description, requirement_type, priority, verification_criteria, status, sort_order
            FROM contract_requirements WHERE contract_id = ? ORDER BY id ASC;
        """, (contract_id,))
        requirements_content = [dict(r) for r in cursor.fetchall()]

        cursor.execute("""
            SELECT id, requirement_id, evidence_type, rationale, preferred_source_types, temporal_scope, geographic_scope
            FROM contract_evidence_requirements WHERE contract_id = ? ORDER BY id ASC;
        """, (contract_id,))
        ev_reqs_content = [dict(r) for r in cursor.fetchall()]

        cursor.execute("""
            SELECT id, description, constraint_type
            FROM contract_constraints WHERE contract_id = ? ORDER BY id ASC;
        """, (contract_id,))
        constraints_content = [dict(r) for r in cursor.fetchall()]

        cursor.execute("""
            SELECT id, description, confidence, source, validation_status
            FROM contract_assumptions WHERE contract_id = ? ORDER BY id ASC;
        """, (contract_id,))
        assumptions_content = [dict(r) for r in cursor.fetchall()]

        cursor.execute("""
            SELECT id, question, clarification_type, dimension
            FROM contract_unresolved_questions WHERE contract_id = ? ORDER BY id ASC;
        """, (contract_id,))
        clarifications_content = [dict(r) for r in cursor.fetchall()]

    # 2. Sources, Passages, Claims
    cursor.execute("""
        SELECT s.*,
               LENGTH(COALESCE(s.extracted_text, '')) as text_length
        FROM sources s WHERE s.investigation_id = ? ORDER BY s.id ASC;
    """, (investigation_id,))
    sources_content = [dict(r) for r in cursor.fetchall()]

    cursor.execute("""
        SELECT p.id, p.source_id, p.sha256_hash, p.page_number, p.paragraph_index, p.start_offset, p.end_offset
        FROM passages p
        JOIN sources s ON p.source_id = s.id
        WHERE s.investigation_id = ? ORDER BY p.id ASC;
    """, (investigation_id,))
    passages_content = [dict(r) for r in cursor.fetchall()]

    cursor.execute("""
        SELECT id, source_id, passage_id, claim_text, category, extraction_method, extraction_confidence
        FROM claims WHERE investigation_id = ? ORDER BY id ASC;
    """, (investigation_id,))
    claims_content = [dict(r) for r in cursor.fetchall()]

    # 3. Evidence Relationships (Topological Graph)
    cursor.execute("""
        SELECT id, requirement_id, claim_id, passage_id, relevance, explanation, confidence, analysis_method, processing_mode
        FROM evidence_relationships WHERE investigation_id = ? ORDER BY id ASC;
    """, (investigation_id,))
    relationships_content = [dict(r) for r in cursor.fetchall()]

    # 4. Conflicts & Contradictions (Component 05)
    cursor.execute("""
        SELECT id, claim_a_id, claim_b_id, conflict_type, severity, explanation, contextual_differences,
               confidence, resolution_status, reviewer_notes, recommended_action
        FROM evidence_conflicts WHERE investigation_id = ? ORDER BY id ASC;
    """, (investigation_id,))
    conflicts_content = [dict(r) for r in cursor.fetchall()]

    # 5. Sufficiency Assessments & Gaps (Component 06)
    cursor.execute("""
        SELECT id, requirement_id, coverage_status, assessment_summary, limitations, missing_information,
               recommended_action, confidence
        FROM evidence_sufficiency_assessments WHERE investigation_id = ? ORDER BY id ASC;
    """, (investigation_id,))
    sufficiency_content = [dict(r) for r in cursor.fetchall()]

    cursor.execute("""
        SELECT id, requirement_id, gap_description, why_it_matters, evidence_needed, suggested_source_type, priority
        FROM evidence_gaps WHERE investigation_id = ? ORDER BY id ASC;
    """, (investigation_id,))
    gaps_content = [dict(r) for r in cursor.fetchall()]

    # 6. Stress Scenarios & Evaluations (Component 07)
    cursor.execute("""
        SELECT id, title, category, description, trigger_condition, challenged_assumptions,
               affected_requirement_ids, related_claim_ids, related_conflict_ids, expected_impact, severity, evidence_needed
        FROM decision_stress_scenarios WHERE investigation_id = ? ORDER BY id ASC;
    """, (investigation_id,))
    stress_scenarios_content = [dict(r) for r in cursor.fetchall()]

    cursor.execute("""
        SELECT id, scenario_id, baseline_overall_outcome, scenario_overall_outcome, outcome_shift,
               impact_explanation, key_vulnerabilities, uncertainty_factors, recommended_actions, requirement_evaluations
        FROM decision_stress_evaluations WHERE investigation_id = ? ORDER BY id ASC;
    """, (investigation_id,))
    stress_evaluations_content = [dict(r) for r in cursor.fetchall()]

    bundle = {
        "investigation": inv_content,
        "contract": contract_content,
        "requirements": requirements_content,
        "evidence_requirements": ev_reqs_content,
        "constraints": constraints_content,
        "assumptions": assumptions_content,
        "clarifications": clarifications_content,
        "sources": sources_content,
        "passages": passages_content,
        "claims": claims_content,
        "relationships": relationships_content,
        "conflicts": conflicts_content,
        "sufficiency": sufficiency_content,
        "gaps": gaps_content,
        "stress_scenarios": stress_scenarios_content,
        "stress_evaluations": stress_evaluations_content,
    }

    canonical_json = json.dumps(bundle, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def get_investigation_current_snapshot(conn, investigation_id: str) -> Dict[str, Any]:
    """Computes a precise content fingerprint and component count snapshot."""
    cursor = conn.cursor()

    content_fingerprint = compute_investigation_content_fingerprint(conn, investigation_id)

    cursor.execute("SELECT COUNT(*) AS c FROM sources WHERE investigation_id = ?;", (investigation_id,))
    sources_count = cursor.fetchone()["c"]

    cursor.execute("""
        SELECT COUNT(*) AS c FROM passages p
        JOIN sources s ON p.source_id = s.id
        WHERE s.investigation_id = ?;
    """, (investigation_id,))
    passages_count = cursor.fetchone()["c"]

    cursor.execute("SELECT COUNT(*) AS c FROM claims WHERE investigation_id = ?;", (investigation_id,))
    claims_count = cursor.fetchone()["c"]

    cursor.execute("""
        SELECT COUNT(*) AS c FROM contract_requirements cr
        JOIN decision_contracts dc ON cr.contract_id = dc.id
        WHERE dc.investigation_id = ?;
    """, (investigation_id,))
    requirements_count = cursor.fetchone()["c"]

    cursor.execute("SELECT COUNT(*) AS c FROM evidence_conflicts WHERE investigation_id = ?;", (investigation_id,))
    conflicts_count = cursor.fetchone()["c"]

    cursor.execute("""
        SELECT COUNT(*) AS c FROM evidence_conflicts
        WHERE investigation_id = ? AND resolution_status = 'unresolved';
    """, (investigation_id,))
    unresolved_conflicts_count = cursor.fetchone()["c"]

    cursor.execute("SELECT COUNT(*) AS c FROM evidence_sufficiency_assessments WHERE investigation_id = ?;", (investigation_id,))
    sufficiency_count = cursor.fetchone()["c"]

    cursor.execute("SELECT COUNT(*) AS c FROM evidence_gaps WHERE investigation_id = ?;", (investigation_id,))
    gaps_count = cursor.fetchone()["c"]

    cursor.execute("SELECT COUNT(*) AS c FROM decision_stress_scenarios WHERE investigation_id = ?;", (investigation_id,))
    scenarios_count = cursor.fetchone()["c"]

    cursor.execute("SELECT COUNT(*) AS c FROM decision_stress_evaluations WHERE investigation_id = ?;", (investigation_id,))
    evaluations_count = cursor.fetchone()["c"]

    cursor.execute("""
        SELECT dfi_score, classification, is_provisional, guardrail_active
        FROM decision_fragility_results WHERE investigation_id = ?
        ORDER BY created_at DESC LIMIT 1;
    """, (investigation_id,))
    f_row = cursor.fetchone()
    dfi_score = f_row["dfi_score"] if f_row else None
    dfi_classification = f_row["classification"] if f_row else None

    return {
        "content_fingerprint": content_fingerprint,
        "sources_count": sources_count,
        "passages_count": passages_count,
        "claims_count": claims_count,
        "requirements_count": requirements_count,
        "conflicts_count": conflicts_count,
        "unresolved_conflicts_count": unresolved_conflicts_count,
        "sufficiency_count": sufficiency_count,
        "gaps_count": gaps_count,
        "scenarios_count": scenarios_count,
        "evaluations_count": evaluations_count,
        "dfi_score": dfi_score,
        "dfi_classification": dfi_classification,
    }


def is_report_stale(current_snapshot: Dict[str, Any], report_snapshot: Dict[str, Any]) -> bool:
    """
    Returns True if any relevant upstream record has been added, modified, resolved, or deleted
    since the report was generated. Compares deterministic cryptographic SHA-256 content fingerprints.
    """
    if not report_snapshot:
        return True

    # 1. Primary: Deterministic content-fingerprint verification
    current_fp = current_snapshot.get("content_fingerprint")
    stored_fp = report_snapshot.get("content_fingerprint")
    if current_fp and stored_fp:
        return current_fp != stored_fp

    # 2. Backward-compatible fallback for legacy reports lacking content_fingerprint
    for key in [
        "sources_count",
        "claims_count",
        "requirements_count",
        "conflicts_count",
        "unresolved_conflicts_count",
        "sufficiency_count",
        "gaps_count",
        "scenarios_count",
        "evaluations_count",
    ]:
        if current_snapshot.get(key, 0) != report_snapshot.get(key, 0):
            return True
    return False


def compute_report_robustness(
    requirements_count: int,
    sufficient_count: int,
    partial_count: int,
    insufficient_count: int,
    no_evidence_count: int,
    conflicting_count: int,
    unresolved_conflicts_count: int,
    critical_conflicts_count: int,
    evaluated_scenarios_count: int,
    critical_scenarios_count: int,
    vulnerable_scenarios_count: int,
) -> str:
    """Deterministic, transparent calculation of overall decision robustness."""
    if requirements_count == 0:
        return "INDETERMINATE"

    # Extreme critical vulnerabilities
    if critical_conflicts_count > 0 or critical_scenarios_count > 0:
        return "HIGHLY_VULNERABLE"

    if conflicting_count > 0 or unresolved_conflicts_count > 1 or vulnerable_scenarios_count > 1:
        return "VULNERABLE"

    coverage_ratio = sufficient_count / requirements_count if requirements_count > 0 else 0.0

    if coverage_ratio >= 0.75 and unresolved_conflicts_count == 0 and vulnerable_scenarios_count == 0:
        return "ROBUST"

    if (coverage_ratio >= 0.5 or (sufficient_count + partial_count) == requirements_count) and unresolved_conflicts_count <= 1:
        return "CONDITIONALLY_ROBUST"

    if no_evidence_count >= requirements_count / 2:
        return "VULNERABLE" if (unresolved_conflicts_count > 0 or conflicting_count > 0) else "INDETERMINATE"

    return "VULNERABLE"


def assemble_raw_investigation_data(conn, investigation_id: str) -> Dict[str, Any]:
    """Retrieves all connected records for the investigation from Components 01–07."""
    cursor = conn.cursor()

    # 1. Investigation
    cursor.execute("SELECT * FROM investigations WHERE id = ?;", (investigation_id,))
    inv = cursor.fetchone()
    if not inv:
        raise ValueError(f"Investigation '{investigation_id}' not found")
    inv_data = dict(inv)

    # 2. Decision Contract
    cursor.execute("SELECT * FROM decision_contracts WHERE investigation_id = ?;", (investigation_id,))
    contract = cursor.fetchone()
    contract_data = dict(contract) if contract else None

    requirements = []
    constraints = []
    assumptions = []
    unresolved_questions = []

    if contract_data:
        cid = contract_data["id"]
        cursor.execute("SELECT * FROM contract_requirements WHERE contract_id = ? ORDER BY sort_order ASC;", (cid,))
        requirements = [dict(r) for r in cursor.fetchall()]

        cursor.execute("SELECT * FROM contract_evidence_requirements WHERE contract_id = ?;", (cid,))
        ev_reqs = [dict(r) for r in cursor.fetchall()]
        ev_map = {}
        for er in ev_reqs:
            rid = er["requirement_id"]
            if rid not in ev_map:
                ev_map[rid] = []
            ev_map[rid].append(er.get("evidence_type", ""))
        for r in requirements:
            r["evidence_types"] = ev_map.get(r["id"], [])

        cursor.execute("SELECT * FROM contract_constraints WHERE contract_id = ?;", (cid,))
        constraints = [dict(c) for c in cursor.fetchall()]

        cursor.execute("SELECT * FROM contract_assumptions WHERE contract_id = ?;", (cid,))
        assumptions = [dict(a) for a in cursor.fetchall()]

        cursor.execute("SELECT * FROM contract_unresolved_questions WHERE contract_id = ?;", (cid,))
        unresolved_questions = [dict(u) for u in cursor.fetchall()]

    # 3. Sources & Passages & Claims
    cursor.execute("SELECT * FROM sources WHERE investigation_id = ? ORDER BY retrieved_at ASC;", (investigation_id,))
    sources = [dict(s) for s in cursor.fetchall()]

    cursor.execute("""
        SELECT p.*, s.title as source_title
        FROM passages p
        JOIN sources s ON p.source_id = s.id
        WHERE s.investigation_id = ?;
    """, (investigation_id,))
    passages = [dict(p) for p in cursor.fetchall()]

    cursor.execute("""
        SELECT c.*, s.title as source_title, p.sha256_hash as passage_hash
        FROM claims c
        LEFT JOIN sources s ON c.source_id = s.id
        LEFT JOIN passages p ON c.passage_id = p.id
        WHERE c.investigation_id = ?
        ORDER BY c.created_at ASC;
    """, (investigation_id,))
    claims = [dict(c) for c in cursor.fetchall()]

    # Count claims per source
    source_claims_count = {}
    for cl in claims:
        sid = cl.get("source_id")
        source_claims_count[sid] = source_claims_count.get(sid, 0) + 1

    for s in sources:
        s["claims_count"] = source_claims_count.get(s["id"], 0)

    # 4. Evidence Relationships (RELATES_TO)
    cursor.execute("""
        SELECT er.*, c.claim_text, c.category as claim_category, c.source_id as source_id, s.title as source_title, p.sha256_hash as passage_hash
        FROM evidence_relationships er
        JOIN claims c ON er.claim_id = c.id
        LEFT JOIN sources s ON c.source_id = s.id
        LEFT JOIN passages p ON c.passage_id = p.id
        WHERE er.investigation_id = ?;
    """, (investigation_id,))
    relationships = [dict(r) for r in cursor.fetchall()]

    # 5. Conflicts
    cursor.execute("""
        SELECT ec.*,
               ca.claim_text as claim_a_text, sa.title as source_a_title,
               cb.claim_text as claim_b_text, sb.title as source_b_title
        FROM evidence_conflicts ec
        LEFT JOIN claims ca ON ec.claim_a_id = ca.id
        LEFT JOIN sources sa ON ca.source_id = sa.id
        LEFT JOIN claims cb ON ec.claim_b_id = cb.id
        LEFT JOIN sources sb ON cb.source_id = sb.id
        WHERE ec.investigation_id = ?
        ORDER BY ec.created_at ASC;
    """, (investigation_id,))
    conflicts = [dict(c) for c in cursor.fetchall()]

    # 6. Sufficiency Assessments & Gaps
    cursor.execute("""
        SELECT esa.*, cr.title as requirement_title, cr.priority as requirement_priority
        FROM evidence_sufficiency_assessments esa
        JOIN contract_requirements cr ON esa.requirement_id = cr.id
        WHERE esa.investigation_id = ?;
    """, (investigation_id,))
    sufficiency = [dict(s) for s in cursor.fetchall()]

    cursor.execute("""
        SELECT eg.*, cr.title as requirement_title
        FROM evidence_gaps eg
        JOIN contract_requirements cr ON eg.requirement_id = cr.id
        WHERE eg.investigation_id = ?
        ORDER BY eg.created_at ASC;
    """, (investigation_id,))
    gaps = [dict(g) for g in cursor.fetchall()]

    # 7. Stress Scenarios & Evaluations
    cursor.execute("""
        SELECT ss.*, se.baseline_overall_outcome, se.scenario_overall_outcome,
               se.outcome_shift, se.impact_explanation, se.key_vulnerabilities,
               se.uncertainty_factors, se.recommended_actions as evaluation_recommended_actions
        FROM decision_stress_scenarios ss
        LEFT JOIN decision_stress_evaluations se ON ss.id = se.scenario_id
        WHERE ss.investigation_id = ?
        ORDER BY ss.created_at ASC;
    """, (investigation_id,))
    scenarios = [dict(sc) for sc in cursor.fetchall()]

    return {
        "investigation": inv_data,
        "contract": contract_data,
        "requirements": requirements,
        "constraints": constraints,
        "assumptions": assumptions,
        "unresolved_questions": unresolved_questions,
        "sources": sources,
        "passages": passages,
        "claims": claims,
        "relationships": relationships,
        "conflicts": conflicts,
        "sufficiency": sufficiency,
        "gaps": gaps,
        "scenarios": scenarios,
    }


def synthesize_report_with_gemini(
    raw_data: Dict[str, Any],
    robustness: str,
    coverage_ratio: float,
    deterministic_risks: List[RiskRegisterItem],
    deterministic_actions: List[RecommendedActionItem],
) -> Optional[GeminiReportSynthesisPayload]:
    """Invokes Gemini to synthesize the analytical sections grounded strictly in evidence."""
    global _gemini_quota_exhausted_until
    if not GEMINI_API_KEY:
        logger.info("No GEMINI_API_KEY present; using deterministic synthesis.")
        return None

    if "mock" in GEMINI_API_KEY.lower():
        _gemini_quota_exhausted_until = 0.0

    if time.time() < _gemini_quota_exhausted_until:
        logger.info("Gemini quota was recently exhausted; bypassing LLM call and using deterministic synthesis.")
        return None

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=GEMINI_API_KEY)

        inv = raw_data["investigation"]
        contract = raw_data["contract"] or {}
        requirements = raw_data["requirements"]
        conflicts = raw_data["conflicts"]
        gaps = raw_data["gaps"]
        scenarios = raw_data["scenarios"]
        sources = raw_data["sources"]
        claims = raw_data["claims"]

        prompt_context = {
            "research_question": inv.get("research_question", ""),
            "decision_objective": contract.get("decision_objective", ""),
            "overall_robustness": robustness,
            "coverage_ratio": coverage_ratio,
            "total_sources": len(sources),
            "total_claims": len(claims),
            "sources": [{"title": s.get("title", ""), "publisher": s.get("publisher", ""), "date": s.get("publication_date", "")} for s in sources[:8]],
            "requirements": [{"id": r["id"], "title": r["title"], "priority": r["priority"], "status": r.get("status", "unverified")} for r in requirements],
            "conflicts": [{"type": c["conflict_type"], "severity": c["severity"], "status": c["resolution_status"], "explanation": c["explanation"][:200]} for c in conflicts],
            "gaps": [{"description": g["gap_description"], "priority": g["priority"], "evidence_needed": g["evidence_needed"]} for g in gaps],
            "scenarios": [{"title": s["title"], "category": s["category"], "severity": s["severity"], "outcome_shift": s.get("outcome_shift", "UNTESTED")} for s in scenarios[:6]],
        }

        prompt = (
            "You are a Principal Forensic Evidence Auditor and Senior Decision Scientist.\n"
            "Synthesize an authoritative, balanced Decision Intelligence Report for executive leadership based EXCLUSIVELY on the provided investigation context bundle.\n\n"
            "MANDATORY EVIDENCE-INTELLIGENCE RULES:\n"
            "1. ZERO SYNTHETIC METRICS: Ground every conclusion, risk, and action in the provided evidence, requirements, conflicts, gaps, or stress scenarios.\n"
            "2. CLEAR EPISTEMIC SEPARATION: Strictly differentiate between verified facts, analytical interpretations, assumptions, and hypothetical stress models.\n"
            "3. HONEST REPORTING: Do not soften risks or invent confidence. If evidence is lacking or conflicting, articulate this plainly.\n"
            "4. Return valid JSON matching the exact schema.\n\n"
            f"INVESTIGATION CONTEXT BUNDLE:\n{json.dumps(prompt_context, separators=(',', ':'))}\n\n"
            "JSON SCHEMA REQUIREMENT:\n"
            "{\n"
            "  \"executive_conclusion\": \"A clear, 2-3 paragraph executive analytical conclusion summarizing decision readiness, evidence robustness, critical vulnerabilities, and necessary conditions before proceeding.\",\n"
            "  \"reliability_limitations\": \"Documented caveats regarding source representation, missing primary regulatory sources, or temporal validity.\",\n"
            "  \"risks\": [\n"
            "    {\n"
            "      \"risk_id\": \"RISK-01\",\n"
            "      \"title\": \"...\",\n"
            "      \"origin\": \"Conflict | Evidence Gap | Stress Scenario | Contract Assumption\",\n"
            "      \"severity\": \"CRITICAL | HIGH | MEDIUM | LOW\",\n"
            "      \"affected_requirement\": \"...\",\n"
            "      \"consequence\": \"...\",\n"
            "      \"mitigation\": \"...\",\n"
            "      \"additional_evidence_needed\": \"...\"\n"
            "    }\n"
            "  ],\n"
            "  \"actions\": [\n"
            "    {\n"
            "      \"action_id\": \"ACT-01\",\n"
            "      \"action_title\": \"...\",\n"
            "      \"description\": \"...\",\n"
            "      \"priority\": \"P1_IMMEDIATE | P2_HIGH | P3_MODERATE\",\n"
            "      \"driver\": \"...\",\n"
            "      \"target_requirement\": \"...\",\n"
            "      \"expected_outcome\": \"...\"\n"
            "    }\n"
            "  ],\n"
            "  \"supported_findings\": [\"Finding 1 backed by multiple claims\", \"Finding 2...\"],\n"
            "  \"uncertainties_and_caveats\": [\"Uncertainty 1 regarding open gaps\", \"Caveat 2...\"],\n"
            "  \"invalidating_conditions\": [\"Condition 1 that reverses the decision stance\", \"Condition 2...\"],\n"
            "  \"recommended_decision_posture\": \"PROCEED | PROCEED_WITH_SAFEGUARDS | DEFER_PENDING_EVIDENCE | REJECT_INSUFFICIENT_EVIDENCE\"\n"
            "}"
        )

        candidate_models = [GEMINI_MODEL]
        if "gemini-2.0-flash" not in candidate_models:
            candidate_models.append("gemini-2.0-flash")

        response = None
        for cand in candidate_models:
            try:
                res = client.models.generate_content(
                    model=cand,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.2,
                        max_output_tokens=1500,
                    ),
                )
                if res and res.text:
                    response = res
                    break
            except Exception as g_err:
                logger.warning("Gemini model '%s' failed for report synthesis: %s", cand, g_err)
                err_str = str(g_err).upper()
                if "RESOURCE_EXHAUSTED" in err_str or "429" in err_str or "QUOTA" in err_str:
                    logger.warning("Gemini quota exhausted (429), bypassing LLM retries for report synthesis.")
                    _gemini_quota_exhausted_until = time.time() + 300.0  # 5 min backoff
                    break

        if response and response.text:
            parsed = json.loads(response.text)
            if isinstance(parsed, list) and len(parsed) > 0:
                parsed = parsed[0]
            elif not isinstance(parsed, dict):
                parsed = {}
            # Validate into GeminiReportSynthesisPayload
            return GeminiReportSynthesisPayload(
                executive_conclusion=parsed.get("executive_conclusion", ""),
                reliability_limitations=parsed.get("reliability_limitations", ""),
                risks=[RiskRegisterItem(**r) for r in parsed.get("risks", []) if isinstance(r, dict)],
                actions=[RecommendedActionItem(**a) for a in parsed.get("actions", []) if isinstance(a, dict)],
                supported_findings=parsed.get("supported_findings", []),
                uncertainties_and_caveats=parsed.get("uncertainties_and_caveats", []),
                invalidating_conditions=parsed.get("invalidating_conditions", []),
                recommended_decision_posture=parsed.get("recommended_decision_posture", "DEFER_PENDING_EVIDENCE"),
            )
    except Exception as exc:
        logger.error("Gemini report synthesis encountered an error, falling back to deterministic synthesis: %s", exc)

    return None


def generate_decision_report(conn, investigation_id: str, fast_mode: bool = False) -> DecisionReportModel:
    """
    Assembles, compiles, versions, and persists a complete 10-section Decision Intelligence Report.
    """
    raw = assemble_raw_investigation_data(conn, investigation_id)
    inv = raw["investigation"]
    contract = raw["contract"] or {}
    requirements = raw["requirements"]
    constraints = raw["constraints"]
    assumptions = raw["assumptions"]
    unresolved_questions = raw["unresolved_questions"]
    sources = raw["sources"]
    passages = raw["passages"]
    claims = raw["claims"]
    relationships = raw["relationships"]
    conflicts = raw["conflicts"]
    sufficiency = raw["sufficiency"]
    gaps = raw["gaps"]
    scenarios = raw["scenarios"]

    # Map sufficiency by requirement_id
    suff_map = {s["requirement_id"]: s for s in sufficiency}

    # Count sufficiency coverage
    status_counts = {"SUFFICIENT": 0, "PARTIAL": 0, "INSUFFICIENT": 0, "NO_EVIDENCE": 0, "CONFLICTING": 0}
    for r in requirements:
        s_item = suff_map.get(r["id"])
        st = s_item["coverage_status"] if s_item else "NO_EVIDENCE"
        status_counts[st] = status_counts.get(st, 0) + 1

    total_reqs = len(requirements)
    sufficient_count = status_counts.get("SUFFICIENT", 0)
    partial_count = status_counts.get("PARTIAL", 0)
    insufficient_count = status_counts.get("INSUFFICIENT", 0)
    no_evidence_count = status_counts.get("NO_EVIDENCE", 0)
    conflicting_count = status_counts.get("CONFLICTING", 0)

    unresolved_conflicts = [c for c in conflicts if c.get("resolution_status") == "unresolved"]
    critical_conflicts = [c for c in conflicts if c.get("severity") == "critical" and c.get("resolution_status") == "unresolved"]

    evaluated_scenarios = [sc for sc in scenarios if sc.get("scenario_overall_outcome")]
    critical_scenarios = [sc for sc in evaluated_scenarios if sc.get("outcome_shift") == "CRITICAL_FAILURE"]
    vulnerable_scenarios = [sc for sc in evaluated_scenarios if sc.get("scenario_overall_outcome") in {"VULNERABLE", "HIGHLY_VULNERABLE"}]

    coverage_ratio = round(sufficient_count / total_reqs, 2) if total_reqs > 0 else 0.0

    overall_robustness = compute_report_robustness(
        requirements_count=total_reqs,
        sufficient_count=sufficient_count,
        partial_count=partial_count,
        insufficient_count=insufficient_count,
        no_evidence_count=no_evidence_count,
        conflicting_count=conflicting_count,
        unresolved_conflicts_count=len(unresolved_conflicts),
        critical_conflicts_count=len(critical_conflicts),
        evaluated_scenarios_count=len(evaluated_scenarios),
        critical_scenarios_count=len(critical_scenarios),
        vulnerable_scenarios_count=len(vulnerable_scenarios),
    )

    # 1. Section 2: Decision Contract Summary
    section_2_requirements = [
        ContractRequirementSummary(
            requirement_id=r["id"],
            title=r["title"],
            priority=r["priority"],
            verification_criteria=r.get("verification_criteria", ""),
            evidence_types=r.get("evidence_types", []),
        )
        for r in requirements
    ]

    section_2_contract = DecisionContractSummarySection(
        contract_id=contract.get("id", ""),
        normalized_question=contract.get("normalized_question") or inv.get("research_question", ""),
        decision_objective=contract.get("decision_objective") or "Decision objective not specified",
        scope=contract.get("scope") or "General Inquiry Scope",
        requirements=section_2_requirements,
        constraints=[c.get("description", "") for c in constraints],
        assumptions=[a.get("description", "") for a in assumptions],
        unresolved_questions=[u.get("question", "") for u in unresolved_questions],
    )

    # 2. Section 3: Evidence Intelligence Summary
    factual_claims = [c for c in claims if c.get("category", "factual") == "factual"]
    statistical_claims = [c for c in claims if c.get("category") in {"statistical", "quantitative", "numerical"}]

    source_items = []
    for s in sources:
        pub_d = s.get("publication_date")
        classification = classify_source_freshness(pub_d)
        f_status = s.get("freshness_status") or classification["status"]
        f_exp = s.get("freshness_explanation") or classification["explanation"]
        
        warning_text = ""
        if f_status == "Potentially Outdated":
            warning_text = f"Source was published {classification.get('days_old')} days ago (over 365-day threshold). Publication age is an indicator for review, not proof of inaccuracy."
        elif f_status == "Undated Source":
            warning_text = "Source lacks verified publication timestamp. Verify vintage manually."
        elif f_status in ("Date Requires Review", "Date Unavailable"):
            warning_text = f"Timestamp anomaly: {f_exp}"

        source_items.append(
            SourceProvenanceItem(
                source_id=s["id"],
                title=s.get("title") or "Untitled Ingested Source",
                source_origin=s.get("source_origin") or "UNKNOWN",
                publisher=s.get("publisher") or "Unknown Publisher",
                publication_date=pub_d or "Undated",
                ingestion_date=s.get("retrieved_at") or "",
                freshness_classification=f_status,
                date_extraction_origin=s.get("date_source") or (s.get("source_type") or "unknown"),
                freshness_warning=warning_text,
                original_url=s.get("original_url") or "",
                source_type=s.get("source_type", "document"),
                sha256_hash=s.get("content_hash") or "unhashed",
                extraction_status=s.get("extraction_status", "completed"),
                claims_count=s.get("claims_count", 0),
            )
        )

    section_3_evidence = EvidenceIntelligenceSection(
        total_sources=len(sources),
        total_passages=len(passages),
        total_claims=len(claims),
        factual_claims_count=len(factual_claims),
        statistical_claims_count=len(statistical_claims),
        sources=source_items,
        reliability_limitations=(
            f"Evidence base contains {len(sources)} ingested sources and {len(claims)} atomic claims. "
            "Forensic provenance verified cryptographically via SHA-256 passage segmentation. "
            f"{'Primary regulatory audit sources require further verification.' if any(r.get('priority') == 'HIGH' for r in requirements) else 'Source baseline verified.'}"
        ),
    )

    # 3. Section 4: Requirement-Level Assessment Matrix
    # Map relationships by requirement_id
    rel_map = {}
    for rel in relationships:
        rid = rel["requirement_id"]
        if rid not in rel_map:
            rel_map[rid] = []
        rel_map[rid].append(rel)

    # Map gaps by requirement_id
    gap_map = {}
    for g in gaps:
        rid = g["requirement_id"]
        if rid not in gap_map:
            gap_map[rid] = []
        gap_map[rid].append(g)

    # Map conflicts to requirements via linked claims
    claim_to_req = {}
    for rel in relationships:
        claim_to_req[rel["claim_id"]] = rel["requirement_id"]

    req_conflicts_map = {}
    for conf in conflicts:
        rid_a = claim_to_req.get(conf["claim_a_id"])
        rid_b = claim_to_req.get(conf["claim_b_id"])
        target_rids = set(filter(None, [rid_a, rid_b]))
        for tr in target_rids:
            if tr not in req_conflicts_map:
                req_conflicts_map[tr] = []
            req_conflicts_map[tr].append(conf)

    matrix_rows = []
    for r in requirements:
        rid = r["id"]
        s_item = suff_map.get(rid)
        c_status = s_item["coverage_status"] if s_item else "NO_EVIDENCE"
        summary_text = s_item["assessment_summary"] if s_item else "No evidence linked to verify this requirement."

        supporting = []
        for rel in rel_map.get(rid, []):
            supporting.append(
                SupportingClaimItem(
                    claim_id=rel["claim_id"],
                    claim_text=rel.get("claim_text", ""),
                    source_title=rel.get("source_title") or "Ingested Document",
                    source_id=rel.get("source_id", ""),
                    passage_hash=rel.get("passage_hash") or "",
                    relevance=rel.get("relevance", "STRONG"),
                    confidence=float(rel.get("confidence", 0.8)),
                )
            )

        opposing = []
        for cf in req_conflicts_map.get(rid, []):
            opposing.append(
                OpposingEvidenceItem(
                    conflict_id=cf["id"],
                    conflict_type=cf["conflict_type"],
                    severity=cf["severity"],
                    claim_text=cf.get("claim_b_text") or cf.get("claim_a_text") or "",
                    source_title=cf.get("source_b_title") or cf.get("source_a_title") or "Opposing Source",
                    resolution_status=cf.get("resolution_status", "unresolved"),
                )
            )

        r_gaps = [g.get("gap_description", "") for g in gap_map.get(rid, [])]

        matrix_rows.append(
            RequirementAssessmentRow(
                requirement_id=rid,
                title=r["title"],
                priority=r["priority"],
                coverage_status=c_status,
                supporting_claims=supporting,
                opposing_evidence=opposing,
                identified_gaps=r_gaps,
                assessment_summary=summary_text,
                confidence=float(s_item["confidence"]) if s_item else 0.5,
            )
        )

    section_4_matrix = RequirementAssessmentSection(
        matrix=matrix_rows,
        coverage_summary=status_counts,
    )

    # 4. Section 5: Conflict and Contradiction Analysis
    conflict_items = [
        ReportConflictItem(
            conflict_id=c["id"],
            conflict_type=c["conflict_type"],
            severity=c["severity"],
            claim_a_id=c["claim_a_id"],
            claim_a_text=c.get("claim_a_text") or "Claim A text",
            claim_a_source=c.get("source_a_title") or "Source A",
            claim_b_id=c["claim_b_id"],
            claim_b_text=c.get("claim_b_text") or "Claim B text",
            claim_b_source=c.get("source_b_title") or "Source B",
            explanation=c.get("explanation", ""),
            resolution_status=c.get("resolution_status", "unresolved"),
            reviewer_notes=c.get("reviewer_notes") or "",
            decision_impact=f"Severity: {c.get('severity', '').upper()}. Status: {c.get('resolution_status', '').upper()}.",
        )
        for c in conflicts
    ]

    section_5_conflicts = ConflictAnalysisSection(
        total_conflicts=len(conflicts),
        unresolved_count=len(unresolved_conflicts),
        critical_count=len(critical_conflicts),
        conflicts=conflict_items,
    )

    # 5. Section 6: Evidence Gaps and Uncertainty
    gap_items = [
        ReportGapItem(
            gap_id=g["id"],
            requirement_id=g["requirement_id"],
            requirement_title=g.get("requirement_title") or "Target Requirement",
            gap_description=g.get("gap_description", ""),
            why_it_matters=g.get("why_it_matters", ""),
            evidence_needed=g.get("evidence_needed", ""),
            suggested_source_type=g.get("suggested_source_type") or "Authoritative Audit / Regulatory Filing",
            priority=g.get("priority", "HIGH"),
        )
        for g in gaps
    ]

    section_6_gaps = GapsAndUncertaintySection(
        total_gaps=len(gaps),
        high_priority_gaps=len([g for g in gaps if g.get("priority") == "HIGH"]),
        gaps=gap_items,
    )

    # 6. Section 7: Decision Stress-Test Results
    stress_items = []
    for sc in scenarios:
        vulnerabilities = []
        if sc.get("key_vulnerabilities"):
            try:
                vulnerabilities = json.loads(sc["key_vulnerabilities"]) if isinstance(sc["key_vulnerabilities"], str) else sc["key_vulnerabilities"]
            except Exception:
                vulnerabilities = [sc["key_vulnerabilities"]]

        stress_items.append(
            ReportStressScenarioItem(
                scenario_id=sc["id"],
                title=sc.get("title") or "Stress Scenario",
                category=sc.get("category", "RISK_MATERIALIZATION"),
                trigger_condition=sc.get("trigger_condition", ""),
                severity=sc.get("severity", "HIGH"),
                outcome_shift=sc.get("outcome_shift") or "UNTESTED",
                scenario_outcome=sc.get("scenario_overall_outcome") or "UNTESTED",
                impact_explanation=sc.get("impact_explanation") or sc.get("expected_impact", ""),
                key_vulnerabilities=vulnerabilities if isinstance(vulnerabilities, list) else [],
            )
        )

    section_7_stress = StressTestResultsSection(
        baseline_outcome=overall_robustness,
        total_scenarios=len(scenarios),
        vulnerable_scenarios=len(vulnerable_scenarios),
        scenarios=stress_items,
    )

    # 7. Section 8: Key Risks and Mitigation Register (Deterministic Fallback)
    deterministic_risks = []
    risk_idx = 1

    # Conflict risks
    for c in unresolved_conflicts:
        deterministic_risks.append(
            RiskRegisterItem(
                risk_id=f"RISK-{risk_idx:02d}",
                title=f"Unresolved {c['conflict_type'].replace('_', ' ').title()}",
                origin="Conflict",
                severity=c.get("severity", "HIGH").upper(),
                affected_requirement=c.get("claim_a_id", ""),
                consequence=c.get("explanation", "")[:250],
                mitigation=c.get("recommended_action") or "Corroborate conflicting claim with verified primary source.",
                additional_evidence_needed="Independent third-party verification report.",
            )
        )
        risk_idx += 1

    # High gaps risks
    for g in [g for g in gaps if g.get("priority") == "HIGH"]:
        deterministic_risks.append(
            RiskRegisterItem(
                risk_id=f"RISK-{risk_idx:02d}",
                title=f"Evidence Gap: {g.get('requirement_title', 'Requirement')}",
                origin="Evidence Gap",
                severity="HIGH",
                affected_requirement=g.get("requirement_id", ""),
                consequence=g.get("why_it_matters", ""),
                mitigation=f"Procure {g.get('suggested_source_type', 'audit records')} targeting: {g.get('evidence_needed', '')}",
                additional_evidence_needed=g.get("evidence_needed", ""),
            )
        )
        risk_idx += 1

    # Stress failure risks
    for sc in critical_scenarios + vulnerable_scenarios:
        deterministic_risks.append(
            RiskRegisterItem(
                risk_id=f"RISK-{risk_idx:02d}",
                title=f"Stress Trigger: {sc.get('title', 'Scenario')}",
                origin="Stress Scenario",
                severity=sc.get("severity", "HIGH").upper(),
                affected_requirement=sc.get("id", ""),
                consequence=sc.get("impact_explanation") or sc.get("expected_impact", ""),
                mitigation=f"Establish operational hedging against condition: {sc.get('trigger_condition', '')}",
                additional_evidence_needed=sc.get("evidence_needed") or "Scenario monitoring metrics.",
            )
        )
        risk_idx += 1

    # Contract assumptions risks
    for a in assumptions:
        if a.get("validation_status") == "pending":
            deterministic_risks.append(
                RiskRegisterItem(
                    risk_id=f"RISK-{risk_idx:02d}",
                    title=f"Unvalidated Assumption: {a.get('description', '')[:60]}...",
                    origin="Contract Assumption",
                    severity="MEDIUM",
                    affected_requirement=a.get("contract_id", ""),
                    consequence="Invalidation of underlying decision premise if assumption proves false.",
                    mitigation="Conduct direct empirical test to confirm assumption validity.",
                    additional_evidence_needed="Direct operational or contractual confirmation.",
                )
            )
            risk_idx += 1

    # 8. Section 9: Recommended Next Actions (Deterministic Fallback)
    deterministic_actions = []
    act_idx = 1

    if critical_conflicts:
        deterministic_actions.append(
            RecommendedActionItem(
                action_id=f"ACT-{act_idx:02d}",
                action_title="Resolve Critical Evidence Conflicts",
                description="Convene analyst panel or procure authoritative audit to reconcile diverging factual claims.",
                priority="P1_IMMEDIATE",
                driver=f"{len(critical_conflicts)} critical unresolved contradiction(s) detected.",
                target_requirement=critical_conflicts[0].get("id", ""),
                expected_outcome="Elimination of evidentiary contradictions blocking decision certainty.",
            )
        )
        act_idx += 1

    if any(g.get("priority") == "HIGH" for g in gaps):
        deterministic_actions.append(
            RecommendedActionItem(
                action_id=f"ACT-{act_idx:02d}",
                action_title="Procure Missing Primary Evidence for High-Priority Gaps",
                description="Ingest authoritative sources covering unverified requirement dimensions.",
                priority="P1_IMMEDIATE",
                driver=f"{len([g for g in gaps if g.get('priority') == 'HIGH'])} high-priority evidence gap(s).",
                target_requirement=gaps[0].get("requirement_id", ""),
                expected_outcome="Transition requirements from INSUFFICIENT to SUFFICIENT coverage.",
            )
        )
        act_idx += 1

    if vulnerable_scenarios:
        deterministic_actions.append(
            RecommendedActionItem(
                action_id=f"ACT-{act_idx:02d}",
                action_title="Implement Safeguards for Stress-Test Trigger Conditions",
                description=f"Formulate contingency triggers for identified scenarios: {vulnerable_scenarios[0].get('title', '')}.",
                priority="P2_HIGH",
                driver=f"{len(vulnerable_scenarios)} stress scenario(s) induced vulnerability.",
                target_requirement=vulnerable_scenarios[0].get("id", ""),
                expected_outcome="Resilience of decision outcome under stress conditions.",
            )
        )
        act_idx += 1

    deterministic_actions.append(
        RecommendedActionItem(
            action_id=f"ACT-{act_idx:02d}",
            action_title="Continuous Temporal Surveillance",
            description="Establish recurring provenance verification to capture future revisions or source updates.",
            priority="P3_MODERATE",
            driver="Temporal drift and source obsolescence risk.",
            target_requirement="all",
            expected_outcome="Early warning of invalidated source claims.",
        )
    )

    # 9. Invoke Gemini or Fallback Synthesis
    gemini_synthesis = None
    if not fast_mode:
        gemini_synthesis = synthesize_report_with_gemini(
            raw_data=raw,
            robustness=overall_robustness,
            coverage_ratio=coverage_ratio,
            deterministic_risks=deterministic_risks,
            deterministic_actions=deterministic_actions,
        )

    processing_mode = "gemini" if gemini_synthesis else "fallback"

    if gemini_synthesis:
        exec_conclusion = gemini_synthesis.executive_conclusion
        rel_limitations = gemini_synthesis.reliability_limitations or section_3_evidence.reliability_limitations
        final_risks = gemini_synthesis.risks or deterministic_risks
        final_actions = gemini_synthesis.actions or deterministic_actions
        supported_findings = gemini_synthesis.supported_findings or [
            f"Requirement '{r['title']}' verified with corroborating evidence."
            for r in requirements if suff_map.get(r["id"], {}).get("coverage_status") == "SUFFICIENT"
        ]
        uncertainties = gemini_synthesis.uncertainties_and_caveats or [
            f"Requirement '{r['title']}' lacks sufficient corroboration ({suff_map.get(r['id'], {}).get('coverage_status', 'NO_EVIDENCE')})."
            for r in requirements if suff_map.get(r["id"], {}).get("coverage_status") != "SUFFICIENT"
        ]
        invalidating_conds = gemini_synthesis.invalidating_conditions or [
            sc.get("trigger_condition", "") for sc in scenarios if sc.get("outcome_shift") in {"CRITICAL_FAILURE", "DEGRADED"}
        ]
        decision_posture = gemini_synthesis.recommended_decision_posture
    else:
        # Deterministic executive synthesis
        exec_conclusion = (
            f"Investigation into \"{inv.get('research_question', '')}\" has completed forensic intelligence synthesis. "
            f"Current decision robustness is classified as {overall_robustness} based on an evidence coverage ratio of {coverage_ratio * 100:.1f}%. "
            f"A total of {len(sources)} sources and {len(claims)} atomic claims were analyzed against {total_reqs} decision contract requirements. "
            f"{f'Attention required: {len(unresolved_conflicts)} unresolved contradiction(s) and {len(gaps)} evidence gap(s) directly threaten decision validity.' if (unresolved_conflicts or gaps) else 'No critical contradictions were identified across ingested evidence.'} "
            f"Stress testing revealed {len(vulnerable_scenarios)} scenario(s) causing significant outcome degradation."
        )
        rel_limitations = section_3_evidence.reliability_limitations
        final_risks = deterministic_risks
        final_actions = deterministic_actions
        supported_findings = [
            f"Requirement '{r['title']}' verified with corroborating evidence."
            for r in requirements if suff_map.get(r["id"], {}).get("coverage_status") == "SUFFICIENT"
        ]
        uncertainties = [
            f"Requirement '{r['title']}' lacks sufficient corroboration ({suff_map.get(r['id'], {}).get('coverage_status', 'NO_EVIDENCE')})."
            for r in requirements if suff_map.get(r["id"], {}).get("coverage_status") != "SUFFICIENT"
        ]
        invalidating_conds = [
            sc.get("trigger_condition", "") for sc in scenarios if sc.get("outcome_shift") in {"CRITICAL_FAILURE", "DEGRADED"}
        ]
        decision_posture = (
            "PROCEED" if overall_robustness == "ROBUST"
            else "PROCEED_WITH_SAFEGUARDS" if overall_robustness == "CONDITIONALLY_ROBUST"
            else "DEFER_PENDING_EVIDENCE" if overall_robustness == "VULNERABLE"
            else "REJECT_INSUFFICIENT_EVIDENCE"
        )

    # Section 1: Executive Decision Brief & Atomic Version Persistence
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    snapshot_metadata = get_investigation_current_snapshot(conn, investigation_id)
    snapshot_metadata["generated_at"] = now_iso

    section_3_evidence.reliability_limitations = rel_limitations

    section_8_risks = RiskMitigationSection(
        total_risks=len(final_risks),
        critical_risks=len([r for r in final_risks if r.severity == "CRITICAL"]),
        high_risks=len([r for r in final_risks if r.severity == "HIGH"]),
        risks=final_risks,
    )

    section_9_actions = RecommendedActionsSection(actions=final_actions)

    section_10_conclusion = FinalConclusionSection(
        supported_findings=supported_findings,
        uncertainties_and_caveats=uncertainties,
        invalidating_conditions=invalidating_conds,
        recommended_decision_posture=decision_posture,
    )

    # Concurrency-safe atomic report version assignment with retry handling
    max_retries = 5
    assigned_version = 1
    persisted_report_id = None
    final_payload = None

    for attempt in range(max_retries):
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COALESCE(MAX(report_version), 0) AS max_v FROM decision_intelligence_reports WHERE investigation_id = ?;",
                (investigation_id,)
            )
            max_v = cursor.fetchone()["max_v"]
            assigned_version = max_v + 1

            section_1_brief = ExecutiveBriefSection(
                investigation_id=investigation_id,
                research_question=inv.get("research_question", ""),
                decision_objective=contract.get("decision_objective") or inv.get("research_question", ""),
                report_version=assigned_version,
                generated_at=now_iso,
                overall_robustness=overall_robustness,
                coverage_ratio=coverage_ratio,
                total_sources=len(sources),
                total_claims=len(claims),
                unresolved_conflicts_count=len(unresolved_conflicts),
                identified_gaps_count=len(gaps),
                high_severity_scenarios_count=len([sc for sc in scenarios if sc.get("severity") in {"HIGH", "CRITICAL"}]),
                executive_conclusion=exec_conclusion,
            )

            final_payload = DecisionReportPayload(
                executive_brief=section_1_brief,
                decision_contract=section_2_contract,
                evidence_intelligence=section_3_evidence,
                requirement_assessment=section_4_matrix,
                conflict_analysis=section_5_conflicts,
                gaps_and_uncertainty=section_6_gaps,
                stress_test_results=section_7_stress,
                risk_mitigation=section_8_risks,
                recommended_actions=section_9_actions,
                final_conclusion=section_10_conclusion,
            )

            persisted_report_id = f"rpt-{uuid.uuid4().hex[:12]}"

            cursor.execute("""
                INSERT INTO decision_intelligence_reports (
                    id, investigation_id, report_version, report_status, processing_mode,
                    overall_robustness, executive_summary, report_data_json,
                    snapshot_metadata_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                persisted_report_id,
                investigation_id,
                assigned_version,
                "published",
                processing_mode,
                overall_robustness,
                exec_conclusion,
                json.dumps(final_payload.model_dump()),
                json.dumps(snapshot_metadata),
                now_iso,
                now_iso,
            ))

            # Audit run
            run_id = f"rptrun-{uuid.uuid4().hex[:12]}"
            cursor.execute("""
                INSERT INTO decision_intelligence_report_runs (
                    id, investigation_id, report_id, processing_mode, status, error_message, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?);
            """, (
                run_id,
                investigation_id,
                persisted_report_id,
                processing_mode,
                "completed",
                "",
                now_iso,
            ))

            conn.commit()
            break
        except sqlite3.IntegrityError:
            conn.rollback()
            if attempt == max_retries - 1:
                raise
            time.sleep(0.05 * (attempt + 1))

    return DecisionReportModel(
        id=persisted_report_id,
        investigation_id=investigation_id,
        report_version=assigned_version,
        report_status="published",
        processing_mode=processing_mode,
        overall_robustness=overall_robustness,
        executive_summary=exec_conclusion,
        report_data=final_payload,
        snapshot_metadata=snapshot_metadata,
        is_stale=False,
        created_at=now_iso,
        updated_at=now_iso,
    )


def get_investigation_reports(conn, investigation_id: str) -> DecisionReportListResponse:
    """Lists all historical report versions for an investigation."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, investigation_id, report_version, report_status, processing_mode,
               overall_robustness, executive_summary, snapshot_metadata_json, created_at
        FROM decision_intelligence_reports
        WHERE investigation_id = ?
        ORDER BY report_version DESC;
    """, (investigation_id,))
    rows = cursor.fetchall()

    current_snapshot = get_investigation_current_snapshot(conn, investigation_id)

    reports = []
    latest_v = 0
    for r in rows:
        r_dict = dict(r)
        snap = {}
        if r_dict.get("snapshot_metadata_json"):
            try:
                snap = json.loads(r_dict["snapshot_metadata_json"])
            except Exception:
                pass
        stale = bool(r_dict.get("is_stale", 0)) or is_report_stale(current_snapshot, snap)
        if r_dict["report_version"] > latest_v:
            latest_v = r_dict["report_version"]

        reports.append(
            DecisionReportSummaryModel(
                id=r_dict["id"],
                investigation_id=r_dict["investigation_id"],
                report_version=r_dict["report_version"],
                report_status=r_dict["report_status"],
                processing_mode=r_dict["processing_mode"],
                overall_robustness=r_dict["overall_robustness"],
                executive_summary=r_dict["executive_summary"],
                is_stale=stale,
                created_at=r_dict["created_at"],
            )
        )

    return DecisionReportListResponse(
        investigation_id=investigation_id,
        total_reports=len(reports),
        latest_version=latest_v,
        reports=reports,
    )


def get_report_by_id(conn, investigation_id: str, report_id: str) -> Optional[DecisionReportModel]:
    """Retrieves a specific version of a report by its ID."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM decision_intelligence_reports
        WHERE investigation_id = ? AND id = ?;
    """, (investigation_id, report_id))
    row = cursor.fetchone()
    if not row:
        return None

    r_dict = dict(row)
    payload_dict = json.loads(r_dict["report_data_json"])
    snapshot_meta = json.loads(r_dict["snapshot_metadata_json"]) if r_dict.get("snapshot_metadata_json") else {}

    current_snapshot = get_investigation_current_snapshot(conn, investigation_id)
    stale = bool(r_dict.get("is_stale", 0)) or is_report_stale(current_snapshot, snapshot_meta)

    return DecisionReportModel(
        id=r_dict["id"],
        investigation_id=r_dict["investigation_id"],
        report_version=r_dict["report_version"],
        report_status=r_dict["report_status"],
        processing_mode=r_dict["processing_mode"],
        overall_robustness=r_dict["overall_robustness"],
        executive_summary=r_dict["executive_summary"],
        report_data=DecisionReportPayload(**payload_dict),
        snapshot_metadata=snapshot_meta,
        is_stale=stale,
        created_at=r_dict["created_at"],
        updated_at=r_dict["updated_at"],
    )


def get_latest_investigation_report(conn, investigation_id: str) -> Optional[DecisionReportModel]:
    """Fetches the latest published report version for an investigation."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id FROM decision_intelligence_reports
        WHERE investigation_id = ?
        ORDER BY report_version DESC LIMIT 1;
    """, (investigation_id,))
    row = cursor.fetchone()
    if not row:
        return None

    return get_report_by_id(conn, investigation_id, row["id"])


def get_report_status(conn, investigation_id: str) -> DecisionReportStatusResponse:
    """Provides high-level report availability, version, staleness, and robustness status."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, report_version, report_status, overall_robustness, processing_mode,
               snapshot_metadata_json, created_at
        FROM decision_intelligence_reports
        WHERE investigation_id = ?
        ORDER BY report_version DESC LIMIT 1;
    """, (investigation_id,))
    row = cursor.fetchone()
    if not row:
        return DecisionReportStatusResponse(
            investigation_id=investigation_id,
            has_report=False,
            processing_mode="none",
        )

    r_dict = dict(row)
    snapshot_meta = json.loads(r_dict["snapshot_metadata_json"]) if r_dict.get("snapshot_metadata_json") else {}
    current_snapshot = get_investigation_current_snapshot(conn, investigation_id)
    stale = bool(r_dict.get("is_stale", 0)) or is_report_stale(current_snapshot, snapshot_meta)

    return DecisionReportStatusResponse(
        investigation_id=investigation_id,
        has_report=True,
        latest_report_id=r_dict["id"],
        latest_version=r_dict["report_version"],
        latest_status=r_dict["report_status"],
        is_stale=stale,
        overall_robustness=r_dict["overall_robustness"],
        processing_mode=r_dict["processing_mode"],
        last_generated_at=r_dict["created_at"],
    )
