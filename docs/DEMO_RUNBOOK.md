# TRUTHMAP AI — Demonstration Runbook

**Scenario:** *Kaveri Components Pvt. Ltd. — 100 kW Rooftop Solar Investment Review*  
**Decision Question:** *"Should a fictional Tamil Nadu manufacturing SME approve a ₹48 lakh rooftop solar proposal claiming a five-year payback?"*  
**Verified Investigation ID:** `de83887a-ca4d-44d0-8e20-21ac863828bd`

---

## 1. Scenario Summary & Integrity Rules

- **Simulated Vendor Document:** An EPC vendor proposal for a 100 kW rooftop solar plant at an SME factory in Coimbatore, TN.
- **Data Integrity Rule:** The vendor proposal is watermarked `SIMULATED DEMONSTRATION DOCUMENT`. Proposal claims are treated strictly as unverified assertions, not established facts.
- **Official Public Sources:** Official guidelines from PMO India, PIB, and TANGEDCO/TNEB are ingested to ground the analysis in verifiable regulatory truth.

---

## 2. Ingested Evidence Materials

### Simulated Demonstration Document
- **Location:** [`data/demo/kaveri_solar_proposal.pdf`](file:///C:/Users/PRADEEP/Downloads/truthmap-ai/data/demo/kaveri_solar_proposal.pdf)
- **Key Claims:**
  - Capital Outlay: ₹48,00,000 for 100 kW system
  - Generation: 150,000 kWh/year
  - Tariff Savings: ₹9,60,000/year (5-year payback)
  - Subsidy Claim: ₹78,000 under PM Surya Ghar Muft Bijli Yojana
  - Net Metering Export Credit: ₹2.08/kWh
  - Statutory Safety: CEIG approval claimed "Not required"
  - Performance: 25-year panel warranty

### Authoritative Public Ground Truth Sources
1. `https://www.pmindia.gov.in/en/news_updates/cabinet-approves-pm-surya-ghar-muft-bijli-yojana-for-installing-rooftop-solar-in-one-crore-households/`  
   *(Proves PM Surya Ghar subsidy is strictly for 1–3 kW domestic residential households)*
2. `https://www.pib.gov.in/PressReleasePage.aspx?PRID=2092717&lang=2&reg=48`  
   *(Provides official central financial assistance tiers and residential limits)*
3. `https://www.tnebltd.gov.in/usrp/faq.xhtml`  
   *(TANGEDCO rules for LT/HT solar grid interconnection and billing)*
4. `https://www.tnebltd.gov.in/usrp/Salientfeatures.pdf`  
   *(Mandatory CEIG safety inspection orders for installations >10 kW)*

---

## 3. Option A: Automated CLI Execution (< 10 seconds)

To run the complete end-to-end demonstration workflow programmatically:

```bash
python scratch/run_kaveri_demo.py de83887a-ca4d-44d0-8e20-21ac863828bd
```

### Observed Output Summary:
```text
======================================================================
COMPONENT C01-C03: INTAKE, INGESTION & CONTRACT COMPILATION
======================================================================
Total Atomic Claims Extracted: 125
Compiled Decision Objective: Determine whether a fictional Tamil Nadu manufacturing SME approve a ₹48 lakh rooftop solar proposal...
Total Decision Requirements: 6

======================================================================
COMPONENT C04: EVIDENCE GRAPH
======================================================================
Evidence Graph Generated: 292 Nodes | 369 Edges

======================================================================
COMPONENT C05: CONTRADICTION & CONFLICT ENGINE
======================================================================
Total Conflicts Detected: 8
  - [CRITICAL] NUMERICAL_CONFLICT: Subsidy eligibility (PM Surya Ghar 1-3 kW residential vs 100 kW industrial SME)
  - [CRITICAL] NUMERICAL_CONFLICT: Export credit rate (₹2.08/kWh feed-in vs ₹9.60 industrial tariff assumptions)

======================================================================
COMPONENT C06: EVIDENCE SUFFICIENCY & GAPS
======================================================================
Sufficiency Summary: Sufficient=0 | Partial=3 | Insufficient=1 | Conflicting=2
Identified Actionable Evidence Gaps: 6

======================================================================
COMPONENT C07: DECISION STRESS TESTING
======================================================================
Generated Stress Scenarios: 5
Outcome Shift: Baseline=HIGHLY_VULNERABLE -> Shifted=HIGHLY_VULNERABLE (CRITICAL_FAILURE)

======================================================================
COMPONENT C09: DECISION FRAGILITY INDEX (DFI)
======================================================================
DFI Score: 73.9 / 100.0 (High Fragility)
Guardrail Active: CRITICAL DEFICIT GUARDRAIL: UNGROUNDED FOUNDATION

======================================================================
COMPONENT C10: VERIFICATION NAVIGATOR
======================================================================
Verification Queue Items: 6
Search Provider Status: UNAVAILABLE (Honest reporting: BLOCKED BY CONFIGURATION)
Dynamic Queries Formulated: 4 targeted audit queries generated

======================================================================
COMPONENT C08: DECISION INTELLIGENCE REPORT
======================================================================
Report ID: rpt-7645f254d72c | Version: 2 | Status: published
Overall Robustness: HIGHLY_VULNERABLE
Executive Verdict:
  "The proposed ₹48 lakh rooftop solar investment is currently unviable for approval due to a 'HIGHLY_VULNERABLE' robustness rating... The financial justification is compromised by severe numerical conflicts regarding subsidy rates and electricity tariffs..."
======================================================================
```

---

## 4. Option B: Step-by-Step Web UI Walkthrough

1. Open **`http://127.0.0.1:5173`** in your browser.
2. Select the investigation **"Should a fictional Tamil Nadu manufacturing SME approve a ₹48 lakh rooftop solar proposal..."** from the top dropdown.
3. **Evidence Explorer:** Note the 125 atomic claims tagged as `SIMULATED DEMONSTRATION DOCUMENT`.
4. **Decision Criteria:** Review the 6 formal requirements, from eligibility to causal impact.
5. **Evidence Map:** View the 292 nodes and 369 edges showing topological dependencies.
6. **Conflicting Evidence:** Review the 8 flagged contradictions, notably the residential PM Surya Ghar mismatch.
7. **Evidence Coverage:** Observe the 25% coverage completeness and 6 identified negative-space gaps.
8. **Test Your Decision:** Review the 5 counterfactual stress scenarios and the resulting `CRITICAL_FAILURE` shifts.
9. **Decision Risk Score:** Inspect the **DFI 73.9** score and the triggered *Critical Deficit Guardrail*.
10. **Find Missing Evidence:** View the dynamic query plans and honest provider status (`UNAVAILABLE`).
11. **Investigation Reports:** Click **`Fast Compile (<0.1s)`** to review the published audit dossier and executive verdict.
