# TRUTHMAP AI — End-to-End System Workflow

This document details the data lifecycle, analytical state transitions, and audit-trail guarantees implemented across TRUTHMAP AI.

---

## 1. End-to-End Sequential Workflow Diagram

```mermaid
sequenceDiagram
    autonumber
    actor Analyst as Decision Analyst
    participant API as FastAPI Backend
    participant Ingest as C02 Ingestion Engine
    participant Contract as C03 Contract Compiler
    participant Graph as C04 Evidence Graph
    participant Forensics as C05 & C06 Forensic Engines
    participant Stress as C07 Stress Engine
    participant Fragility as C09 DFI Calculator
    participant Report as C08 Intelligence Report

    Analyst->>API: 1. Submit Research Question & Document Bundles
    API->>Ingest: Extract PDF text & Scrape Web Sources
    Ingest-->>API: Yield 125 Claims + SHA-256 Hashes
    
    Analyst->>API: 2. Compile Decision Contract
    API->>Contract: Generate 6 Formal Decision Criteria
    Contract-->>API: Persist Requirements & Assumptions Matrix
    
    Analyst->>API: 3. Build Evidence Graph
    API->>Graph: Map Topological Relationships
    Graph-->>API: 292 Nodes, 369 Directed Edges
    
    Analyst->>API: 4. Execute Forensic Analysis
    API->>Forensics: Cross-Examine Claims & Detect Gaps
    Forensics-->>API: 8 Contradictions + 6 Critical Gaps
    
    Analyst->>API: 5. Execute Stress Tests
    API->>Stress: Evaluate 5 Counterfactual Scenarios
    Stress-->>API: Outcome Shifts (Baseline -> Stressed)
    
    Analyst->>API: 6. Calculate Decision Fragility Index
    API->>Fragility: Compute 5-Dimensional Deterministic Score
    Fragility-->>API: DFI: 73.9 / 100.0 (Critical Guardrail Active)
    
    Analyst->>API: 7. Compile Decision Intelligence Dossier
    API->>Report: Synthesize 10-Section Published Dossier
    Report-->>Analyst: Published Report with SHA-256 Seal
```

---

## 2. Forensic Epistemic Lifecycle States

Every piece of data in TRUTHMAP AI transitions through strict epistemic classification boundaries:

```
[Raw Proposal Claim] ──(Ingestion)──> [Unverified Claim Assertion]
                                             │
                       ┌─────────────────────┴─────────────────────┐
                       ▼                                           ▼
             [Statutory Conflict]                          [Supported Evidence]
         (Cross-Examined vs. Policy)                    (Corroborated by Primary Sources)
                       │                                           │
                       └─────────────────────┬─────────────────────┘
                                             ▼
                                 [Requirement Sufficiency]
                       (SUFFICIENT | PARTIAL | INSUFFICIENT | CONFLICTING)
                                             │
                                             ▼
                               [Stress Testing & Fragility]
                                (Counterfactual Degradation)
                                             │
                                             ▼
                                [Executive Decision Dossier]
                              (Cryptographically Sealed v1..vn)
```

---

## 3. Freshness & Invalidation Mechanism

When new evidence is ingested or an existing conflict is resolved:
1. **Cryptographic State Fingerprint:** The engine computes a unified SHA-256 digest across all active claims, contract requirements, conflicts, and sufficiency assessments.
2. **Staleness Flagging:** Any previously compiled report whose stored snapshot hash differs from the current investigation fingerprint is flagged with `is_stale: true`.
3. **Audit Trail Preservation:** Historical versions are never overwritten; recompilation increments the atomic `report_version` (e.g. `v1 -> v2 -> v3`), preserving complete evidentiary lineage.
