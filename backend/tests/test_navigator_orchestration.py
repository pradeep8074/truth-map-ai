import pytest
import sqlite3
import uuid
import datetime
import json
from fastapi.testclient import TestClient

from backend.main import app
from backend.database import init_db, get_db
from backend.models import (
    GapReassessmentCommitRequest,
    CandidateReviewRequest,
    ManualCandidateRequest,
)
from backend.services.verification_planner import (
    get_gap_verification_queue,
    generate_verification_plan,
    update_verification_plan_queries,
    add_manual_candidate_source,
    review_candidate_source,
)
from backend.services.search_adapter import (
    execute_search_discovery,
)
from backend.services.verification_evaluator import (
    evaluate_gap_reassessment,
    commit_gap_reassessment,
)
from backend.services.orchestrator_service import (
    orchestrate_source_integration,
    get_source_impact_summary,
)

client = TestClient(app)


@pytest.fixture
def temp_db(tmp_path):
    """Provides a fresh isolated SQLite database file for testing Component 10."""
    db_file = str(tmp_path / "test_truthmap_navigator.db")
    init_db(db_file)
    return db_file


def _seed_test_investigation_with_gaps(db_path: str):
    """Helper to seed an investigation with contract, requirements, sufficiency, and gaps."""
    with get_db(db_path) as conn:
        cursor = conn.cursor()
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        inv_id = str(uuid.uuid4())
        contract_id = str(uuid.uuid4())

        # Investigation
        cursor.execute("INSERT INTO investigations (id, research_question, status, created_at) VALUES (?, 'Capital Expansion Feasibility', 'active', ?);", (inv_id, now))

        # Contract
        cursor.execute("""
            INSERT INTO decision_contracts (id, investigation_id, original_question, normalized_question, decision_objective, compilation_method, created_at, updated_at)
            VALUES (?, ?, 'Q', 'Normalized Q', 'Evaluate Tier-1 Solvency and Expansion Feasibility', 'deterministic', ?, ?);
        """, (contract_id, inv_id, now, now))

        # Requirements
        req_crit = str(uuid.uuid4())
        req_high = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO contract_requirements (id, contract_id, title, description, requirement_type, priority, verification_criteria, sort_order)
            VALUES (?, ?, 'Tier-1 Capital Adequacy', 'Verify capital adequacy >= 12%', 'STATISTICAL', 'CRITICAL', 'Tier-1 capital adequacy ratio must exceed 12%', 0);
        """, (req_crit, contract_id))
        cursor.execute("""
            INSERT INTO contract_requirements (id, contract_id, title, description, requirement_type, priority, verification_criteria, sort_order)
            VALUES (?, ?, 'Environmental Audit Compliance', 'Verify ISO 14001 certification', 'FACTUAL', 'HIGH', 'Valid ISO 14001 environmental certification audit', 1);
        """, (req_high, contract_id))

        # Assumption
        assump_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO contract_assumptions (id, contract_id, description, confidence, validation_status, source)
            VALUES (?, ?, 'Solvency ratio remains above regulatory threshold of 12%', 0.85, 'unvalidated', 'contract_explicit');
        """, (assump_id, contract_id))

        # Sufficiency Assessments
        assess_crit = str(uuid.uuid4())
        assess_high = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO evidence_sufficiency_assessments (
                id, investigation_id, requirement_id, coverage_status, assessment_summary,
                recommended_action, confidence, analysis_method, processing_mode, created_at, updated_at
            ) VALUES (?, ?, ?, 'NO_EVIDENCE', 'Missing statutory solvency metric', 'Obtain audited filing', 0.9, 'deterministic', 'fallback', ?, ?);
        """, (assess_crit, inv_id, req_crit, now, now))
        cursor.execute("""
            INSERT INTO evidence_sufficiency_assessments (
                id, investigation_id, requirement_id, coverage_status, assessment_summary,
                recommended_action, confidence, analysis_method, processing_mode, created_at, updated_at
            ) VALUES (?, ?, ?, 'INSUFFICIENT', 'Audit pending', 'Obtain ISO report', 0.8, 'deterministic', 'fallback', ?, ?);
        """, (assess_high, inv_id, req_high, now, now))

        # Gaps
        gap_crit = str(uuid.uuid4())
        gap_high = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO evidence_gaps (
                id, investigation_id, requirement_id, assessment_id, gap_description,
                why_it_matters, evidence_needed, suggested_source_type, priority, created_at
            ) VALUES (?, ?, ?, ?, 'Missing Tier-1 Capital ratio for Subsidiary', 'Statutory requirement', 'Tier-1 capital adequacy ratio audited metric', 'Regulatory Filing', 'CRITICAL', ?);
        """, (gap_crit, inv_id, req_crit, assess_crit, now))
        cursor.execute("""
            INSERT INTO evidence_gaps (
                id, investigation_id, requirement_id, assessment_id, gap_description,
                why_it_matters, evidence_needed, suggested_source_type, priority, created_at
            ) VALUES (?, ?, ?, ?, 'Unverified environmental audit certification', 'Permit compliance', 'ISO 14001 certification report', 'Audit Certificate', 'HIGH', ?);
        """, (gap_high, inv_id, req_high, assess_high, now))

        # Existing published report (to test is_stale stamping)
        report_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO decision_intelligence_reports (
                id, investigation_id, report_version, report_status, processing_mode,
                overall_robustness, executive_summary, report_data_json, is_stale, created_at, updated_at
            ) VALUES (?, ?, 1, 'published', 'fallback', 'VULNERABLE', 'Initial report', '{}', 0, ?, ?);
        """, (report_id, inv_id, now, now))

        conn.commit()

        return {
            "inv_id": inv_id,
            "contract_id": contract_id,
            "req_crit": req_crit,
            "req_high": req_high,
            "gap_crit": gap_crit,
            "gap_high": gap_high,
            "assump_id": assump_id,
            "report_id": report_id,
        }


def test_gap_queue_prioritization(temp_db):
    """Verifies that gaps in get_gap_verification_queue are prioritized by CRITICAL > HIGH."""
    data = _seed_test_investigation_with_gaps(temp_db)
    with get_db(temp_db) as conn:
        queue = get_gap_verification_queue(conn, data["inv_id"])
        assert len(queue) == 2
        assert queue[0].priority == "CRITICAL"
        assert queue[0].gap_id == data["gap_crit"]
        assert queue[0].projected_dfi_reduction >= queue[1].projected_dfi_reduction
        assert queue[1].priority == "HIGH"
        assert queue[1].gap_id == data["gap_high"]


def test_verification_plan_formulation(temp_db):
    """Verifies generation of context-driven queries without hardcoded templates, and UNAVAILABLE search status."""
    data = _seed_test_investigation_with_gaps(temp_db)
    with get_db(temp_db) as conn:
        plan = generate_verification_plan(conn, data["inv_id"], data["gap_crit"])
        assert plan.target_authority_tier == "TIER_1"
        assert len(plan.search_queries) >= 2
        # Grounded in live investigation requirement title and evidence needed
        assert any("Tier-1 Capital Adequacy" in q for q in plan.search_queries)
        assert any("capital adequacy ratio" in q.lower() for q in plan.search_queries)
        # Verify complete absence of predefined query templates and operators
        assert not any("filetype:pdf" in q for q in plan.search_queries)
        assert not any("site:sec.gov" in q for q in plan.search_queries)
        assert not any("site:gov" in q for q in plan.search_queries)
        assert not any("annual report 10-K" in q for q in plan.search_queries)
        assert not any("audit certified" in q for q in plan.search_queries)
        assert plan.search_provider_status == "UNAVAILABLE"
        assert plan.status == "PLANNED"


def test_manual_candidate_url_triage_gate_1(temp_db):
    """Tests manual candidate submission and analyst review gate 1."""
    data = _seed_test_investigation_with_gaps(temp_db)
    with get_db(temp_db) as conn:
        plan = generate_verification_plan(conn, data["inv_id"], data["gap_crit"])
        cand = add_manual_candidate_source(
            conn, plan.id, data["inv_id"],
            url="https://sec.gov/filings/apex_10k.pdf",
            title="SEC 10-K Apex Global",
            snippet="Apex Global Tier-1 capital adequacy ratio stands at 13.4%."
        )
        assert cand.review_status == "PENDING_REVIEW"
        assert cand.authority_tier == "TIER_1"
        assert cand.relevance_score > 50.0

        # Approve candidate (Gate 1)
        reviewed = review_candidate_source(conn, cand.id, action="APPROVE")
        assert reviewed.review_status == "APPROVED"


def test_ssrf_quarantine_in_manual_candidate(temp_db):
    """Candidate URLs with private IP destinations must be rejected."""
    data = _seed_test_investigation_with_gaps(temp_db)
    with get_db(temp_db) as conn:
        plan = generate_verification_plan(conn, data["inv_id"], data["gap_crit"])
        with pytest.raises(ValueError, match="Security validation rejected candidate URL"):
            add_manual_candidate_source(conn, plan.id, data["inv_id"], url="http://127.0.0.1:8000/internal")


def test_deterministic_reassessment_proposal_only(temp_db):
    """
    Mandatory Safeguard 1:
    evaluate_gap_reassessment computes a proposed resolution state, but NEVER
    automatically marks the gap or sufficiency assessment as RESOLVED.
    """
    data = _seed_test_investigation_with_gaps(temp_db)
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with get_db(temp_db) as conn:
        # Ingest a mock source with supporting claim for req_crit
        src_id = str(uuid.uuid4())
        pass_id = str(uuid.uuid4())
        claim_id = str(uuid.uuid4())
        conn.execute("INSERT INTO sources (id, investigation_id, source_type, original_url, title, retrieved_at, extraction_status) VALUES (?, ?, 'web', 'https://sec.gov/10k', 'SEC Filing', ?, 'completed');", (src_id, data["inv_id"], now))
        conn.execute("INSERT INTO passages (id, source_id, passage_text, sha256_hash) VALUES (?, ?, 'Consolidated Tier-1 capital adequacy ratio stood at 13.4% in audited filing.', 'hash123');", (pass_id, src_id))
        conn.execute("INSERT INTO claims (id, investigation_id, source_id, passage_id, claim_text, category, extraction_method, extraction_confidence, created_at) VALUES (?, ?, ?, ?, 'Tier-1 capital adequacy ratio is 13.4%', 'statistical', 'deterministic', 0.95, ?);", (claim_id, data["inv_id"], src_id, pass_id, now))
        conn.execute("INSERT INTO evidence_relationships (id, investigation_id, requirement_id, claim_id, passage_id, relevance, explanation, confidence, analysis_method, processing_mode, created_at) VALUES (?, ?, ?, ?, NULL, 'DIRECTLY_RELEVANT', 'Test evidence linkage', 0.95, 'deterministic', 'fallback', ?);", (str(uuid.uuid4()), data["inv_id"], data["req_crit"], claim_id, now))
        conn.commit()

        # Compute reassessment
        reassess = evaluate_gap_reassessment(conn, data["inv_id"], data["gap_crit"])
        assert reassess.proposed_resolution_state == "RESOLVED"
        assert reassess.analyst_decision == "PENDING_DECISION"
        assert reassess.analyst_final_state is None

        # Verify that evidence_sufficiency_assessments is STILL NO_EVIDENCE in the DB
        cursor = conn.cursor()
        cursor.execute("SELECT coverage_status FROM evidence_sufficiency_assessments WHERE requirement_id = ?;", (data["req_crit"],))
        assert cursor.fetchone()["coverage_status"] == "NO_EVIDENCE"

        # Verify gap still exists in evidence_gaps
        cursor.execute("SELECT id FROM evidence_gaps WHERE id = ?;", (data["gap_crit"],))
        assert cursor.fetchone() is not None


def test_analyst_commit_gate_2_resolves_gap(temp_db):
    """Analyst explicitly approves resolution, which transitions the gap and sufficiency assessment."""
    data = _seed_test_investigation_with_gaps(temp_db)
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with get_db(temp_db) as conn:
        # Ingest claim and evaluate
        src_id = str(uuid.uuid4())
        pass_id = str(uuid.uuid4())
        claim_id = str(uuid.uuid4())
        conn.execute("INSERT INTO sources (id, investigation_id, source_type, original_url, title, retrieved_at, extraction_status) VALUES (?, ?, 'web', 'https://sec.gov/10k', 'SEC Filing', ?, 'completed');", (src_id, data["inv_id"], now))
        conn.execute("INSERT INTO passages (id, source_id, passage_text, sha256_hash) VALUES (?, ?, 'Passage', 'hash');", (pass_id, src_id))
        conn.execute("INSERT INTO claims (id, investigation_id, source_id, passage_id, claim_text, category, extraction_method, extraction_confidence, created_at) VALUES (?, ?, ?, ?, 'Tier-1 capital adequacy ratio is 13.4%', 'statistical', 'deterministic', 0.95, ?);", (claim_id, data["inv_id"], src_id, pass_id, now))
        conn.execute("INSERT INTO evidence_relationships (id, investigation_id, requirement_id, claim_id, passage_id, relevance, explanation, confidence, analysis_method, processing_mode, created_at) VALUES (?, ?, ?, ?, NULL, 'DIRECTLY_RELEVANT', 'Test evidence linkage', 0.95, 'deterministic', 'fallback', ?);", (str(uuid.uuid4()), data["inv_id"], data["req_crit"], claim_id, now))
        conn.commit()

        reassess = evaluate_gap_reassessment(conn, data["inv_id"], data["gap_crit"])

        # Commit approval (HITL Gate 2)
        req = GapReassessmentCommitRequest(
            analyst_decision="APPROVED",
            analyst_final_state="RESOLVED",
            analyst_notes="Audited 10-K confirms 13.4% capital adequacy ratio.",
            analyst_id="Senior Auditor"
        )
        committed = commit_gap_reassessment(conn, reassess.id, req)
        assert committed.analyst_decision == "APPROVED"
        assert committed.analyst_final_state == "RESOLVED"
        assert committed.is_analyst_override is False

        # Verify sufficiency assessment is now SUFFICIENT
        cursor = conn.cursor()
        cursor.execute("SELECT coverage_status FROM evidence_sufficiency_assessments WHERE requirement_id = ?;", (data["req_crit"],))
        assert cursor.fetchone()["coverage_status"] == "SUFFICIENT"


def test_analyst_override_preservation(temp_db):
    """Analyst overrides proposed RESOLVED to PARTIALLY_ADDRESSED; override is flagged and notes preserved."""
    data = _seed_test_investigation_with_gaps(temp_db)
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with get_db(temp_db) as conn:
        src_id = str(uuid.uuid4())
        pass_id = str(uuid.uuid4())
        claim_id = str(uuid.uuid4())
        conn.execute("INSERT INTO sources (id, investigation_id, source_type, original_url, title, retrieved_at, extraction_status) VALUES (?, ?, 'web', 'https://sec.gov/10k', 'SEC Filing', ?, 'completed');", (src_id, data["inv_id"], now))
        conn.execute("INSERT INTO passages (id, source_id, passage_text, sha256_hash) VALUES (?, ?, 'Passage', 'hash');", (pass_id, src_id))
        conn.execute("INSERT INTO claims (id, investigation_id, source_id, passage_id, claim_text, category, extraction_method, extraction_confidence, created_at) VALUES (?, ?, ?, ?, 'Tier-1 capital adequacy ratio is 13.4%', 'statistical', 'deterministic', 0.95, ?);", (claim_id, data["inv_id"], src_id, pass_id, now))
        conn.execute("INSERT INTO evidence_relationships (id, investigation_id, requirement_id, claim_id, passage_id, relevance, explanation, confidence, analysis_method, processing_mode, created_at) VALUES (?, ?, ?, ?, NULL, 'DIRECTLY_RELEVANT', 'Test evidence linkage', 0.95, 'deterministic', 'fallback', ?);", (str(uuid.uuid4()), data["inv_id"], data["req_crit"], claim_id, now))
        conn.commit()

        reassess = evaluate_gap_reassessment(conn, data["inv_id"], data["gap_crit"])

        req = GapReassessmentCommitRequest(
            analyst_decision="OVERRIDDEN",
            analyst_final_state="PARTIALLY_ADDRESSED",
            analyst_notes="Only Subsidiary A covered; Subsidiary B still unverified.",
            analyst_id="Senior Auditor"
        )
        committed = commit_gap_reassessment(conn, reassess.id, req)
        assert committed.is_analyst_override is True
        assert committed.analyst_final_state == "PARTIALLY_ADDRESSED"
        assert "Subsidiary B" in committed.analyst_notes


def test_contradiction_forces_worsened(temp_db):
    """A conflicting claim forces proposed reassessment to WORSENED."""
    data = _seed_test_investigation_with_gaps(temp_db)
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with get_db(temp_db) as conn:
        src_id = str(uuid.uuid4())
        pass_id = str(uuid.uuid4())
        claim_a = str(uuid.uuid4())
        claim_b = str(uuid.uuid4())
        conn.execute("INSERT INTO sources (id, investigation_id, source_type, original_url, title, retrieved_at, extraction_status) VALUES (?, ?, 'web', 'https://sec.gov/10k', 'SEC Filing', ?, 'completed');", (src_id, data["inv_id"], now))
        conn.execute("INSERT INTO passages (id, source_id, passage_text, sha256_hash) VALUES (?, ?, 'Passage', 'hash');", (pass_id, src_id))
        conn.execute("INSERT INTO claims (id, investigation_id, source_id, passage_id, claim_text, category, extraction_method, extraction_confidence, created_at) VALUES (?, ?, ?, ?, 'Capital adequacy ratio is 13.4%', 'statistical', 'deterministic', 0.95, ?);", (claim_a, data["inv_id"], src_id, pass_id, now))
        conn.execute("INSERT INTO claims (id, investigation_id, source_id, passage_id, claim_text, category, extraction_method, extraction_confidence, created_at) VALUES (?, ?, ?, ?, 'Capital adequacy ratio failed at 9.1%', 'statistical', 'deterministic', 0.95, ?);", (claim_b, data["inv_id"], src_id, pass_id, now))
        conn.execute("INSERT INTO evidence_relationships (id, investigation_id, requirement_id, claim_id, passage_id, relevance, explanation, confidence, analysis_method, processing_mode, created_at) VALUES (?, ?, ?, ?, NULL, 'DIRECTLY_RELEVANT', 'Test evidence linkage', 0.95, 'deterministic', 'fallback', ?);", (str(uuid.uuid4()), data["inv_id"], data["req_crit"], claim_a, now))

        # Insert active critical conflict
        conn.execute("""
            INSERT INTO evidence_conflicts (
                id, investigation_id, claim_a_id, claim_b_id, conflict_type, severity,
                explanation, contextual_differences, confidence, resolution_status,
                reviewer_notes, recommended_action, analysis_method, processing_mode, created_at, updated_at
            ) VALUES (
                ?, ?, ?, ?, 'NUMERICAL_CONFLICT', 'CRITICAL',
                'Direct numerical clash on solvency ratio', '', 0.95, 'unresolved',
                '', 'Request audit reconciliation', 'deterministic', 'fallback', ?, ?
            );
        """, (str(uuid.uuid4()), data["inv_id"], claim_a, claim_b, now, now))
        conn.commit()

        reassess = evaluate_gap_reassessment(conn, data["inv_id"], data["gap_crit"])
        assert reassess.proposed_resolution_state == "WORSENED"


def test_source_orchestration_workflow_b(temp_db):
    """
    Workflow B: Integrating a source runs the central orchestrator across Components 02-09,
    marks reports stale, updates DFI, and produces the unified SourceImpactSummary.
    """
    data = _seed_test_investigation_with_gaps(temp_db)
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with get_db(temp_db) as conn:
        src_id = str(uuid.uuid4())
        pass_id = str(uuid.uuid4())
        claim_id = str(uuid.uuid4())
        conn.execute("INSERT INTO sources (id, investigation_id, source_type, original_url, title, content_hash, retrieved_at, extraction_status) VALUES (?, ?, 'web', 'https://sec.gov/apex_10k.pdf', 'SEC Form 10-K', 'hash_unique_1', ?, 'completed');", (src_id, data["inv_id"], now))
        conn.execute("INSERT INTO passages (id, source_id, passage_text, sha256_hash) VALUES (?, ?, 'Apex Tier-1 capital adequacy ratio reached 13.4%.', 'p_hash');", (pass_id, src_id))
        conn.execute("INSERT INTO claims (id, investigation_id, source_id, passage_id, claim_text, category, extraction_method, extraction_confidence, created_at) VALUES (?, ?, ?, ?, 'Tier-1 capital adequacy ratio reached 13.4%', 'statistical', 'deterministic', 0.95, ?);", (claim_id, data["inv_id"], src_id, pass_id, now))
        conn.commit()

        impact = orchestrate_source_integration(conn, data["inv_id"], src_id)
        assert impact.source_id == src_id
        assert impact.total_claims_extracted == 1
        assert len(impact.affected_requirements) >= 1
        assert impact.report_invalidated is True
        assert "STAGE_0_INGESTION" in impact.stages_execution
        assert impact.stages_execution["STAGE_0_INGESTION"].status == "COMPLETED"
        assert impact.stages_execution["STAGE_7_REPORT_INVALIDATION"].status == "COMPLETED"

        # Verify Component 08 report was flagged is_stale = 1
        cursor = conn.cursor()
        cursor.execute("SELECT is_stale FROM decision_intelligence_reports WHERE id = ?;", (data["report_id"],))
        assert cursor.fetchone()["is_stale"] == 1


def test_assumption_semantics_preserved(temp_db):
    """
    Mandatory Safeguard: Evidence supporting an assumption records relationship: 'SUPPORTS',
    but leaves contract_assumptions.validation_status strictly UNTOUCHED ('unvalidated').
    """
    data = _seed_test_investigation_with_gaps(temp_db)
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with get_db(temp_db) as conn:
        src_id = str(uuid.uuid4())
        pass_id = str(uuid.uuid4())
        claim_id = str(uuid.uuid4())
        conn.execute("INSERT INTO sources (id, investigation_id, source_type, original_url, title, content_hash, retrieved_at, extraction_status) VALUES (?, ?, 'web', 'https://sec.gov/10k', 'SEC Filing', 'hash_assump_1', ?, 'completed');", (src_id, data["inv_id"], now))
        conn.execute("INSERT INTO passages (id, source_id, passage_text, sha256_hash) VALUES (?, ?, 'Solvency ratio remains above regulatory threshold of 12%.', 'hash');", (pass_id, src_id))
        conn.execute("INSERT INTO claims (id, investigation_id, source_id, passage_id, claim_text, category, extraction_method, extraction_confidence, created_at) VALUES (?, ?, ?, ?, 'Solvency ratio remains above regulatory threshold of 12%', 'statistical', 'deterministic', 0.9, ?);", (claim_id, data["inv_id"], src_id, pass_id, now))
        conn.commit()

        impact = orchestrate_source_integration(conn, data["inv_id"], src_id)
        assert len(impact.affected_assumptions) >= 1
        assert impact.affected_assumptions[0]["relationship"] == "SUPPORTS"

        # Verify DB validation_status is STILL 'unvalidated'
        cursor = conn.cursor()
        cursor.execute("SELECT validation_status FROM contract_assumptions WHERE id = ?;", (data["assump_id"],))
        assert cursor.fetchone()["validation_status"] == "unvalidated"


def test_idempotency_duplicate_source_skipped(temp_db):
    """Ingesting an identical content hash triggers DUPLICATE_SOURCE_SKIPPED with 0 duplicate claims."""
    data = _seed_test_investigation_with_gaps(temp_db)
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with get_db(temp_db) as conn:
        # First source
        src_id_1 = str(uuid.uuid4())
        conn.execute("INSERT INTO sources (id, investigation_id, source_type, original_url, title, content_hash, retrieved_at, extraction_status) VALUES (?, ?, 'web', 'https://example.com/doc', 'Doc 1', 'same_hash_123', ?, 'completed');", (src_id_1, data["inv_id"], now))
        conn.commit()

        # Second source with exact same content hash
        src_id_2 = str(uuid.uuid4())
        conn.execute("INSERT INTO sources (id, investigation_id, source_type, original_url, title, content_hash, retrieved_at, extraction_status) VALUES (?, ?, 'web', 'https://example.com/doc', 'Doc 1 Duplicate', 'same_hash_123', ?, 'completed');", (src_id_2, data["inv_id"], now))
        conn.commit()

        impact_dup = orchestrate_source_integration(conn, data["inv_id"], src_id_2)
        assert impact_dup.is_duplicate is True
        assert "Identical content hash" in impact_dup.stages_execution["STAGE_0_INGESTION"].skipped_reason


def test_audit_trail_immutability(temp_db):
    """Audit log records verification and orchestration events."""
    data = _seed_test_investigation_with_gaps(temp_db)
    with get_db(temp_db) as conn:
        plan = generate_verification_plan(conn, data["inv_id"], data["gap_crit"])
        cand = add_manual_candidate_source(conn, plan.id, data["inv_id"], url="https://sec.gov/apex_10k.pdf")
        review_candidate_source(conn, cand.id, action="APPROVE")

        cursor = conn.cursor()
        cursor.execute("SELECT event_type FROM orchestration_audit_log WHERE investigation_id = ? ORDER BY created_at ASC;", (data["inv_id"],))
        events = [r["event_type"] for r in cursor.fetchall()]
        assert "PLAN_GENERATED" in events
        assert "SOURCE_APPROVED" in events


def test_navigator_api_endpoints_workflow(temp_db, monkeypatch):
    """Verifies complete REST API workflow for Component 10."""
    monkeypatch.setattr("backend.database.DB_PATH", temp_db)
    data = _seed_test_investigation_with_gaps(temp_db)

    # 1. Queue endpoint
    resp_q = client.get(f"/api/investigations/{data['inv_id']}/navigator/gaps/queue")
    assert resp_q.status_code == 200
    q_data = resp_q.json()
    assert q_data["total_gaps"] == 2
    assert q_data["search_provider_active"] is False

    # 2. Plan generation endpoint (with context)
    resp_plan = client.post(f"/api/investigations/{data['inv_id']}/navigator/gaps/{data['gap_crit']}/plan")
    assert resp_plan.status_code == 200
    plan_data = resp_plan.json()
    plan_id = plan_data["id"]
    assert len(plan_data["search_queries"]) >= 2
    assert not any("filetype:pdf" in q for q in plan_data["search_queries"])

    # 2b. Manual query editing endpoint
    resp_update_q = client.put(
        f"/api/investigations/{data['inv_id']}/navigator/plans/{plan_id}/queries",
        json={"queries": ["Custom analyst verification query 1", "Audited balance sheet disclosure note 12"]}
    )
    assert resp_update_q.status_code == 200
    assert resp_update_q.json()["search_queries"] == [
        "Custom analyst verification query 1",
        "Audited balance sheet disclosure note 12"
    ]

    # 2c. Plan details endpoint
    resp_get_plan = client.get(f"/api/investigations/{data['inv_id']}/navigator/plans/{plan_id}")
    assert resp_get_plan.status_code == 200
    assert resp_get_plan.json()["search_queries"] == [
        "Custom analyst verification query 1",
        "Audited balance sheet disclosure note 12"
    ]

    # 3. Manual candidate submission
    resp_cand = client.post(
        f"/api/investigations/{data['inv_id']}/navigator/plans/{plan_id}/candidates/manual",
        json={"url": "https://sec.gov/10k_filing.pdf", "title": "SEC 10-K", "snippet": "Capital ratio 13.4%"}
    )
    assert resp_cand.status_code == 200
    cand_data = resp_cand.json()
    cand_id = cand_data["id"]

    # 4. Review candidate (Gate 1)
    resp_rev = client.post(
        f"/api/investigations/{data['inv_id']}/navigator/candidates/{cand_id}/review",
        json={"action": "APPROVE"}
    )
    assert resp_rev.status_code == 200
    assert resp_rev.json()["review_status"] == "APPROVED"

    # 5. Evaluate gap (PROPOSAL ONLY)
    resp_eval = client.post(f"/api/investigations/{data['inv_id']}/navigator/gaps/{data['gap_crit']}/evaluate")
    assert resp_eval.status_code == 200
    eval_data = resp_eval.json()
    reassess_id = eval_data["id"]
    assert eval_data["analyst_decision"] == "PENDING_DECISION"

    # 6. Commit reassessment (Gate 2)
    resp_commit = client.post(
        f"/api/investigations/{data['inv_id']}/navigator/reassessments/{reassess_id}/commit",
        json={
            "analyst_decision": "APPROVED",
            "analyst_final_state": "RESOLVED",
            "analyst_notes": "Audited confirmation accepted by analyst.",
            "analyst_id": "Lead Auditor"
        }
    )
    assert resp_commit.status_code == 200
    assert resp_commit.json()["analyst_decision"] == "APPROVED"
    assert resp_commit.json()["analyst_final_state"] == "RESOLVED"

    # 7. Audit trail endpoint
    resp_audit = client.get(f"/api/investigations/{data['inv_id']}/navigator/audit-trail")
    assert resp_audit.status_code == 200
    assert len(resp_audit.json()) >= 3


def test_distinct_contexts_produce_distinct_queries(temp_db):
    """
    Verifies that different investigation contexts dynamically generate
    context-specific queries with zero canned overlap or fixed templates.
    """
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with get_db(temp_db) as conn:
        cursor = conn.cursor()

        # Context A: Financial Solvency Investigation
        inv_a = str(uuid.uuid4())
        contract_a = str(uuid.uuid4())
        req_a = str(uuid.uuid4())
        assess_a = str(uuid.uuid4())
        gap_a = str(uuid.uuid4())
        cursor.execute("INSERT INTO investigations (id, research_question, status, created_at) VALUES (?, 'Evaluate Subsidiary Solvency and Liquidity', 'active', ?);", (inv_a, now))
        cursor.execute("INSERT INTO decision_contracts (id, investigation_id, original_question, normalized_question, decision_objective, compilation_method, created_at, updated_at) VALUES (?, ?, 'Q', 'Q', 'Verify statutory capital solvency ratio', 'deterministic', ?, ?);", (contract_a, inv_a, now, now))
        cursor.execute("INSERT INTO contract_requirements (id, contract_id, title, description, requirement_type, priority, verification_criteria, sort_order) VALUES (?, ?, 'Tier-1 Capital Adequacy', 'Verify capital adequacy >= 12%', 'STATISTICAL', 'CRITICAL', 'Audited statutory capital ratio exceeds 12%', 0);", (req_a, contract_a))
        cursor.execute("INSERT INTO evidence_sufficiency_assessments (id, investigation_id, requirement_id, coverage_status, assessment_summary, recommended_action, confidence, analysis_method, processing_mode, created_at, updated_at) VALUES (?, ?, ?, 'NO_EVIDENCE', 'Missing statutory solvency metric', 'Obtain audited filing', 0.9, 'deterministic', 'fallback', ?, ?);", (assess_a, inv_a, req_a, now, now))
        cursor.execute("INSERT INTO evidence_gaps (id, investigation_id, requirement_id, assessment_id, gap_description, why_it_matters, evidence_needed, suggested_source_type, priority, created_at) VALUES (?, ?, ?, ?, 'Missing audited Tier-1 capital ratio', 'Statutory requirement', 'Audited statutory capital adequacy ratio metric', 'Regulatory Filing', 'CRITICAL', ?);", (gap_a, inv_a, req_a, assess_a, now))

        # Context B: Clinical Trial Investigation
        inv_b = str(uuid.uuid4())
        contract_b = str(uuid.uuid4())
        req_b = str(uuid.uuid4())
        assess_b = str(uuid.uuid4())
        gap_b = str(uuid.uuid4())
        cursor.execute("INSERT INTO investigations (id, research_question, status, created_at) VALUES (?, 'Assess Oncology Drug X Phase 3 Efficacy', 'active', ?);", (inv_b, now))
        cursor.execute("INSERT INTO decision_contracts (id, investigation_id, original_question, normalized_question, decision_objective, compilation_method, created_at, updated_at) VALUES (?, ?, 'Q', 'Q', 'Evaluate overall survival rate and toxicity', 'deterministic', ?, ?);", (contract_b, inv_b, now, now))
        cursor.execute("INSERT INTO contract_requirements (id, contract_id, title, description, requirement_type, priority, verification_criteria, sort_order) VALUES (?, ?, 'Overall Survival Efficacy', 'Median OS improvement >= 4.5 months', 'STATISTICAL', 'CRITICAL', 'Double-blind randomized trial median overall survival data', 0);", (req_b, contract_b))
        cursor.execute("INSERT INTO evidence_sufficiency_assessments (id, investigation_id, requirement_id, coverage_status, assessment_summary, recommended_action, confidence, analysis_method, processing_mode, created_at, updated_at) VALUES (?, ?, ?, 'NO_EVIDENCE', 'Missing survival curve', 'Obtain clinical data', 0.9, 'deterministic', 'fallback', ?, ?);", (assess_b, inv_b, req_b, now, now))
        cursor.execute("INSERT INTO evidence_gaps (id, investigation_id, requirement_id, assessment_id, gap_description, why_it_matters, evidence_needed, suggested_source_type, priority, created_at) VALUES (?, ?, ?, ?, 'Lack of peer-reviewed Kaplan-Meier survival curves', 'Efficacy substantiation', 'Phase 3 randomized trial peer-reviewed overall survival metric', 'Clinical Journal', 'CRITICAL', ?);", (gap_b, inv_b, req_b, assess_b, now))

        conn.commit()

        plan_a = generate_verification_plan(conn, inv_a, gap_a)
        plan_b = generate_verification_plan(conn, inv_b, gap_b)

        # Context A queries must contain financial terms and NO clinical terms
        assert any("Capital" in q or "Solvency" in q for q in plan_a.search_queries)
        assert not any("oncology" in q.lower() or "survival" in q.lower() for q in plan_a.search_queries)

        # Context B queries must contain clinical terms and NO financial terms
        assert any("Survival" in q or "Efficacy" in q for q in plan_b.search_queries)
        assert not any("solvency" in q.lower() or "capital" in q.lower() for q in plan_b.search_queries)

        # Neither context may contain hardcoded query templates
        for p in [plan_a, plan_b]:
            assert not any("filetype:pdf" in q for q in p.search_queries)
            assert not any("site:sec.gov" in q for q in p.search_queries)
            assert not any("site:gov" in q for q in p.search_queries)
            assert not any("annual report 10-K" in q for q in p.search_queries)
            assert not any("audit certified" in q for q in p.search_queries)


def test_missing_context_produces_clear_error_no_fallback(temp_db):
    """
    Verifies that when required investigation context is missing, the system
    raises a clear ValueError explaining the missing input rather than fabricating a fallback query.
    """
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with get_db(temp_db) as conn:
        cursor = conn.cursor()
        inv_id = str(uuid.uuid4())
        contract_id = str(uuid.uuid4())
        req_id = str(uuid.uuid4())
        assess_empty = str(uuid.uuid4())
        gap_id = str(uuid.uuid4())

        cursor.execute("INSERT INTO investigations (id, research_question, status, created_at) VALUES (?, '', 'active', ?);", (inv_id, now))
        cursor.execute("INSERT INTO decision_contracts (id, investigation_id, original_question, normalized_question, decision_objective, compilation_method, created_at, updated_at) VALUES (?, ?, '', '', '', 'deterministic', ?, ?);", (contract_id, inv_id, now, now))
        cursor.execute("INSERT INTO contract_requirements (id, contract_id, title, description, requirement_type, priority, verification_criteria, sort_order) VALUES (?, ?, '', '', 'FACTUAL', 'MEDIUM', '', 0);", (req_id, contract_id))
        cursor.execute("INSERT INTO evidence_sufficiency_assessments (id, investigation_id, requirement_id, coverage_status, assessment_summary, recommended_action, confidence, analysis_method, processing_mode, created_at, updated_at) VALUES (?, ?, ?, 'NO_EVIDENCE', '', '', 0.5, 'deterministic', 'fallback', ?, ?);", (assess_empty, inv_id, req_id, now, now))
        cursor.execute("INSERT INTO evidence_gaps (id, investigation_id, requirement_id, assessment_id, gap_description, why_it_matters, evidence_needed, suggested_source_type, priority, created_at) VALUES (?, ?, ?, ?, '', '', '', '', 'MEDIUM', ?);", (gap_id, inv_id, req_id, assess_empty, now))
        conn.commit()

        # Attempting dynamic generation with zero context must fail with clear message
        with pytest.raises(ValueError) as excinfo:
            generate_verification_plan(conn, inv_id, gap_id)
        
        assert "Missing required investigation context" in str(excinfo.value)
        assert "enter queries manually" in str(excinfo.value)


def test_manual_query_entry_and_editing(temp_db):
    """
    Verifies that an analyst can manually provide, edit, and replace queries on a plan,
    and that changes are recorded in the audit ledger.
    """
    data = _seed_test_investigation_with_gaps(temp_db)
    with get_db(temp_db) as conn:
        plan = generate_verification_plan(conn, data["inv_id"], data["gap_crit"])
        
        custom_queries = [
            "Analyst Custom Query Alpha: subsidiary Basel III disclosures",
            "Analyst Custom Query Beta: audited debt-to-equity covenant test"
        ]

        updated_plan = update_verification_plan_queries(conn, plan.id, custom_queries)
        assert updated_plan.search_queries == custom_queries

        # Verify audit log recorded the update
        cursor = conn.cursor()
        cursor.execute("SELECT event_type, details_json FROM orchestration_audit_log WHERE investigation_id = ? AND event_type = 'PLAN_QUERIES_UPDATED';", (data["inv_id"],))
        audit_row = cursor.fetchone()
        assert audit_row is not None
        assert audit_row["event_type"] == "PLAN_QUERIES_UPDATED"
        details = json.loads(audit_row["details_json"])
        assert details["queries_count"] == 2
        assert details["queries"] == custom_queries

        # Empty queries must be rejected with ValueError
        with pytest.raises(ValueError) as exc:
            update_verification_plan_queries(conn, plan.id, [])
        assert "At least one non-empty verification query must be provided" in str(exc.value)


def test_analyst_custom_instructions_guide_queries(temp_db):
    """
    Verifies that analyst custom instructions/directives are directly incorporated
    into dynamic query formulation.
    """
    data = _seed_test_investigation_with_gaps(temp_db)
    directive = "Focus specifically on European subsidiary liquidity coverage ratio"
    with get_db(temp_db) as conn:
        plan = generate_verification_plan(conn, data["inv_id"], data["gap_crit"], custom_instructions=directive)
        assert any(directive in q for q in plan.search_queries)
        assert not any("filetype:pdf" in q for q in plan.search_queries)


def test_search_provider_unavailability_does_not_inject_fallback(temp_db):
    """
    Verifies that when autonomous search is unavailable or empty queries are provided,
    the system reports UNAVAILABLE status with zero results and never fabricates a fallback query.
    """
    # 1. Empty queries
    res_empty = execute_search_discovery([], ["keyword1", "keyword2"])
    assert res_empty["status"] == "UNAVAILABLE"
    assert res_empty["is_available"] is False
    assert res_empty["results"] == []
    assert "No verification queries formulated" in res_empty["message"]

    # 2. Search provider 'none'
    res_none = execute_search_discovery(["custom query 1"], ["keyword1"])
    assert res_none["status"] == "UNAVAILABLE"
    assert res_none["is_available"] is False
    assert res_none["results"] == []
    assert "Manual candidate URL entry mode active" in res_none["message"]

