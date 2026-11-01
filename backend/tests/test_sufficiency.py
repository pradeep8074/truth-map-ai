import pytest
import uuid
import datetime
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from backend.main import app
from backend.database import init_db, get_db

client = TestClient(app)

CURRENT_TEST_DB = None


@pytest.fixture(autouse=True)
def setup_test_database(tmp_path, monkeypatch):
    """Initializes a fresh isolated SQLite database for each test run."""
    global CURRENT_TEST_DB
    test_db = tmp_path / "test_truthmap_sufficiency.db"
    CURRENT_TEST_DB = test_db
    init_db(test_db)
    monkeypatch.setattr("backend.database.DB_PATH", test_db)
    monkeypatch.setattr("backend.routers.investigations.get_db", lambda: get_db(test_db))
    monkeypatch.setattr("backend.routers.sources.get_db", lambda: get_db(test_db))
    monkeypatch.setattr("backend.routers.contracts.get_db", lambda: get_db(test_db))
    monkeypatch.setattr("backend.routers.graph.get_db", lambda: get_db(test_db))
    monkeypatch.setattr("backend.routers.conflicts.get_db", lambda: get_db(test_db))
    monkeypatch.setattr("backend.routers.sufficiency.get_db", lambda: get_db(test_db))
    # Keep contract compiler instant
    monkeypatch.setattr("backend.services.contract_compiler.GEMINI_API_KEY", "")


def _create_investigation_and_contract():
    """Helper to create investigation, decision contract, and requirements."""
    res = client.post("/api/investigations", json={
        "research_question": "Does solar microgrid deployment improve continuous power reliability in rural communities?"
    })
    assert res.status_code == 201
    inv_id = res.json()["investigation_id"]

    # Compile contract
    c_res = client.post(f"/api/investigations/{inv_id}/contract/compile")
    assert c_res.status_code == 201
    contract_data = c_res.json()
    reqs = contract_data["requirements"]
    return inv_id, contract_data["contract_id"], reqs


def _insert_source_passage_claim(inv_id: str, title: str, claim_text: str, passage_text: str):
    """Inserts a source, passage, and claim into test database."""
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
            VALUES (?, ?, ?, 1, 1, 'mocked_sha256_sufficiency');
        """, (pas_id, src_id, passage_text))

        cursor.execute("""
            INSERT INTO claims (id, investigation_id, source_id, passage_id, claim_text, category, extraction_method, extraction_confidence, created_at)
            VALUES (?, ?, ?, ?, ?, 'factual', 'deterministic', 0.95, ?);
        """, (clm_id, inv_id, src_id, pas_id, claim_text, now))

        conn.commit()
        return clm_id, src_id, pas_id


def _link_claim_to_requirement(inv_id: str, req_id: str, claim_id: str, relevance: str = "DIRECTLY_RELEVANT"):
    """Links a claim to a requirement in evidence_relationships."""
    with get_db(CURRENT_TEST_DB) as conn:
        cursor = conn.cursor()
        rel_id = f"rel_{uuid.uuid4().hex[:8]}"
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        cursor.execute("""
            INSERT INTO evidence_relationships (
                id, investigation_id, requirement_id, claim_id,
                relevance, explanation, confidence, analysis_method, processing_mode, created_at
            ) VALUES (?, ?, ?, ?, ?, 'Direct factual verification', 0.92, 'test_manual', 'fallback', ?);
        """, (rel_id, inv_id, req_id, claim_id, relevance, now))
        conn.commit()


def _insert_conflict(inv_id: str, claim_a_id: str, claim_b_id: str, status: str = "unresolved"):
    """Inserts a conflict record between two claims."""
    with get_db(CURRENT_TEST_DB) as conn:
        cursor = conn.cursor()
        conf_id = f"conf_{uuid.uuid4().hex[:8]}"
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        cursor.execute("""
            INSERT INTO evidence_conflicts (
                id, investigation_id, claim_a_id, claim_b_id,
                conflict_type, severity, explanation, confidence,
                resolution_status, reviewer_notes, recommended_action,
                analysis_method, processing_mode, created_at, updated_at
            ) VALUES (?, ?, ?, ?, 'NUMERICAL_CONFLICT', 'CRITICAL', 'Direct numerical clash in uptime hours.', 0.95, ?, '', 'Audit protocols', 'test', 'fallback', ?, ?);
        """, (conf_id, inv_id, claim_a_id, claim_b_id, status, now, now))
        conn.commit()
        return conf_id


def test_requirement_with_no_linked_evidence_returns_no_evidence(monkeypatch):
    monkeypatch.setattr("backend.services.sufficiency_service.GEMINI_API_KEY", "")

    inv_id, contract_id, reqs = _create_investigation_and_contract()

    # Run Sufficiency Analysis
    res = client.post(f"/api/investigations/{inv_id}/sufficiency/analyze")
    assert res.status_code == 200
    data = res.json()

    assert data["investigation_id"] == inv_id
    assert data["processing_mode"] == "fallback"
    assert len(data["assessments"]) == len(reqs)

    # Every requirement has 0 claims, so all must be NO_EVIDENCE
    for asm in data["assessments"]:
        assert asm["coverage_status"] == "NO_EVIDENCE"
        assert asm["confidence"] == 1.0
        assert len(asm["supporting_claims"]) == 0
        assert len(asm["gaps"]) >= 1
        assert asm["gaps"][0]["priority"] in {"HIGH", "MEDIUM"}

    assert data["summary"]["no_evidence_count"] == len(reqs)
    assert data["summary"]["sufficient_count"] == 0


def test_requirement_with_single_source_claim_returns_partial(monkeypatch):
    monkeypatch.setattr("backend.services.sufficiency_service.GEMINI_API_KEY", "")

    inv_id, contract_id, reqs = _create_investigation_and_contract()
    target_req = reqs[0]

    # Ingest one claim
    clm_id, src_id, _ = _insert_source_passage_claim(
        inv_id,
        "Energy Ministry Report 2024",
        "Solar microgrid installations increased continuous electricity availability to 19 hours daily.",
        "Our audit showed solar microgrid installations increased continuous electricity availability to 19 hours daily."
    )
    _link_claim_to_requirement(inv_id, target_req["requirement_id"], clm_id, relevance="DIRECTLY_RELEVANT")

    res = client.post(f"/api/investigations/{inv_id}/sufficiency/analyze")
    assert res.status_code == 200
    data = res.json()

    target_asm = next(a for a in data["assessments"] if a["requirement_id"] == target_req["requirement_id"])
    assert target_asm["coverage_status"] == "PARTIAL"
    assert "Energy Ministry Report 2024" in target_asm["limitations"]
    assert len(target_asm["gaps"]) >= 1
    assert target_asm["gaps"][0]["priority"] == "MEDIUM"


def test_requirement_with_multi_source_corroboration_returns_sufficient(monkeypatch):
    monkeypatch.setattr("backend.services.sufficiency_service.GEMINI_API_KEY", "")

    inv_id, contract_id, reqs = _create_investigation_and_contract()
    target_req = reqs[0]

    # Ingest two independent claims from distinct sources
    c1, _, _ = _insert_source_passage_claim(
        inv_id,
        "Source A: State Energy Grid",
        "Microgrids delivered 18.5 hours of continuous power per day across 84 villages.",
        "Telemetry data confirmed microgrids delivered 18.5 hours of continuous power per day."
    )
    c2, _, _ = _insert_source_passage_claim(
        inv_id,
        "Source B: Independent Academic Survey",
        "Independent telemetry verified daily power availability averaged 19.1 hours across tested microgrid regions.",
        "Independent telemetry verified daily power availability averaged 19.1 hours."
    )

    _link_claim_to_requirement(inv_id, target_req["requirement_id"], c1, relevance="DIRECTLY_RELEVANT")
    _link_claim_to_requirement(inv_id, target_req["requirement_id"], c2, relevance="DIRECTLY_RELEVANT")

    res = client.post(f"/api/investigations/{inv_id}/sufficiency/analyze")
    assert res.status_code == 200
    data = res.json()

    target_asm = next(a for a in data["assessments"] if a["requirement_id"] == target_req["requirement_id"])
    assert target_asm["coverage_status"] == "SUFFICIENT"
    assert len(target_asm["supporting_claims"]) == 2
    assert "Adequately corroborated" in target_asm["assessment_summary"]


def test_requirement_affected_by_unresolved_conflict_returns_conflicting(monkeypatch):
    monkeypatch.setattr("backend.services.sufficiency_service.GEMINI_API_KEY", "")

    inv_id, contract_id, reqs = _create_investigation_and_contract()
    target_req = reqs[0]

    c1, _, _ = _insert_source_passage_claim(
        inv_id,
        "Source Alpha",
        "Power availability reached 19.6 hours after commissioning.",
        "Power availability reached 19.6 hours after commissioning."
    )
    c2, _, _ = _insert_source_passage_claim(
        inv_id,
        "Source Beta",
        "Power availability fell to 4.8 hours after commissioning.",
        "Power availability fell to 4.8 hours after commissioning."
    )

    _link_claim_to_requirement(inv_id, target_req["requirement_id"], c1, relevance="DIRECTLY_RELEVANT")

    # Add unresolved conflict involving c1
    _insert_conflict(inv_id, c1, c2, status="unresolved")

    res = client.post(f"/api/investigations/{inv_id}/sufficiency/analyze")
    assert res.status_code == 200
    data = res.json()

    target_asm = next(a for a in data["assessments"] if a["requirement_id"] == target_req["requirement_id"])
    assert target_asm["coverage_status"] == "CONFLICTING"
    assert target_asm["unresolved_conflict_count"] == 1
    assert "unresolved conflict" in target_asm["assessment_summary"].lower()
    assert len(target_asm["gaps"]) >= 1
    assert target_asm["gaps"][0]["priority"] == "HIGH"


def test_requirement_with_resolved_conflict_does_not_block_sufficiency(monkeypatch):
    monkeypatch.setattr("backend.services.sufficiency_service.GEMINI_API_KEY", "")

    inv_id, contract_id, reqs = _create_investigation_and_contract()
    target_req = reqs[0]

    c1, _, _ = _insert_source_passage_claim(
        inv_id, "Source Alpha",
        "Power availability reached 19.6 hours per day.",
        "Power availability reached 19.6 hours per day."
    )
    c2, _, _ = _insert_source_passage_claim(
        inv_id, "Source Beta",
        "Power availability reached 19.2 hours per day.",
        "Power availability reached 19.2 hours per day."
    )
    _link_claim_to_requirement(inv_id, target_req["requirement_id"], c1, relevance="DIRECTLY_RELEVANT")
    _link_claim_to_requirement(inv_id, target_req["requirement_id"], c2, relevance="DIRECTLY_RELEVANT")

    # Add resolved conflict
    _insert_conflict(inv_id, c1, c2, status="resolved")

    res = client.post(f"/api/investigations/{inv_id}/sufficiency/analyze")
    assert res.status_code == 200
    data = res.json()

    target_asm = next(a for a in data["assessments"] if a["requirement_id"] == target_req["requirement_id"])
    # Resolved conflict does not block SUFFICIENT
    assert target_asm["coverage_status"] == "SUFFICIENT"
    assert target_asm["unresolved_conflict_count"] == 0


def test_top_level_routes_and_status_endpoints(monkeypatch):
    monkeypatch.setattr("backend.services.sufficiency_service.GEMINI_API_KEY", "")

    inv_id, contract_id, reqs = _create_investigation_and_contract()

    # 1. Analyze via top-level endpoint
    res = client.post(f"/api/sufficiency/analyze?investigation_id={inv_id}")
    assert res.status_code == 200
    data = res.json()
    assert data["investigation_id"] == inv_id

    # 2. Get via top-level endpoint
    res_get = client.get(f"/api/sufficiency?investigation_id={inv_id}")
    assert res_get.status_code == 200
    assert res_get.json()["investigation_id"] == inv_id

    # 3. Status endpoint
    status_res = client.get(f"/api/sufficiency/status?investigation_id={inv_id}")
    assert status_res.status_code == 200
    s_data = status_res.json()
    assert s_data["total_requirements"] == len(reqs)
    assert s_data["processing_mode"] == "fallback"

    # 4. Single requirement detail
    req_id = reqs[0]["requirement_id"]
    detail_res = client.get(f"/api/sufficiency/requirements/{req_id}?investigation_id={inv_id}")
    assert detail_res.status_code == 200
    assert detail_res.json()["requirement_id"] == req_id


def test_idempotent_analysis_prevents_duplicate_records(monkeypatch):
    monkeypatch.setattr("backend.services.sufficiency_service.GEMINI_API_KEY", "")

    inv_id, contract_id, reqs = _create_investigation_and_contract()

    # Run twice
    client.post(f"/api/investigations/{inv_id}/sufficiency/analyze")
    client.post(f"/api/investigations/{inv_id}/sufficiency/analyze")

    with get_db(CURRENT_TEST_DB) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM evidence_sufficiency_assessments WHERE investigation_id = ?;", (inv_id,))
        count = cursor.fetchone()[0]
        assert count == len(reqs)


def test_404_error_handling():
    fake_id = "non-existent-inv-999"

    assert client.get(f"/api/investigations/{fake_id}/sufficiency").status_code == 404
    assert client.post(f"/api/investigations/{fake_id}/sufficiency/analyze").status_code == 404
    assert client.get(f"/api/investigations/{fake_id}/sufficiency/status").status_code == 404
    assert client.get(f"/api/investigations/{fake_id}/sufficiency/requirements/fake-req").status_code == 404


def test_gemini_sufficiency_mocked_success(monkeypatch):
    """Verifies Gemini structured output parsing and processing_mode='gemini'."""
    inv_id, contract_id, reqs = _create_investigation_and_contract()
    target_req = reqs[0]

    c1, _, _ = _insert_source_passage_claim(
        inv_id, "Source Alpha",
        "Microgrid power reliability reached 99.4% uptime.",
        "Detailed logs showed microgrid power reliability reached 99.4% uptime."
    )
    _link_claim_to_requirement(inv_id, target_req["requirement_id"], c1, relevance="DIRECTLY_RELEVANT")

    monkeypatch.setattr("backend.services.sufficiency_service.GEMINI_API_KEY", "mock_key")

    mock_gemini_response = {
        "assessments": [
            {
                "requirement_id": target_req["requirement_id"],
                "coverage_status": "PARTIAL",
                "assessment_summary": "Gemini evaluated single-source logs confirming high uptime.",
                "limitations": "Lack of third-party utility auditing.",
                "missing_information": "Year-round seasonal monsoon data.",
                "recommended_action": "Audit monsoon quarter outage telemetry.",
                "confidence": 0.94,
                "gaps": [
                    {
                        "gap_description": "Absence of monsoon season reliability metrics",
                        "why_it_matters": "Monsoon clouds and rain could degrade solar microgrid battery reserves.",
                        "evidence_needed": "Outage logs during July-August peak monsoon.",
                        "suggested_source_type": "Meteorological & Grid Telemetry Logs",
                        "priority": "HIGH"
                    }
                ]
            }
        ]
    }

    mock_response = MagicMock()
    import json
    mock_response.text = json.dumps(mock_gemini_response)

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response

    mock_genai = MagicMock()
    mock_genai.Client.return_value = mock_client

    monkeypatch.setattr("google.genai", mock_genai, raising=False)
    monkeypatch.setattr("google.genai.Client", MagicMock(return_value=mock_client), raising=False)

    import sys
    monkeypatch.setitem(sys.modules, "google.genai", mock_genai)
    monkeypatch.setitem(sys.modules, "google.genai.types", MagicMock())

    res = client.post(f"/api/investigations/{inv_id}/sufficiency/analyze")
    assert res.status_code == 200
    data = res.json()

    assert data["processing_mode"] == "gemini"
    target_asm = next(a for a in data["assessments"] if a["requirement_id"] == target_req["requirement_id"])
    assert target_asm["coverage_status"] == "PARTIAL"
    assert target_asm["confidence"] == 0.94
    assert "monsoon" in target_asm["missing_information"].lower()
    assert len(target_asm["gaps"]) == 1
    assert "monsoon" in target_asm["gaps"][0]["gap_description"].lower()
