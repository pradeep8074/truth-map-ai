import asyncio
from unittest.mock import MagicMock, patch
import pytest
from backend.services.claim_extractor import (
    extract_claims_deterministic,
    extract_claims_from_passage,
    classify_claim_category,
)


def test_deterministic_claim_extraction_compound_sentence():
    passage = "India's digital payments ecosystem recorded substantial growth in 2025, while rural adoption continued to expand."
    claims = extract_claims_deterministic(passage, "src-01", "pas-01", "inv-01")

    assert len(claims) >= 2
    claim_texts = [c["claim_text"] for c in claims]
    
    # Must decompose both clauses
    assert any("growth in 2025" in ct for ct in claim_texts)
    assert any("rural adoption continued to expand" in ct.lower() for ct in claim_texts)
    
    for c in claims:
        assert c["extraction_method"] == "deterministic_syntactic_decomposition"
        assert c["processing_mode"] == "fallback"
        assert 0.0 < c["extraction_confidence"] <= 1.0
        assert c["passage_id"] == "pas-01"
        assert c["source_id"] == "src-01"
        assert c["category"] in {"statistical", "causal", "factual", "policy", "temporal"}


def test_discourse_marker_stripping():
    passage = "Furthermore, the regulatory sandbox approved four institutional pilots in Q4."
    claims = extract_claims_deterministic(passage, "src-01", "pas-01", "inv-01")
    assert len(claims) == 1
    assert not claims[0]["claim_text"].startswith("Furthermore")
    assert "regulatory sandbox approved" in claims[0]["claim_text"]
    assert claims[0]["processing_mode"] == "fallback"


def test_empty_or_short_passage_returns_no_claims():
    assert extract_claims_deterministic("", "s1", "p1", "i1") == []
    assert extract_claims_deterministic("   ", "s1", "p1", "i1") == []
    assert extract_claims_deterministic("Short text.", "s1", "p1", "i1") == []

    claims_async = asyncio.run(extract_claims_from_passage("", "s1", "p1", "i1"))
    assert claims_async == []


def test_claim_category_classifier():
    assert classify_claim_category("Payments reached 45% penetration in 2024.") == "statistical"
    assert classify_claim_category("Enacted scholarship guideline for tertiary admission criteria.") == "policy"
    assert classify_claim_category("Subsidies led to higher enrolment because fees decreased.") == "causal"
    assert classify_claim_category("The university operates three campuses across the province.") == "factual"


def test_gemini_extraction_mocked_success():
    """Verifies structured Gemini extraction path with provenance anchoring and categories."""
    mock_response = MagicMock()
    mock_response.text = '''{
        "claims": [
            {
                "claim_text": "The programme provided tuition subsidies to 42,000 rural recipients.",
                "category": "statistical",
                "confidence": 0.95
            },
            {
                "claim_text": "Eligible candidates must maintain an academic record above 75%.",
                "category": "policy",
                "confidence": 0.92
            }
        ]
    }'''

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response

    with patch("backend.services.claim_extractor.GEMINI_API_KEY", "test-key-mocked"):
        with patch("google.genai.Client", return_value=mock_client):
            passage = "The programme provided tuition subsidies to 42,000 rural recipients. Eligible candidates must maintain an academic record above 75%."
            claims = asyncio.run(extract_claims_from_passage(passage, "src-test", "pas-test", "inv-test"))

            assert len(claims) == 2
            assert claims[0]["claim_text"].startswith("The programme provided")
            assert claims[0]["category"] == "statistical"
            assert claims[0]["extraction_method"] == "gemini_llm_structured"
            assert claims[0]["processing_mode"] == "gemini"
            assert claims[0]["passage_id"] == "pas-test"
            assert claims[0]["source_id"] == "src-test"
            assert claims[0]["investigation_id"] == "inv-test"

            assert claims[1]["category"] == "policy"
            assert claims[1]["processing_mode"] == "gemini"


def test_gemini_extraction_mocked_error_falls_back():
    """Verifies that when Gemini throws an exception, it seamlessly falls back to deterministic extraction."""
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = RuntimeError("Quota exceeded or connection error")

    with patch("backend.services.claim_extractor.GEMINI_API_KEY", "test-key-mocked"):
        with patch("google.genai.Client", return_value=mock_client):
            passage = "The annual scholarship fund disbursed 150 crore rupees across 12 participating universities."
            claims = asyncio.run(extract_claims_from_passage(passage, "src-test", "pas-test", "inv-test"))

            assert len(claims) >= 1
            # Must be fallback mode, NOT gemini
            assert claims[0]["extraction_method"] == "deterministic_syntactic_decomposition"
            assert claims[0]["processing_mode"] == "fallback"
            assert claims[0]["passage_id"] == "pas-test"
            assert claims[0]["source_id"] == "src-test"
