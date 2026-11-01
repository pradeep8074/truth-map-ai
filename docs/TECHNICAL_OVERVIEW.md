# TRUTHMAP AI — Comprehensive Technical Specification

## Component Architecture Breakdown (C01–C10)

### C01: Investigation Intake & Ledger
- **Purpose:** Registers the research question, provisions isolated database contexts, and establishes the audit baseline.
- **Inputs:** Raw decision question string, optional initial URLs.
- **Processing:** Normalizes question text, validates inputs, generates UUIDv4 investigation keys, and records timestamped lifecycle metadata in SQLite.
- **Outputs:** Investigation ID, normalized hypothesis, initialization status.
- **API Endpoints:** `POST /api/investigations`, `GET /api/investigations`, `GET /api/investigations/{id}`.
- **Dependencies:** `sqlite3`, `uuid`, `datetime`.
- **Implementation Status:** **Verified & 100% Functional.**

---

### C02: Multi-Modal Ingestion & Atomic Evidence Extraction
- **Purpose:** Extracts structured text, tabular data, and claims from PDF proposals and regulatory web pages.
- **Inputs:** PDF byte streams, public HTTP/HTTPS URLs.
- **Processing:**
  - PDF: PyMuPDF (`fitz`) character-indexed extraction with page and offset tracking.
  - Web: Trafilatura article extraction with SSRF security filter (blocking private RFC 1918 networks, loopback, and cloud metadata addresses).
  - Provenance: Deterministic SHA-256 hashes generated per text passage.
  - Claim Extraction: Atomic claim deconstruction with extraction method (`deterministic` or `gemini_llm_structured`) and confidence score.
- **Outputs:** Segmented passages with cryptographic hashes, atomic claims ledger.
- **API Endpoints:** `POST /api/investigations/{id}/documents`, `POST /api/investigations/{id}/sources`, `GET /api/investigations/{id}/claims`.
- **Dependencies:** `pymupdf`, `trafilatura`, `beautifulsoup4`, `httpx`, `hashlib`.
- **Implementation Status:** **Verified & 100% Functional.**

---

### C03: Decision Contract Compiler
- **Purpose:** Translates ambiguous business propositions into testable operational criteria.
- **Inputs:** Research question, investigation objective.
- **Processing:** Compiles 6 formal requirements spanning eligibility, cohort size, benefit uptake, counterfactual baseline, causal impact, and displacement risks. Records underlying assumptions.
- **Outputs:** Formal decision requirements ledger, criteria verification rules, assumptions matrix.
- **API Endpoints:** `POST /api/investigations/{id}/contract/compile`, `GET /api/investigations/{id}/contract`.
- **Dependencies:** Google GenAI / Deterministic heuristic fallback engine.
- **Implementation Status:** **Verified & 100% Functional.**

---

### C04: Evidence Dependency Graph
- **Purpose:** Maps multi-tiered topological dependencies between claims, sources, and contractual criteria.
- **Inputs:** Atomic claims, contract requirements, ingested passages.
- **Processing:** Analyzes semantic relevance and evidentiary linkage, computing directed bipartite edges (`RELATES_TO`, `SUPPORTS`, `CONTRADICTS`).
- **Outputs:** Directed graph object (nodes, edges, topological bands).
- **API Endpoints:** `POST /api/investigations/{id}/evidence-graph/analyze`, `GET /api/investigations/{id}/evidence-graph`.
- **Dependencies:** Network graph serializer, SQLite.
- **Implementation Status:** **Verified & 100% Functional.**

---

### C05: Contradiction & Conflict Detection Engine
- **Purpose:** Identifies factual, numerical, and regulatory contradictions between vendor proposals and official ground truth.
- **Inputs:** Linked atomic claims across diverse sources.
- **Processing:** Pairwise cross-examination detecting:
  1. *Numerical Disparities:* Conflicting numbers on identical metrics (e.g. ₹2.08 export credit vs. ₹9.60 tariff).
  2. *Scope / Regulatory Inconsistencies:* Category mismatches (e.g. domestic residential subsidy applied to industrial SME).
- **Outputs:** Classified conflict records (Severity: `CRITICAL`, `HIGH`, `MEDIUM`, `LOW`; Status: `unresolved`).
- **API Endpoints:** `POST /api/investigations/{id}/conflicts/analyze`, `GET /api/investigations/{id}/conflicts`.
- **Dependencies:** Deterministic numerical parser + Gemini semantic validator.
- **Implementation Status:** **Verified & 100% Functional.**

---

### C06: Evidence Sufficiency & Negative-Space Gap Analysis
- **Purpose:** Assesses requirement fulfillment and identifies what evidence *should* exist but is missing.
- **Inputs:** Decision requirements, linked supporting claims, detected conflicts.
- **Processing:** Evaluates coverage status per requirement (`SUFFICIENT`, `PARTIAL`, `INSUFFICIENT`, `CONFLICTING`, `NO_EVIDENCE`). Flags uncorroborated premises as actionable *evidence gaps*.
- **Outputs:** Sufficiency assessment summary, coverage completeness ratio, prioritized evidence gaps queue.
- **API Endpoints:** `POST /api/investigations/{id}/sufficiency/analyze`, `GET /api/investigations/{id}/sufficiency`.
- **Dependencies:** Evidence matrix evaluator, SQLite.
- **Implementation Status:** **Verified & 100% Functional.**

---

### C07: Decision Stress Testing Engine
- **Purpose:** Evaluates how resilient the decision is against counterfactual real-world shocks.
- **Inputs:** Decision contract, validated/unvalidated assumptions, active conflicts.
- **Processing:** Generates 5 counterfactual scenarios (*Risk Materialization*, *Evidence Weakening*, *Missing Evidence Discovery*, *Adverse Conflict Resolution*, *External Condition Shifts*). Simulates shift from baseline robustness to stressed state.
- **Outputs:** Scenario evaluations, outcome shifts (`CRITICAL_FAILURE`, `DEGRADED`, `STABLE`).
- **API Endpoints:** `POST /api/investigations/{id}/stress-tests/generate`, `POST /api/investigations/{id}/stress-tests/{id}/evaluate`.
- **Dependencies:** Scenario evaluator, Gemini / Deterministic stress engine.
- **Implementation Status:** **Verified & 100% Functional.**

---

### C08: Decision Intelligence Report Engine
- **Purpose:** Compiles, versions, and publishes an audit-grade 10-section decision brief.
- **Inputs:** All upstream data from C01 through C07 and C09.
- **Processing:** Assembles structured dossiers, calculates SHA-256 content fingerprint, assigns atomic version numbers, and generates executive conclusions. Includes an instant (<0.1s) fast compilation mode.
- **Outputs:** Published Decision Intelligence Report with cryptographic snapshot seal.
- **API Endpoints:** `POST /api/investigations/{id}/reports/generate`, `GET /api/investigations/{id}/reports`, `GET /api/investigations/{id}/reports/{id}`.
- **Dependencies:** `hashlib`, SQLite atomic version transactions.
- **Implementation Status:** **Verified & 100% Functional.**

---

### C09: Decision Fragility Index (DFI)
- **Purpose:** Computes a transparent, reproducible 0–100 risk score measuring structural decision vulnerability.
- **Inputs:** Sufficiency statuses, contract assumptions, active conflicts, stress test outcomes, source distribution.
- **Formula:**
  $$DFI = 0.30 \cdot D_1 + 0.15 \cdot D_2 + 0.25 \cdot D_3 + 0.20 \cdot D_4 + 0.10 \cdot D_5$$
  - $D_1$ (Coverage Deficit): Weighted requirement gaps.
  - $D_2$ (Assumption Exposure): Unvalidated premise penalties.
  - $D_3$ (Conflict Severity): Unresolved contradictions penalty.
  - $D_4$ (Stress Shift): Vulnerability under simulated failure.
  - $D_5$ (Concentration Risk): Herfindahl index of source distribution.
- **Guardrail Mechanism:** If any CRITICAL requirement is ungrounded (`NO_EVIDENCE` or `CONFLICTING`), the *Critical Deficit Guardrail* trips automatically, preventing premature approval.
- **API Endpoints:** `POST /api/investigations/{id}/fragility/analyze`, `GET /api/investigations/{id}/fragility/latest`.
- **Dependencies:** Deterministic mathematical formulation.
- **Implementation Status:** **Verified & 100% Functional.**

---

### C10: Autonomous Gap Verification Navigator & Update Orchestrator
- **Purpose:** Formulates targeted research queries to close top-priority evidentiary voids and coordinates investigation-wide freshness updates.
- **Inputs:** Prioritized evidence gaps queue from C06.
- **Processing:** Generates dynamic search queries tailored to target missing regulatory documents; checks external search provider configuration.
- **Outputs:** Verification action plans, dynamic queries, candidate URL submission gateway.
- **API Endpoints:** `GET /api/investigations/{id}/navigator/gaps/queue`, `POST /api/investigations/{id}/navigator/gaps/{id}/plan`.
- **Dependencies:** Query generator, Tavily API adapter (reported honestly as `UNAVAILABLE` when key is unconfigured).
- **Implementation Status:** **Verified & Functional (Search Provider Honest Reporting Active).**
