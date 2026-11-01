import pytest
import datetime
from backend.services.freshness_service import (
    classify_source_freshness,
    extract_web_date_metadata,
    extract_pdf_date_metadata,
    STATUS_DATE_AVAILABLE,
    STATUS_POTENTIALLY_OUTDATED,
    STATUS_UNDATED_SOURCE,
    STATUS_DATE_UNAVAILABLE,
    STATUS_DATE_REQUIRES_REVIEW,
)

REF_DATE = datetime.datetime(2026, 10, 31, 0, 0, 0, tzinfo=datetime.timezone.utc)


def test_missing_date_produces_undated_source():
    """Missing or empty publication date must produce Undated Source, never crash."""
    for val in [None, "", "   "]:
        res = classify_source_freshness(val, reference_time=REF_DATE)
        assert res["status"] == STATUS_UNDATED_SOURCE
        assert res["is_outdated"] is False
        assert res["requires_review"] is True


def test_ambiguous_date_candidates_produce_date_requires_review():
    """Conflicting candidate dates must produce Date Requires Review."""
    res = classify_source_freshness("2026-05-01", reference_time=REF_DATE, date_validation_status="AMBIGUOUS")
    assert res["status"] == STATUS_DATE_REQUIRES_REVIEW
    assert "conflicting publication dates" in res["explanation"].lower()
    assert res["requires_review"] is True


def test_future_date_produces_date_requires_review():
    """Publication date in the future relative to reference clock requires analyst review."""
    future_date = "2028-01-15"
    res = classify_source_freshness(future_date, reference_time=REF_DATE)
    assert res["status"] == STATUS_DATE_REQUIRES_REVIEW
    assert "in the future" in res["explanation"]
    assert res["requires_review"] is True


def test_invalid_date_format_produces_date_unavailable():
    """Unparseable string produces Date Unavailable with inspection requirement."""
    res = classify_source_freshness("not-a-real-date-string-123", reference_time=REF_DATE)
    assert res["status"] == STATUS_DATE_UNAVAILABLE
    assert res["requires_review"] is True


def test_365_day_threshold_boundary():
    """Consistent application of 365-day threshold."""
    # 200 days old -> Date Available
    fresh_date = "2026-04-14"
    res_fresh = classify_source_freshness(fresh_date, reference_time=REF_DATE, threshold_days=365)
    assert res_fresh["status"] == STATUS_DATE_AVAILABLE
    assert res_fresh["is_outdated"] is False

    # 400 days old -> Potentially Outdated
    old_date = "2025-09-26"
    res_old = classify_source_freshness(old_date, reference_time=REF_DATE, threshold_days=365)
    assert res_old["status"] == STATUS_POTENTIALLY_OUTDATED
    assert res_old["is_outdated"] is True
    assert "Publication age is an indicator for review, not proof of inaccuracy." in res_old["explanation"] or "threshold" in res_old["explanation"]


def test_pdf_creation_date_not_promoted_to_publication_date():
    """PDF metadata creationDate must NOT be silently promoted to publication date."""
    doc_metadata = {"creationDate": "D:20250101120000Z", "modDate": "D:20250601120000Z"}
    doc_text = "This report discusses energy infrastructure in Southeast Asia without an explicit publication header."
    
    extracted = extract_pdf_date_metadata(doc_metadata, doc_text)
    assert extracted["publication_date"] is None
    assert extracted["pdf_creation_date"] == "2025-01-01"
    assert extracted["date_validation_status"] == "MISSING"


def test_http_last_modified_not_promoted_to_publication_date():
    """HTTP Last-Modified header is recorded as source_modified_date, never publication date."""
    headers = {"Last-Modified": "Wed, 21 Oct 2025 07:28:00 GMT"}
    html = "<html><body><p>Article content without schema markup</p></body></html>"
    
    extracted = extract_web_date_metadata(html, headers)
    assert extracted["publication_date"] is None
    assert extracted["source_modified_date"] is not None
    assert extracted["date_validation_status"] == "MISSING"
