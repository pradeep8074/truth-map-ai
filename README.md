# TRUTHMAP AI

### Evidence-First Autonomous Decision Intelligence & Stress-Testing Platform

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18.0+-61DAFB.svg?logo=react&logoColor=black)](https://reactjs.org/)
[![Vite](https://img.shields.io/badge/Vite-6.0+-646CFF.svg?logo=vite&logoColor=white)](https://vitejs.dev/)
[![SQLite](https://img.shields.io/badge/SQLite3-WAL_Mode-003B57.svg?logo=sqlite&logoColor=white)](https://sqlite.org/)
[![Python Tests](https://img.shields.io/badge/Pytest-159_Passed-brightgreen.svg?logo=pytest&logoColor=white)](https://docs.pytest.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

> ### *"Traditional AI tools summarize available information.*  
> ### *TRUTHMAP AI investigates what is missing, conflicting, outdated, and still needs verification."*

---

## 1. Executive Summary & Value Proposition

In high-stakes enterprise, regulatory, and public-policy decisions, standard generative AI tools create a dangerous illusion of certainty. They passively summarize uploaded documents, assume vendor assertions are truthful, hallucinate bridging premises, and obscure life-or-death evidence omissions.

**TRUTHMAP AI** flips the paradigm. It is an **Evidence-First Decision Intelligence Platform** designed to audit proposals, cross-examine assertions against official ground-truth regulations, expose *negative-space evidence gaps*, and stress-test strategic choices before capital is committed.

Every metric, node, conflict, and score in TRUTHMAP AI is **100% computed from deterministic mathematical formulations and cryptographic SHA-256 passage coordinates**. It operates under a strict **Zero Synthetic Metrics** standard: no invented confidence numbers, no hallucinated citations, and no ungrounded dashboard metrics.

---

## 2. Key Problem Statement vs. Solution

| Challenge in Traditional AI Decision Support | TRUTHMAP AI Solution |
|---|---|
| **Passive Acceptance:** LLMs summarize vendor claims as if they were established facts. | **Adversarial Cross-Examination:** Every claim is treated as an unverified assertion until corroborated by independent primary sources. |
| **Silent Omissions:** Summaries hide missing documentation (structural audits, CEIG approvals). | **Negative-Space Modeling:** Explicitly maps what evidence *should* exist and flags critical voids as actionable gaps. |
| **Contradiction Blindness:** Generative models smooth over conflicting numbers across sources. | **Automated Contradiction Engine:** Pairwise cross-examination flags numerical disparities and regulatory scope mismatches. |
| **Black-Box Confidence:** Proprietary 0-100% AI "confidence" scores with zero auditability. | **Deterministic Decision Fragility Index (DFI):** Transparent 5-dimensional mathematical formula ($D_1$ to $D_5$) with safety guardrails. |
| **Static Snapshots:** Analyses become obsolete when regulations or tariffs change. | **Cryptographic Fingerprinting & Staleness Alerts:** Automated SHA-256 state tracking with update orchestration. |

---

## 3. System Architecture

```mermaid
flowchart TD
    subgraph INTAKE["1. Ingestion & Provenance"]
        DOCS["PDF Proposals / Vendor Docs"] --> C02["C02: Multi-Modal Ingestion Engine"]
        WEB["Official Regulatory Web Sources"] --> C02
        C02 --> HASH["Deterministic SHA-256 Passage Hashes"]
        HASH --> EXTRACT["Atomic Claim Extractor"]
        EXTRACT --> CLAIMS[("Atomic Claims Ledger")]
    end

    subgraph CONTRACT["2. Criteria Compilation"]
        RQ["Decision Question / Hypothesis"] --> C01["C01: Intake Ledger"]
        C01 --> C03["C03: Decision Contract Compiler"]
        C03 --> CRITERIA["6 Operational Requirements"]
        C03 --> ASSUMPTIONS["Contract Assumptions"]
    end

    subgraph GRAPH["3. Topological Mapping"]
        CLAIMS --> C04["C04: Evidence Dependency Graph"]
        CRITERIA --> C04
        C04 --> TOPOMAP[("Directed Bipartite Graph (292 Nodes, 369 Edges)")]
    end

    subgraph FORENSICS["4. Forensic Contradiction & Gap Engine"]
        TOPOMAP --> C05["C05: Contradiction Engine"]
        TOPOMAP --> C06["C06: Sufficiency & Gaps Engine"]
        C05 --> CONFLICTS[("8 Factual/Numerical Contradictions")]
        C06 --> GAPS[("Actionable Negative-Space Evidence Gaps")]
    end

    subgraph RESILIENCE["5. Stress Testing & Fragility Index"]
        CRITERIA --> C07["C07: Stress Testing Engine"]
        CONFLICTS --> C07
        GAPS --> C07
        C07 --> STRESS_SHIFTS["Counterfactual Scenarios (Baseline -> Stressed)"]
        
        CONFLICTS --> C09["C09: Decision Fragility Index (DFI)"]
        GAPS --> C09
        STRESS_SHIFTS --> C09
        C09 --> DFI_SCORE["DFI: 73.9 / 100.0 (Critical Deficit Guardrail Active)"]
    end

    subgraph SYNTHESIS["6. Audit Dossier & Navigator"]
        DFI_SCORE --> C08["C08: Decision Intelligence Report Engine"]
        STRESS_SHIFTS --> C08
        CONFLICTS --> C08
        GAPS --> C08
        C08 --> SEAL["Cryptographic Snapshot Hash Seal"]
        C08 --> DOSSIER["10-Section Published Audit Dossier (<0.1s Fast Mode)"]
        
        GAPS --> C10["C10: Verification Navigator"]
        C10 --> TARGET_PLANS["Dynamic Target Audit Queries"]
        C10 --> ORCHESTRATE["Continuous Investigation Freshness Updates"]
    end
```

---

## 4. The 10 Core Platform Components (C01–C10)

| ID | Component Name | Operational Purpose |
|:---:|---|---|
| **C01** | **Investigation Intake** | Registers decision hypotheses, provisions isolated forensic contexts, and tracks audit lifecycles. |
| **C02** | **Multi-Modal Ingestion** | Ingests PDF proposals and regulatory web pages; generates SHA-256 passage hashes; extracts atomic claims with strict SSRF defense. |
| **C03** | **Decision Contract Compiler** | Deconstructs ambiguous business proposals into 6 testable formal criteria with verification rules and recorded assumptions. |
| **C04** | **Evidence Dependency Graph** | Builds an interactive directed bipartite graph mapping topological relationships between sources, passages, claims, and criteria. |
| **C05** | **Contradiction & Conflict Engine** | Cross-examines assertions across sources to flag numerical disparities and regulatory scope mismatches (e.g. residential subsidy claimed for industrial plant). |
| **C06** | **Sufficiency & Gap Analysis** | Assesses requirement fulfillment (`SUFFICIENT`, `PARTIAL`, `INSUFFICIENT`, `CONFLICTING`, `NO_EVIDENCE`) and models negative-space evidence gaps. |
| **C07** | **Decision Stress Testing** | Subjects proposals to 5 counterfactual shocks (*Risk Materialization*, *Evidence Weakening*, *Adverse Contradiction Resolution*, etc.) and evaluates outcome shifts. |
| **C08** | **Decision Intelligence Report** | Synthesizes a 10-section published audit brief with cryptographic state seals and instant (<0.1s) fast compilation. |
| **C09** | **Decision Fragility Index (DFI)** | Computes a deterministic 0–100 fragility score across 5 weighted dimensions with safety guardrails against premature approval. |
| **C10** | **Verification Navigator** | Prioritizes unresolved evidence voids, formulates targeted dynamic search queries, and orchestrates live analysis updates. |

---

## 5. Live Demonstration Scenario: Kaveri Components Solar Review

**Decision Question:** *"Should a fictional Tamil Nadu manufacturing SME approve a ₹48 lakh rooftop solar proposal claiming a five-year payback?"*  
**Verified Investigation ID:** `de83887a-ca4d-44d0-8e20-21ac863828bd`

### The Scenario:
Kaveri Components Pvt. Ltd., an industrial manufacturing SME in Coimbatore, received an unsolicited EPC vendor proposal claiming a 100 kW captive rooftop solar installation costing ₹48,00,000 would achieve full payback in 5.0 years.

```
Proposal Document: data/demo/kaveri_solar_proposal.pdf (WATERMARKED: SIMULATED DEMONSTRATION DOCUMENT)
Ingested Official Ground Truth:
1. https://www.pmindia.gov.in/en/news_updates/cabinet-approves-pm-surya-ghar-muft-bijli-yojana-for-installing-rooftop-solar-in-one-crore-households/
2. https://www.pib.gov.in/PressReleasePage.aspx?PRID=2092717&lang=2&reg=48
3. https://www.tnebltd.gov.in/usrp/faq.xhtml
4. https://www.tnebltd.gov.in/usrp/Salientfeatures.pdf
```

### Forensic Findings Discovered by TRUTHMAP AI:
1. **Critical Subsidy Mismatch:** Vendor claimed ₹78,000 subsidy under *PM Surya Ghar: Muft Bijli Yojana*. Official Cabinet and PIB releases prove the scheme applies strictly to 1–3 kW domestic residential households. Industrial SMEs are 100% ineligible.
2. **Export Credit Disparity:** Vendor assumed surplus electricity exports receive ₹2.08/kWh net metering compensation against a ₹9.60/year savings model. Official TNEB/USRP regulations cap feed-in rates and impose HT transformer limitations.
3. **Statutory Inspection Violation:** Vendor claimed CEIG (Chief Electrical Inspector to Government) safety inspection is "Not required". TNEB statutory rules mandate CEIG safety certification for all rooftop solar systems above 10 kW.
4. **Computed Decision Fragility:**
   - **DFI Score: 73.9 / 100.0** (`CRITICAL DEFICIT GUARDRAIL: UNGROUNDED FOUNDATION`).
   - Guardrail triggered due to ungrounded causal impact and unresolved statutory conflicts.
5. **Executive Audit Verdict:** **Reject or defer proposal** until commercial tariff sanctions, structural load engineering, and CEIG approvals are procured.

---

## 6. Prototype Screenshot Gallery

All screenshots below are captured directly from the live application during execution of the Kaveri Components investigation:

### 1. Investigation Intake & Multi-Modal Setup (Component C01 & C02)
![Investigation Intake](screenshots/01-investigation-intake.png)
*Setup interface: Normalizes decision hypothesis, ingests PDF proposals and live public URLs with SSRF validation.*

---

### 2. Decision Criteria & Contract Matrix (Component C03)
![Decision Criteria](screenshots/02-decision-criteria.png)
*Deconstructs the hypothesis into 6 formal criteria: Eligibility, Target Population, Benefit Uptake, Counterfactual Baseline, Causal Attribution, and Displacement Risk.*

---

### 3. Evidence Explorer & Atomic Claims Ledger (Component C02)
![Evidence Explorer](screenshots/03-evidence-explorer.png)
*Atomic claims extracted with cryptographic passage hash anchors, confidence scores, and SIMULATED DEMONSTRATION DOCUMENT provenance tags.*

---

### 4. Interactive Evidence Dependency Graph (Component C04)
![Evidence Map](screenshots/04-evidence-graph.png)
*Directed bipartite graph mapping 292 Nodes and 369 Edges across topological bands from Contract Objective down to Source Passages.*

---

### 5. Contradiction & Conflict Detection Engine (Component C05)
![Conflicting Evidence](screenshots/05-conflict-detection.png)
*Automated pairwise cross-examination flagging 8 numerical disparities and regulatory scope conflicts between proposal assertions and official policy.*

---

### 6. Evidence Coverage & Negative-Space Gap Analysis (Component C06)
![Evidence Coverage](screenshots/06-evidence-coverage.png)
*Requirement fulfillment matrix revealing 25% coverage completeness and identifying 6 actionable negative-space evidence gaps.*

---

### 7. Counterfactual Decision Stress Testing (Component C07)
![Test Your Decision](screenshots/07-decision-stress-testing.png)
*Simulating real-world shocks (Subsidy Retraction, Industrial Curtailment, Adverse Tariff Orders), shifting baseline robustness to CRITICAL_FAILURE.*

---

### 8. Deterministic Decision Fragility Index — DFI (Component C09)
![Decision Fragility Index](screenshots/08-decision-fragility-index.png)
*Deterministic 0–100 fragility formulation (DFI: 73.9). Demonstrates active Critical Deficit Guardrail preventing premature capital commitment.*

---

### 9. Autonomous Verification Navigator & Update Orchestrator (Component C10)
![Verification Navigator](screenshots/09-verification-navigator.png)
*Prioritizes negative-space voids and synthesizes dynamic audit queries. Demonstrates honest external provider reporting (UNAVAILABLE).*

---

### 10. Scenario Specification Reference Table
![Scenario Specification Table](screenshots/10-scenario-specification-table.png)
*Formal vendor proposal parameters and verification criteria governing the live demonstration scenario.*

---

## 7. Technology Stack

- **Backend:** Python 3.11 / 3.14, FastAPI, Uvicorn (ASGI)
- **Database:** SQLite 3 (WAL Mode, Foreign Key Cascades, In-Memory Test Isolation)
- **Document Processing:** PyMuPDF (`fitz`), Trafilatura, BeautifulSoup4
- **AI & Reasoning:** Google GenAI SDK (Gemini 2.0 Flash) + Deterministic Rule Engine
- **Frontend:** React 18, Vite, TypeScript, Tailwind CSS, Lucide React
- **Testing & Security:** Pytest, Pytest-Asyncio, HTTPX, Cryptographic SHA-256

---

## 8. Installation & Quick Start

### Option A: One-Click Windows Launcher (Easiest)
Simply double-click **`start_all.bat`** in the project root:
```cmd
start_all.bat
```
*This automatically launches the FastAPI backend (port 8000), Vite frontend (port 5173), and opens your default browser to [http://localhost:5173](http://localhost:5173).*

---

### Option B: One-Click GitHub Upload
To upload this repository directly to your personal or organization GitHub account in seconds:
```cmd
upload_to_github.bat
```
*(On Linux/macOS: `./upload_to_github.sh`)*
*The script automatically verifies git status, stages code cleanly (safely ignoring `.env` and local `.db` files), prompts for your GitHub repo URL, and pushes the `main` branch.*

---

### Option C: Manual Multi-Terminal Setup

#### Prerequisites
- Python 3.11+
- Node.js 18.0+

#### Terminal 1: Backend Setup & API Server
```bash
# Set up virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: .\venv\Scripts\Activate.ps1

# Install Python requirements
pip install -r requirements.txt

# Start FastAPI backend
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```
*Backend API available at: [http://127.0.0.1:8000](http://127.0.0.1:8000) (Docs: [/docs](http://127.0.0.1:8000/docs))*

#### Terminal 2: Frontend Setup & Dev Server
```bash
# Navigate to frontend
cd frontend

# Install dependencies & start
npm install
npm run dev
```
*Frontend UI available at: [http://localhost:5173](http://localhost:5173)*

---

### Option D: Docker Compose Deployment
```bash
# Build and run both backend & frontend
docker compose up --build
```
*Frontend accessible at [http://localhost:5173](http://localhost:5173) and Backend at [http://localhost:8000](http://localhost:8000).*

---

### Automated Verification & Benchmark Testing
```bash
# 1. Run Backend Pytest Suite (159 tests)
python -m pytest backend/tests/ -q

# 2. Run Frontend Vitest Suite (55 tests)
cd frontend && npm test

# 3. Run Kaveri Demo CLI Workflow (C01–C10)
python scripts/run_kaveri_demo.py

# 4. Run System Performance & Latency Benchmark
python scripts/benchmark_performance.py
```

---

## 9. Current Limitations & Honest Disclosure

In accordance with our platform honesty rules:
1. **Autonomous Web Search Provider:** External search via Tavily API is currently **UNAVAILABLE / BLOCKED BY CONFIGURATION** because no external search key is configured by default. The system honestly reports `UNAVAILABLE` and provides a manual URL submission gateway rather than faking search results.
2. **Gemini API Quota Failover:** When free-tier daily rate limits (500 req/day) are reached, the system engages an immediate circuit breaker and falls back to its deterministic local rule engine without crashing or delaying.
3. **Local PDF Execution:** Static analysis extracts and verifies text and tabular data without executing active code inside PDF documents.

---

## 10. Repository Structure

```text
truthmap-ai/
├── README.md                          # Master documentation & screenshot showcase
├── LICENSE                            # MIT Open-Source License
├── CONTRIBUTING.md                    # Contributor guide & honesty guidelines
├── SECURITY.md                        # SSRF defense & security architecture
├── requirements.txt                   # Tested Python dependencies
├── package.json                       # Frontend dependencies & scripts
├── vite.config.ts                     # Vite bundler configuration
│
├── backend/                           # FastAPI backend application
│   ├── config.py                      # SSRF filters & system configuration
│   ├── database.py                    # SQLite schema & migration ledger
│   ├── main.py                        # FastAPI application instance & routing
│   ├── models.py                      # Pydantic v2 schemas across C01–C10
│   ├── routers/                       # REST endpoint routers
│   ├── services/                      # C01–C10 core analytical engines
│   └── tests/                         # 159 automated unit & integration tests
│
├── src/                               # React 18 frontend application
│   ├── components/                    # Modular UI components & design system
│   ├── pages/                         # C01–C10 interactive studios & views
│   └── lib/api.ts                     # Typed REST API client & error handling
│
├── docs/                              # In-depth architectural & operational guides
│   ├── ARCHITECTURE.md                # System architecture & Mermaid blueprints
│   ├── INSTALLATION.md                # Multi-platform installation guide
│   ├── API_DOCUMENTATION.md           # Complete REST API reference
│   ├── DEMO_RUNBOOK.md                # Click-by-click demonstration script
│   ├── SYSTEM_WORKFLOW.md             # Sequential workflow & data lifecycle
│   └── TECHNICAL_OVERVIEW.md          # Technical specifications for C01–C10
│
├── screenshots/                       # Verified prototype screenshots
│   ├── 01-investigation-intake.png
│   ├── 02-decision-criteria.png
│   ├── 03-evidence-explorer.png
│   ├── 04-evidence-graph.png
│   ├── 05-conflict-detection.png
│   ├── 06-evidence-coverage.png
│   ├── 07-decision-stress-testing.png
│   ├── 08-decision-fragility-index.png
│   ├── 09-verification-navigator.png
│   └── 10-scenario-specification-table.png
│
├── data/
│   └── demo/
│       └── kaveri_solar_proposal.pdf  # Simulated demonstration proposal document
│
└── scratch/
    └── run_kaveri_demo.py             # Reproducible CLI demonstration runner
```

---

## 11. Contributors & License

- **Project:** TRUTHMAP AI
- **License:** Released under the [MIT License](LICENSE).
- **Core Mission:** Advancing trustworthy, verifiable, and stress-tested decision intelligence.
