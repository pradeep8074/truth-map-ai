import pytest
from backend.services.provenance import (
    compute_sha256,
    normalize_for_fingerprint,
    segment_into_passages,
)


def test_normalization_and_sha256_reproducibility():
    text1 = "  India's Digital Payments Recorded   Substantial Growth in 2025. \n "
    text2 = "india's digital payments recorded substantial growth in 2025."
    
    assert normalize_for_fingerprint(text1) == normalize_for_fingerprint(text2)
    assert compute_sha256(text1) == compute_sha256(text2)
    # Ensure it's a valid 64-char hex string
    assert len(compute_sha256(text1)) == 64


def test_passage_segmentation_offsets_and_page_number():
    sample_doc = (
        "This is paragraph one containing important economic and regulatory findings.\n\n"
        "This is paragraph two providing additional empirical validation for the decision criteria."
    )
    passages = segment_into_passages(sample_doc, source_id="src-123", page_number=2)

    assert len(passages) == 2
    p1 = passages[0]
    p2 = passages[1]

    assert p1["page_number"] == 2
    assert p1["paragraph_index"] == 0
    assert p1["start_offset"] == 0
    assert p1["end_offset"] > 0
    assert sample_doc[p1["start_offset"]:p1["end_offset"]].strip() == p1["passage_text"]
    assert len(p1["sha256_hash"]) == 64

    assert p2["page_number"] == 2
    assert p2["paragraph_index"] == 1
    assert p2["start_offset"] > p1["end_offset"]
