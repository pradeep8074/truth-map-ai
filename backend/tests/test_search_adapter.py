import pytest
from unittest.mock import patch, MagicMock
import httpx
from backend.services.search_adapter import (
    execute_search_discovery,
    classify_domain_authority,
    calculate_candidate_relevance,
)


def test_search_missing_configuration():
    """When SEARCH_PROVIDER is none or empty, reports 'Missing Configuration'."""
    with patch("backend.services.search_adapter.SEARCH_PROVIDER", "none"):
        res = execute_search_discovery(["solar capacity growth"], ["solar", "capacity"])
        assert res["status"] == "UNAVAILABLE"
        assert res["provider_state"] == "Missing Configuration"
        assert res["is_available"] is False
        assert "Manual candidate URL entry mode active" in res["message"]


def test_search_missing_api_key_when_tavily_selected():
    """When SEARCH_PROVIDER is tavily but TAVILY_API_KEY is empty, reports 'Missing Configuration'."""
    with patch("backend.services.search_adapter.SEARCH_PROVIDER", "tavily"), \
         patch("backend.services.search_adapter.TAVILY_API_KEY", ""):
        res = execute_search_discovery(["solar energy grid"], ["solar"])
        assert res["status"] == "UNAVAILABLE"
        assert res["provider_state"] == "Missing Configuration"
        assert "requires TAVILY_API_KEY" in res["message"]


def test_search_rate_limited_handling():
    """When Tavily returns HTTP 429, reports 'Rate Limited' status."""
    mock_resp = MagicMock()
    mock_resp.status_code = 429

    with patch("backend.services.search_adapter.SEARCH_PROVIDER", "tavily"), \
         patch("backend.services.search_adapter.TAVILY_API_KEY", "mock_key_tavily"), \
         patch("httpx.Client.post", return_value=mock_resp):
        res = execute_search_discovery(["wind turbine supply chain"], ["turbine"])
        assert res["status"] == "UNAVAILABLE"
        assert res["provider_state"] == "Rate Limited"
        assert "rate limit exceeded" in res["message"]


def test_search_authentication_failed_handling():
    """When Tavily returns HTTP 401, reports 'Failed' status."""
    mock_resp = MagicMock()
    mock_resp.status_code = 401

    with patch("backend.services.search_adapter.SEARCH_PROVIDER", "tavily"), \
         patch("backend.services.search_adapter.TAVILY_API_KEY", "invalid_key"), \
         patch("httpx.Client.post", return_value=mock_resp):
        res = execute_search_discovery(["energy storage capacity"], ["storage"])
        assert res["status"] == "UNAVAILABLE"
        assert res["provider_state"] == "Failed"
        assert "authentication failed" in res["message"]


def test_search_timeout_handling():
    """When Tavily request times out, reports 'Unavailable' status."""
    with patch("backend.services.search_adapter.SEARCH_PROVIDER", "tavily"), \
         patch("backend.services.search_adapter.TAVILY_API_KEY", "mock_key"), \
         patch("httpx.Client.post", side_effect=httpx.TimeoutException("Read timed out")):
        res = execute_search_discovery(["grid stability indicators"], ["stability"])
        assert res["status"] == "UNAVAILABLE"
        assert res["provider_state"] == "Unavailable"
        assert "timed out" in res["message"]


def test_search_empty_results_handling():
    """When Tavily succeeds with 200 OK but returns empty list, reports 'No Results'."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"results": []}

    with patch("backend.services.search_adapter.SEARCH_PROVIDER", "tavily"), \
         patch("backend.services.search_adapter.TAVILY_API_KEY", "mock_key"), \
         patch("httpx.Client.post", return_value=mock_resp):
        res = execute_search_discovery(["ultra rare specific query"], ["rare"])
        assert res["status"] == "UNAVAILABLE"
        assert res["provider_state"] == "No Results"
        assert res["results"] == []


def test_search_successful_response_and_ssrf_filtering():
    """Verifies that safe public URLs are accepted while private/SSRF IPs are filtered."""
    raw_hits = [
        {
            "url": "https://www.sec.gov/news/press-release/2025-10",
            "title": "SEC Regulatory Framework Update",
            "content": "Regulatory guidelines on energy grid investments and mandatory audits.",
            "published_date": "2025-03-20"
        },
        {
            "url": "http://169.254.169.254/latest/meta-data/",
            "title": "Cloud Metadata Instance",
            "content": "AWS IAM credentials and instance metadata.",
        },
        {
            "url": "http://127.0.0.1:8000/internal-admin",
            "title": "Localhost Admin",
            "content": "Internal administrative controls.",
        },
        {
            "url": "https://www.reuters.com/business/energy-transition-2025",
            "title": "Energy Transition Report",
            "content": "Commercial renewables expanded across major industrial corridors.",
            "published_date": "2025-05-12"
        }
    ]

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"results": raw_hits}

    with patch("backend.services.search_adapter.SEARCH_PROVIDER", "tavily"), \
         patch("backend.services.search_adapter.TAVILY_API_KEY", "mock_key"), \
         patch("httpx.Client.post", return_value=mock_resp):
        res = execute_search_discovery(
            queries=["energy regulatory framework"],
            required_keywords=["regulatory", "energy", "audits"]
        )

        assert res["status"] == "ACTIVE"
        assert res["provider_state"] == "Available"
        assert res["is_available"] is True
        # Only the 2 safe public URLs should be in results; loopback and cloud metadata filtered by SSRF check!
        candidate_urls = [c["url"] for c in res["results"]]
        assert "https://www.sec.gov/news/press-release/2025-10" in candidate_urls
        assert "https://www.reuters.com/business/energy-transition-2025" in candidate_urls
        assert "http://169.254.169.254/latest/meta-data/" not in candidate_urls
        assert "http://127.0.0.1:8000/internal-admin" not in candidate_urls

        # Verify domain authority classification
        sec_item = next(c for c in res["results"] if "sec.gov" in c["url"])
        assert sec_item["authority_tier"] == "TIER_1"
        assert sec_item["published_date"] == "2025-03-20"
