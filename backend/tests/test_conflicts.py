import pytest
import uuid
import datetime
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from backend.main import app
from backend.database import init_db, get_db
from backend.models import GeminiConflictAnalysisPayload, GeminiConflictFinding

client = TestClient(app)

CURRENT_TEST_DB = None


@pytest.fixture(autouse=True)
def setup_test_database(tmp_path, monkeypatch):
    """Initializes a fresh isolated SQLite database for each test run."""
    global CURRENT_TEST_DB
    test_db = tmp_path / "test_truthmap_conflicts.db"
    CURRENT_TEST_DB = test_db
    init_db(test_db)
    monkeypatch.setattr("backend.database.DB_PATH", test_db)
    monkeypatch.setattr("backend.routers.investigations.get_db", lambda: get_db(test_db))
    monkeypatch.setattr("backend.routers.sources.get_db", lambda: get_db(test_db))
    monkeypatch.setattr("backend.routers.contracts.get_db", lambda: get_db(test_db))
    monkeypatch.setattr("backend.routers.graph.get_db", lambda: get_db(test_db))
    monkeypatch.setattr("backend.routers.conflicts.get_db", lambda: get_db(test_db))


def _create_investigation(question: str = "Does remote work improve software engineering team velocity?"):
    res = client.post("/api/investigations", json={"research_question": question})
    assert res.status_code == 201
    return res.json()["investigation_id"]


def _insert_source_passage_claim(inv_id: str, source_title: str, claim_text: str, passage_text: str, page_num: int = 1):
    with get_db(CURRENT_TEST_DB) as conn:
        cursor = conn.cursor()
        src_id = f"src_{uuid.uuid4().hex[:8]}"
        pas_id = f"pas_{uuid.uuid4().hex[:8]}"
        clm_id = f"clm_{uuid.uuid4().hex[:8]}"
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()

        cursor.execute("""
            INSERT INTO sources (id, investigation_id, source_type, title, extraction_status, retrieved_at)
            VALUES (?, ?, 'web', ?, 'completed', ?);
        """, (src_id, inv_id, source_title, now))

        cursor.execute("""
            INSERT INTO passages (id, source_id, passage_text, page_number, paragraph_index, sha256_hash)
            VALUES (?, ?, ?, ?, 1, 'mocked_sha256_hash_12345');
        """, (pas_id, src_id, passage_text, page_num))

        cursor.execute("""
            INSERT INTO claims (id, investigation_id, source_id, passage_id, claim_text, category, extraction_method, extraction_confidence, created_at)
            VALUES (?, ?, ?, ?, ?, 'factual', 'deterministic', 0.95, ?);
        """, (clm_id, inv_id, src_id, pas_id, claim_text, now))

        conn.commit()
        return clm_id


def test_empty_conflicts_returns_valid_structure():
    inv_id = _create_investigation()

    # Query conflicts
    res = client.get(f"/api/investigations/{inv_id}/conflicts")
    assert res.status_code == 200
    data = res.json()

    assert data["investigation_id"] == inv_id
    assert data["conflicts"] == []
    assert data["summary"]["total_conflicts"] == 0
    assert data["summary"]["direct_contradictions"] == 0
    assert data["summary"]["unresolved_conflicts"] == 0
    assert data["processing_mode"] == "pending"

    # Query status
    status_res = client.get(f"/api/investigations/{inv_id}/conflicts/status")
    assert status_res.status_code == 200
    s_data = status_res.json()
    assert s_data["total_conflicts"] == 0
    assert s_data["last_analysis_status"] == "none"


def test_single_claim_returns_no_conflicts():
    inv_id = _create_investigation()
    _insert_source_passage_claim(
        inv_id,
        "Tech Report A",
        "Remote work increased developer velocity by 25%.",
        "Our survey demonstrated that remote work increased developer velocity by 25% across engineering teams."
    )

    res = client.post(f"/api/investigations/{inv_id}/conflicts/analyze")
    assert res.status_code == 200
    data = res.json()
    assert len(data["conflicts"]) == 0
    assert data["summary"]["total_conflicts"] == 0


def test_compatible_claims_produce_zero_conflicts():
    inv_id = _create_investigation()
    _insert_source_passage_claim(
        inv_id,
        "Source Alpha",
        "Solar installations expanded across southwest regions in 2023.",
        "Solar installations expanded across southwest regions in 2023 due to tax incentives."
    )
    _insert_source_passage_claim(
        inv_id,
        "Source Beta",
        "Wind turbine efficiency reached modern benchmarks in northern plains.",
        "Wind turbine efficiency reached modern benchmarks in northern plains during spring months."
    )

    res = client.post(f"/api/investigations/{inv_id}/conflicts/analyze")
    assert res.status_code == 200
    data = res.json()
    assert len(data["conflicts"]) == 0
    assert data["summary"]["total_conflicts"] == 0


def test_fallback_polar_contradiction_detection(monkeypatch):
    # Ensure Gemini key is cleared so fallback runs
    monkeypatch.setattr("backend.services.conflict_service.GEMINI_API_KEY", "")

    inv_id = _create_investigation()
    c1 = _insert_source_passage_claim(
        inv_id,
        "Tech Insights 2024",
        "Remote work significantly increased worker productivity across engineering teams.",
        "The survey data confirmed remote work significantly increased worker productivity across engineering teams."
    )
    c2 = _insert_source_passage_claim(
        inv_id,
        "Corporate Audit Bureau",
        "Remote work drastically decreased worker productivity across engineering teams.",
        "In contrast, the annual audit showed remote work drastically decreased worker productivity across engineering teams."
    )

    res = client.post(f"/api/investigations/{inv_id}/conflicts/analyze")
    assert res.status_code == 200
    data = res.json()

    assert data["processing_mode"] == "fallback"
    assert len(data["conflicts"]) >= 1

    conflict = data["conflicts"][0]
    assert conflict["conflict_type"] == "DIRECT_CONTRADICTION"
    assert conflict["severity"] in {"HIGH", "CRITICAL"}
    assert conflict["resolution_status"] == "unresolved"
    assert "increased" in conflict["explanation"].lower() or "polar" in conflict["explanation"].lower()
    assert conflict["source_a_title"] is not None
    assert conflict["source_b_title"] is not None
    assert conflict["passage_a_text"] is not None
    assert conflict["passage_b_text"] is not None


def test_fallback_numerical_conflict_detection(monkeypatch):
    monkeypatch.setattr("backend.services.conflict_service.GEMINI_API_KEY", "")

    inv_id = _create_investigation()
    c1 = _insert_source_passage_claim(
        inv_id,
        "Budget Office Report",
        "Total project capital expenditure reached 15 million dollars.",
        "Audited accounts confirmed total project capital expenditure reached 15 million dollars."
    )
    c2 = _insert_source_passage_claim(
        inv_id,
        "Contractor Financial Disclosure",
        "Total project capital expenditure reached 45 million dollars.",
        "Subcontractor filings indicated total project capital expenditure reached 45 million dollars."
    )

    res = client.post(f"/api/investigations/{inv_id}/conflicts/analyze")
    assert res.status_code == 200
    data = res.json()

    assert len(data["conflicts"]) >= 1
    conflict = data["conflicts"][0]
    assert conflict["conflict_type"] == "NUMERICAL_CONFLICT"
    assert conflict["severity"] in {"HIGH", "CRITICAL"}
    assert "15" in conflict["explanation"] and "45" in conflict["explanation"]


def test_conflict_resolution_lifecycle(monkeypatch):
    monkeypatch.setattr("backend.services.conflict_service.GEMINI_API_KEY", "")

    inv_id = _create_investigation()
    _insert_source_passage_claim(
        inv_id,
        "Report 1",
        "The hospital expansion decreased emergency room wait times.",
        "Hospital statistics showed the expansion decreased emergency room wait times."
    )
    _insert_source_passage_claim(
        inv_id,
        "Report 2",
        "The hospital expansion increased emergency room wait times.",
        "State monitoring revealed the expansion increased emergency room wait times."
    )

    # 1. Analyze
    analyze_res = client.post(f"/api/investigations/{inv_id}/conflicts/analyze")
    assert analyze_res.status_code == 200
    conflicts = analyze_res.json()["conflicts"]
    assert len(conflicts) > 0
    conflict_id = conflicts[0]["conflict_id"]
    assert conflicts[0]["resolution_status"] == "unresolved"

    # 2. Update to under_review with reviewer notes
    patch_res = client.patch(
        f"/api/investigations/{inv_id}/conflicts/{conflict_id}",
        json={
            "resolution_status": "under_review",
            "reviewer_notes": "Auditing data methodologies between quarterly reports."
        }
    )
    assert patch_res.status_code == 200
    updated = patch_res.json()
    assert updated["resolution_status"] == "under_review"
    assert updated["reviewer_notes"] == "Auditing data methodologies between quarterly reports."

    # 3. Update to resolved with conclusion
    resolve_res = client.patch(
        f"/api/investigations/{inv_id}/conflicts/{conflict_id}",
        json={
            "resolution_status": "resolved",
            "reviewer_notes": "Discrepancy resolved: Report 1 measured median wait time while Report 2 measured 99th percentile peak."
        }
    )
    assert resolve_res.status_code == 200
    resolved = resolve_res.json()
    assert resolved["resolution_status"] == "resolved"
    assert "median" in resolved["reviewer_notes"]

    # 4. Check summary reflects resolution
    list_res = client.get(f"/api/investigations/{inv_id}/conflicts")
    assert list_res.status_code == 200
    summary = list_res.json()["summary"]
    assert summary["resolved_count"] == 1
    assert summary["unresolved_conflicts"] == 0


def test_evidence_graph_includes_conflicts_with_edges(monkeypatch):
    monkeypatch.setattr("backend.services.conflict_service.GEMINI_API_KEY", "")

    inv_id = _create_investigation()
    c1 = _insert_source_passage_claim(
        inv_id,
        "Source 1",
        "Solar generation expanded rapidly during summer months.",
        "Solar generation expanded rapidly during summer months."
    )
    c2 = _insert_source_passage_claim(
        inv_id,
        "Source 2",
        "Solar generation dropped severely during summer months.",
        "Solar generation dropped severely during summer months."
    )

    # Detect conflicts
    client.post(f"/api/investigations/{inv_id}/conflicts/analyze")

    # Fetch Evidence Dependency Graph
    graph_res = client.get(f"/api/investigations/{inv_id}/evidence-graph")
    assert graph_res.status_code == 200
    graph_data = graph_res.json()

    # Look for CONFLICTS_WITH edge
    conflict_edges = [e for e in graph_data["edges"] if e["relationship"] == "CONFLICTS_WITH"]
    assert len(conflict_edges) >= 1
    edge = conflict_edges[0]
    assert edge["source"] in [f"claim_{c1}", f"claim_{c2}"]
    assert edge["target"] in [f"claim_{c1}", f"claim_{c2}"]
    assert edge["metadata"]["conflict_type"] == "DIRECT_CONTRADICTION"


def test_idempotent_conflict_analysis_prevents_duplicates(monkeypatch):
    monkeypatch.setattr("backend.services.conflict_service.GEMINI_API_KEY", "")

    inv_id = _create_investigation()
    _insert_source_passage_claim(
        inv_id,
        "Alpha",
        "Project revenue increased by 20 percent.",
        "Project revenue increased by 20 percent."
    )
    _insert_source_passage_claim(
        inv_id,
        "Beta",
        "Project revenue decreased by 20 percent.",
        "Project revenue decreased by 20 percent."
    )

    # First run
    run1 = client.post(f"/api/investigations/{inv_id}/conflicts/analyze").json()
    count1 = len(run1["conflicts"])

    # Second run
    run2 = client.post(f"/api/investigations/{inv_id}/conflicts/analyze").json()
    count2 = len(run2["conflicts"])

    assert count1 == count2 == 1


def test_404_handling_for_invalid_ids():
    fake_id = "non-existent-inv-123"

    res_get = client.get(f"/api/investigations/{fake_id}/conflicts")
    assert res_get.status_code == 404

    res_post = client.post(f"/api/investigations/{fake_id}/conflicts/analyze")
    assert res_post.status_code == 404

    res_status = client.get(f"/api/investigations/{fake_id}/conflicts/status")
    assert res_status.status_code == 404

    inv_id = _create_investigation()
    res_patch = client.patch(
        f"/api/investigations/{inv_id}/conflicts/non-existent-conflict",
        json={"resolution_status": "resolved"}
    )
    assert res_patch.status_code == 404


def test_gemini_analysis_mocked_success(monkeypatch):
    """Mocks Google GenAI client returning valid structured GeminiConflictAnalysisPayload."""
    inv_id = _create_investigation()
    c1 = _insert_source_passage_claim(
        inv_id,
        "Government Survey 2024",
        "The employment rate grew to 78% in Q4.",
        "National statistics show employment rate grew to 78% in Q4."
    )
    c2 = _insert_source_passage_claim(
        inv_id,
        "Independent Research Council",
        "The employment rate dropped to 62% in Q4.",
        "Independent audits showed employment rate dropped to 62% in Q4."
    )

    monkeypatch.setattr("backend.services.conflict_service.GEMINI_API_KEY", "mock_key")

    mock_parsed_payload = GeminiConflictAnalysisPayload(
        conflicts=[
            GeminiConflictFinding(
                claim_a_id=c1,
                claim_b_id=c2,
                conflict_type="NUMERICAL_CONFLICT",
                severity="CRITICAL",
                explanation="Direct clash between reported Q4 employment rates (78% vs 62%).",
                contextual_differences="Survey sampled formal sector while Council included unorganized informal labor.",
                confidence=0.98,
                recommended_action="Reconcile cohort definitions between formal establishment surveys and household labor surveys.",
            )
        ]
    )

    mock_response = MagicMock()
    mock_response.parsed = mock_parsed_payload
    mock_response.text = mock_parsed_payload.model_dump_json()

    mock_client_instance = MagicMock()
    mock_client_instance.models.generate_content.return_value = mock_response

    mock_genai = MagicMock()
    mock_genai.Client.return_value = mock_client_instance

    monkeypatch.setattr("google.genai", mock_genai, raising=False)

    import sys
    monkeypatch.setitem(sys.modules, "google.genai", mock_genai)
    monkeypatch.setitem(sys.modules, "google.genai.types", MagicMock())

    res = client.post(f"/api/investigations/{inv_id}/conflicts/analyze")
    assert res.status_code == 200
    data = res.json()

    assert data["processing_mode"] == "gemini"
    assert len(data["conflicts"]) == 1
    c = data["conflicts"][0]
    assert c["conflict_type"] == "NUMERICAL_CONFLICT"
    assert c["severity"] == "CRITICAL"
    assert c["confidence"] == 0.98
    assert "Direct clash" in c["explanation"]
    assert "informal labor" in c["contextual_differences"]
