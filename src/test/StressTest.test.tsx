import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { StressTestPage } from "../pages/StressTestPage";
import * as api from "../lib/api";

// Mock API functions
vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof api>("../lib/api");
  return {
    ...actual,
    listInvestigations: vi.fn(),
    getInvestigationStressTests: vi.fn(),
    generateInvestigationStressScenarios: vi.fn(),
    evaluateInvestigationStressScenario: vi.fn(),
  };
});

describe("Component 07: Decision Stress Testing Engine", () => {
  const mockInvestigations: api.Investigation[] = [
    {
      id: "inv-stress-test",
      research_question: "Should the company transition from AWS to bare-metal servers?",
      status: "completed",
      created_at: "2026-10-30T20:00:00Z",
      sources_count: 3,
      claims_count: 8,
    },
  ];

  const mockStressTestResponse: api.StressTestListResponse = {
    investigation_id: "inv-stress-test",
    processing_mode: "gemini",
    last_generated_at: "2026-10-30T22:00:00Z",
    baseline: {
      baseline_outcome: "CONDITIONALLY_ROBUST",
      total_requirements: 3,
      sufficient_requirements: 2,
      partial_requirements: 1,
      insufficient_requirements: 0,
      no_evidence_requirements: 0,
      conflicting_requirements: 0,
      active_conflicts: 0,
      critical_conflicts: 0,
      unresolved_gaps: 1,
      baseline_rationale: "Core requirements partially or adequately corroborated pending single-source decoupling.",
      key_dependencies: ["Bare-metal hardware lease rates"],
    },
    summary: {
      total_scenarios: 6,
      evaluated_scenarios: 1,
      vulnerable_scenarios: 1,
      indeterminate_scenarios: 0,
      critical_severity_count: 1,
      high_severity_count: 3,
      baseline_outcome: "CONDITIONALLY_ROBUST",
      processing_mode: "gemini",
    },
    scenarios: [
      {
        id: "sc-1",
        investigation_id: "inv-stress-test",
        title: "Assumption Failure: Hardware Lease Escalation",
        category: "ASSUMPTION_FAILURE",
        description: "Simulates what happens if colocation facility doubles power and rack lease fees.",
        trigger_condition: "Colocation datacenter provider invokes contractual 100% power surcharge.",
        challenged_assumptions: ["Datacenter utility tariffs remain flat over the 3-year depreciation horizon."],
        affected_requirement_ids: ["req-1"],
        affected_requirement_titles: ["Total Cost of Ownership Reduction"],
        related_claim_ids: ["clm-1"],
        related_source_ids: ["src-1"],
        related_conflict_ids: [],
        expected_impact: "Eradicates projected 28% cost savings, flipping requirement from SUFFICIENT to INSUFFICIENT.",
        severity: "CRITICAL",
        evidence_needed: "Fixed-rate multi-year utility agreement with energy provider.",
        evaluation_status: "evaluated",
        processing_mode: "gemini",
        created_at: "2026-10-30T22:00:00Z",
        evaluation: {
          id: "eval-1",
          scenario_id: "sc-1",
          investigation_id: "inv-stress-test",
          baseline_overall_outcome: "CONDITIONALLY_ROBUST",
          scenario_overall_outcome: "VULNERABLE",
          outcome_shift: "DOWNGRADED",
          impact_explanation: "Power cost escalation eliminates economic margin of safety, turning decision negative.",
          key_vulnerabilities: [
            "Single-source dependency on volatile electricity tariffs.",
            "Absence of contractual hedging on datacenter power consumption.",
          ],
          uncertainty_factors: ["Future statutory caps on municipal power rates."],
          recommended_actions: [
            "Negotiate 36-month fixed power PPA before signing hardware purchase orders.",
          ],
          requirement_evaluations: [
            {
              requirement_id: "req-1",
              requirement_title: "Total Cost of Ownership Reduction",
              baseline_status: "SUFFICIENT",
              scenario_status: "INSUFFICIENT",
              status_shift: "DEGRADED",
              degradation_reason: "Surging operational energy costs exceed baseline savings ceiling.",
            },
          ],
          processing_mode: "gemini",
          evaluated_at: "2026-10-30T22:05:00Z",
        },
      },
      {
        id: "sc-2",
        investigation_id: "inv-stress-test",
        title: "Risk Materialization: Inter-rack Network Latency Spikes",
        category: "RISK_MATERIALIZATION",
        description: "Evaluates impact if multi-tenant noisy neighbors degrade cross-rack packet latency.",
        trigger_condition: "Peak evening traffic introduces 15ms packet jitter exceeding 5ms SLA.",
        challenged_assumptions: ["Network isolation is guaranteed at physical switch layer."],
        affected_requirement_ids: ["req-2"],
        affected_requirement_titles: ["Network Latency & SLA Guarantees"],
        related_claim_ids: [],
        related_source_ids: [],
        related_conflict_ids: [],
        expected_impact: "Degrades user experience for real-time transactional database replication.",
        severity: "HIGH",
        evidence_needed: "Dedicated physical switch port telemetry logs.",
        evaluation_status: "unevaluated",
        processing_mode: "gemini",
        created_at: "2026-10-30T22:00:00Z",
      },
    ],
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.listInvestigations).mockResolvedValue(mockInvestigations);
    vi.mocked(api.getInvestigationStressTests).mockResolvedValue(mockStressTestResponse);
    vi.mocked(api.generateInvestigationStressScenarios).mockResolvedValue(mockStressTestResponse);
    vi.mocked(api.evaluateInvestigationStressScenario).mockResolvedValue({
      ...mockStressTestResponse.scenarios[1],
      evaluation_status: "evaluated",
      evaluation: {
        id: "eval-2",
        scenario_id: "sc-2",
        investigation_id: "inv-stress-test",
        baseline_overall_outcome: "CONDITIONALLY_ROBUST",
        scenario_overall_outcome: "CONDITIONALLY_ROBUST",
        outcome_shift: "UNCHANGED",
        impact_explanation: "Jitter can be managed with local queue buffering.",
        key_vulnerabilities: ["Queue depth buffer limits."],
        uncertainty_factors: ["Switch buffer sizing."],
        recommended_actions: ["Deploy DPDK kernel bypass."],
        requirement_evaluations: [
          {
            requirement_id: "req-2",
            requirement_title: "Network Latency & SLA Guarantees",
            baseline_status: "PARTIAL",
            scenario_status: "PARTIAL",
            status_shift: "UNMODIFIED",
            degradation_reason: "Mitigated by software buffer.",
          },
        ],
        processing_mode: "gemini",
        evaluated_at: "2026-10-30T22:10:00Z",
      },
    });
  });

  const renderComponent = () => {
    return render(
      <MemoryRouter initialEntries={["/stress-test?inv=inv-stress-test"]}>
        <StressTestPage />
      </MemoryRouter>
    );
  };

  it("renders page header and processing mode badge", async () => {
    renderComponent();

    expect(await screen.findByText("Test Your Decision")).toBeInTheDocument();
    expect(await screen.findByText("AI ANALYSIS ACTIVE")).toBeInTheDocument();
  });

  it("renders overview KPI summary cards with computed numbers", async () => {
    renderComponent();

    const items = await screen.findAllByText("Assumption Failure: Hardware Lease Escalation");
    expect(items[0]).toBeInTheDocument();

    expect(screen.getByText("Baseline Outcome")).toBeInTheDocument();
    expect(screen.getByText("CONDITIONALLY ROBUST")).toBeInTheDocument();
    expect(screen.getByText("Total Scenarios")).toBeInTheDocument();
    expect(screen.getByText("Across 6 risk categories")).toBeInTheDocument();
  });

  it("renders scenario cards in the explorer feed", async () => {
    renderComponent();

    const sc1Items = await screen.findAllByText("Assumption Failure: Hardware Lease Escalation");
    expect(sc1Items[0]).toBeInTheDocument();

    expect(screen.getByText("Risk Materialization: Inter-rack Network Latency Spikes")).toBeInTheDocument();
    expect(screen.getAllByText("Assumption Failure").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Risk Materialization").length).toBeGreaterThan(0);
  });

  it("displays inspector details for selected evaluated scenario", async () => {
    renderComponent();

    const items = await screen.findAllByText("Assumption Failure: Hardware Lease Escalation");
    expect(items[0]).toBeInTheDocument();

    // Inspector shows trigger condition
    expect(screen.getByText("Trigger Condition")).toBeInTheDocument();
    expect(
      screen.getAllByText("Colocation datacenter provider invokes contractual 100% power surcharge.")[0]
    ).toBeInTheDocument();

    // Inspector shows evaluated outcome comparison
    expect(screen.getByText("Outcome Shift:")).toBeInTheDocument();
    expect(screen.getByText("DOWNGRADED")).toBeInTheDocument();
    expect(screen.getByText("Key Vulnerabilities")).toBeInTheDocument();
    expect(screen.getByText("Recommended Mitigations")).toBeInTheDocument();
  });

  it("filters scenarios by category and severity", async () => {
    renderComponent();

    const items = await screen.findAllByText("Assumption Failure: Hardware Lease Escalation");
    expect(items[0]).toBeInTheDocument();

    // Filter by category ASSUMPTION_FAILURE
    const categorySelect = screen.getByDisplayValue("All Categories");
    fireEvent.change(categorySelect, { target: { value: "ASSUMPTION_FAILURE" } });

    expect(screen.getAllByText("Assumption Failure: Hardware Lease Escalation")[0]).toBeInTheDocument();
    expect(
      screen.queryByText("Risk Materialization: Inter-rack Network Latency Spikes")
    ).not.toBeInTheDocument();
  });

  it("evaluates an unevaluated scenario on button click", async () => {
    renderComponent();

    const sc2Items = await screen.findAllByText("Risk Materialization: Inter-rack Network Latency Spikes");
    expect(sc2Items[0]).toBeInTheDocument();

    // Click on the second (unevaluated) scenario card
    fireEvent.click(sc2Items[0]);

    // Inspector should now show "Evaluate Scenario" button
    const evalBtns = await screen.findAllByRole("button", { name: /Evaluate Scenario/i });
    expect(evalBtns[0]).toBeInTheDocument();

    fireEvent.click(evalBtns[0]);

    expect(api.evaluateInvestigationStressScenario).toHaveBeenCalledWith("inv-stress-test", "sc-2");
  });

  it("switches to Comparative Stress Matrix tab", async () => {
    renderComponent();

    expect(await screen.findByText("Test Your Decision")).toBeInTheDocument();

    // Click matrix tab
    const matrixTab = screen.getByRole("button", { name: /Comparative Stress Matrix/i });
    fireEvent.click(matrixTab);

    expect(
      screen.getByText("Comparative Requirement Degradation Matrix")
    ).toBeInTheDocument();
    expect(screen.getByText("Overall Decision Outcome")).toBeInTheDocument();
  });
});
