import asyncio
from unittest.mock import MagicMock, patch
import pytest
from backend.services.contract_compiler import (
    normalize_question,
    extract_decision_objective,
    detect_ambiguities,
    compile_contract_deterministic,
    compile_decision_contract,
)


def test_question_normalization():
    raw = "   Does this government scholarship programme improve access to higher education for rural students?   "
    normalized = normalize_question(raw)
    assert normalized == "Does this government scholarship programme improve access to higher education for rural students?"
    assert not normalized.startswith(" ")
    assert not normalized.endswith("  ")

    raw_no_q = "Evaluate whether digital payments improve inclusion"
    assert normalize_question(raw_no_q) == "Evaluate whether digital payments improve inclusion?"


def test_decision_objective_extraction():
    q1 = "Does this government scholarship programme improve access to higher education for rural students?"
    obj1 = extract_decision_objective(q1)
    assert "Evaluate whether this government scholarship programme improves access to higher education for rural students" in obj1
    assert "decision criteria" in obj1

    q2 = "Should we acquire the cloud security startup?"
    obj2 = extract_decision_objective(q2)
    assert "Determine whether we acquire the cloud security startup is justified" in obj2


def test_requirement_decomposition_and_evidence_mapping():
    q = "Does this government scholarship programme improve access to higher education for rural students?"
    contract = compile_contract_deterministic("inv-test-01", q)

    assert contract["investigation_id"] == "inv-test-01"
    assert contract["compilation_method"] == "deterministic_contract_compiler"
    assert contract["processing_mode"] == "fallback"
    assert len(contract["requirements"]) >= 6

    req_types = [r["requirement_type"] for r in contract["requirements"]]
    assert "ELIGIBILITY" in req_types
    assert "QUANTITATIVE" in req_types
    assert "IMPLEMENTATION" in req_types
    assert "COMPARATIVE" in req_types
    assert "CAUSAL" in req_types
    assert "RISK" in req_types

    # Ensure every requirement has linked evidence requirements
    for r in contract["requirements"]:
        assert len(r["evidence_needed"]) >= 1
        ev = r["evidence_needed"][0]
        assert ev["requirement_id"] == r["requirement_id"]
        assert len(ev["preferred_source_types"]) > 0
        assert ev["rationale"] != ""


def test_ambiguity_detection_generates_actionable_clarifications():
    # Question missing explicit year, jurisdiction, and metric definitions
    q = "Does this scholarship programme improve access for students?"
    ambiguities = detect_ambiguities(q)

    assert len(ambiguities) >= 4
    dimensions = [a["dimension"] for a in ambiguities]
    assert "geographic" in dimensions
    assert "temporal" in dimensions
    assert "metric" in dimensions
    assert "baseline" in dimensions

    types = [a["clarification_type"] for a in ambiguities]
    assert "required" in types
    assert "assumption_review" in types


def test_constraints_and_assumptions_present():
    q = "Does this government scholarship programme improve access to higher education for rural students?"
    contract = compile_contract_deterministic("inv-test-01", q)

    assert len(contract["constraints"]) >= 3
    assert len(contract["assumptions"]) >= 2

    # Check causal discipline constraint
    const_descs = [c["description"] for c in contract["constraints"]]
    assert any("Distinguish correlation from causation" in cd for cd in const_descs)

    # Check assumption source differentiation
    for a in contract["assumptions"]:
        assert a["source"] == "ai_inferred"


def test_gemini_contract_compilation_mocked_success():
    """Verifies that when Gemini is available and succeeds, it produces structured contract with processing_mode='gemini'."""
    mock_response = MagicMock()
    mock_response.text = '''{
        "decision_objective": "Determine whether the scholarship programme measurably improves tertiary access for rural cohorts.",
        "scope": "Rural tertiary institutions within the 2022-2025 observation window",
        "requirements": [
            {
                "title": "Establish Beneficiary Criteria",
                "description": "Verify official domicile and income eligibility standards.",
                "requirement_type": "ELIGIBILITY",
                "priority": "CRITICAL",
                "verification_criteria": "Official Gazette Notification and Scheme Guidelines",
                "evidence_type": "Government Policy Gazette",
                "evidence_rationale": "Establishes baseline qualifying cohort",
                "preferred_sources": ["official_documentation"]
            },
            {
                "title": "Quantify Enrollment Delta",
                "description": "Measure net change in rural enrollment post-disbursement.",
                "requirement_type": "QUANTITATIVE",
                "priority": "HIGH",
                "verification_criteria": "Institutional Higher Education Survey (AISHE)",
                "evidence_type": "Institutional Census Data",
                "evidence_rationale": "Demonstrates volume shift",
                "preferred_sources": ["institutional_data"]
            },
            {
                "title": "Verify Baseline Control Group",
                "description": "Isolate concurrent macroeconomic trends via comparison cohort.",
                "requirement_type": "COMPARATIVE",
                "priority": "HIGH",
                "verification_criteria": "Difference-in-differences empirical analysis",
                "evidence_type": "Econometric Evaluation",
                "evidence_rationale": "Prevents spurious attribution",
                "preferred_sources": ["peer_reviewed_studies"]
            },
            {
                "title": "Evaluate Causal Impact",
                "description": "Establish direct link between subsidy receipt and degree retention.",
                "requirement_type": "CAUSAL",
                "priority": "CRITICAL",
                "verification_criteria": "Regression discontinuity or longitudinal panel data",
                "evidence_type": "Longitudinal Survey",
                "evidence_rationale": "Proves causal efficacy",
                "preferred_sources": ["peer_reviewed_studies"]
            }
        ],
        "constraints": [
            {
                "description": "Do not extrapolate rural outcomes to urban or semi-urban beneficiaries.",
                "constraint_type": "scope_boundary"
            }
        ],
        "assumptions": [
            {
                "description": "Fund disbursements were deposited without systemic banking friction.",
                "confidence": 0.82,
                "source": "ai_inferred"
            }
        ],
        "unresolved_questions": [
            {
                "question": "Which specific states or districts define the rural cohort?",
                "clarification_type": "required",
                "dimension": "geographic"
            }
        ]
    }'''

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response

    with patch("backend.services.contract_compiler.GEMINI_API_KEY", "test-gemini-key"):
        with patch("google.genai.Client", return_value=mock_client):
            q = "Does this government scholarship programme improve access to higher education for rural students?"
            contract = asyncio.run(compile_decision_contract("inv-gemini-01", q))

            assert contract["investigation_id"] == "inv-gemini-01"
            assert contract["compilation_method"] == "gemini_contract_compiler"
            assert contract["processing_mode"] == "gemini"
            assert contract["original_question"] == q
            assert len(contract["requirements"]) == 4
            assert contract["requirements"][0]["requirement_type"] == "ELIGIBILITY"
            assert contract["requirements"][1]["requirement_type"] == "QUANTITATIVE"
            assert contract["requirements"][2]["requirement_type"] == "COMPARATIVE"
            assert contract["requirements"][3]["requirement_type"] == "CAUSAL"

            assert len(contract["constraints"]) == 1
            assert len(contract["assumptions"]) == 1
            assert contract["assumptions"][0]["source"] == "ai_inferred"
            assert len(contract["unresolved_questions"]) == 1
            assert contract["unresolved_questions"][0]["dimension"] == "geographic"


def test_gemini_contract_compilation_mocked_error_falls_back():
    """Verifies that if Gemini encounters an error, the compiler safely falls back to deterministic engine."""
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = TimeoutError("Gemini API call timed out after 10s")

    with patch("backend.services.contract_compiler.GEMINI_API_KEY", "test-gemini-key"):
        with patch("google.genai.Client", return_value=mock_client):
            q = "Does this scholarship programme improve access to higher education for rural students?"
            contract = asyncio.run(compile_decision_contract("inv-fallback-01", q))

            assert contract["investigation_id"] == "inv-fallback-01"
            assert contract["compilation_method"] == "deterministic_contract_compiler"
            assert contract["processing_mode"] == "fallback"
            assert len(contract["requirements"]) >= 6
