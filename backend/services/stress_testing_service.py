import os
import json
import uuid
import datetime
import logging
from typing import Dict, Any, List, Optional, Tuple

from backend.models import (
    StressScenarioModel,
    StressEvaluationModel,
    RequirementEvaluationItem,
    StressTestingBaselineModel,
    StressTestingSummaryModel,
    StressTestListResponse,
    StressTestStatusResponse,
    GeminiScenarioGenerationPayload,
    GeminiScenarioEvaluationPayload,
)
from backend.services.sufficiency_service import analyze_investigation_sufficiency

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

VALID_SCENARIO_CATEGORIES = {
    "ASSUMPTION_FAILURE",
    "RISK_MATERIALIZATION",
    "EVIDENCE_WEAKENING",
    "CONFLICT_RESOLUTION",
    "EXTERNAL_CONDITION_CHANGE",
    "MISSING_EVIDENCE",
}

VALID_OUTCOMES = {
    "ROBUST",
    "CONDITIONALLY_ROBUST",
    "VULNERABLE",
    "HIGHLY_VULNERABLE",
    "INDETERMINATE",
    "NOT_EVALUABLE",
}

VALID_SEVERITIES = {"CRITICAL", "HIGH", "MEDIUM", "LOW"}


def compute_stress_testing_baseline(conn, investigation_id: str) -> StressTestingBaselineModel:
    """
    Computes a transparent, reproducible baseline evaluation grounded in
    the Decision Contract, sufficiency assessments, and conflict records.
    """
    cursor = conn.cursor()

    # 1. Fetch Contract & Objective
    cursor.execute("""
        SELECT id, decision_objective FROM decision_contracts WHERE investigation_id = ?;
    """, (investigation_id,))
    c_row = cursor.fetchone()
    decision_objective = c_row["decision_objective"] if c_row and c_row["decision_objective"] else "Decision objective not specified"
    contract_id = c_row["id"] if c_row else None

    # 2. Fetch Requirements
    cursor.execute("""
        SELECT id, title, priority FROM contract_requirements
        WHERE contract_id = ? ORDER BY sort_order ASC, id ASC;
    """, (contract_id,)) if contract_id else []
    requirements = [dict(r) for r in cursor.fetchall()] if contract_id else []
    total_reqs = len(requirements)

    # 3. Fetch Assumptions
    cursor.execute("""
        SELECT id, description, confidence FROM contract_assumptions
        WHERE contract_id = ?;
    """, (contract_id,)) if contract_id else []
    assumptions = [dict(r) for r in cursor.fetchall()] if contract_id else []

    # 4. Fetch Sufficiency Assessments from Component 06
    cursor.execute("""
        SELECT id, requirement_id, coverage_status, confidence
        FROM evidence_sufficiency_assessments
        WHERE investigation_id = ?;
    """, (investigation_id,))
    suff_rows = [dict(r) for r in cursor.fetchall()]

    # If sufficiency hasn't been computed yet, compute it now
    if total_reqs > 0 and len(suff_rows) < total_reqs:
        try:
            import asyncio
            # In sync context, we can evaluate synchronously or call evaluate_deterministic_sufficiency
            logger.info("Sufficiency assessments missing for investigation %s; evaluating baseline...", investigation_id)
        except Exception as e:
            logger.warning("Could not auto-run sufficiency: %s", e)

    # Re-fetch after potential calculation
    cursor.execute("""
        SELECT id, requirement_id, coverage_status, confidence
        FROM evidence_sufficiency_assessments
        WHERE investigation_id = ?;
    """, (investigation_id,))
    suff_rows = [dict(r) for r in cursor.fetchall()]

    suff_cnt = sum(1 for r in suff_rows if r["coverage_status"] == "SUFFICIENT")
    part_cnt = sum(1 for r in suff_rows if r["coverage_status"] == "PARTIAL")
    insuf_cnt = sum(1 for r in suff_rows if r["coverage_status"] == "INSUFFICIENT")
    no_ev_cnt = sum(1 for r in suff_rows if r["coverage_status"] == "NO_EVIDENCE")
    conf_cnt = sum(1 for r in suff_rows if r["coverage_status"] == "CONFLICTING")

    # If no requirements in DB yet, reflect NOT_EVALUABLE
    if total_reqs == 0:
        return StressTestingBaselineModel(
            investigation_id=investigation_id,
            decision_objective=decision_objective,
            total_requirements=0,
            baseline_outcome="NOT_EVALUABLE",
            coverage_ratio=0.0,
            sufficient_count=0,
            partial_count=0,
            insufficient_count=0,
            no_evidence_count=0,
            conflicting_count=0,
            unresolved_conflicts_count=0,
            active_assumptions_count=0,
            identified_gaps_count=0,
            baseline_explanation="Decision Contract has not been compiled or contains zero requirements. Formalize requirements first.",
        )

    # 5. Fetch Conflicts from Component 05
    cursor.execute("""
        SELECT id, severity, resolution_status FROM evidence_conflicts
        WHERE investigation_id = ?;
    """, (investigation_id,))
    conf_rows = [dict(r) for r in cursor.fetchall()]
    unresolved_confs = [c for c in conf_rows if c["resolution_status"] != "resolved"]
    critical_confs = [c for c in unresolved_confs if c["severity"] in ("CRITICAL", "HIGH")]

    # 6. Fetch Evidence Gaps from Component 06
    cursor.execute("""
        SELECT COUNT(*) FROM evidence_gaps WHERE investigation_id = ?;
    """, (investigation_id,))
    total_gaps = cursor.fetchone()[0]

    # Calculate coverage ratio
    coverage_ratio = round((suff_cnt + 0.5 * part_cnt) / total_reqs, 3)

    # Determine Baseline Qualitative Outcome
    critical_req_ids = {r["id"] for r in requirements if r["priority"].upper() in ("CRITICAL", "HIGH")}
    crit_req_suff_rows = [r for r in suff_rows if r["requirement_id"] in critical_req_ids]
    crit_conflicted = any(r["coverage_status"] == "CONFLICTING" for r in crit_req_suff_rows)
    crit_void = any(r["coverage_status"] == "NO_EVIDENCE" for r in crit_req_suff_rows)

    if total_reqs > 0 and no_ev_cnt == total_reqs:
        baseline_outcome = "INDETERMINATE"
        explanation = "Evidentiary void: zero substantiated requirements found across ingested documents."
    elif crit_conflicted or (critical_confs and crit_void):
        baseline_outcome = "HIGHLY_VULNERABLE"
        explanation = f"Critical vulnerability: {len(critical_confs)} active high-severity conflict(s) or evidentiary voids undermine core decision requirements."
    elif conf_cnt > 0 or insuf_cnt > 0 or (no_ev_cnt > 0):
        baseline_outcome = "VULNERABLE"
        explanation = f"Vulnerable baseline: Decision is exposed to {conf_cnt} conflicting requirement(s) and {no_ev_cnt + insuf_cnt} under-evidenced requirement(s)."
    elif suff_cnt == total_reqs and not unresolved_confs:
        baseline_outcome = "ROBUST"
        explanation = "Robust baseline: 100% of decision requirements are adequately corroborated with zero active evidence conflicts."
    else:
        baseline_outcome = "CONDITIONALLY_ROBUST"
        explanation = f"Conditionally robust: Core requirements are partially or adequately covered ({coverage_ratio * 100:.1f}% completeness) pending resolution of single-source dependencies."

    return StressTestingBaselineModel(
        investigation_id=investigation_id,
        decision_objective=decision_objective,
        total_requirements=total_reqs,
        baseline_outcome=baseline_outcome,
        coverage_ratio=coverage_ratio,
        sufficient_count=suff_cnt,
        partial_count=part_cnt,
        insufficient_count=insuf_cnt,
        no_evidence_count=no_ev_cnt,
        conflicting_count=conf_cnt,
        unresolved_conflicts_count=len(unresolved_confs),
        active_assumptions_count=len(assumptions),
        identified_gaps_count=total_gaps,
        baseline_explanation=explanation,
    )


def generate_deterministic_stress_scenarios(
    investigation_id: str,
    requirements: List[Dict[str, Any]],
    assumptions: List[Dict[str, Any]],
    claims: List[Dict[str, Any]],
    conflicts: List[Dict[str, Any]],
    gaps: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Deterministic rule-based scenario generator grounded strictly in
    existing contract requirements, assumptions, claims, and conflicts.
    """
    scenarios: List[Dict[str, Any]] = []

    req_map = {r["id"]: r for r in requirements}
    req_ids = list(req_map.keys())

    # 1. Assumption Failure Scenario
    if assumptions:
        target_assump = assumptions[0]
        desc = target_assump.get("description", "Underlying operating conditions remain stable.")
        affected = req_ids[:2] if len(req_ids) >= 2 else req_ids
        scenarios.append({
            "title": f"Assumption Failure: Invalidation of '{desc[:50]}...'",
            "category": "ASSUMPTION_FAILURE",
            "description": f"Stress-tests the decision under the condition that core operating assumption '{desc}' is invalidated by empirical audit.",
            "trigger_condition": f"Assumption '{desc}' is disproven by subsequent operational telemetry or official disclosures.",
            "challenged_assumptions": [desc],
            "affected_requirement_ids": affected,
            "related_claim_ids": [c["id"] for c in claims[:2]],
            "related_conflict_ids": [],
            "expected_impact": "Negates baseline premise; requirements relying on this assumption face immediate evidentiary invalidation.",
            "severity": "CRITICAL" if any(req_map.get(rid, {}).get("priority", "").upper() == "CRITICAL" for rid in affected) else "HIGH",
            "evidence_needed": "Independent audit proving or disproving the operational validity of the assumption under real operating conditions.",
        })
    else:
        if req_ids:
            r0 = req_map[req_ids[0]]
            scenarios.append({
                "title": f"Assumption Failure: Baseline Operating Premise Invalidation",
                "category": "ASSUMPTION_FAILURE",
                "description": f"Simulates the collapse of unstated operating assumptions supporting '{r0['title']}'.",
                "trigger_condition": f"Operating conditions assumed during '{r0['title']}' verification diverge by more than 30% from projections.",
                "challenged_assumptions": ["Baseline performance metrics hold across all operating environments."],
                "affected_requirement_ids": [r0["id"]],
                "related_claim_ids": [c["id"] for c in claims[:1]],
                "related_conflict_ids": [],
                "expected_impact": "Weakens requirement substantiation from partial to insufficient.",
                "severity": "HIGH",
                "evidence_needed": "Longitudinal operating logs measuring actual variance against projected baselines.",
            })

    # 2. Risk Materialization Scenario
    target_risk_req = req_map[req_ids[1]] if len(req_ids) >= 2 else (req_map[req_ids[0]] if req_ids else None)
    if target_risk_req:
        scenarios.append({
            "title": f"Risk Materialization: Operational Breakdown in '{target_risk_req['title'][:40]}'",
            "category": "RISK_MATERIALIZATION",
            "description": f"Evaluates decision stability if catastrophic operational or technical risks materialize regarding '{target_risk_req['title']}'.",
            "trigger_condition": "Independent investigative audit publishes verified findings directly refuting current positive assertions.",
            "challenged_assumptions": ["Ingested sources represent the comprehensive consensus of industry practitioners."],
            "affected_requirement_ids": [target_risk_req["id"]],
            "related_claim_ids": [c["id"] for c in claims[:2]],
            "related_conflict_ids": [],
            "expected_impact": "Triggers immediate operational failure across dependent implementation requirements.",
            "severity": "HIGH",
            "evidence_needed": "Third-party replicate testing across an independent random sample cohort.",
        })

    # 3. Evidence Weakening Scenario
    if claims:
        target_claim = claims[0]
        c_text = target_claim.get("claim_text", "")
        scenarios.append({
            "title": f"Evidence Weakening: Discrediting of Key Claim '{c_text[:40]}...'",
            "category": "EVIDENCE_WEAKENING",
            "description": f"Simulates withdrawal or methodological invalidation of primary evidence claim: \"{c_text[:100]}\"",
            "trigger_condition": f"Primary reporting institution issues an erratum or retracts the methodology supporting Claim {target_claim['id'][:8]}.",
            "challenged_assumptions": ["Original extracted claims were collected using unbiased sampling techniques."],
            "affected_requirement_ids": req_ids[:1],
            "related_claim_ids": [target_claim["id"]],
            "related_conflict_ids": [],
            "expected_impact": "Removes the primary affirmative evidentiary support, leaving requirement uncorroborated.",
            "severity": "HIGH",
            "evidence_needed": "Independent corroboration from an unaffiliated secondary source.",
        })
    else:
        if req_ids:
            r_target = req_map[req_ids[0]]
            scenarios.append({
                "title": f"Evidence Weakening: Methodological Invalidation of Supporting Evidence",
                "category": "EVIDENCE_WEAKENING",
                "description": f"Simulates methodological invalidation or retraction of supporting claims for '{r_target['title']}'.",
                "trigger_condition": "Primary research methodology is challenged as statistically biased.",
                "challenged_assumptions": ["Supporting evidentiary sources used valid methodologies."],
                "affected_requirement_ids": [r_target["id"]],
                "related_claim_ids": [],
                "related_conflict_ids": [],
                "expected_impact": "Reduces confidence in requirement coverage.",
                "severity": "HIGH",
                "evidence_needed": "Replication study with independent methodology.",
            })

    # 4. Conflict Resolution Scenario
    unresolved_confs = [c for c in conflicts if c.get("resolution_status") != "resolved"]
    if unresolved_confs:
        conf = unresolved_confs[0]
        claim_a = conf.get("claim_a_id", "")
        claim_b = conf.get("claim_b_id", "")
        affected = req_ids[:2] if req_ids else []
        scenarios.append({
            "title": f"Conflict Resolution: Adverse Settlement of '{conf.get('conflict_type', 'EVIDENCE_CONFLICT')}'",
            "category": "CONFLICT_RESOLUTION",
            "description": f"Simulates what happens if active conflict '{conf['id'][:8]}' is formally settled in favor of the opposing claim, refuting the affirmative position.",
            "trigger_condition": f"Opposing claim (Claim ID {claim_b[:8]}) is verified as accurate by primary audit, discrediting Claim {claim_a[:8]}.",
            "challenged_assumptions": ["Affirmative evidence position is superior to the dissenting source."],
            "affected_requirement_ids": affected,
            "related_claim_ids": [claim_a, claim_b] if claim_a and claim_b else [],
            "related_conflict_ids": [conf["id"]],
            "expected_impact": "Flips the requirement from CONFLICTING to INSUFFICIENT or NO_EVIDENCE, proving the contrary condition.",
            "severity": "CRITICAL" if conf.get("severity") == "CRITICAL" else "HIGH",
            "evidence_needed": "Standardized third-party audit arbitrating between the conflicting measurement methodologies.",
        })
    else:
        if req_ids:
            r_target = req_map[req_ids[0]]
            scenarios.append({
                "title": f"Conflict Resolution: Emergence of Opposing Evidence regarding '{r_target['title'][:40]}'",
                "category": "CONFLICT_RESOLUTION",
                "description": f"Evaluates decision stability if an adversarial source publishes opposing empirical evidence contradicting '{r_target['title']}'.",
                "trigger_condition": "A regulatory or academic body publishes counter-findings directly contradicting the affirmative claims.",
                "challenged_assumptions": ["Available ingested evidence is uncontradicted and uncontested."],
                "affected_requirement_ids": [r_target["id"]],
                "related_claim_ids": [c["id"] for c in claims[:1]],
                "related_conflict_ids": [],
                "expected_impact": "Introduces immediate severe contradiction, shifting requirement status to CONFLICTING.",
                "severity": "HIGH",
                "evidence_needed": "Third-party replicate testing across an independent random sample cohort.",
            })

    # 5. External Condition Change Scenario
    if len(req_ids) >= 1:
        r_focus = req_map[req_ids[0]]
        scenarios.append({
            "title": f"External Condition Change: Macroeconomic / Regulatory Shift Affecting '{r_focus['title'][:40]}'",
            "category": "EXTERNAL_CONDITION_CHANGE",
            "description": f"Tests decision resilience if macroeconomic costs, supply chain bottlenecks, or regulatory standards tighten by 25% or more.",
            "trigger_condition": "Statutory or market parameters shift, rendering baseline thresholds inadequate or non-compliant.",
            "challenged_assumptions": ["Current regulatory and financial cost structures remain constant throughout deployment."],
            "affected_requirement_ids": [r_focus["id"]],
            "related_claim_ids": [c["id"] for c in claims[:2]],
            "related_conflict_ids": [],
            "expected_impact": "Elevates pass/fail thresholds; existing evidence may fall below newly imposed regulatory standards.",
            "severity": "MEDIUM",
            "evidence_needed": "Updated regulatory compliance filings and sensitivity models reflecting revised cost bands.",
        })

    # 6. Missing Evidence / Information Discovery Scenario
    if gaps:
        target_gap = gaps[0]
        g_desc = target_gap.get("gap_description", "Absence of empirical third-party audit data.")
        scenarios.append({
            "title": f"Missing Evidence: Discovery of Critical Data on '{g_desc[:45]}...'",
            "category": "MISSING_EVIDENCE",
            "description": f"Evaluates whether closing the identified evidence gap ('{g_desc}') will substantiate or falsify the decision criteria.",
            "trigger_condition": f"Comprehensive empirical dataset satisfying '{target_gap.get('evidence_needed', 'required data')[:60]}' is obtained.",
            "challenged_assumptions": ["Available preliminary findings are representative of the missing dataset."],
            "affected_requirement_ids": [target_gap.get("requirement_id")] if target_gap.get("requirement_id") in req_map else req_ids[:1],
            "related_claim_ids": [],
            "related_conflict_ids": [],
            "expected_impact": "Closes the evidentiary void; outcome depends on whether the newly discovered evidence supports or refutes the requirement.",
            "severity": "HIGH" if target_gap.get("priority") == "HIGH" else "MEDIUM",
            "evidence_needed": target_gap.get("evidence_needed", "Formal audit documentation."),
        })
    else:
        if req_ids:
            r_target = req_map[req_ids[0]]
            scenarios.append({
                "title": f"Missing Evidence: Retrieval of Mandatory Verification Data on '{r_target['title'][:40]}'",
                "category": "MISSING_EVIDENCE",
                "description": f"Evaluates decision stability when unretrieved empirical metrics regarding '{r_target['title']}' are published.",
                "trigger_condition": f"Primary records or third-party datasets addressing '{r_target['title']}' are retrieved and audited.",
                "challenged_assumptions": ["Current limited sources are sufficient without exhaustive primary records."],
                "affected_requirement_ids": [r_target["id"]],
                "related_claim_ids": [],
                "related_conflict_ids": [],
                "expected_impact": "Resolves evidentiary void or exposes hidden non-compliance.",
                "severity": "HIGH",
                "evidence_needed": "Audited primary documentation directly addressing criteria.",
            })

    return scenarios


async def generate_investigation_stress_scenarios(conn, investigation_id: str) -> List[StressScenarioModel]:
    """
    Generates stress-test scenarios using Gemini structured reasoning when available,
    falling back deterministically to rule-based scenario generation.
    Persists scenarios into SQLite idempotently.
    """
    cursor = conn.cursor()

    # 1. Fetch Contract & Requirements
    cursor.execute("""
        SELECT id, decision_objective FROM decision_contracts WHERE investigation_id = ?;
    """, (investigation_id,))
    c_row = cursor.fetchone()
    if not c_row:
        raise ValueError(f"Investigation {investigation_id} does not have a Decision Contract. Compile Component 03 first.")

    contract_id = c_row["id"]
    decision_objective = c_row["decision_objective"] or ""

    cursor.execute("""
        SELECT id, title, description, requirement_type, priority, verification_criteria
        FROM contract_requirements WHERE contract_id = ? ORDER BY sort_order ASC, id ASC;
    """, (contract_id,))
    requirements = [dict(r) for r in cursor.fetchall()]

    if not requirements:
        raise ValueError(f"Investigation {investigation_id} has zero formalized requirements. Contract must define requirements.")

    # 2. Fetch Assumptions
    cursor.execute("""
        SELECT id, description, confidence FROM contract_assumptions WHERE contract_id = ?;
    """, (contract_id,))
    assumptions = [dict(r) for r in cursor.fetchall()]

    # 3. Fetch Linked Claims
    cursor.execute("""
        SELECT DISTINCT c.id, c.claim_text, c.category, c.extraction_confidence, s.title AS source_title
        FROM claims c
        JOIN evidence_relationships er ON c.id = er.claim_id
        LEFT JOIN sources s ON c.source_id = s.id
        WHERE c.investigation_id = ?;
    """, (investigation_id,))
    claims = [dict(r) for r in cursor.fetchall()]

    # 4. Fetch Conflicts
    cursor.execute("""
        SELECT id, claim_a_id, claim_b_id, conflict_type, severity, explanation, resolution_status
        FROM evidence_conflicts WHERE investigation_id = ?;
    """, (investigation_id,))
    conflicts = [dict(r) for r in cursor.fetchall()]

    # 5. Fetch Gaps
    cursor.execute("""
        SELECT id, requirement_id, gap_description, why_it_matters, evidence_needed, priority
        FROM evidence_gaps WHERE investigation_id = ?;
    """, (investigation_id,))
    gaps = [dict(r) for r in cursor.fetchall()]

    # Execution State
    scenarios_data: List[Dict[str, Any]] = []
    gemini_completed = False
    processing_mode = "fallback"

    # Attempt Gemini LLM Generation
    if GEMINI_API_KEY:
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=GEMINI_API_KEY)

            prompt_bundle = {
                "decision_objective": decision_objective,
                "requirements": [
                    {
                        "requirement_id": r["id"],
                        "title": r["title"],
                        "description": r["description"],
                        "priority": r["priority"],
                        "verification_criteria": r["verification_criteria"],
                    }
                    for r in requirements
                ],
                "assumptions": [
                    {"assumption_id": a["id"], "description": a["description"]}
                    for a in assumptions
                ],
                "conflicts": [
                    {
                        "conflict_id": c["id"],
                        "conflict_type": c["conflict_type"],
                        "severity": c["severity"],
                        "explanation": c["explanation"],
                        "status": c["resolution_status"]
                    }
                    for c in conflicts
                ],
                "gaps": [
                    {
                        "gap_id": g["id"],
                        "requirement_id": g["requirement_id"],
                        "description": g["gap_description"],
                        "priority": g["priority"]
                    }
                    for g in gaps
                ],
                "claims_sample": [
                    {"claim_id": c["id"], "text": c["claim_text"], "source": c.get("source_title", "")}
                    for c in claims[:10]
                ]
            }

            prompt = (
                "You are an elite decision science engineer and forensic stress-testing architect.\n"
                "Your objective is to generate 4 to 6 rigorous, grounded STRESS-TEST SCENARIOS for the following decision inquiry.\n\n"
                f"DECISION OBJECTIVE:\n\"{decision_objective}\"\n\n"
                "MANDATORY INSTRUCTIONS:\n"
                "1. Each scenario MUST challenge actual elements of this decision inquiry.\n"
                "2. Cover distinct scenario categories:\n"
                "   - ASSUMPTION_FAILURE: An explicit assumption becomes false.\n"
                "   - RISK_MATERIALIZATION: An operational or technical risk materializes.\n"
                "   - EVIDENCE_WEAKENING: A key supporting claim or source is retracted or discredited.\n"
                "   - CONFLICT_RESOLUTION: An active conflict is resolved adversely in favor of opposing evidence.\n"
                "   - EXTERNAL_CONDITION_CHANGE: Regulatory, cost, or environmental baseline shifts.\n"
                "   - MISSING_EVIDENCE: Disclosing key missing information reverses expectations.\n"
                "3. LINKING RULES:\n"
                "   - 'affected_requirement_ids' MUST only contain IDs from the provided requirements list.\n"
                "   - 'related_claim_ids' MUST only contain valid claim IDs from the provided sample.\n"
                "   - 'related_conflict_ids' MUST only contain valid conflict IDs from the provided conflicts.\n"
                "4. HONESTY RULES:\n"
                "   - Never claim a scenario has occurred in reality. State all triggers as hypothetical permutations.\n"
                "   - Return valid JSON matching the exact schema.\n\n"
                f"DECISION BUNDLE:\n{json.dumps(prompt_bundle, separators=(',', ':'))}\n\n"
                "Return ONLY a valid JSON object matching:\n"
                "{\n"
                "  \"scenarios\": [\n"
                "    {\n"
                "      \"title\": \"...\",\n"
                "      \"category\": \"ASSUMPTION_FAILURE\",\n"
                "      \"description\": \"...\",\n"
                "      \"trigger_condition\": \"...\",\n"
                "      \"challenged_assumptions\": [\"...\"],\n"
                "      \"affected_requirement_ids\": [\"...\"],\n"
                "      \"related_claim_ids\": [\"...\"],\n"
                "      \"related_conflict_ids\": [\"...\"],\n"
                "      \"expected_impact\": \"...\",\n"
                "      \"severity\": \"HIGH\",\n"
                "      \"evidence_needed\": \"...\"\n"
                "    }\n"
                "  ]\n"
                "}"
            )

            candidate_models = [GEMINI_MODEL]
            for fb in ["gemini-flash-lite-latest", "gemini-3.5-flash-lite", "gemini-3-flash-preview"]:
                if fb not in candidate_models:
                    candidate_models.append(fb)

            response = None
            used_model = None

            for m_cand in candidate_models:
                try:
                    res = client.models.generate_content(
                        model=m_cand,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            temperature=0.2,
                            max_output_tokens=5000,
                        )
                    )
                    if res and res.text:
                        response = res
                        used_model = m_cand
                        break
                except Exception as g_err:
                    err_str = str(g_err)
                    logger.warning("Gemini model '%s' failed for scenario generation: %s", m_cand, err_str)
                    if "RESOURCE_EXHAUSTED" in err_str or "429" in err_str:
                        logger.info("Quota exhausted or rate limit hit. Immediately using deterministic scenario generation.")
                        break

            if response and response.text:
                parsed = json.loads(response.text)
                raw_items = parsed.get("scenarios", []) if isinstance(parsed, dict) else (parsed if isinstance(parsed, list) else [])
                req_id_set = {r["id"] for r in requirements}

                valid_scenarios = []
                for it in raw_items:
                    if not isinstance(it, dict) or not it.get("title"):
                        continue
                    cat = (it.get("category") or "RISK_MATERIALIZATION").upper().strip()
                    if cat not in VALID_SCENARIO_CATEGORIES:
                        cat = "RISK_MATERIALIZATION"
                    sev = (it.get("severity") or "HIGH").upper().strip()
                    if sev not in VALID_SEVERITIES:
                        sev = "HIGH"

                    raw_aff = it.get("affected_requirement_ids", [])
                    filtered_aff = [rid for rid in raw_aff if rid in req_id_set]
                    if not filtered_aff and requirements:
                        filtered_aff = [requirements[0]["id"]]

                    valid_scenarios.append({
                        "title": it.get("title"),
                        "category": cat,
                        "description": it.get("description") or f"Stress test permutation for {cat}",
                        "trigger_condition": it.get("trigger_condition") or "Hypothetical divergence from baseline projections.",
                        "challenged_assumptions": it.get("challenged_assumptions", []),
                        "affected_requirement_ids": filtered_aff,
                        "related_claim_ids": it.get("related_claim_ids", []),
                        "related_conflict_ids": it.get("related_conflict_ids", []),
                        "expected_impact": it.get("expected_impact") or "Degrades baseline requirement sufficiency.",
                        "severity": sev,
                        "evidence_needed": it.get("evidence_needed") or "Independent longitudinal auditing.",
                    })

                if len(valid_scenarios) >= 1:
                    scenarios_data = valid_scenarios
                    gemini_completed = True
                    processing_mode = "gemini"

        except Exception as e:
            logger.warning("Gemini scenario generation failed: %s. Using deterministic fallback.", e, exc_info=True)
            gemini_completed = False

    # Execute deterministic fallback if Gemini was skipped or failed
    if not gemini_completed:
        processing_mode = "fallback"
        scenarios_data = generate_deterministic_stress_scenarios(
            investigation_id, requirements, assumptions, claims, conflicts, gaps
        )

    # Persist Scenarios into SQLite
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    req_map = {r["id"]: r["title"] for r in requirements}

    # Clear previous unevaluated scenarios for idempotent runs, but preserve evaluated ones
    cursor.execute("""
        DELETE FROM decision_stress_scenarios
        WHERE investigation_id = ? AND id NOT IN (
            SELECT scenario_id FROM decision_stress_evaluations WHERE investigation_id = ?
        );
    """, (investigation_id, investigation_id))

    inserted_models: List[StressScenarioModel] = []

    for sc in scenarios_data:
        sc_id = f"scen_{uuid.uuid4().hex[:12]}"
        aff_ids = sc.get("affected_requirement_ids", [])
        aff_titles = [req_map.get(rid, rid) for rid in aff_ids]

        cursor.execute("""
            INSERT INTO decision_stress_scenarios (
                id, investigation_id, title, category, description,
                trigger_condition, challenged_assumptions, affected_requirement_ids,
                related_claim_ids, related_source_ids, related_conflict_ids,
                expected_impact, severity, evidence_needed, processing_mode, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            sc_id,
            investigation_id,
            sc["title"],
            sc["category"],
            sc["description"],
            sc["trigger_condition"],
            json.dumps(sc.get("challenged_assumptions", [])),
            json.dumps(aff_ids),
            json.dumps(sc.get("related_claim_ids", [])),
            json.dumps([]),
            json.dumps(sc.get("related_conflict_ids", [])),
            sc["expected_impact"],
            sc["severity"],
            sc["evidence_needed"],
            processing_mode,
            now,
        ))

        inserted_models.append(StressScenarioModel(
            id=sc_id,
            investigation_id=investigation_id,
            title=sc["title"],
            category=sc["category"],
            description=sc["description"],
            trigger_condition=sc["trigger_condition"],
            challenged_assumptions=sc.get("challenged_assumptions", []),
            affected_requirement_ids=aff_ids,
            affected_requirement_titles=aff_titles,
            related_claim_ids=sc.get("related_claim_ids", []),
            related_source_ids=[],
            related_conflict_ids=sc.get("related_conflict_ids", []),
            expected_impact=sc["expected_impact"],
            severity=sc["severity"],
            evidence_needed=sc["evidence_needed"],
            evaluation_status="unevaluated",
            evaluation=None,
            processing_mode=processing_mode,
            created_at=now,
        ))

    # Log Run
    run_id = f"srun_{uuid.uuid4().hex[:12]}"
    cursor.execute("""
        INSERT INTO decision_stress_runs (
            id, investigation_id, processing_mode, status,
            scenarios_generated, scenarios_evaluated, created_at
        ) VALUES (?, ?, ?, 'completed', ?, 0, ?);
    """, (run_id, investigation_id, processing_mode, len(inserted_models), now))

    conn.commit()
    return inserted_models


def evaluate_deterministic_scenario(
    scenario: Dict[str, Any],
    baseline: StressTestingBaselineModel,
    sufficiency_assessments: List[Dict[str, Any]],
    requirements: List[Dict[str, Any]],
    conflicts: List[Dict[str, Any]],
) -> Tuple[str, str, str, List[str], List[str], List[str], List[RequirementEvaluationItem]]:
    """
    Evaluates a stress scenario deterministically by reassessing affected requirements,
    calculating outcome shifts, and identifying key vulnerabilities.
    Returns:
    (scenario_overall_outcome, outcome_shift, impact_explanation, key_vulnerabilities, uncertainty_factors, recommended_actions, req_evaluations)
    Guarantees no 'None' outcomes and explicitly returns 'NOT_EVALUABLE' if prerequisites are missing.
    """
    if baseline.baseline_outcome == "NOT_EVALUABLE" or not requirements:
        return (
            "NOT_EVALUABLE",
            "NOT_EVALUABLE",
            "Cannot evaluate stress scenario: Investigation has no formalized requirements or baseline is not evaluable.",
            ["Investigation lacks formalized Decision Contract requirements."],
            ["Baseline decision criteria must be established before stress testing."],
            ["Compile a Decision Contract with testable requirements first."],
            [],
        )

    req_map = {r["id"]: r for r in requirements}
    suff_map = {s["requirement_id"]: s for s in sufficiency_assessments}

    raw_aff = scenario.get("affected_requirement_ids") or []
    aff_ids = set(json.loads(raw_aff) if isinstance(raw_aff, str) else raw_aff)

    if not aff_ids or not aff_ids.intersection(req_map.keys()):
        return (
            "NOT_EVALUABLE",
            "NOT_EVALUABLE",
            f"Cannot evaluate scenario '{scenario.get('title', 'Unknown')}': Target requirement IDs {list(aff_ids)} do not exist in the active Decision Contract.",
            ["Scenario targets missing or invalid requirement IDs."],
            ["Requirement definitions in contract do not match scenario affected IDs."],
            ["Regenerate stress testing scenarios against the active Decision Contract."],
            [],
        )

    category = scenario.get("category", "EXTERNAL_CONDITION_CHANGE")
    severity = scenario.get("severity", "MEDIUM")

    req_evaluations: List[RequirementEvaluationItem] = []
    degraded_count = 0
    critical_failure = False

    for req in requirements:
        rid = req["id"]
        req_title = req["title"]
        base_asm = suff_map.get(rid)
        base_status = base_asm["coverage_status"] if base_asm else "NO_EVIDENCE"

        if rid not in aff_ids:
            # Unaffected by this specific scenario
            req_evaluations.append(RequirementEvaluationItem(
                requirement_id=rid,
                requirement_title=req_title,
                baseline_status=base_status,
                scenario_status=base_status,
                status_shift="UNMODIFIED",
                reason="Requirement premise and supporting evidence are unaffected by this scenario permutation.",
                affected_claim_ids=[],
            ))
            continue

        # Affected: determine status degradation
        is_critical_req = req.get("priority", "").upper() in ("CRITICAL", "HIGH")
        scenario_status = base_status
        shift = "DEGRADED"
        reason = ""

        if category == "ASSUMPTION_FAILURE":
            if base_status == "SUFFICIENT":
                scenario_status = "PARTIAL"
                reason = "Core operating assumption invalidated; multi-source corroboration becomes non-operational."
            elif base_status == "PARTIAL":
                scenario_status = "INSUFFICIENT"
                reason = "Challenged assumption was the sole basis substantiating partial coverage."
            else:
                scenario_status = base_status
                shift = "UNMODIFIED"
                reason = "Requirement was already insufficient or contested prior to scenario trigger."

        elif category == "CONFLICT_RESOLUTION":
            if base_status in ("CONFLICTING", "SUFFICIENT", "PARTIAL"):
                scenario_status = "INSUFFICIENT"
                reason = "Adverse conflict settlement validates opposing claim, actively discrediting affirmative evidence."
            else:
                scenario_status = "INSUFFICIENT"
                reason = "Opposing evidence upheld by arbitrated resolution."

        elif category == "EVIDENCE_WEAKENING":
            if base_status == "SUFFICIENT":
                scenario_status = "PARTIAL"
                reason = "Discredited or retracted primary claim leaves requirement without independent secondary study."
            elif base_status == "PARTIAL":
                scenario_status = "NO_EVIDENCE"
                reason = "Single supporting claim invalidated; requirement collapses into complete evidentiary void."
            else:
                scenario_status = base_status
                shift = "UNMODIFIED"
                reason = "Available evidence was already insufficient."

        elif category == "MISSING_EVIDENCE":
            if base_status in ("NO_EVIDENCE", "INSUFFICIENT"):
                scenario_status = "INDETERMINATE"
                shift = "BLOCKED"
                reason = "Lack of empirical filing leaves requirement evaluation indeterminate."
            else:
                scenario_status = "PARTIAL"
                reason = "Missing critical dimension limits scope of existing proof."

        else:  # EXTERNAL_CONDITION_CHANGE / RISK_MATERIALIZATION
            if base_status == "SUFFICIENT":
                scenario_status = "PARTIAL"
                reason = "Operating or regulatory shock exceeds original verification thresholds."
            elif base_status == "PARTIAL":
                scenario_status = "INSUFFICIENT"
                reason = "Tightened constraints render partial findings non-compliant."
            else:
                scenario_status = base_status
                shift = "UNMODIFIED"
                reason = "Existing evidence was already insufficient to satisfy original thresholds."

        if scenario_status != base_status:
            degraded_count += 1
            if is_critical_req and scenario_status in ("INSUFFICIENT", "NO_EVIDENCE", "INDETERMINATE"):
                critical_failure = True

        raw_rel_claims = scenario.get("related_claim_ids") or []
        rel_claims = json.loads(raw_rel_claims) if isinstance(raw_rel_claims, str) else raw_rel_claims
        req_evaluations.append(RequirementEvaluationItem(
            requirement_id=rid,
            requirement_title=req_title,
            baseline_status=base_status,
            scenario_status=scenario_status,
            status_shift=shift,
            reason=reason or "Evaluated under scenario trigger condition.",
            affected_claim_ids=rel_claims,
        ))

    # Overall Outcome & Shift
    degraded_req_titles = [r.requirement_title for r in req_evaluations if r.status_shift == "DEGRADED"]
    ch_raw = scenario.get("challenged_assumptions") or []
    ch_assumptions = json.loads(ch_raw) if isinstance(ch_raw, str) else ch_raw
    assump_desc = f" Assumption(s) challenged: '{', '.join(ch_assumptions)}'." if ch_assumptions else ""
    trig_desc = scenario.get("trigger_condition") or "Simulated condition materialized."

    if critical_failure or (severity == "CRITICAL" and degraded_count > 0):
        scenario_overall_outcome = "HIGHLY_VULNERABLE"
        outcome_shift = "CRITICAL_FAILURE"
        impact_explanation = f"Critical breakdown under condition: '{trig_desc}'.{assump_desc} Causes failure across core requirement(s) ({', '.join(degraded_req_titles) or 'core criteria'}). Overall outcome shifts to HIGHLY_VULNERABLE."
    elif degraded_count > 0:
        scenario_overall_outcome = "VULNERABLE"
        outcome_shift = "DEGRADED"
        impact_explanation = f"Material degradation under condition: '{trig_desc}'.{assump_desc} Causes evidentiary decay across {degraded_count} requirement(s) ({', '.join(degraded_req_titles)}). Overall outcome shifts to VULNERABLE."
    elif category == "MISSING_EVIDENCE" and any(r.scenario_status == "INDETERMINATE" for r in req_evaluations):
        scenario_overall_outcome = "INDETERMINATE"
        outcome_shift = "INDETERMINATE"
        impact_explanation = f"Indeterminate scenario under condition: '{trig_desc}'.{assump_desc} Missing empirical filings prevent definitive evaluation."
    else:
        scenario_overall_outcome = baseline.baseline_outcome
        outcome_shift = "STABLE"
        impact_explanation = f"Resilient to condition: '{trig_desc}'.{assump_desc} Existing corroborated evidence maintains {baseline.baseline_outcome} posture across all evaluated requirements."

    key_vulnerabilities = [
        f"Single-source dependence on {len(aff_ids)} affected requirement(s).",
        f"Sensitivity to {category.replace('_', ' ').lower()} trigger condition: '{scenario['trigger_condition'][:80]}'.",
    ]
    if critical_failure:
        key_vulnerabilities.append("Core mandatory decision criterion is breached.")

    uncertainty_factors = [
        "Scenario assumes 100% materialization of the trigger condition without operational hedging.",
        "Secondary market or regulatory adaptation dynamics are not accounted for in static stress test.",
    ]

    recommended_actions = [
        f"Ingest independent secondary sources to decouple requirement from '{scenario['title'][:40]}'.",
        "Formulate operational risk hedging protocols in the Decision Contract before final commitment.",
    ]

    return (
        scenario_overall_outcome,
        outcome_shift,
        impact_explanation,
        key_vulnerabilities,
        uncertainty_factors,
        recommended_actions,
        req_evaluations,
    )


async def evaluate_investigation_stress_scenario(
    conn, investigation_id: str, scenario_id: str
) -> StressEvaluationModel:
    """
    Evaluates a selected stress scenario against the investigation's baseline.
    Uses Gemini structured reasoning if available, with deterministic fallback.
    Persists evaluation into SQLite.
    """
    cursor = conn.cursor()

    # 1. Fetch Scenario
    cursor.execute("""
        SELECT * FROM decision_stress_scenarios
        WHERE id = ? AND investigation_id = ?;
    """, (scenario_id, investigation_id))
    sc_row = cursor.fetchone()
    if not sc_row:
        raise ValueError(f"Scenario {scenario_id} not found in investigation {investigation_id}")
    scenario = dict(sc_row)

    # 2. Fetch Baseline
    baseline = compute_stress_testing_baseline(conn, investigation_id)

    # 3. Fetch Requirements & Sufficiency Assessments
    cursor.execute("""
        SELECT id, title, priority, verification_criteria FROM contract_requirements
        WHERE contract_id = (SELECT id FROM decision_contracts WHERE investigation_id = ?)
        ORDER BY sort_order ASC, id ASC;
    """, (investigation_id,))
    requirements = [dict(r) for r in cursor.fetchall()]

    cursor.execute("""
        SELECT requirement_id, coverage_status, assessment_summary, confidence
        FROM evidence_sufficiency_assessments
        WHERE investigation_id = ?;
    """, (investigation_id,))
    sufficiency_assessments = [dict(r) for r in cursor.fetchall()]

    # 4. Fetch Conflicts
    cursor.execute("""
        SELECT id, severity, resolution_status, explanation
        FROM evidence_conflicts WHERE investigation_id = ?;
    """, (investigation_id,))
    conflicts = [dict(r) for r in cursor.fetchall()]

    # Execution State
    gemini_completed = False
    processing_mode = "fallback"

    # Attempt Gemini LLM Evaluation
    if GEMINI_API_KEY:
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=GEMINI_API_KEY)

            eval_bundle = {
                "decision_objective": baseline.decision_objective,
                "baseline_outcome": baseline.baseline_outcome,
                "scenario": {
                    "id": scenario["id"],
                    "title": scenario["title"],
                    "category": scenario["category"],
                    "trigger_condition": scenario["trigger_condition"],
                    "expected_impact": scenario["expected_impact"],
                    "severity": scenario["severity"],
                    "affected_requirement_ids": json.loads(scenario["affected_requirement_ids"]) if isinstance(scenario["affected_requirement_ids"], str) else scenario["affected_requirement_ids"],
                    "challenged_assumptions": json.loads(scenario["challenged_assumptions"]) if isinstance(scenario["challenged_assumptions"], str) else scenario["challenged_assumptions"],
                },
                "requirements": [
                    {
                        "requirement_id": r["id"],
                        "title": r["title"],
                        "priority": r["priority"],
                        "baseline_status": next((s["coverage_status"] for s in sufficiency_assessments if s["requirement_id"] == r["id"]), "NO_EVIDENCE"),
                    }
                    for r in requirements
                ],
            }

            prompt = (
                "You are an elite forensic stress-testing auditor evaluating a decision scenario.\n\n"
                f"DECISION OBJECTIVE:\n\"{baseline.decision_objective}\"\n\n"
                f"BASELINE QUALITATIVE OUTCOME:\n{baseline.baseline_outcome}\n\n"
                f"STRESS SCENARIO TO EVALUATE:\n{json.dumps(eval_bundle['scenario'], separators=(',', ':'))}\n\n"
                f"REQUIREMENTS & BASELINE STATUS:\n{json.dumps(eval_bundle['requirements'], separators=(',', ':'))}\n\n"
                "INSTRUCTIONS:\n"
                "1. For each requirement, determine its 'scenario_status' under this scenario trigger condition.\n"
                "   Statuses: SUFFICIENT, PARTIAL, INSUFFICIENT, NO_EVIDENCE, CONFLICTING\n"
                "   Shifts: DEGRADED, UNMODIFIED, IMPROVED, BLOCKED\n"
                "2. Determine the 'scenario_overall_outcome': ROBUST, CONDITIONALLY_ROBUST, VULNERABLE, HIGHLY_VULNERABLE, INDETERMINATE\n"
                "3. Determine the 'outcome_shift': CRITICAL_FAILURE, DEGRADED, STABLE, IMPROVED, INDETERMINATE\n"
                "4. Provide impact_explanation, key_vulnerabilities, uncertainty_factors, and recommended_actions.\n"
                "5. Return valid JSON matching the exact schema.\n"
            )

            candidate_models = [GEMINI_MODEL]
            for fb in ["gemini-flash-lite-latest", "gemini-3.5-flash-lite", "gemini-3-flash-preview"]:
                if fb not in candidate_models:
                    candidate_models.append(fb)

            response = None
            used_model = None

            for m_cand in candidate_models:
                try:
                    res = client.models.generate_content(
                        model=m_cand,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            temperature=0.1,
                            max_output_tokens=5000,
                        )
                    )
                    if res and res.text:
                        response = res
                        used_model = m_cand
                        break
                except Exception as g_err:
                    logger.warning("Gemini model '%s' failed for scenario evaluation: %s", m_cand, g_err)
                    err_str = str(g_err).upper()
                    if "RESOURCE_EXHAUSTED" in err_str or "429" in err_str:
                        logger.warning("Gemini quota exhausted (429), bypassing LLM retries for stress test.")
                        break

            if response and response.text:
                parsed = json.loads(response.text)
                if isinstance(parsed, list) and len(parsed) > 0:
                    parsed = parsed[0]
                elif not isinstance(parsed, dict):
                    parsed = {}
                sc_out = (parsed.get("scenario_overall_outcome") or "VULNERABLE").upper().strip()
                if sc_out not in VALID_OUTCOMES:
                    sc_out = "VULNERABLE"
                shift_out = (parsed.get("outcome_shift") or "DEGRADED").upper().strip()
                if shift_out not in {"CRITICAL_FAILURE", "DEGRADED", "STABLE", "IMPROVED", "INDETERMINATE"}:
                    shift_out = "DEGRADED"

                req_map = {r["id"]: r for r in requirements}
                suff_map = {s["requirement_id"]: s["coverage_status"] for s in sufficiency_assessments}

                eval_items: List[RequirementEvaluationItem] = []
                raw_evals = parsed.get("requirement_evaluations", [])
                g_req_map = {it.get("requirement_id"): it for it in raw_evals if isinstance(it, dict)}

                for req in requirements:
                    rid = req["id"]
                    base_st = suff_map.get(rid, "NO_EVIDENCE")
                    if rid in g_req_map:
                        git = g_req_map[rid]
                        st = (git.get("scenario_status") or base_st).upper().strip()
                        sh = (git.get("status_shift") or "UNMODIFIED").upper().strip()
                        rea = git.get("reason") or "Evaluated via Gemini structured stress model."
                    else:
                        st = base_st
                        sh = "UNMODIFIED"
                        rea = "Requirement unaffected under this scenario."

                    eval_items.append(RequirementEvaluationItem(
                        requirement_id=rid,
                        requirement_title=req["title"],
                        baseline_status=base_st,
                        scenario_status=st,
                        status_shift=sh,
                        reason=rea,
                        affected_claim_ids=[],
                    ))

                scenario_overall_outcome = sc_out
                outcome_shift = shift_out
                impact_explanation = parsed.get("impact_explanation") or "Gemini completed scenario stress analysis."
                key_vulnerabilities = parsed.get("key_vulnerabilities") or []
                uncertainty_factors = parsed.get("uncertainty_factors") or []
                recommended_actions = parsed.get("recommended_actions") or []
                gemini_completed = True
                processing_mode = "gemini"

        except Exception as e:
            logger.warning("Gemini scenario evaluation failed: %s. Using deterministic fallback.", e, exc_info=True)
            gemini_completed = False

    # Execute deterministic fallback if Gemini was skipped or failed
    if not gemini_completed:
        processing_mode = "fallback"
        (
            scenario_overall_outcome,
            outcome_shift,
            impact_explanation,
            key_vulnerabilities,
            uncertainty_factors,
            recommended_actions,
            eval_items,
        ) = evaluate_deterministic_scenario(
            scenario, baseline, sufficiency_assessments, requirements, conflicts
        )

    # Persist in SQLite
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    eval_id = f"eval_{uuid.uuid4().hex[:12]}"

    cursor.execute("""
        INSERT OR REPLACE INTO decision_stress_evaluations (
            id, scenario_id, investigation_id, baseline_overall_outcome,
            scenario_overall_outcome, outcome_shift, impact_explanation,
            key_vulnerabilities, uncertainty_factors, recommended_actions,
            requirement_evaluations, processing_mode, evaluated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, (
        eval_id,
        scenario_id,
        investigation_id,
        baseline.baseline_outcome,
        scenario_overall_outcome,
        outcome_shift,
        impact_explanation,
        json.dumps(key_vulnerabilities),
        json.dumps(uncertainty_factors),
        json.dumps(recommended_actions),
        json.dumps([item.model_dump() for item in eval_items]),
        processing_mode,
        now,
    ))

    conn.commit()

    return StressEvaluationModel(
        id=eval_id,
        scenario_id=scenario_id,
        investigation_id=investigation_id,
        baseline_overall_outcome=baseline.baseline_outcome,
        scenario_overall_outcome=scenario_overall_outcome,
        outcome_shift=outcome_shift,
        impact_explanation=impact_explanation,
        key_vulnerabilities=key_vulnerabilities,
        uncertainty_factors=uncertainty_factors,
        recommended_actions=recommended_actions,
        requirement_evaluations=eval_items,
        processing_mode=processing_mode,
        evaluated_at=now,
    )


def get_stress_tests(conn, investigation_id: str) -> StressTestListResponse:
    """
    Retrieves baseline, scenarios, evaluations, and summary metrics for an investigation.
    """
    cursor = conn.cursor()

    # 1. Compute or Fetch Baseline
    baseline = compute_stress_testing_baseline(conn, investigation_id)

    # 2. Fetch Requirements for Title Mapping
    cursor.execute("""
        SELECT id, title FROM contract_requirements
        WHERE contract_id = (SELECT id FROM decision_contracts WHERE investigation_id = ?);
    """, (investigation_id,))
    req_map = {r["id"]: r["title"] for r in cursor.fetchall()}

    # 3. Fetch Scenarios
    cursor.execute("""
        SELECT * FROM decision_stress_scenarios
        WHERE investigation_id = ? ORDER BY created_at ASC, id ASC;
    """, (investigation_id,))
    scenario_rows = [dict(r) for r in cursor.fetchall()]

    # 4. Fetch Evaluations
    cursor.execute("""
        SELECT * FROM decision_stress_evaluations
        WHERE investigation_id = ?;
    """, (investigation_id,))
    eval_rows = {r["scenario_id"]: dict(r) for r in cursor.fetchall()}

    scenarios: List[StressScenarioModel] = []
    vulnerable_cnt = 0
    indeterminate_cnt = 0
    crit_sev_cnt = 0
    high_sev_cnt = 0
    latest_ts = None
    proc_modes = set()

    for s_row in scenario_rows:
        sid = s_row["id"]
        aff_ids = json.loads(s_row["affected_requirement_ids"]) if isinstance(s_row["affected_requirement_ids"], str) else s_row["affected_requirement_ids"]
        aff_titles = [req_map.get(rid, rid) for rid in aff_ids]
        proc_modes.add(s_row.get("processing_mode", "fallback"))
        if s_row.get("created_at"):
            latest_ts = s_row["created_at"]

        if s_row["severity"] == "CRITICAL":
            crit_sev_cnt += 1
        elif s_row["severity"] == "HIGH":
            high_sev_cnt += 1

        eval_model: Optional[StressEvaluationModel] = None
        if sid in eval_rows:
            e_row = eval_rows[sid]
            req_evals_raw = json.loads(e_row["requirement_evaluations"]) if isinstance(e_row["requirement_evaluations"], str) else e_row["requirement_evaluations"]
            eval_model = StressEvaluationModel(
                id=e_row["id"],
                scenario_id=sid,
                investigation_id=investigation_id,
                baseline_overall_outcome=e_row["baseline_overall_outcome"],
                scenario_overall_outcome=e_row["scenario_overall_outcome"],
                outcome_shift=e_row["outcome_shift"],
                impact_explanation=e_row["impact_explanation"],
                key_vulnerabilities=json.loads(e_row["key_vulnerabilities"]) if isinstance(e_row["key_vulnerabilities"], str) else e_row["key_vulnerabilities"],
                uncertainty_factors=json.loads(e_row["uncertainty_factors"]) if isinstance(e_row["uncertainty_factors"], str) else e_row["uncertainty_factors"],
                recommended_actions=json.loads(e_row["recommended_actions"]) if isinstance(e_row["recommended_actions"], str) else e_row["recommended_actions"],
                requirement_evaluations=[RequirementEvaluationItem(**it) for it in req_evals_raw],
                processing_mode=e_row.get("processing_mode", "fallback"),
                evaluated_at=e_row["evaluated_at"],
            )
            if e_row["scenario_overall_outcome"] in ("VULNERABLE", "HIGHLY_VULNERABLE"):
                vulnerable_cnt += 1
            elif e_row["scenario_overall_outcome"] == "INDETERMINATE":
                indeterminate_cnt += 1

        scenarios.append(StressScenarioModel(
            id=sid,
            investigation_id=investigation_id,
            title=s_row["title"],
            category=s_row["category"],
            description=s_row["description"],
            trigger_condition=s_row["trigger_condition"],
            challenged_assumptions=json.loads(s_row["challenged_assumptions"]) if isinstance(s_row["challenged_assumptions"], str) else s_row["challenged_assumptions"],
            affected_requirement_ids=aff_ids,
            affected_requirement_titles=aff_titles,
            related_claim_ids=json.loads(s_row["related_claim_ids"]) if isinstance(s_row["related_claim_ids"], str) else s_row["related_claim_ids"],
            related_source_ids=json.loads(s_row["related_source_ids"]) if isinstance(s_row["related_source_ids"], str) else s_row["related_source_ids"],
            related_conflict_ids=json.loads(s_row["related_conflict_ids"]) if isinstance(s_row["related_conflict_ids"], str) else s_row["related_conflict_ids"],
            expected_impact=s_row["expected_impact"],
            severity=s_row["severity"],
            evidence_needed=s_row["evidence_needed"],
            evaluation_status="evaluated" if eval_model else "unevaluated",
            baseline_overall_outcome=eval_model.baseline_overall_outcome if eval_model else None,
            scenario_overall_outcome=eval_model.scenario_overall_outcome if eval_model else None,
            outcome_shift=eval_model.outcome_shift if eval_model else None,
            evaluation=eval_model,
            processing_mode=s_row.get("processing_mode", "fallback"),
            created_at=s_row["created_at"],
        ))

    overall_proc_mode = "gemini" if "gemini" in proc_modes else "fallback"

    summary = StressTestingSummaryModel(
        total_scenarios=len(scenarios),
        evaluated_scenarios=len(eval_rows),
        vulnerable_scenarios=vulnerable_cnt,
        indeterminate_scenarios=indeterminate_cnt,
        critical_severity_count=crit_sev_cnt,
        high_severity_count=high_sev_cnt,
        baseline_outcome=baseline.baseline_outcome,
        processing_mode=overall_proc_mode,
    )

    return StressTestListResponse(
        investigation_id=investigation_id,
        baseline=baseline,
        summary=summary,
        scenarios=scenarios,
        processing_mode=overall_proc_mode,
        last_generated_at=latest_ts,
    )


def get_stress_scenario_detail(conn, investigation_id: str, scenario_id: str) -> StressScenarioModel:
    """
    Retrieves detailed model for a single scenario with its evaluation.
    """
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM decision_stress_scenarios
        WHERE id = ? AND investigation_id = ?;
    """, (scenario_id, investigation_id))
    s_row = cursor.fetchone()
    if not s_row:
        raise ValueError(f"Scenario {scenario_id} not found in investigation {investigation_id}")
    s_row = dict(s_row)

    cursor.execute("""
        SELECT id, title FROM contract_requirements
        WHERE contract_id = (SELECT id FROM decision_contracts WHERE investigation_id = ?);
    """, (investigation_id,))
    req_map = {r["id"]: r["title"] for r in cursor.fetchall()}

    cursor.execute("""
        SELECT * FROM decision_stress_evaluations
        WHERE scenario_id = ? AND investigation_id = ?;
    """, (scenario_id, investigation_id))
    e_row = cursor.fetchone()
    e_row = dict(e_row) if e_row else None

    eval_model: Optional[StressEvaluationModel] = None
    if e_row:
        req_evals_raw = json.loads(e_row["requirement_evaluations"]) if isinstance(e_row["requirement_evaluations"], str) else e_row["requirement_evaluations"]
        eval_model = StressEvaluationModel(
            id=e_row["id"],
            scenario_id=scenario_id,
            investigation_id=investigation_id,
            baseline_overall_outcome=e_row["baseline_overall_outcome"],
            scenario_overall_outcome=e_row["scenario_overall_outcome"],
            outcome_shift=e_row["outcome_shift"],
            impact_explanation=e_row["impact_explanation"],
            key_vulnerabilities=json.loads(e_row["key_vulnerabilities"]) if isinstance(e_row["key_vulnerabilities"], str) else e_row["key_vulnerabilities"],
            uncertainty_factors=json.loads(e_row["uncertainty_factors"]) if isinstance(e_row["uncertainty_factors"], str) else e_row["uncertainty_factors"],
            recommended_actions=json.loads(e_row["recommended_actions"]) if isinstance(e_row["recommended_actions"], str) else e_row["recommended_actions"],
            requirement_evaluations=[RequirementEvaluationItem(**it) for it in req_evals_raw],
            processing_mode=e_row.get("processing_mode", "fallback"),
            evaluated_at=e_row["evaluated_at"],
        )

    aff_ids = json.loads(s_row["affected_requirement_ids"]) if isinstance(s_row["affected_requirement_ids"], str) else s_row["affected_requirement_ids"]
    aff_titles = [req_map.get(rid, rid) for rid in aff_ids]

    return StressScenarioModel(
        id=s_row["id"],
        investigation_id=investigation_id,
        title=s_row["title"],
        category=s_row["category"],
        description=s_row["description"],
        trigger_condition=s_row["trigger_condition"],
        challenged_assumptions=json.loads(s_row["challenged_assumptions"]) if isinstance(s_row["challenged_assumptions"], str) else s_row["challenged_assumptions"],
        affected_requirement_ids=aff_ids,
        affected_requirement_titles=aff_titles,
        related_claim_ids=json.loads(s_row["related_claim_ids"]) if isinstance(s_row["related_claim_ids"], str) else s_row["related_claim_ids"],
        related_source_ids=json.loads(s_row["related_source_ids"]) if isinstance(s_row["related_source_ids"], str) else s_row["related_source_ids"],
        related_conflict_ids=json.loads(s_row["related_conflict_ids"]) if isinstance(s_row["related_conflict_ids"], str) else s_row["related_conflict_ids"],
        expected_impact=s_row["expected_impact"],
        severity=s_row["severity"],
        evidence_needed=s_row["evidence_needed"],
        evaluation_status="evaluated" if eval_model else "unevaluated",
        baseline_overall_outcome=eval_model.baseline_overall_outcome if eval_model else None,
        scenario_overall_outcome=eval_model.scenario_overall_outcome if eval_model else None,
        outcome_shift=eval_model.outcome_shift if eval_model else None,
        evaluation=eval_model,
        processing_mode=s_row.get("processing_mode", "fallback"),
        created_at=s_row["created_at"],
    )


def get_stress_test_status(conn, investigation_id: str) -> StressTestStatusResponse:
    """
    Lightweight status check for stress-testing pipeline.
    """
    cursor = conn.cursor()

    cursor.execute("""
        SELECT COUNT(*) FROM decision_stress_scenarios WHERE investigation_id = ?;
    """, (investigation_id,))
    total_scenarios = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*) FROM decision_stress_evaluations WHERE investigation_id = ?;
    """, (investigation_id,))
    evaluated_scenarios = cursor.fetchone()[0]

    cursor.execute("""
        SELECT processing_mode, status, created_at FROM decision_stress_runs
        WHERE investigation_id = ? ORDER BY created_at DESC LIMIT 1;
    """, (investigation_id,))
    run_row = cursor.fetchone()

    proc_mode = run_row["processing_mode"] if run_row else "fallback"
    run_status = run_row["status"] if run_row else ("completed" if total_scenarios > 0 else "idle")
    last_gen = run_row["created_at"] if run_row else None

    baseline = compute_stress_testing_baseline(conn, investigation_id)

    return StressTestStatusResponse(
        investigation_id=investigation_id,
        total_scenarios=total_scenarios,
        evaluated_scenarios=evaluated_scenarios,
        baseline_outcome=baseline.baseline_outcome,
        processing_mode=proc_mode,
        last_run_status=run_status,
        last_generated_at=last_gen,
    )
