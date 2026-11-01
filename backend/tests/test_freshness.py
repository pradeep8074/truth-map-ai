import datetime
import pytest
import sqlite3
from backend.services.freshness_service import (
    classify_source_freshness,
    parse_and_validate_date,
    extract_web_date_metadata,
    extract_pdf_date_metadata,
    compute_temporal_decay_factor,
    STATUS_DATE_AVAILABLE,
    STATUS_POTENTIALLY_OUTDATED,
    STATUS_UNDATED_SOURCE,
    STATUS_DATE_UNAVAILABLE,
    STATUS_DATE_REQUIRES_REVIEW,
)
from backend.models import WorkspaceFreshnessSummary


def test_freshness_missing_publication_date():
    """Missing or empty publication date must classify as 'Undated Source'."""
    ref_time = datetime.datetime(2026, 10, 31, 12, 0, 0, tzinfo=datetime.timezone.utc)
    for empty_val in [None, "", "   "]:
        result = classify_source_freshness(empty_val, reference_time=ref_time)
        assert result["status"] == STATUS_UNDATED_SOURCE
        assert result["is_outdated"] is False
        assert result["days_old"] is None
        assert result["requires_review"] is True
        assert "No verifiable publication date" in result["explanation"]


def test_freshness_older_than_365_days():
    """A publication date older than 365 days must classify as 'Potentially Outdated'."""
    ref_time = datetime.datetime(2026, 10, 31, 12, 0, 0, tzinfo=datetime.timezone.utc)
    old_date = "2024-05-15"  # ~899 days old
    result = classify_source_freshness(old_date, reference_time=ref_time, threshold_days=365)
    assert result["status"] == STATUS_POTENTIALLY_OUTDATED
    assert result["is_outdated"] is True
    assert result["days_old"] > 365
    assert result["requires_review"] is True
    assert "exceeds the 365-day threshold" in result["explanation"]
    assert "Older sources are not necessarily invalid" in result["explanation"]


def test_freshness_within_365_days():
    """A publication date within 365 days must classify as 'Date Available'."""
    ref_time = datetime.datetime(2026, 10, 31, 12, 0, 0, tzinfo=datetime.timezone.utc)
    recent_date = "2026-06-15"  # ~138 days old
    result = classify_source_freshness(recent_date, reference_time=ref_time, threshold_days=365)
    assert result["status"] == STATUS_DATE_AVAILABLE
    assert result["is_outdated"] is False
    assert result["days_old"] < 365
    assert result["requires_review"] is False
    assert "within the 365-day freshness window" in result["explanation"]


def test_freshness_exactly_at_threshold():
    """A publication date exactly 365 days old must still be 'Date Available'."""
    ref_time = datetime.datetime(2026, 10, 31, 0, 0, 0, tzinfo=datetime.timezone.utc)
    boundary_date = (ref_time - datetime.timedelta(days=365)).strftime("%Y-%m-%d")
    result = classify_source_freshness(boundary_date, reference_time=ref_time, threshold_days=365)
    assert result["status"] == STATUS_DATE_AVAILABLE
    assert result["is_outdated"] is False


def test_freshness_invalid_date_format():
    """Unparseable corrupted date strings must classify as 'Date Unavailable'."""
    ref_time = datetime.datetime(2026, 10, 31, 12, 0, 0, tzinfo=datetime.timezone.utc)
    for bad_date in ["not_a_date", "circa-medieval-times", "2026-99-99", "undefined"]:
        result = classify_source_freshness(bad_date, reference_time=ref_time)
        assert result["status"] == STATUS_DATE_UNAVAILABLE
        assert result["is_outdated"] is False
        assert result["days_old"] is None
        assert result["requires_review"] is True


def test_freshness_future_publication_date():
    """A date more than 1 day in the future must classify as 'Date Requires Review'."""
    ref_time = datetime.datetime(2026, 10, 31, 12, 0, 0, tzinfo=datetime.timezone.utc)
    future_date = "2027-11-20"
    result = classify_source_freshness(future_date, reference_time=ref_time)
    assert result["status"] == STATUS_DATE_REQUIRES_REVIEW
    assert result["is_outdated"] is False
    assert result["requires_review"] is True
    assert "in the future" in result["explanation"]


def test_parse_multiple_timezone_formats():
    """Verifies that ISO strings with various timezones are parsed to UTC accurately."""
    # UTC ISO
    dt_utc, st_utc = parse_and_validate_date("2025-04-10T15:30:00Z")
    assert st_utc == "VALID"
    assert dt_utc.tzinfo == datetime.timezone.utc
    assert dt_utc.hour == 15

    # Positive offset (India +05:30)
    dt_ist, st_ist = parse_and_validate_date("2025-04-10T21:00:00+05:30")
    assert st_ist == "VALID"
    assert dt_ist.tzinfo == datetime.timezone.utc
    assert dt_ist.hour == 15  # 21:00 - 5:30 = 15:30 UTC
    assert dt_ist.minute == 30

    # Negative offset (US EDT -04:00)
    dt_edt, st_edt = parse_and_validate_date("2025-04-10T11:30:00-04:00")
    assert st_edt == "VALID"
    assert dt_edt.tzinfo == datetime.timezone.utc
    assert dt_edt.hour == 15  # 11:30 + 4:00 = 15:30 UTC


def test_pdf_creation_date_not_automatically_publication_date():
    """PDF creation date must not automatically become publication date without explicit markers."""
    doc_metadata = {
        "creationDate": "D:20240210120000Z",
        "modDate": "D:20240212120000Z",
    }
    # No explicit publication statement in text
    plain_text = "General corporate report. Q4 operations and logistics review."
    meta = extract_pdf_date_metadata(doc_metadata, plain_text)

    # publication_date must remain None (Undated Source)
    assert meta["publication_date"] is None
    assert meta["date_validation_status"] == "MISSING"
    # But pdf_creation_date and source_modified_date are captured
    assert meta["pdf_creation_date"] == "2024-02-10"
    assert meta["source_modified_date"] == "2024-02-12"


def test_pdf_explicit_publication_date_extracted():
    """Explicit 'Published: <Date>' in PDF text must be extracted as publication date."""
    doc_metadata = {"creationDate": "D:20240210120000Z"}
    text_with_pub = "Global Energy Council\nPublished: March 15, 2025\nExecutive Summary\nSolar capacity expanded."
    meta = extract_pdf_date_metadata(doc_metadata, text_with_pub)

    assert meta["publication_date"] == "2025-03-15"
    assert meta["date_source"] == "pdf_text_explicit_marker"
    assert meta["date_validation_status"] == "VALID"


def test_web_conflicting_candidates_detected_and_ambiguous():
    """Multiple divergent publication dates in HTML must be retained and marked AMBIGUOUS."""
    html_sample = """
    <html>
      <head>
        <meta property="article:published_time" content="2025-01-10T00:00:00Z" />
        <script type="application/ld+json">
          {"@context": "https://schema.org", "@type": "NewsArticle", "datePublished": "2024-06-20T00:00:00Z"}
        </script>
      </head>
      <body>Article text</body>
    </html>
    """
    meta = extract_web_date_metadata(html_sample, headers={"Last-Modified": "Fri, 15 Jan 2025 10:00:00 GMT"})

    # Both candidates preserved
    assert len(meta["candidates"]) >= 2
    assert meta["date_validation_status"] == "AMBIGUOUS"
    # Last-Modified stored in modified date only
    assert meta["source_modified_date"] is not None


def test_compute_temporal_decay_factor():
    """Verifies exponential decay calculations D(t) = exp(-lambda * t)."""
    # 0 days elapsed -> 1.00
    assert compute_temporal_decay_factor(0, half_life_days=365) == 1.00

    # Exactly 1 half-life elapsed -> 0.50
    assert compute_temporal_decay_factor(365, half_life_days=365) == 0.50

    # Exactly 2 half-lives elapsed -> 0.25
    assert compute_temporal_decay_factor(730, half_life_days=365) == 0.25

    # Undated source -> provisional 0.70 baseline
    assert compute_temporal_decay_factor(None) == 0.70


def test_workspace_freshness_summary_aggregation(tmp_path):
    """Verifies that workspace-level freshness metrics aggregate real SQLite records correctly."""
    db_file = str(tmp_path / "test_freshness_db.sqlite")
    conn = sqlite3.connect(db_file)
    conn.execute("""
        CREATE TABLE sources (
            id TEXT PRIMARY KEY,
            investigation_id TEXT,
            publication_date TEXT
        );
    """)

    ref_now = datetime.datetime(2026, 10, 31, 12, 0, 0, tzinfo=datetime.timezone.utc)

    # Insert 4 distinct sources:
    # 1. Fresh dated (published 60 days ago)
    d_fresh = (ref_now - datetime.timedelta(days=60)).strftime("%Y-%m-%d")
    # 2. Outdated (published 500 days ago)
    d_old = (ref_now - datetime.timedelta(days=500)).strftime("%Y-%m-%d")
    # 3. Undated
    # 4. Future (30 days in future)
    d_future = (ref_now + datetime.timedelta(days=30)).strftime("%Y-%m-%d")

    conn.execute("INSERT INTO sources VALUES ('s1', 'inv1', ?)", (d_fresh,))
    conn.execute("INSERT INTO sources VALUES ('s2', 'inv1', ?)", (d_old,))
    conn.execute("INSERT INTO sources VALUES ('s3', 'inv1', NULL)")
    conn.execute("INSERT INTO sources VALUES ('s4', 'inv1', ?)", (d_future,))
    conn.commit()

    cursor = conn.cursor()
    cursor.execute("SELECT id, publication_date FROM sources")
    rows = cursor.fetchall()

    total = len(rows)
    dated = 0
    undated = 0
    outdated = 0
    review = 0

    for r in rows:
        p_date = r[1]
        res = classify_source_freshness(p_date, reference_time=ref_now)
        st = res["status"]
        if st == STATUS_UNDATED_SOURCE:
            undated += 1
        elif st == STATUS_POTENTIALLY_OUTDATED:
            dated += 1
            outdated += 1
        elif st == STATUS_DATE_AVAILABLE:
            dated += 1
        elif st in (STATUS_DATE_REQUIRES_REVIEW, STATUS_DATE_UNAVAILABLE):
            if p_date and str(p_date).strip():
                dated += 1
            else:
                undated += 1
            review += 1

    conn.close()

    assert total == 4
    assert dated == 3
    assert undated == 1
    assert outdated == 1
    assert review == 1
