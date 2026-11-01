import datetime
import hashlib
from urllib.parse import urlparse
import httpx
import trafilatura
from bs4 import BeautifulSoup

from backend.config import (
    CONNECT_TIMEOUT,
    READ_TIMEOUT,
    MAX_CONTENT_LENGTH,
    MAX_REDIRECTS,
)
from backend.security import is_safe_url, sanitize_text
from backend.services.freshness_service import extract_web_date_metadata


class WebScrapingError(Exception):
    pass


async def fetch_webpage(url: str) -> dict:
    """
    Fetches and extracts clean article text and metadata from a live web URL.
    Enforces SSRF prevention on initial URL and on all redirect hops.
    Enforces maximum payload length and response timeouts.
    """
    # 1. Initial SSRF check
    is_safe, reason = is_safe_url(url)
    if not is_safe:
        raise WebScrapingError(f"Security validation blocked URL '{url}': {reason}")

    retrieved_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 TruthMap-ForensicAudit/1.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

    current_url = url
    redirect_count = 0

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(CONNECT_TIMEOUT, read=READ_TIMEOUT),
        follow_redirects=False,
        verify=True,
    ) as client:
        while True:
            try:
                response = await client.get(current_url, headers=headers)
            except httpx.TimeoutException:
                raise WebScrapingError(f"Connection timed out while fetching '{current_url}'")
            except httpx.RequestError as e:
                raise WebScrapingError(f"Network error fetching '{current_url}': {str(e)}")

            # Handle redirects manually to inspect target IP safety
            if response.status_code in (301, 302, 303, 307, 308):
                redirect_count += 1
                if redirect_count > MAX_REDIRECTS:
                    raise WebScrapingError(f"Exceeded maximum redirects ({MAX_REDIRECTS})")
                
                location = response.headers.get("Location")
                if not location:
                    raise WebScrapingError("Redirect response missing 'Location' header")
                
                # Resolve relative redirect URLs
                next_url = str(httpx.URL(current_url).join(location))
                safe_redirect, redirect_reason = is_safe_url(next_url)
                if not safe_redirect:
                    raise WebScrapingError(f"SSRF blocked redirect to unsafe destination '{next_url}': {redirect_reason}")
                
                current_url = next_url
                continue
            
            break

    # 2. Check HTTP status code
    if response.status_code >= 400:
        raise WebScrapingError(f"Web server responded with HTTP {response.status_code}: {response.reason_phrase}")

    # 3. Check Content-Type & Length
    content_type = response.headers.get("Content-Type", "").lower()
    raw_content = response.content

    if len(raw_content) > MAX_CONTENT_LENGTH:
        raise WebScrapingError(f"Response size ({len(raw_content)} bytes) exceeded limit of {MAX_CONTENT_LENGTH} bytes")

    # 4. Content Hash
    content_hash = hashlib.sha256(raw_content).hexdigest()
    parsed_domain = urlparse(current_url).netloc

    # Handle PDF responses if a public source URL points directly to a PDF document
    if raw_content.startswith(b"%PDF-") or "application/pdf" in content_type:
        from backend.services.pdf_parser import parse_pdf_document
        import os
        filename = os.path.basename(urlparse(current_url).path) or "document.pdf"
        pdf_res = parse_pdf_document(raw_content, filename)
        return {
            "url": current_url,
            "title": pdf_res.get("title") or filename or parsed_domain,
            "publisher": pdf_res.get("publisher") or parsed_domain,
            "publication_date": pdf_res.get("publication_date"),
            "source_modified_date": pdf_res.get("source_modified_date"),
            "date_source": pdf_res.get("date_source"),
            "date_extraction_method": pdf_res.get("date_extraction_method"),
            "date_confidence": pdf_res.get("date_confidence", 0.0),
            "date_validation_status": pdf_res.get("date_validation_status", "Undated Source"),
            "retrieved_at": retrieved_at,
            "content_type": "application/pdf",
            "http_status": response.status_code,
            "content_hash": pdf_res.get("content_hash", content_hash),
            "extracted_text": pdf_res.get("extracted_text", ""),
        }

    # 5. Extract readable article content using Trafilatura
    html_text = response.text
    extracted_text = trafilatura.extract(
        html_text,
        include_links=False,
        include_images=False,
        include_tables=True,
        no_fallback=False,
        favor_recall=True,
    )

    metadata_obj = trafilatura.extract_metadata(html_text)
    title = metadata_obj.title if metadata_obj and metadata_obj.title else ""
    publisher = metadata_obj.sitename if metadata_obj and metadata_obj.sitename else parsed_domain
    raw_pub_date = metadata_obj.date if metadata_obj and metadata_obj.date else ""

    # Comprehensive date extraction with separation of publication and modification dates
    date_meta = extract_web_date_metadata(
        html_text=html_text,
        headers=dict(response.headers),
        trafilatura_date=raw_pub_date
    )
    pub_date = date_meta["publication_date"]

    # 6. Fallback extraction with BeautifulSoup if Trafilatura yields insufficient text
    if not extracted_text or len(extracted_text.strip()) < 50:
        soup = BeautifulSoup(html_text, "html.parser")
        
        # Remove script, style, navigation, footer, header
        for tag in soup(["script", "style", "nav", "footer", "header", "noscript", "aside", "svg"]):
            tag.decompose()

        if not title:
            title_tag = soup.find("title")
            title = title_tag.get_text(strip=True) if title_tag else ""

        # Target main content containers
        main_container = soup.find("article") or soup.find("main") or soup.find(id="content") or soup.body
        if main_container:
            paragraphs = main_container.find_all(["p", "h1", "h2", "h3", "h4", "li"])
            text_blocks = [p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 20]
            extracted_text = "\n\n".join(text_blocks)

    if not extracted_text or len(extracted_text.strip()) < 30:
        raise WebScrapingError(f"No readable article text could be extracted from '{current_url}'. The page may rely on client-side JS rendering or be blocked.")

    clean_text = sanitize_text(extracted_text)

    return {
        "url": current_url,
        "title": title or parsed_domain,
        "publisher": publisher,
        "publication_date": pub_date,
        "source_modified_date": date_meta["source_modified_date"],
        "date_source": date_meta["date_source"],
        "date_extraction_method": date_meta["date_extraction_method"],
        "date_confidence": date_meta["date_confidence"],
        "date_validation_status": date_meta["date_validation_status"],
        "retrieved_at": retrieved_at,
        "content_type": content_type,
        "http_status": response.status_code,
        "content_hash": content_hash,
        "extracted_text": clean_text,
    }
