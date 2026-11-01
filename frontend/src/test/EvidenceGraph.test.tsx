import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { GraphToolbar } from "../components/graph/GraphToolbar";
import { GraphDetailsPanel } from "../components/graph/GraphDetailsPanel";
import type { GraphNode, GraphEdge } from "../lib/api";

describe("Component 04: Evidence Dependency Graph - Frontend Components", () => {
  const mockInvestigations = [
    {
      id: "inv-123",
      research_question: "Does rural scholarship improve enrollment access?",
      status: "analyzed",
      created_at: "2026-10-30T20:00:00Z",
      sources_count: 2,
      claims_count: 5,
      has_contract: true,
    },
  ];

  const mockSummary = {
    total_nodes: 10,
    total_edges: 8,
    contract_nodes: 1,
    requirement_nodes: 3,
    evidence_requirement_nodes: 3,
    claim_nodes: 2,
    passage_nodes: 1,
    source_nodes: 1,
    directly_relevant_links: 2,
    partially_relevant_links: 0,
    contextual_links: 0,
  };

  it("renders the GraphToolbar with investigation selector, mode badge, and filters", () => {
    const handleSelectInv = vi.fn();
    const handleSearch = vi.fn();
    const handleFilter = vi.fn();
    const handleAnalyze = vi.fn();

    render(
      <GraphToolbar
        investigations={mockInvestigations}
        selectedInvestigationId="inv-123"
        onSelectInvestigation={handleSelectInv}
        searchQuery=""
        onSearchChange={handleSearch}
        activeTypeFilter="all"
        onTypeFilterChange={handleFilter}
        processingMode="gemini"
        summary={mockSummary}
        onRunAnalysis={handleAnalyze}
        isAnalyzing={false}
        onFitView={vi.fn()}
        onResetView={vi.fn()}
        hasContract={true}
        claimsCount={5}
      />
    );

    // Verify investigation selector
    expect(screen.getByText(/Investigation:/i)).toBeInTheDocument();
    expect(screen.getByText(/Does rural scholarship improve enrollment access/i)).toBeInTheDocument();

    // Verify AI Badge
    expect(screen.getByText(/AI RELEVANCE ACTIVE/i)).toBeInTheDocument();

    // Verify Analysis Button
    expect(screen.getByText(/Remap Evidence/i)).toBeInTheDocument();

    // Verify Filter pills
    expect(screen.getByText("All Nodes")).toBeInTheDocument();
    expect(screen.getByText("Criteria")).toBeInTheDocument();
    expect(screen.getByText("Requirements")).toBeInTheDocument();
    expect(screen.getByText("Claims")).toBeInTheDocument();
    expect(screen.getByText("Passages")).toBeInTheDocument();
    expect(screen.getByText("Sources")).toBeInTheDocument();

    // Trigger filter change
    fireEvent.click(screen.getByText("Claims"));
    expect(handleFilter).toHaveBeenCalledWith("atomic_claim");

    // Trigger analysis
    fireEvent.click(screen.getByText(/Remap Evidence/i));
    expect(handleAnalyze).toHaveBeenCalled();
  });

  it("renders the GraphDetailsPanel with full claim text and cryptographic provenance", () => {
    const mockClaimNode: GraphNode = {
      id: "claim_c1",
      type: "atomic_claim",
      label: "Rural college enrollment increased by 34%",
      record_id: "c1-uuid-9999",
      metadata: {
        claim_text: "The National Rural Higher Education Initiative achieved a 34 percent increase in first-generation college enrollment.",
        category: "statistical",
        confidence: 0.94,
        extraction_method: "gemini_llm_structured",
        passage_id: "pas-1-uuid",
      },
    };

    const mockEdges: GraphEdge[] = [
      {
        id: "edge_c1_req1",
        source: "claim_c1",
        target: "req_r1",
        relationship: "RELATES_TO",
        origin: "gemini",
        confidence: 0.92,
        metadata: {
          relevance: "DIRECTLY_RELEVANT",
          explanation: "Provides quantitative enrollment increase matching requirement criteria.",
        },
      },
    ];

    const mockAllNodes: GraphNode[] = [
      mockClaimNode,
      {
        id: "req_r1",
        type: "decision_requirement",
        label: "Quantitative Enrollment Outcomes",
        record_id: "r1-uuid",
        metadata: {},
      },
    ];

    const handleClose = vi.fn();
    const handleSelectNode = vi.fn();

    render(
      <GraphDetailsPanel
        node={mockClaimNode}
        edges={mockEdges}
        allNodes={mockAllNodes}
        onClose={handleClose}
        onSelectNode={handleSelectNode}
      />
    );

    // Verify header and record id
    expect(screen.getAllByText(/ATOMIC CLAIM/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/c1-uuid-9999/i)).toBeInTheDocument();

    // Verify full claim text
    expect(
      screen.getByText(
        /"The National Rural Higher Education Initiative achieved a 34 percent increase in first-generation college enrollment."/i
      )
    ).toBeInTheDocument();

    // Verify category and confidence
    expect(screen.getByText("statistical")).toBeInTheDocument();
    expect(screen.getByText("94%")).toBeInTheDocument();

    // Verify connected edge explanation
    expect(
      screen.getByText(/Provides quantitative enrollment increase matching requirement criteria/i)
    ).toBeInTheDocument();
  });

  it("renders GraphDetailsPanel with original passage text and SHA-256 hash", () => {
    const mockPassageNode: GraphNode = {
      id: "passage_p1",
      type: "source_passage",
      label: "Passage (p. 1)",
      record_id: "p1-uuid-4444",
      metadata: {
        passage_text: "In fiscal year 2024, the scholarship initiative disbursed grants totaling $45 million...",
        page_number: 1,
        paragraph_index: 2,
        start_offset: 120,
        end_offset: 350,
        sha256_hash: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
      },
    };

    render(
      <GraphDetailsPanel
        node={mockPassageNode}
        edges={[]}
        allNodes={[mockPassageNode]}
        onClose={vi.fn()}
        onSelectNode={vi.fn()}
      />
    );

    // Verify passage details
    expect(screen.getByText(/SOURCE PASSAGE/i)).toBeInTheDocument();
    expect(screen.getByText(/Page 1/i)).toBeInTheDocument();
    expect(screen.getByText(/In fiscal year 2024/i)).toBeInTheDocument();
    expect(screen.getByText(/e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855/i)).toBeInTheDocument();
  });
});
