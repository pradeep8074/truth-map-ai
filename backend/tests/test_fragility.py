import pytest
import sqlite3
import uuid
import datetime
import json
from decimal import Decimal
from fastapi.testclient import TestClient

from backend.main import app
from backend.database import init_db, get_db
from backend.models import SensitivitySimulationRequest
from backend.services.fragility_service import (
    round_score,
    compute_composite_dfi,
    compute_d1_coverage_fragility,
    compute_d2_assumption_fragility,
    compute_d3_conflict_fragility,
    compute_d4_stress_fragility,
    compute_d5_sensitivity_concentration,
    execute_fragility_analysis,
    get_latest_fragility_result,
    get_fragility_methodology,
)
from backend.services.sensitivity_service import (
    simulate_sensitivity_experiment,
    generate_fragility_recommendations,
)

client = TestClient(app)


@pytest.fixture
def temp_db(tmp_path):
    """Provides a fresh isolated SQLite database file for testing."""
    db_file = str(tmp_path / "test_truthmap_fragility.db")
    init_db(db_file)
    return db_file


def _seed_investigation_contract_and_sufficiency(
    db_path: str,
    req_priorities_and_statuses: list[tuple[str, str]],
    assumptions_list: list[tuple[str, float]] = None,
    conflicts_list: list[tuple[str, str]] = None,
    stress_evals_list: list[tuple[str, str]] = None,
    run_conflicts: bool = True,
    run_stress: bool = True,
):
    """
    Helper to seed an investigation with specific requirements, sufficiency,
    assumptions, conflicts, and stress test records.
    """
    with get_db(db_path) as conn:
        cursor = conn.cursor()
        inv_id = str(uuid.uuid4())
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()

        # 1. Investigation
        cursor.execute("INSERT INTO investigations (id, research_question, status, created_at) VALUES (?, ?, ?, ?);",
                       (inv_id, "Test Decision Hypothesis", "active", now))

        # Base source, passage, and claims for foreign-key constraints
        src_id = f"src-{str(uuid.uuid4())[:8]}"
        pass_id = f"pass-{str(uuid.uuid4())[:8]}"
        claim_a_id = f"claim-a-{str(uuid.uuid4())[:8]}"
        claim_b_id = f"claim-b-{str(uuid.uuid4())[:8]}"
        cursor.execute("INSERT INTO sources (id, investigation_id, source_type, retrieved_at, extraction_status) VALUES (?, ?, 'web', ?, 'completed');", (src_id, inv_id, now))
        cursor.execute("INSERT INTO passages (id, source_id, passage_text, sha256_hash) VALUES (?, ?, 'Sample passage text for testing', 'hash123');", (pass_id, src_id))
        cursor.execute("INSERT INTO claims (id, investigation_id, source_id, passage_id, claim_text, extraction_method, extraction_confidence, created_at) VALUES (?, ?, ?, ?, 'Claim A', 'deterministic', 0.9, ?);", (claim_a_id, inv_id, src_id, pass_id, now))
        cursor.execute("INSERT INTO claims (id, investigation_id, source_id, passage_id, claim_text, extraction_method, extraction_confidence, created_at) VALUES (?, ?, ?, ?, 'Claim B', 'deterministic', 0.9, ?);", (claim_b_id, inv_id, src_id, pass_id, now))

        # 2. Decision Contract
        contract_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO decision_contracts (id, investigation_id, original_question, normalized_question, decision_objective, compilation_method, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 'deterministic', ?, ?);
        """, (contract_id, inv_id, "Test Question", "Normalized Test Question", "Evaluate capital expansion feasibility", now, now))

        # 3. Requirements & Sufficiency
        for idx, (priority, status) in enumerate(req_priorities_and_statuses):
            req_id = f"req-{idx}-{str(uuid.uuid4())[:8]}"
            cursor.execute("""
                INSERT INTO contract_requirements (id, contract_id, title, description, requirement_type, priority, verification_criteria, sort_order)
                VALUES (?, ?, ?, ?, 'FACTUAL', ?, 'Verification criteria text', ?);
            """, (req_id, contract_id, f"Requirement {idx}", f"Description {idx}", priority, idx))

            cursor.execute("""
                INSERT INTO evidence_sufficiency_assessments (
                    id, investigation_id, requirement_id, coverage_status, confidence,
                    assessment_summary, limitations, missing_information, recommended_action,
                    analysis_method, processing_mode, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 0.9, 'Summary', '', '', 'Action', 'deterministic', 'fallback', ?, ?);
            """, (str(uuid.uuid4()), inv_id, req_id, status, now, now))

        # 4. Assumptions
        if assumptions_list is not None:
            for idx, (status, conf) in enumerate(assumptions_list):
                cursor.execute("""
                    INSERT INTO contract_assumptions (id, contract_id, description, confidence, validation_status)
                    VALUES (?, ?, ?, ?, ?);
                """, (f"assump-{idx}-{str(uuid.uuid4())[:8]}", contract_id, f"Assumption {idx}", conf, status))

        # 5. Conflicts
        if run_conflicts:
            cursor.execute("INSERT INTO evidence_conflict_runs (id, investigation_id, processing_mode, analysis_status, created_at) VALUES (?, ?, 'deterministic', 'success', ?);",
                           (str(uuid.uuid4()), inv_id, now))
            if conflicts_list:
                for idx, (sev, res_status) in enumerate(conflicts_list):
                    cursor.execute("""
                        INSERT INTO evidence_conflicts (id, investigation_id, claim_a_id, claim_b_id, conflict_type, severity, explanation, confidence, resolution_status, recommended_action, analysis_method, processing_mode, created_at, updated_at)
                        VALUES (?, ?, ?, ?, 'CONTRADICTION', ?, 'Explanation', 0.85, ?, 'Action', 'deterministic', 'fallback', ?, ?);
                    """, (f"conf-{idx}-{str(uuid.uuid4())[:8]}", inv_id, claim_a_id, claim_b_id, sev, res_status, now, now))

        # 6. Stress Tests
        if run_stress:
            cursor.execute("INSERT INTO decision_stress_runs (id, investigation_id, processing_mode, status, created_at) VALUES (?, ?, 'deterministic', 'success', ?);",
                           (str(uuid.uuid4()), inv_id, now))
            if stress_evals_list:
                for idx, (shift, sev) in enumerate(stress_evals_list):
                    sc_id = f"sc-{idx}-{str(uuid.uuid4())[:8]}"
                    cursor.execute("""
                        INSERT INTO decision_stress_scenarios (
                            id, investigation_id, title, category, description, trigger_condition,
                            expected_impact, severity, evidence_needed, processing_mode, created_at
                        ) VALUES (?, ?, ?, 'RISK_MATERIALIZATION', 'Scenario Description', 'Trigger condition', 'Impact', ?, 'Evidence needed', 'fallback', ?);
                    """, (sc_id, inv_id, f"Scenario {idx}", sev, now))

                    cursor.execute("""
                        INSERT INTO decision_stress_evaluations (
                            id, scenario_id, investigation_id, baseline_overall_outcome, scenario_overall_outcome,
                            outcome_shift, impact_explanation, evaluated_at
                        ) VALUES (?, ?, ?, 'ROBUST', 'VULNERABLE', ?, 'Explanation', ?);
                    """, (str(uuid.uuid4()), sc_id, inv_id, shift, now))

        conn.commit()
        return inv_id


# ==========================================
# 10 APPROVED METHODOLOGY VALIDATION TESTS
# ==========================================

def test_case_1_standard_balanced_baseline():
    """
    Test Case 1: Standard Balanced Baseline
    D1=30.0, D2=40.0, D3=20.0, D4=15.0, D5=10.0
    Composite: 0.30(30) + 0.15(40) + 0.25(20) + 0.20(15) + 0.10(10) = 9 + 6 + 5 + 3 + 1 = 24.0.
    Classification: LOW FRAGILITY (<= 25.0).
    """
    dfi, classification, is_prov, _, guardrail, _ = compute_composite_dfi(
        d1=30.0, d2=40.0, d3=20.0, d4=15.0, d5=10.0,
        d1_status="ASSESSED", d2_status="ASSESSED", d3_status="ASSESSED", d4_status="ASSESSED", d5_status="ASSESSED",
        requirements=[{"id": "r1", "priority": "MEDIUM"}],
        sufficiency_map={"r1": {"coverage_status": "PARTIAL"}}
    )
    assert dfi == 24.0
    assert classification == "LOW FRAGILITY"
    assert is_prov is False
    assert guardrail is False


def test_case_2_critical_deficit_guardrail_triggered(temp_db):
    """
    Test Case 2: Critical Deficit Guardrail Triggered
    4 CRITICAL requirements, all have NO_EVIDENCE (Deficit = 1.0).
    D1 = 100.0, D2=0, D3=0, D4=0, D5=0 -> Raw DFI = 30.0.
    Since CRITICAL requirements have NO_EVIDENCE, guardrail unconditionally overrides classification.
    """
    inv_id = _seed_investigation_contract_and_sufficiency(
        temp_db,
        req_priorities_and_statuses=[
            ("CRITICAL", "NO_EVIDENCE"),
            ("CRITICAL", "NO_EVIDENCE"),
            ("CRITICAL", "NO_EVIDENCE"),
            ("CRITICAL", "NO_EVIDENCE"),
        ],
        assumptions_list=[],
        conflicts_list=[],
        stress_evals_list=[("STABLE", "LOW")],
        run_conflicts=True,
        run_stress=True,
    )

    with get_db(temp_db) as conn:
        res = execute_fragility_analysis(conn, inv_id, allow_gemini=False)

    assert res.dfi_score == 30.0
    assert res.guardrail_active is True
    assert "CRITICAL DEFICIT GUARDRAIL: UNGROUNDED FOUNDATION" in res.classification
    assert "DFI: 30.0" in res.classification
    assert len(res.unsubstantiated_critical_requirements) == 4


def test_case_3_empty_assumptions_explicit_handling():
    """
    Test Case 3: Empty Assumptions Explicit Handling
    |A| == 0 -> D2 = 0.0 with status NOT_APPLICABLE, implicit_uncertainty_flag = True.
    Net DFI contribution is 0.0.
    """
    d2_score, status, flag, ledger = compute_d2_assumption_fragility([])
    assert d2_score == 0.0
    assert status == "NOT_APPLICABLE"
    assert flag is True
    assert len(ledger) == 0


def test_case_4_sensitivity_concentration_extremes():
    """
    Test Case 4: Sensitivity Concentration Extremes (D5)
    1. Single high-deficit requirement (1 CRITICAL NO_EVIDENCE, 3 LOW SUFFICIENT)
       -> HHI=1.0, C=1.0, Fmax=1.0 -> D5 = 100.0.
    2. Evenly distributed deficits across all requirements -> C = 0.0 -> D5 = 0.0.
    """
    reqs_concentrated = [
        {"id": "r1", "priority": "CRITICAL"},
        {"id": "r2", "priority": "LOW"},
        {"id": "r3", "priority": "LOW"},
        {"id": "r4", "priority": "LOW"},
    ]
    suff_concentrated = {
        "r1": {"coverage_status": "NO_EVIDENCE"},
        "r2": {"coverage_status": "SUFFICIENT"},
        "r3": {"coverage_status": "SUFFICIENT"},
        "r4": {"coverage_status": "SUFFICIENT"},
    }
    d5_conc, status, ledger, metrics = compute_d5_sensitivity_concentration(reqs_concentrated, suff_concentrated)
    assert d5_conc == 100.0
    assert metrics["normalized_concentration"] == 1.0
    assert metrics["concentration_label"] == "HIGH CONCENTRATION"

    # Evenly distributed
    reqs_even = [
        {"id": f"r{i}", "priority": "MEDIUM"} for i in range(4)
    ]
    suff_even = {
        f"r{i}": {"coverage_status": "PARTIAL"} for i in range(4)
    }
    d5_even, _, _, metrics_even = compute_d5_sensitivity_concentration(reqs_even, suff_even)
    assert d5_even == 0.0
    assert metrics_even["normalized_concentration"] == 0.0


def test_case_5_unassessed_dimensions_and_provisional_policy():
    """
    Test Case 5: Unassessed Optional Dimensions & Provisional Policy (with Clarification 1)
    If C05 (conflicts) or C07 (stress tests) not executed:
    - Dimensions are marked NOT_ASSESSED.
    - is_provisional = True.
    - If raw score <= 25.0, classification is held at:
      MODERATE FRAGILITY (PROVISIONAL - INCOMPLETE COVERAGE)
    - Clarification 1 phrasing:
      'No degradation was detected in the evaluated scenarios. This does not establish resilience to untested scenarios or real-world shocks.'
    """
    # Unassessed check
    dfi, classification, is_prov, prov_reasons, _, _ = compute_composite_dfi(
        d1=20.0, d2=0.0, d3=0.0, d4=0.0, d5=0.0,
        d1_status="ASSESSED", d2_status="NOT_APPLICABLE", d3_status="NOT_ASSESSED", d4_status="NOT_ASSESSED", d5_status="ASSESSED",
        requirements=[{"id": "r1", "priority": "MEDIUM"}],
        sufficiency_map={"r1": {"coverage_status": "PARTIAL"}}
    )
    assert dfi == 6.0  # 0.30 * 20
    assert is_prov is True
    assert classification == "MODERATE FRAGILITY (PROVISIONAL - INCOMPLETE COVERAGE)"
    assert len(prov_reasons) == 2

    # Clarification 1 check on stable stress test
    evals = [{"scenario_id": "sc1", "outcome_shift": "STABLE", "severity": "MEDIUM"}]
    d4_score, d4_status, _, note = compute_d4_stress_fragility(evals, has_stress_testing_run=True)
    assert d4_score == 0.0
    assert d4_status == "ASSESSED"
    assert note == "No degradation was detected in the evaluated scenarios. This does not establish resilience to untested scenarios or real-world shocks."


def test_case_6_boundary_values_0_and_100():
    """
    Test Case 6: Boundary Values (0.0 and 100.0)
    All 0s -> DFI = 0.0 (LOW FRAGILITY).
    All 100s -> DFI = 100.0 (CRITICAL FRAGILITY).
    """
    dfi_zero, class_zero, _, _, _, _ = compute_composite_dfi(
        0.0, 0.0, 0.0, 0.0, 0.0,
        "ASSESSED", "ASSESSED", "ASSESSED", "ASSESSED", "ASSESSED",
        [{"id": "r1", "priority": "LOW"}], {"r1": {"coverage_status": "SUFFICIENT"}}
    )
    assert dfi_zero == 0.0
    assert class_zero == "LOW FRAGILITY"

    dfi_max, class_max, _, _, _, _ = compute_composite_dfi(
        100.0, 100.0, 100.0, 100.0, 100.0,
        "ASSESSED", "ASSESSED", "ASSESSED", "ASSESSED", "ASSESSED",
        [{"id": "r1", "priority": "LOW"}], {"r1": {"coverage_status": "NO_EVIDENCE"}}
    )
    assert dfi_max == 100.0
    assert class_max == "CRITICAL FRAGILITY"


def test_case_7_strict_half_up_rounding():
    """
    Test Case 7: Strict Half-Up Rounding
    25.049 -> 25.0 (LOW FRAGILITY)
    25.050 -> 25.1 (MODERATE FRAGILITY)
    50.049 -> 50.0 (MODERATE FRAGILITY)
    50.050 -> 50.1 (HIGH FRAGILITY)
    """
    assert round_score(25.049) == 25.0
    assert round_score(25.050) == 25.1
    assert round_score(50.049) == 50.0
    assert round_score(50.050) == 50.1


def test_case_8_in_memory_sensitivity_sandbox_isolation(temp_db):
    """
    Test Case 8: In-Memory Sensitivity Sandbox Isolation
    Counterfactual simulations modify in-memory structures only.
    Verifies primary database tables remain completely unchanged before and after simulation.
    """
    inv_id = _seed_investigation_contract_and_sufficiency(
        temp_db,
        req_priorities_and_statuses=[("HIGH", "SUFFICIENT"), ("MEDIUM", "PARTIAL")],
        assumptions_list=[("validated", 1.0)],
        conflicts_list=[("HIGH", "unresolved")],
        stress_evals_list=[("STABLE", "LOW")],
    )

    with get_db(temp_db) as conn:
        # Snapshot primary table records before simulation
        cursor = conn.cursor()
        cursor.execute("SELECT requirement_id, coverage_status FROM evidence_sufficiency_assessments WHERE investigation_id = ? ORDER BY requirement_id;", (inv_id,))
        before_suff = cursor.fetchall()
        cursor.execute("SELECT id, resolution_status FROM evidence_conflicts WHERE investigation_id = ? ORDER BY id;", (inv_id,))
        before_conf = cursor.fetchall()

        # Target requirement for weakening simulation
        req_id = before_suff[0]["requirement_id"]
        req = SensitivitySimulationRequest(
            experiment_type="SIM_EVIDENCE_WEAKENING",
            target_entity_id=req_id,
            target_entity_type="requirement",
            hypothetical_parameters={"target_status": "NO_EVIDENCE"}
        )
        sim_res = simulate_sensitivity_experiment(conn, inv_id, req)

        assert sim_res.is_hypothetical is True
        assert sim_res.delta_dfi > 0  # Fragility increased

        # Verify primary table records after simulation are identical
        cursor.execute("SELECT requirement_id, coverage_status FROM evidence_sufficiency_assessments WHERE investigation_id = ? ORDER BY requirement_id;", (inv_id,))
        after_suff = cursor.fetchall()
        cursor.execute("SELECT id, resolution_status FROM evidence_conflicts WHERE investigation_id = ? ORDER BY id;", (inv_id,))
        after_conf = cursor.fetchall()

        assert [tuple(r) for r in before_suff] == [tuple(r) for r in after_suff]
        assert [tuple(r) for r in before_conf] == [tuple(r) for r in after_conf]


def test_case_9_substantiation_warning_for_partial_critical_requirements(temp_db):
    """
    Test Case 9: Substantiation Warning for Partial/Insufficient Critical Requirements (Clarification 2)
    CRITICAL requirement has PARTIAL coverage (Deficit = 0.40).
    Critical Deficit Guardrail is NOT triggered (since not NO_EVIDENCE or CONFLICTING).
    However, unsubstantiated_critical_requirements MUST visibly flag the requirement.
    """
    inv_id = _seed_investigation_contract_and_sufficiency(
        temp_db,
        req_priorities_and_statuses=[
            ("CRITICAL", "PARTIAL"),
            ("HIGH", "SUFFICIENT"),
        ],
        assumptions_list=[("validated", 1.0)],
        conflicts_list=[],
        stress_evals_list=[("STABLE", "LOW")],
    )

    with get_db(temp_db) as conn:
        res = execute_fragility_analysis(conn, inv_id, allow_gemini=False)

    assert res.guardrail_active is False
    assert len(res.unsubstantiated_critical_requirements) == 1
    assert "Status: PARTIAL" in res.unsubstantiated_critical_requirements[0]


def test_case_10_evidence_improvement_prioritization(temp_db):
    """
    Test Case 10: Evidence Improvement Prioritization
    Generates actionable recommendations with deterministic projected DFI reductions.
    Verifies recommendations are ranked by projected_dfi_reduction DESC.
    """
    inv_id = _seed_investigation_contract_and_sufficiency(
        temp_db,
        req_priorities_and_statuses=[
            ("CRITICAL", "NO_EVIDENCE"),  # Big deficit
            ("LOW", "PARTIAL"),           # Small deficit
        ],
        assumptions_list=[("unvalidated", 0.2)],
        conflicts_list=[("CRITICAL", "unresolved")],
        stress_evals_list=[("STABLE", "LOW")],
    )

    with get_db(temp_db) as conn:
        recs_resp = generate_fragility_recommendations(conn, inv_id)

    assert recs_resp.total_recommendations >= 3
    # Check that reductions are strictly descending
    reductions = [r.projected_dfi_reduction for r in recs_resp.recommendations]
    assert reductions == sorted(reductions, reverse=True)
    assert recs_resp.recommendations[0].projected_dfi_reduction > 0


# ==========================================
# END-TO-END API ROUTE WORKFLOW TESTS
# ==========================================

def test_api_fragility_workflow_and_error_handling(temp_db, monkeypatch):
    """
    Verifies the complete REST API workflow for Component 09:
    - Prerequisite errors (PREREQ_NO_CONTRACT, PREREQ_NO_SUFFICIENCY)
    - Full analysis endpoint
    - Latest result endpoint
    - Status endpoint
    - Sensitivity simulation endpoint
    - Sensitivity results listing
    - Recommendations endpoint
    - Methodology endpoint
    """
    # Override DB_PATH in backend.database to use temp_db
    monkeypatch.setattr("backend.database.DB_PATH", temp_db)

    # 1. Methodology endpoint (does not require investigation)
    resp_meth = client.get("/api/fragility/methodology")
    assert resp_meth.status_code == 200
    meth_data = resp_meth.json()
    assert meth_data["version"] == "v1.2.0-deterministic"
    assert meth_data["weights"]["d1_coverage"] == 0.30

    # 2. Non-existent investigation 404
    fake_id = str(uuid.uuid4())
    resp_404 = client.get(f"/api/investigations/{fake_id}/fragility/latest")
    assert resp_404.status_code == 404

    # 3. Investigation without contract -> 400 PREREQ_NO_CONTRACT
    with get_db(temp_db) as conn:
        cursor = conn.cursor()
        empty_inv_id = str(uuid.uuid4())
        cursor.execute("INSERT INTO investigations (id, research_question, status, created_at) VALUES (?, ?, 'active', ?);",
                       (empty_inv_id, "Empty Inv", datetime.datetime.now(datetime.timezone.utc).isoformat()))
        conn.commit()

    resp_no_contract = client.post(f"/api/investigations/{empty_inv_id}/fragility/analyze")
    assert resp_no_contract.status_code == 400
    assert "PREREQ_NO_CONTRACT" in resp_no_contract.json()["detail"]

    # 4. Valid seeded investigation
    valid_inv_id = _seed_investigation_contract_and_sufficiency(
        temp_db,
        req_priorities_and_statuses=[("HIGH", "PARTIAL"), ("MEDIUM", "SUFFICIENT")],
        assumptions_list=[("validated", 1.0)],
        conflicts_list=[("MEDIUM", "unresolved")],
        stress_evals_list=[("STABLE", "LOW")],
    )

    # 5. Status endpoint before analysis
    resp_status_init = client.get(f"/api/investigations/{valid_inv_id}/fragility/status")
    assert resp_status_init.status_code == 200
    assert resp_status_init.json()["has_result"] is False

    # 6. Analyze endpoint
    resp_analyze = client.post(f"/api/investigations/{valid_inv_id}/fragility/analyze?allow_gemini=false")
    assert resp_analyze.status_code == 200
    analyze_data = resp_analyze.json()
    assert analyze_data["status"] == "success"
    assert analyze_data["result"]["dfi_score"] >= 0.0
    assert "d1_coverage" in analyze_data["result"]["dimensions"]

    # 7. Latest result endpoint
    resp_latest = client.get(f"/api/investigations/{valid_inv_id}/fragility/latest")
    assert resp_latest.status_code == 200
    latest_data = resp_latest.json()
    assert latest_data["id"] == analyze_data["result"]["id"]
    assert len(latest_data["attribution_ledger"]) > 0

    # 8. Status endpoint after analysis
    resp_status_after = client.get(f"/api/investigations/{valid_inv_id}/fragility/status")
    assert resp_status_after.status_code == 200
    assert resp_status_after.json()["has_result"] is True

    # 9. Sensitivity simulation endpoint
    with get_db(temp_db) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT requirement_id FROM evidence_sufficiency_assessments WHERE investigation_id = ? LIMIT 1;", (valid_inv_id,))
        target_req = cursor.fetchone()["requirement_id"]

    sim_payload = {
        "experiment_type": "SIM_EVIDENCE_WEAKENING",
        "target_entity_id": target_req,
        "target_entity_type": "requirement",
        "hypothetical_parameters": {"target_status": "NO_EVIDENCE"}
    }
    resp_sim = client.post(f"/api/investigations/{valid_inv_id}/fragility/sensitivity/simulate", json=sim_payload)
    assert resp_sim.status_code == 200
    sim_data = resp_sim.json()
    assert sim_data["is_hypothetical"] is True
    assert sim_data["simulated_dfi"] >= sim_data["baseline_dfi"]

    # 10. Sensitivity listing endpoint
    resp_sim_list = client.get(f"/api/investigations/{valid_inv_id}/fragility/sensitivity/results")
    assert resp_sim_list.status_code == 200
    sim_list_data = resp_sim_list.json()
    assert len(sim_list_data["experiments"]) >= 1

    # 11. Recommendations endpoint
    resp_recs = client.get(f"/api/investigations/{valid_inv_id}/fragility/recommendations")
    assert resp_recs.status_code == 200
    recs_data = resp_recs.json()
    assert recs_data["total_recommendations"] >= 1


def test_fragility_status_prerequisites_and_staleness_indeterminate(temp_db, monkeypatch):
    """
    Audit Rule 6 Verification:
    Verify that the system returns INDETERMINATE if:
    - no decision contract exists
    - no requirements exist
    - Component 06 sufficiency analysis is absent
    - mandatory upstream data is stale.
    Do not silently substitute zeros for missing mandatory data.
    """
    monkeypatch.setattr("backend.database.DB_PATH", temp_db)
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # 1. Non-existent investigation
    fake_inv_id = str(uuid.uuid4())
    resp = client.get(f"/api/investigations/{fake_inv_id}/fragility/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["has_result"] is False
    assert data["is_indeterminate"] is True

    # 2. Investigation exists, but no decision contract exists
    inv_no_contract = str(uuid.uuid4())
    with get_db(temp_db) as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO investigations (id, research_question, status, created_at) VALUES (?, 'No contract', 'active', ?);", (inv_no_contract, now))
        conn.commit()

    resp = client.get(f"/api/investigations/{inv_no_contract}/fragility/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["has_result"] is False
    assert data["is_indeterminate"] is True
    assert data["classification"] == "INDETERMINATE"
    assert "contract" in data["indeterminate_reason"].lower()

    # 3. Investigation + Contract exists, but 0 requirements exist
    inv_no_reqs = str(uuid.uuid4())
    contract_id_empty = str(uuid.uuid4())
    with get_db(temp_db) as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO investigations (id, research_question, status, created_at) VALUES (?, 'No reqs', 'active', ?);", (inv_no_reqs, now))
        cursor.execute("INSERT INTO decision_contracts (id, investigation_id, original_question, normalized_question, decision_objective, compilation_method, created_at, updated_at) VALUES (?, ?, 'Q', 'Norm Q', 'Objective', 'deterministic', ?, ?);", (contract_id_empty, inv_no_reqs, now, now))
        conn.commit()

    resp = client.get(f"/api/investigations/{inv_no_reqs}/fragility/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["has_result"] is False
    assert data["is_indeterminate"] is True
    assert data["classification"] == "INDETERMINATE"
    assert "requirements" in data["indeterminate_reason"].lower()

    # 4. Investigation + Contract + Requirements exist, but NO sufficiency analysis exists
    inv_no_suff = str(uuid.uuid4())
    contract_id_reqs = str(uuid.uuid4())
    req_id_1 = str(uuid.uuid4())
    with get_db(temp_db) as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO investigations (id, research_question, status, created_at) VALUES (?, 'No suff', 'active', ?);", (inv_no_suff, now))
        cursor.execute("INSERT INTO decision_contracts (id, investigation_id, original_question, normalized_question, decision_objective, compilation_method, created_at, updated_at) VALUES (?, ?, 'Q', 'Norm Q', 'Objective', 'deterministic', ?, ?);", (contract_id_reqs, inv_no_suff, now, now))
        cursor.execute("INSERT INTO contract_requirements (id, contract_id, title, description, requirement_type, priority, verification_criteria, sort_order) VALUES (?, ?, 'Req 1', 'Desc', 'FACTUAL', 'HIGH', 'Crit', 0);", (req_id_1, contract_id_reqs))
        conn.commit()

    resp = client.get(f"/api/investigations/{inv_no_suff}/fragility/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["has_result"] is False
    assert data["is_indeterminate"] is True
    assert data["classification"] == "INDETERMINATE"
    assert "sufficiency" in data["indeterminate_reason"].lower()

    # 5. Fully seeded valid investigation -> run analysis
    valid_inv_id = _seed_investigation_contract_and_sufficiency(
        temp_db,
        req_priorities_and_statuses=[("HIGH", "SUFFICIENT"), ("MEDIUM", "PARTIAL")],
        assumptions_list=[("validated", 1.0)],
        conflicts_list=[("LOW", "resolved_claim_a")],
        stress_evals_list=[("STABLE", "LOW")],
    )

    resp_analyze = client.post(f"/api/investigations/{valid_inv_id}/fragility/analyze?allow_gemini=false")
    assert resp_analyze.status_code == 200

    resp_status = client.get(f"/api/investigations/{valid_inv_id}/fragility/status")
    assert resp_status.status_code == 200
    st_data = resp_status.json()
    assert st_data["has_result"] is True
    assert st_data["is_stale"] is False
    assert st_data["is_indeterminate"] is False

    # 6. Staleness Check: Modify upstream assumption
    with get_db(temp_db) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE contract_assumptions SET confidence = 0.2 WHERE contract_id = (SELECT id FROM decision_contracts WHERE investigation_id = ?);", (valid_inv_id,))
        conn.commit()

    resp_stale = client.get(f"/api/investigations/{valid_inv_id}/fragility/status")
    assert resp_stale.status_code == 200
    stale_data = resp_stale.json()
    assert stale_data["has_result"] is True
    assert stale_data["is_stale"] is True
    assert stale_data["is_indeterminate"] is True
    assert "STALE" in stale_data["classification"]

    # Also check /latest endpoint returns is_stale=True
    resp_latest = client.get(f"/api/investigations/{valid_inv_id}/fragility/latest")
    assert resp_latest.status_code == 200
    assert resp_latest.json()["is_stale"] is True

    # 7. Re-running analysis resolves staleness
    resp_reanalyze = client.post(f"/api/investigations/{valid_inv_id}/fragility/analyze?allow_gemini=false")
    assert resp_reanalyze.status_code == 200
    resp_refreshed = client.get(f"/api/investigations/{valid_inv_id}/fragility/status")
    assert resp_refreshed.status_code == 200
    assert resp_refreshed.json()["is_stale"] is False
    assert resp_refreshed.json()["is_indeterminate"] is False
