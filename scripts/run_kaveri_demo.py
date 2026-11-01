import os
import sys
import time
import json
import httpx

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_URL = "http://127.0.0.1:8000"

def log_step(step_num: str, title: str, details: str):
    print("\n" + "="*70)
    print(f"COMPONENT {step_num}: {title.upper()}")
    print(f"Details: {details}")
    print("="*70)

def main():
    existing_inv_id = sys.argv[1] if len(sys.argv) > 1 else None
    print(f"Connecting to TRUTHMAP AI Backend at {BASE_URL}...")
    try:
        resp = httpx.get(f"{BASE_URL}/api/health", timeout=5.0)
        resp.raise_for_status()
        print(f"Backend Health: {resp.json()}")
    except Exception as e:
        print(f"FATAL: Backend not reachable at {BASE_URL}. Error: {e}")
        sys.exit(1)

    client = httpx.Client(base_url=BASE_URL, timeout=90.0, follow_redirects=True)

    if existing_inv_id:
        inv_id = existing_inv_id
        print(f"Resuming with Existing Investigation ID: {inv_id}")
    else:
        # -------------------------------------------------------------
        # C01: Create Investigation
        # -------------------------------------------------------------
        log_step("C01", "Create Investigation", "Registering Kaveri Components SME Solar Review")
        inv_payload = {
            "research_question": "Should a fictional Tamil Nadu manufacturing SME approve a ₹48 lakh rooftop solar proposal claiming a five-year payback?",
            "urls": []
        }
        r = client.post("/api/investigations", json=inv_payload)
        if r.status_code != 201:
            print(f"Failed to create investigation: {r.status_code} {r.text}")
            sys.exit(1)
        inv_data = r.json()
        inv_id = inv_data["investigation_id"]
        print(f"Created Investigation ID: {inv_id}")
        print(f"Status: {inv_data.get('status')}")

        # -------------------------------------------------------------
        # C02: Ingest Proposal (Demo Doc) & Real Public Sources
        # -------------------------------------------------------------
        log_step("C02", "Ingest Source Materials", "Uploading vendor proposal (Simulated) and official public sources")
        
        # 1. Ingest Fictional Vendor Proposal PDF
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        proposal_path = os.path.join(root_dir, "data", "demo", "kaveri_solar_proposal.pdf")
        if not os.path.exists(proposal_path):
            proposal_path = os.path.join("data", "demo", "kaveri_solar_proposal.pdf")
        if not os.path.exists(proposal_path):
            print(f"ERROR: {proposal_path} does not exist.")
            sys.exit(1)
        
        with open(proposal_path, "rb") as f:
            pdf_bytes = f.read()
        
        upload_files = [("files", ("kaveri_solar_proposal.pdf", pdf_bytes, "application/pdf"))]
        r = client.post(f"/api/investigations/{inv_id}/documents", files=upload_files)
        if r.status_code != 200:
            print(f"Failed to upload proposal: {r.status_code} {r.text}")
            sys.exit(1)
        prop_sources = r.json()
        prop_source = prop_sources[0] if prop_sources else {}
        print(f"Proposal Ingested: ID={prop_source.get('id')} | Passages={prop_source.get('passages_count')} | Claims={prop_source.get('claims_count')} | Origin={prop_source.get('source_origin', 'DEMONSTRATION_DOCUMENT')}")

        # 2. Ingest Public Sources
        public_urls = [
            "https://www.pmindia.gov.in/en/news_updates/cabinet-approves-pm-surya-ghar-muft-bijli-yojana-for-installing-rooftop-solar-in-one-crore-households/",
            "https://www.pib.gov.in/PressReleasePage.aspx?PRID=2092717&lang=2&reg=48",
            "https://www.tnebltd.gov.in/usrp/faq.xhtml",
            "https://www.tnebltd.gov.in/usrp/Salientfeatures.pdf"
        ]

        for url in public_urls:
            print(f"Ingesting Public Source: {url}...")
            try:
                r = client.post(f"/api/investigations/{inv_id}/sources", json={"urls": [url]}, timeout=60.0)
                if r.status_code == 200:
                    s_list = r.json()
                    s_data = s_list[-1] if s_list else {}
                    print(f"  -> Ingested: {s_data.get('title')} | Published: {s_data.get('publication_date')} | Passages: {s_data.get('passages_count')} | Claims: {s_data.get('claims_count')}")
                else:
                    print(f"  -> HTTP {r.status_code}: {r.text[:120]}")
            except Exception as e:
                print(f"  -> Ingestion warning: {e}")

        # -------------------------------------------------------------
        # C03: Generate Decision Criteria (Contract)
        # -------------------------------------------------------------
        log_step("C03", "Compile Decision Criteria", "Deconstructing hypothesis into explicit Decision Contract")
        r = client.post(f"/api/investigations/{inv_id}/contract/compile")
        if r.status_code != 201:
            print(f"Failed to compile contract: {r.text}")

    # List all claims
    r = client.get(f"/api/investigations/{inv_id}/claims")
    claims = r.json() if r.status_code == 200 else []
    print(f"Total Atomic Claims Extracted across All Sources: {len(claims)}")
    for c in claims[:6]:
        print(f"  - [{c.get('claim_type', 'claim')}] \"{c.get('claim_text')[:100]}...\" (Conf: {c.get('confidence')})")

    r = client.get(f"/api/investigations/{inv_id}/contract")
    contract = r.json()
    print(f"Compiled Objective: {contract.get('decision_objective')}")
    reqs = contract.get("requirements", [])
    print(f"Total Decision Requirements: {len(reqs)}")
    for req in reqs:
        print(f"  - [{req.get('priority')}] {req.get('title')}: {req.get('description')[:90]}...")
    assumptions = contract.get("assumptions", [])
    print(f"Total Contract Assumptions: {len(assumptions)}")
    for a in assumptions[:3]:
        print(f"  - Assumption: {a.get('assumption_text')}")

    # -------------------------------------------------------------
    # C04: Build Complete Evidence Graph
    # -------------------------------------------------------------
    log_step("C04", "Build Evidence Graph", "Mapping topological relationships between Claims & Contract Requirements")
    r = client.post(f"/api/investigations/{inv_id}/evidence-graph/analyze")
    if r.status_code != 200:
        print(f"Failed to analyze graph: {r.text}")
    r = client.get(f"/api/investigations/{inv_id}/evidence-graph")
    graph = r.json()
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    print(f"Evidence Graph Generated: {len(nodes)} Nodes | {len(edges)} Edges")
    rel_edges = [e for e in edges if e.get("type") == "RELATES_TO"]
    print(f"  - Evidence-to-Requirement Relationships: {len(rel_edges)}")

    # -------------------------------------------------------------
    # C05: Identify Conflicting Claims & References
    # -------------------------------------------------------------
    log_step("C05", "Contradiction & Conflict Engine", "Cross-examining proposal claims against official regulations")
    r = client.post(f"/api/investigations/{inv_id}/conflicts/analyze")
    if r.status_code != 200:
        print(f"Failed to analyze conflicts: {r.text}")
    r = client.get(f"/api/investigations/{inv_id}/conflicts")
    conflicts_data = r.json()
    conflict_items = conflicts_data.get("conflicts", [])
    print(f"Total Conflicts Detected: {len(conflict_items)}")
    for cf in conflict_items:
        print(f"  - [{cf.get('severity')}] {cf.get('conflict_type')}:")
        print(f"      Claim A: \"{cf.get('claim_a_text')[:90]}...\"")
        print(f"      Claim B: \"{cf.get('claim_b_text')[:90]}...\"")
        print(f"      Status: {cf.get('resolution_status')}")

    # -------------------------------------------------------------
    # C06: Identify Missing Evidence & Gaps (Sufficiency)
    # -------------------------------------------------------------
    log_step("C06", "Evidence Sufficiency & Gaps", "Checking requirement fulfillment and unverified premises")
    r = client.post(f"/api/investigations/{inv_id}/sufficiency/analyze")
    if r.status_code != 200:
        print(f"Failed to analyze sufficiency: {r.text}")
    r = client.get(f"/api/investigations/{inv_id}/sufficiency")
    suff_data = r.json()
    summary = suff_data.get("summary", {})
    print(f"Sufficiency Summary: Sufficient={summary.get('sufficient_count')} | Partial={summary.get('partial_count')} | Insufficient={summary.get('insufficient_count')} | Conflicting={summary.get('conflicting_count')}")
    gaps = suff_data.get("gaps", [])
    print(f"Identified Actionable Evidence Gaps: {len(gaps)}")
    for g in gaps[:4]:
        print(f"  - [{g.get('priority')}] Gap: {g.get('gap_description')[:80]}...")
        print(f"      Why it matters: {g.get('why_it_matters')[:80]}...")
        print(f"      Evidence needed: {g.get('evidence_needed')[:80]}...")

    # -------------------------------------------------------------
    # Basic Temporal Checks & Freshness Warnings
    # -------------------------------------------------------------
    log_step("Freshness", "Timeline & Freshness Intelligence", "Checking document vintages and staleness thresholds")
    r = client.get(f"/api/investigations/{inv_id}/freshness-summary")
    if r.status_code == 200:
        fresh_data = r.json()
        print(f"Total Sources Audited: {fresh_data.get('total_sources')}")
        print(f"Dated Sources: {fresh_data.get('dated_sources')} | Undated: {fresh_data.get('undated_sources')}")
        print(f"Potentially Outdated (>365d): {fresh_data.get('outdated_sources')} | Requires Review: {fresh_data.get('requires_review_sources')}")

    # -------------------------------------------------------------
    # C07: Decision Stress Tests
    # -------------------------------------------------------------
    log_step("C07", "Decision Stress Testing", "Subjecting decision to counterfactual shocks")
    r = client.post(f"/api/investigations/{inv_id}/stress-tests/generate")
    if r.status_code != 200:
        print(f"Failed to generate stress tests: {r.text}")
    r = client.get(f"/api/investigations/{inv_id}/stress-tests")
    stress_data = r.json()
    scenarios = stress_data.get("scenarios", [])
    print(f"Generated Stress Scenarios: {len(scenarios)}")
    for sc in scenarios:
        # Evaluate scenario
        sc_id = sc.get("id")
        eval_r = client.post(f"/api/investigations/{inv_id}/stress-tests/{sc_id}/evaluate")
        if eval_r.status_code == 200:
            res_sc = eval_r.json()
            print(f"  - Scenario '{res_sc.get('title')}': Baseline={res_sc.get('baseline_overall_outcome')} -> Shifted={res_sc.get('scenario_overall_outcome')} ({res_sc.get('outcome_shift')})")
            print(f"      Impact: {res_sc.get('expected_impact')[:90]}...")

    # -------------------------------------------------------------
    # C09: Calculate & Explain Real Implemented DFI
    # -------------------------------------------------------------
    log_step("C09", "Decision Fragility Index (DFI)", "Computing deterministic 0-100 fragility score across 5 dimensions")
    r = client.post(f"/api/investigations/{inv_id}/fragility/analyze")
    if r.status_code != 200:
        print(f"Failed to calculate DFI: {r.text}")
    r = client.get(f"/api/investigations/{inv_id}/fragility/latest")
    dfi_data = r.json()
    score = dfi_data.get("dfi_score")
    band = dfi_data.get("classification")
    dims = dfi_data.get("dimensions", {})
    print(f"DFI Score: {score} / 100 ({band})")
    print(f"Dimensions Breakdown:")
    print(f"  - D1 (Coverage Deficit)       : {dfi_data.get('d1_coverage')}")
    print(f"  - D2 (Assumption Exposure)    : {dfi_data.get('d2_assumptions')}")
    print(f"  - D3 (Conflict Severity)      : {dfi_data.get('d3_conflicts')}")
    print(f"  - D4 (Stress Test Failure)    : {dfi_data.get('d4_stress')}")
    print(f"  - D5 (Concentration Risk)     : {dfi_data.get('d5_concentration')}")
    print(f"Guardrail Active: {dfi_data.get('guardrail_active')} ({dfi_data.get('guardrail_reason')})")

    # -------------------------------------------------------------
    # C10: Autonomous Verification Navigator
    # -------------------------------------------------------------
    log_step("C10", "Verification Navigator", "Formulating targeted dynamic queries to close evidence gaps")
    r = client.get(f"/api/investigations/{inv_id}/navigator/gaps/queue")
    queue = r.json().get("queue", []) if r.status_code == 200 else []
    print(f"Verification Queue Items: {len(queue)}")
    if queue:
        top_item = queue[0]
        gap_id = top_item.get("gap_id")
        plan_r = client.post(f"/api/investigations/{inv_id}/navigator/gaps/{gap_id}/plan")
        if plan_r.status_code == 200:
            plan = plan_r.json()
            print(f"Formulated Plan for Gap: '{plan.get('requirement_title')}'")
            print(f"  - Verification Objective: {plan.get('verification_objective')}")
            print(f"  - Dynamically Formulated Queries: {plan.get('search_queries')}")
            print(f"  - Search Provider Status: {plan.get('search_provider_status')} (Honest reporting: BLOCKED BY CONFIGURATION if no Tavily API key)")

    # -------------------------------------------------------------
    # C08: Generate Final Investigation Report
    # -------------------------------------------------------------
    log_step("C08", "Decision Intelligence Report", "Synthesizing 10-section audit brief with SHA-256 seal")
    r = client.post(f"/api/investigations/{inv_id}/reports/generate")
    if r.status_code != 200:
        print(f"Failed to generate report: {r.text}")
    r = client.get(f"/api/investigations/{inv_id}/reports")
    reports_data = r.json() if r.status_code == 200 else {}
    reports_list = reports_data.get("reports", [])
    if reports_list:
        rpt = reports_list[0]
        rpt_id = rpt.get("id")
        det_r = client.get(f"/api/investigations/{inv_id}/reports/{rpt_id}")
        det = det_r.json()
        print(f"Report ID: {det.get('id')} | Version: {det.get('report_version')} | Status: {det.get('report_status')}")
        print(f"Snapshot Seal: {det.get('content_snapshot_hash')}")
        print(f"Overall Robustness: {det.get('overall_robustness')}")
        print(f"Executive Verdict:\n  \"{det.get('executive_summary')}\"")

    print("\n" + "="*70)
    print("SUCCESS: KAVERI COMPONENTS DEMONSTRATION WORKFLOW COMPLETED!")
    print(f"Demo Investigation ID: {inv_id}")
    print("="*70)

if __name__ == "__main__":
    main()
