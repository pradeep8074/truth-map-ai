import { useState, useEffect, useMemo, useCallback } from "react";
import { useSearchParams, Link } from "react-router-dom";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  MarkerType,
  type Node,
  type Edge,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import {
  Network,
  AlertCircle,
  Sparkles,
  Target,
  RefreshCw,
  FolderOpen,
} from "lucide-react";
import { Button } from "@/components/ui/Button";
import { CustomGraphNode } from "@/components/graph/CustomGraphNode";
import { GraphDetailsPanel } from "@/components/graph/GraphDetailsPanel";
import { GraphToolbar } from "@/components/graph/GraphToolbar";

import {
  listInvestigations,
  getEvidenceGraph,
  analyzeEvidenceGraph,
  type Investigation,
  type EvidenceGraphData,
  type GraphNode,
  type GraphNodeType,
} from "@/lib/api";

const NODE_TYPES: any = {
  custom: CustomGraphNode,
};

// Topological Level Ordering for Deterministic Hierarchical Layout
const LEVEL_CONFIG: Record<GraphNodeType, { level: number; y: number; nodeWidth: number }> = {
  decision_contract: { level: 0, y: 50, nodeWidth: 300 },
  decision_requirement: { level: 1, y: 260, nodeWidth: 300 },
  evidence_requirement: { level: 2, y: 480, nodeWidth: 300 },
  atomic_claim: { level: 3, y: 720, nodeWidth: 300 },
  source_passage: { level: 4, y: 980, nodeWidth: 300 },
  source_document: { level: 5, y: 1240, nodeWidth: 300 },
};

export function EvidenceGraphPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [investigations, setInvestigations] = useState<Investigation[]>([]);
  const [selectedInvId, setSelectedInvId] = useState<string>("");
  const [graphData, setGraphData] = useState<EvidenceGraphData | null>(null);

  const [loading, setLoading] = useState(true);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [typeFilter, setTypeFilter] = useState<GraphNodeType | "all">("all");

  const [reactFlowInstance, setReactFlowInstance] = useState<any>(null);

  // 1. Fetch investigations list
  useEffect(() => {
    async function loadInvestigations() {
      try {
        setLoading(true);
        const invs = await listInvestigations();
        setInvestigations(invs);

        const urlInvId = searchParams.get("inv");
        if (urlInvId && invs.some((i) => i.id === urlInvId)) {
          setSelectedInvId(urlInvId);
        } else if (invs.length > 0) {
          setSelectedInvId(invs[0].id);
        }
      } catch (err: any) {
        setError(err.message || "Failed to load investigations");
      } finally {
        setLoading(false);
      }
    }
    loadInvestigations();
  }, [searchParams]);

  // 2. Load graph data when selected investigation changes
  const loadGraph = useCallback(async (invId: string) => {
    if (!invId) return;
    try {
      setLoading(true);
      setError(null);
      const data = await getEvidenceGraph(invId);
      setGraphData(data);
      setSelectedNodeId(null);
    } catch (err: any) {
      setError(err.message || "Failed to load evidence graph");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (selectedInvId) {
      loadGraph(selectedInvId);
      setSearchParams({ inv: selectedInvId });
    }
  }, [selectedInvId, loadGraph, setSearchParams]);

  // 3. Trigger Gemini / Fallback relationship analysis
  const handleRunAnalysis = async () => {
    if (!selectedInvId || isAnalyzing) return;
    try {
      setIsAnalyzing(true);
      setError(null);
      const updatedGraph = await analyzeEvidenceGraph(selectedInvId);
      setGraphData(updatedGraph);
    } catch (err: any) {
      setError(err.message || "Relevance analysis failed");
    } finally {
      setIsAnalyzing(false);
    }
  };

  // Find connected nodes when a node is selected
  const connectedNodeIds = useMemo(() => {
    if (!selectedNodeId || !graphData) return new Set<string>();
    const ids = new Set<string>();
    ids.add(selectedNodeId);

    graphData.edges.forEach((edge) => {
      if (edge.source === selectedNodeId) {
        ids.add(edge.target);
      }
      if (edge.target === selectedNodeId) {
        ids.add(edge.source);
      }
    });

    return ids;
  }, [selectedNodeId, graphData]);

  // Compute Layout Positions for Nodes deterministically
  const { flowNodes, flowEdges } = useMemo(() => {
    if (!graphData || !graphData.nodes.length) {
      return { flowNodes: [], flowEdges: [] };
    }

    // Group nodes by type
    const grouped: Record<GraphNodeType, GraphNode[]> = {
      decision_contract: [],
      decision_requirement: [],
      evidence_requirement: [],
      atomic_claim: [],
      source_passage: [],
      source_document: [],
    };

    graphData.nodes.forEach((n) => {
      if (grouped[n.type]) {
        grouped[n.type].push(n);
      }
    });

    const HORIZONTAL_GAP = 60;
    const NODE_WIDTH = 288; // w-72 = 18rem = 288px

    // Find the maximum row width to center all levels
    let maxRowWidth = 0;
    Object.values(grouped).forEach((row) => {
      const rowWidth = row.length * (NODE_WIDTH + HORIZONTAL_GAP);
      if (rowWidth > maxRowWidth) maxRowWidth = rowWidth;
    });

    const nodes: Node[] = [];

    // Lay out each level
    Object.entries(grouped).forEach(([typeStr, levelNodes]) => {
      const type = typeStr as GraphNodeType;
      const config = LEVEL_CONFIG[type];
      const count = levelNodes.length;
      if (count === 0) return;

      const totalRowWidth = count * NODE_WIDTH + (count - 1) * HORIZONTAL_GAP;
      const startX = (maxRowWidth - totalRowWidth) / 2;

      levelNodes.forEach((node, idx) => {
        const x = startX + idx * (NODE_WIDTH + HORIZONTAL_GAP);
        const y = config.y;

        // Filtering & search logic
        const matchesSearch =
          !searchQuery ||
          node.label.toLowerCase().includes(searchQuery.toLowerCase()) ||
          JSON.stringify(node.metadata).toLowerCase().includes(searchQuery.toLowerCase());

        const matchesType = typeFilter === "all" || node.type === typeFilter;
        const isDimmed = !matchesSearch || !matchesType || (selectedNodeId !== null && !connectedNodeIds.has(node.id));

        nodes.push({
          id: node.id,
          type: "custom",
          position: { x, y },
          data: {
            label: node.label,
            type: node.type,
            recordId: node.record_id,
            metadata: node.metadata,
            isSelected: selectedNodeId === node.id,
            isHighlighted: connectedNodeIds.has(node.id) && selectedNodeId !== node.id,
            isDimmed,
          },
        });
      });
    });

    // Lay out edges
    const edges: Edge[] = graphData.edges.map((edge) => {
      const isConnected =
        selectedNodeId === null ||
        edge.source === selectedNodeId ||
        edge.target === selectedNodeId;

      let strokeColor = "#475569";
      let strokeWidth = 1.5;
      let strokeDasharray: string | undefined = undefined;
      let animated = false;

      if (edge.relationship === "HAS_REQUIREMENT") {
        strokeColor = "#3B82F6"; // blue
        strokeWidth = 2;
      } else if (edge.relationship === "REQUIRES_EVIDENCE") {
        strokeColor = "#14B8A6"; // teal
        strokeDasharray = "5,5";
      } else if (edge.relationship === "RELATES_TO") {
        const relevance = edge.metadata?.relevance;
        if (relevance === "DIRECTLY_RELEVANT") {
          strokeColor = "#10B981"; // emerald
          strokeWidth = 2.5;
          animated = true;
        } else if (relevance === "PARTIALLY_RELEVANT") {
          strokeColor = "#F59E0B"; // amber
          strokeWidth = 2;
        } else {
          strokeColor = "#A855F7"; // purple
          strokeDasharray = "4,4";
        }
      } else if (edge.relationship === "EXTRACTED_FROM") {
        strokeColor = "#059669";
      } else if (edge.relationship === "BELONGS_TO_SOURCE") {
        strokeColor = "#6366F1";
        strokeDasharray = "4,4";
      } else if (edge.relationship === "CONFLICTS_WITH") {
        strokeColor = "#EF4444"; // red for evidence conflict
        strokeWidth = 2.5;
        strokeDasharray = "4,4";
        animated = true;
      }

      return {
        id: edge.id,
        source: edge.source,
        target: edge.target,
        type: "smoothstep",
        animated,
        style: {
          stroke: strokeColor,
          strokeWidth: isConnected && selectedNodeId ? strokeWidth + 1 : strokeWidth,
          opacity: isConnected ? 1 : 0.15,
          strokeDasharray,
        },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: strokeColor,
          width: 16,
          height: 16,
        },
        data: edge.metadata,
      };
    });

    return { flowNodes: nodes, flowEdges: edges };
  }, [graphData, selectedNodeId, connectedNodeIds, searchQuery, typeFilter]);

  const [nodes, setNodes, onNodesChange] = useNodesState(flowNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(flowEdges);

  useEffect(() => {
    setNodes(flowNodes);
    setEdges(flowEdges);
  }, [flowNodes, flowEdges, setNodes, setEdges]);

  // Fit view helper
  const handleFitView = useCallback(() => {
    if (reactFlowInstance) {
      reactFlowInstance.fitView({ padding: 0.2, duration: 600 });
    }
  }, [reactFlowInstance]);

  const handleResetView = useCallback(() => {
    setSelectedNodeId(null);
    setSearchQuery("");
    setTypeFilter("all");
    if (reactFlowInstance) {
      reactFlowInstance.fitView({ padding: 0.2, duration: 500 });
    }
  }, [reactFlowInstance]);

  // Click on a node
  const onNodeClick = useCallback((_: any, node: Node) => {
    setSelectedNodeId((prev) => (prev === node.id ? null : node.id));
  }, []);

  const activeInvestigation = investigations.find((i) => i.id === selectedInvId);
  const selectedNode = useMemo(() => {
    if (!selectedNodeId || !graphData) return null;
    return graphData.nodes.find((n) => n.id === selectedNodeId) || null;
  }, [selectedNodeId, graphData]);

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)] overflow-hidden bg-dark-950">
      {/* Top Controls Toolbar */}
      <GraphToolbar
        investigations={investigations}
        selectedInvestigationId={selectedInvId}
        onSelectInvestigation={setSelectedInvId}
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        activeTypeFilter={typeFilter}
        onTypeFilterChange={setTypeFilter}
        processingMode={graphData?.processing_mode || "pending"}
        summary={
          graphData?.summary || {
            total_nodes: 0,
            total_edges: 0,
            contract_nodes: 0,
            requirement_nodes: 0,
            evidence_requirement_nodes: 0,
            claim_nodes: 0,
            passage_nodes: 0,
            source_nodes: 0,
            directly_relevant_links: 0,
            partially_relevant_links: 0,
            contextual_links: 0,
          }
        }
        onRunAnalysis={handleRunAnalysis}
        isAnalyzing={isAnalyzing}
        onFitView={handleFitView}
        onResetView={handleResetView}
        hasContract={Boolean(activeInvestigation?.has_contract || graphData?.summary?.contract_nodes)}
        claimsCount={activeInvestigation?.claims_count || graphData?.summary?.claim_nodes || 0}
      />

      {/* Analysis Callout Banner when relationships are pending */}
      {graphData && graphData.processing_mode === "pending" && graphData.summary.claim_nodes > 0 && graphData.summary.requirement_nodes > 0 && (
        <div className="bg-primary-950/60 border-b border-primary-500/30 px-4 py-2 flex items-center justify-between text-xs text-primary-200">
          <div className="flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-primary-400 shrink-0" />
            <span>
              <strong>Topological Evidence Ready:</strong> Decision Requirements and Atomic Claims are extracted. Run Gemini Relevance Analysis to map empirical load-bearing edges.
            </span>
          </div>
          <Button
            size="sm"
            variant="primary"
            onClick={handleRunAnalysis}
            disabled={isAnalyzing}
            className="h-7 text-xs bg-primary-600 hover:bg-primary-500 text-white gap-1"
          >
            <Sparkles className="w-3 h-3 text-teal-300" />
            Analyze Now
          </Button>
        </div>
      )}

      {/* Main Canvas Area */}
      <div className="flex-1 relative flex overflow-hidden">
        {loading && (
          <div className="absolute inset-0 bg-dark-950/80 backdrop-blur z-30 flex items-center justify-center">
            <div className="flex flex-col items-center gap-3 text-slate-300">
              <RefreshCw className="w-8 h-8 text-primary-400 animate-spin" />
              <p className="text-sm font-medium">Constructing Evidence Dependency Graph...</p>
            </div>
          </div>
        )}

        {error && (
          <div className="absolute top-4 left-1/2 -translate-x-1/2 z-30 bg-red-950/90 border border-red-500/50 text-red-200 px-4 py-2 rounded-lg text-xs shadow-xl flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0 text-red-400" />
            <span>{error}</span>
          </div>
        )}

        {/* Empty State when no nodes exist */}
        {!loading && (!graphData || graphData.nodes.length === 0) && (
          <div className="flex-1 flex flex-col items-center justify-center p-8 text-center bg-dark-950">
            <div className="w-16 h-16 rounded-2xl bg-dark-800 border border-dark-700 flex items-center justify-center mb-4 text-slate-400">
              <Network className="w-8 h-8 text-primary-400" />
            </div>
            <h3 className="text-lg font-semibold text-slate-100 mb-1">
              No Evidence Dependency Graph Available
            </h3>
            <p className="text-sm text-slate-400 max-w-md mb-6 leading-relaxed">
              To construct the evidence graph, you must first ingest sources and compile a Decision Contract for this investigation.
            </p>
            <div className="flex items-center gap-3">
              <Link to="/decision-contract">
                <Button variant="primary" className="gap-2 text-xs">
                  <Target className="w-3.5 h-3.5" />
                  Compile Decision Contract
                </Button>
              </Link>
              <Link to="/investigations">
                <Button variant="secondary" className="gap-2 text-xs">
                  <FolderOpen className="w-3.5 h-3.5" />
                  Ingest Sources
                </Button>
              </Link>
            </div>
          </div>
        )}

        {/* React Flow Canvas */}
        {graphData && graphData.nodes.length > 0 && (
          <div className="flex-1 h-full bg-[#070b14] relative">
            <ReactFlow
              nodes={nodes}
              edges={edges}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              onNodeClick={onNodeClick}
              nodeTypes={NODE_TYPES}
              onInit={setReactFlowInstance}
              fitView
              minZoom={0.15}
              maxZoom={2.0}
              defaultEdgeOptions={{ type: "smoothstep" }}
              className="bg-[#070b14]"
            >
              <Background color="#1e293b" gap={24} size={1} />
              <Controls className="!bg-dark-800 !border-dark-700 !text-slate-300" />
              <MiniMap
                nodeColor={(node: any) => {
                  const t = node.data?.type;
                  if (t === "decision_contract") return "#8B5CF6";
                  if (t === "decision_requirement") return "#3B82F6";
                  if (t === "evidence_requirement") return "#14B8A6";
                  if (t === "atomic_claim") return "#10B981";
                  if (t === "source_passage") return "#F59E0B";
                  return "#6366F1";
                }}
                className="!bg-dark-900 !border-dark-700 rounded-lg shadow-xl"
                maskColor="rgba(11, 18, 32, 0.75)"
              />
            </ReactFlow>

            {/* Bottom Legend */}
            <div className="absolute bottom-4 left-4 z-10 bg-dark-900/90 backdrop-blur border border-dark-700/80 rounded-lg p-2.5 flex items-center gap-4 text-[11px] font-mono text-slate-300 shadow-xl">
              <span className="text-slate-500 uppercase font-bold text-[10px]">Topological Band:</span>
              <div className="flex items-center gap-1.5">
                <div className="w-2.5 h-2.5 rounded-full bg-purple-500" />
                <span>Contract</span>
              </div>
              <div className="flex items-center gap-1.5">
                <div className="w-2.5 h-2.5 rounded-full bg-blue-500" />
                <span>Requirement</span>
              </div>
              <div className="flex items-center gap-1.5">
                <div className="w-2.5 h-2.5 rounded-full bg-teal-500" />
                <span>Evidence Req</span>
              </div>
              <div className="flex items-center gap-1.5">
                <div className="w-2.5 h-2.5 rounded-full bg-emerald-500" />
                <span>Atomic Claim</span>
              </div>
              <div className="flex items-center gap-1.5">
                <div className="w-2.5 h-2.5 rounded-full bg-amber-500" />
                <span>Passage</span>
              </div>
              <div className="flex items-center gap-1.5">
                <div className="w-2.5 h-2.5 rounded-full bg-indigo-500" />
                <span>Source</span>
              </div>
              <div className="h-3 w-px bg-dark-700" />
              <div className="flex items-center gap-1.5">
                <div className="w-3 h-0.5 bg-red-500" />
                <span className="text-red-400 font-semibold">Conflict Link</span>
              </div>
            </div>
          </div>
        )}

        {/* Selected Node Details Inspector Panel */}
        {selectedNode && (
          <GraphDetailsPanel
            node={selectedNode}
            edges={graphData?.edges || []}
            allNodes={graphData?.nodes || []}
            onClose={() => setSelectedNodeId(null)}
            onSelectNode={setSelectedNodeId}
          />
        )}
      </div>
    </div>
  );
}
