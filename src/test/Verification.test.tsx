import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { VerificationPage } from "../pages/VerificationPage";
import * as api from "../lib/api";

// Mock API functions
vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof api>("../lib/api");
  return {
    ...actual,
    listInvestigations: vi.fn(),
    getNavigatorQueue: vi.fn(),
    generateVerificationPlan: vi.fn(),
    submitManualCandidate: vi.fn(),
    reviewCandidateSource: vi.fn(),
    evaluateGap: vi.fn(),
    commitGapReassessment: vi.fn(),
    getSourceImpactSummary: vi.fn(),
    getNavigatorAuditTrail: vi.fn(),
  };
});

describe("Component 10: Autonomous Gap Verification & Investigation Update Navigator", () => {
  const mockInvestigations: api.Investigation[] = [
    {
      id: "inv-nav-001",
      research_question: "Verify subsidiary compliance and financial resilience",
      status: "active",
      created_at: "2026-10-31T00:00:00Z",
      sources_count: 2,
      claims_count: 5,
    },
  ];

  const mockQueueResponse: api.NavigatorQueueResponse = {
    investigation_id: "inv-nav-001",
    total_gaps: 2,
    search_provider: "none",
    search_provider_active: false,
    queue: [
      {
        gap_id: "gap-001",
        requirement_id: "req-001",
        requirement_title: "Subsidiary Solvency & Tier-1 Capital",
        priority: "CRITICAL",
        gap_description: "Missing audited Tier-1 capital ratio",
        why_it_matters: "Statutory capitalization boundary",
        evidence_needed: "Regulatory filing with certified capital ratio",
        suggested_source_type: "Regulatory Filing",
        current_coverage_status: "NO_EVIDENCE",
        projected_dfi_reduction: 14.5,
        verification_state: "UNVERIFIED",
        has_active_plan: false,
        active_plan_id: undefined,
      },
      {
        gap_id: "gap-002",
        requirement_id: "req-002",
        requirement_title: "ISO Environmental Audit",
        priority: "HIGH",
        gap_description: "Unverified environmental permit compliance",
        why_it_matters: "Regulatory operation licensing",
        evidence_needed: "ISO 14001 certificate",
        suggested_source_type: "Audit Certificate",
        current_coverage_status: "NO_EVIDENCE",
        projected_dfi_reduction: 8.0,
        verification_state: "IN_PROGRESS",
        has_active_plan: true,
        active_plan_id: "plan-002",
      },
    ],
  };

  const mockPlan: api.GapVerificationPlan = {
    id: "plan-001",
    investigation_id: "inv-nav-001",
    gap_id: "gap-001",
    requirement_id: "req-001",
    verification_objective: "Obtain verified empirical evidence for Subsidiary Solvency",
    required_evidence_type: "Regulatory Filing",
    target_authority_tier: "TIER_1",
    search_queries: [
      "Subsidiary Solvency Tier-1 capital ratio audited metric",
      "Subsidiary Solvency capital adequacy ratio regulatory report",
    ],
    search_provider_status: "UNAVAILABLE",
    status: "ACTIVE",
    candidates: [
      {
        id: "cand-001",
        plan_id: "plan-001",
        investigation_id: "inv-nav-001",
        url: "https://sec.gov/filings/subsidiary_10k.pdf",
        domain: "sec.gov",
        title: "SEC 10-K Subsidiary Annual Report",
        snippet: "Audited Tier-1 capital adequacy ratio verified at 13.4%.",
        authority_tier: "TIER_1",
        relevance_score: 85.0,
        discovery_mode: "MANUAL_ENTRY",
        relevance_rationale: "Matched regulatory domain and 4 key terms.",
        review_status: "PENDING_REVIEW",
        rejection_reason: undefined,
        discovered_at: "2026-10-31T01:00:00Z",
      },
    ],
    created_at: "2026-10-31T01:00:00Z",
  };

  const mockImpactSummary: api.SourceImpactSummary = {
    orchestration_run_id: "run-001",
    investigation_id: "inv-nav-001",
    source_id: "src-001",
    source_title: "SEC 10-K Filing 2026",
    source_url_or_filename: "https://sec.gov/filings/subsidiary_10k.pdf",
    authority_tier: "TIER_1",
    is_duplicate: false,
    total_claims_extracted: 3,
    claims_by_category: { statistical: 2, factual: 1 },
    extracted_claim_previews: [
      { claim_id: "c-001", text: "Tier-1 capital ratio is 13.4%", category: "statistical" },
    ],
    affected_requirements: [
      { requirement_id: "req-001", requirement_title: "Tier-1 Capital", priority: "CRITICAL", matched_claims_count: 2 },
    ],
    affected_assumptions: [],
    new_conflicts_detected: [],
    conflicts_resolved_count: 0,
    gaps_resolved: ["gap-001"],
    gaps_reduced: [],
    gaps_unchanged: [],
    gaps_worsened: [],
    baseline_outcome_shifted: false,
    old_baseline_outcome: "MODERATE",
    new_baseline_outcome: "ROBUST",
    old_dfi_score: 35.0,
    new_dfi_score: 21.0,
    delta_dfi: -14.0,
    old_classification: "MODERATE FRAGILITY",
    new_classification: "LOW FRAGILITY",
    guardrail_status_changed: false,
    report_invalidated: true,
    unresolved_items_remaining: 1,
    pending_analyst_actions: [
      "Review and confirm 1 proposed gap resolution(s) in Navigator.",
      "Re-generate published decision intelligence report to reflect updated evidence.",
    ],
    stages_execution: {
      STAGE_0_INGESTION: { status: "COMPLETED", duration_ms: 120 },
      STAGE_1_GRAPH_TOPOLOGY: { status: "COMPLETED", duration_ms: 85 },
      STAGE_2_CONTRADICTIONS: { status: "COMPLETED", duration_ms: 95 },
      STAGE_3_ASSUMPTIONS: { status: "NOT_AFFECTED", skipped_reason: "No assumption relationships identified", duration_ms: 10 },
      STAGE_4_SUFFICIENCY: { status: "COMPLETED", duration_ms: 110 },
      STAGE_5_STRESS_TESTS: { status: "NOT_RUN", skipped_reason: "No active stress scenarios affected", duration_ms: 5 },
      STAGE_6_DFI_RESCORE: { status: "COMPLETED", duration_ms: 150 },
      STAGE_7_REPORT_INVALIDATION: { status: "COMPLETED", duration_ms: 25 },
    },
    executive_impact_narrative: "Source SEC 10-K Filing 2026 integrated. Extracted 3 claims. DFI reduced by 14.0 pts.",
    processing_mode: "fallback",
    created_at: "2026-10-31T01:30:00Z",
  };

  const mockAuditLogs: api.OrchestrationAuditLogItem[] = [
    {
      id: "audit-001",
      investigation_id: "inv-nav-001",
      event_type: "CANDIDATE_SUBMITTED",
      actor: "analyst",
      details: { url: "https://sec.gov/filings/subsidiary_10k.pdf", discovery_mode: "MANUAL_ENTRY" },
      created_at: "2026-10-31T01:00:00Z",
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.listInvestigations).mockResolvedValue(mockInvestigations);
    vi.mocked(api.getNavigatorQueue).mockResolvedValue(mockQueueResponse);
    vi.mocked(api.generateVerificationPlan).mockResolvedValue(mockPlan);
    vi.mocked(api.getSourceImpactSummary).mockResolvedValue(mockImpactSummary);
    vi.mocked(api.getNavigatorAuditTrail).mockResolvedValue(mockAuditLogs);

    // Mock global fetch for sources list
    globalThis.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes("/sources")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve([{ id: "src-001", title: "SEC 10-K Filing 2026" }]),
        });
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({}),
      });
    }) as any;
  });

  it("renders Navigator page header and Gap Verification Queue (Workflow A)", async () => {
    render(
      <MemoryRouter initialEntries={["/verification-navigator?investigation_id=inv-nav-001"]}>
        <VerificationPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText("Verification Navigator & Update Orchestrator")).toBeInTheDocument();
    });

    await waitFor(() => {
      expect(screen.getAllByText("Subsidiary Solvency & Tier-1 Capital").length).toBeGreaterThan(0);
    });

    expect(screen.getByText("CRITICAL")).toBeInTheDocument();
    expect(screen.getByText("-14.5 DFI")).toBeInTheDocument();
    expect(screen.getByText("ISO Environmental Audit")).toBeInTheDocument();
  });

  it("generates a targeted verification plan upon clicking Formulate Plan", async () => {
    render(
      <MemoryRouter initialEntries={["/verification-navigator?investigation_id=inv-nav-001"]}>
        <VerificationPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getAllByText("Subsidiary Solvency & Tier-1 Capital").length).toBeGreaterThan(0);
    });

    const planBtn = screen.getByText("Formulate Plan");
    fireEvent.click(planBtn);

    await waitFor(() => {
      expect(api.generateVerificationPlan).toHaveBeenCalledWith("inv-nav-001", "gap-001");
      expect(screen.getByText("Formulated Verification Queries")).toBeInTheDocument();
    });

    expect(screen.getByText("Target Tier: TIER_1")).toBeInTheDocument();
  });

  it("submits a manual candidate source for triage (Gate 1)", async () => {
    const updatedCandidate: api.GapCandidateSource = {
      id: "cand-002",
      plan_id: "plan-001",
      investigation_id: "inv-nav-001",
      url: "https://audit.gov/reports/apex_cert.pdf",
      domain: "audit.gov",
      title: "Audit Certificate Apex",
      snippet: "Official ISO audit certificate",
      authority_tier: "TIER_1",
      relevance_score: 92.0,
      discovery_mode: "MANUAL_ENTRY",
      relevance_rationale: "Tier-1 domain match",
      review_status: "PENDING_REVIEW",
      rejection_reason: undefined,
      discovered_at: "2026-10-31T01:10:00Z",
    };

    vi.mocked(api.submitManualCandidate).mockResolvedValue(updatedCandidate);

    render(
      <MemoryRouter initialEntries={["/verification-navigator?investigation_id=inv-nav-001"]}>
        <VerificationPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getAllByText("Subsidiary Solvency & Tier-1 Capital").length).toBeGreaterThan(0);
    });

    fireEvent.click(screen.getByText("Formulate Plan"));

    await waitFor(() => {
      expect(screen.getByText("Submit Candidate Source URL for Triage")).toBeInTheDocument();
    });

    const inputUrl = screen.getByPlaceholderText("https://example.gov/filing.pdf");
    fireEvent.change(inputUrl, { target: { value: "https://audit.gov/reports/apex_cert.pdf" } });

    const submitBtn = screen.getByText("Submit Candidate");
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(api.submitManualCandidate).toHaveBeenCalledWith(
        "inv-nav-001",
        "plan-001",
        expect.objectContaining({
          url: "https://audit.gov/reports/apex_cert.pdf",
        })
      );
    });
  });

  it("handles analyst Gate 1 review actions (Approve for Ingestion)", async () => {
    vi.mocked(api.reviewCandidateSource).mockResolvedValue({
      ...mockPlan.candidates![0],
      review_status: "APPROVED",
    });

    render(
      <MemoryRouter initialEntries={["/verification-navigator?investigation_id=inv-nav-001"]}>
        <VerificationPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getAllByText("Subsidiary Solvency & Tier-1 Capital").length).toBeGreaterThan(0);
    });

    fireEvent.click(screen.getByText("Formulate Plan"));

    await waitFor(() => {
      expect(screen.getByText("SEC 10-K Subsidiary Annual Report")).toBeInTheDocument();
    });

    const approveBtn = screen.getByText("Approve for Ingestion");
    fireEvent.click(approveBtn);

    await waitFor(() => {
      expect(api.reviewCandidateSource).toHaveBeenCalledWith(
        "inv-nav-001",
        "cand-001",
        "APPROVE"
      );
    });
  });

  it("evaluates deterministic gap reassessment proposal and commits Gate 2 approval", async () => {
    const mockReassess: api.GapReassessment = {
      id: "reassess-001",
      gap_id: "gap-001",
      investigation_id: "inv-nav-001",
      predicate_fulfillment_score: 95.0,
      composite_evidence_score: 90.0,
      previous_state: "NO_EVIDENCE",
      proposed_resolution_state: "RESOLVED",
      analyst_decision: "PENDING_DECISION",
      analyst_notes: "",
      matched_claim_ids: ["c-001"],
      is_analyst_override: false,
      created_at: "2026-10-31T01:20:00Z",
    };

    vi.mocked(api.evaluateGap).mockResolvedValue(mockReassess);
    vi.mocked(api.commitGapReassessment).mockResolvedValue({
      ...mockReassess,
      analyst_decision: "APPROVED",
      analyst_notes: "Verified regulatory filing matches requirement.",
    });

    render(
      <MemoryRouter initialEntries={["/verification-navigator?investigation_id=inv-nav-001"]}>
        <VerificationPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getAllByText("Subsidiary Solvency & Tier-1 Capital").length).toBeGreaterThan(0);
    });

    const evalBtn = screen.getByText("Compute Proposed Reassessment");
    fireEvent.click(evalBtn);

    await waitFor(() => {
      expect(api.evaluateGap).toHaveBeenCalledWith("inv-nav-001", "gap-001");
      expect(screen.getByText("Proposed Resolution State:")).toBeInTheDocument();
      expect(screen.getByText("Commit Resolution Decision to Database")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("Commit Resolution Decision to Database"));

    await waitFor(() => {
      expect(api.commitGapReassessment).toHaveBeenCalledWith(
        "inv-nav-001",
        "reassess-001",
        expect.objectContaining({
          analyst_decision: "APPROVED",
          analyst_final_state: "RESOLVED",
        })
      );
    });
  });

  it("displays Source Impact Feed (Workflow B) with stage breakdown and narrative", async () => {
    render(
      <MemoryRouter initialEntries={["/verification-navigator?investigation_id=inv-nav-001"]}>
        <VerificationPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/Workflow B: Source Impact Feed/)).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText(/Workflow B: Source Impact Feed/));

    await waitFor(() => {
      expect(screen.getByText("SEC 10-K Filing 2026")).toBeInTheDocument();
      expect(screen.getByText("Selective Orchestration Stage Breakdown")).toBeInTheDocument();
      expect(screen.getByText("Orchestrator Forensic Narrative (Grounded in Verified Evidence)")).toBeInTheDocument();
    });
  });

  it("displays Audit Log with tamper-evident records", async () => {
    render(
      <MemoryRouter initialEntries={["/verification-navigator?investigation_id=inv-nav-001"]}>
        <VerificationPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/Orchestration Audit Log/)).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText(/Orchestration Audit Log/));

    await waitFor(() => {
      expect(screen.getByText("CANDIDATE_SUBMITTED")).toBeInTheDocument();
      expect(screen.getByText("analyst")).toBeInTheDocument();
    });
  });
});
