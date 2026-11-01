import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { FragilityPage } from "../pages/FragilityPage";
import * as api from "../lib/api";

// Mock API functions
vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof api>("../lib/api");
  return {
    ...actual,
    listInvestigations: vi.fn(),
    getLatestFragility: vi.fn(),
    runFragilityAnalysis: vi.fn(),
    getFragilityStatus: vi.fn(),
    simulateSensitivity: vi.fn(),
    getSensitivityResults: vi.fn(),
    getFragilityRecommendations: vi.fn(),
    getFragilityMethodology: vi.fn(),
  };
});

describe("Component 09: Decision Fragility Index & Sensitivity Scoring", () => {
  const mockInvestigations: api.Investigation[] = [
    {
      id: "inv-frag-001",
      research_question: "Should we acquire HyperScale Cloud Infrastructure?",
      status: "active",
      created_at: "2026-10-31T00:00:00Z",
      sources_count: 3,
      claims_count: 8,
    },
  ];

  const mockFragilityResult: api.DecisionFragilityResult = {
    id: "frag-res-101",
    run_id: "run-101",
    investigation_id: "inv-frag-001",
    methodology_version: "v1.2.0-deterministic",
    dfi_score: 24.0,
    classification: "LOW FRAGILITY",
    is_provisional: false,
    provisional_reasons: [],
    guardrail_active: false,
    guardrail_reason: undefined,
    unsubstantiated_critical_requirements: ["Data Center Redundancy (Status: PARTIAL)"],
    d1_coverage: 30.0,
    d2_assumptions: 40.0,
    d3_conflicts: 20.0,
    d4_stress: 15.0,
    d5_concentration: 10.0,
    dimensions: {
      d1_coverage: {
        dimension_key: "d1_coverage",
        dimension_name: "Evidence Coverage Fragility",
        score: 30.0,
        weight: 0.30,
        weighted_contribution: 9.0,
        status: "ASSESSED",
        explanation: "Evaluated 4 requirement(s) across sufficiency coverage states.",
        metrics: { requirements_count: 4 },
      },
      d2_assumptions: {
        dimension_key: "d2_assumptions",
        dimension_name: "Assumption Fragility",
        score: 40.0,
        weight: 0.15,
        weighted_contribution: 6.0,
        status: "ASSESSED",
        explanation: "Evaluated recorded contract assumptions.",
        metrics: { assumptions_count: 2 },
      },
      d3_conflicts: {
        dimension_key: "d3_conflicts",
        dimension_name: "Conflict Fragility",
        score: 20.0,
        weight: 0.25,
        weighted_contribution: 5.0,
        status: "ASSESSED",
        explanation: "Evaluated 1 conflict record(s).",
        metrics: { conflicts_count: 1 },
      },
      d4_stress: {
        dimension_key: "d4_stress",
        dimension_name: "Stress Test Fragility",
        score: 15.0,
        weight: 0.20,
        weighted_contribution: 3.0,
        status: "ASSESSED",
        explanation: "Evaluated 2 stress scenarios. Score: 15.0.",
        metrics: { evaluated_scenarios_count: 2 },
      },
      d5_concentration: {
        dimension_key: "d5_concentration",
        dimension_name: "Requirement Sensitivity Concentration",
        score: 10.0,
        weight: 0.10,
        weighted_contribution: 1.0,
        status: "ASSESSED",
        explanation: "Concentration profile: DISTRIBUTED.",
        metrics: { concentration_label: "DISTRIBUTED" },
      },
    },
    attribution_ledger: [
      {
        item_id: "led-1",
        dimension: "d1_coverage",
        category: "REQUIREMENT_GAP",
        entity_id: "req-1",
        entity_type: "requirement",
        entity_title: "Annual Recurring Revenue Verification",
        base_penalty: 40.0,
        multiplier: 0.35,
        net_dimension_points: 14.0,
        net_dfi_contribution: 4.2,
        rationale: "Requirement has PARTIAL sufficiency state.",
      },
    ],
    explanation_text: "DECISION FRAGILITY ANALYSIS (DFI: 24.0 / 100.0) — CLASSIFICATION: LOW FRAGILITY",
    processing_mode: "gemini",
    created_at: "2026-10-31T02:00:00Z",
  };

  const mockRecommendations: api.EvidenceImprovementRecommendation[] = [
    {
      id: "rec-1",
      investigation_id: "inv-frag-001",
      run_id: "run-101",
      recommendation_type: "FILL_CRITICAL_GAP",
      target_entity_id: "req-1",
      target_entity_type: "requirement",
      title: "Fill Critical Gap: Data Center Redundancy",
      description: "Ingest independent audit reports verifying SLA tiers.",
      projected_dfi_reduction: 6.5,
      is_hypothetical_projection: true,
      priority: "HIGH",
      effort_estimate: "HIGH",
      action_steps: ["Procure Tier III audit certificate", "Link to requirement"],
      created_at: "2026-10-31T02:00:00Z",
    },
  ];

  const mockSimulations: api.SensitivityExperimentResult[] = [
    {
      id: "sim-1",
      investigation_id: "inv-frag-001",
      experiment_type: "SIM_GAP_CORROBORATION",
      is_hypothetical: true,
      target_entity_id: "req-1",
      target_entity_type: "requirement",
      target_entity_title: "Data Center Redundancy",
      baseline_dfi: 24.0,
      simulated_dfi: 17.5,
      delta_dfi: -6.5,
      baseline_classification: "LOW FRAGILITY",
      simulated_classification: "LOW FRAGILITY",
      simulated_guardrail_active: false,
      simulated_guardrail_reason: undefined,
      simulation_parameters: {},
      narrative_impact: "Fragility decreased by 6.5 points.",
      created_at: "2026-10-31T02:05:00Z",
    },
  ];

  const mockMethodology: api.FragilityMethodology = {
    version: "v1.2.0-deterministic",
    weights: {
      d1_coverage: 0.30,
      d2_assumptions: 0.15,
      d3_conflicts: 0.25,
      d4_stress: 0.20,
      d5_concentration: 0.10,
    },
    deficit_penalties: { NO_EVIDENCE: 1.0 },
    conflict_penalties: { CRITICAL: 35.0 },
    stress_shift_penalties: { CRITICAL_FAILURE: 30.0 },
    guardrail_criteria: "CRITICAL requirement with NO_EVIDENCE triggers override.",
    provisional_policy: "Unassessed dimensions held at 0.0.",
    rounding_rule: "ROUND_HALF_UP to 1 decimal place.",
    epistemic_disclaimer: "Scores quantify empirical support within the ingested boundary.",
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.listInvestigations).mockResolvedValue(mockInvestigations);
    vi.mocked(api.getLatestFragility).mockResolvedValue(mockFragilityResult);
    vi.mocked(api.getFragilityStatus).mockResolvedValue({
      investigation_id: "inv-frag-001",
      has_result: true,
      dfi_score: 24.0,
      classification: "LOW FRAGILITY",
      is_provisional: false,
      guardrail_active: false,
      has_unsubstantiated_critical: true,
      is_stale: false,
      is_indeterminate: false,
    });
    vi.mocked(api.getSensitivityResults).mockResolvedValue({
      investigation_id: "inv-frag-001",
      baseline_dfi: 24.0,
      baseline_classification: "LOW FRAGILITY",
      experiments: mockSimulations,
    });
    vi.mocked(api.getFragilityRecommendations).mockResolvedValue({
      investigation_id: "inv-frag-001",
      total_recommendations: 1,
      max_projected_reduction: 6.5,
      recommendations: mockRecommendations,
    });
    vi.mocked(api.getFragilityMethodology).mockResolvedValue(mockMethodology);
  });

  it("renders page header and processing mode pill", async () => {
    render(
      <MemoryRouter>
        <FragilityPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText("Decision Fragility Index")).toBeDefined();
      expect(screen.getByText("Gemini Synthesized")).toBeDefined();
    });
  });

  it("renders composite DFI score and all 5 dimension cards", async () => {
    render(
      <MemoryRouter>
        <FragilityPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText("24.0")).toBeDefined();
      expect(screen.getByText("LOW FRAGILITY")).toBeDefined();
      expect(screen.getByText("Evidence Coverage Fragility")).toBeDefined();
      expect(screen.getByText("Assumption Fragility")).toBeDefined();
      expect(screen.getByText("Conflict Fragility")).toBeDefined();
      expect(screen.getByText("Stress Test Fragility")).toBeDefined();
      expect(screen.getByText("Requirement Sensitivity Concentration")).toBeDefined();
    });
  });

  it("renders unsubstantiated critical requirements warning banner", async () => {
    render(
      <MemoryRouter>
        <FragilityPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(
        screen.getByText(/Mandatory Substantiation Warning: 1 Critical Requirement\(s\) Not Fully Substantiated/i)
      ).toBeDefined();
      expect(screen.getByText("Data Center Redundancy (Status: PARTIAL)")).toBeDefined();
    });
  });

  it("renders Critical Deficit Guardrail banner when guardrail is active", async () => {
    vi.mocked(api.getLatestFragility).mockResolvedValueOnce({
      ...mockFragilityResult,
      guardrail_active: true,
      classification: "CRITICAL DEFICIT GUARDRAIL: UNGROUNDED FOUNDATION (DFI: 30.0)",
      guardrail_reason: "Critical requirement has NO_EVIDENCE.",
    });

    render(
      <MemoryRouter>
        <FragilityPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/Critical Deficit Guardrail Triggered/i)).toBeDefined();
      expect(screen.getByText("FOUNDATION UNGROUNDED")).toBeDefined();
      expect(screen.getByText("Critical requirement has NO_EVIDENCE.")).toBeDefined();
    });
  });

  it("switches tabs between Attribution Ledger, Simulator, Recommendations, and Methodology", async () => {
    render(
      <MemoryRouter>
        <FragilityPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText("Annual Recurring Revenue Verification")).toBeDefined();
    });

    // Switch to Simulator tab
    const simTab = screen.getByRole("button", { name: /What-If Sensitivity Simulator/i });
    fireEvent.click(simTab);
    expect(screen.getByText("Configure Counterfactual Experiment")).toBeDefined();
    expect(screen.getByText("In-Memory Sandbox Guarantee")).toBeDefined();

    // Switch to Recommendations tab
    const recTab = screen.getByRole("button", { name: /Actionable Evidence Improvements/i });
    fireEvent.click(recTab);
    expect(screen.getByText("Fill Critical Gap: Data Center Redundancy")).toBeDefined();
    expect(screen.getByText("-6.5 DFI Reduction")).toBeDefined();

    // Switch to Methodology tab
    const methTab = screen.getByRole("button", { name: /Analytical Narrative & Methodology/i });
    fireEvent.click(methTab);
    expect(screen.getByText(/Methodology Specification: v1.2.0-deterministic/i)).toBeDefined();
    expect(screen.getByText(/Epistemic Boundary Disclaimer:/i)).toBeDefined();
  });
});
