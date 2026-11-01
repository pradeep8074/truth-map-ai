import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { ReportsPage } from "../pages/ReportsPage";
import * as api from "../lib/api";

// Mock API functions
vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof api>("../lib/api");
  return {
    ...actual,
    listInvestigations: vi.fn(),
    getReportStatus: vi.fn(),
    getInvestigationReports: vi.fn(),
    getReportById: vi.fn(),
    generateInvestigationReport: vi.fn(),
  };
});

describe("Component 08: Decision Intelligence Report Engine", () => {
  const mockInvestigations: api.Investigation[] = [
    {
      id: "inv-rpt-001",
      research_question: "Should we acquire HyperScale Cloud Infrastructure?",
      status: "completed",
      created_at: "2026-10-31T00:00:00Z",
      sources_count: 2,
      claims_count: 5,
    },
  ];

  const mockReportStatus: api.DecisionReportStatus = {
    investigation_id: "inv-rpt-001",
    has_report: true,
    latest_report_id: "rpt-101",
    latest_version: 1,
    latest_status: "published",
    is_stale: false,
    overall_robustness: "CONDITIONALLY_ROBUST",
    processing_mode: "gemini",
    last_generated_at: "2026-10-31T02:00:00Z",
  };

  const mockReportSummary: api.DecisionReportSummary = {
    id: "rpt-101",
    investigation_id: "inv-rpt-001",
    report_version: 1,
    report_status: "published",
    processing_mode: "gemini",
    overall_robustness: "CONDITIONALLY_ROBUST",
    executive_summary: "Acquisition satisfies financial criteria with verified ARR of $11.4M, but cybersecurity compliance remains unverified.",
    is_stale: false,
    created_at: "2026-10-31T02:00:00Z",
  };

  const mockFullReport: api.DecisionReport = {
    id: "rpt-101",
    investigation_id: "inv-rpt-001",
    report_version: 1,
    report_status: "published",
    processing_mode: "gemini",
    overall_robustness: "CONDITIONALLY_ROBUST",
    executive_summary: "Acquisition satisfies financial criteria with verified ARR of $11.4M, but cybersecurity compliance remains unverified.",
    is_stale: false,
    created_at: "2026-10-31T02:00:00Z",
    updated_at: "2026-10-31T02:00:00Z",
    snapshot_metadata: {
      sources_count: 2,
      claims_count: 5,
    },
    report_data: {
      executive_brief: {
        investigation_id: "inv-rpt-001",
        research_question: "Should we acquire HyperScale Cloud Infrastructure?",
        decision_objective: "Authorize $45M strategic acquisition of HyperScale Cloud assets",
        report_version: 1,
        generated_at: "2026-10-31T02:00:00Z",
        overall_robustness: "CONDITIONALLY_ROBUST",
        coverage_ratio: 0.67,
        total_sources: 2,
        total_claims: 5,
        unresolved_conflicts_count: 0,
        identified_gaps_count: 1,
        high_severity_scenarios_count: 1,
        executive_conclusion: "Acquisition satisfies financial criteria with verified ARR of $11.4M, but cybersecurity compliance remains unverified.",
      },
      decision_contract: {
        contract_id: "dc-101",
        normalized_question: "Should we acquire HyperScale Cloud Infrastructure?",
        decision_objective: "Authorize $45M strategic acquisition of HyperScale Cloud assets",
        scope: "Global Infrastructure",
        requirements: [
          {
            requirement_id: "req-1",
            title: "Audited Recurring ARR Exceeds $10M",
            priority: "HIGH",
            verification_criteria: "GAAP audited statements",
            evidence_types: ["Financial Audit"],
          },
        ],
        constraints: ["Close within Q4"],
        assumptions: ["Key engineering leadership retention"],
        unresolved_questions: ["Top 5 customer churn rates"],
      },
      evidence_intelligence: {
        total_sources: 2,
        total_passages: 4,
        total_claims: 5,
        factual_claims_count: 3,
        statistical_claims_count: 2,
        sources: [
          {
            source_id: "src-1",
            title: "Q3 2026 HyperScale Financial Audit Report",
            publisher: "Ernst & Young",
            publication_date: "2026-09-30",
            source_type: "document",
            sha256_hash: "hash_ey_1234567890abcdef",
            extraction_status: "completed",
            claims_count: 3,
          },
        ],
        reliability_limitations: "Evidence base verified cryptographically via SHA-256 hashes.",
      },
      requirement_assessment: {
        matrix: [
          {
            requirement_id: "req-1",
            title: "Audited Recurring ARR Exceeds $10M",
            priority: "HIGH",
            coverage_status: "SUFFICIENT",
            supporting_claims: [
              {
                claim_id: "clm-1",
                claim_text: "HyperScale achieved $11.4M ARR with positive cash flow.",
                source_title: "Q3 2026 HyperScale Financial Audit Report",
                source_id: "src-1",
                passage_hash: "p_hash_1",
                relevance: "STRONG",
                confidence: 0.95,
              },
            ],
            opposing_evidence: [],
            identified_gaps: [],
            assessment_summary: "Audited revenue confirms ARR requirement is met.",
            confidence: 0.95,
          },
        ],
        coverage_summary: {
          SUFFICIENT: 1,
        },
      },
      conflict_analysis: {
        total_conflicts: 0,
        unresolved_count: 0,
        critical_count: 0,
        conflicts: [],
      },
      gaps_and_uncertainty: {
        total_gaps: 1,
        high_priority_gaps: 1,
        gaps: [
          {
            gap_id: "gap-1",
            requirement_id: "req-2",
            requirement_title: "SOC-2 Type II Compliance",
            gap_description: "Missing current year SOC-2 Type II audit certificate",
            why_it_matters: "Unverified cybersecurity posture exposes infrastructure to liability",
            evidence_needed: "Current SOC-2 Type II audit report",
            suggested_source_type: "Independent Compliance Audit",
            priority: "HIGH",
          },
        ],
      },
      stress_test_results: {
        baseline_outcome: "CONDITIONALLY_ROBUST",
        total_scenarios: 1,
        vulnerable_scenarios: 1,
        scenarios: [
          {
            scenario_id: "sc-1",
            title: "Top 2 Enterprise Customer Churn Event",
            category: "RISK_MATERIALIZATION",
            trigger_condition: "Customer cancellation notice served before closing",
            severity: "CRITICAL",
            outcome_shift: "CRITICAL_FAILURE",
            scenario_outcome: "VULNERABLE",
            impact_explanation: "ARR falls below minimum acquisition hurdle.",
            key_vulnerabilities: ["Customer concentration risk"],
          },
        ],
      },
      risk_mitigation: {
        total_risks: 1,
        critical_risks: 1,
        high_risks: 0,
        risks: [
          {
            risk_id: "RISK-01",
            title: "Customer Concentration Stress",
            origin: "Stress Scenario",
            severity: "CRITICAL",
            affected_requirement: "req-1",
            consequence: "Severe ARR degradation under top customer churn.",
            mitigation: "Structure earnout tied to 12-month enterprise retention.",
            additional_evidence_needed: "Enterprise contract renewal logs.",
          },
        ],
      },
      recommended_actions: {
        actions: [
          {
            action_id: "ACT-01",
            action_title: "Procure Missing SOC-2 Type II Attestation",
            description: "Condition transaction closing on delivery of clean audit.",
            priority: "P1_IMMEDIATE",
            driver: "High-priority compliance evidence gap.",
            target_requirement: "req-2",
            expected_outcome: "Transition cybersecurity requirement to SUFFICIENT.",
          },
        ],
      },
      final_conclusion: {
        supported_findings: ["Audited revenue threshold satisfied at $11.4M."],
        uncertainties_and_caveats: ["Cybersecurity compliance remains unverified."],
        invalidating_conditions: ["Cancellation notice from top 2 enterprise accounts."],
        recommended_decision_posture: "PROCEED_WITH_SAFEGUARDS",
        epistemic_boundary_disclaimer: "EPISTEMIC BOUNDARY DISCLAIMER: Every finding reported herein is strictly conditioned on the evidence ingested.",
      },
    },
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.listInvestigations).mockResolvedValue(mockInvestigations);
    vi.mocked(api.getReportStatus).mockResolvedValue(mockReportStatus);
    vi.mocked(api.getInvestigationReports).mockResolvedValue({
      investigation_id: "inv-rpt-001",
      total_reports: 1,
      latest_version: 1,
      reports: [mockReportSummary],
    });
    vi.mocked(api.getReportById).mockResolvedValue(mockFullReport);
    vi.mocked(api.generateInvestigationReport).mockResolvedValue(mockFullReport);
  });

  it("renders page header and processing mode pill", async () => {
    render(
      <MemoryRouter initialEntries={["/reports?investigation_id=inv-rpt-001"]}>
        <ReportsPage />
      </MemoryRouter>
    );

    expect(await screen.findByText("Decision Intelligence Report Engine")).toBeInTheDocument();
    expect(await screen.findByText("✦ Gemini 2.5 Flash Synthesis")).toBeInTheDocument();
    expect(screen.getByText("CONDITIONALLY ROBUST")).toBeInTheDocument();
  });

  it("renders all 10 core report sections", async () => {
    render(
      <MemoryRouter initialEntries={["/reports?investigation_id=inv-rpt-001"]}>
        <ReportsPage />
      </MemoryRouter>
    );

    expect(await screen.findByText("Executive Decision Brief")).toBeInTheDocument();
    expect(screen.getByText("Decision Contract Baseline")).toBeInTheDocument();
    expect(screen.getByText("Evidence Intelligence & Provenance")).toBeInTheDocument();
    expect(screen.getByText("Requirement-Level Assessment Matrix")).toBeInTheDocument();
    expect(screen.getByText("Conflict & Contradiction Analysis")).toBeInTheDocument();
    expect(screen.getByText("Evidence Gaps & Uncertainty Register")).toBeInTheDocument();
    expect(screen.getByText("Decision Stress-Test Results")).toBeInTheDocument();
    expect(screen.getByText("Actionable Risk Register & Mitigations")).toBeInTheDocument();
    expect(screen.getByText("Prioritized Analyst Next Actions")).toBeInTheDocument();
    expect(screen.getByText("Final Decision Intelligence Conclusion")).toBeInTheDocument();
  });

  it("displays actionable risk register and recommended action items", async () => {
    render(
      <MemoryRouter initialEntries={["/reports?investigation_id=inv-rpt-001"]}>
        <ReportsPage />
      </MemoryRouter>
    );

    expect(await screen.findByText("RISK-01")).toBeInTheDocument();
    expect(screen.getByText("Customer Concentration Stress")).toBeInTheDocument();
    expect(screen.getByText("ACT-01")).toBeInTheDocument();
    expect(screen.getByText("Procure Missing SOC-2 Type II Attestation")).toBeInTheDocument();
  });

  it("displays stale snapshot banner when report is stale", async () => {
    const staleReport: api.DecisionReport = {
      ...mockFullReport,
      is_stale: true,
    };
    vi.mocked(api.getReportById).mockResolvedValue(staleReport);

    render(
      <MemoryRouter initialEntries={["/reports?investigation_id=inv-rpt-001"]}>
        <ReportsPage />
      </MemoryRouter>
    );

    expect(await screen.findByText("Upstream Data Changed:")).toBeInTheDocument();
    expect(screen.getByText("Recompile Full")).toBeInTheDocument();
  });

  it("triggers report compilation when Compile New Version button is clicked", async () => {
    render(
      <MemoryRouter initialEntries={["/reports?investigation_id=inv-rpt-001"]}>
        <ReportsPage />
      </MemoryRouter>
    );

    const compileBtn = await screen.findByText("Compile New Version");
    fireEvent.click(compileBtn);

    await waitFor(() => {
      expect(api.generateInvestigationReport).toHaveBeenCalledWith("inv-rpt-001", expect.anything());
    });
  });
});
