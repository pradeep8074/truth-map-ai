import pytest
import uuid
import datetime
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from backend.main import app
from backend.database import init_db, get_db

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_test_database(tmp_path, monkeypatch):
    """Initializes a fresh isolated SQLite database for each test run."""
    test_db = tmp_path / "test_truthmap_graph.db"
    init_db(test_db)
    monkeypatch.setattr("backend.database.DB_PATH", test_db)
    monkeypatch.setattr("backend.routers.investigations.get_db", lambda: get_db(test_db))
    monkeypatch.setattr("backend.routers.sources.get_db", lambda: get_db(test_db))
    monkeypatch.setattr("backend.routers.contracts.get_db", lambda: get_db(test_db))
    monkeypatch.setattr("backend.routers.graph.get_db", lambda: get_db(test_db))


def test_empty_graph_returns_valid_structure():
    # Create empty investigation
    res = client.post("/api/investigations", json={"research_question": "Does renewable energy reduce grid stability?"})
    assert res.status_code == 201
    inv_id = res.json()["investigation_id"]

    # Query graph
    graph_res = client.get(f"/api/investigations/{inv_id}/evidence-graph")
    assert graph_res.status_code == 200
    data = graph_res.json()

    assert data["investigation_id"] == inv_id
    assert data["nodes"] == []
    assert data["edges"] == []
    assert data["summary"]["total_nodes"] == 0
    assert data["summary"]["total_edges"] == 0
    assert data["processing_mode"] == "pending"

    # Query status
    status_res = client.get(f"/api/investigations/{inv_id}/evidence-graph/status")
    assert status_res.status_code == 200
    status_data = status_res.json()
    assert status_data["total_nodes"] == 0
    assert status_data["total_edges"] == 0
    assert status_data["requirements_represented"] == 0
    assert status_data["claims_represented"] == 0


def test_graph_with_contract_only():
    # 1. Create investigation
    res = client.post("/api/investigations", json={"research_question": "Does this scholarship increase rural college access?"})
    inv_id = res.json()["investigation_id"]

    # 2. Compile contract
    compile_res = client.post(f"/api/investigations/{inv_id}/contract/compile")
    assert compile_res.status_code == 201
    contract = compile_res.json()

    # 3. Query graph
    graph_res = client.get(f"/api/investigations/{inv_id}/evidence-graph")
    assert graph_res.status_code == 200
    data = graph_res.json()

    node_types = {n["type"] for n in data["nodes"]}
    assert "decision_contract" in node_types
    assert "decision_requirement" in node_types
    assert "evidence_requirement" in node_types
    assert "atomic_claim" not in node_types

    edge_rels = {e["relationship"] for e in data["edges"]}
    assert "HAS_REQUIREMENT" in edge_rels
    assert "REQUIRES_EVIDENCE" in edge_rels
    assert "RELATES_TO" not in edge_rels

    assert data["summary"]["contract_nodes"] == 1
    assert data["summary"]["requirement_nodes"] >= 4
    assert data["summary"]["evidence_requirement_nodes"] >= 4
    assert data["summary"]["claim_nodes"] == 0


def test_graph_with_sources_and_claims_only(tmp_path):
    # 1. Create investigation
    res = client.post("/api/investigations", json={"research_question": "What is the economic impact of clean water initiatives?"})
    inv_id = res.json()["investigation_id"]

    # 2. Ingest mock source data directly into test db
    test_db = tmp_path / "test_truthmap_graph.db"
    with get_db(test_db) as conn:
        cursor = conn.cursor()
        src_id = str(uuid.uuid4())
        pas_id = str(uuid.uuid4())
        claim_id = str(uuid.uuid4())
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()

        cursor.execute("""
            INSERT INTO sources (id, investigation_id, source_type, title, retrieved_at, extraction_status)
            VALUES (?, ?, 'url', 'Clean Water Study 2024', ?, 'completed');
        """, (src_id, inv_id, now))

        cursor.execute("""
            INSERT INTO passages (id, source_id, passage_text, page_number, sha256_hash)
            VALUES (?, ?, 'Water filtration programs reduced waterborne diseases by 42 percent across 12 villages.', 1, 'mockhash123');
        """, (pas_id, src_id))

        cursor.execute("""
            INSERT INTO claims (id, investigation_id, source_id, passage_id, claim_text, category, extraction_method, extraction_confidence, created_at)
            VALUES (?, ?, ?, ?, 'Water filtration programs reduced waterborne diseases by 42 percent.', 'statistical', 'deterministic_parser', 0.92, ?);
        """, (claim_id, inv_id, src_id, pas_id, now))
        conn.commit()

    # 3. Query graph
    graph_res = client.get(f"/api/investigations/{inv_id}/evidence-graph")
    assert graph_res.status_code == 200
    data = graph_res.json()

    node_types = {n["type"] for n in data["nodes"]}
    assert "source_document" in node_types
    assert "source_passage" in node_types
    assert "atomic_claim" in node_types
    assert "decision_contract" not in node_types

    edge_rels = {e["relationship"] for e in data["edges"]}
    assert "EXTRACTED_FROM" in edge_rels
    assert "BELONGS_TO_SOURCE" in edge_rels

    assert data["summary"]["claim_nodes"] == 1
    assert data["summary"]["passage_nodes"] == 1
    assert data["summary"]["source_nodes"] == 1


def test_fallback_relevance_analysis_and_persistence(tmp_path):
    # 1. Create investigation with contract and claims
    res = client.post("/api/investigations", json={"research_question": "Does this scholarship programme improve access to higher education for rural students?"})
    inv_id = res.json()["investigation_id"]

    compile_res = client.post(f"/api/investigations/{inv_id}/contract/compile")
    assert compile_res.status_code == 201

    test_db = tmp_path / "test_truthmap_graph.db"
    with get_db(test_db) as conn:
        cursor = conn.cursor()
        src_id = str(uuid.uuid4())
        pas_id = str(uuid.uuid4())
        claim1_id = str(uuid.uuid4())
        claim2_id = str(uuid.uuid4())
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()

        cursor.execute("""
            INSERT INTO sources (id, investigation_id, source_type, title, retrieved_at, extraction_status)
            VALUES (?, ?, 'document', 'State Higher Education Report 2024.pdf', ?, 'completed');
        """, (src_id, inv_id, now))

        cursor.execute("""
            INSERT INTO passages (id, source_id, passage_text, page_number, sha256_hash)
            VALUES (?, ?, 'In fiscal year 2024, the scholarship initiative increased rural college enrollment access by 34 percent compared to baseline cohorts.', 1, 'hash_abc');
        """, (pas_id, src_id))

        # Relevant claim
        cursor.execute("""
            INSERT INTO claims (id, investigation_id, source_id, passage_id, claim_text, category, extraction_method, extraction_confidence, created_at)
            VALUES (?, ?, ?, ?, 'The scholarship initiative increased rural college enrollment access by 34 percent compared to baseline cohorts.', 'statistical', 'deterministic_parser', 0.94, ?);
        """, (claim1_id, inv_id, src_id, pas_id, now))

        # Irrelevant claim
        cursor.execute("""
            INSERT INTO claims (id, investigation_id, source_id, passage_id, claim_text, category, extraction_method, extraction_confidence, created_at)
            VALUES (?, ?, ?, ?, 'The campus cafeteria updated its menu to include gluten-free items.', 'factual', 'deterministic_parser', 0.85, ?);
        """, (claim2_id, inv_id, src_id, pas_id, now))
        conn.commit()

    # 2. Trigger relationship analysis (without Gemini key -> triggers deterministic fallback)
    analyze_res = client.post(f"/api/investigations/{inv_id}/evidence-graph/analyze")
    assert analyze_res.status_code == 200
    graph = analyze_res.json()

    assert graph["processing_mode"] in {"gemini", "fallback"}
    assert graph["summary"]["total_edges"] > 0

    # Find RELATES_TO edges
    relates_edges = [e for e in graph["edges"] if e["relationship"] == "RELATES_TO"]
    assert len(relates_edges) >= 1

    # Check edge provenance and metadata
    edge = relates_edges[0]
    assert edge["source"].startswith("claim_")
    assert edge["target"].startswith("req_")
    assert edge["origin"] in {"gemini", "fallback"}
    assert "relevance" in edge["metadata"]
    assert edge["metadata"]["relevance"] in {"DIRECTLY_RELEVANT", "PARTIALLY_RELEVANT", "CONTEXTUAL"}

    # 3. Verify persistence on subsequent GET
    get_res = client.get(f"/api/investigations/{inv_id}/evidence-graph")
    assert get_res.status_code == 200
    persisted_graph = get_res.json()
    assert len(persisted_graph["edges"]) == len(graph["edges"])

    # 4. Verify graph status endpoint
    status_res = client.get(f"/api/investigations/{inv_id}/evidence-graph/status")
    assert status_res.status_code == 200
    status = status_res.json()
    assert status["requirements_represented"] >= 4
    assert status["claims_represented"] == 2
    assert status["sources_represented"] == 1
    assert status["last_analysis_status"] == "completed"


def test_gemini_relevance_analysis_mocked_success(tmp_path):
    from unittest.mock import patch

    res = client.post("/api/investigations", json={"research_question": "Does rural scholarship programme improve access?"})
    inv_id = res.json()["investigation_id"]
    client.post(f"/api/investigations/{inv_id}/contract/compile")

    test_db = tmp_path / "test_truthmap_graph.db"
    with get_db(test_db) as conn:
        cursor = conn.cursor()
        src_id = str(uuid.uuid4())
        pas_id = str(uuid.uuid4())
        claim_id = str(uuid.uuid4())
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()

        cursor.execute("SELECT id FROM contract_requirements WHERE contract_id = (SELECT id FROM decision_contracts WHERE investigation_id = ?) LIMIT 1;", (inv_id,))
        req_id = cursor.fetchone()[0]

        cursor.execute("""
            INSERT INTO sources (id, investigation_id, source_type, title, retrieved_at, extraction_status)
            VALUES (?, ?, 'url', 'Enrollment Evaluation Study', ?, 'completed');
        """, (src_id, inv_id, now))

        cursor.execute("""
            INSERT INTO passages (id, source_id, passage_text, page_number, sha256_hash)
            VALUES (?, ?, 'Rural student enrollment increased by 28 percent over 3 years.', 1, 'hash999');
        """, (pas_id, src_id))

        cursor.execute("""
            INSERT INTO claims (id, investigation_id, source_id, passage_id, claim_text, category, extraction_method, extraction_confidence, created_at)
            VALUES (?, ?, ?, ?, 'Rural student enrollment increased by 28 percent over 3 years.', 'statistical', 'gemini_llm_structured', 0.95, ?);
        """, (claim_id, inv_id, src_id, pas_id, now))
        conn.commit()

    # Mock google.genai Client
    mock_payload = f"""{{
        "relationships": [
            {{
                "requirement_id": "{req_id}",
                "claim_id": "{claim_id}",
                "passage_id": "{pas_id}",
                "relevance": "DIRECTLY_RELEVANT",
                "explanation": "Claim presents quantitative proof of rural student enrollment growth matching requirement criteria.",
                "confidence": 0.94
            }}
        ]
    }}"""

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = mock_payload
    mock_client.models.generate_content.return_value = mock_response

    with patch("backend.services.graph_service.GEMINI_API_KEY", "mock-gemini-key"):
        with patch("google.genai.Client", return_value=mock_client):
            analyze_res = client.post(f"/api/investigations/{inv_id}/evidence-graph/analyze")
            assert analyze_res.status_code == 200
            graph = analyze_res.json()

            assert graph["processing_mode"] == "gemini"
            rel_edges = [e for e in graph["edges"] if e["relationship"] == "RELATES_TO"]
            assert len(rel_edges) == 1
            assert rel_edges[0]["origin"] == "gemini"
            assert rel_edges[0]["metadata"]["relevance"] == "DIRECTLY_RELEVANT"
            assert rel_edges[0]["confidence"] == 0.94


def test_gemini_relevance_analysis_mocked_error_falls_back(tmp_path):
    from unittest.mock import patch

    res = client.post("/api/investigations", json={"research_question": "Does rural scholarship programme improve access?"})
    inv_id = res.json()["investigation_id"]
    client.post(f"/api/investigations/{inv_id}/contract/compile")

    test_db = tmp_path / "test_truthmap_graph.db"
    with get_db(test_db) as conn:
        cursor = conn.cursor()
        src_id = str(uuid.uuid4())
        pas_id = str(uuid.uuid4())
        claim_id = str(uuid.uuid4())
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()

        cursor.execute("""
            INSERT INTO sources (id, investigation_id, source_type, title, retrieved_at, extraction_status)
            VALUES (?, ?, 'url', 'Enrollment Evaluation Study', ?, 'completed');
        """, (src_id, inv_id, now))

        cursor.execute("""
            INSERT INTO passages (id, source_id, passage_text, page_number, sha256_hash)
            VALUES (?, ?, 'Rural student enrollment increased by 28 percent over 3 years.', 1, 'hash999');
        """, (pas_id, src_id))

        cursor.execute("""
            INSERT INTO claims (id, investigation_id, source_id, passage_id, claim_text, category, extraction_method, extraction_confidence, created_at)
            VALUES (?, ?, ?, ?, 'Rural student enrollment increased by 28 percent over 3 years.', 'statistical', 'gemini_llm_structured', 0.95, ?);
        """, (claim_id, inv_id, src_id, pas_id, now))
        conn.commit()

    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = RuntimeError("Rate limit or model unavailable")

    with patch("backend.services.graph_service.GEMINI_API_KEY", "mock-gemini-key"):
        with patch("google.genai.Client", return_value=mock_client):
            analyze_res = client.post(f"/api/investigations/{inv_id}/evidence-graph/analyze")
            assert analyze_res.status_code == 200
            graph = analyze_res.json()

            # Must gracefully fall back without crashing
            assert graph["processing_mode"] == "fallback"
            assert graph["summary"]["total_edges"] > 0
            for edge in graph["edges"]:
                if edge["relationship"] == "RELATES_TO":
                    assert edge["origin"] == "fallback"


def test_gemini_quota_rate_limit_failure_falls_back(tmp_path):
    """Verifies that 429 RESOURCE_EXHAUSTED rate-limit errors trigger deterministic fallback without crashing."""
    from unittest.mock import patch

    res = client.post("/api/investigations", json={"research_question": "Does solar microgrids improve power reliability in rural communities?"})
    inv_id = res.json()["investigation_id"]
    client.post(f"/api/investigations/{inv_id}/contract/compile")

    test_db = tmp_path / "test_truthmap_graph.db"
    with get_db(test_db) as conn:
        cursor = conn.cursor()
        src_id = str(uuid.uuid4())
        pas_id = str(uuid.uuid4())
        claim_id = str(uuid.uuid4())
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()

        cursor.execute("""
            INSERT INTO sources (id, investigation_id, source_type, title, retrieved_at, extraction_status)
            VALUES (?, ?, 'url', 'Solar Energy Report 2024', ?, 'completed');
        """, (src_id, inv_id, now))

        cursor.execute("""
            INSERT INTO passages (id, source_id, passage_text, page_number, sha256_hash)
            VALUES (?, ?, 'Solar microgrid installations increased continuous electricity availability to 18 hours daily.', 1, 'hash_solar_1');
        """, (pas_id, src_id))

        cursor.execute("""
            INSERT INTO claims (id, investigation_id, source_id, passage_id, claim_text, category, extraction_method, extraction_confidence, created_at)
            VALUES (?, ?, ?, ?, 'Solar microgrids increased electricity availability to 18 hours daily.', 'statistical', 'gemini_llm_structured', 0.95, ?);
        """, (claim_id, inv_id, src_id, pas_id, now))
        conn.commit()

    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = Exception("429 RESOURCE_EXHAUSTED: Generate content requests per day limit exceeded on Free Tier")

    with patch("backend.services.graph_service.GEMINI_API_KEY", "mock-gemini-key"):
        with patch("google.genai.Client", return_value=mock_client):
            analyze_res = client.post(f"/api/investigations/{inv_id}/evidence-graph/analyze")
            assert analyze_res.status_code == 200
            graph = analyze_res.json()

            assert graph["processing_mode"] == "fallback"
            for edge in graph["edges"]:
                if edge["relationship"] == "RELATES_TO":
                    assert edge["origin"] == "fallback"


def test_gemini_auth_failure_falls_back(tmp_path):
    """Verifies that authentication failures (401/403) trigger deterministic fallback with origin='fallback'."""
    from unittest.mock import patch

    res = client.post("/api/investigations", json={"research_question": "Does solar microgrids improve power reliability in rural communities?"})
    inv_id = res.json()["investigation_id"]
    client.post(f"/api/investigations/{inv_id}/contract/compile")

    test_db = tmp_path / "test_truthmap_graph.db"
    with get_db(test_db) as conn:
        cursor = conn.cursor()
        src_id = str(uuid.uuid4())
        pas_id = str(uuid.uuid4())
        claim_id = str(uuid.uuid4())
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()

        cursor.execute("""
            INSERT INTO sources (id, investigation_id, source_type, title, retrieved_at, extraction_status)
            VALUES (?, ?, 'url', 'Solar Energy Report 2024', ?, 'completed');
        """, (src_id, inv_id, now))

        cursor.execute("""
            INSERT INTO passages (id, source_id, passage_text, page_number, sha256_hash)
            VALUES (?, ?, 'Solar microgrid installations increased continuous electricity availability to 18 hours daily.', 1, 'hash_solar_1');
        """, (pas_id, src_id))

        cursor.execute("""
            INSERT INTO claims (id, investigation_id, source_id, passage_id, claim_text, category, extraction_method, extraction_confidence, created_at)
            VALUES (?, ?, ?, ?, 'Solar microgrids increased electricity availability to 18 hours daily.', 'statistical', 'gemini_llm_structured', 0.95, ?);
        """, (claim_id, inv_id, src_id, pas_id, now))
        conn.commit()

    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = Exception("403 PERMISSION_DENIED: API key not valid. Please pass a valid API key.")

    with patch("backend.services.graph_service.GEMINI_API_KEY", "invalid-key"):
        with patch("google.genai.Client", return_value=mock_client):
            analyze_res = client.post(f"/api/investigations/{inv_id}/evidence-graph/analyze")
            assert analyze_res.status_code == 200
            graph = analyze_res.json()

            assert graph["processing_mode"] == "fallback"


def test_gemini_network_failure_falls_back(tmp_path):
    """Verifies that network connection timeouts trigger deterministic fallback."""
    from unittest.mock import patch

    res = client.post("/api/investigations", json={"research_question": "Does solar microgrids improve power reliability in rural communities?"})
    inv_id = res.json()["investigation_id"]
    client.post(f"/api/investigations/{inv_id}/contract/compile")

    test_db = tmp_path / "test_truthmap_graph.db"
    with get_db(test_db) as conn:
        cursor = conn.cursor()
        src_id = str(uuid.uuid4())
        pas_id = str(uuid.uuid4())
        claim_id = str(uuid.uuid4())
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()

        cursor.execute("""
            INSERT INTO sources (id, investigation_id, source_type, title, retrieved_at, extraction_status)
            VALUES (?, ?, 'url', 'Solar Energy Report 2024', ?, 'completed');
        """, (src_id, inv_id, now))

        cursor.execute("""
            INSERT INTO passages (id, source_id, passage_text, page_number, sha256_hash)
            VALUES (?, ?, 'Solar microgrid installations increased continuous electricity availability to 18 hours daily.', 1, 'hash_solar_1');
        """, (pas_id, src_id))

        cursor.execute("""
            INSERT INTO claims (id, investigation_id, source_id, passage_id, claim_text, category, extraction_method, extraction_confidence, created_at)
            VALUES (?, ?, ?, ?, 'Solar microgrids increased electricity availability to 18 hours daily.', 'statistical', 'gemini_llm_structured', 0.95, ?);
        """, (claim_id, inv_id, src_id, pas_id, now))
        conn.commit()

    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = TimeoutError("HTTPSConnectionPool: Read timed out after 10.0 seconds")

    with patch("backend.services.graph_service.GEMINI_API_KEY", "mock-gemini-key"):
        with patch("google.genai.Client", return_value=mock_client):
            analyze_res = client.post(f"/api/investigations/{inv_id}/evidence-graph/analyze")
            assert analyze_res.status_code == 200
            graph = analyze_res.json()

            assert graph["processing_mode"] == "fallback"


def test_gemini_invalid_json_response_falls_back(tmp_path):
    """Verifies that non-JSON or malformed responses from Gemini trigger deterministic fallback."""
    from unittest.mock import patch

    res = client.post("/api/investigations", json={"research_question": "Does solar microgrids improve power reliability in rural communities?"})
    inv_id = res.json()["investigation_id"]
    client.post(f"/api/investigations/{inv_id}/contract/compile")

    test_db = tmp_path / "test_truthmap_graph.db"
    with get_db(test_db) as conn:
        cursor = conn.cursor()
        src_id = str(uuid.uuid4())
        pas_id = str(uuid.uuid4())
        claim_id = str(uuid.uuid4())
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()

        cursor.execute("""
            INSERT INTO sources (id, investigation_id, source_type, title, retrieved_at, extraction_status)
            VALUES (?, ?, 'url', 'Solar Energy Report 2024', ?, 'completed');
        """, (src_id, inv_id, now))

        cursor.execute("""
            INSERT INTO passages (id, source_id, passage_text, page_number, sha256_hash)
            VALUES (?, ?, 'Solar microgrid installations increased continuous electricity availability to 18 hours daily.', 1, 'hash_solar_1');
        """, (pas_id, src_id))

        cursor.execute("""
            INSERT INTO claims (id, investigation_id, source_id, passage_id, claim_text, category, extraction_method, extraction_confidence, created_at)
            VALUES (?, ?, ?, ?, 'Solar microgrids increased electricity availability to 18 hours daily.', 'statistical', 'gemini_llm_structured', 0.95, ?);
        """, (claim_id, inv_id, src_id, pas_id, now))
        conn.commit()

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "This is plain text not JSON, causing JSONDecodeError"
    mock_client.models.generate_content.return_value = mock_response

    with patch("backend.services.graph_service.GEMINI_API_KEY", "mock-gemini-key"):
        with patch("google.genai.Client", return_value=mock_client):
            analyze_res = client.post(f"/api/investigations/{inv_id}/evidence-graph/analyze")
            assert analyze_res.status_code == 200
            graph = analyze_res.json()

            assert graph["processing_mode"] == "fallback"


def test_invalid_investigation_returns_404():
    bad_id = "non-existent-uuid"
    res = client.get(f"/api/investigations/{bad_id}/evidence-graph")
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()

    analyze_res = client.post(f"/api/investigations/{bad_id}/evidence-graph/analyze")
    assert analyze_res.status_code == 404

    status_res = client.get(f"/api/investigations/{bad_id}/evidence-graph/status")
    assert status_res.status_code == 404
