import os
import json
import uuid
import datetime
import logging
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Any, List, Optional, Tuple

from backend.models import (
    FragilityDimensionDetail,
    AttributionLedgerItem,
    DecisionFragilityResultModel,
    FragilityAnalysisResponse,
    FragilityStatusResponse,
    FragilityMethodologyResponse,
)

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# Methodology Version
METHODOLOGY_VERSION = "v1.2.0-deterministic"

# Dimension Weights (Sum = 1.00)
WEIGHT_D1 = 0.30  # Evidence Coverage Fragility
WEIGHT_D2 = 0.15  # Assumption Fragility
WEIGHT_D3 = 0.25  # Conflict Fragility
WEIGHT_D4 = 0.20  # Stress Test Fragility
WEIGHT_D5 = 0.10  # Requirement Sensitivity Concentration

# Priority Weights for Requirements
PRIORITY_WEIGHTS = {
    "CRITICAL": 1.00,
    "HIGH": 0.75,
    "MEDIUM": 0.50,
    "LOW": 0.25,
}

# Deficit Penalties for Sufficiency Statuses
DEFICIT_PENALTIES = {
    "NO_EVIDENCE": 1.00,
    "CONFLICTING": 0.85,
    "INSUFFICIENT": 0.75,
    "PARTIAL": 0.40,
    "SUFFICIENT": 0.00,
}

# Conflict Severity Base Penalties
CONFLICT_SEVERITY_PENALTIES = {
    "CRITICAL": 35.0,
    "HIGH": 20.0,
    "MEDIUM": 10.0,
    "LOW": 5.0,
}

# Conflict Resolution Multipliers
CONFLICT_RESOLUTION_MULTIPLIERS = {
    "unresolved": 1.00,
    "under_review": 0.70,
    "resolved_claim_a": 0.15,
    "resolved_claim_b": 0.15,
    "resolved_dismissed": 0.15,
    "resolved_both_valid": 0.15,
}

# Stress Test Shift Penalties
STRESS_SHIFT_PENALTIES = {
    "CRITICAL_FAILURE": 30.0,
    "DEGRADED": 15.0,
    "UNTESTED": 10.0,
    "STABLE": 0.0,
    "IMPROVED": -5.0,
}

# Stress Test Severity Multipliers
STRESS_SEVERITY_MULTIPLIERS = {
    "CRITICAL": 1.00,
    "HIGH": 0.80,
    "MEDIUM": 0.50,
    "LOW": 0.25,
}


def round_score(val: float) -> float:
    """
    Rounds a numerical score to exactly 1 decimal place using strict ROUND_HALF_UP.
    Guarantees deterministic, reproducible boundary transitions.
    """
    d = Decimal(str(val))
    return float(d.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def compute_fragility_input_fingerprint(conn, investigation_id: str) -> str:
    """
    Computes a cryptographic SHA-256 fingerprint representing the current
    state of contract, requirements, assumptions, sufficiency, conflicts, and stress tests.
    """
    import hashlib

    cursor = conn.cursor()
    hasher = hashlib.sha256()

    # 1. Contract & Requirements
    cursor.execute("""
        SELECT id, normalized_question, decision_objective FROM decision_contracts WHERE investigation_id = ?;
    """, (investigation_id,))
    c_row = cursor.fetchone()
    if c_row:
        hasher.update(f"contract:{c_row['id']}:{c_row['normalized_question']}:{c_row['decision_objective']}".encode())

    cursor.execute("""
        SELECT id, priority, title FROM contract_requirements
        WHERE contract_id = (SELECT id FROM decision_contracts WHERE investigation_id = ?)
        ORDER BY id ASC;
    """, (investigation_id,))
    for r in cursor.fetchall():
        hasher.update(f"req:{r['id']}:{r['priority']}:{r['title']}".encode())

    # 2. Assumptions
    cursor.execute("""
        SELECT id, description, confidence, validation_status FROM contract_assumptions
        WHERE contract_id = (SELECT id FROM decision_contracts WHERE investigation_id = ?)
        ORDER BY id ASC;
    """, (investigation_id,))
    for a in cursor.fetchall():
        hasher.update(f"assump:{a['id']}:{a['description']}:{a['confidence']}:{a['validation_status']}".encode())

    # 3. Sufficiency Assessments
    cursor.execute("""
        SELECT requirement_id, coverage_status, confidence FROM evidence_sufficiency_assessments
        WHERE investigation_id = ? ORDER BY requirement_id ASC;
    """, (investigation_id,))
    for s in cursor.fetchall():
        hasher.update(f"suff:{s['requirement_id']}:{s['coverage_status']}:{s['confidence']}".encode())

    # 4. Conflicts
    cursor.execute("""
        SELECT id, severity, resolution_status FROM evidence_conflicts
        WHERE investigation_id = ? ORDER BY id ASC;
    """, (investigation_id,))
    for cf in cursor.fetchall():
        hasher.update(f"conflict:{cf['id']}:{cf['severity']}:{cf['resolution_status']}".encode())

    # 5. Stress Evaluations
    cursor.execute("""
        SELECT scenario_id, outcome_shift, scenario_overall_outcome FROM decision_stress_evaluations
        WHERE investigation_id = ? ORDER BY scenario_id ASC;
    """, (investigation_id,))
    for se in cursor.fetchall():
        hasher.update(f"stress:{se['scenario_id']}:{se['outcome_shift']}:{se['scenario_overall_outcome']}".encode())

    return hasher.hexdigest()


def compute_d1_coverage_fragility(
    requirements: List[Dict[str, Any]],
    sufficiency_map: Dict[str, Dict[str, Any]]
) -> Tuple[float, List[AttributionLedgerItem], List[str]]:
    """
    Computes D1: Evidence Coverage Fragility (0 to 100).
    Formula: 100 * sum(w_i * Deficit(r_i)) / sum(w_i)
    Also identifies unsubstantiated critical requirements.
    """
    if not requirements:
        return 0.0, [], []

    total_weight = 0.0
    weighted_deficit_sum = 0.0
    ledger_items = []
    unsubstantiated_critical = []

    for req in requirements:
        r_id = req["id"]
        priority = req.get("priority", "MEDIUM").upper()
        w_i = PRIORITY_WEIGHTS.get(priority, 0.50)
        total_weight += w_i

        suff = sufficiency_map.get(r_id, {})
        status = suff.get("coverage_status", "NO_EVIDENCE")
        deficit = DEFICIT_PENALTIES.get(status, 1.00)

        weighted_deficit_sum += (w_i * deficit)

        # Flag critical unsubstantiated
        if priority == "CRITICAL" and status in ("NO_EVIDENCE", "CONFLICTING", "INSUFFICIENT", "PARTIAL"):
            unsubstantiated_critical.append(f"{req.get('title', r_id)} (Status: {status})")

    if total_weight <= 0.0:
        return 0.0, [], unsubstantiated_critical

    d1_score = 100.0 * (weighted_deficit_sum / total_weight)

    # Build ledger items for non-zero deficits
    for req in requirements:
        r_id = req["id"]
        priority = req.get("priority", "MEDIUM").upper()
        w_i = PRIORITY_WEIGHTS.get(priority, 0.50)
        suff = sufficiency_map.get(r_id, {})
        status = suff.get("coverage_status", "NO_EVIDENCE")
        deficit = DEFICIT_PENALTIES.get(status, 1.00)

        if deficit > 0:
            net_pts = 100.0 * ((w_i * deficit) / total_weight)
            net_dfi = WEIGHT_D1 * net_pts
            ledger_items.append(AttributionLedgerItem(
                item_id=str(uuid.uuid4()),
                dimension="d1_coverage",
                category="REQUIREMENT_GAP",
                entity_id=r_id,
                entity_type="requirement",
                entity_title=req.get("title", f"Requirement {r_id[:8]}"),
                base_penalty=round_score(deficit * 100.0),
                multiplier=round_score(w_i / total_weight),
                net_dimension_points=round_score(net_pts),
                net_dfi_contribution=round_score(net_dfi),
                rationale=f"Priority {priority} requirement has '{status}' sufficiency state (deficit: {deficit:.2f}).",
            ))

    return d1_score, ledger_items, unsubstantiated_critical


def compute_d2_assumption_fragility(
    assumptions: List[Dict[str, Any]]
) -> Tuple[float, str, bool, List[AttributionLedgerItem]]:
    """
    Computes D2: Assumption Fragility (0 to 100).
    If |A| == 0: returns 0.0, 'NOT_APPLICABLE', implicit_uncertainty_flag = True.
    If |A| > 0: returns 100 * sum(P(a_j)) / |A|, 'ASSESSED', False.
    """
    if not assumptions:
        return 0.0, "NOT_APPLICABLE", True, []

    n_assump = len(assumptions)
    penalty_sum = 0.0
    ledger_items = []

    for a in assumptions:
        a_id = a["id"]
        status = str(a.get("validation_status", "unvalidated")).lower()
        conf = float(a.get("confidence", 0.5))
        if conf < 0.0:
            conf = 0.0
        elif conf > 1.0:
            conf = 1.0

        if status == "invalidated":
            p_a = 1.0
        elif status == "unvalidated":
            p_a = 1.0 - (0.5 * conf)
        elif status == "partially_validated":
            p_a = 0.5 * (1.0 - conf)
        elif status == "validated":
            p_a = 0.0
        else:
            p_a = 1.0 - (0.5 * conf)

        penalty_sum += p_a

        if p_a > 0:
            net_pts = 100.0 * (p_a / n_assump)
            net_dfi = WEIGHT_D2 * net_pts
            ledger_items.append(AttributionLedgerItem(
                item_id=str(uuid.uuid4()),
                dimension="d2_assumptions",
                category="ASSUMPTION_UNCERTAINTY",
                entity_id=a_id,
                entity_type="assumption",
                entity_title=a.get("description", f"Assumption {a_id[:8]}"),
                base_penalty=round_score(p_a * 100.0),
                multiplier=round_score(1.0 / n_assump),
                net_dimension_points=round_score(net_pts),
                net_dfi_contribution=round_score(net_dfi),
                rationale=f"Assumption status '{status}' with confidence {conf:.2f} incurs penalty P={p_a:.2f}.",
            ))

    d2_score = 100.0 * (penalty_sum / n_assump)
    return d2_score, "ASSESSED", False, ledger_items


def compute_d3_conflict_fragility(
    conflicts: List[Dict[str, Any]],
    has_conflict_analysis_run: bool
) -> Tuple[float, str, List[AttributionLedgerItem]]:
    """
    Computes D3: Conflict Fragility (0 to 100).
    If C05 not executed: returns 0.0, 'NOT_ASSESSED', [].
    If C05 executed: returns min(100.0, sum(BasePenalty * Multiplier)), 'ASSESSED', ledger.
    """
    if not has_conflict_analysis_run:
        return 0.0, "NOT_ASSESSED", []

    if not conflicts:
        return 0.0, "ASSESSED", []

    penalty_sum = 0.0
    ledger_items = []

    for c in conflicts:
        c_id = c["id"]
        sev = str(c.get("severity", "MEDIUM")).upper()
        res_status = str(c.get("resolution_status", "unresolved")).lower()

        base_pen = CONFLICT_SEVERITY_PENALTIES.get(sev, 10.0)
        mult = CONFLICT_RESOLUTION_MULTIPLIERS.get(res_status, 1.0)
        net_pts = base_pen * mult
        penalty_sum += net_pts

        net_dfi = WEIGHT_D3 * min(100.0, net_pts)
        title = c.get("title") or c.get("explanation") or f"Conflict {c_id[:8]}"
        if len(title) > 80:
            title = title[:77] + "..."

        ledger_items.append(AttributionLedgerItem(
            item_id=str(uuid.uuid4()),
            dimension="d3_conflicts",
            category="EVIDENCE_CONFLICT",
            entity_id=c_id,
            entity_type="conflict",
            entity_title=title,
            base_penalty=round_score(base_pen),
            multiplier=round_score(mult),
            net_dimension_points=round_score(net_pts),
            net_dfi_contribution=round_score(net_dfi),
            rationale=f"Severity '{sev}' conflict with status '{res_status}' contributes {net_pts:.1f} penalty points.",
        ))

    d3_score = min(100.0, penalty_sum)
    return d3_score, "ASSESSED", ledger_items


def compute_d4_stress_fragility(
    evaluations: List[Dict[str, Any]],
    has_stress_testing_run: bool
) -> Tuple[float, str, List[AttributionLedgerItem], str]:
    """
    Computes D4: Stress Test Fragility (0 to 100).
    If C07 not executed: returns 0.0, 'NOT_ASSESSED', [], "".
    If C07 executed: returns max(0.0, min(100.0, sum(ShiftPenalty * Multiplier))), 'ASSESSED', ledger, note.
    """
    if not has_stress_testing_run:
        return 0.0, "NOT_ASSESSED", [], "Stress testing analysis (Component 07) has not been executed."

    if not evaluations:
        return 0.0, "ASSESSED", [], "Stress testing evaluated 0 scenarios."

    penalty_sum = 0.0
    ledger_items = []
    all_stable = True

    for ev in evaluations:
        s_id = ev.get("scenario_id", ev.get("id", str(uuid.uuid4())))
        shift = str(ev.get("outcome_shift", "STABLE")).upper()
        sev = str(ev.get("severity", "MEDIUM")).upper()

        if shift != "STABLE":
            all_stable = False

        base_pen = STRESS_SHIFT_PENALTIES.get(shift, 0.0)
        mult = STRESS_SEVERITY_MULTIPLIERS.get(sev, 0.50)
        net_pts = base_pen * mult
        penalty_sum += net_pts

        if net_pts != 0.0:
            net_dfi = WEIGHT_D4 * net_pts
            title = ev.get("title") or ev.get("scenario_title") or f"Stress Scenario {s_id[:8]}"
            ledger_items.append(AttributionLedgerItem(
                item_id=str(uuid.uuid4()),
                dimension="d4_stress",
                category="STRESS_VULNERABILITY",
                entity_id=s_id,
                entity_type="scenario",
                entity_title=title,
                base_penalty=round_score(base_pen),
                multiplier=round_score(mult),
                net_dimension_points=round_score(net_pts),
                net_dfi_contribution=round_score(net_dfi),
                rationale=f"Scenario shift '{shift}' under severity '{sev}' contributes {net_pts:.1f} penalty points.",
            ))

    d4_score = max(0.0, min(100.0, penalty_sum))

    # Clarification 1 phrasing
    if d4_score == 0.0 and all_stable:
        note = "No degradation was detected in the evaluated scenarios. This does not establish resilience to untested scenarios or real-world shocks."
    else:
        note = f"Evaluated {len(evaluations)} stress scenarios. Score: {d4_score:.1f}."

    return d4_score, "ASSESSED", ledger_items, note


def compute_d5_sensitivity_concentration(
    requirements: List[Dict[str, Any]],
    sufficiency_map: Dict[str, Dict[str, Any]]
) -> Tuple[float, str, List[AttributionLedgerItem], Dict[str, Any]]:
    """
    Computes D5: Requirement Sensitivity Concentration (0 to 100).
    Deterministic, bounded formula:
    F_i = w_i * Deficit(r_i)
    F_total = sum(F_i)
    F_max = max(Deficit(r_i))
    p_i = F_i / F_total
    HHI = sum(p_i^2)
    C = (HHI - 1/n) / (1 - 1/n) if n > 1 else 1.0 (clamped to [0.0, 1.0])
    D5 = 100.0 * (C * F_max)
    """
    if not requirements:
        return 0.0, "NOT_ASSESSED", [], {}

    n = len(requirements)
    weighted_deficits = []
    deficits = []

    for req in requirements:
        r_id = req["id"]
        priority = req.get("priority", "MEDIUM").upper()
        w_i = PRIORITY_WEIGHTS.get(priority, 0.50)
        suff = sufficiency_map.get(r_id, {})
        status = suff.get("coverage_status", "NO_EVIDENCE")
        deficit = DEFICIT_PENALTIES.get(status, 1.00)

        f_i = w_i * deficit
        weighted_deficits.append((r_id, req.get("title", r_id), f_i, deficit, priority))
        deficits.append(deficit)

    f_total = sum(f[2] for f in weighted_deficits)
    f_max = max(deficits) if deficits else 0.0

    if f_total == 0.0:
        return 0.0, "ASSESSED", [], {
            "hhi": 0.0,
            "normalized_concentration": 0.0,
            "peak_deficit": 0.0,
            "concentration_label": "UNCONCENTRATED",
        }

    if n == 1:
        c_norm = 1.0
        hhi = 1.0
    else:
        proportions = [f[2] / f_total for f in weighted_deficits]
        hhi = sum(p ** 2 for p in proportions)
        inv_n = 1.0 / n
        denom = 1.0 - inv_n
        if denom > 0:
            c_norm = (hhi - inv_n) / denom
        else:
            c_norm = 0.0
        c_norm = max(0.0, min(1.0, c_norm))

    d5_score = 100.0 * (c_norm * f_max)

    label = "HIGH CONCENTRATION" if c_norm >= 0.6 else ("MODERATE CONCENTRATION" if c_norm >= 0.3 else "DISTRIBUTED")

    ledger_items = []
    if d5_score > 0:
        ledger_items.append(AttributionLedgerItem(
            item_id=str(uuid.uuid4()),
            dimension="d5_concentration",
            category="SENSITIVITY_CONCENTRATION",
            entity_id="req_concentration",
            entity_type="concentration",
            entity_title=f"Sensitivity Concentration ({label})",
            base_penalty=round_score(f_max * 100.0),
            multiplier=round_score(c_norm),
            net_dimension_points=round_score(d5_score),
            net_dfi_contribution=round_score(WEIGHT_D5 * d5_score),
            rationale=f"Concentration index C={c_norm:.2f} scaled by peak deficit F_max={f_max:.2f} across {n} requirements.",
        ))

    metrics = {
        "hhi": round_score(hhi),
        "normalized_concentration": round_score(c_norm),
        "peak_deficit": round_score(f_max),
        "concentration_label": label,
    }

    return d5_score, "ASSESSED", ledger_items, metrics


def compute_composite_dfi(
    d1: float,
    d2: float,
    d3: float,
    d4: float,
    d5: float,
    d1_status: str,
    d2_status: str,
    d3_status: str,
    d4_status: str,
    d5_status: str,
    requirements: List[Dict[str, Any]],
    sufficiency_map: Dict[str, Dict[str, Any]]
) -> Tuple[float, str, bool, List[str], bool, Optional[str]]:
    """
    Computes raw composite DFI, rounds via ROUND_HALF_UP, determines classification,
    applies Critical Deficit Guardrail, and enforces Provisional Status Policy.
    Returns: (dfi_score, classification, is_provisional, provisional_reasons, guardrail_active, guardrail_reason)
    """
    raw_dfi = (
        (WEIGHT_D1 * d1) +
        (WEIGHT_D2 * d2) +
        (WEIGHT_D3 * d3) +
        (WEIGHT_D4 * d4) +
        (WEIGHT_D5 * d5)
    )
    dfi_score = round_score(raw_dfi)

    # Base Classification
    if dfi_score <= 25.0:
        base_classification = "LOW FRAGILITY"
    elif dfi_score <= 50.0:
        base_classification = "MODERATE FRAGILITY"
    elif dfi_score <= 75.0:
        base_classification = "HIGH FRAGILITY"
    else:
        base_classification = "CRITICAL FRAGILITY"

    # Evaluate Critical Deficit Guardrail
    guardrail_active = False
    guardrail_reason = None
    critical_deficits = []

    for req in requirements:
        if req.get("priority", "").upper() == "CRITICAL":
            suff = sufficiency_map.get(req["id"], {})
            status = suff.get("coverage_status", "NO_EVIDENCE")
            if status in ("NO_EVIDENCE", "CONFLICTING"):
                critical_deficits.append(f"{req.get('title', req['id'])} ({status})")

    if critical_deficits:
        guardrail_active = True
        guardrail_reason = (
            f"One or more CRITICAL requirements lack substantiating evidence (NO_EVIDENCE) or suffer "
            f"from unresolved contradictions (CONFLICTING): {', '.join(critical_deficits)}. "
            "Foundational evidence is ungrounded."
        )

    # Evaluate Provisional Policy
    is_provisional = False
    provisional_reasons = []

    if d3_status == "NOT_ASSESSED":
        is_provisional = True
        provisional_reasons.append("Conflict analysis (Component 05) has not been executed; D3 is unassessed.")
    if d4_status == "NOT_ASSESSED":
        is_provisional = True
        provisional_reasons.append("Stress testing (Component 07) has not been executed; D4 is unassessed.")

    # Determine Final Classification
    if guardrail_active:
        final_classification = f"CRITICAL DEFICIT GUARDRAIL: UNGROUNDED FOUNDATION (DFI: {dfi_score:.1f})"
    elif is_provisional:
        if dfi_score <= 25.0:
            final_classification = "MODERATE FRAGILITY (PROVISIONAL - INCOMPLETE COVERAGE)"
        else:
            final_classification = f"{base_classification} (PROVISIONAL)"
    else:
        final_classification = base_classification

    return dfi_score, final_classification, is_provisional, provisional_reasons, guardrail_active, guardrail_reason


def generate_deterministic_explanation(
    dfi_score: float,
    classification: str,
    guardrail_active: bool,
    guardrail_reason: Optional[str],
    is_provisional: bool,
    provisional_reasons: List[str],
    unsubstantiated_critical: List[str],
    d1: float,
    d2: float,
    d3: float,
    d4: float,
    d5: float,
    top_drivers: List[AttributionLedgerItem],
    d4_note: str,
) -> str:
    """
    Generates a deterministic analytical explanation narrative.
    """
    lines = [
        f"DECISION FRAGILITY ANALYSIS (DFI: {dfi_score:.1f} / 100.0) — CLASSIFICATION: {classification}",
        "",
    ]

    if guardrail_active:
        lines.append(f"CRITICAL DEFICIT GUARDRAIL TRIGGERED: {guardrail_reason}")
        lines.append("")

    if is_provisional:
        lines.append("PROVISIONAL ASSESSMENT NOTICE:")
        for pr in provisional_reasons:
            lines.append(f"- {pr}")
        lines.append("Unassessed dimensions are held at 0.0 in the raw calculation but prevent a low-fragility designation.")
        lines.append("")

    if unsubstantiated_critical:
        lines.append("UNSUBSTANTIATED CRITICAL REQUIREMENTS:")
        for uc in unsubstantiated_critical:
            lines.append(f"- {uc} is not fully substantiated by multi-source corroboration.")
        lines.append("")

    lines.append("DIMENSION BREAKDOWN:")
    lines.append(f"1. Evidence Coverage Fragility (D1, 30%): {d1:.1f}/100.0 (Net contribution: {d1*WEIGHT_D1:.1f} pts)")
    lines.append(f"2. Assumption Fragility (D2, 15%): {d2:.1f}/100.0 (Net contribution: {d2*WEIGHT_D2:.1f} pts)")
    lines.append(f"3. Conflict Fragility (D3, 25%): {d3:.1f}/100.0 (Net contribution: {d3*WEIGHT_D3:.1f} pts)")
    lines.append(f"4. Stress Test Fragility (D4, 20%): {d4:.1f}/100.0 (Net contribution: {d4*WEIGHT_D4:.1f} pts)")
    lines.append(f"   Note: {d4_note}")
    lines.append(f"5. Sensitivity Concentration (D5, 10%): {d5:.1f}/100.0 (Net contribution: {d5*WEIGHT_D5:.1f} pts)")
    lines.append("")

    if top_drivers:
        lines.append("PRIMARY FRAGILITY DRIVERS (POINT-BY-POINT ATTRIBUTION):")
        for idx, dr in enumerate(top_drivers[:5], 1):
            lines.append(f"{idx}. [{dr.dimension.upper()}] {dr.entity_title}: +{dr.net_dfi_contribution:.1f} DFI pts ({dr.rationale})")
    else:
        lines.append("No active penalty drivers recorded across evaluated dimensions.")

    return "\n".join(lines)


async def synthesize_fragility_explanation_with_gemini(
    dfi_score: float,
    classification: str,
    guardrail_active: bool,
    guardrail_reason: Optional[str],
    is_provisional: bool,
    provisional_reasons: List[str],
    unsubstantiated_critical: List[str],
    d1: float,
    d2: float,
    d3: float,
    d4: float,
    d5: float,
    top_drivers: List[AttributionLedgerItem],
    d4_note: str,
    objective: str
) -> Tuple[str, str]:
    """
    Attempts to generate an executive explanation narrative using Gemini.
    Falls back gracefully to deterministic explanation if Gemini fails or is unconfigured.
    Returns: (explanation_text, processing_mode)
    """
    deterministic_fallback = generate_deterministic_explanation(
        dfi_score, classification, guardrail_active, guardrail_reason,
        is_provisional, provisional_reasons, unsubstantiated_critical,
        d1, d2, d3, d4, d5, top_drivers, d4_note
    )

    if not GEMINI_API_KEY:
        return deterministic_fallback, "fallback"

    try:
        from google import genai

        client = genai.Client(api_key=GEMINI_API_KEY)

        prompt = (
            "You are an elite forensic evidence auditor interpreting a Decision Fragility Index (DFI) evaluation.\n\n"
            f"DECISION OBJECTIVE:\n\"{objective}\"\n\n"
            f"COMPUTED SCORES (100% DETERMINISTIC):\n"
            f"- DFI Score: {dfi_score:.1f} / 100.0\n"
            f"- Classification: {classification}\n"
            f"- Guardrail Active: {guardrail_active} (Reason: {guardrail_reason})\n"
            f"- Provisional: {is_provisional} (Reasons: {provisional_reasons})\n"
            f"- Unsubstantiated Critical Requirements: {unsubstantiated_critical}\n"
            f"- D1 Evidence Coverage: {d1:.1f}/100.0\n"
            f"- D2 Assumptions: {d2:.1f}/100.0\n"
            f"- D3 Conflicts: {d3:.1f}/100.0\n"
            f"- D4 Stress Permutations: {d4:.1f}/100.0 (Note: {d4_note})\n"
            f"- D5 Sensitivity Concentration: {d5:.1f}/100.0\n\n"
            f"TOP PENALTY DRIVERS:\n"
            f"{json.dumps([d.model_dump() for d in top_drivers[:5]], indent=2)}\n\n"
            "INSTRUCTIONS:\n"
            "Write a concise, rigorous 3-4 paragraph forensic interpretation explaining why this decision received this score, "
            "highlighting the highest-leverage evidentiary vulnerabilities, and advising the decision-maker on required safeguards.\n"
            "Do NOT alter or dispute any of the computed numbers. Maintain total fidelity to the empirical findings.\n"
            "If D4 note states 'No degradation was detected...', do not claim proof of real-world resilience."
        )

        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
        )

        text = response.text.strip() if response and response.text else ""
        if text:
            return text, "gemini"
        return deterministic_fallback, "fallback"

    except Exception as e:
        logger.warning(f"Gemini fragility explanation failed: {e}. Falling back to deterministic narrative.")
        return deterministic_fallback, "fallback"


def execute_fragility_analysis(
    conn,
    investigation_id: str,
    allow_gemini: bool = True
) -> DecisionFragilityResultModel:
    """
    Executes the complete, deterministic Decision Fragility Index evaluation for an investigation.
    Validates prerequisites, calculates D1-D5, applies guardrails, generates ledger,
    synthesizes explanation, and persists results to database.
    """
    cursor = conn.cursor()

    # 1. Prerequisite Validation
    cursor.execute("SELECT id FROM investigations WHERE id = ?;", (investigation_id,))
    if not cursor.fetchone():
        raise ValueError(f"Investigation {investigation_id} does not exist.")

    cursor.execute("""
        SELECT id, decision_objective FROM decision_contracts WHERE investigation_id = ?;
    """, (investigation_id,))
    c_row = cursor.fetchone()
    if not c_row:
        raise ValueError("PREREQ_NO_CONTRACT: Investigation has no decision contract compiled.")
    contract_id = c_row["id"]
    decision_objective = c_row["decision_objective"] or "Decision objective not specified"

    cursor.execute("""
        SELECT id, title, priority, verification_criteria
        FROM contract_requirements WHERE contract_id = ?
        ORDER BY sort_order ASC, id ASC;
    """, (contract_id,))
    requirements = [dict(r) for r in cursor.fetchall()]
    if not requirements:
        raise ValueError("PREREQ_NO_REQUIREMENTS: Decision contract contains 0 requirements.")

    cursor.execute("""
        SELECT requirement_id, coverage_status, confidence
        FROM evidence_sufficiency_assessments WHERE investigation_id = ?;
    """, (investigation_id,))
    suff_rows = cursor.fetchall()
    if not suff_rows:
        # Auto-compute and persist baseline sufficiency assessments from existing contract & evidence
        from backend.services.sufficiency_service import evaluate_deterministic_sufficiency
        claims_query = """
            SELECT r.requirement_id, r.relevance, c.id AS claim_id, c.claim_text, c.category,
                   s.title AS source_title
            FROM evidence_relationships r
            JOIN claims c ON r.claim_id = c.id
            LEFT JOIN sources s ON c.source_id = s.id
            WHERE r.investigation_id = ?;
        """
        cursor.execute(claims_query, (investigation_id,))
        req_claim_map: Dict[str, List[Dict[str, Any]]] = {}
        for row in cursor.fetchall():
            req_claim_map.setdefault(row["requirement_id"], []).append(dict(row))

        now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
        for req in requirements:
            rid = req["id"]
            linked_c = req_claim_map.get(rid, [])
            st_f, sum_f, lim_f, mis_f, act_f, conf_f, gaps_f = evaluate_deterministic_sufficiency(
                req, linked_c, []
            )
            asm_id = f"suff_{uuid.uuid4().hex[:12]}"
            cursor.execute("""
                INSERT INTO evidence_sufficiency_assessments (
                    id, investigation_id, requirement_id, coverage_status,
                    assessment_summary, limitations, missing_information,
                    recommended_action, confidence, analysis_method,
                    processing_mode, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'deterministic_baseline_init', 'fallback', ?, ?);
            """, (asm_id, investigation_id, rid, st_f, sum_f, lim_f, mis_f, act_f, conf_f, now_str, now_str))

        cursor.execute("""
            INSERT INTO evidence_sufficiency_runs (
                id, investigation_id, processing_mode, analysis_method,
                requirements_evaluated, sufficient_count, partial_count,
                insufficient_count, no_evidence_count, conflicting_count,
                total_gaps, created_at
            ) VALUES (?, ?, 'fallback', 'deterministic_baseline_init', ?, 0, 0, ?, 0, 0, 0, ?);
        """, (str(uuid.uuid4()), investigation_id, len(requirements), len(requirements), now_str))
        conn.commit()

        cursor.execute("""
            SELECT requirement_id, coverage_status, confidence
            FROM evidence_sufficiency_assessments WHERE investigation_id = ?;
        """, (investigation_id,))
        suff_rows = cursor.fetchall()

    sufficiency_map = {r["requirement_id"]: dict(r) for r in suff_rows}

    # Assumptions
    cursor.execute("""
        SELECT id, description, confidence, validation_status
        FROM contract_assumptions WHERE contract_id = ? ORDER BY id ASC;
    """, (contract_id,))
    assumptions = [dict(r) for r in cursor.fetchall()]

    # Conflicts & Runs
    cursor.execute("SELECT id FROM evidence_conflict_runs WHERE investigation_id = ?;", (investigation_id,))
    has_conflict_run = bool(cursor.fetchone())
    cursor.execute("""
        SELECT id, severity, resolution_status, explanation
        FROM evidence_conflicts WHERE investigation_id = ? ORDER BY id ASC;
    """, (investigation_id,))
    conflicts = [dict(r) for r in cursor.fetchall()]

    # Stress Tests & Runs
    cursor.execute("SELECT id FROM decision_stress_runs WHERE investigation_id = ?;", (investigation_id,))
    has_stress_run = bool(cursor.fetchone())
    cursor.execute("""
        SELECT se.scenario_id, se.outcome_shift, se.scenario_overall_outcome, ss.severity, ss.title
        FROM decision_stress_evaluations se
        JOIN decision_stress_scenarios ss ON se.scenario_id = ss.id
        WHERE se.investigation_id = ? ORDER BY se.scenario_id ASC;
    """, (investigation_id,))
    stress_evals = [dict(r) for r in cursor.fetchall()]

    # Fingerprint
    fingerprint = compute_fragility_input_fingerprint(conn, investigation_id)

    # 2. Compute Dimensions
    d1_score, d1_ledger, unsubstantiated_critical = compute_d1_coverage_fragility(requirements, sufficiency_map)
    d2_score, d2_status, d2_implicit_uncertainty, d2_ledger = compute_d2_assumption_fragility(assumptions)
    d3_score, d3_status, d3_ledger = compute_d3_conflict_fragility(conflicts, has_conflict_run)
    d4_score, d4_status, d4_ledger, d4_note = compute_d4_stress_fragility(stress_evals, has_stress_run)
    d5_score, d5_status, d5_ledger, d5_metrics = compute_d5_sensitivity_concentration(requirements, sufficiency_map)

    # 3. Composite Score & Classification
    dfi_score, classification, is_provisional, provisional_reasons, guardrail_active, guardrail_reason = compute_composite_dfi(
        d1_score, d2_score, d3_score, d4_score, d5_score,
        "ASSESSED", d2_status, d3_status, d4_status, d5_status,
        requirements, sufficiency_map
    )

    # Consolidated Attribution Ledger sorted by DFI contribution DESC
    full_ledger = d1_ledger + d2_ledger + d3_ledger + d4_ledger + d5_ledger
    full_ledger.sort(key=lambda x: x.net_dfi_contribution, reverse=True)

    # Dimension Details Map
    dimensions = {
        "d1_coverage": FragilityDimensionDetail(
            dimension_key="d1_coverage",
            dimension_name="Evidence Coverage Fragility",
            score=round_score(d1_score),
            weight=WEIGHT_D1,
            weighted_contribution=round_score(WEIGHT_D1 * d1_score),
            status="ASSESSED",
            explanation=f"Evaluated {len(requirements)} requirement(s) across sufficiency coverage states.",
            metrics={"requirements_count": len(requirements), "unsubstantiated_critical_count": len(unsubstantiated_critical)},
        ),
        "d2_assumptions": FragilityDimensionDetail(
            dimension_key="d2_assumptions",
            dimension_name="Assumption Fragility",
            score=round_score(d2_score),
            weight=WEIGHT_D2,
            weighted_contribution=round_score(WEIGHT_D2 * d2_score),
            status=d2_status,
            explanation="Evaluated recorded contract assumptions." if d2_status == "ASSESSED" else "No contract assumptions recorded. Implicit uncertainty remains unquantified.",
            metrics={"assumptions_count": len(assumptions), "implicit_uncertainty_flag": d2_implicit_uncertainty},
        ),
        "d3_conflicts": FragilityDimensionDetail(
            dimension_key="d3_conflicts",
            dimension_name="Conflict Fragility",
            score=round_score(d3_score),
            weight=WEIGHT_D3,
            weighted_contribution=round_score(WEIGHT_D3 * d3_score),
            status=d3_status,
            explanation=f"Evaluated {len(conflicts)} conflict record(s)." if d3_status == "ASSESSED" else "Conflict analysis (Component 05) has not been executed.",
            metrics={"conflicts_count": len(conflicts), "unresolved_count": sum(1 for c in conflicts if c.get("resolution_status") == "unresolved")},
        ),
        "d4_stress": FragilityDimensionDetail(
            dimension_key="d4_stress",
            dimension_name="Stress Test Fragility",
            score=round_score(d4_score),
            weight=WEIGHT_D4,
            weighted_contribution=round_score(WEIGHT_D4 * d4_score),
            status=d4_status,
            explanation=d4_note,
            metrics={"evaluated_scenarios_count": len(stress_evals)},
        ),
        "d5_concentration": FragilityDimensionDetail(
            dimension_key="d5_concentration",
            dimension_name="Requirement Sensitivity Concentration",
            score=round_score(d5_score),
            weight=WEIGHT_D5,
            weighted_contribution=round_score(WEIGHT_D5 * d5_score),
            status=d5_status,
            explanation=f"Concentration profile: {d5_metrics.get('concentration_label', 'EVALUATED')}.",
            metrics=d5_metrics,
        ),
    }

    # 4. Generate Narrative Explanation
    if allow_gemini and GEMINI_API_KEY:
        import asyncio
        try:
            # Check if running in async event loop
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Direct call fallback
                explanation_text, processing_mode = generate_deterministic_explanation(
                    dfi_score, classification, guardrail_active, guardrail_reason,
                    is_provisional, provisional_reasons, unsubstantiated_critical,
                    d1_score, d2_score, d3_score, d4_score, d5_score, full_ledger, d4_note
                ), "fallback"
            else:
                explanation_text, processing_mode = loop.run_until_complete(
                    synthesize_fragility_explanation_with_gemini(
                        dfi_score, classification, guardrail_active, guardrail_reason,
                        is_provisional, provisional_reasons, unsubstantiated_critical,
                        d1_score, d2_score, d3_score, d4_score, d5_score, full_ledger, d4_note, decision_objective
                    )
                )
        except Exception:
            explanation_text, processing_mode = generate_deterministic_explanation(
                dfi_score, classification, guardrail_active, guardrail_reason,
                is_provisional, provisional_reasons, unsubstantiated_critical,
                d1_score, d2_score, d3_score, d4_score, d5_score, full_ledger, d4_note
            ), "fallback"
    else:
        explanation_text = generate_deterministic_explanation(
            dfi_score, classification, guardrail_active, guardrail_reason,
            is_provisional, provisional_reasons, unsubstantiated_critical,
            d1_score, d2_score, d3_score, d4_score, d5_score, full_ledger, d4_note
        )
        processing_mode = "fallback"

    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    run_id = str(uuid.uuid4())
    result_id = str(uuid.uuid4())

    # 5. Persist Run and Result
    cursor.execute("""
        INSERT INTO decision_fragility_runs (
            id, investigation_id, input_fingerprint, is_provisional, processing_mode, status, error_message, created_at
        ) VALUES (?, ?, ?, ?, ?, 'success', '', ?);
    """, (run_id, investigation_id, fingerprint, 1 if is_provisional else 0, processing_mode, now_iso))

    cursor.execute("""
        INSERT INTO decision_fragility_results (
            id, run_id, investigation_id, methodology_version, dfi_score, classification,
            is_provisional, guardrail_active, guardrail_reason,
            d1_coverage, d2_assumptions, d3_conflicts, d4_stress, d5_concentration,
            dimension_details_json, attribution_ledger_json, explanation_text, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, (
        result_id, run_id, investigation_id, METHODOLOGY_VERSION, dfi_score, classification,
        1 if is_provisional else 0, 1 if guardrail_active else 0, guardrail_reason or "",
        round_score(d1_score), round_score(d2_score), round_score(d3_score), round_score(d4_score), round_score(d5_score),
        json.dumps({k: v.model_dump() for k, v in dimensions.items()}),
        json.dumps([item.model_dump() for item in full_ledger]),
        explanation_text,
        now_iso,
    ))

    conn.commit()

    return DecisionFragilityResultModel(
        id=result_id,
        run_id=run_id,
        investigation_id=investigation_id,
        methodology_version=METHODOLOGY_VERSION,
        dfi_score=dfi_score,
        classification=classification,
        is_provisional=is_provisional,
        provisional_reasons=provisional_reasons,
        guardrail_active=guardrail_active,
        guardrail_reason=guardrail_reason,
        unsubstantiated_critical_requirements=unsubstantiated_critical,
        d1_coverage=round_score(d1_score),
        d2_assumptions=round_score(d2_score),
        d3_conflicts=round_score(d3_score),
        d4_stress=round_score(d4_score),
        d5_concentration=round_score(d5_score),
        dimensions=dimensions,
        attribution_ledger=full_ledger,
        explanation_text=explanation_text,
        processing_mode=processing_mode,
        created_at=now_iso,
    )


def get_latest_fragility_result(conn, investigation_id: str) -> Optional[DecisionFragilityResultModel]:
    """
    Retrieves the most recent Decision Fragility evaluation result for an investigation.
    """
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM decision_fragility_results
        WHERE investigation_id = ?
        ORDER BY created_at DESC LIMIT 1;
    """, (investigation_id,))
    row = cursor.fetchone()
    if not row:
        return None

    r = dict(row)
    dim_dict = json.loads(r["dimension_details_json"]) if r["dimension_details_json"] else {}
    ledger_list = json.loads(r["attribution_ledger_json"]) if r["attribution_ledger_json"] else []

    dimensions = {k: FragilityDimensionDetail(**v) for k, v in dim_dict.items()}
    ledger = [AttributionLedgerItem(**item) for item in ledger_list]

    # Reconstruct unsubstantiated critical requirements from ledger or dimensions
    unsubstantiated = []
    if "d1_coverage" in dimensions:
        cursor.execute("""
            SELECT cr.title, esa.coverage_status
            FROM contract_requirements cr
            JOIN evidence_sufficiency_assessments esa ON cr.id = esa.requirement_id
            WHERE esa.investigation_id = ? AND cr.priority = 'CRITICAL'
              AND esa.coverage_status IN ('NO_EVIDENCE', 'CONFLICTING', 'INSUFFICIENT', 'PARTIAL');
        """, (investigation_id,))
        for uc in cursor.fetchall():
            unsubstantiated.append(f"{uc['title']} (Status: {uc['coverage_status']})")

    # Fetch run processing mode and check staleness
    cursor.execute("SELECT input_fingerprint, processing_mode FROM decision_fragility_runs WHERE id = ?;", (r["run_id"],))
    run_row = cursor.fetchone()
    processing_mode = run_row["processing_mode"] if run_row else "fallback"
    run_fp = run_row["input_fingerprint"] if run_row else ""
    current_fp = compute_fragility_input_fingerprint(conn, investigation_id)
    is_stale = bool(run_fp and run_fp != current_fp)

    return DecisionFragilityResultModel(
        id=r["id"],
        run_id=r["run_id"],
        investigation_id=r["investigation_id"],
        methodology_version=r["methodology_version"],
        dfi_score=r["dfi_score"],
        classification=r["classification"],
        is_provisional=bool(r["is_provisional"]),
        provisional_reasons=[],
        guardrail_active=bool(r["guardrail_active"]),
        guardrail_reason=r["guardrail_reason"] if r["guardrail_reason"] else None,
        unsubstantiated_critical_requirements=unsubstantiated,
        d1_coverage=r["d1_coverage"],
        d2_assumptions=r["d2_assumptions"],
        d3_conflicts=r["d3_conflicts"],
        d4_stress=r["d4_stress"],
        d5_concentration=r["d5_concentration"],
        dimensions=dimensions,
        attribution_ledger=ledger,
        explanation_text=r["explanation_text"] or "",
        processing_mode=processing_mode,
        is_stale=is_stale,
        created_at=r["created_at"],
    )


def get_fragility_status(conn, investigation_id: str) -> FragilityStatusResponse:
    """
    Evaluates the complete prerequisite and staleness status of the Fragility Engine.
    Enforces strict INDETERMINATE classification when mandatory inputs are missing
    (no contract, no requirements, no sufficiency assessment) or when upstream
    records are stale.
    """
    cursor = conn.cursor()

    # 1. Verify Investigation Existence
    cursor.execute("SELECT id FROM investigations WHERE id = ?;", (investigation_id,))
    if not cursor.fetchone():
        return FragilityStatusResponse(
            investigation_id=investigation_id,
            has_result=False,
            is_indeterminate=True,
            indeterminate_reason=f"Investigation {investigation_id} does not exist.",
        )

    # 2. Check Decision Contract (Component 03)
    cursor.execute("SELECT id FROM decision_contracts WHERE investigation_id = ?;", (investigation_id,))
    c_row = cursor.fetchone()
    if not c_row:
        return FragilityStatusResponse(
            investigation_id=investigation_id,
            has_result=False,
            is_indeterminate=True,
            classification="INDETERMINATE",
            indeterminate_reason="Missing Decision Contract (Component 03). Decision contract must be compiled before fragility evaluation.",
        )
    contract_id = c_row["id"]

    # 3. Check Contract Requirements
    cursor.execute("SELECT id FROM contract_requirements WHERE contract_id = ?;", (contract_id,))
    reqs = cursor.fetchall()
    if not reqs:
        return FragilityStatusResponse(
            investigation_id=investigation_id,
            has_result=False,
            is_indeterminate=True,
            classification="INDETERMINATE",
            indeterminate_reason="No Contract Requirements defined. Requirements are required to assess fragility.",
        )

    # 4. Check Evidence Sufficiency Assessments (Component 06)
    cursor.execute("SELECT requirement_id FROM evidence_sufficiency_assessments WHERE investigation_id = ?;", (investigation_id,))
    suff = cursor.fetchall()
    if not suff:
        return FragilityStatusResponse(
            investigation_id=investigation_id,
            has_result=False,
            is_indeterminate=True,
            classification="INDETERMINATE",
            indeterminate_reason="Evidence Sufficiency analysis not yet executed. Click 'Run Fragility Analysis Now' to evaluate baseline sufficiency and compute the Fragility Index.",
        )

    # 5. Check Latest Fragility Evaluation
    cursor.execute("""
        SELECT r.*, run.input_fingerprint
        FROM decision_fragility_results r
        JOIN decision_fragility_runs run ON r.run_id = run.id
        WHERE r.investigation_id = ?
        ORDER BY r.created_at DESC LIMIT 1;
    """, (investigation_id,))
    latest = cursor.fetchone()

    if not latest:
        return FragilityStatusResponse(
            investigation_id=investigation_id,
            has_result=False,
            is_indeterminate=True,
            classification="INDETERMINATE (NOT_EVALUATED)",
            indeterminate_reason="Fragility evaluation has not yet been executed for this investigation.",
        )

    # 6. Staleness Fingerprint Check
    current_fingerprint = compute_fragility_input_fingerprint(conn, investigation_id)
    is_stale = bool(latest["input_fingerprint"] and latest["input_fingerprint"] != current_fingerprint)

    # Unsubstantiated critical check
    cursor.execute("""
        SELECT cr.id
        FROM contract_requirements cr
        JOIN evidence_sufficiency_assessments esa ON cr.id = esa.requirement_id
        WHERE esa.investigation_id = ? AND cr.priority = 'CRITICAL'
          AND esa.coverage_status IN ('NO_EVIDENCE', 'CONFLICTING', 'INSUFFICIENT', 'PARTIAL');
    """, (investigation_id,))
    has_unsubstantiated = bool(cursor.fetchone())

    if is_stale:
        classification = "INDETERMINATE (STALE UPSTREAM DATA)"
        is_indeterminate = True
        indeterminate_reason = "Upstream evidence, requirements, or assessments have changed since the last fragility analysis. Re-run analysis to refresh."
    else:
        classification = latest["classification"]
        is_indeterminate = False
        indeterminate_reason = None

    return FragilityStatusResponse(
        investigation_id=investigation_id,
        has_result=True,
        latest_run_id=latest["run_id"],
        dfi_score=latest["dfi_score"] if not is_stale else latest["dfi_score"],
        classification=classification,
        is_provisional=bool(latest["is_provisional"]),
        guardrail_active=bool(latest["guardrail_active"]),
        guardrail_reason=latest["guardrail_reason"] if latest["guardrail_reason"] else None,
        has_unsubstantiated_critical=has_unsubstantiated,
        is_stale=is_stale,
        is_indeterminate=is_indeterminate,
        indeterminate_reason=indeterminate_reason,
        created_at=latest["created_at"],
    )


def get_fragility_methodology() -> FragilityMethodologyResponse:
    """
    Returns the formal specification parameters of methodology v1.2.0-deterministic.
    """
    return FragilityMethodologyResponse(
        version=METHODOLOGY_VERSION,
        weights={
            "d1_coverage": WEIGHT_D1,
            "d2_assumptions": WEIGHT_D2,
            "d3_conflicts": WEIGHT_D3,
            "d4_stress": WEIGHT_D4,
            "d5_concentration": WEIGHT_D5,
        },
        deficit_penalties=DEFICIT_PENALTIES,
        conflict_penalties=CONFLICT_SEVERITY_PENALTIES,
        stress_shift_penalties=STRESS_SHIFT_PENALTIES,
        guardrail_criteria="If ANY requirement with priority CRITICAL has sufficiency status NO_EVIDENCE or CONFLICTING, the score classification is unconditionally overridden to 'CRITICAL DEFICIT GUARDRAIL: UNGROUNDED FOUNDATION'.",
        provisional_policy="If Component 05 (conflicts) or Component 07 (stress tests) has not been run, the dimension is marked NOT_ASSESSED, and any score <= 25.0 is classified as 'MODERATE FRAGILITY (PROVISIONAL - INCOMPLETE COVERAGE)'.",
        rounding_rule="ROUND_HALF_UP to 1 decimal place via Python Decimal.",
        epistemic_disclaimer="Decision Fragility Index scores and sensitivity projections quantify empirical support and structural sensitivity within the ingested evidence boundary. Stable stress-test outcomes indicate lack of degradation in tested scenarios, not real-world resilience.",
    )
