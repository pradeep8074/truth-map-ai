import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
import pymupdf
import httpx

from backend.main import app
from backend.database import init_db, get_db

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_test_database(tmp_path, monkeypatch):
    """Initializes a fresh isolated SQLite database for each test run."""
    test_db = tmp_path / "test_truthmap.db"
    init_db(test_db)
    monkeypatch.setattr("backend.database.DB_PATH", test_db)
    monkeypatch.setattr("backend.routers.investigations.get_db", lambda: get_db(test_db))
    monkeypatch.setattr("backend.routers.sources.get_db", lambda: get_db(test_db))


def create_sample_pdf_bytes() -> bytes:
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text(
        (50, 72),
        "Higher education scholarship grants increased university enrollment by 18% among target cohorts.",
        fontsize=12
    )
    b = doc.tobytes()
    doc.close()
    return b


def test_create_and_get_investigation():
    # 1. Invalid input: too short
    bad_res = client.post("/api/investigations", json={"research_question": "No"})
    assert bad_res.status_code == 422

    # 2. Valid creation
    create_res = client.post(
        "/api/investigations",
        json={"research_question": "Does this scholarship program improve access to higher education?"}
    )
    assert create_res.status_code == 201
    data = create_res.json()
    assert "investigation_id" in data
    assert data["status"] in ("ready", "processing")
    inv_id = data["investigation_id"]

    # 3. Get investigation details
    get_res = client.get(f"/api/investigations/{inv_id}")
    assert get_res.status_code == 200
    inv_data = get_res.json()
    assert inv_data["id"] == inv_id
    assert "scholarship" in inv_data["research_question"]
    assert inv_data["sources_count"] == 0
    assert inv_data["claims_count"] == 0


def test_pdf_document_upload_and_claim_extraction():
    # Create investigation
    create_res = client.post(
        "/api/investigations",
        json={"research_question": "Evaluate student outcome metrics under grant funding."}
    )
    inv_id = create_res.json()["investigation_id"]

    # Upload PDF
    pdf_bytes = create_sample_pdf_bytes()
    upload_res = client.post(
        f"/api/investigations/{inv_id}/documents",
        files=[("files", ("scholarship_study.pdf", pdf_bytes, "application/pdf"))]
    )
    assert upload_res.status_code == 200
    sources = upload_res.json()
    assert len(sources) == 1
    src = sources[0]
    assert src["source_type"] == "pdf"
    assert src["extraction_status"] == "completed"
    assert src["passages_count"] >= 1
    assert src["claims_count"] >= 1
    src_id = src["id"]

    # Retrieve passages
    passages_res = client.get(f"/api/sources/{src_id}/passages")
    assert passages_res.status_code == 200
    passages = passages_res.json()
    assert len(passages) >= 1
    assert passages[0]["page_number"] == 1
    assert len(passages[0]["sha256_hash"]) == 64

    # Retrieve claims
    claims_res = client.get(f"/api/investigations/{inv_id}/claims")
    assert claims_res.status_code == 200
    claims = claims_res.json()
    assert len(claims) >= 1
    assert "university enrollment" in claims[0]["claim_text"].lower()
    assert claims[0]["source_id"] == src_id
    assert claims[0]["page_number"] == 1


def test_web_url_ingestion_with_mocked_network():
    create_res = client.post(
        "/api/investigations",
        json={"research_question": "Examine digital public infrastructure impact."}
    )
    inv_id = create_res.json()["investigation_id"]

    sample_html = """
    <html><body><article>
    <h1>Digital Infrastructure Report</h1>
    <p>Unified digital identity platforms processed 120 million authentication transactions in 2025.</p>
    </article></body></html>
    """

    mock_response = httpx.Response(
        status_code=200,
        headers={"Content-Type": "text/html; charset=utf-8"},
        text=sample_html,
        request=httpx.Request("GET", "https://example.org/report")
    )

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response
        ingest_res = client.post(
            f"/api/investigations/{inv_id}/sources",
            json={"urls": ["https://example.org/report"]}
        )
        assert ingest_res.status_code == 200
        sources = ingest_res.json()
        assert len(sources) == 1
        assert sources[0]["extraction_status"] == "completed"

        # Check extracted claims
        claims_res = client.get(f"/api/investigations/{inv_id}/claims")
        assert claims_res.status_code == 200
        claims = claims_res.json()
        assert len(claims) >= 1
        assert any("120 million" in c["claim_text"] for c in claims)
