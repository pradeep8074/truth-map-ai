import re
import urllib.parse
from typing import Dict, Any, List, Tuple, Optional
from backend.config import (
    SEARCH_PROVIDER,
    TAVILY_API_KEY,
    SEARCH_TIMEOUT_SECONDS,
    SEARCH_MAX_RESULTS,
)
from backend.security import is_safe_url

TIER_1_DOMAINS = {
    "sec.gov", "rbi.org.in", "federalregister.gov", "supremecourt.gov",
    "fda.gov", "epa.gov", "justice.gov", "bis.org", "imf.org", "worldbank.org",
    "treasury.gov", "ftc.gov", "fcc.gov", "iso.org", "nist.gov", "who.int"
}

TIER_2_PATTERNS = [
    r"\.edu$", r"\.ac\.[a-z]{2}$", r"investor\.", r"ir\.", r"annualreports\.com",
    r"arxiv\.org", r"sciencedirect\.com", r"nature\.com", r"ieee\.org"
]

TIER_3_DOMAINS = {
    "reuters.com", "bloomberg.com", "ft.com", "wsj.com", "nytimes.com",
    "cnbc.com", "forbes.com", "spglobal.com", "moodys.com", "gartner.com"
}

TIER_4_DOMAINS = {
    "medium.com", "prnewswire.com", "businesswire.com", "globenewswire.com",
    "substack.com", "wordpress.com", "blogspot.com", "twitter.com", "x.com",
    "linkedin.com", "reddit.com", "facebook.com", "youtube.com"
}


def classify_domain_authority(url: str) -> Tuple[str, float]:
    """
    Classifies an external URL's domain authority into one of 4 tiers.
    Returns: (authority_tier, weight)
    - TIER_1: Regulatory & Statutory Registries (1.00)
    - TIER_2: Primary Disclosures, Audited Reports & Academic Research (0.85)
    - TIER_3: Reputable Financial & Industry Press (0.60)
    - TIER_4: Secondary News, Blogs, Vendor Marketing (0.25)
    """
    try:
        parsed = urllib.parse.urlparse(url)
        hostname = (parsed.hostname or "").lower()
    except Exception:
        return "TIER_4", 0.25

    if not hostname:
        return "TIER_4", 0.25

    # Check TIER 1
    if hostname.endswith(".gov") or hostname.endswith(".mil") or hostname in TIER_1_DOMAINS:
        return "TIER_1", 1.00
    for t1 in TIER_1_DOMAINS:
        if hostname.endswith("." + t1):
            return "TIER_1", 1.00

    # Check TIER 2
    for pat in TIER_2_PATTERNS:
        if re.search(pat, hostname):
            return "TIER_2", 0.85

    # Check TIER 4 (before Tier 3 check to catch blogs/wires)
    for t4 in TIER_4_DOMAINS:
        if hostname == t4 or hostname.endswith("." + t4):
            return "TIER_4", 0.25

    # Check TIER 3
    for t3 in TIER_3_DOMAINS:
        if hostname == t3 or hostname.endswith("." + t3):
            return "TIER_3", 0.60

    # Default general web domain
    return "TIER_3", 0.60


def calculate_candidate_relevance(
    title: str,
    snippet: str,
    required_keywords: List[str],
    authority_weight: float
) -> Tuple[float, str]:
    """
    Calculates prototype heuristic relevance score for a candidate search hit:
    S_relevance = min(100.0, 40*K_title + 30*K_snippet + 30*w_auth)
    """
    if not required_keywords:
        score = round(min(100.0, 50.0 + 50.0 * authority_weight), 1)
        return score, f"Keyword-neutral assessment with authority weight {authority_weight:.2f}."

    title_lower = (title or "").lower()
    snippet_lower = (snippet or "").lower()

    title_matches = sum(1 for kw in required_keywords if kw.lower() in title_lower)
    snippet_matches = sum(1 for kw in required_keywords if kw.lower() in snippet_lower)

    norm_denom = max(1, min(len(required_keywords), 3))
    k_title = min(1.0, title_matches / norm_denom)
    k_snippet = min(1.0, snippet_matches / norm_denom)

    score = min(100.0, 40.0 * k_title + 30.0 * k_snippet + 30.0 * authority_weight)
    score = round(score, 1)

    rationale = (
        f"Candidate matched {title_matches}/{len(required_keywords)} title keywords, "
        f"{snippet_matches}/{len(required_keywords)} snippet keywords, "
        f"with authority weight {authority_weight:.2f}."
    )
    return score, rationale


def execute_search_discovery(
    queries: List[str],
    required_keywords: Optional[List[str]] = None,
    max_results: int = SEARCH_MAX_RESULTS,
    existing_urls: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Executes search discovery through the configured search adapter.
    Enforces security SSRF validation, candidate deduplication, and provider state reporting.
    Provider states: Available, Missing Configuration, Unavailable, Rate Limited, Failed, No Results.
    Never falls back to predefined or canned queries.
    """
    keywords = required_keywords or []
    if not queries:
        return {
            "status": "UNAVAILABLE",
            "provider_state": "Missing Configuration",
            "is_available": False,
            "provider": SEARCH_PROVIDER or "none",
            "results": [],
            "message": "No verification queries formulated. Please formulate queries or enter candidate URLs manually."
        }

    if SEARCH_PROVIDER in ("none", "", None):
        return {
            "status": "UNAVAILABLE",
            "provider_state": "Missing Configuration",
            "is_available": False,
            "provider": "none",
            "results": [],
            "message": "Autonomous search provider is not configured. Manual candidate URL entry mode active (BLOCKED BY CONFIGURATION)."
        }

    # If Tavily configured but key is missing
    if SEARCH_PROVIDER == "tavily" and not TAVILY_API_KEY:
        return {
            "status": "UNAVAILABLE",
            "provider_state": "Missing Configuration",
            "is_available": False,
            "provider": "tavily",
            "results": [],
            "message": "Tavily autonomous search provider requires TAVILY_API_KEY (BLOCKED BY CONFIGURATION). Manual candidate URL and PDF workflows remain fully operational."
        }

    # If Tavily configured with key
    if SEARCH_PROVIDER == "tavily" and TAVILY_API_KEY:
        try:
            import httpx
            results: List[Dict[str, Any]] = []
            seen_urls = set(existing_urls or [])

            for q in queries[:2]:
                with httpx.Client(timeout=SEARCH_TIMEOUT_SECONDS) as client:
                    resp = client.post(
                        "https://api.tavily.com/search",
                        json={
                            "api_key": TAVILY_API_KEY,
                            "query": q,
                            "max_results": max_results,
                            "include_raw_content": False
                        }
                    )
                    if resp.status_code == 429:
                        return {
                            "status": "UNAVAILABLE",
                            "provider_state": "Rate Limited",
                            "is_available": False,
                            "provider": "tavily",
                            "results": [],
                            "message": "Tavily search API rate limit exceeded (HTTP 429). Please retry later or provide manual candidate URLs."
                        }
                    if resp.status_code in (401, 403):
                        return {
                            "status": "UNAVAILABLE",
                            "provider_state": "Failed",
                            "is_available": False,
                            "provider": "tavily",
                            "results": [],
                            "message": f"Tavily authentication failed (HTTP {resp.status_code}). Invalid or expired TAVILY_API_KEY (BLOCKED BY CONFIGURATION)."
                        }
                    if resp.status_code >= 400:
                        return {
                            "status": "UNAVAILABLE",
                            "provider_state": "Failed",
                            "is_available": False,
                            "provider": "tavily",
                            "results": [],
                            "message": f"Tavily search provider returned HTTP {resp.status_code}."
                        }

                    data = resp.json()
                    for item in data.get("results", []):
                        url = (item.get("url") or "").strip()
                        if not url or url in seen_urls:
                            continue
                        
                        is_safe, _ = is_safe_url(url)
                        if not is_safe:
                            continue

                        seen_urls.add(url)
                        tier, weight = classify_domain_authority(url)
                        rel_score, rel_rationale = calculate_candidate_relevance(
                            item.get("title", ""), item.get("content", ""), keywords, weight
                        )
                        parsed = urllib.parse.urlparse(url)
                        results.append({
                            "url": url,
                            "domain": parsed.hostname or url,
                            "title": item.get("title", "") or url,
                            "snippet": item.get("content", "")[:300],
                            "published_date": item.get("published_date") or None,
                            "authority_tier": tier,
                            "domain_authority_tier": tier,
                            "relevance_score": rel_score,
                            "relevance_rationale": rel_rationale,
                            "discovery_mode": "SEARCH_PROVIDER"
                        })

            if not results:
                return {
                    "status": "UNAVAILABLE",
                    "provider_state": "No Results",
                    "is_available": False,
                    "provider": "tavily",
                    "results": [],
                    "message": "Search provider completed with 0 results matching the dynamic query context."
                }

            return {
                "status": "ACTIVE",
                "provider_state": "Available",
                "is_available": True,
                "provider": "tavily",
                "results": results,
                "message": f"Retrieved {len(results)} candidate sources via Tavily search."
            }
        except httpx.TimeoutException:
            return {
                "status": "UNAVAILABLE",
                "provider_state": "Unavailable",
                "is_available": False,
                "provider": "tavily",
                "results": [],
                "message": f"Search provider request timed out after {SEARCH_TIMEOUT_SECONDS}s. Fallback to manual URL entry."
            }
        except Exception as e:
            return {
                "status": "UNAVAILABLE",
                "provider_state": "Failed",
                "is_available": False,
                "provider": "tavily",
                "results": [],
                "message": f"Search provider request failed: {str(e)}. Fallback to manual URL entry."
            }

    # Fallback default
    return {
        "status": "UNAVAILABLE",
        "provider_state": "Missing Configuration",
        "is_available": False,
        "provider": SEARCH_PROVIDER,
        "results": [],
        "message": f"Search provider '{SEARCH_PROVIDER}' is not active or missing API keys. Manual URL entry active."
    }
