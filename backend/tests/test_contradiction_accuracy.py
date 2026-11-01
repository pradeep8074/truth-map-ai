import pytest
from backend.services.conflict_service import (
    compute_fallback_conflict,
    extract_keywords,
    extract_numbers,
    extract_metric_context,
    extract_years,
)


def test_unrelated_claims_do_not_produce_false_contradiction():
    """
    Operating margins of 21.5% in 2024 and foreign ownership cap of 49% in 2026
    are distinct metrics and distinct propositions. They must NOT be marked as conflicts.
    """
    claim_a = {
        "id": "clm-margin-2024",
        "claim_text": "Operating margins reached 21.5% in 2024 with high regional counterparty concentration risk.",
    }
    claim_b = {
        "id": "clm-cap-2026",
        "claim_text": "The ASEAN Energy Regulatory Commission announced new foreign ownership caps of 49% for commercial solar.",
    }

    conflict = compute_fallback_conflict(claim_a, claim_b)
    assert conflict is None, f"False positive detected between unrelated metrics: {conflict}"


def test_different_metrics_with_percentages_do_not_conflict():
    """Claims measuring different percentage metrics (e.g. tax rate vs gross margin) must not conflict."""
    claim_a = {"id": "c1", "claim_text": "Corporate income tax rate in Vietnam is 20% for renewable projects."}
    claim_b = {"id": "c2", "claim_text": "Gross profit margins reached 35% across operating solar assets."}

    conflict = compute_fallback_conflict(claim_a, claim_b)
    assert conflict is None


def test_genuine_polarity_contradiction_is_detected():
    """Mutually exclusive directional claims on the same subject must be detected as DIRECT_CONTRADICTION."""
    claim_a = {
        "id": "c1",
        "claim_text": "Quarterly solar tariff revenue increased substantially by 18% across installations.",
    }
    claim_b = {
        "id": "c2",
        "claim_text": "Quarterly solar tariff revenue decreased by 18% due to severe grid curtailment.",
    }

    conflict = compute_fallback_conflict(claim_a, claim_b)
    assert conflict is not None
    assert conflict["conflict_type"] == "DIRECT_CONTRADICTION"
    assert conflict["severity"] == "HIGH"
    assert "Direct polarity clash" in conflict["explanation"]


def test_genuine_numerical_conflict_is_detected():
    """Incompatible figures for the exact same metric on the same entity must be detected as NUMERICAL_CONFLICT."""
    claim_a = {
        "id": "c1",
        "claim_text": "Audited operating margins reached 21.5% across Vietnamese microgrid installations.",
    }
    claim_b = {
        "id": "c2",
        "claim_text": "Audited operating margins reached 11.2% across Vietnamese microgrid installations.",
    }

    conflict = compute_fallback_conflict(claim_a, claim_b)
    assert conflict is not None
    assert conflict["conflict_type"] == "NUMERICAL_CONFLICT"
    assert conflict["severity"] in ("CRITICAL", "HIGH")
    assert "21.5" in conflict["explanation"]
    assert "11.2" in conflict["explanation"]


def test_temporal_metric_evolution_is_distinguished():
    """Divergent figures across explicitly distinct calendar years are classified as TEMPORAL_CONFLICT."""
    claim_a = {
        "id": "c1",
        "claim_text": "Average tariff subsidy rate was audited at 8.5% in 2022.",
    }
    claim_b = {
        "id": "c2",
        "claim_text": "Average tariff subsidy rate was reduced to 3.2% in 2026.",
    }

    conflict = compute_fallback_conflict(claim_a, claim_b)
    assert conflict is not None
    assert conflict["conflict_type"] == "TEMPORAL_CONFLICT"
    assert "Temporal metric evolution" in conflict["explanation"]
