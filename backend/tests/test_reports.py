import pytest
import sqlite3
import json
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from backend.main import app
from backend.database import init_db, get_db
from backend.services.report_service import (
    generate_decision_report,
    get_investigation_reports,
    get_latest_investigation_report,
    get_report_by_id,
    get_report_status,
    is_report_stale,
    get_investigation_current_snapshot,
)

client = TestClient(app)


@pytest.fixture
def setup_test_investigation(tmp_path, monkeypatch):
    """Sets up a fully-wired investigation in a temporary SQLite database."""
    test_db = tmp_path / "test_truthmap_reports.db"
    init_db(test_db)
    monkeypatch.setattr("backend.database.DB_PATH", test_db)
    monkeypatch.setattr("backend.routers.reports.get_db", lambda: get_db(test_db))

    with sqlite3.connect(test_db) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # 1. Investigation
        inv_id = "inv-test-rpt"
        cursor.execute(
            "INSERT INTO investigations (id, research_question, status, created_at) VALUES (?, ?, ?, ?);",
            (inv_id, "Should we acquire HyperScale Cloud Infrastructure?", "active", "2026-10-31T00:00:00Z"),
        )

        # 2. Contract
        contract_id = "dc-test-rpt"
        cursor.execute(
            """INSERT INTO decision_contracts (
                id, investigation_id, original_question, normalized_question, decision_objective, scope, compilation_method, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);""",
            (
                contract_id,
                inv_id,
                "Should we acquire HyperScale Cloud?",
                "Should we acquire HyperScale Cloud Infrastructure?",
                "Authorize $45M strategic acquisition of HyperScale Cloud assets",
                "Infrastructure assets, IP, and recurring SaaS contracts",
                "deterministic",
                "2026-10-31T00:00:00Z",
                "2026-10-31T00:00:00Z",
            ),
        )

        # Requirements
        req_1 = "req-rpt-01"
        cursor.execute(
            """INSERT INTO contract_requirements (
                id, contract_id, title, description, requirement_type, priority, verification_criteria, status, sort_order
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);""",
            (
                req_1,
                contract_id,
                "Audited Recurring ARR Exceeds $10M",
                "Verify audited annualized recurring revenue",
                "financial",
                "HIGH",
                "GAAP audited financial audit statements",
                "verified",
                1,
            ),
        )

        req_2 = "req-rpt-02"
        cursor.execute(
            """INSERT INTO contract_requirements (
                id, contract_id, title, description, requirement_type, priority, verification_criteria, status, sort_order
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);""",
            (
                req_2,
                contract_id,
                "SOC-2 Type II Compliance & Security Zero Criticals",
                "Must possess clean compliance attestation",
                "technical",
                "HIGH",
                "SOC-2 Type II third party audit report",
                "unverified",
                2,
            ),
        )

        # Constraints & Assumptions
        cursor.execute(
            "INSERT INTO contract_constraints (id, contract_id, description, constraint_type) VALUES (?, ?, ?, ?);",
            ("con-rpt-01", contract_id, "Transaction close within Q4", "temporal"),
        )
        cursor.execute(
            "INSERT INTO contract_assumptions (id, contract_id, description, confidence, source, validation_status) VALUES (?, ?, ?, ?, ?, ?);",
            ("asm-rpt-01", contract_id, "Key engineering leadership retains post-acquisition", 0.85, "analyst", "pending"),
        )
        cursor.execute(
            "INSERT INTO contract_unresolved_questions (id, contract_id, question, clarification_type, dimension) VALUES (?, ?, ?, ?, ?);",
            ("unr-rpt-01", contract_id, "What is the churn rate in top 5 enterprise accounts?", "clarification", "financial"),
        )

        # 3. Sources & Passages & Claims
        s1 = "src-rpt-01"
        cursor.execute(
            """INSERT INTO sources (
                id, investigation_id, source_type, title, publisher, publication_date, retrieved_at, content_hash, extraction_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);""",
            (s1, inv_id, "document", "Q3 2026 HyperScale Financial Audit Report", "Ernst & Young", "2026-09-30", "2026-10-31T00:00:00Z", "hash_ey_123", "completed"),
        )

        p1 = "pas-rpt-01"
        cursor.execute(
            """INSERT INTO passages (
                id, source_id, passage_text, sha256_hash
            ) VALUES (?, ?, ?, ?);""",
            (p1, s1, "HyperScale achieved $11.4M ARR with positive operating cash flow.", "hash_p1_sha256"),
        )

        cl1 = "clm-rpt-01"
        cursor.execute(
            """INSERT INTO claims (
                id, investigation_id, source_id, passage_id, claim_text, category, extraction_method, extraction_confidence, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);""",
            (cl1, inv_id, s1, p1, "HyperScale ARR reached $11.4M with positive operating cash flow.", "statistical", "deterministic", 0.95, "2026-10-31T00:00:00Z"),
        )

        # Evidence relationship
        cursor.execute(
            """INSERT INTO evidence_relationships (
                id, investigation_id, requirement_id, claim_id, passage_id, relevance, explanation, confidence, analysis_method, processing_mode, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);""",
            ("rel-rpt-01", inv_id, req_1, cl1, p1, "STRONG", "Proves ARR exceeds $10M threshold.", 0.95, "fallback", "fallback", "2026-10-31T00:00:00Z"),
        )

        # 4. Conflicts
        cursor.execute(
            """INSERT INTO evidence_conflicts (
                id, investigation_id, claim_a_id, claim_b_id, conflict_type, severity, explanation, confidence, resolution_status, recommended_action, analysis_method, processing_mode, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);""",
            (
                "cnf-rpt-01",
                inv_id,
                cl1,
                cl1,
                "numerical_conflict",
                "medium",
                "Minor variance in reported EBITDA margin.",
                0.8,
                "unresolved",
                "Reconcile net vs gross margin.",
                "deterministic",
                "fallback",
                "2026-10-31T00:00:00Z",
                "2026-10-31T00:00:00Z",
            ),
        )

        # 5. Sufficiency
        cursor.execute(
            """INSERT INTO evidence_sufficiency_assessments (
                id, investigation_id, requirement_id, coverage_status, assessment_summary, recommended_action, confidence, analysis_method, processing_mode, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);""",
            (
                "suf-rpt-01",
                inv_id,
                req_1,
                "SUFFICIENT",
                "Audited revenue confirms ARR requirement is satisfied.",
                "Maintain audit proof in dossier.",
                0.95,
                "deterministic",
                "fallback",
                "2026-10-31T00:00:00Z",
                "2026-10-31T00:00:00Z",
            ),
        )

        cursor.execute(
            """INSERT INTO evidence_gaps (
                id, investigation_id, requirement_id, assessment_id, gap_description, why_it_matters, evidence_needed, suggested_source_type, priority, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);""",
            (
                "gap-rpt-01",
                inv_id,
                req_2,
                "suf-rpt-01",
                "Missing current year SOC-2 Type II audit certificate",
                "Unverified cybersecurity posture exposes infrastructure to liability",
                "Current SOC-2 Type II audit report signed by certified CPA",
                "Independent Compliance Audit",
                "HIGH",
                "2026-10-31T00:00:00Z",
            ),
        )

        # 6. Stress Scenario & Evaluation
        sc1 = "sc-rpt-01"
        cursor.execute(
            """INSERT INTO decision_stress_scenarios (
                id, investigation_id, title, category, description, trigger_condition, affected_requirement_ids, expected_impact, severity, evidence_needed, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);""",
            (
                sc1,
                inv_id,
                "Top 2 Enterprise Customer Churn Event",
                "RISK_MATERIALIZATION",
                "Two major enterprise contracts expire without renewal.",
                "Customer cancellation notice served before closing",
                json.dumps([req_1]),
                "Reduces ARR by $3.5M, falling below $10M threshold.",
                "CRITICAL",
                "Customer renewal confirmations.",
                "2026-10-31T00:00:00Z",
            ),
        )

        cursor.execute(
            """INSERT INTO decision_stress_evaluations (
                id, scenario_id, investigation_id, baseline_overall_outcome, scenario_overall_outcome, outcome_shift, impact_explanation, key_vulnerabilities, evaluated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);""",
            (
                "eval-rpt-01",
                sc1,
                inv_id,
                "CONDITIONALLY_ROBUST",
                "VULNERABLE",
                "CRITICAL_FAILURE",
                "ARR falls below minimum acquisition hurdle.",
                json.dumps(["High customer concentration in top 2 enterprise accounts."]),
                "2026-10-31T00:00:00Z",
            ),
        )

        conn.commit()

    yield {
        "db_path": test_db,
        "investigation_id": inv_id,
    }


def test_generate_report_with_deterministic_fallback(setup_test_investigation):
    """Verifies complete 10-section generation, versioning, and structure."""
    inv_id = setup_test_investigation["investigation_id"]

    res = client.post(f"/api/investigations/{inv_id}/reports/generate")
    assert res.status_code == 200, res.text
    data = res.json()

    assert data["investigation_id"] == inv_id
    assert data["report_version"] == 1
    assert data["report_status"] == "published"
    assert data["overall_robustness"] in {"ROBUST", "CONDITIONALLY_ROBUST", "VULNERABLE", "HIGHLY_VULNERABLE", "INDETERMINATE"}
    assert data["is_stale"] is False

    # Check 10 sections
    rd = data["report_data"]
    assert "executive_brief" in rd
    assert "decision_contract" in rd
    assert "evidence_intelligence" in rd
    assert "requirement_assessment" in rd
    assert "conflict_analysis" in rd
    assert "gaps_and_uncertainty" in rd
    assert "stress_test_results" in rd
    assert "risk_mitigation" in rd
    assert "recommended_actions" in rd
    assert "final_conclusion" in rd

    # Section 1: Executive Brief
    eb = rd["executive_brief"]
    assert eb["total_sources"] == 1
    assert eb["total_claims"] == 1
    assert eb["unresolved_conflicts_count"] == 1
    assert eb["identified_gaps_count"] == 1
    assert eb["report_version"] == 1

    # Section 2: Decision Contract
    dc = rd["decision_contract"]
    assert len(dc["requirements"]) == 2
    assert len(dc["constraints"]) == 1
    assert len(dc["assumptions"]) == 1

    # Section 3: Evidence Intelligence
    ei = rd["evidence_intelligence"]
    assert len(ei["sources"]) == 1
    assert ei["sources"][0]["sha256_hash"] == "hash_ey_123"

    # Section 4: Requirement Assessment
    ra = rd["requirement_assessment"]
    assert len(ra["matrix"]) == 2
    req_01 = next(r for r in ra["matrix"] if r["requirement_id"] == "req-rpt-01")
    assert req_01["coverage_status"] == "SUFFICIENT"
    assert len(req_01["supporting_claims"]) == 1

    # Section 5: Conflict Analysis
    ca = rd["conflict_analysis"]
    assert ca["total_conflicts"] == 1
    assert ca["unresolved_count"] == 1

    # Section 6: Gaps and Uncertainty
    gu = rd["gaps_and_uncertainty"]
    assert gu["total_gaps"] == 1
    assert gu["gaps"][0]["priority"] == "HIGH"

    # Section 7: Stress Test Results
    st = rd["stress_test_results"]
    assert st["total_scenarios"] == 1
    assert len(st["scenarios"]) == 1
    assert st["scenarios"][0]["outcome_shift"] == "CRITICAL_FAILURE"

    # Section 8: Risk Mitigation Register
    rm = rd["risk_mitigation"]
    assert rm["total_risks"] >= 1
    assert any(r["origin"] == "Conflict" for r in rm["risks"])

    # Section 9: Recommended Actions
    act = rd["recommended_actions"]
    assert len(act["actions"]) >= 1

    # Section 10: Final Conclusion
    fc = rd["final_conclusion"]
    assert len(fc["supported_findings"]) >= 1
    assert "EPISTEMIC BOUNDARY DISCLAIMER" in fc["epistemic_boundary_disclaimer"]


def test_report_versioning_and_list_endpoints(setup_test_investigation):
    """Verifies that multiple generations increment version and preserve history."""
    inv_id = setup_test_investigation["investigation_id"]

    # Generate v1
    res1 = client.post(f"/api/investigations/{inv_id}/reports/generate")
    assert res1.status_code == 200
    v1_data = res1.json()
    assert v1_data["report_version"] == 1

    # Generate v2
    res2 = client.post(f"/api/investigations/{inv_id}/reports/generate")
    assert res2.status_code == 200
    v2_data = res2.json()
    assert v2_data["report_version"] == 2
    assert v2_data["id"] != v1_data["id"]

    # List reports
    list_res = client.get(f"/api/investigations/{inv_id}/reports")
    assert list_res.status_code == 200
    list_data = list_res.json()
    assert list_data["total_reports"] == 2
    assert list_data["latest_version"] == 2
    assert len(list_data["reports"]) == 2

    # Fetch latest
    latest_res = client.get(f"/api/investigations/{inv_id}/reports/latest")
    assert latest_res.status_code == 200
    latest_data = latest_res.json()
    assert latest_data["report_version"] == 2

    # Fetch specific v1
    v1_res = client.get(f"/api/investigations/{inv_id}/reports/{v1_data['id']}")
    assert v1_res.status_code == 200
    assert v1_res.json()["report_version"] == 1


def test_mandatory_stale_detection_scenarios(setup_test_investigation):
    """
    Mandatory quality hardening: verifies content-based fingerprint staleness detection
    across all 7 required scenarios.
    """
    inv_id = setup_test_investigation["investigation_id"]
    db_path = setup_test_investigation["db_path"]

    # Baseline: Generate fresh report
    res0 = client.post(f"/api/investigations/{inv_id}/reports/generate")
    assert res0.status_code == 200
    report_id = res0.json()["id"]
    assert res0.json()["is_stale"] is False

    # Scenario 1: Add a new source -> report becomes stale
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO sources (id, investigation_id, source_type, title, retrieved_at, extraction_status) "
            "VALUES ('src-extra-01', ?, 'document', 'Extra Disclosure', '2026-10-31T01:00:00Z', 'completed');",
            (inv_id,)
        )
        conn.commit()

    detail = client.get(f"/api/investigations/{inv_id}/reports/{report_id}").json()
    assert detail["is_stale"] is True, "Scenario 1 failed: Adding a source should mark report stale"

    # Reset with new version
    res1 = client.post(f"/api/investigations/{inv_id}/reports/generate")
    report_id = res1.json()["id"]
    assert res1.json()["is_stale"] is False

    # Scenario 2: Modify existing source record without changing row count -> report becomes stale
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE sources SET publisher = 'PricewaterhouseCoopers' WHERE id = 'src-rpt-01';"
        )
        conn.commit()

    detail = client.get(f"/api/investigations/{inv_id}/reports/{report_id}").json()
    assert detail["is_stale"] is True, "Scenario 2 failed: Modifying source attributes without row count change should mark report stale"

    # Reset with new version
    res2 = client.post(f"/api/investigations/{inv_id}/reports/generate")
    report_id = res2.json()["id"]
    assert res2.json()["is_stale"] is False

    # Scenario 3: Update an existing conflict resolution -> report becomes stale
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE evidence_conflicts SET resolution_status = 'resolved_claim_a_valid', reviewer_notes = 'Audited GAAP overrides' "
            "WHERE id = 'cnf-rpt-01';"
        )
        conn.commit()

    detail = client.get(f"/api/investigations/{inv_id}/reports/{report_id}").json()
    assert detail["is_stale"] is True, "Scenario 3 failed: Updating conflict resolution status should mark report stale"

    # Reset with new version
    res3 = client.post(f"/api/investigations/{inv_id}/reports/generate")
    report_id = res3.json()["id"]
    assert res3.json()["is_stale"] is False

    # Scenario 4: Modify a sufficiency assessment -> report becomes stale
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE evidence_sufficiency_assessments SET coverage_status = 'PARTIAL' WHERE id = 'suf-rpt-01';"
        )
        conn.commit()

    detail = client.get(f"/api/investigations/{inv_id}/reports/{report_id}").json()
    assert detail["is_stale"] is True, "Scenario 4 failed: Modifying sufficiency coverage status should mark report stale"

    # Reset with new version
    res4 = client.post(f"/api/investigations/{inv_id}/reports/generate")
    report_id = res4.json()["id"]
    assert res4.json()["is_stale"] is False

    # Scenario 5: Modify a stress-test evaluation -> report becomes stale
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE decision_stress_evaluations SET outcome_shift = 'STABLE', scenario_overall_outcome = 'ROBUST' "
            "WHERE id = 'eval-rpt-01';"
        )
        conn.commit()

    detail = client.get(f"/api/investigations/{inv_id}/reports/{report_id}").json()
    assert detail["is_stale"] is True, "Scenario 5 failed: Modifying stress evaluation should mark report stale"

    # Reset with new version
    res5 = client.post(f"/api/investigations/{inv_id}/reports/generate")
    report_id = res5.json()["id"]
    assert res5.json()["is_stale"] is False

    # Scenario 6: Change the decision contract -> report becomes stale
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE decision_contracts SET decision_objective = 'Authorize restructured $35M strategic acquisition' "
            "WHERE investigation_id = ?;",
            (inv_id,)
        )
        conn.commit()

    detail = client.get(f"/api/investigations/{inv_id}/reports/{report_id}").json()
    assert detail["is_stale"] is True, "Scenario 6 failed: Changing decision contract objective should mark report stale"

    # Reset with new version
    res6 = client.post(f"/api/investigations/{inv_id}/reports/generate")
    report_id = res6.json()["id"]
    assert res6.json()["is_stale"] is False

    # Scenario 7: Irrelevant report-viewing actions -> report remains current
    _ = client.get(f"/api/investigations/{inv_id}/reports/status")
    _ = client.get(f"/api/investigations/{inv_id}/reports")
    _ = client.get(f"/api/investigations/{inv_id}/reports/latest")
    read_again = client.get(f"/api/investigations/{inv_id}/reports/{report_id}").json()
    assert read_again["is_stale"] is False, "Scenario 7 failed: Reading or listing reports must NOT mark reports stale"


def test_mandatory_report_versioning_lifecycle(tmp_path, monkeypatch):
    """
    Mandatory quality hardening: verifies versioning sequence in an isolated investigation:
    1. Generate v1.
    2. Confirm latest is v1 with same ID.
    3. Generate v2.
    4. Confirm latest is v2 with same ID.
    5. List history and verify versions 1 and 2.
    6. Retrieve v1 and verify content remains immutable.
    Prints actual IDs and versions.
    """
    test_db = tmp_path / "test_iso_versioning.db"
    init_db(test_db)
    monkeypatch.setattr("backend.database.DB_PATH", test_db)
    monkeypatch.setattr("backend.routers.reports.get_db", lambda: get_db(test_db))

    iso_inv_id = "inv-iso-version-test"
    with sqlite3.connect(test_db) as conn:
        conn.execute(
            "INSERT INTO investigations (id, research_question, status, created_at) "
            "VALUES (?, 'Isolated Versioning Inquiry', 'active', '2026-10-31T00:00:00Z');",
            (iso_inv_id,)
        )
        conn.commit()

    # 1. Generate version 1
    v1_res = client.post(f"/api/investigations/{iso_inv_id}/reports/generate")
    assert v1_res.status_code == 200
    v1_data = v1_res.json()
    v1_id = v1_data["id"]
    v1_ver = v1_data["report_version"]
    print(f"\n[Isolated Test] Generated v1: ID={v1_id}, Version={v1_ver}")
    assert v1_ver == 1

    # 2. Retrieve latest and confirm v1
    latest_1_res = client.get(f"/api/investigations/{iso_inv_id}/reports/latest")
    assert latest_1_res.status_code == 200
    latest_1 = latest_1_res.json()
    print(f"[Isolated Test] Retrieved latest: ID={latest_1['id']}, Version={latest_1['report_version']}")
    assert latest_1["id"] == v1_id
    assert latest_1["report_version"] == 1

    # 3. Generate version 2
    v2_res = client.post(f"/api/investigations/{iso_inv_id}/reports/generate")
    assert v2_res.status_code == 200
    v2_data = v2_res.json()
    v2_id = v2_data["id"]
    v2_ver = v2_data["report_version"]
    print(f"[Isolated Test] Generated v2: ID={v2_id}, Version={v2_ver}")
    assert v2_ver == 2
    assert v2_id != v1_id

    # 4. Retrieve latest and confirm v2
    latest_2_res = client.get(f"/api/investigations/{iso_inv_id}/reports/latest")
    assert latest_2_res.status_code == 200
    latest_2 = latest_2_res.json()
    print(f"[Isolated Test] Retrieved latest: ID={latest_2['id']}, Version={latest_2['report_version']}")
    assert latest_2["id"] == v2_id
    assert latest_2["report_version"] == 2

    # 5. List history and verify versions 1 and 2
    list_res = client.get(f"/api/investigations/{iso_inv_id}/reports")
    assert list_res.status_code == 200
    history = list_res.json()
    print(f"[Isolated Test] Historical reports count={history['total_reports']}, latest_v={history['latest_version']}")
    assert history["total_reports"] == 2
    assert history["latest_version"] == 2
    assert history["reports"][0]["id"] == v2_id
    assert history["reports"][0]["report_version"] == 2
    assert history["reports"][1]["id"] == v1_id
    assert history["reports"][1]["report_version"] == 1

    # 6. Retrieve version 1 and verify content remains immutable
    v1_check = client.get(f"/api/investigations/{iso_inv_id}/reports/{v1_id}").json()
    assert v1_check["id"] == v1_id
    assert v1_check["report_version"] == 1
    assert v1_check["created_at"] == v1_data["created_at"]
    print(f"[Isolated Test] Version 1 content confirmed immutable: ID={v1_check['id']}")


def test_stale_report_detection(setup_test_investigation):
    """Verifies that is_stale becomes True when upstream components change."""
    inv_id = setup_test_investigation["investigation_id"]
    db_path = setup_test_investigation["db_path"]

    # Generate report
    gen_res = client.post(f"/api/investigations/{inv_id}/reports/generate")
    assert gen_res.status_code == 200
    report_id = gen_res.json()["id"]

    # Initial status check: fresh
    status_res1 = client.get(f"/api/investigations/{inv_id}/reports/status")
    assert status_res1.status_code == 200
    assert status_res1.json()["is_stale"] is False

    # Simulate upstream change: insert a new source
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """INSERT INTO sources (
                id, investigation_id, source_type, title, retrieved_at, extraction_status
            ) VALUES (?, ?, ?, ?, ?, ?);""",
            ("src-new-upstream", inv_id, "document", "New Audit Addendum", "2026-10-31T01:00:00Z", "completed"),
        )
        conn.commit()

    # Status check: should now be stale
    status_res2 = client.get(f"/api/investigations/{inv_id}/reports/status")
    assert status_res2.status_code == 200
    assert status_res2.json()["is_stale"] is True

    # Report fetch should also reflect is_stale: True
    detail_res = client.get(f"/api/investigations/{inv_id}/reports/{report_id}")
    assert detail_res.status_code == 200
    assert detail_res.json()["is_stale"] is True


def test_invalid_investigation_returns_404(setup_test_investigation):
    """Verifies 404 behavior for non-existent investigations."""
    res = client.post("/api/investigations/inv-nonexistent/reports/generate")
    assert res.status_code == 404

    res2 = client.get("/api/investigations/inv-nonexistent/reports/latest")
    assert res2.status_code == 404

    res3 = client.get("/api/investigations/inv-nonexistent/reports/rpt-invalid")
    assert res3.status_code == 404


def test_gemini_synthesis_mock(setup_test_investigation):
    """Verifies structured synthesis when Gemini API responds."""
    inv_id = setup_test_investigation["investigation_id"]

    mock_gemini_payload = {
        "executive_conclusion": "HyperScale Cloud presents a conditionally viable acquisition candidate with verified financial ARR of $11.4M.",
        "reliability_limitations": "Primary gap: SOC-2 Type II audit remains unverified.",
        "risks": [
            {
                "risk_id": "RISK-01",
                "title": "Customer Concentration Stress",
                "origin": "Stress Scenario",
                "severity": "CRITICAL",
                "affected_requirement": "req-rpt-01",
                "consequence": "Severe ARR degradation under top customer churn.",
                "mitigation": "Structure earnout tied to 12-month enterprise retention.",
                "additional_evidence_needed": "Enterprise contract renewal logs.",
            }
        ],
        "actions": [
            {
                "action_id": "ACT-01",
                "action_title": "Demand SOC-2 Type II Attestation",
                "description": "Condition closing on delivery of clean audit.",
                "priority": "P1_IMMEDIATE",
                "driver": "Cybersecurity compliance requirement.",
                "target_requirement": "req-rpt-02",
                "expected_outcome": "Definitive verification of technical compliance.",
            }
        ],
        "supported_findings": ["Audited revenue threshold satisfied at $11.4M."],
        "uncertainties_and_caveats": ["Cybersecurity posture unverified."],
        "invalidating_conditions": ["Loss of either top enterprise customer."],
        "recommended_decision_posture": "PROCEED_WITH_SAFEGUARDS",
    }

    mock_response = MagicMock()
    mock_response.text = json.dumps(mock_gemini_payload)

    with patch("backend.services.report_service.GEMINI_API_KEY", "mock-test-key"):
        with patch("google.genai.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.models.generate_content.return_value = mock_response
            mock_client_cls.return_value = mock_client

            res = client.post(f"/api/investigations/{inv_id}/reports/generate")
            assert res.status_code == 200
            data = res.json()
            assert data["processing_mode"] == "gemini"
            assert "conditionally viable" in data["executive_summary"]
            assert data["report_data"]["final_conclusion"]["recommended_decision_posture"] == "PROCEED_WITH_SAFEGUARDS"
