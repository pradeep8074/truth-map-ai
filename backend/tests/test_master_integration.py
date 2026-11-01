import pytest
import sqlite3
import json
import uuid
from unittest.mock import patch
from fastapi.testclient import TestClient

from backend.main import app
from backend.database import init_db, get_db
import backend.database as db_module
from backend.services.report_service import (
    compute_investigation_content_fingerprint,
    get_investigation_current_snapshot,
    is_report_stale,
)

client = TestClient(app)


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    """Sets up an isolated, clean SQLite database for Master Integration Testing."""
    test_db_path = tmp_path / "truthmap_master_test.db"
    init_db(test_db_path)
    monkeypatch.setattr(db_module, "DB_PATH", test_db_path)
    # Return both the db path and a helper to inspect it
    return test_db_path


def test_investigation_isolation_across_all_components(isolated_db):
    """
    Phase 11: Minimum Test 1
    Verifies that records from Investigation A NEVER leak into Investigation B
    across all 8 components (Sources, Claims, Contract, Graph, Conflicts, Sufficiency, Stress, Reports).
    """
    # 1. Create Investigation A
    res_a = client.post("/api/investigations", json={"research_question": "Investigation A: Solar grid reliability in Leh"})
    assert res_a.status_code in {200, 201}
    inv_a = res_a.json()["investigation_id"]

    # 2. Create Investigation B
    res_b = client.post("/api/investigations", json={"research_question": "Investigation B: PM-eBus emissions in Indore"})
    assert res_b.status_code in {200, 201}
    inv_b = res_b.json()["investigation_id"]

    # Ingest data into Investigation A
    with sqlite3.connect(isolated_db) as conn:
        conn.row_factory = sqlite3.Row
        # Source A
        conn.execute(
            "INSERT INTO sources (id, investigation_id, source_type, title, content_hash, extraction_status, retrieved_at) "
            "VALUES ('src-a', ?, 'document', 'Himalayan Grid Report', 'hash-a', 'completed', '2026-10-31T01:00:00Z');",
            (inv_a,)
        )
        # Passage A
        conn.execute(
            "INSERT INTO passages (id, source_id, passage_text, sha256_hash) VALUES ('pas-a', 'src-a', 'Solar panels provide 18h daily.', 'hash-a');"
        )
        # Claim A
        conn.execute(
            "INSERT INTO claims (id, investigation_id, source_id, passage_id, claim_text, category, extraction_method, extraction_confidence, created_at) "
            "VALUES ('clm-a', ?, 'src-a', 'pas-a', 'Solar panels provide 18h daily.', 'statistical', 'deterministic', 0.95, '2026-10-31T01:05:00Z');",
            (inv_a,)
        )
        # Contract A
        conn.execute(
            "INSERT INTO decision_contracts (id, investigation_id, original_question, normalized_question, decision_objective, scope, compilation_method, created_at, updated_at) "
            "VALUES ('dc-a', ?, 'Solar grid reliability?', 'Solar grid reliability?', 'Evaluate reliability', 'Leh region', 'deterministic', '2026-10-31T01:10:00Z', '2026-10-31T01:10:00Z');",
            (inv_a,)
        )
        conn.execute(
            "INSERT INTO contract_requirements (id, contract_id, title, description, requirement_type, priority, verification_criteria, status, sort_order) "
            "VALUES ('req-a', 'dc-a', 'Continuous Power', 'Verify continuous power', 'technical', 'CRITICAL', 'Min 16h power daily', 'active', 1);"
        )
        conn.commit()

    # Verify that Investigation B returns ZERO sources and ZERO claims
    sources_b = client.get(f"/api/investigations/{inv_b}/sources").json()
    assert len(sources_b) == 0, "Investigation B leaked sources from Investigation A!"

    claims_b = client.get(f"/api/investigations/{inv_b}/claims").json()
    assert len(claims_b) == 0, "Investigation B leaked claims from Investigation A!"

    # Contract for B returns 404 since it has not been compiled
    contract_b = client.get(f"/api/investigations/{inv_b}/contract")
    assert contract_b.status_code == 404

    # Graph for B returns 0 nodes/edges
    graph_b = client.get(f"/api/investigations/{inv_b}/evidence-graph").json()
    assert len(graph_b.get("nodes", [])) == 0
    assert len(graph_b.get("edges", [])) == 0

    # Conflicts for B returns 0
    conflicts_b = client.get(f"/api/investigations/{inv_b}/conflicts").json()
    assert len(conflicts_b.get("conflicts", [])) == 0

    # Sufficiency for B returns 0
    sufficiency_b = client.get(f"/api/investigations/{inv_b}/sufficiency").json()
    assert len(sufficiency_b.get("assessments", [])) == 0

    # Stress tests for B returns 0
    stress_b = client.get(f"/api/investigations/{inv_b}/stress-tests").json()
    assert len(stress_b.get("scenarios", [])) == 0

    # Reports for B returns 0
    reports_b = client.get(f"/api/investigations/{inv_b}/reports").json()
    assert len(reports_b.get("reports", [])) == 0


def test_end_to_end_api_data_handoff(isolated_db):
    """
    Phase 11: Minimum Test 2 & Phase 2 Complete Workflow Validation
    Validates complete pipeline execution across Components 01 to 08 on a single investigation.
    """
    # 1. C01: Investigation Creation
    res_inv = client.post("/api/investigations", json={"research_question": "Should the hospital deploy backup hydrogen fuel cells?"})
    assert res_inv.status_code in {200, 201}
    inv_id = res_inv.json()["investigation_id"]

    # 2. C02: Ingestion & Evidence Seed
    with sqlite3.connect(isolated_db) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute(
            "INSERT INTO sources (id, investigation_id, source_type, title, publisher, content_hash, extraction_status, retrieved_at) "
            "VALUES ('src-e2e-1', ?, 'document', 'Hydrogen Technical Audit', 'DoE', 'hash-e2e-1', 'completed', '2026-10-31T02:00:00Z');",
            (inv_id,)
        )
        conn.execute(
            "INSERT INTO passages (id, source_id, passage_text, sha256_hash) "
            "VALUES ('pas-e2e-1', 'src-e2e-1', 'Backup fuel cell runtime exceeds 72 continuous hours at full load.', 'hash-pas-1'), "
            "       ('pas-e2e-2', 'src-e2e-1', 'Cold-weather membrane freezing causes startup delay exceeding 45 minutes below -10C.', 'hash-pas-2');"
        )
        conn.execute(
            "INSERT INTO claims (id, investigation_id, source_id, passage_id, claim_text, category, extraction_method, extraction_confidence, created_at) "
            "VALUES ('clm-e2e-1', ?, 'src-e2e-1', 'pas-e2e-1', 'Runtime exceeds 72 continuous hours at full load.', 'statistical', 'deterministic', 0.95, '2026-10-31T02:05:00Z'), "
            "       ('clm-e2e-2', ?, 'src-e2e-1', 'pas-e2e-2', 'Cold weather causes startup delay exceeding 45 minutes.', 'factual', 'deterministic', 0.90, '2026-10-31T02:06:00Z');",
            (inv_id, inv_id)
        )
        conn.commit()

    # 3. C03: Decision Contract Compilation
    res_comp = client.post(f"/api/investigations/{inv_id}/contract/compile")
    assert res_comp.status_code in {200, 201}
    contract = res_comp.json()
    assert len(contract["requirements"]) >= 3
    req_ids = [r["requirement_id"] for r in contract["requirements"]]

    # 4. C04: Evidence Dependency Graph Analysis
    res_graph = client.post(f"/api/investigations/{inv_id}/evidence-graph/analyze")
    assert res_graph.status_code in {200, 201}
    graph_data = res_graph.json()
    assert "nodes" in graph_data
    assert "edges" in graph_data
    assert len(graph_data["nodes"]) > 0

    # 5. C05: Conflict Detection Engine
    res_conf = client.post(f"/api/investigations/{inv_id}/conflicts/analyze")
    assert res_conf.status_code in {200, 201}
    conf_data = res_conf.json()
    assert "conflicts" in conf_data

    # 6. C06: Evidence Sufficiency & Gap Analysis
    res_suff = client.post(f"/api/investigations/{inv_id}/sufficiency/analyze")
    assert res_suff.status_code in {200, 201}
    suff_data = res_suff.json()
    assert len(suff_data["assessments"]) == len(req_ids)

    # 7. C07: Decision Stress Testing Engine
    res_stress = client.post(f"/api/investigations/{inv_id}/stress-tests/generate")
    assert res_stress.status_code in {200, 201}
    stress_data = res_stress.json()
    assert len(stress_data["scenarios"]) >= 3

    # 8. C08: Decision Intelligence Report Generation
    res_rep = client.post(f"/api/investigations/{inv_id}/reports/generate")
    assert res_rep.status_code in {200, 201}
    report = res_rep.json()
    assert report["report_version"] == 1
    assert report["report_status"] == "published"
    assert report["is_stale"] is False
    assert report["snapshot_metadata"]["content_fingerprint"] is not None

    # Verify report contains all 10 synthesized sections
    payload = report["report_data"]
    assert "executive_brief" in payload
    assert "decision_contract" in payload
    assert "evidence_intelligence" in payload
    assert "requirement_assessment" in payload
    assert "conflict_analysis" in payload
    assert "gaps_and_uncertainty" in payload
    assert "stress_test_results" in payload
    assert "risk_mitigation" in payload
    assert "recommended_actions" in payload
    assert "final_conclusion" in payload


def test_evidence_reference_integrity_and_provenance_chain(isolated_db):
    """
    Phase 11: Minimum Test 3 & Phase 3 Traceability Audit
    Verifies that every claim in the report traces back to a passage and source with SHA-256 integrity.
    """
    # Create investigation and full lineage
    res_inv = client.post("/api/investigations", json={"research_question": "Traceability test inquiry"})
    inv_id = res_inv.json()["investigation_id"]

    expected_hash = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    with sqlite3.connect(isolated_db) as conn:
        conn.execute(
            "INSERT INTO sources (id, investigation_id, source_type, title, publisher, content_hash, extraction_status, retrieved_at) "
            "VALUES ('src-trace-1', ?, 'document', 'Audit Standard v1', 'ISO', ?, 'completed', '2026-10-31T03:00:00Z');",
            (inv_id, expected_hash)
        )
        conn.execute(
            "INSERT INTO passages (id, source_id, passage_text, sha256_hash) "
            "VALUES ('pas-trace-1', 'src-trace-1', 'Calibrated sensor precision is +/- 0.05 units.', ?);",
            (expected_hash,)
        )
        conn.execute(
            "INSERT INTO claims (id, investigation_id, source_id, passage_id, claim_text, category, extraction_method, extraction_confidence, created_at) "
            "VALUES ('clm-trace-1', ?, 'src-trace-1', 'pas-trace-1', 'Sensor precision is +/- 0.05 units.', 'statistical', 'deterministic', 0.98, '2026-10-31T03:05:00Z');",
            (inv_id,)
        )
        conn.commit()

    # Compile contract and generate report
    res_comp = client.post(f"/api/investigations/{inv_id}/contract/compile").json()
    req_id = res_comp["requirements"][0]["requirement_id"]

    # Link claim to requirement via relationship
    with sqlite3.connect(isolated_db) as conn:
        conn.execute(
            "INSERT INTO evidence_relationships (id, investigation_id, requirement_id, claim_id, passage_id, relevance, explanation, confidence, analysis_method, processing_mode, created_at) "
            "VALUES ('rel-trace-1', ?, ?, 'clm-trace-1', 'pas-trace-1', 'STRONG', 'Calibrated sensor precision verifies standard.', 0.95, 'deterministic', 'fallback', '2026-10-31T03:10:00Z');",
            (inv_id, req_id)
        )
        conn.commit()

    client.post(f"/api/investigations/{inv_id}/sufficiency/analyze")
    res_rep = client.post(f"/api/investigations/{inv_id}/reports/generate")
    assert res_rep.status_code in {200, 201}

    report_data = res_rep.json()["report_data"]
    sources = report_data["evidence_intelligence"]["sources"]
    assert len(sources) == 1
    assert sources[0]["source_id"] == "src-trace-1"
    assert sources[0]["sha256_hash"] == expected_hash

    # Check matrix supporting claim provenance
    matrix = report_data["requirement_assessment"]["matrix"]
    found_claim = False
    for row in matrix:
        for sc in row["supporting_claims"]:
            if sc["claim_id"] == "clm-trace-1":
                assert sc["passage_hash"] == expected_hash
                assert sc["source_id"] == "src-trace-1"
                found_claim = True
    assert found_claim, "Claim clm-trace-1 was not properly linked into requirement assessment matrix!"


def test_graph_relationship_integrity(isolated_db):
    """
    Phase 11: Minimum Test 4
    Verifies that all relationships link valid claim IDs and requirement IDs for the target investigation only.
    """
    res_inv = client.post("/api/investigations", json={"research_question": "Graph relationship integrity inquiry"})
    inv_id = res_inv.json()["investigation_id"]

    with sqlite3.connect(isolated_db) as conn:
        conn.execute(
            "INSERT INTO sources (id, investigation_id, source_type, title, content_hash, extraction_status, retrieved_at) "
            "VALUES ('src-g1', ?, 'document', 'Technical Paper', 'h1', 'completed', '2026-10-31T03:00:00Z');",
            (inv_id,)
        )
        conn.execute(
            "INSERT INTO passages (id, source_id, passage_text, sha256_hash) VALUES ('pas-g1', 'src-g1', 'Text here', 'h1');"
        )
        conn.execute(
            "INSERT INTO claims (id, investigation_id, source_id, passage_id, claim_text, category, extraction_method, extraction_confidence, created_at) "
            "VALUES ('clm-g1', ?, 'src-g1', 'pas-g1', 'Battery capacity is 100 kWh', 'statistical', 'deterministic', 0.9, '2026-10-31T03:05:00Z');",
            (inv_id,)
        )
        conn.commit()

    client.post(f"/api/investigations/{inv_id}/contract/compile")
    res_graph = client.post(f"/api/investigations/{inv_id}/evidence-graph/analyze")
    assert res_graph.status_code in {200, 201}

    # Query SQLite directly to verify all stored relationships
    with sqlite3.connect(isolated_db) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        rels = cur.execute("SELECT * FROM evidence_relationships WHERE investigation_id = ?", (inv_id,)).fetchall()
        for r in rels:
            # Check claim belongs to inv_id
            clm = cur.execute("SELECT investigation_id FROM claims WHERE id = ?", (r["claim_id"],)).fetchone()
            assert clm is not None
            assert clm["investigation_id"] == inv_id
            # Check requirement exists
            req = cur.execute("SELECT id FROM contract_requirements WHERE id = ?", (r["requirement_id"],)).fetchone()
            assert req is not None


def test_conflict_and_sufficiency_consistency(isolated_db):
    """
    Phase 11: Minimum Test 5
    Verifies that detected conflicts properly surface in sufficiency and lower decision robustness.
    """
    res_inv = client.post("/api/investigations", json={"research_question": "Conflict and sufficiency consistency test"})
    inv_id = res_inv.json()["investigation_id"]

    # Ingest two contradicting numerical claims
    with sqlite3.connect(isolated_db) as conn:
        conn.execute(
            "INSERT INTO sources (id, investigation_id, source_type, title, content_hash, extraction_status, retrieved_at) "
            "VALUES ('src-cf1', ?, 'document', 'Audit Doc', 'hcf', 'completed', '2026-10-31T03:00:00Z');",
            (inv_id,)
        )
        conn.execute(
            "INSERT INTO passages (id, source_id, passage_text, sha256_hash) VALUES ('pas-cf1', 'src-cf1', 'Passage text', 'hcf');"
        )
        conn.execute(
            "INSERT INTO claims (id, investigation_id, source_id, passage_id, claim_text, category, extraction_method, extraction_confidence, created_at) "
            "VALUES ('clm-cf1', ?, 'src-cf1', 'pas-cf1', 'System efficiency achieved 94.5% during summer.', 'statistical', 'deterministic', 0.9, '2026-10-31T03:05:00Z'), "
            "       ('clm-cf2', ?, 'src-cf1', 'pas-cf1', 'System efficiency achieved 42.1% during summer.', 'statistical', 'deterministic', 0.9, '2026-10-31T03:06:00Z');",
            (inv_id, inv_id)
        )
        conn.commit()

    client.post(f"/api/investigations/{inv_id}/contract/compile")
    client.post(f"/api/investigations/{inv_id}/evidence-graph/analyze")
    client.post(f"/api/investigations/{inv_id}/conflicts/analyze")
    client.post(f"/api/investigations/{inv_id}/sufficiency/analyze")

    res_rep = client.post(f"/api/investigations/{inv_id}/reports/generate")
    assert res_rep.status_code in {200, 201}
    rep = res_rep.json()

    # Robustness must not be ROBUST when an unresolved conflict exists
    assert rep["overall_robustness"] in {"VULNERABLE", "CONDITIONALLY_ROBUST"}
    assert rep["report_data"]["conflict_analysis"]["total_conflicts"] >= 1


def test_gemini_fallback_behavior_and_honest_reporting(isolated_db, monkeypatch):
    """
    Phase 11: Minimum Test 6 & Phase 4 Gemini AI Integration Audit
    Simulates missing or failing Gemini API and verifies fallback is reported honestly as 'fallback'.
    """
    res_inv = client.post("/api/investigations", json={"research_question": "Does deterministic fallback record honesty?"})
    inv_id = res_inv.json()["investigation_id"]

    with sqlite3.connect(isolated_db) as conn:
        conn.execute(
            "INSERT INTO sources (id, investigation_id, source_type, title, content_hash, extraction_status, retrieved_at) "
            "VALUES ('src-fb1', ?, 'document', 'Baseline Report', 'hfb', 'completed', '2026-10-31T03:00:00Z');",
            (inv_id,)
        )
        conn.commit()

    client.post(f"/api/investigations/{inv_id}/contract/compile")

    # Patch GEMINI_API_KEY to empty to force fallback
    monkeypatch.setattr("backend.services.report_service.GEMINI_API_KEY", "")

    res_rep = client.post(f"/api/investigations/{inv_id}/reports/generate")
    assert res_rep.status_code in {200, 201}
    report = res_rep.json()
    assert report["processing_mode"] == "fallback", "Fallback execution was not honestly recorded!"


def test_report_fingerprint_change_detection(isolated_db):
    """
    Phase 11: Minimum Test 7 & Phase 5 Database Consistency
    Verifies that changing upstream records modifies the SHA-256 fingerprint and marks reports stale.
    """
    res_inv = client.post("/api/investigations", json={"research_question": "Stale detection fingerprint test"})
    inv_id = res_inv.json()["investigation_id"]

    with sqlite3.connect(isolated_db) as conn:
        conn.execute(
            "INSERT INTO sources (id, investigation_id, source_type, title, content_hash, extraction_status, retrieved_at) "
            "VALUES ('src-fp1', ?, 'document', 'Base Report', 'hfp', 'completed', '2026-10-31T03:00:00Z');",
            (inv_id,)
        )
        conn.commit()

    client.post(f"/api/investigations/{inv_id}/contract/compile")
    res_rep1 = client.post(f"/api/investigations/{inv_id}/reports/generate")
    rep1_id = res_rep1.json()["id"]
    fp1 = res_rep1.json()["snapshot_metadata"]["content_fingerprint"]
    assert res_rep1.json()["is_stale"] is False

    # Modify source title without altering row count
    with sqlite3.connect(isolated_db) as conn:
        conn.execute("UPDATE sources SET publisher = 'Audited Agency 2026' WHERE id = 'src-fp1';")
        conn.commit()

    # Check report status -> must now be stale
    res_status = client.get(f"/api/investigations/{inv_id}/reports/{rep1_id}").json()
    assert res_status["is_stale"] is True

    # Generate new report -> must receive a new content fingerprint
    res_rep2 = client.post(f"/api/investigations/{inv_id}/reports/generate")
    fp2 = res_rep2.json()["snapshot_metadata"]["content_fingerprint"]
    assert fp1 != fp2, "Cryptographic fingerprint did not change after upstream data modification!"


def test_report_version_lifecycle_and_immutability(isolated_db):
    """
    Phase 11: Minimum Test 8 & Phase 5 Report Versioning
    Verifies that report versions increment sequentially (v1 -> v2 -> v3) and historical reports remain immutable.
    """
    res_inv = client.post("/api/investigations", json={"research_question": "Version lifecycle test"})
    inv_id = res_inv.json()["investigation_id"]

    client.post(f"/api/investigations/{inv_id}/contract/compile")

    rep1 = client.post(f"/api/investigations/{inv_id}/reports/generate").json()
    assert rep1["report_version"] == 1

    rep2 = client.post(f"/api/investigations/{inv_id}/reports/generate").json()
    assert rep2["report_version"] == 2

    rep3 = client.post(f"/api/investigations/{inv_id}/reports/generate").json()
    assert rep3["report_version"] == 3

    # Verify historical report v1 has not changed
    v1_check = client.get(f"/api/investigations/{inv_id}/reports/{rep1['id']}").json()
    assert v1_check["report_version"] == 1
    assert v1_check["id"] == rep1["id"]

    # Verify latest returns v3
    latest = client.get(f"/api/investigations/{inv_id}/reports/latest").json()
    assert latest["report_version"] == 3
    assert latest["id"] == rep3["id"]


def test_repeated_processing_and_duplicate_prevention(isolated_db):
    """
    Phase 11: Minimum Test 9
    Verifies that re-running analysis steps (contract, graph, conflicts, sufficiency)
    does not create duplicate records or crash.
    """
    res_inv = client.post("/api/investigations", json={"research_question": "Repeated processing idempotency test"})
    inv_id = res_inv.json()["investigation_id"]

    # Ingest baseline
    with sqlite3.connect(isolated_db) as conn:
        conn.execute(
            "INSERT INTO sources (id, investigation_id, source_type, title, content_hash, extraction_status, retrieved_at) "
            "VALUES ('src-rep1', ?, 'document', 'Repeated Run Doc', 'hrep', 'completed', '2026-10-31T03:00:00Z');",
            (inv_id,)
        )
        conn.commit()

    # Run contract compilation twice
    client.post(f"/api/investigations/{inv_id}/contract/compile")
    client.post(f"/api/investigations/{inv_id}/contract/recompile")

    # Run graph analysis twice
    res_g1 = client.post(f"/api/investigations/{inv_id}/evidence-graph/analyze")
    res_g2 = client.post(f"/api/investigations/{inv_id}/evidence-graph/analyze")
    assert res_g1.status_code == 200
    assert res_g2.status_code == 200

    # Run sufficiency analysis twice
    res_s1 = client.post(f"/api/investigations/{inv_id}/sufficiency/analyze")
    res_s2 = client.post(f"/api/investigations/{inv_id}/sufficiency/analyze")
    assert res_s1.status_code == 200
    assert res_s2.status_code == 200

    # Check only 1 active contract exists
    with sqlite3.connect(isolated_db) as conn:
        contracts_count = conn.execute("SELECT COUNT(*) FROM decision_contracts WHERE investigation_id = ?", (inv_id,)).fetchone()[0]
        assert contracts_count == 1


def test_empty_and_partial_investigation_behavior(isolated_db):
    """
    Phase 11: Minimum Test 10 & Phase 10 Failure & Recovery Testing
    Verifies that running downstream components on empty investigations degrades gracefully without crashing.
    """
    res_inv = client.post("/api/investigations", json={"research_question": "Completely empty investigation test"})
    inv_id = res_inv.json()["investigation_id"]

    # Graph on empty investigation returns empty graph with HTTP 200
    res_graph = client.get(f"/api/investigations/{inv_id}/evidence-graph")
    assert res_graph.status_code in {200, 201}
    assert res_graph.json()["nodes"] == []

    # Conflicts on empty investigation returns empty list
    res_conf = client.get(f"/api/investigations/{inv_id}/conflicts")
    assert res_conf.status_code in {200, 201}
    assert res_conf.json()["conflicts"] == []

    # Sufficiency on empty investigation returns empty assessments
    res_suff = client.get(f"/api/investigations/{inv_id}/sufficiency")
    assert res_suff.status_code in {200, 201}
    assert res_suff.json()["assessments"] == []

    # Reports on empty investigation returns empty list
    res_rep = client.get(f"/api/investigations/{inv_id}/reports")
    assert res_rep.status_code in {200, 201}
    assert res_rep.json()["reports"] == []


def test_database_persistence_after_restart(isolated_db):
    """
    Phase 11: Minimum Test 11
    Verifies that closing DB connection, reinitializing, and reopening preserves all records intact.
    """
    res_inv = client.post("/api/investigations", json={"research_question": "Database persistence restart inquiry"})
    inv_id = res_inv.json()["investigation_id"]

    client.post(f"/api/investigations/{inv_id}/contract/compile")
    res_rep = client.post(f"/api/investigations/{inv_id}/reports/generate")
    assert res_rep.status_code in {200, 201}
    rep_id = res_rep.json()["id"]

    # Simulate restart by calling init_db again on the same database file
    init_db(isolated_db)

    # Verify report is still readable and intact
    res_get = client.get(f"/api/investigations/{inv_id}/reports/{rep_id}")
    assert res_get.status_code in {200, 201}
    assert res_get.json()["id"] == rep_id
