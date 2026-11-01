# TRUTHMAP AI — REST API Documentation

TRUTHMAP AI provides a structured, OpenAPI-compliant REST API powered by FastAPI.

**Base URL:** `http://127.0.0.1:8000`  
**Interactive API Docs (Swagger):** `http://127.0.0.1:8000/docs`

---

## 1. System Health & Diagnostics

### `GET /api/health`
Returns the operational status, current platform integrity mode, and active components.

**Response (200 OK):**
```json
{
  "status": "online",
  "platform": "TRUTHMAP AI",
  "component": "Component 10 — Autonomous Gap Verification & Investigation Update Navigator",
  "integrity_mode": "Zero Synthetic Metrics"
}
```

---

## 2. Component C01: Investigation Intake

### `POST /api/investigations`
Creates a new decision investigation ledger.

**Request Body:**
```json
{
  "research_question": "Should a fictional Tamil Nadu manufacturing SME approve a ₹48 lakh rooftop solar proposal claiming a five-year payback?",
  "urls": []
}
```

**Response (201 Created):**
```json
{
  "investigation_id": "de83887a-ca4d-44d0-8e20-21ac863828bd",
  "research_question": "Should a fictional Tamil Nadu manufacturing SME approve a ₹48 lakh rooftop solar proposal claiming a five-year payback?",
  "status": "intake_completed",
  "created_at": "2026-11-01T08:15:00Z"
}
```

### `GET /api/investigations`
Lists all historical investigations stored in the forensic database.

---

## 3. Component C02: Ingestion & Atomic Evidence Extraction

### `POST /api/investigations/{id}/documents`
Uploads local PDF documents (e.g. vendor proposals) for text/table extraction and SHA-256 passage segmentation.

**Request:** `multipart/form-data` with `files` binary attachment.

### `POST /api/investigations/{id}/sources`
Scrapes and parses official web sources with SSRF validation.

**Request Body:**
```json
{
  "urls": [
    "https://www.pmindia.gov.in/en/news_updates/cabinet-approves-pm-surya-ghar-muft-bijli-yojana-for-installing-rooftop-solar-in-one-crore-households/",
    "https://www.tnebltd.gov.in/usrp/faq.xhtml"
  ]
}
```

### `GET /api/investigations/{id}/claims`
Retrieves all atomic claims extracted from ingested sources, including confidence scores and passage hash anchors.

---

## 4. Component C03: Decision Contract Compiler

### `POST /api/investigations/{id}/contract/compile`
Deconstructs the hypothesis into 6 formal criteria with verification standards and evidentiary requirements.

### `GET /api/investigations/{id}/contract`
Returns the compiled Decision Contract, requirements matrix, and recorded assumptions.

---

## 5. Component C04: Evidence Dependency Graph

### `POST /api/investigations/{id}/evidence-graph/analyze`
Builds directed graph edges (`RELATES_TO`, `SUPPORTS`, `CONTRADICTS`) between claims and contract requirements.

### `GET /api/investigations/{id}/evidence-graph`
Returns node and edge collections formatted for visualization.

---

## 6. Component C05: Contradiction & Conflict Engine

### `POST /api/investigations/{id}/conflicts/analyze`
Executes pairwise cross-examination across claims to detect numerical disparities and regulatory scope conflicts.

### `GET /api/investigations/{id}/conflicts`
Returns detected conflict items with Claim A vs. Claim B comparative dossiers.

---

## 7. Component C06: Evidence Sufficiency & Gap Analysis

### `POST /api/investigations/{id}/sufficiency/analyze`
Evaluates requirement coverage across `SUFFICIENT`, `PARTIAL`, `INSUFFICIENT`, `CONFLICTING`, and `NO_EVIDENCE`.

### `GET /api/investigations/{id}/sufficiency`
Returns coverage counts, completeness percentage, and actionable negative-space evidence gaps.

---

## 8. Component C07: Decision Stress Testing

### `POST /api/investigations/{id}/stress-tests/generate`
Formulates 5 counterfactual shock scenarios targeting weak assumptions and critical contradictions.

### `POST /api/investigations/{id}/stress-tests/{scenario_id}/evaluate`
Evaluates decision robustness degradation under the counterfactual scenario.

---

## 9. Component C09: Decision Fragility Index (DFI)

### `POST /api/investigations/{id}/fragility/analyze`
Calculates the deterministic 0–100 DFI score across all 5 dimensions.

### `GET /api/investigations/{id}/fragility/latest`
Returns the latest DFI score, dimension breakdown ($D_1$ to $D_5$), point attribution ledger, and safety guardrail status.

---

## 10. Component C10: Autonomous Gap Verification Navigator

### `GET /api/investigations/{id}/navigator/gaps/queue`
Returns the prioritized queue of unresolved evidence gaps.

### `POST /api/investigations/{id}/navigator/gaps/{gap_id}/plan`
Synthesizes dynamic search queries to address the specific missing evidence requirement.

---

## 11. Component C08: Decision Intelligence Report Engine

### `POST /api/investigations/{id}/reports/generate`
Compiles, versions, and publishes an audit-grade 10-section decision brief.

**Query Parameters:**
- `fast`: `boolean` (optional, default `false`). When set to `true`, uses the instant deterministic engine (<0.1s execution).

### `GET /api/investigations/{id}/reports`
Lists all historical report versions with staleness indicators.

### `GET /api/investigations/{id}/reports/{report_id}`
Returns the full versioned report payload including cryptographic snapshot hash and executive verdict.
