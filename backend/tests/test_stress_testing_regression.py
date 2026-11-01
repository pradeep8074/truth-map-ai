import pytest
import sqlite3
from backend.database import init_db, get_db
from backend.models import StressTestingBaselineModel
from backend.services.stress_testing_service import (
    compute_stress_testing_baseline,
    evaluate_deterministic_scenario,
    VALID_OUTCOMES,
)


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test_stress_reg.db"
    init_db(db_file)
    monkeypatch.setattr("backend.database.DB_PATH", db_file)
    return db_file


def test_baseline_empty_requirements_returns_not_evaluable(temp_db):
    """Zero contract requirements must produce NOT_EVALUABLE, never None."""
    with sqlite3.connect(temp_db) as conn:
        conn.row_factory = sqlite3.Row
        # Create empty investigation
        conn.execute("INSERT INTO investigations (id, research_question, status, created_at) VALUES ('inv-empty', 'Empty question', 'ready', '2026-10-31T00:00:00Z');")
        conn.commit()

        baseline = compute_stress_testing_baseline(conn, "inv-empty")
        assert baseline.baseline_outcome == "NOT_EVALUABLE"
        assert baseline.total_requirements == 0
        assert "zero requirements" in baseline.baseline_explanation.lower()


def test_evaluate_scenario_with_not_evaluable_baseline():
    """If baseline is NOT_EVALUABLE, scenario evaluation must return NOT_EVALUABLE with explanation."""
    baseline = StressTestingBaselineModel(
        investigation_id="inv-none",
        decision_objective="Objective",
        total_requirements=0,
        baseline_outcome="NOT_EVALUABLE",
        baseline_explanation="No requirements.",
    )
    scenario = {
        "id": "scen-1",
        "title": "Hypothetical shock",
        "category": "EXTERNAL_CONDITION_CHANGE",
        "severity": "HIGH",
        "affected_requirement_ids": ["req-1"],
        "trigger_condition": "Market shift occurs",
    }
    sc_outcome, shift, expl, key_vulns, _, _, _ = evaluate_deterministic_scenario(
        scenario, baseline, [], [], []
    )
    assert sc_outcome == "NOT_EVALUABLE"
    assert shift == "NOT_EVALUABLE"
    assert "not evaluable" in expl.lower()
    assert len(key_vulns) > 0


def test_evaluate_scenario_with_invalid_affected_requirements():
    """If scenario targets requirements that do not exist, returns NOT_EVALUABLE, never None."""
    baseline = StressTestingBaselineModel(
        investigation_id="inv-1",
        decision_objective="Objective",
        total_requirements=1,
        baseline_outcome="ROBUST",
        baseline_explanation="All requirements satisfied.",
    )
    requirements = [{"id": "req-real", "title": "Real Requirement", "priority": "HIGH"}]
    scenario = {
        "id": "scen-bogus",
        "title": "Bogus Scenario",
        "category": "ASSUMPTION_FAILURE",
        "severity": "CRITICAL",
        "affected_requirement_ids": ["req-nonexistent"],
        "trigger_condition": "Phantom shock",
    }
    sc_outcome, shift, expl, _, _, _, _ = evaluate_deterministic_scenario(
        scenario, baseline, [], requirements, []
    )
    assert sc_outcome == "NOT_EVALUABLE"
    assert shift == "NOT_EVALUABLE"
    assert "do not exist" in expl


def test_valid_scenario_evaluation_calculates_actual_difference():
    """Valid scenario must calculate actual outcome difference and explain which condition changed."""
    baseline = StressTestingBaselineModel(
        investigation_id="inv-2",
        decision_objective="Evaluate solar expansion in ASEAN",
        total_requirements=2,
        baseline_outcome="CONDITIONALLY_ROBUST",
        coverage_ratio=0.75,
        sufficient_count=1,
        partial_count=1,
        baseline_explanation="Conditionally robust with partial coverage.",
    )
    requirements = [
        {"id": "req-1", "title": "Grid Interconnection Regulatory Approval", "priority": "CRITICAL"},
        {"id": "req-2", "title": "Financial IRR Threshold > 15%", "priority": "HIGH"},
    ]
    sufficiency = [
        {"requirement_id": "req-1", "coverage_status": "SUFFICIENT"},
        {"requirement_id": "req-2", "coverage_status": "PARTIAL"},
    ]
    scenario = {
        "id": "scen-real",
        "title": "Regulatory Policy Invalidation",
        "category": "ASSUMPTION_FAILURE",
        "severity": "CRITICAL",
        "affected_requirement_ids": ["req-1"],
        "challenged_assumptions": ["Interconnection policy remains unrevoked through 2026."],
        "trigger_condition": "Regulatory body cancels feed-in tariff and foreign asset guarantees.",
        "related_claim_ids": ["clm-1"],
    }

    sc_outcome, shift, expl, key_vulns, _, _, req_evals = evaluate_deterministic_scenario(
        scenario, baseline, sufficiency, requirements, []
    )

    # Invariants:
    assert sc_outcome is not None
    assert sc_outcome in VALID_OUTCOMES
    assert sc_outcome == "HIGHLY_VULNERABLE"  # degraded a CRITICAL requirement
    assert shift == "CRITICAL_FAILURE"
    assert "Interconnection policy remains unrevoked" in expl
    assert "Regulatory body cancels feed-in tariff" in expl
    assert len(req_evals) == 2

    # Check requirement evaluations
    req1_eval = next(r for r in req_evals if r.requirement_id == "req-1")
    assert req1_eval.baseline_status == "SUFFICIENT"
    assert req1_eval.scenario_status == "PARTIAL"
    assert req1_eval.status_shift == "DEGRADED"

    req2_eval = next(r for r in req_evals if r.requirement_id == "req-2")
    assert req2_eval.baseline_status == "PARTIAL"
    assert req2_eval.scenario_status == "PARTIAL"
    assert req2_eval.status_shift == "UNMODIFIED"
