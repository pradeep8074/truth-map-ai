# TRUTHMAP AI — Project Status

Updated: 31 October 2026

## Overview
TRUTHMAP AI is an Evidence Intelligence & Decision Stress-Testing Platform that cross-examines information from websites and documents, identifies evidence dependencies, detects factual contradictions and numerical variances, evaluates evidence sufficiency against decision contracts, stress-tests decision fragility, and synthesizes audit-grade, traceable decision intelligence reports.

---

## 1. Completed Components

### Component 01 — Project Foundation & Enterprise UI Shell
- Modern React + TypeScript + Vite + Tailwind CSS shell with dark tactical aesthetic.
- Global navigation across all 11 enterprise intelligence modules.
- Responsive AppShell, collapsible sidebar, search command palette (`Ctrl+K`).
- Strict zero-synthetic metric policy on dashboard.

### Component 02 — Live Source Ingestion & Evidence Extraction Pipeline
- Ingestion of live web URLs (with SSRF protection, readability parsing, article extraction).
- Ingestion of PDF documents (page tracking, paragraph segmentation, scanned document heuristic warnings).
- Cryptographic provenance tracking (SHA-256 passage hashes, character offsets, page coordinates).
- Atomic claim extraction with Gemini LLM integration and deterministic NLP compound-sentence fallback.
- SQLite persistence (`investigations`, `sources`, `passages`, `claims`).

### Component 03 — Decision Contract Compiler
- Natural language decision question parsing and contract compilation.
- Structured breakdown into Decision Objective, Scope, Decision Requirements, and Evidence Requirements.
- Identification of explicit Constraints, Assumptions, and actionable Ambiguity Clarifications.
- Gemini structured compilation with deterministic rule-based fallback.
- SQLite persistence (`decision_contracts`, `contract_requirements`, `contract_evidence_requirements`, `contract_constraints`, `contract_assumptions`, `contract_unresolved_questions`).
- Interactive Decision Contract Studio interface.

### Component 04 — Evidence Dependency Graph
- Topological graph data model linking Decision Contract -> Requirements -> Evidence Requirements -> Claims -> Passages -> Sources.
- Gemini semantic relevance classifier evaluating claim-to-requirement links (`DIRECTLY_RELEVANT`, `PARTIALLY_RELEVANT`, `CONTEXTUAL`, `NOT_RELEVANT`).
- Deterministic keyword and entity fallback scanner.
- SQLite persistence (`evidence_relationships`, `evidence_graph_runs`).
- Interactive React Flow Evidence Explorer with topological band layouts, edge animations, minimap, and node inspection drawer.

### Component 05 — Evidence Contradiction & Conflict Detection Engine
- Cross-claim contradiction engine detecting factual clashes, numerical discrepancies, temporal misalignments, and contextual tensions across sources.
- 6 conflict classifications: `DIRECT_CONTRADICTION`, `NUMERICAL_CONFLICT`, `TEMPORAL_CONFLICT`, `CONTEXTUAL_TENSION`, `METHODOLOGICAL_DISAGREEMENT`, `UNRESOLVED_CONFLICT`.
- 4 severity levels: `CRITICAL`, `HIGH`, `MEDIUM`, `LOW`.
- Dual analysis pipeline: Live Gemini LLM structured reasoning with multi-model fallback and deterministic token/polarity fallback.
- Provenance verification: Every conflict links directly to both claims, original passage texts, page coordinates, and SHA-256 hashes.
- Evidence Dependency Graph integration: Conflicting claim nodes connected via `CONFLICTS_WITH` dashed red edges in the topological graph.
- Human-in-the-loop analyst resolution workflow: Lifecycle statuses (`unresolved`, `under_review`, `resolved`) with persistent reviewer forensic notes.
- Enterprise Conflict Explorer UI (`src/pages/ConflictPage.tsx`): KPI summary cards, filter/search toolbar, split feed, and side-by-side forensic inspector.

### Component 06 — Evidence Sufficiency & Gap Analysis Engine
- Evaluates whether available evidence adequately addresses each requirement in the Decision Contract.
- 5 rigorously defined coverage statuses: `SUFFICIENT`, `PARTIAL`, `INSUFFICIENT`, `NO_EVIDENCE`, `CONFLICTING`.
- Conflict-Aware Reasoning: Unresolved conflicts (Component 05) block `SUFFICIENT` status and flag `CONFLICTING`; resolved conflicts do not penalize sufficiency.
- Concrete Evidence Gaps: Isolates actionable gaps with `gap_description`, `why_it_matters`, `evidence_needed`, `suggested_source_type`, and `priority` (`HIGH`, `MEDIUM`, `LOW`).
- Dual Evaluation Engine: Live Gemini Structured Reasoning (`gemini-2.5-flash` with candidate fallback models) and deterministic rule-based fallback.
- SQLite Database Persistence: `evidence_sufficiency_assessments`, `evidence_gaps`, `evidence_sufficiency_runs`.
- Evidence Dependency Graph Integration: Requirement nodes (`decision_requirement`) in Component 04's Evidence Graph enriched with `coverage_status`, `sufficiency_confidence`, `assessment_summary`, and `gaps_count`.
- Full REST API Suite (`/api/investigations/{id}/sufficiency`, `/analyze`, `/status`, `/requirements/{id}`).

### Component 07 — Decision Stress Testing Engine
- Rigorous stress testing against 6 failure scenario categories:
  1. `ASSUMPTION_FAILURE`: A foundational contract assumption proves invalid.
  2. `EVIDENCE_WEAKENING`: High-confidence evidence is invalidated, discredited, or retracted.
  3. `CONFLICT_RESOLUTION`: An unresolved conflict is resolved in favor of the unfavorable claim.
  4. `EXTERNAL_CONDITION_CHANGE`: Macro, environmental, regulatory, or operational parameters shift unfavorably.
  5. `RISK_MATERIALIZATION`: A low-probability, high-impact risk identified in evidence occurs.
  6. `COUNTERFACTUAL_REVERSAL`: Counterfactual or baseline comparison demonstrates lack of causal attribution.
- Baseline Outcome Computation: Grounded in contract coverage and unresolved critical conflicts.
- Scenario Outcome Shift: `CRITICAL_FAILURE`, `DEGRADED`, `STABLE`, `IMPROVED`, `INDETERMINATE`.
- Requirement-Level Impact Tracking: Maps exactly which requirements are shifted and reasons for shift.
- Dual Stress-Testing Engine: Live Gemini LLM structured scenario generation with multi-model fallback and deterministic heuristic generation.
- Evidence Dependency Graph Integration: Stress scenario nodes (`stress_scenario`) rendered in React Flow with animated `CHALLENGES` and `CONTESTS` edges.
- Interactive Stress Testing Studio (`src/pages/StressTestPage.tsx`): KPI summary cards, scenario catalog, outcome shift inspector, and comparative matrix.

### Component 08 — Decision Intelligence Report Engine
- Comprehensive aggregation and synthesis of Components 02–07 into an audit-grade, traceable Decision Intelligence Report.
- 10 Standardized Sections:
  1. `Executive Decision Brief`: Investigation title, objective, date, overall robustness (`ROBUST`, `CONDITIONALLY_ROBUST`, `VULNERABLE`, `HIGHLY_VULNERABLE`, `INDETERMINATE`), coverage %, unresolved conflicts, gaps, stress scenarios, executive verdict.
  2. `Decision Contract Baseline`: Objective, criteria, evidence requirements, constraints, assumptions, and ambiguities.
  3. `Evidence Intelligence Summary`: Ingested sources, atomic claims, passage provenance, SHA-256 hashes, and reliability limitations.
  4. `Requirement-Level Assessment Matrix`: Structured matrix connecting requirements to sufficiency statuses, supporting claims, opposing evidence, gaps, and confidence.
  5. `Conflict & Contradiction Analysis`: Classifications, severities, claims, sources, lifecycle resolution statuses, reviewer notes, and decision impact.
  6. `Evidence Gaps & Uncertainty Register`: Missing requirements, partially supported areas, conflicting evidence, data limitations, and evidence needed.
  7. `Decision Stress-Test Results`: Baseline outcome vs stress scenario outcomes across 6 categories, trigger conditions, affected requirements, outcome shifts, vulnerabilities, and mitigations.
  8. `Actionable Risk Register & Mitigations`: Actionable risks derived from conflicts, gaps, stress tests, and assumptions (ID, title, origin, severity, consequence, mitigation, required evidence).
  9. `Prioritized Analyst Next Actions`: Action items prioritized by urgency (`P1_IMMEDIATE`, `P2_HIGH`, `P3_MODERATE`) with drivers and expected analytical outcomes.
  10. `Final Decision Intelligence Conclusion`: Evidence-backed supported findings, uncertainties and caveats, invalidating conditions, recommended decision posture (`PROCEED`, `PROCEED_WITH_SAFEGUARDS`, `DEFER_PENDING_EVIDENCE`, `REJECT_INSUFFICIENT_EVIDENCE`), epistemic boundary disclaimer, and cryptographic integrity seal.
- Atomic Versioning & Immutability:
  - Reports versioned sequentially (`report_version: 1, 2, ...`).
  - Historical reports remain strictly immutable and never overwritten.
  - Concurrency-safe atomic version assignment with SQLite transaction retry logic.
  - Deterministic content-based snapshot fingerprinting (SHA-256 canonical hash across all upstream Components 02–07 records).
  - Staleness detection: Flags `is_stale: True` when any upstream record is added, modified, or removed.
- Dual Synthesis Engine: Live Gemini LLM structured synthesis (`gemini-2.5-flash` with candidate fallback models) and deterministic synthesis fallback.
- SQLite Database Persistence: `decision_intelligence_reports`, `decision_intelligence_report_runs`.
- Enterprise Intelligence Reports UI (`src/pages/ReportsPage.tsx`).

### Component 09 — Decision Fragility Index & Sensitivity Scoring Engine
- Implemented strictly in accordance with approved specification methodology `v1.2.0-deterministic`.
- Deterministic 5-Dimension Fragility Architecture:
  1. `D1 Evidence Coverage Fragility (30%)`: Priority-weighted deficit sum over contract requirements ($w_i \in \{1.0, 0.75, 0.50, 0.25\}$; Deficits: `NO_EVIDENCE` 1.0, `CONFLICTING` 0.85, `INSUFFICIENT` 0.75, `PARTIAL` 0.40, `SUFFICIENT` 0.0).
  2. `D2 Assumption Fragility (15%)`: Explicit assumption uncertainty penalty $P(a_j)$ based on validation status and confidence. If $|A| == 0 \implies D_2 = 0.0$ (`NOT_APPLICABLE`) with `implicit_uncertainty_flag: true`.
  3. `D3 Conflict Fragility (25%)`: Sum of conflict severity base penalties ($35, 20, 10, 5$) scaled by resolution multipliers ($1.0, 0.7, 0.15$). If C05 unexecuted $\implies D_3 = 0.0$ (`NOT_ASSESSED`).
  4. `D4 Stress Test Vulnerability (20%)`: Cumulative outcome shift penalty from stress testing ($30, 15, 10, 0, -5$) scaled by severity multipliers ($1.0, 0.8, 0.5, 0.25$). If C07 unexecuted $\implies D_4 = 0.0$ (`NOT_ASSESSED`).
  5. `D5 Sensitivity Concentration (10%)`: Normalized Herfindahl-Hirschman Index $C \in [0.0, 1.0]$ scaled by peak requirement deficit $F_{\max}$. Unconcentrated/distributed profiles yield 0.0; single-point critical failures yield 100.0.
- Strict Half-Up Rounding: Standard Python `Decimal.quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)` guaranteeing reproducible boundary behavior.
- Guardrail & Provisional Policy Overrides:
  - `Critical Deficit Guardrail`: If any `CRITICAL` requirement has `NO_EVIDENCE` or `CONFLICTING`, classification is unconditionally overridden to `CRITICAL DEFICIT GUARDRAIL: UNGROUNDED FOUNDATION (DFI: X.X)` regardless of score.
  - `Provisional Policy`: If C05 or C07 has not been run, `is_provisional = true`, and any score $\le 25.0$ is held at `MODERATE FRAGILITY (PROVISIONAL - INCOMPLETE COVERAGE)`.
  - `Substantiation Warning`: Any `CRITICAL` requirement with `INSUFFICIENT` or `PARTIAL` evidence is visibly flagged as not fully substantiated, even when the Critical Deficit Guardrail is not triggered.
  - `Stress Phrasing`: If all evaluated stress scenarios are stable ($D_4 = 0.0$), notice explicitly reports: "No degradation was detected in the evaluated scenarios. This does not establish resilience to untested scenarios or real-world shocks."
- Point-by-Point Attribution Ledger: Every score point is tied to specific requirement IDs, assumption statements, conflict IDs, or stress scenarios with base penalties, multipliers, and net contributions.
- Isolated In-Memory Sensitivity Sandbox: Counterfactual experiments evaluate hypothetical evidence shifts strictly in-memory without mutating underlying database records.
- Prioritized Evidence Improvement Matrix: Deterministically projects DFI reduction ($\Delta \text{DFI}_{\text{reduction}}$) for resolving each conflict, validating each assumption, or corroborating each gap, ranked by impact descending.
- SQLite Database Persistence: `decision_fragility_runs`, `decision_fragility_results`, `decision_sensitivity_experiments`, `decision_fragility_recommendations`.
- Enterprise Fragility Workspace UI (`src/pages/FragilityPage.tsx`).

### Component 10 — Autonomous Gap Verification & Investigation Update Navigator
- Implemented in accordance with approved architecture specification `v2.1-Final` and strict Predefined Query Removal directive.
- Dual-Workflow Architecture:
  1. `Workflow A: Gap-Driven Verification`:
     - Prioritized queue of Component 06 negative-space gaps ordered by requirement priority (`CRITICAL` > `HIGH` > `MEDIUM` > `LOW`) and projected DFI reduction.
     - **Dynamic Context-Driven Query Generation**: 100% dynamic synthesis deriving search queries strictly from live investigation parameters: `research_question`, `decision_objective`, `requirement_title`, `verification_criteria`, `evidence_needed`, `gap_description`, and analyst `custom_instructions`.
     - **Zero Predefined / Hardcoded Queries**: Complete removal of all static search templates, fixed boolean operators, hardcoded domain scopes (`filetype:pdf`, `site:sec.gov`, `site:gov`, `annual report 10-K`, `audit certified`), and canned phrase injection.
     - **Full Analyst Query Control**: Dedicated manual query formulation, inline editing, addition, and deletion in both REST API (`PUT /navigator/plans/{plan_id}/queries`) and Enterprise UI.
     - **Explicit Missing Context Guardrail**: If substantive context is missing, the engine refuses to run or synthesize generic fallbacks; instead it provides transparent actionable diagnostics and prompts analyst guidance.
     - SSRF-quarantined manual candidate source discovery and candidate triage.
     - **HITL Gate 1 (Analyst Triage)**: Analysts approve or reject candidate sources before ingestion.
     - Ingestion and cross-claim examination via Component 02 and Component 05.
     - Deterministic proposed reassessment computation (`PENDING_DECISION`) with predicate fulfillment scoring and composite evidence scoring.
     - **HITL Gate 2 (Analyst Commit)**: Analysts review and commit final resolution state (`RESOLVED`, `PARTIALLY_ADDRESSED`, `UNCHANGED`, `WORSENED`) with mandatory forensic rationale.
  2. `Workflow B: Investigation-Wide Source Integration`:
     - Central Idempotent Orchestrator wired to automatic ingestion hooks for web URLs and PDF document uploads.
     - 8-stage selective DAG execution pipeline:
       * `STAGE_0_INGESTION`: Source ingestion & content hash deduplication.
       * `STAGE_1_GRAPH_LINKAGE`: Atomic claims linkage to contract requirements.
       * `STAGE_2_CONTRADICTIONS`: Cross-source contradiction & conflict detection.
       * `STAGE_3_ASSUMPTIONS`: Assumption impact evaluation (`SUPPORTS`, `CHALLENGES`, `CONTRADICTS`).
       * `STAGE_4_SUFFICIENCY_GAPS`: Requirement coverage and gap impact assessment.
       * `STAGE_5_STRESS_TESTS`: Stress scenario invalidation and selective re-run.
       * `STAGE_6_FRAGILITY_DFI`: Deterministic DFI re-scoring and classification shift tracking.
       * `STAGE_7_REPORT_INVALIDATION`: Explicit report staleness stamping (`is_stale = 1`).
     - Unified Source Impact Summary presenting stage breakdown, downstream impacts, and DFI shift.
- Mandatory Epistemic Guardrails:
  - **No Auto-Resolution**: The orchestrator only ever calculates and stores a proposed gap reassessment (`PENDING_DECISION`). Gaps remain in active registers until explicit analyst Gate 2 sign-off.
  - **No Auto-Validation**: Assumption `validation_status` is strictly preserved (`unvalidated` remains untouched); relationships are recorded as `SUPPORTS`, `CHALLENGES`, or `CONTRADICTS` in `evidence_relationships`.
  - **No Auto-Regeneration**: Existing Component 08 reports are never automatically regenerated or overwritten during orchestration; they are explicitly stamped `is_stale = 1`.
  - **Transparent Search Provider State**: If no external search API key is configured (`SEARCH_PROVIDER=none`), provider status is prominently flagged as `UNAVAILABLE` with manual candidate URL submission active and zero mock, synthetic, or fallback search results.
  - **Idempotency & Deduplication**: Re-running existing sources returns cached execution records; sources with duplicate content hashes bypass extraction with 0 duplicate claims.
- SQLite Database Persistence:
  - `investigation_orchestration_runs`
  - `source_impact_reports`
  - `gap_verification_plans` (with `missing_context_warning`)
  - `gap_candidate_sources`
  - `gap_reassessments`
  - `orchestration_audit_log`
- Enterprise Verification Navigator UI (`src/pages/VerificationPage.tsx`):
  - Dual-mode workspace: Gap Verification Queue & Plan Studio (Workflow A) and Source Integration Feed (Workflow B).
  - Analyst instructions input field for dynamic plan steering.
  - Interactive Query Management: Inline edit, save, cancel, delete, and manual query addition.
  - Missing context diagnostic alerts.
  - Gate 1 Candidate Triage drawer and Gate 2 Reassessment Sign-off modal.
  - Interactive 8-Stage DAG execution timeline with stage badges (`COMPLETED`, `NOT_AFFECTED`, `NOT_RUN`, `FAILED`).
  - Immutable audit trail inspector.

---

## 2. Master Integration Status (Components 01–10)

Completed comprehensive validation across all 10 components on 31 October 2026:
- **System Architecture**: 10 registered FastAPI routers, 32 SQLite database tables, React Flow graph architecture, zero orphaned records, zero foreign key violations (`PRAGMA foreign_key_check = 0`).
- **Live Empirical Demonstration** (`backend/scratch/verify_live_component10.py`):
  - **Workflow B**: Source ingestion triggered 8-stage Central Orchestrator, dynamically marked baseline report stale (`is_stale = 1`), preserved assumption status (`unvalidated`), shifted DFI score from 0.0 to 33.8, and verified duplicate content hash suppression (`is_duplicate = True`).
  - **Workflow A**: Prioritized queue sorted by requirement priority (`CRITICAL` > `HIGH`), dynamically formulated 3 context-derived verification queries without predefined templates, allowed manual analyst query editing with immutable audit logging, submitted Tier-1 candidate with SSRF safety, triaged candidate at Gate 1 (`APPROVED`), computed deterministic proposed reassessment (`PENDING_DECISION`), verified that gap was NOT auto-resolved prior to Gate 2, committed Gate 2 analyst sign-off upgrading requirement to `SUFFICIENT`, and recorded 6 immutable audit trail events.

---

## 3. Test Suite Status

- **Backend Pytest**: **159 tests passed** across all backend test suites (`test_freshness_safety.py`, `test_search_provider_config.py`, `test_contradiction_accuracy.py`, `test_stress_testing_regression.py`, `test_freshness.py`, `test_search_adapter.py`, `test_navigator_orchestration.py`, `test_reports.py`, `test_fragility.py`, `test_sufficiency.py`, `test_stress_testing.py`, `test_conflicts.py`, `test_evidence_graph.py`, `test_contract_compiler.py`, `test_pdf_parser.py`, `test_web_scraper.py`, `test_api.py`).
- **Frontend Vitest**: **55 tests passed** across 9 test suites (`src/test/Temporal.test.tsx`, `Verification.test.tsx`, `Fragility.test.tsx`, `App.test.tsx`, `Report.test.tsx`, `StressTest.test.tsx`, `Sufficiency.test.tsx`, `Conflict.test.tsx`, `EvidenceGraph.test.tsx`).
- **Production Build**: Passed (`tsc -b && vite build` built in 9.00s with 0 errors).
- **Live 20-Step End-to-End Simulation**: **PASS — 20 / 20 steps passed** (`scratch/demonstrate_full_workflow.py`).
- **Decision Stress Testing**: Evaluated with actual investigation contract data; valid outcome shifts computed with explanatory impact narratives (`NOT_EVALUABLE` returned when requirements are missing; `None` prohibited).
- **Contradiction Detection Accuracy**: Enforces entity, proposition, scope, and metric compatibility; 0 false conflicts between unrelated metrics (e.g. 2024 operating margin vs 2026 ownership cap).
- **External Search Reporting**: Explicitly marked `BLOCKED BY CONFIGURATION` when `TAVILY_API_KEY` is absent; manual URL/PDF ingestion fully operational.
- **Source Authenticity & Provenance**: Tracks `source_origin` (`ACTUAL_PUBLIC_SOURCE`, `USER_PROVIDED_DOCUMENT`, `DEMONSTRATION_DOCUMENT`, `SYNTHETIC_TEST_FIXTURE`); demonstration documents transparently labeled.
- **Date Extraction Safety**: Strict multi-candidate validation prevents ingestion or file modification dates from being promoted to publication dates; ambiguous dates flag `Date Requires Review`.

---

## 4. Remaining Tasks (Subsequent Components)

- **Component 11**: Global Command Center Integration.

---

## 5. Run Instructions

### Start Backend API Server
```powershell
cd truthmap-ai
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

### Start Frontend Development Server
```powershell
cd truthmap-ai
npm run dev
```
Frontend runs at `http://localhost:5173`.

### Run Test Suites
```powershell
# Backend (all 113 tests)
cd truthmap-ai
python -m pytest backend/tests -q

# Component 10 Specific Tests (13 tests)
cd truthmap-ai
python -m pytest backend/tests/test_navigator_orchestration.py -v

# Frontend (all 54 tests)
cd truthmap-ai
npm test -- --run

# Production Build
cd truthmap-ai
npm run build
```
