import os
import json
import uuid
import datetime
import logging
from typing import Dict, Any, List, Optional, Tuple

from backend.models import (
    SensitivitySimulationRequest,
    SensitivityExperimentResult,
    SensitivityAnalysisResponse,
    EvidenceImprovementRecommendationItem,
    FragilityRecommendationsResponse,
)
from backend.services.fragility_service import (
    compute_d1_coverage_fragility,
    compute_d2_assumption_fragility,
    compute_d3_conflict_fragility,
    compute_d4_stress_fragility,
    compute_d5_sensitivity_concentration,
    compute_composite_dfi,
    get_latest_fragility_result,
    execute_fragility_analysis,
    round_score,
)

logger = logging.getLogger(__name__)


def _fetch_investigation_state_in_memory(conn, investigation_id: str):
    """
    Fetches an isolated in-memory snapshot of all data needed for fragility evaluation.
    This guarantees pure isolation so the counterfactual simulator never modifies the database.
    """
    cursor = conn.cursor()

    # Contract
    cursor.execute("""
        SELECT id, decision_objective FROM decision_contracts WHERE investigation_id = ?;
    """, (investigation_id,))
    c_row = cursor.fetchone()
    if not c_row:
        raise ValueError(f"Investigation {investigation_id} has no compiled contract.")
    contract_id = c_row["id"]
    objective = c_row["decision_objective"] or ""

    # Requirements
    cursor.execute("""
        SELECT id, title, priority, verification_criteria
        FROM contract_requirements WHERE contract_id = ?
        ORDER BY sort_order ASC, id ASC;
    """, (contract_id,))
    requirements = [dict(r) for r in cursor.fetchall()]

    # Sufficiency
    cursor.execute("""
        SELECT requirement_id, coverage_status, confidence
        FROM evidence_sufficiency_assessments WHERE investigation_id = ?;
    """, (investigation_id,))
    sufficiency_map = {r["requirement_id"]: dict(r) for r in cursor.fetchall()}

    # Assumptions
    cursor.execute("""
        SELECT id, description, confidence, validation_status
        FROM contract_assumptions WHERE contract_id = ? ORDER BY id ASC;
    """, (contract_id,))
    assumptions = [dict(r) for r in cursor.fetchall()]

    # Conflicts
    cursor.execute("SELECT id FROM evidence_conflict_runs WHERE investigation_id = ?;", (investigation_id,))
    has_conflict_run = bool(cursor.fetchone())
    cursor.execute("""
        SELECT id, severity, resolution_status, explanation
        FROM evidence_conflicts WHERE investigation_id = ? ORDER BY id ASC;
    """, (investigation_id,))
    conflicts = [dict(r) for r in cursor.fetchall()]

    # Stress Evals
    cursor.execute("SELECT id FROM decision_stress_runs WHERE investigation_id = ?;", (investigation_id,))
    has_stress_run = bool(cursor.fetchone())
    cursor.execute("""
        SELECT se.scenario_id, se.outcome_shift, se.scenario_overall_outcome, ss.severity, ss.title
        FROM decision_stress_evaluations se
        JOIN decision_stress_scenarios ss ON se.scenario_id = ss.id
        WHERE se.investigation_id = ? ORDER BY se.scenario_id ASC;
    """, (investigation_id,))
    stress_evals = [dict(r) for r in cursor.fetchall()]

    return (
        contract_id,
        objective,
        requirements,
        sufficiency_map,
        assumptions,
        conflicts,
        has_conflict_run,
        stress_evals,
        has_stress_run,
    )


def _evaluate_state_in_memory(
    requirements: List[Dict[str, Any]],
    sufficiency_map: Dict[str, Dict[str, Any]],
    assumptions: List[Dict[str, Any]],
    conflicts: List[Dict[str, Any]],
    has_conflict_run: bool,
    stress_evals: List[Dict[str, Any]],
    has_stress_run: bool,
) -> Tuple[float, str, bool, Optional[str]]:
    """
    Evaluates in-memory data structures using the exact v1.2.0-deterministic formula.
    Returns: (dfi_score, classification, guardrail_active, guardrail_reason)
    """
    d1, _, _ = compute_d1_coverage_fragility(requirements, sufficiency_map)
    d2, d2_status, _, _ = compute_d2_assumption_fragility(assumptions)
    d3, d3_status, _ = compute_d3_conflict_fragility(conflicts, has_conflict_run)
    d4, d4_status, _, _ = compute_d4_stress_fragility(stress_evals, has_stress_run)
    d5, d5_status, _, _ = compute_d5_sensitivity_concentration(requirements, sufficiency_map)

    dfi, classification, is_prov, _, guardrail_active, guardrail_reason = compute_composite_dfi(
        d1, d2, d3, d4, d5,
        "ASSESSED", d2_status, d3_status, d4_status, d5_status,
        requirements, sufficiency_map
    )

    return dfi, classification, guardrail_active, guardrail_reason


def simulate_sensitivity_experiment(
    conn,
    investigation_id: str,
    request: SensitivitySimulationRequest
) -> SensitivityExperimentResult:
    """
    Executes a counterfactual sensitivity simulation strictly in-memory.
    Persists ONLY the hypothetical experiment record, leaving primary evidence tables unchanged.
    """
    # 1. Fetch Baseline
    latest = get_latest_fragility_result(conn, investigation_id)
    if not latest:
        latest = execute_fragility_analysis(conn, investigation_id, allow_gemini=False)

    baseline_dfi = latest.dfi_score
    baseline_classification = latest.classification

    # 2. Fetch in-memory copies
    (
        contract_id,
        objective,
        requirements,
        sufficiency_map,
        assumptions,
        conflicts,
        has_conflict_run,
        stress_evals,
        has_stress_run,
    ) = _fetch_investigation_state_in_memory(conn, investigation_id)

    # Deep copy / clone dictionaries for safe mutation
    sim_requirements = [dict(r) for r in requirements]
    sim_sufficiency_map = {k: dict(v) for k, v in sufficiency_map.items()}
    sim_assumptions = [dict(a) for a in assumptions]
    sim_conflicts = [dict(c) for c in conflicts]
    sim_stress_evals = [dict(s) for s in stress_evals]

    target_title = request.target_entity_id
    narrative_impact = ""

    # 3. Apply Counterfactual Mutation
    exp_type = request.experiment_type.upper()

    if exp_type == "SIM_EVIDENCE_WEAKENING":
        # Target is requirement; simulate worsening of evidence
        new_status = request.hypothetical_parameters.get("target_status", "NO_EVIDENCE")
        r_id = request.target_entity_id
        req_obj = next((r for r in sim_requirements if r["id"] == r_id), None)
        if req_obj:
            target_title = req_obj.get("title", r_id)
        if r_id in sim_sufficiency_map:
            old_status = sim_sufficiency_map[r_id].get("coverage_status", "UNKNOWN")
            sim_sufficiency_map[r_id]["coverage_status"] = new_status
            narrative_impact = f"Simulated evidentiary weakening of requirement '{target_title}' from {old_status} to {new_status}."
        else:
            sim_sufficiency_map[r_id] = {"coverage_status": new_status, "confidence": 0.0}
            narrative_impact = f"Simulated evidentiary loss on requirement '{target_title}' to {new_status}."

    elif exp_type == "SIM_GAP_CORROBORATION":
        # Target is requirement; simulate closing of evidence gap
        r_id = request.target_entity_id
        req_obj = next((r for r in sim_requirements if r["id"] == r_id), None)
        if req_obj:
            target_title = req_obj.get("title", r_id)
        old_status = sim_sufficiency_map.get(r_id, {}).get("coverage_status", "UNKNOWN")
        sim_sufficiency_map[r_id] = {"coverage_status": "SUFFICIENT", "confidence": 0.95}
        narrative_impact = f"Simulated corroborating evidence for requirement '{target_title}', advancing coverage from {old_status} to SUFFICIENT."

    elif exp_type == "SIM_CONFLICT_RESOLUTION":
        # Target is conflict; simulate resolution
        c_id = request.target_entity_id
        conf_obj = next((c for c in sim_conflicts if c["id"] == c_id), None)
        if conf_obj:
            target_title = conf_obj.get("title") or conf_obj.get("explanation") or c_id
            conf_obj["resolution_status"] = request.hypothetical_parameters.get("resolution_status", "resolved_claim_a")
            narrative_impact = f"Simulated resolution of conflict '{target_title}' to status '{conf_obj['resolution_status']}'."

    elif exp_type == "SIM_ASSUMPTION_FAILURE":
        # Target is assumption; simulate assumption invalidation
        a_id = request.target_entity_id
        assump_obj = next((a for a in sim_assumptions if a["id"] == a_id), None)
        if assump_obj:
            target_title = assump_obj.get("description", a_id)
            assump_obj["validation_status"] = "invalidated"
            narrative_impact = f"Simulated assumption failure: assumption '{target_title}' is marked invalidated."

    else:
        raise ValueError(f"Unknown experiment type: {exp_type}")

    # 4. Compute Simulated DFI
    sim_dfi, sim_class, sim_guardrail, sim_guardrail_reason = _evaluate_state_in_memory(
        sim_requirements,
        sim_sufficiency_map,
        sim_assumptions,
        sim_conflicts,
        has_conflict_run,
        sim_stress_evals,
        has_stress_run,
    )

    delta_dfi = round_score(sim_dfi - baseline_dfi)

    if delta_dfi > 0:
        narrative_impact += f" Fragility increased by +{delta_dfi:.1f} points (from {baseline_dfi:.1f} to {sim_dfi:.1f})."
    elif delta_dfi < 0:
        narrative_impact += f" Fragility decreased by {abs(delta_dfi):.1f} points (from {baseline_dfi:.1f} to {sim_dfi:.1f})."
    else:
        narrative_impact += f" Fragility remained unchanged at {sim_dfi:.1f} points."

    if sim_guardrail and not latest.guardrail_active:
        narrative_impact += " Critical Deficit Guardrail was triggered in this simulation!"

    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    exp_id = str(uuid.uuid4())

    # 5. Persist simulation experiment (without touching primary tables)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO decision_sensitivity_experiments (
            id, investigation_id, experiment_type, is_hypothetical, target_entity_id, target_entity_type,
            baseline_dfi, simulated_dfi, delta_dfi, baseline_classification, simulated_classification,
            simulation_parameters_json, narrative_impact, created_at
        ) VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, (
        exp_id, investigation_id, exp_type, request.target_entity_id, request.target_entity_type,
        baseline_dfi, sim_dfi, delta_dfi, baseline_classification, sim_class,
        json.dumps(request.hypothetical_parameters), narrative_impact, now_iso
    ))
    conn.commit()

    return SensitivityExperimentResult(
        id=exp_id,
        investigation_id=investigation_id,
        experiment_type=exp_type,
        is_hypothetical=True,
        target_entity_id=request.target_entity_id,
        target_entity_type=request.target_entity_type,
        target_entity_title=target_title,
        baseline_dfi=baseline_dfi,
        simulated_dfi=sim_dfi,
        delta_dfi=delta_dfi,
        baseline_classification=baseline_classification,
        simulated_classification=sim_class,
        simulated_guardrail_active=sim_guardrail,
        simulated_guardrail_reason=sim_guardrail_reason,
        simulation_parameters=request.hypothetical_parameters,
        narrative_impact=narrative_impact,
        created_at=now_iso,
    )


def list_sensitivity_experiments(conn, investigation_id: str) -> List[SensitivityExperimentResult]:
    """
    Returns all sensitivity simulation experiments conducted for an investigation.
    """
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM decision_sensitivity_experiments
        WHERE investigation_id = ?
        ORDER BY created_at DESC;
    """, (investigation_id,))
    rows = cursor.fetchall()

    results = []
    for r in rows:
        d = dict(r)
        results.append(SensitivityExperimentResult(
            id=d["id"],
            investigation_id=d["investigation_id"],
            experiment_type=d["experiment_type"],
            is_hypothetical=bool(d["is_hypothetical"]),
            target_entity_id=d["target_entity_id"] or "",
            target_entity_type=d["target_entity_type"] or "",
            target_entity_title=d["target_entity_id"] or "",
            baseline_dfi=d["baseline_dfi"],
            simulated_dfi=d["simulated_dfi"],
            delta_dfi=d["delta_dfi"],
            baseline_classification=d["baseline_classification"],
            simulated_classification=d["simulated_classification"],
            simulated_guardrail_active=False,
            simulated_guardrail_reason=None,
            simulation_parameters=json.loads(d["simulation_parameters_json"]) if d["simulation_parameters_json"] else {},
            narrative_impact=d["narrative_impact"] or "",
            created_at=d["created_at"],
        ))
    return results


def generate_fragility_recommendations(
    conn,
    investigation_id: str
) -> FragilityRecommendationsResponse:
    """
    Generates actionable, prioritized evidence improvement recommendations.
    Uses in-memory simulations to calculate exact projected DFI reduction for each action.
    Ranks recommendations by projected reduction DESC.
    """
    latest = get_latest_fragility_result(conn, investigation_id)
    if not latest:
        latest = execute_fragility_analysis(conn, investigation_id, allow_gemini=False)

    baseline_dfi = latest.dfi_score

    (
        contract_id,
        objective,
        requirements,
        sufficiency_map,
        assumptions,
        conflicts,
        has_conflict_run,
        stress_evals,
        has_stress_run,
    ) = _fetch_investigation_state_in_memory(conn, investigation_id)

    recommendations = []
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # 1. Actionable Conflict Resolutions
    for c in conflicts:
        c_status = str(c.get("resolution_status", "unresolved")).lower()
        if c_status in ("unresolved", "under_review"):
            c_id = c["id"]
            sev = str(c.get("severity", "MEDIUM")).upper()

            # Simulate resolution
            sim_conflicts = [dict(x) for x in conflicts]
            target_c = next((x for x in sim_conflicts if x["id"] == c_id), None)
            if target_c:
                target_c["resolution_status"] = "resolved_claim_a"

            sim_dfi, _, _, _ = _evaluate_state_in_memory(
                requirements, sufficiency_map, assumptions, sim_conflicts,
                has_conflict_run, stress_evals, has_stress_run
            )
            reduction = round_score(max(0.0, baseline_dfi - sim_dfi))
            c_title = c.get("title") or c.get("explanation") or f"Conflict {c_id[:8]}"
            if len(c_title) > 60:
                c_title = c_title[:57] + "..."

            priority = "HIGH" if (reduction >= 5.0 or sev == "CRITICAL") else ("MEDIUM" if reduction >= 2.0 else "LOW")
            effort = "LOW" if sev == "LOW" else ("MEDIUM" if sev == "MEDIUM" else "HIGH")

            recommendations.append(EvidenceImprovementRecommendationItem(
                id=str(uuid.uuid4()),
                investigation_id=investigation_id,
                run_id=latest.run_id,
                recommendation_type="RESOLVE_CONFLICT",
                target_entity_id=c_id,
                target_entity_type="conflict",
                title=f"Resolve {sev} Conflict: {c_title}",
                description=f"Formally adjudicate contradictory claims in conflict '{c_title}'. Reduces conflict penalty and stabilizes downstream sufficiency.",
                projected_dfi_reduction=reduction,
                is_hypothetical_projection=True,
                priority=priority,
                effort_estimate=effort,
                action_steps=[
                    "Inspect both contradictory claims and source publication metadata in Evidence Explorer.",
                    "Determine whether temporal shift, methodological disparity, or source bias explains the discrepancy.",
                    "Record adjudication decision (dismissal, selective adoption, or context qualification) in Conflict Engine."
                ],
                created_at=now_iso,
            ))

    # 2. Actionable Assumption Verifications
    for a in assumptions:
        a_status = str(a.get("validation_status", "unvalidated")).lower()
        if a_status in ("unvalidated", "invalidated", "partially_validated"):
            a_id = a["id"]
            a_desc = a.get("description", f"Assumption {a_id[:8]}")
            if len(a_desc) > 60:
                a_desc = a_desc[:57] + "..."

            # Simulate validation
            sim_assumptions = [dict(x) for x in assumptions]
            target_a = next((x for x in sim_assumptions if x["id"] == a_id), None)
            if target_a:
                target_a["validation_status"] = "validated"

            sim_dfi, _, _, _ = _evaluate_state_in_memory(
                requirements, sufficiency_map, sim_assumptions, conflicts,
                has_conflict_run, stress_evals, has_stress_run
            )
            reduction = round_score(max(0.0, baseline_dfi - sim_dfi))
            priority = "HIGH" if reduction >= 4.0 else ("MEDIUM" if reduction >= 1.5 else "LOW")

            recommendations.append(EvidenceImprovementRecommendationItem(
                id=str(uuid.uuid4()),
                investigation_id=investigation_id,
                run_id=latest.run_id,
                recommendation_type="VERIFY_ASSUMPTION",
                target_entity_id=a_id,
                target_entity_type="assumption",
                title=f"Validate Assumption: {a_desc}",
                description=f"Gather primary empirical documentation to validate '{a_desc}', eliminating assumption uncertainty penalty.",
                projected_dfi_reduction=reduction,
                is_hypothetical_projection=True,
                priority=priority,
                effort_estimate="MEDIUM",
                action_steps=[
                    "Retrieve official regulatory filings or verified empirical reports addressing this assumption.",
                    "Extract supporting claims into the investigation repository.",
                    "Update assumption status to validated in the Decision Contract."
                ],
                created_at=now_iso,
            ))

    # 3. Actionable Evidence Gap Corroborations
    for req in requirements:
        r_id = req["id"]
        priority_str = req.get("priority", "MEDIUM").upper()
        suff = sufficiency_map.get(r_id, {})
        cov_status = suff.get("coverage_status", "NO_EVIDENCE")

        if cov_status in ("NO_EVIDENCE", "INSUFFICIENT", "PARTIAL", "CONFLICTING"):
            r_title = req.get("title", f"Requirement {r_id[:8]}")
            if len(r_title) > 60:
                r_title = r_title[:57] + "..."

            # Simulate corroboration to SUFFICIENT
            sim_suff = {k: dict(v) for k, v in sufficiency_map.items()}
            sim_suff[r_id] = {"coverage_status": "SUFFICIENT", "confidence": 0.95}

            sim_dfi, _, _, _ = _evaluate_state_in_memory(
                requirements, sim_suff, assumptions, conflicts,
                has_conflict_run, stress_evals, has_stress_run
            )
            reduction = round_score(max(0.0, baseline_dfi - sim_dfi))
            is_crit = (priority_str == "CRITICAL")
            rec_priority = "HIGH" if (is_crit or reduction >= 5.0) else ("MEDIUM" if reduction >= 2.0 else "LOW")
            rec_type = "FILL_CRITICAL_GAP" if is_crit else "CORROBORATE_EVIDENCE"

            recommendations.append(EvidenceImprovementRecommendationItem(
                id=str(uuid.uuid4()),
                investigation_id=investigation_id,
                run_id=latest.run_id,
                recommendation_type=rec_type,
                target_entity_id=r_id,
                target_entity_type="requirement",
                title=f"{'Fill Critical Gap' if is_crit else 'Corroborate'}: {r_title}",
                description=f"Ingest independent secondary evidence to substantiate '{r_title}' (Current: {cov_status}).",
                projected_dfi_reduction=reduction,
                is_hypothetical_projection=True,
                priority=rec_priority,
                effort_estimate="HIGH" if is_crit else "MEDIUM",
                action_steps=[
                    f"Search and ingest multi-source publications matching verification criteria: '{req.get('verification_criteria', '')[:80]}'.",
                    "Extract factual claims and link them to this requirement via Evidence Explorer.",
                    "Re-run Sufficiency Engine to achieve SUFFICIENT status."
                ],
                created_at=now_iso,
            ))

    # Sort recommendations by projected DFI reduction DESC
    recommendations.sort(key=lambda x: (x.projected_dfi_reduction, 1 if x.priority == "HIGH" else 0), reverse=True)

    # Persist into decision_fragility_recommendations
    cursor = conn.cursor()
    cursor.execute("DELETE FROM decision_fragility_recommendations WHERE investigation_id = ?;", (investigation_id,))
    for rec in recommendations:
        cursor.execute("""
            INSERT INTO decision_fragility_recommendations (
                id, investigation_id, run_id, recommendation_type, target_entity_id, target_entity_type,
                title, description, projected_dfi_reduction, is_hypothetical_projection, priority, effort_estimate,
                action_steps_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?);
        """, (
            rec.id, investigation_id, rec.run_id, rec.recommendation_type, rec.target_entity_id, rec.target_entity_type,
            rec.title, rec.description, rec.projected_dfi_reduction, rec.priority, rec.effort_estimate,
            json.dumps(rec.action_steps), rec.created_at
        ))
    conn.commit()

    max_red = recommendations[0].projected_dfi_reduction if recommendations else 0.0

    return FragilityRecommendationsResponse(
        investigation_id=investigation_id,
        total_recommendations=len(recommendations),
        max_projected_reduction=max_red,
        recommendations=recommendations,
    )
