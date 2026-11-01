import pytest
from unittest.mock import patch, MagicMock
import httpx
from backend.services.search_adapter import execute_search_discovery


def test_search_missing_key_behavior(monkeypatch):
    """When TAVILY_API_KEY is not configured, provider returns UNAVAILABLE with BLOCKED BY CONFIGURATION notice."""
    monkeypatch.setattr("backend.services.search_adapter.SEARCH_PROVIDER", "tavily")
    monkeypatch.setattr("backend.services.search_adapter.TAVILY_API_KEY", "")

    result = execute_search_discovery(["Solar microgrid Vietnam licensing"])
    assert result["status"] == "UNAVAILABLE"
    assert result["provider_state"] == "Missing Configuration"
    assert result["is_available"] is False
    assert "BLOCKED BY CONFIGURATION" in result["message"]
    assert "requires TAVILY_API_KEY" in result["message"]
    assert result["results"] == []


def test_search_provider_none_behavior(monkeypatch):
    """When SEARCH_PROVIDER is none, returns UNAVAILABLE with manual fallback message."""
    monkeypatch.setattr("backend.services.search_adapter.SEARCH_PROVIDER", "none")
    monkeypatch.setattr("backend.services.search_adapter.TAVILY_API_KEY", "")

    result = execute_search_discovery(["Renewable energy policy"])
    assert result["status"] == "UNAVAILABLE"
    assert result["provider_state"] == "Missing Configuration"
    assert result["is_available"] is False
    assert "Manual candidate URL entry mode active" in result["message"]


def test_search_invalid_key_behavior(monkeypatch):
    """When Tavily returns HTTP 401/403, returns UNAVAILABLE with authentication failed and BLOCKED BY CONFIGURATION notice."""
    monkeypatch.setattr("backend.services.search_adapter.SEARCH_PROVIDER", "tavily")
    monkeypatch.setattr("backend.services.search_adapter.TAVILY_API_KEY", "tvly-invalid-key-example")

    mock_resp = MagicMock()
    mock_resp.status_code = 401

    with patch("httpx.Client.post", return_value=mock_resp):
        result = execute_search_discovery(["Solar microgrid tariffs"])
        assert result["status"] == "UNAVAILABLE"
        assert result["provider_state"] == "Failed"
        assert result["is_available"] is False
        assert "authentication failed" in result["message"]
        assert "BLOCKED BY CONFIGURATION" in result["message"]


def test_search_rate_limit_behavior(monkeypatch):
    """When Tavily returns HTTP 429, returns Rate Limited."""
    monkeypatch.setattr("backend.services.search_adapter.SEARCH_PROVIDER", "tavily")
    monkeypatch.setattr("backend.services.search_adapter.TAVILY_API_KEY", "tvly-mock-valid-key")

    mock_resp = MagicMock()
    mock_resp.status_code = 429

    with patch("httpx.Client.post", return_value=mock_resp):
        result = execute_search_discovery(["Cross border PPA"])
        assert result["status"] == "UNAVAILABLE"
        assert result["provider_state"] == "Rate Limited"
        assert result["is_available"] is False
        assert "rate limit exceeded" in result["message"]


def test_search_timeout_behavior(monkeypatch):
    """When Tavily client times out, gracefully returns Timeout."""
    monkeypatch.setattr("backend.services.search_adapter.SEARCH_PROVIDER", "tavily")
    monkeypatch.setattr("backend.services.search_adapter.TAVILY_API_KEY", "tvly-mock-valid-key")

    with patch("httpx.Client.post", side_effect=httpx.TimeoutException("Connection timed out")):
        result = execute_search_discovery(["Grid stabilization"])
        assert result["status"] == "UNAVAILABLE"
        assert result["provider_state"] == "Unavailable"
        assert result["is_available"] is False
        assert "timed out" in result["message"]


def test_search_valid_response_with_mock_credentials(monkeypatch):
    """When credentials are valid and provider returns hits, parses and scores candidate sources."""
    monkeypatch.setattr("backend.services.search_adapter.SEARCH_PROVIDER", "tavily")
    monkeypatch.setattr("backend.services.search_adapter.TAVILY_API_KEY", "tvly-mock-active-key")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "results": [
            {
                "url": "https://sec.gov/filings/energy-audit-2026.pdf",
                "title": "SEC Official Energy Audit 2026",
                "content": "Official statutory audit confirming tariff stabilization and sovereign guarantees."
            }
        ]
    }

    with patch("httpx.Client.post", return_value=mock_resp):
        result = execute_search_discovery(["Official energy audit"], required_keywords=["audit", "tariff"])
        assert result["status"] == "ACTIVE"
        assert result["provider_state"] == "Available"
        assert result["is_available"] is True
        assert len(result["results"]) == 1
        item = result["results"][0]
        assert item["domain_authority_tier"] == "TIER_1"
        assert item["url"] == "https://sec.gov/filings/energy-audit-2026.pdf"
