import {
  Search,
  Sparkles,
  Maximize2,
  RotateCcw,
  Layers,
  Cpu,
  Loader2,
  CheckCircle2,
  Target,
  Quote,
  BookOpen,
  Globe,
} from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import type { GraphNodeType, GraphSummary, Investigation } from "@/lib/api";

interface GraphToolbarProps {
  investigations: Investigation[];
  selectedInvestigationId: string;
  onSelectInvestigation: (id: string) => void;
  searchQuery: string;
  onSearchChange: (q: string) => void;
  activeTypeFilter: GraphNodeType | "all";
  onTypeFilterChange: (type: GraphNodeType | "all") => void;
  processingMode: "gemini" | "fallback" | "pending";
  summary: GraphSummary;
  onRunAnalysis: () => void;
  isAnalyzing: boolean;
  onFitView: () => void;
  onResetView: () => void;
  hasContract: boolean;
  claimsCount: number;
}

export function GraphToolbar({
  investigations,
  selectedInvestigationId,
  onSelectInvestigation,
  searchQuery,
  onSearchChange,
  activeTypeFilter,
  onTypeFilterChange,
  processingMode,
  summary,
  onRunAnalysis,
  isAnalyzing,
  onFitView,
  onResetView,
  hasContract,
  claimsCount,
}: GraphToolbarProps) {
  const FILTER_OPTIONS: { id: GraphNodeType | "all"; label: string; count?: number; icon?: any }[] = [
    { id: "all", label: "All Nodes", count: summary.total_nodes },
    { id: "decision_contract", label: "Criteria", count: summary.contract_nodes, icon: Target },
    { id: "decision_requirement", label: "Requirements", count: summary.requirement_nodes, icon: CheckCircle2 },
    { id: "evidence_requirement", label: "Evidence Needed", count: summary.evidence_requirement_nodes, icon: Layers },
    { id: "atomic_claim", label: "Claims", count: summary.claim_nodes, icon: Quote },
    { id: "source_passage", label: "Passages", count: summary.passage_nodes, icon: BookOpen },
    { id: "source_document", label: "Sources", count: summary.source_nodes, icon: Globe },
  ];

  return (
    <div className="bg-dark-900 border-b border-dark-700/80 p-3 space-y-3 shrink-0">
      {/* Top Row: Investigation Select, Mode Badge, and Analysis Trigger */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        {/* Left: Investigation dropdown */}
        <div className="flex items-center gap-2 min-w-0">
          <label className="text-[11px] font-mono text-slate-400 uppercase tracking-wider shrink-0">
            Investigation:
          </label>
          <select
            value={selectedInvestigationId}
            onChange={(e) => onSelectInvestigation(e.target.value)}
            className="bg-slate-900 text-slate-100 border border-slate-700 rounded-md px-2.5 py-1 text-xs focus:ring-1 focus:ring-primary-500 focus:border-primary-500 max-w-xs md:max-w-md truncate cursor-pointer shadow-sm"
          >
            {investigations.map((inv) => (
              <option key={inv.id} value={inv.id} className="bg-slate-900 text-slate-100 py-1">
                {inv.research_question} ({inv.claims_count} claims)
              </option>
            ))}
          </select>

          {/* Mode Badge */}
          {processingMode === "gemini" && (
            <Badge variant="supported" className="gap-1 font-mono text-[10px] uppercase">
              <Sparkles className="w-3 h-3 text-emerald-400" />
              AI RELEVANCE ACTIVE
            </Badge>
          )}
          {processingMode === "fallback" && (
            <Badge variant="gap" className="gap-1 font-mono text-[10px] uppercase">
              <Cpu className="w-3 h-3 text-amber-400" />
              TEXT MATCHING ACTIVE
            </Badge>
          )}
          {processingMode === "pending" && (
            <Badge variant="neutral" className="font-mono text-[10px] uppercase">
              READY TO MAP
            </Badge>
          )}
        </div>

        {/* Right: Actions */}
        <div className="flex items-center gap-2">
          {/* Analyze Relevance Button */}
          <Button
            variant="primary"
            size="sm"
            onClick={onRunAnalysis}
            disabled={isAnalyzing || !hasContract || claimsCount === 0}
            className="gap-1.5 text-xs font-medium bg-primary-600 hover:bg-primary-500 text-white shadow-md shadow-primary-950/50"
          >
            {isAnalyzing ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Sparkles className="w-3.5 h-3.5 text-teal-300" />
            )}
            {isAnalyzing
              ? "Mapping Evidence..."
              : processingMode === "pending"
              ? "Map Evidence to Criteria"
              : "Remap Evidence"}
          </Button>

          {/* Fit & Reset */}
          <div className="flex items-center border border-dark-700 rounded-md bg-dark-800/80">
            <button
              onClick={onFitView}
              title="Fit View"
              className="p-1.5 text-slate-400 hover:text-slate-200 hover:bg-dark-700/60 transition rounded-l-md"
            >
              <Maximize2 className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={onResetView}
              title="Reset Graph"
              className="p-1.5 text-slate-400 hover:text-slate-200 hover:bg-dark-700/60 transition rounded-r-md border-l border-dark-700"
            >
              <RotateCcw className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>

      {/* Bottom Row: Search Box and Type Filter Pills */}
      <div className="flex flex-wrap items-center justify-between gap-3 pt-1 border-t border-dark-800">
        {/* Search */}
        <div className="relative min-w-[220px] max-w-xs">
          <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Search nodes, claims, passages..."
            className="w-full bg-dark-800/90 text-xs text-slate-200 pl-8 pr-3 py-1 rounded-md border border-dark-700 focus:outline-none focus:border-primary-500 placeholder:text-slate-500"
          />
        </div>

        {/* Filter Pills */}
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-[10px] font-mono text-slate-500 uppercase mr-1">Filter:</span>
          {FILTER_OPTIONS.map((opt) => {
            const isActive = activeTypeFilter === opt.id;
            return (
              <button
                key={opt.id}
                onClick={() => onTypeFilterChange(opt.id)}
                className={`text-xs px-2.5 py-0.5 rounded-full border transition flex items-center gap-1 font-mono ${
                  isActive
                    ? "bg-primary-950/80 border-primary-500/80 text-primary-300 font-medium"
                    : "bg-dark-800/80 border-dark-700 text-slate-400 hover:text-slate-200 hover:border-dark-600"
                }`}
              >
                <span>{opt.label}</span>
                {typeof opt.count === "number" && (
                  <span
                    className={`text-[10px] px-1 rounded-full ${
                      isActive ? "bg-primary-800/60 text-primary-200" : "bg-dark-700 text-slate-400"
                    }`}
                  >
                    {opt.count}
                  </span>
                )}
              </button>
            );
          })}
        </div>

        {/* Quick Metrics */}
        <div className="hidden lg:flex items-center gap-3 text-xs font-mono text-slate-400">
          <span>
            Nodes: <strong className="text-slate-200">{summary.total_nodes}</strong>
          </span>
          <span>
            Edges: <strong className="text-slate-200">{summary.total_edges}</strong>
          </span>
          <span>
            Direct Links:{" "}
            <strong className="text-emerald-400">{summary.directly_relevant_links}</strong>
          </span>
        </div>
      </div>
    </div>
  );
}
