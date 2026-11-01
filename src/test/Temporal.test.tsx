import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { TemporalPage } from "../pages/TemporalPage";
import * as api from "../lib/api";

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual("../lib/api");
  return {
    ...actual,
    listInvestigations: vi.fn(),
    getInvestigationSources: vi.fn(),
    getInvestigationClaims: vi.fn(),
    getInvestigationConflicts: vi.fn(),
  };
});

describe("Component 08 / Outcome 06: Timeline & Freshness Intelligence", () => {
  const mockInvestigations: api.Investigation[] = [
    {
      id: "inv-test-1",
      research_question: "Evaluating solar expansion feasibility in Southeast Asia",
      status: "ready",
      created_at: "2026-10-31T10:00:00Z",
      sources_count: 3,
      claims_count: 6,
    },
  ];

  const mockSources: api.Source[] = [
    {
      id: "src-1",
      investigation_id: "inv-test-1",
      source_type: "web",
      original_url: "https://example.org/recent-solar",
      title: "ASEAN Renewable Energy Report 2026",
      publication_date: "2026-06-01",
      retrieved_at: "2026-10-31T10:05:00Z",
      extraction_status: "completed",
      passages_count: 4,
      claims_count: 3,
      freshness_status: "Date Available",
      freshness_explanation: "Published 152 days ago, within the 365-day freshness window.",
      days_old: 152,
    },
    {
      id: "src-2",
      investigation_id: "inv-test-1",
      source_type: "pdf",
      original_url: "historical_grid_audit_2023.pdf",
      title: "Historical Grid Audit 2023",
      publication_date: "2023-04-15",
      retrieved_at: "2026-10-31T10:06:00Z",
      extraction_status: "completed",
      passages_count: 6,
      claims_count: 2,
      freshness_status: "Potentially Outdated",
      freshness_explanation: "Source was published 1295 days ago, exceeding the 365-day threshold.",
      days_old: 1295,
    },
    {
      id: "src-3",
      investigation_id: "inv-test-1",
      source_type: "web",
      original_url: "https://example.org/undated-note",
      title: "Internal Policy Brief",
      publication_date: "",
      retrieved_at: "2026-10-31T10:07:00Z",
      extraction_status: "completed",
      passages_count: 2,
      claims_count: 1,
      freshness_status: "Undated Source",
      freshness_explanation: "No verifiable publication date could be extracted from metadata.",
      days_old: undefined,
    },
  ];

  const mockClaims: api.Claim[] = [
    {
      id: "clm-1",
      investigation_id: "inv-test-1",
      source_id: "src-1",
      passage_id: "pas-1",
      claim_text: "Solar capacity grew by 28% in 2025 across regional hubs.",
      category: "statistical",
      extraction_method: "rule-based",
      extraction_confidence: 0.95,
      created_at: "2026-10-31T10:05:00Z",
    },
  ];

  const mockConflicts: api.ConflictListResponse = {
    investigation_id: "inv-test-1",
    processing_mode: "fallback",
    conflicts: [],
    summary: {
      total_conflicts: 0,
      direct_contradictions: 0,
      numerical_conflicts: 0,
      temporal_conflicts: 0,
      contextual_tensions: 0,
      methodological_disagreements: 0,
      unresolved_conflicts: 0,
      critical_severity: 0,
      high_severity: 0,
      medium_severity: 0,
      low_severity: 0,
      under_review_count: 0,
      resolved_count: 0,
    },
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.listInvestigations).mockResolvedValue(mockInvestigations);
    vi.mocked(api.getInvestigationSources).mockResolvedValue(mockSources);
    vi.mocked(api.getInvestigationClaims).mockResolvedValue(mockClaims);
    vi.mocked(api.getInvestigationConflicts).mockResolvedValue(mockConflicts);
  });

  it("renders page header, KPI cards, and decay model controls", async () => {
    render(
      <MemoryRouter>
        <TemporalPage />
      </MemoryRouter>
    );

    // Verify Header
    expect(screen.getByText(/Timeline & Freshness Intelligence/i)).toBeInTheDocument();

    // Verify Decay model
    expect(screen.getByText(/Exponential Evidence Confidence Decay Model/i)).toBeInTheDocument();
    expect(screen.getByText(/365d \(Standard\)/i)).toBeInTheDocument();

    // Wait for sources to load and KPI cards to compute
    await waitFor(() => {
      expect(screen.getByText("ASEAN Renewable Energy Report 2026")).toBeInTheDocument();
      expect(screen.getByText("Historical Grid Audit 2023")).toBeInTheDocument();
    });

    // Check freshness badges
    expect(screen.getAllByText(/Date Available/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/Potentially Outdated/i).length).toBeGreaterThanOrEqual(1);

    // Check KPI counts
    expect(screen.getByText("Dated Sources")).toBeInTheDocument();
    expect(screen.getByText("Undated Sources")).toBeInTheDocument();
  });
});
