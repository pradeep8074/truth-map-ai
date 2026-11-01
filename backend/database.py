import sqlite3
import contextlib
from typing import Iterator
from backend.config import DB_PATH


def init_db(db_path=DB_PATH):
    """Initializes SQLite tables and indexes with foreign keys enabled."""
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON;")
        cursor = conn.cursor()

        # 1. Investigations table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS investigations (
                id TEXT PRIMARY KEY,
                research_question TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
        """)

        # 2. Sources table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sources (
                id TEXT PRIMARY KEY,
                investigation_id TEXT NOT NULL,
                source_type TEXT NOT NULL,
                source_origin TEXT DEFAULT 'UNKNOWN',
                original_url TEXT,
                title TEXT,
                publisher TEXT,
                publication_date TEXT,
                source_modified_date TEXT,
                date_source TEXT,
                date_extraction_method TEXT,
                date_confidence REAL DEFAULT 0.0,
                date_validation_status TEXT DEFAULT 'MISSING',
                freshness_status TEXT DEFAULT 'Undated Source',
                freshness_explanation TEXT DEFAULT '',
                retrieved_at TEXT NOT NULL,
                content_hash TEXT,
                extraction_status TEXT NOT NULL,
                extracted_text TEXT,
                error_message TEXT,
                FOREIGN KEY (investigation_id) REFERENCES investigations(id) ON DELETE CASCADE
            );
        """)

        # 3. Passages table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS passages (
                id TEXT PRIMARY KEY,
                source_id TEXT NOT NULL,
                passage_text TEXT NOT NULL,
                page_number INTEGER,
                paragraph_index INTEGER,
                start_offset INTEGER,
                end_offset INTEGER,
                sha256_hash TEXT NOT NULL,
                FOREIGN KEY (source_id) REFERENCES sources(id) ON DELETE CASCADE
            );
        """)

        # 4. Claims table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS claims (
                id TEXT PRIMARY KEY,
                investigation_id TEXT NOT NULL,
                source_id TEXT NOT NULL,
                passage_id TEXT NOT NULL,
                claim_text TEXT NOT NULL,
                category TEXT DEFAULT 'factual',
                extraction_method TEXT NOT NULL,
                extraction_confidence REAL NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (investigation_id) REFERENCES investigations(id) ON DELETE CASCADE,
                FOREIGN KEY (source_id) REFERENCES sources(id) ON DELETE CASCADE,
                FOREIGN KEY (passage_id) REFERENCES passages(id) ON DELETE CASCADE
            );
        """)

        # 5. Decision Contracts table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS decision_contracts (
                id TEXT PRIMARY KEY,
                investigation_id TEXT NOT NULL UNIQUE,
                original_question TEXT NOT NULL,
                normalized_question TEXT NOT NULL,
                decision_objective TEXT NOT NULL,
                scope TEXT,
                compilation_method TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (investigation_id) REFERENCES investigations(id) ON DELETE CASCADE
            );
        """)

        # 6. Contract Requirements table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS contract_requirements (
                id TEXT PRIMARY KEY,
                contract_id TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                requirement_type TEXT NOT NULL,
                priority TEXT NOT NULL,
                verification_criteria TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'unverified',
                sort_order INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (contract_id) REFERENCES decision_contracts(id) ON DELETE CASCADE
            );
        """)

        # 7. Contract Evidence Requirements table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS contract_evidence_requirements (
                id TEXT PRIMARY KEY,
                requirement_id TEXT NOT NULL,
                contract_id TEXT NOT NULL,
                evidence_type TEXT NOT NULL,
                rationale TEXT NOT NULL,
                preferred_source_types TEXT NOT NULL,
                temporal_scope TEXT,
                geographic_scope TEXT,
                FOREIGN KEY (requirement_id) REFERENCES contract_requirements(id) ON DELETE CASCADE,
                FOREIGN KEY (contract_id) REFERENCES decision_contracts(id) ON DELETE CASCADE
            );
        """)

        # 8. Contract Constraints table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS contract_constraints (
                id TEXT PRIMARY KEY,
                contract_id TEXT NOT NULL,
                description TEXT NOT NULL,
                constraint_type TEXT NOT NULL,
                FOREIGN KEY (contract_id) REFERENCES decision_contracts(id) ON DELETE CASCADE
            );
        """)

        # 9. Contract Assumptions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS contract_assumptions (
                id TEXT PRIMARY KEY,
                contract_id TEXT NOT NULL,
                description TEXT NOT NULL,
                confidence REAL NOT NULL DEFAULT 0.8,
                source TEXT NOT NULL DEFAULT 'ai_inferred',
                validation_status TEXT NOT NULL DEFAULT 'pending',
                FOREIGN KEY (contract_id) REFERENCES decision_contracts(id) ON DELETE CASCADE
            );
        """)

        # 10. Contract Unresolved Questions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS contract_unresolved_questions (
                id TEXT PRIMARY KEY,
                contract_id TEXT NOT NULL,
                question TEXT NOT NULL,
                clarification_type TEXT NOT NULL,
                dimension TEXT NOT NULL,
                FOREIGN KEY (contract_id) REFERENCES decision_contracts(id) ON DELETE CASCADE
            );
        """)

        # 11. Component 04: Evidence Relationships table (RELATES_TO edges)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS evidence_relationships (
                id TEXT PRIMARY KEY,
                investigation_id TEXT NOT NULL,
                requirement_id TEXT NOT NULL,
                claim_id TEXT NOT NULL,
                passage_id TEXT,
                relevance TEXT NOT NULL,
                explanation TEXT NOT NULL,
                confidence REAL NOT NULL,
                analysis_method TEXT NOT NULL,
                processing_mode TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (investigation_id) REFERENCES investigations(id) ON DELETE CASCADE,
                FOREIGN KEY (requirement_id) REFERENCES contract_requirements(id) ON DELETE CASCADE,
                FOREIGN KEY (claim_id) REFERENCES claims(id) ON DELETE CASCADE,
                FOREIGN KEY (passage_id) REFERENCES passages(id) ON DELETE CASCADE,
                UNIQUE(investigation_id, requirement_id, claim_id)
            );
        """)

        # 12. Component 04: Evidence Graph Runs / Status table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS evidence_graph_runs (
                id TEXT PRIMARY KEY,
                investigation_id TEXT NOT NULL,
                processing_mode TEXT NOT NULL,
                analysis_status TEXT NOT NULL,
                analyzed_pairs_count INTEGER NOT NULL DEFAULT 0,
                relevant_links_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY (investigation_id) REFERENCES investigations(id) ON DELETE CASCADE
            );
        """)

        # 13. Component 05: Evidence Conflicts & Contradictions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS evidence_conflicts (
                id TEXT PRIMARY KEY,
                investigation_id TEXT NOT NULL,
                claim_a_id TEXT NOT NULL,
                claim_b_id TEXT NOT NULL,
                conflict_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                explanation TEXT NOT NULL,
                contextual_differences TEXT,
                confidence REAL NOT NULL,
                resolution_status TEXT NOT NULL DEFAULT 'unresolved',
                reviewer_notes TEXT DEFAULT '',
                recommended_action TEXT NOT NULL,
                analysis_method TEXT NOT NULL,
                processing_mode TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (investigation_id) REFERENCES investigations(id) ON DELETE CASCADE,
                FOREIGN KEY (claim_a_id) REFERENCES claims(id) ON DELETE CASCADE,
                FOREIGN KEY (claim_b_id) REFERENCES claims(id) ON DELETE CASCADE,
                UNIQUE(investigation_id, claim_a_id, claim_b_id)
            );
        """)

        # 14. Component 05: Evidence Conflict Analysis Runs / Audit table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS evidence_conflict_runs (
                id TEXT PRIMARY KEY,
                investigation_id TEXT NOT NULL,
                processing_mode TEXT NOT NULL,
                analysis_status TEXT NOT NULL,
                pairs_analyzed_count INTEGER NOT NULL DEFAULT 0,
                conflicts_detected_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY (investigation_id) REFERENCES investigations(id) ON DELETE CASCADE
            );
        """)

        # 15. Component 06: Evidence Sufficiency Assessments table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS evidence_sufficiency_assessments (
                id TEXT PRIMARY KEY,
                investigation_id TEXT NOT NULL,
                requirement_id TEXT NOT NULL,
                coverage_status TEXT NOT NULL,
                assessment_summary TEXT NOT NULL,
                limitations TEXT DEFAULT '',
                missing_information TEXT DEFAULT '',
                recommended_action TEXT NOT NULL,
                confidence REAL NOT NULL DEFAULT 0.8,
                analysis_method TEXT NOT NULL,
                processing_mode TEXT NOT NULL DEFAULT 'fallback',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (investigation_id) REFERENCES investigations(id) ON DELETE CASCADE,
                FOREIGN KEY (requirement_id) REFERENCES contract_requirements(id) ON DELETE CASCADE,
                UNIQUE(investigation_id, requirement_id)
            );
        """)

        # 16. Component 06: Evidence Gaps table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS evidence_gaps (
                id TEXT PRIMARY KEY,
                investigation_id TEXT NOT NULL,
                requirement_id TEXT NOT NULL,
                assessment_id TEXT NOT NULL,
                gap_description TEXT NOT NULL,
                why_it_matters TEXT NOT NULL,
                evidence_needed TEXT NOT NULL,
                suggested_source_type TEXT DEFAULT 'Authoritative Audit / Regulatory Filing',
                priority TEXT NOT NULL DEFAULT 'HIGH',
                created_at TEXT NOT NULL,
                FOREIGN KEY (investigation_id) REFERENCES investigations(id) ON DELETE CASCADE,
                FOREIGN KEY (requirement_id) REFERENCES contract_requirements(id) ON DELETE CASCADE,
                FOREIGN KEY (assessment_id) REFERENCES evidence_sufficiency_assessments(id) ON DELETE CASCADE
            );
        """)

        # 17. Component 06: Evidence Sufficiency Runs / Audit table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS evidence_sufficiency_runs (
                id TEXT PRIMARY KEY,
                investigation_id TEXT NOT NULL,
                processing_mode TEXT NOT NULL,
                analysis_status TEXT NOT NULL,
                requirements_count INTEGER NOT NULL DEFAULT 0,
                sufficient_count INTEGER NOT NULL DEFAULT 0,
                partial_count INTEGER NOT NULL DEFAULT 0,
                insufficient_count INTEGER NOT NULL DEFAULT 0,
                no_evidence_count INTEGER NOT NULL DEFAULT 0,
                conflicting_count INTEGER NOT NULL DEFAULT 0,
                gaps_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY (investigation_id) REFERENCES investigations(id) ON DELETE CASCADE
            );
        """)

        # 18. Component 07: Decision Stress Scenarios table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS decision_stress_scenarios (
                id TEXT PRIMARY KEY,
                investigation_id TEXT NOT NULL,
                title TEXT NOT NULL,
                category TEXT NOT NULL,
                description TEXT NOT NULL,
                trigger_condition TEXT NOT NULL,
                challenged_assumptions TEXT NOT NULL DEFAULT '[]',
                affected_requirement_ids TEXT NOT NULL DEFAULT '[]',
                related_claim_ids TEXT NOT NULL DEFAULT '[]',
                related_source_ids TEXT NOT NULL DEFAULT '[]',
                related_conflict_ids TEXT NOT NULL DEFAULT '[]',
                expected_impact TEXT NOT NULL,
                severity TEXT NOT NULL,
                evidence_needed TEXT NOT NULL,
                processing_mode TEXT NOT NULL DEFAULT 'fallback',
                created_at TEXT NOT NULL,
                FOREIGN KEY (investigation_id) REFERENCES investigations(id) ON DELETE CASCADE
            );
        """)

        # 19. Component 07: Decision Stress Evaluations table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS decision_stress_evaluations (
                id TEXT PRIMARY KEY,
                scenario_id TEXT NOT NULL UNIQUE,
                investigation_id TEXT NOT NULL,
                baseline_overall_outcome TEXT NOT NULL,
                scenario_overall_outcome TEXT NOT NULL,
                outcome_shift TEXT NOT NULL,
                impact_explanation TEXT NOT NULL,
                key_vulnerabilities TEXT NOT NULL DEFAULT '[]',
                uncertainty_factors TEXT NOT NULL DEFAULT '[]',
                recommended_actions TEXT NOT NULL DEFAULT '[]',
                requirement_evaluations TEXT NOT NULL DEFAULT '[]',
                processing_mode TEXT NOT NULL DEFAULT 'fallback',
                evaluated_at TEXT NOT NULL,
                FOREIGN KEY (scenario_id) REFERENCES decision_stress_scenarios(id) ON DELETE CASCADE,
                FOREIGN KEY (investigation_id) REFERENCES investigations(id) ON DELETE CASCADE
            );
        """)

        # 20. Component 07: Decision Stress Runs / Audit table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS decision_stress_runs (
                id TEXT PRIMARY KEY,
                investigation_id TEXT NOT NULL,
                processing_mode TEXT NOT NULL,
                status TEXT NOT NULL,
                scenarios_generated INTEGER NOT NULL DEFAULT 0,
                scenarios_evaluated INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY (investigation_id) REFERENCES investigations(id) ON DELETE CASCADE
            );
        """)

        # 21. Component 08: Decision Intelligence Reports table (Versioned)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS decision_intelligence_reports (
                id TEXT PRIMARY KEY,
                investigation_id TEXT NOT NULL,
                report_version INTEGER NOT NULL,
                report_status TEXT NOT NULL DEFAULT 'published',
                processing_mode TEXT NOT NULL DEFAULT 'fallback',
                overall_robustness TEXT NOT NULL,
                executive_summary TEXT NOT NULL,
                report_data_json TEXT NOT NULL,
                snapshot_metadata_json TEXT NOT NULL DEFAULT '{}',
                is_stale INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (investigation_id) REFERENCES investigations(id) ON DELETE CASCADE,
                UNIQUE(investigation_id, report_version)
            );
        """)

        # 22. Component 08: Decision Intelligence Report Runs / Audit table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS decision_intelligence_report_runs (
                id TEXT PRIMARY KEY,
                investigation_id TEXT NOT NULL,
                report_id TEXT,
                processing_mode TEXT NOT NULL,
                status TEXT NOT NULL,
                error_message TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                FOREIGN KEY (investigation_id) REFERENCES investigations(id) ON DELETE CASCADE
            );
        """)

        # 23. Component 09: Decision Fragility Runs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS decision_fragility_runs (
                id TEXT PRIMARY KEY,
                investigation_id TEXT NOT NULL,
                input_fingerprint TEXT NOT NULL,
                is_provisional INTEGER NOT NULL DEFAULT 0,
                processing_mode TEXT NOT NULL DEFAULT 'fallback',
                status TEXT NOT NULL DEFAULT 'success',
                error_message TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                FOREIGN KEY (investigation_id) REFERENCES investigations(id) ON DELETE CASCADE
            );
        """)

        # 24. Component 09: Decision Fragility Results table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS decision_fragility_results (
                id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                investigation_id TEXT NOT NULL,
                methodology_version TEXT NOT NULL DEFAULT 'v1.2.0-deterministic',
                dfi_score REAL NOT NULL,
                classification TEXT NOT NULL,
                is_provisional INTEGER NOT NULL DEFAULT 0,
                guardrail_active INTEGER NOT NULL DEFAULT 0,
                guardrail_reason TEXT DEFAULT '',
                d1_coverage REAL NOT NULL,
                d2_assumptions REAL NOT NULL,
                d3_conflicts REAL NOT NULL,
                d4_stress REAL NOT NULL,
                d5_concentration REAL NOT NULL,
                dimension_details_json TEXT NOT NULL DEFAULT '{}',
                attribution_ledger_json TEXT NOT NULL DEFAULT '[]',
                explanation_text TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                FOREIGN KEY (run_id) REFERENCES decision_fragility_runs(id) ON DELETE CASCADE,
                FOREIGN KEY (investigation_id) REFERENCES investigations(id) ON DELETE CASCADE
            );
        """)

        # 25. Component 09: Decision Sensitivity Experiments table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS decision_sensitivity_experiments (
                id TEXT PRIMARY KEY,
                investigation_id TEXT NOT NULL,
                experiment_type TEXT NOT NULL,
                is_hypothetical INTEGER NOT NULL DEFAULT 1,
                target_entity_id TEXT,
                target_entity_type TEXT,
                baseline_dfi REAL NOT NULL,
                simulated_dfi REAL NOT NULL,
                delta_dfi REAL NOT NULL,
                baseline_classification TEXT NOT NULL,
                simulated_classification TEXT NOT NULL,
                simulation_parameters_json TEXT NOT NULL DEFAULT '{}',
                narrative_impact TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                FOREIGN KEY (investigation_id) REFERENCES investigations(id) ON DELETE CASCADE
            );
        """)

        # 26. Component 09: Decision Fragility Recommendations table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS decision_fragility_recommendations (
                id TEXT PRIMARY KEY,
                investigation_id TEXT NOT NULL,
                run_id TEXT,
                recommendation_type TEXT NOT NULL,
                target_entity_id TEXT NOT NULL,
                target_entity_type TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                projected_dfi_reduction REAL NOT NULL,
                is_hypothetical_projection INTEGER NOT NULL DEFAULT 1,
                priority TEXT NOT NULL,
                effort_estimate TEXT NOT NULL,
                action_steps_json TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL,
                FOREIGN KEY (investigation_id) REFERENCES investigations(id) ON DELETE CASCADE
            );
        """)

        # 27. Component 10: Investigation Orchestration Runs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS investigation_orchestration_runs (
                id TEXT PRIMARY KEY,
                investigation_id TEXT NOT NULL,
                source_id TEXT,
                trigger_workflow TEXT NOT NULL,       -- 'GAP_VERIFICATION' or 'DIRECT_SOURCE_INTEGRATION'
                status TEXT NOT NULL,                 -- 'PENDING', 'RUNNING', 'SUCCESS', 'PARTIAL_SUCCESS', 'FAILED', 'DUPLICATE_SOURCE_SKIPPED'
                current_stage TEXT NOT NULL,
                failure_stage TEXT,
                error_message TEXT,
                stages_execution_json TEXT NOT NULL DEFAULT '{}', -- Keyed by stage: {status, skipped_reason, duration_ms}
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (investigation_id) REFERENCES investigations(id) ON DELETE CASCADE,
                FOREIGN KEY (source_id) REFERENCES sources(id) ON DELETE CASCADE
            );
        """)

        # 28. Component 10: Unified Source Impact Reports table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS source_impact_reports (
                id TEXT PRIMARY KEY,
                orchestration_run_id TEXT NOT NULL UNIQUE,
                investigation_id TEXT NOT NULL,
                source_id TEXT NOT NULL,
                impact_summary_json TEXT NOT NULL,
                delta_dfi REAL NOT NULL DEFAULT 0.0,
                is_stale_flagged INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                FOREIGN KEY (orchestration_run_id) REFERENCES investigation_orchestration_runs(id) ON DELETE CASCADE,
                FOREIGN KEY (investigation_id) REFERENCES investigations(id) ON DELETE CASCADE,
                FOREIGN KEY (source_id) REFERENCES sources(id) ON DELETE CASCADE
            );
        """)

        # 29. Component 10: Gap Verification Plans table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS gap_verification_plans (
                id TEXT PRIMARY KEY,
                investigation_id TEXT NOT NULL,
                gap_id TEXT NOT NULL,
                requirement_id TEXT NOT NULL,
                verification_objective TEXT NOT NULL,
                required_evidence_type TEXT NOT NULL,
                target_authority_tier TEXT NOT NULL,
                search_queries_json TEXT NOT NULL DEFAULT '[]',
                search_provider_status TEXT NOT NULL DEFAULT 'UNAVAILABLE', -- 'ACTIVE' or 'UNAVAILABLE'
                status TEXT NOT NULL DEFAULT 'PLANNED',                     -- 'PLANNED', 'DISCOVERED', 'COMPLETED', 'ABANDONED', 'REQUIRES_MANUAL_QUERIES'
                missing_context_warning TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (investigation_id) REFERENCES investigations(id) ON DELETE CASCADE,
                FOREIGN KEY (gap_id) REFERENCES evidence_gaps(id) ON DELETE CASCADE,
                FOREIGN KEY (requirement_id) REFERENCES contract_requirements(id) ON DELETE CASCADE
            );
        """)

        # 30. Component 10: Candidate Sources table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS gap_candidate_sources (
                id TEXT PRIMARY KEY,
                plan_id TEXT NOT NULL,
                investigation_id TEXT NOT NULL,
                url TEXT NOT NULL,
                domain TEXT NOT NULL,
                title TEXT NOT NULL,
                snippet TEXT NOT NULL,
                authority_tier TEXT NOT NULL DEFAULT 'TIER_3',
                relevance_score REAL NOT NULL DEFAULT 0.0,
                discovery_mode TEXT NOT NULL DEFAULT 'MANUAL_ENTRY', -- 'MANUAL_ENTRY' or 'SEARCH_PROVIDER'
                relevance_rationale TEXT NOT NULL,
                review_status TEXT NOT NULL DEFAULT 'PENDING_REVIEW', -- 'PENDING_REVIEW', 'APPROVED', 'REJECTED'
                rejection_reason TEXT,
                discovered_at TEXT NOT NULL,
                FOREIGN KEY (plan_id) REFERENCES gap_verification_plans(id) ON DELETE CASCADE,
                FOREIGN KEY (investigation_id) REFERENCES investigations(id) ON DELETE CASCADE,
                UNIQUE(plan_id, url)
            );
        """)

        # 31. Component 10: Gap Reassessments table (Human-Governed)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS gap_reassessments (
                id TEXT PRIMARY KEY,
                investigation_id TEXT NOT NULL,
                gap_id TEXT NOT NULL,
                orchestration_run_id TEXT,
                previous_state TEXT NOT NULL,             -- State prior to reassessment
                proposed_resolution_state TEXT NOT NULL,  -- Calculated by deterministic rule engine
                analyst_decision TEXT NOT NULL DEFAULT 'PENDING_DECISION', -- 'APPROVED', 'OVERRIDDEN', 'REJECTED', 'PENDING_DECISION'
                analyst_final_state TEXT,                 -- Effective state after analyst review
                analyst_notes TEXT,                       -- Mandatory reviewer forensic notes
                reviewed_by TEXT,                         -- Analyst identifier
                reviewed_at TEXT,                         -- Review timestamp
                matched_claim_ids_json TEXT NOT NULL DEFAULT '[]',
                predicate_fulfillment_score REAL NOT NULL,
                composite_evidence_score REAL NOT NULL,
                is_analyst_override INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY (investigation_id) REFERENCES investigations(id) ON DELETE CASCADE,
                FOREIGN KEY (gap_id) REFERENCES evidence_gaps(id) ON DELETE CASCADE,
                FOREIGN KEY (orchestration_run_id) REFERENCES investigation_orchestration_runs(id) ON DELETE SET NULL
            );
        """)

        # 32. Component 10: Central Orchestration Audit Log table (Append-Only)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS orchestration_audit_log (
                id TEXT PRIMARY KEY,
                investigation_id TEXT NOT NULL,
                orchestration_run_id TEXT,
                source_id TEXT,
                event_type TEXT NOT NULL,
                actor TEXT NOT NULL,                      -- 'SYSTEM_ORCHESTRATOR', 'ANALYST', 'SEARCH_ADAPTER'
                details_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                FOREIGN KEY (investigation_id) REFERENCES investigations(id) ON DELETE CASCADE
            );
        """)

        # Schema migrations for backward-compatibility with existing SQLite db
        try:
            cursor.execute("ALTER TABLE claims ADD COLUMN category TEXT DEFAULT 'factual';")
        except sqlite3.OperationalError:
            pass

        try:
            cursor.execute("ALTER TABLE contract_assumptions ADD COLUMN source TEXT DEFAULT 'ai_inferred';")
        except sqlite3.OperationalError:
            pass

        try:
            cursor.execute("ALTER TABLE decision_intelligence_reports ADD COLUMN is_stale INTEGER NOT NULL DEFAULT 0;")
        except sqlite3.OperationalError:
            pass

        # Freshness metadata migrations for sources table
        for col_name, col_type in [
            ("source_modified_date", "TEXT"),
            ("date_source", "TEXT"),
            ("date_extraction_method", "TEXT"),
            ("date_confidence", "REAL DEFAULT 0.0"),
            ("date_validation_status", "TEXT DEFAULT 'MISSING'"),
            ("freshness_status", "TEXT DEFAULT 'Undated Source'"),
            ("freshness_explanation", "TEXT DEFAULT ''"),
            ("source_origin", "TEXT DEFAULT 'UNKNOWN'"),
        ]:
            try:
                cursor.execute(f"ALTER TABLE sources ADD COLUMN {col_name} {col_type};")
            except sqlite3.OperationalError:
                pass

        # Indexes for fast joins
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sources_inv ON sources(investigation_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_passages_source ON passages(source_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_claims_inv ON claims(investigation_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_claims_passage ON claims(passage_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_contracts_inv ON decision_contracts(investigation_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_req_contract ON contract_requirements(contract_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ev_req ON contract_evidence_requirements(requirement_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_const_contract ON contract_constraints(contract_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_assump_contract ON contract_assumptions(contract_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_unres_contract ON contract_unresolved_questions(contract_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ev_rel_inv ON evidence_relationships(investigation_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ev_rel_req ON evidence_relationships(requirement_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ev_rel_claim ON evidence_relationships(claim_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_graph_runs_inv ON evidence_graph_runs(investigation_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_conflicts_inv ON evidence_conflicts(investigation_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_conflicts_claim_a ON evidence_conflicts(claim_a_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_conflicts_claim_b ON evidence_conflicts(claim_b_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_conflict_runs_inv ON evidence_conflict_runs(investigation_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sufficiency_inv ON evidence_sufficiency_assessments(investigation_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sufficiency_req ON evidence_sufficiency_assessments(requirement_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_gaps_inv ON evidence_gaps(investigation_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_gaps_req ON evidence_gaps(requirement_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sufficiency_runs_inv ON evidence_sufficiency_runs(investigation_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_scenarios_inv ON decision_stress_scenarios(investigation_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_evaluations_scenario ON decision_stress_evaluations(scenario_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_evaluations_inv ON decision_stress_evaluations(investigation_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_stress_runs_inv ON decision_stress_runs(investigation_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_reports_inv ON decision_intelligence_reports(investigation_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_reports_version ON decision_intelligence_reports(investigation_id, report_version);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_report_runs_inv ON decision_intelligence_report_runs(investigation_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_fragility_runs_inv ON decision_fragility_runs(investigation_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_fragility_results_inv ON decision_fragility_results(investigation_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_fragility_results_run ON decision_fragility_results(run_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sensitivity_exp_inv ON decision_sensitivity_experiments(investigation_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_fragility_recs_inv ON decision_fragility_recommendations(investigation_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_orch_runs_inv ON investigation_orchestration_runs(investigation_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_orch_runs_source ON investigation_orchestration_runs(source_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_impact_reports_inv ON source_impact_reports(investigation_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cand_sources_plan ON gap_candidate_sources(plan_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_gap_reassess_gap ON gap_reassessments(gap_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_orch_audit_inv ON orchestration_audit_log(investigation_id);")

        # Backward compatibility migration for gap_verification_plans
        cursor.execute("PRAGMA table_info(gap_verification_plans);")
        plan_cols = [c[1] for c in cursor.fetchall()]
        if plan_cols and "missing_context_warning" not in plan_cols:
            cursor.execute("ALTER TABLE gap_verification_plans ADD COLUMN missing_context_warning TEXT;")

        conn.commit()


@contextlib.contextmanager
def get_db(db_path=None) -> Iterator[sqlite3.Connection]:
    """Yields a database connection with Row factory and foreign keys enabled."""
    target_path = db_path if db_path is not None else DB_PATH
    conn = sqlite3.connect(target_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        yield conn
    finally:
        conn.close()
