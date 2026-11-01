import re
import datetime
import dateutil.parser
from typing import Optional, Dict, Any, Tuple, List
from bs4 import BeautifulSoup

# Configurable freshness threshold in days (default 365 days / 1 year)
DEFAULT_FRESHNESS_THRESHOLD_DAYS = 365

# Classification Status Constants
STATUS_DATE_AVAILABLE = "Date Available"
STATUS_POTENTIALLY_OUTDATED = "Potentially Outdated"
STATUS_UNDATED_SOURCE = "Undated Source"
STATUS_DATE_UNAVAILABLE = "Date Unavailable"
STATUS_DATE_REQUIRES_REVIEW = "Date Requires Review"


def parse_and_validate_date(date_str: Optional[str]) -> Tuple[Optional[datetime.datetime], str]:
    """
    Parses arbitrary date strings into a timezone-aware UTC datetime.
    Supports ISO formats, PDF dates ('D:YYYYMMDDHHmmSS'), and human-readable dates.
    Returns: (parsed_datetime_utc, validation_status)
    validation_status is one of: 'VALID', 'MISSING', 'INVALID_FORMAT'
    """
    if not date_str or not str(date_str).strip():
        return None, "MISSING"

    raw_val = str(date_str).strip()

    # Clean PDF metadata date format: e.g., "D:20240515120000Z" or "D:20240515120000+05'30'"
    if raw_val.startswith("D:"):
        clean_pdf_date = raw_val[2:].replace("'", "")
        # Try matching YYYYMMDD
        m = re.match(r"^(\d{4})(\d{2})(\d{2})", clean_pdf_date)
        if m:
            try:
                year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
                dt = datetime.datetime(year, month, day, tzinfo=datetime.timezone.utc)
                return dt, "VALID"
            except Exception:
                pass

    try:
        # Use dateutil parser with fuzzy parsing disabled initially
        dt = dateutil.parser.parse(raw_val)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        else:
            dt = dt.astimezone(datetime.timezone.utc)
        return dt, "VALID"
    except Exception:
        # Fallback regex for common YYYY-MM-DD or YYYY/MM/DD
        m = re.search(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", raw_val)
        if m:
            try:
                year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
                dt = datetime.datetime(year, month, day, tzinfo=datetime.timezone.utc)
                return dt, "VALID"
            except Exception:
                pass

    return None, "INVALID_FORMAT"


def classify_source_freshness(
    publication_date_str: Optional[str],
    reference_time: Optional[datetime.datetime] = None,
    threshold_days: int = DEFAULT_FRESHNESS_THRESHOLD_DAYS,
    date_validation_status: Optional[str] = None,
    is_ambiguous: bool = False,
) -> Dict[str, Any]:
    """
    Deterministically classifies a source's freshness based on its actual publication date.
    Accepts an injectable reference clock for reproducible calculations and unit tests.
    Does NOT use ingestion date for classification.
    Flags conflicting date candidates as 'Date Requires Review'.
    """
    ref_dt = reference_time or datetime.datetime.now(datetime.timezone.utc)
    if ref_dt.tzinfo is None:
        ref_dt = ref_dt.replace(tzinfo=datetime.timezone.utc)

    # Check explicit ambiguity or conflicting candidate dates first
    if date_validation_status == "AMBIGUOUS" or is_ambiguous:
        return {
            "status": STATUS_DATE_REQUIRES_REVIEW,
            "is_outdated": False,
            "days_old": None,
            "threshold_days": threshold_days,
            "assessed_date": str(publication_date_str) if publication_date_str else None,
            "reference_date": ref_dt.isoformat(),
            "explanation": "Multiple conflicting publication dates were detected in source metadata. Requires manual analyst review to verify correct publication date.",
            "requires_review": True,
            "badge_variant": "gap",
        }

    if not publication_date_str or not str(publication_date_str).strip():
        return {
            "status": STATUS_UNDATED_SOURCE,
            "is_outdated": False,
            "days_old": None,
            "threshold_days": threshold_days,
            "assessed_date": None,
            "reference_date": ref_dt.isoformat(),
            "explanation": "No verifiable publication date could be extracted from source metadata. Verify publication vintage manually before relying on time-sensitive facts.",
            "requires_review": True,
            "badge_variant": "unverified",
        }

    parsed_dt, val_status = parse_and_validate_date(publication_date_str)

    if val_status == "INVALID_FORMAT" or parsed_dt is None:
        return {
            "status": STATUS_DATE_UNAVAILABLE,
            "is_outdated": False,
            "days_old": None,
            "threshold_days": threshold_days,
            "assessed_date": str(publication_date_str),
            "reference_date": ref_dt.isoformat(),
            "explanation": f"The publication date value '{publication_date_str}' could not be parsed into a valid timestamp. Requires manual inspection.",
            "requires_review": True,
            "badge_variant": "conflict",
        }

    delta = ref_dt - parsed_dt
    days_old = delta.total_seconds() / 86400.0

    # 1. Future publication date check (allow 1 day buffer for timezone discrepancies)
    if days_old < -1.0:
        return {
            "status": STATUS_DATE_REQUIRES_REVIEW,
            "is_outdated": False,
            "days_old": round(days_old, 1),
            "threshold_days": threshold_days,
            "assessed_date": parsed_dt.strftime("%Y-%m-%d"),
            "reference_date": ref_dt.isoformat(),
            "explanation": f"Source publication date ({parsed_dt.strftime('%Y-%m-%d')}) is in the future relative to the reference audit time. Requires analyst verification.",
            "requires_review": True,
            "badge_variant": "gap",
        }

    # 2. Older than configured threshold (e.g. 365 days)
    if days_old > threshold_days:
        int_days = int(days_old)
        years = round(int_days / 365.25, 1)
        return {
            "status": STATUS_POTENTIALLY_OUTDATED,
            "is_outdated": True,
            "days_old": int_days,
            "threshold_days": threshold_days,
            "assessed_date": parsed_dt.strftime("%Y-%m-%d"),
            "reference_date": ref_dt.isoformat(),
            "explanation": f"Source was published {int_days} days ago (~{years} yrs), which exceeds the {threshold_days}-day threshold. Older sources are not necessarily invalid or false, but require human review to confirm if conditions or regulatory policies have changed.",
            "requires_review": True,
            "badge_variant": "gap",
        }

    # 3. Within threshold
    int_days = max(0, int(days_old))
    return {
        "status": STATUS_DATE_AVAILABLE,
        "is_outdated": False,
        "days_old": int_days,
        "threshold_days": threshold_days,
        "assessed_date": parsed_dt.strftime("%Y-%m-%d"),
        "reference_date": ref_dt.isoformat(),
        "explanation": f"Published {int_days} days ago ({parsed_dt.strftime('%Y-%m-%d')}), within the {threshold_days}-day freshness window.",
        "requires_review": False,
        "badge_variant": "supported",
    }


def extract_web_date_metadata(html_text: str, headers: Dict[str, str], trafilatura_date: Optional[str] = None) -> Dict[str, Any]:
    """
    Thoroughly extracts publication and modification dates from HTML metadata,
    JSON-LD structured data, OpenGraph tags, Dublin Core, and HTTP headers.
    Retains conflicting candidates and explicitly distinguishes publication from modification.
    """
    candidates: List[Dict[str, Any]] = []
    modified_candidates: List[Dict[str, Any]] = []

    # 1. Trafilatura extracted date if available
    if trafilatura_date and str(trafilatura_date).strip():
        candidates.append({
            "date": str(trafilatura_date).strip(),
            "source": "trafilatura_metadata",
            "method": "readability_extraction",
            "confidence": 0.85
        })

    # 2. Parse HTML via BeautifulSoup for high-priority meta tags and JSON-LD
    try:
        soup = BeautifulSoup(html_text, "html.parser")

        # Check JSON-LD
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                import json
                data = json.loads(script.string or "")
                items = data if isinstance(data, list) else [data]
                for item in items:
                    if isinstance(item, dict):
                        if "datePublished" in item and item["datePublished"]:
                            candidates.append({
                                "date": str(item["datePublished"]),
                                "source": "jsonld_datePublished",
                                "method": "structured_schema",
                                "confidence": 0.95
                            })
                        if "dateCreated" in item and item["dateCreated"]:
                            candidates.append({
                                "date": str(item["dateCreated"]),
                                "source": "jsonld_dateCreated",
                                "method": "structured_schema",
                                "confidence": 0.80
                            })
                        if "dateModified" in item and item["dateModified"]:
                            modified_candidates.append({
                                "date": str(item["dateModified"]),
                                "source": "jsonld_dateModified",
                                "method": "structured_schema",
                                "confidence": 0.90
                            })
            except Exception:
                continue

        # Check meta tags
        meta_pub_tags = [
            ("article:published_time", "opengraph"),
            ("publication_date", "meta_standard"),
            ("pubdate", "meta_standard"),
            ("dc.date", "dublin_core"),
            ("dc.date.issued", "dublin_core"),
            ("sailthru.date", "sailthru"),
            ("parsely-pub-date", "parsely"),
            ("byl", "byline_meta"),
            ("publish-date", "meta_standard"),
        ]

        for tag_name, meta_type in meta_pub_tags:
            tag = soup.find("meta", property=tag_name) or soup.find("meta", attrs={"name": tag_name})
            if tag and tag.get("content"):
                candidates.append({
                    "date": tag["content"].strip(),
                    "source": f"meta_{tag_name}",
                    "method": meta_type,
                    "confidence": 0.90 if "article" in tag_name else 0.80
                })

        # Check modification meta tags
        meta_mod_tags = [
            ("article:modified_time", "opengraph"),
            ("last-modified", "meta_standard"),
            ("dc.date.modified", "dublin_core"),
            ("updated_time", "opengraph"),
        ]
        for tag_name, meta_type in meta_mod_tags:
            tag = soup.find("meta", property=tag_name) or soup.find("meta", attrs={"name": tag_name})
            if tag and tag.get("content"):
                modified_candidates.append({
                    "date": tag["content"].strip(),
                    "source": f"meta_{tag_name}",
                    "method": meta_type,
                    "confidence": 0.85
                })

    except Exception:
        pass

    # 3. HTTP Header Last-Modified (stored ONLY as modified date, never publication date)
    http_last_mod = headers.get("Last-Modified") or headers.get("last-modified")
    if http_last_mod:
        modified_candidates.append({
            "date": http_last_mod.strip(),
            "source": "http_header_last_modified",
            "method": "http_transport",
            "confidence": 0.70
        })

    # Pick best publication date candidate
    publication_date = None
    date_source = None
    date_extraction_method = None
    date_confidence = 0.0
    is_ambiguous = False

    if candidates:
        # Sort by confidence descending
        candidates.sort(key=lambda x: x["confidence"], reverse=True)
        best = candidates[0]
        parsed_best, status_best = parse_and_validate_date(best["date"])
        if status_best == "VALID":
            publication_date = parsed_best.strftime("%Y-%m-%d")
            date_source = best["source"]
            date_extraction_method = best["method"]
            date_confidence = best["confidence"]
        else:
            publication_date = best["date"]
            date_source = best["source"]
            date_extraction_method = best["method"]
            date_confidence = 0.3

        # Check for ambiguity if multiple distinct valid dates found
        unique_dates = set()
        for c in candidates:
            p_dt, st = parse_and_validate_date(c["date"])
            if st == "VALID" and p_dt:
                unique_dates.add(p_dt.strftime("%Y-%m-%d"))
        if len(unique_dates) > 1:
            is_ambiguous = True

    # Best modified date
    source_modified_date = None
    if modified_candidates:
        modified_candidates.sort(key=lambda x: x["confidence"], reverse=True)
        best_mod = modified_candidates[0]
        parsed_mod, st_mod = parse_and_validate_date(best_mod["date"])
        if st_mod == "VALID" and parsed_mod:
            source_modified_date = parsed_mod.strftime("%Y-%m-%d")
        else:
            source_modified_date = best_mod["date"]

    val_status = "VALID" if publication_date else "MISSING"
    if is_ambiguous:
        val_status = "AMBIGUOUS"

    return {
        "publication_date": publication_date,
        "source_modified_date": source_modified_date,
        "date_source": date_source,
        "date_extraction_method": date_extraction_method,
        "date_confidence": date_confidence,
        "date_validation_status": val_status,
        "candidates": candidates,
        "modified_candidates": modified_candidates,
    }


def extract_pdf_date_metadata(doc_metadata: Dict[str, Any], doc_first_pages_text: str = "") -> Dict[str, Any]:
    """
    Extracts dates from PDF documents with strict separation between creation and publication dates.
    PDF creation date must NOT automatically be treated as publication date.
    Looks for explicit publication markers in text (e.g. 'Published:', 'Publication Date:', 'Issue Date:').
    """
    meta_creation = doc_metadata.get("creationDate") or ""
    meta_mod = doc_metadata.get("modDate") or ""

    parsed_creation, st_create = parse_and_validate_date(meta_creation)
    parsed_mod, st_mod = parse_and_validate_date(meta_mod)

    creation_iso = parsed_creation.strftime("%Y-%m-%d") if (st_create == "VALID" and parsed_creation) else None
    mod_iso = parsed_mod.strftime("%Y-%m-%d") if (st_mod == "VALID" and parsed_mod) else None

    # Search for explicit publication date in the first few pages of text
    explicit_pub_date = None
    date_source = None
    date_method = None
    confidence = 0.0

    if doc_first_pages_text:
        # Regex patterns for explicit publication statements
        pub_patterns = [
            r"(?:published|publication date|published on|issue date|released on|date of publication)\s*[:\-]?\s*([A-Za-z]+\s+\d{1,2},?\s+\d{4})",
            r"(?:published|publication date|published on|issue date|released on|date of publication)\s*[:\-]?\s*(\d{1,2}\s+[A-Za-z]+\s+\d{4})",
            r"(?:published|publication date|published on|issue date|released on|date of publication)\s*[:\-]?\s*(\d{4}[-/.]\d{1,2}[-/.]\d{1,2})",
            r"(?:published|publication date|issued)\s*[:\-]?\s*([A-Za-z]+\s+\d{4})",
        ]
        for pat in pub_patterns:
            m = re.search(pat, doc_first_pages_text, re.IGNORECASE)
            if m:
                raw_match = m.group(1).strip()
                p_dt, st = parse_and_validate_date(raw_match)
                if st == "VALID" and p_dt:
                    explicit_pub_date = p_dt.strftime("%Y-%m-%d")
                    date_source = "pdf_text_explicit_marker"
                    date_method = "text_regex_extraction"
                    confidence = 0.90
                    break

    # If no explicit publication date was found in the text, DO NOT silently convert creationDate into publication date!
    # Explicitly mark as Undated, but keep creation date recorded in source_modified_date / date_source.
    validation_status = "VALID" if explicit_pub_date else "MISSING"

    return {
        "publication_date": explicit_pub_date,
        "source_modified_date": mod_iso or creation_iso,
        "pdf_creation_date": creation_iso,
        "date_source": date_source or ("pdf_metadata_creation" if creation_iso else None),
        "date_extraction_method": date_method or ("pdf_metadata_reader" if creation_iso else None),
        "date_confidence": confidence,
        "date_validation_status": validation_status,
    }


def compute_temporal_decay_factor(
    days_old: Optional[float],
    half_life_days: float = 365.0
) -> float:
    """
    Computes deterministic exponential confidence decay:
    factor = exp(- (ln(2) / half_life) * days_old)
    If days_old is None (undated), factor defaults to 0.70 (provisional penalization).
    If days_old <= 0 (recent or future), factor is 1.00.
    """
    if days_old is None:
        return 0.70
    if days_old <= 0:
        return 1.00

    import math
    decay_rate = math.log(2.0) / max(1.0, float(half_life_days))
    decay = math.exp(-decay_rate * float(days_old))
    return round(max(0.10, min(1.00, decay)), 3)
