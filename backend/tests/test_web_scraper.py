import asyncio
from unittest.mock import patch, AsyncMock
import httpx
import pytest
from backend.services.web_scraper import fetch_webpage, WebScrapingError


def test_web_scraper_extracts_article_and_strips_nav():
    sample_html = """
    <!DOCTYPE html>
    <html>
      <head>
        <title>Renewable Energy Adoption Trends in 2025</title>
        <meta name="author" content="Global Energy Council">
      </head>
      <body>
        <nav><a href="/home">Home</a> <a href="/login">Login</a></nav>
        <article>
          <h1>Renewable Energy Adoption Trends in 2025</h1>
          <p>Global solar capacity expanded by 34% across commercial sectors in fiscal year 2025.</p>
          <p>Offshore wind investments also accelerated in coastal economic development zones.</p>
        </article>
        <footer>Copyright 2025 All Rights Reserved</footer>
      </body>
    </html>
    """

    mock_response = httpx.Response(
        status_code=200,
        headers={"Content-Type": "text/html; charset=utf-8"},
        text=sample_html,
        request=httpx.Request("GET", "https://example.org/renewable-report")
    )

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response
        result = asyncio.run(fetch_webpage("https://example.org/renewable-report"))

        assert "Renewable Energy Adoption" in result["title"]
        assert "Global solar capacity expanded by 34%" in result["extracted_text"]
        # Ensure navigation was stripped
        assert "Login" not in result["extracted_text"]
        assert len(result["content_hash"]) == 64


def test_web_scraper_ssrf_rejection():
    with pytest.raises(WebScrapingError) as exc_info:
        asyncio.run(fetch_webpage("http://127.0.0.1:8080/secret"))
    assert "Security validation blocked" in str(exc_info.value)
