import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import { EvidenceSufficiencyPage } from "../pages/EvidenceSufficiencyPage";
import * as api from "../lib/api";

// Mock API functions
vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof api>("../lib/api");
  return {
    ...actual,
    listInvestigations: vi.fn(),
    getInvestigationSufficiency: vi.fn(),
    analyzeInvestigationSufficiency: vi.fn(),
    getRequirementSufficiencyDetail: vi.fn(),
  };
});

describe("Component 06: Evidence Sufficiency & Gap Analysis Engine", () => {
  const mockInvestigations: api.Investigation[] = [
    {
      id: "inv-sufficiency-test",
      research_question: "Should the company transition from AWS to bare-metal servers?",
      status: "completed",
      created_at: "2026-10-30T20:00:00Z",
      sources_count: 3,
      claims_count: 8,
    },
  ];

  const mockSufficiencyResponse: api.SufficiencyResponse = {
    investigation_id: "inv-sufficiency-test",
    contract_id: "contract-123",
    decision_objective: "Evaluate cost efficiency, performance, and operational feasibility of bare-metal migration.",
    processing_mode: "gemini",
    last_analyzed_at: "2026-10-30T21:30:00Z",
    summary: {
      total_requirements: 3,
      sufficient_count: 1,
      partial_count: 1,
      insufficient_count: 0,
      no_evidence_count: 0,
      conflicting_count: 1,
      overall_coverage_ratio: 0.333,
      coverage_explanation: "33% satisfied",
      total_gaps: 2,
      high_priority_gaps: 1,
      medium_priority_gaps: 1,
      low_priority_gaps: 0,
    },
    assessments: [
      {
        requirement_id: "req-1",
        investigation_id: "inv-sufficiency-test",
        requirement_title: "Total Cost of Ownership Reduction",
        requirement_description: "Migration must achieve a verified 25% decrease in overall infrastructure costs.",
        requirement_type: "financial",
        priority: "CRITICAL",
        verification_criteria: "Audited annual compute expenditure, Facility rack rental and power costs",
        coverage_status: "SUFFICIENT",
        assessment_summary: "Adequately corroborated by independent financial audits from both IT finance and vendor proposals.",
        limitations: "Assumes power utility tariffs remain stable over 3 years.",
        missing_information: "None identified for current phase.",
        recommended_action: "Proceed to operational stress-testing.",
        confidence: 0.94,
        supporting_claims: [
          {
            claim_id: "clm-1",
            claim_text: "Bare-metal transition yields a 28% reduction in recurring compute operational costs.",
            source_id: "src-1",
            source_title: "Internal IT Finance Audit 2025",
            source_url: "https://internal.audit/it-finance",
            passage_text: "Consolidated projections confirm bare-metal transition yields a 28% reduction in recurring operational compute costs.",
            page_number: 14,
            sha256_hash: "abcdef0123456789",
            relevance: "DIRECTLY_RELEVANT",
            relevance_explanation: "Directly verifies 25%+ cost savings criterion.",
            extraction_confidence: 0.95,
          },
        ],
        supporting_claim_ids: ["clm-1"],
        supporting_passage_ids: ["pas-1"],
        source_ids: ["src-1"],
        related_conflicts: [],
        related_conflict_ids: [],
        unresolved_conflict_count: 0,
        gaps: [],
        analysis_method: "gemini_sufficiency_engine:gemini-flash-lite-latest",
        processing_mode: "gemini",
        analyzed_at: "2026-10-30T21:30:00Z",
      },
      {
        requirement_id: "req-2",
        investigation_id: "inv-sufficiency-test",
        requirement_title: "Network Latency & SLA Guarantees",
        requirement_description: "Bare-metal infrastructure must sustain sub-5ms inter-service latency at 99.99% SLA.",
        requirement_type: "technical",
        priority: "HIGH",
        verification_criteria: "Independent synthetic network benchmark",
        coverage_status: "PARTIAL",
        assessment_summary: "Single-source benchmark provided by prospective server vendor without third-party audit.",
        limitations: "Vendor-provided benchmark may not account for peak production bursts.",
        missing_information: "Third-party synthetic latency telemetry during simulated traffic spikes.",
        recommended_action: "Execute independent black-box synthetic latency benchmarks.",
        confidence: 0.78,
        supporting_claims: [],
        supporting_claim_ids: [],
        supporting_passage_ids: [],
        source_ids: ["src-2"],
        related_conflicts: [],
        related_conflict_ids: [],
        unresolved_conflict_count: 0,
        gaps: [
          {
            id: "gap-1",
            investigation_id: "inv-sufficiency-test",
            requirement_id: "req-2",
            assessment_id: "suff-2",
            gap_description: "Missing independent multi-tenant synthetic network latency audit.",
            why_it_matters: "Relying purely on vendor assertions risks latency regression under production peak.",
            evidence_needed: "Third-party network telemetry verifying p99 < 5ms under 50k req/sec load.",
            suggested_source_type: "Independent Network Performance Benchmark",
            priority: "HIGH",
            created_at: "2026-10-30T21:30:00Z",
          },
        ],
        analysis_method: "gemini_sufficiency_engine:gemini-flash-lite-latest",
        processing_mode: "gemini",
        analyzed_at: "2026-10-30T21:30:00Z",
      },
      {
        requirement_id: "req-3",
        investigation_id: "inv-sufficiency-test",
        requirement_title: "Operational Reliability & MTTR",
        requirement_description: "Hardware replacement and MTTR must remain under 4 hours.",
        requirement_type: "operational",
        priority: "HIGH",
        verification_criteria: "Data center on-site parts availability contract",
        coverage_status: "CONFLICTING",
        assessment_summary: "Evidence basis is compromised by an active conflict regarding on-site parts dispatch times.",
        limitations: "SLA states 2-hour dispatch while third-party review notes 8-hour average response.",
        missing_information: "Reconciliation of colocation facility dispatch times.",
        recommended_action: "Review conflict in Conflict Intelligence module.",
        confidence: 0.88,
        supporting_claims: [],
        supporting_claim_ids: [],
        supporting_passage_ids: [],
        source_ids: ["src-3", "src-4"],
        related_conflicts: [
          {
            conflict_id: "conf-101",
            claim_a_id: "clm-3",
            claim_b_id: "clm-4",
            opposing_claim_text: "Average replacement hardware turnaround took 8.2 hours.",
            conflict_type: "NUMERICAL_CONFLICT",
            severity: "HIGH",
            explanation: "Vendor asserts 2h dispatch while external audit proved 8.2h average turnaround.",
            resolution_status: "unresolved",
            is_unresolved: true,
          },
        ],
        related_conflict_ids: ["conf-101"],
        unresolved_conflict_count: 1,
        gaps: [
          {
            id: "gap-2",
            investigation_id: "inv-sufficiency-test",
            requirement_id: "req-3",
            assessment_id: "suff-3",
            gap_description: "Contradiction between vendor SLA and customer-reported dispatch times.",
            why_it_matters: "Unresolved MTTR variance may cause unacceptable downtime.",
            evidence_needed: "Audited historical incident logs from the colocation facility.",
            suggested_source_type: "Facility Incident Records",
            priority: "HIGH",
            created_at: "2026-10-30T21:30:00Z",
          },
        ],
        analysis_method: "gemini_sufficiency_engine:gemini-flash-lite-latest",
        processing_mode: "gemini",
        analyzed_at: "2026-10-30T21:30:00Z",
      },
    ],
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.listInvestigations).mockResolvedValue(mockInvestigations);
    vi.mocked(api.getInvestigationSufficiency).mockResolvedValue(mockSufficiencyResponse);
    vi.mocked(api.analyzeInvestigationSufficiency).mockResolvedValue(mockSufficiencyResponse);
  });

  const renderComponent = () => {
    return render(
      <BrowserRouter>
        <EvidenceSufficiencyPage />
      </BrowserRouter>
    );
  };

  it("renders page header, title, and processing mode badge", async () => {
    renderComponent();

    expect(await screen.findByText(/AI ANALYSIS ACTIVE/i)).toBeInTheDocument();
    expect(screen.getByText("Evidence Coverage")).toBeInTheDocument();
    expect(screen.getByText(/Evaluate cost efficiency, performance, and operational feasibility/i)).toBeInTheDocument();
  });

  it("renders summary metric cards with accurate computed numbers", async () => {
    renderComponent();

    const items = await screen.findAllByText("Total Cost of Ownership Reduction");
    expect(items[0]).toBeInTheDocument();

    expect(screen.getByText("Requirements")).toBeInTheDocument();
    expect(screen.getAllByText("Supported")[0]).toBeInTheDocument();
    expect(screen.getAllByText("Partially Supported")[0]).toBeInTheDocument();
    expect(screen.getAllByText("Conflicting")[0]).toBeInTheDocument();
    expect(screen.getByText("Evidence Gaps")).toBeInTheDocument();
    expect(screen.getByText("Coverage Completeness:")).toBeInTheDocument();
    expect(screen.getByText("33%")).toBeInTheDocument();
  });

  it("filters requirements by coverage status", async () => {
    renderComponent();

    const items = await screen.findAllByText("Total Cost of Ownership Reduction");
    expect(items[0]).toBeInTheDocument();

    const statusSelect = screen.getByDisplayValue("All Coverage Statuses");
    fireEvent.change(statusSelect, { target: { value: "CONFLICTING" } });

    expect(await screen.findByText("Operational Reliability & MTTR")).toBeInTheDocument();
    const filteredH4 = screen.queryAllByRole("heading", { level: 4, name: "Total Cost of Ownership Reduction" });
    expect(filteredH4.length).toBe(0);
  });

  it("searches requirements by text query", async () => {
    renderComponent();

    const items = await screen.findAllByText("Total Cost of Ownership Reduction");
    expect(items[0]).toBeInTheDocument();

    const searchInput = screen.getByPlaceholderText(/search requirements, criteria/i);
    fireEvent.change(searchInput, { target: { value: "latency" } });

    expect(await screen.findByText("Network Latency & SLA Guarantees")).toBeInTheDocument();
    const filteredH4 = screen.queryAllByRole("heading", { level: 4, name: "Total Cost of Ownership Reduction" });
    expect(filteredH4.length).toBe(0);
  });

  it("selects requirement card and displays detailed inspector pane", async () => {
    renderComponent();

    const items = await screen.findAllByText("Total Cost of Ownership Reduction");
    fireEvent.click(items[0]);

    expect(await screen.findByText(/Audited annual compute expenditure/i)).toBeInTheDocument();
    expect(screen.getAllByText(/Adequately corroborated by independent financial audits/i)[0]).toBeInTheDocument();
    expect(screen.getByText(/Internal IT Finance Audit 2025/i)).toBeInTheDocument();
    expect(screen.getAllByText(/Bare-metal transition yields a 28% reduction/i)[0]).toBeInTheDocument();
  });

  it("inspects actionable evidence gaps for requirements with partial coverage", async () => {
    renderComponent();

    const partialCard = await screen.findByText("Network Latency & SLA Guarantees");
    fireEvent.click(partialCard);

    expect(await screen.findByText(/Actionable Evidence Gaps/i)).toBeInTheDocument();
    expect(screen.getByText(/Missing independent multi-tenant synthetic network latency audit/i)).toBeInTheDocument();
    expect(screen.getByText(/Third-party network telemetry verifying p99 < 5ms/i)).toBeInTheDocument();
    expect(screen.getByText(/Independent Network Performance Benchmark/i)).toBeInTheDocument();
  });

  it("displays related conflicts and navigation link to Conflict Explorer", async () => {
    renderComponent();

    const conflictCard = await screen.findByText("Operational Reliability & MTTR");
    fireEvent.click(conflictCard);

    expect(await screen.findByText(/Contested Evidence Conflicts/i)).toBeInTheDocument();
    expect(screen.getByText(/Vendor asserts 2h dispatch while external audit proved 8.2h/i)).toBeInTheDocument();
    expect(screen.getByText(/Open Conflict Explorer/i)).toBeInTheDocument();
  });

  it("triggers re-analysis when Check Evidence Coverage button is clicked", async () => {
    renderComponent();

    const items = await screen.findAllByText("Total Cost of Ownership Reduction");
    expect(items[0]).toBeInTheDocument();

    const runBtn = screen.getByText("Check Evidence Coverage");
    fireEvent.click(runBtn);

    await waitFor(() => {
      expect(api.analyzeInvestigationSufficiency).toHaveBeenCalledWith("inv-sufficiency-test");
    });
  });
});
