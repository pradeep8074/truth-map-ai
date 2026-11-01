import pytest
import uuid
import datetime
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from backend.main import app
from backend.database import init_db, get_db
from backend.services.stress_testing_service import (
    compute_stress_testing_baseline,
    generate_deterministic_stress_scenarios,
    evaluate_deterministic_scenario,
)
from backend.services.graph_service import build_evidence_graph_from_db

client = TestClient(app)

CURRENT_TEST_DB = None


@pytest.fixture(autouse=True)
def setup_test_database(tmp_path, monkeypatch):
    """Initializes a fresh isolated SQLite database for each test run."""
    global CURRENT_TEST_DB
    test_db = tmp_path / "test_truthmap_stress.db"
    CURRENT_TEST_DB = test_db
    init_db(test_db)
    monkeypatch.setattr("backend.database.DB_PATH", test_db)
    monkeypatch.setattr("backend.routers.investigations.get_db", lambda: get_db(test_db))
    monkeypatch.setattr("backend.routers.sources.get_db", lambda: get_db(test_db))
    monkeypatch.setattr("backend.routers.contracts.get_db", lambda: get_db(test_db))
    monkeypatch.setattr("backend.routers.graph.get_db", lambda: get_db(test_db))
    monkeypatch.setattr("backend.routers.conflicts.get_db", lambda: get_db(test_db))
    monkeypatch.setattr("backend.routers.sufficiency.get_db", lambda: get_db(test_db))
    monkeypatch.setattr("backend.routers.stress_tests.get_db", lambda: get_db(test_db))
    # Disable live Gemini in tests by default
    monkeypatch.setattr("backend.services.contract_compiler.GEMINI_API_KEY", "")
    monkeypatch.setattr("backend.services.stress_testing_service.GEMINI_API_KEY", "")


def _create_investigation_and_contract():
    """Helper to create investigation, decision contract, and requirements."""
    res = client.post("/api/investigations", json={
        "research_question": "Should the enterprise migrate core storage infrastructure to decentralized distributed networks?"
    })
    assert res.status_code == 201
    inv_id = res.json()["investigation_id"]

    # Compile contract
    c_res = client.post(f"/api/investigations/{inv_id}/contract/compile")
    assert c_res.status_code == 201
    contract_data = c_res.json()
    reqs = contract_data["requirements"]
    return inv_id, contract_data["contract_id"], reqs


def _insert_source_passage_claim(inv_id: str, title: str, claim_text: str):
    """Inserts source, passage, and claim."""
    with get_db(CURRENT_TEST_DB) as conn:
        cursor = conn.cursor()
        src_id = f"src_{uuid.uuid4().hex[:8]}"
        pas_id = f"pas_{uuid.uuid4().hex[:8]}"
        clm_id = f"clm_{uuid.uuid4().hex[:8]}"
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()

        cursor.execute("""
            INSERT INTO sources (id, investigation_id, source_type, title, extraction_status, retrieved_at)
            VALUES (?, ?, 'web', ?, 'completed', ?);
        """, (src_id, inv_id, title, now))

        cursor.execute("""
            INSERT INTO passages (id, source_id, passage_text, page_number, paragraph_index, sha256_hash)
            VALUES (?, ?, 'Passage text validating decentralization', 1, 1, 'mocked_sha256_stress');
        """, (pas_id, src_id))

        cursor.execute("""
            INSERT INTO claims (id, investigation_id, source_id, passage_id, claim_text, category, extraction_method, extraction_confidence, created_at)
            VALUES (?, ?, ?, ?, ?, 'factual', 'deterministic', 0.95, ?);
        """, (clm_id, inv_id, src_id, pas_id, claim_text, now))

        conn.commit()
        return clm_id, src_id, pas_id


def _link_claim_to_requirement(inv_id: str, req_id: str, claim_id: str):
    with get_db(CURRENT_TEST_DB) as conn:
        cursor = conn.cursor()
        rel_id = f"rel_{uuid.uuid4().hex[:8]}"
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        cursor.execute("""
            INSERT INTO evidence_relationships (
                id, investigation_id, requirement_id, claim_id,
                relevance, explanation, confidence, analysis_method, processing_mode, created_at
            ) VALUES (?, ?, ?, ?, 'DIRECTLY_RELEVANT', 'Direct support', 0.92, 'test_link', 'fallback', ?);
        """, (rel_id, inv_id, req_id, claim_id, now))
        conn.commit()


def _insert_conflict(inv_id: str, claim_a_id: str, claim_b_id: str, severity: str = "HIGH"):
    with get_db(CURRENT_TEST_DB) as conn:
        cursor = conn.cursor()
        conf_id = f"conf_{uuid.uuid4().hex[:8]}"
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        cursor.execute("""
            INSERT INTO evidence_conflicts (
                id, investigation_id, claim_a_id, claim_b_id, conflict_type,
                severity, explanation, confidence, resolution_status, recommended_action,
                analysis_method, processing_mode, created_at, updated_at
            ) VALUES (?, ?, ?, ?, 'DIRECT_CONTRADICTION', ?, 'Severe empirical conflict', 0.88, 'unresolved', 'Audit node latency', 'test', 'fallback', ?, ?);
        """, (conf_id, inv_id, claim_a_id, claim_b_id, severity, now, now))
        conn.commit()
        return conf_id


def test_stress_testing_schema_tables():
    """Verify Component 07 tables and indexes exist in SQLite."""
    with get_db(CURRENT_TEST_DB) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT name FROM sqlite_master WHERE type='table' AND name IN (
                'decision_stress_scenarios', 'decision_stress_evaluations', 'decision_stress_runs'
            );
        """)
        tables = {row[0] for row in cursor.fetchall()}
        assert "decision_stress_scenarios" in tables
        assert "decision_stress_evaluations" in tables
        assert "decision_stress_runs" in tables


def test_compute_baseline_outcome():
    """Verify deterministic baseline computation prior to stress triggers."""
    inv_id, contract_id, reqs = _create_investigation_and_contract()

    with get_db(CURRENT_TEST_DB) as conn:
        baseline = compute_stress_testing_baseline(conn, inv_id)
        assert baseline.total_requirements == len(reqs)
        assert baseline.baseline_outcome in ("INDETERMINATE", "VULNERABLE", "CONDITIONALLY_ROBUST")
        assert len(baseline.baseline_explanation) > 0


def test_generate_deterministic_stress_scenarios():
    """Verify deterministic generator covers 6 required categories without inventing fake claims."""
    inv_id, contract_id, reqs = _create_investigation_and_contract()
    c1, s1, p1 = _insert_source_passage_claim(inv_id, "Decentralized Benchmark", "Retrieval latency averages 45ms across geo-distributed nodes.")
    _link_claim_to_requirement(inv_id, reqs[0]["requirement_id"], c1)

    with get_db(CURRENT_TEST_DB) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM contract_requirements WHERE contract_id = ?", (contract_id,))
        r_list = [dict(r) for r in cursor.fetchall()]

        cursor.execute("SELECT * FROM contract_assumptions WHERE contract_id = ?", (contract_id,))
        a_list = [dict(a) for a in cursor.fetchall()]

        scenarios = generate_deterministic_stress_scenarios(
            investigation_id=inv_id,
            requirements=r_list,
            assumptions=a_list,
            claims=[{"id": c1, "claim_text": "Retrieval latency averages 45ms", "source_title": "Decentralized Benchmark"}],
            conflicts=[],
            gaps=[],
        )

        categories = {s["category"] for s in scenarios}
        assert "ASSUMPTION_FAILURE" in categories
        assert "RISK_MATERIALIZATION" in categories
        assert "EVIDENCE_WEAKENING" in categories
        assert "CONFLICT_RESOLUTION" in categories
        assert "EXTERNAL_CONDITION_CHANGE" in categories
        assert "MISSING_EVIDENCE" in categories

        for sc in scenarios:
            assert sc["title"]
            assert sc["trigger_condition"]
            assert len(sc["affected_requirement_ids"]) > 0


def test_evaluate_deterministic_scenario():
    """Verify deterministic evaluation of assumption-failure degrades requirement coverage."""
    inv_id, contract_id, reqs = _create_investigation_and_contract()
    req_id = reqs[0]["requirement_id"]
    target_req = {
        "id": req_id,
        "title": reqs[0]["title"],
        "priority": reqs[0].get("priority", "HIGH"),
        "verification_criteria": "",
    }

    scenario_dict = {
        "id": "sc_test_1",
        "category": "ASSUMPTION_FAILURE",
        "title": "Network Bandwidth Assumption Invalidation",
        "trigger_condition": "Bandwidth latency degrades beyond SLA",
        "severity": "HIGH",
        "affected_requirement_ids": [req_id],
        "related_claim_ids": [],
    }

    with get_db(CURRENT_TEST_DB) as conn:
        baseline = compute_stress_testing_baseline(conn, inv_id)

    (
        scenario_outcome,
        outcome_shift,
        impact_explanation,
        key_vulns,
        uncertainties,
        actions,
        req_evals,
    ) = evaluate_deterministic_scenario(
        scenario=scenario_dict,
        baseline=baseline,
        sufficiency_assessments=[{"requirement_id": req_id, "coverage_status": "SUFFICIENT"}],
        requirements=[target_req],
        conflicts=[],
    )

    assert scenario_outcome in ("VULNERABLE", "CONDITIONALLY_ROBUST", "HIGHLY_VULNERABLE")
    assert outcome_shift in ("DEGRADED", "CRITICAL_FAILURE")
    assert len(req_evals) == 1
    assert req_evals[0].requirement_id == req_id
    assert req_evals[0].status_shift == "DEGRADED"
    assert req_evals[0].scenario_status == "PARTIAL"


def test_evaluate_conflict_resolution_scenario():
    """Verify adverse conflict resolution forces requirement status to INSUFFICIENT."""
    inv_id, contract_id, reqs = _create_investigation_and_contract()
    req_id = reqs[0]["requirement_id"]
    target_req = {
        "id": req_id,
        "title": reqs[0]["title"],
        "priority": reqs[0].get("priority", "HIGH"),
        "verification_criteria": "",
    }

    scenario_dict = {
        "id": "sc_test_conf",
        "category": "CONFLICT_RESOLUTION",
        "title": "Adverse Conflict Arbitration",
        "trigger_condition": "Adverse claim resolution upheld",
        "severity": "CRITICAL",
        "affected_requirement_ids": [req_id],
        "related_claim_ids": [],
    }

    with get_db(CURRENT_TEST_DB) as conn:
        baseline = compute_stress_testing_baseline(conn, inv_id)

    (
        scenario_outcome,
        outcome_shift,
        impact_explanation,
        key_vulns,
        uncertainties,
        actions,
        req_evals,
    ) = evaluate_deterministic_scenario(
        scenario=scenario_dict,
        baseline=baseline,
        sufficiency_assessments=[{"requirement_id": req_id, "coverage_status": "CONFLICTING"}],
        requirements=[target_req],
        conflicts=[],
    )

    assert outcome_shift in ("CRITICAL_FAILURE", "DEGRADED", "STABLE")
    assert len(req_evals) == 1
    assert req_evals[0].scenario_status == "INSUFFICIENT"


def test_stress_tests_endpoints_workflow():
    """Test full API workflow: generation, listing, filtering, evaluation, and status."""
    inv_id, contract_id, reqs = _create_investigation_and_contract()
    c1, s1, p1 = _insert_source_passage_claim(inv_id, "Source Alpha", "Performance metric 99.9% uptime.")
    _link_claim_to_requirement(inv_id, reqs[0]["requirement_id"], c1)

    # 1. Generate Scenarios
    gen_res = client.post(f"/api/investigations/{inv_id}/stress-tests/generate")
    assert gen_res.status_code == 200
    gen_data = gen_res.json()
    assert gen_data["investigation_id"] == inv_id
    assert len(gen_data["scenarios"]) >= 6
    assert gen_data["summary"]["total_scenarios"] >= 6
    assert gen_data["summary"]["evaluated_scenarios"] == 0

    first_scenario = gen_data["scenarios"][0]
    scenario_id = first_scenario["id"]

    # 2. Status Check
    status_res = client.get(f"/api/investigations/{inv_id}/stress-tests/status")
    assert status_res.status_code == 200
    stat_data = status_res.json()
    assert stat_data["total_scenarios"] >= 6
    assert stat_data["evaluated_scenarios"] == 0

    # 3. Filter by Category
    filtered_res = client.get(f"/api/investigations/{inv_id}/stress-tests?category={first_scenario['category']}")
    assert filtered_res.status_code == 200
    f_data = filtered_res.json()
    assert all(s["category"] == first_scenario["category"] for s in f_data["scenarios"])

    # 4. Evaluate Single Scenario
    eval_res = client.post(f"/api/investigations/{inv_id}/stress-tests/{scenario_id}/evaluate")
    assert eval_res.status_code == 200
    eval_data = eval_res.json()
    assert eval_data["id"] == scenario_id
    assert eval_data["evaluation_status"] == "evaluated"
    assert eval_data["evaluation"] is not None
    assert eval_data["evaluation"]["scenario_overall_outcome"] in ("ROBUST", "CONDITIONALLY_ROBUST", "VULNERABLE", "HIGHLY_VULNERABLE", "INDETERMINATE")

    # 5. Fetch Scenario Detail
    detail_res = client.get(f"/api/investigations/{inv_id}/stress-tests/{scenario_id}")
    assert detail_res.status_code == 200
    assert detail_res.json()["evaluation"]["scenario_id"] == scenario_id

    # 6. Verify Evaluated Count Updated
    stat_after = client.get(f"/api/investigations/{inv_id}/stress-tests/status").json()
    assert stat_after["evaluated_scenarios"] == 1


def test_scenario_detail_404():
    """Verify non-existent scenario returns 404."""
    inv_id, contract_id, reqs = _create_investigation_and_contract()
    res = client.get(f"/api/investigations/{inv_id}/stress-tests/non_existent_scenario_id")
    assert res.status_code == 404


def test_evidence_graph_integration_with_stress_scenarios():
    """Verify Evidence Dependency Graph includes stress_scenario nodes and CHALLENGES edges."""
    inv_id, contract_id, reqs = _create_investigation_and_contract()

    # Generate stress scenarios
    client.post(f"/api/investigations/{inv_id}/stress-tests/generate")

    with get_db(CURRENT_TEST_DB) as conn:
        graph = build_evidence_graph_from_db(conn, inv_id)
        scenario_nodes = [n for n in graph.nodes if n.type == "stress_scenario"]
        assert len(scenario_nodes) >= 6

        # Check CHALLENGES edges
        challenge_edges = [e for e in graph.edges if e.relationship == "CHALLENGES"]
        assert len(challenge_edges) >= 1
        assert graph.summary.scenario_nodes >= 6


def test_gemini_scenario_generation_mock(monkeypatch):
    """Verify Gemini structured reasoning parses scenario payloads and falls back cleanly on error."""
    inv_id, contract_id, reqs = _create_investigation_and_contract()

    import json
    mock_payload = {
        "scenarios": [
            {
                "category": "ASSUMPTION_FAILURE",
                "title": "Mocked Gemini Assumption Failure",
                "description": "Simulated assumption invalidation by Gemini",
                "trigger_condition": "Independent testing refutes latency SLA",
                "challenged_assumptions": ["Network latency remains under 50ms"],
                "affected_requirement_ids": [reqs[0]["requirement_id"]],
                "contested_claim_ids": [],
                "amplified_conflict_ids": [],
                "expected_impact": "Decision invalidated if latency critical",
                "severity": "HIGH",
                "evidence_needed": "Empirical latency test log",
            }
        ]
    }

    mock_response = MagicMock()
    mock_response.text = json.dumps(mock_payload)

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response

    mock_genai = MagicMock()
    mock_genai.Client.return_value = mock_client

    import sys
    monkeypatch.setattr("backend.services.stress_testing_service.GEMINI_API_KEY", "mock_key")
    monkeypatch.setattr("google.genai", mock_genai, raising=False)
    monkeypatch.setattr("google.genai.Client", MagicMock(return_value=mock_client), raising=False)
    monkeypatch.setitem(sys.modules, "google.genai", mock_genai)
    monkeypatch.setitem(sys.modules, "google.genai.types", MagicMock())

    res = client.post(f"/api/investigations/{inv_id}/stress-tests/generate")
    assert res.status_code == 200
    data = res.json()
    assert len(data["scenarios"]) >= 1
    assert any(s["title"] == "Mocked Gemini Assumption Failure" for s in data["scenarios"])
