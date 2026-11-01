import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import { ConflictPage } from "../pages/ConflictPage";
import * as api from "../lib/api";

// Mock API functions
vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof api>("../lib/api");
  return {
    ...actual,
    listInvestigations: vi.fn(),
    getInvestigationConflicts: vi.fn(),
    analyzeInvestigationConflicts: vi.fn(),
    updateConflictResolution: vi.fn(),
  };
});

describe("Component 05: Evidence Contradiction & Conflict Detection Engine", () => {
  const mockInvestigations: api.Investigation[] = [
    {
      id: "inv-conflict-test",
      research_question: "Does remote work enhance engineering output?",
      status: "completed",
      created_at: "2026-10-30T19:00:00Z",
      sources_count: 2,
      claims_count: 4,
    },
  ];

  const mockConflictsResponse: api.ConflictListResponse = {
    investigation_id: "inv-conflict-test",
    processing_mode: "gemini",
    last_analyzed_at: "2026-10-30T21:00:00Z",
    summary: {
      total_conflicts: 2,
      direct_contradictions: 1,
      numerical_conflicts: 1,
      temporal_conflicts: 0,
      contextual_tensions: 0,
      methodological_disagreements: 0,
      unresolved_conflicts: 2,
      critical_severity: 1,
      high_severity: 1,
      medium_severity: 0,
      low_severity: 0,
      under_review_count: 0,
      resolved_count: 0,
    },
    conflicts: [
      {
        conflict_id: "conf-1",
        investigation_id: "inv-conflict-test",
        claim_a_id: "clm-1",
        claim_b_id: "clm-2",
        claim_a_text: "Remote work significantly increased worker productivity across tech teams.",
        claim_b_text: "Remote work severely decreased worker productivity across tech teams.",
        claim_a_category: "productivity",
        claim_b_category: "productivity",
        source_a_title: "Tech Insights Journal",
        source_b_title: "Audit Bureau Report",
        source_a_url: "https://example.com/journal",
        source_b_url: "https://example.com/audit",
        passage_a_text: "Our survey showed remote work significantly increased worker productivity across tech teams.",
        passage_b_text: "Internal audits proved remote work severely decreased worker productivity across tech teams.",
        passage_a_page: 12,
        passage_b_page: 4,
        passage_a_hash: "a1b2c3d4e5f67890",
        passage_b_hash: "f6e5d4c3b2a10987",
        conflict_type: "DIRECT_CONTRADICTION",
        severity: "CRITICAL",
        explanation: "Direct semantic contradiction on productivity polarity: increased vs decreased.",
        contextual_differences: "Journal analyzed self-reported surveys while Bureau audited git commit frequencies.",
        confidence: 0.96,
        resolution_status: "unresolved",
        reviewer_notes: "",
        recommended_action: "Examine whether self-reporting biased Journal survey results.",
        analysis_method: "gemini_conflict_engine:gemini-flash-lite-latest",
        processing_mode: "gemini",
        created_at: "2026-10-30T21:00:00Z",
        updated_at: "2026-10-30T21:00:00Z",
      },
      {
        conflict_id: "conf-2",
        investigation_id: "inv-conflict-test",
        claim_a_id: "clm-3",
        claim_b_id: "clm-4",
        claim_a_text: "Capital expenditure totaled 15 million dollars.",
        claim_b_text: "Capital expenditure totaled 45 million dollars.",
        source_a_title: "Treasury Budget",
        source_b_title: "Vendor Filing",
        conflict_type: "NUMERICAL_CONFLICT",
        severity: "HIGH",
        explanation: "Numerical clash between budget estimates: 15 million vs 45 million.",
        contextual_differences: "Treasury counted Phase 1 only; Vendor included Phase 1 and 2.",
        confidence: 0.92,
        resolution_status: "unresolved",
        recommended_action: "Verify accounting cut-off dates.",
        analysis_method: "gemini_conflict_engine:gemini-flash-lite-latest",
        processing_mode: "gemini",
        created_at: "2026-10-30T21:00:00Z",
        updated_at: "2026-10-30T21:00:00Z",
      },
    ],
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.listInvestigations).mockResolvedValue(mockInvestigations);
    vi.mocked(api.getInvestigationConflicts).mockResolvedValue(mockConflictsResponse);
  });

  it("renders page header, mode badge, and summary cards", async () => {
    render(
      <BrowserRouter>
        <ConflictPage />
      </BrowserRouter>
    );

    // Verify Title & Subtitle
    expect(screen.getByText("Conflicting Evidence")).toBeInTheDocument();

    // Verify Mode Badge
    await waitFor(() => {
      expect(screen.getByText("AI ANALYSIS ACTIVE")).toBeInTheDocument();
    });

    // Verify KPI summary metrics
    expect(screen.getAllByText("Direct Contradictions").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Numerical Disparities").length).toBeGreaterThanOrEqual(1);
  });

  it("renders conflict list and side-by-side inspector details", async () => {
    render(
      <BrowserRouter>
        <ConflictPage />
      </BrowserRouter>
    );

    // Wait for conflicts to load
    await waitFor(() => {
      expect(screen.getByText("Detected Conflicts (2)")).toBeInTheDocument();
    });

    // Verify claim previews exist
    expect(
      screen.getAllByText(/Remote work significantly increased worker productivity/).length
    ).toBeGreaterThan(0);
    expect(
      screen.getAllByText(/Remote work severely decreased worker productivity/).length
    ).toBeGreaterThan(0);

    // Verify Inspector renders selected conflict details
    expect(screen.getByText("Forensic Contradiction Dossier")).toBeInTheDocument();
    expect(screen.getAllByText("Tech Insights Journal").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Audit Bureau Report").length).toBeGreaterThan(0);
    expect(screen.getByText("Contradiction Rationale")).toBeInTheDocument();
    expect(
      screen.getAllByText(/Direct semantic contradiction on productivity polarity/).length
    ).toBeGreaterThan(0);
    expect(
      screen.getByText("Contextual Variance & Confounding Factors")
    ).toBeInTheDocument();
  });

  it("filters conflicts by search query", async () => {
    render(
      <BrowserRouter>
        <ConflictPage />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByText("Detected Conflicts (2)")).toBeInTheDocument();
    });

    const searchInput = screen.getByPlaceholderText("Search claims, sources, or explanations...");
    fireEvent.change(searchInput, { target: { value: "Capital expenditure" } });

    // Should only show the numerical conflict now
    expect(screen.getByText("Detected Conflicts (1)")).toBeInTheDocument();
    expect(screen.getByText(/Capital expenditure totaled 15 million/)).toBeInTheDocument();
  });

  it("allows analyst to update resolution status and save notes", async () => {
    const updatedConflict: api.ConflictItem = {
      ...mockConflictsResponse.conflicts[0],
      resolution_status: "resolved",
      reviewer_notes: "Survey bias verified and documented.",
    };

    vi.mocked(api.updateConflictResolution).mockResolvedValue(updatedConflict);

    render(
      <BrowserRouter>
        <ConflictPage />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByText("Forensic Contradiction Dossier")).toBeInTheDocument();
    });

    // Click 'Resolved' resolution button
    const resolvedBtn = screen.getByRole("button", { name: "Resolved" });
    fireEvent.click(resolvedBtn);

    // Enter notes
    const textarea = screen.getByPlaceholderText(/Enter audit notes on why this conflict was resolved/);
    fireEvent.change(textarea, { target: { value: "Survey bias verified and documented." } });

    // Save verdict
    const saveBtn = screen.getByRole("button", { name: /Save Resolution Verdict/ });
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(api.updateConflictResolution).toHaveBeenCalledWith(
        "inv-conflict-test",
        "conf-1",
        {
          resolution_status: "resolved",
          reviewer_notes: "Survey bias verified and documented.",
        }
      );
    });

    await waitFor(() => {
      expect(
        screen.getByText("Resolution status and forensic notes saved successfully.")
      ).toBeInTheDocument();
    });
  });
});
