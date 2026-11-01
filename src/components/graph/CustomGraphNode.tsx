import { memo } from "react";
import { Handle, Position } from "@xyflow/react";
import {
  FileText,
  Target,
  Layers,
  Quote,
  BookOpen,
  Globe,
  CheckCircle2,
} from "lucide-react";
import type { GraphNodeType } from "@/lib/api";

export interface CustomNodeData {
  label: string;
  type: GraphNodeType;
  recordId: string;
  metadata: Record<string, any>;
  isSelected?: boolean;
  isHighlighted?: boolean;
  isDimmed?: boolean;
}

const TYPE_CONFIG: Record<
  GraphNodeType,
  {
    title: string;
    icon: typeof FileText;
    border: string;
    activeBorder: string;
    bg: string;
    headerBg: string;
  }
> = {
  decision_contract: {
    title: "DECISION CONTRACT",
    icon: Target,
    border: "border-purple-500/40",
    activeBorder: "border-purple-400 ring-2 ring-purple-500/50",
    bg: "bg-[#131b2e]",
    headerBg: "bg-purple-950/40 text-purple-300",
  },
  decision_requirement: {
    title: "REQUIREMENT",
    icon: CheckCircle2,
    border: "border-blue-500/40",
    activeBorder: "border-blue-400 ring-2 ring-blue-500/50",
    bg: "bg-[#111c30]",
    headerBg: "bg-blue-950/40 text-blue-300",
  },
  evidence_requirement: {
    title: "EVIDENCE NEEDED",
    icon: Layers,
    border: "border-teal-500/40",
    activeBorder: "border-teal-400 ring-2 ring-teal-500/50",
    bg: "bg-[#0f212a]",
    headerBg: "bg-teal-950/40 text-teal-300",
  },
  atomic_claim: {
    title: "ATOMIC CLAIM",
    icon: Quote,
    border: "border-emerald-500/40",
    activeBorder: "border-emerald-400 ring-2 ring-emerald-500/50",
    bg: "bg-[#0f231e]",
    headerBg: "bg-emerald-950/40 text-emerald-300",
  },
  source_passage: {
    title: "SOURCE PASSAGE",
    icon: BookOpen,
    border: "border-amber-500/40",
    activeBorder: "border-amber-400 ring-2 ring-amber-500/50",
    bg: "bg-[#231e13]",
    headerBg: "bg-amber-950/40 text-amber-300",
  },
  source_document: {
    title: "DOCUMENT / URL",
    icon: Globe,
    border: "border-indigo-500/40",
    activeBorder: "border-indigo-400 ring-2 ring-indigo-500/50",
    bg: "bg-[#161a2e]",
    headerBg: "bg-indigo-950/40 text-indigo-300",
  },
};

export const CustomGraphNode: any = memo(({ data }: { data: any }) => {
  const nodeData = data as CustomNodeData;
  const config = TYPE_CONFIG[nodeData.type] || TYPE_CONFIG.source_document;
  const Icon = config.icon;

  const isDimmed = nodeData.isDimmed && !nodeData.isSelected && !nodeData.isHighlighted;
  const isSelected = nodeData.isSelected;
  const isHighlighted = nodeData.isHighlighted;

  return (
    <div
      className={`relative w-72 rounded-lg border transition-all duration-200 shadow-lg cursor-pointer ${
        config.bg
      } ${
        isSelected
          ? config.activeBorder + " shadow-xl scale-[1.02]"
          : isHighlighted
          ? config.activeBorder
          : config.border
      } ${isDimmed ? "opacity-25 grayscale-[40%]" : "opacity-100"}`}
    >
      {/* Top Handle for Incoming Edges */}
      <Handle
        type="target"
        position={Position.Top}
        className="!w-2.5 !h-2.5 !bg-primary-400 !border-2 !border-dark-900 rounded-full transition-transform hover:scale-125"
      />

      {/* Header bar */}
      <div
        className={`flex items-center justify-between px-3 py-1.5 border-b border-dark-700/60 rounded-t-lg ${config.headerBg}`}
      >
        <div className="flex items-center gap-1.5 min-w-0">
          <Icon className="w-3.5 h-3.5 shrink-0" />
          <span className="text-[10px] font-mono tracking-wider font-semibold uppercase truncate">
            {config.title}
          </span>
        </div>

        {nodeData.type === "decision_requirement" && nodeData.metadata.priority && (
          <span
            className={`text-[9px] font-mono font-bold px-1.5 py-0.5 rounded ${
              nodeData.metadata.priority === "CRITICAL"
                ? "bg-red-500/20 text-red-400 border border-red-500/30"
                : nodeData.metadata.priority === "HIGH"
                ? "bg-amber-500/20 text-amber-400 border border-amber-500/30"
                : "bg-blue-500/20 text-blue-400 border border-blue-500/30"
            }`}
          >
            {nodeData.metadata.priority}
          </span>
        )}

        {nodeData.type === "atomic_claim" && nodeData.metadata.category && (
          <span className="text-[9px] font-mono uppercase bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 px-1.5 py-0.5 rounded">
            {nodeData.metadata.category}
          </span>
        )}

        {nodeData.type === "source_passage" && (
          <span className="text-[9px] font-mono text-amber-300">
            {nodeData.metadata.page_number
              ? `p. ${nodeData.metadata.page_number}`
              : `§${nodeData.metadata.paragraph_index || 1}`}
          </span>
        )}

        {nodeData.type === "source_document" && (
          <span className="text-[9px] font-mono uppercase text-indigo-300">
            {nodeData.metadata.source_type}
          </span>
        )}
      </div>

      {/* Body content */}
      <div className="p-3 space-y-2 text-left">
        <p className="text-xs font-medium text-slate-200 line-clamp-3 leading-relaxed">
          {nodeData.type === "atomic_claim"
            ? nodeData.metadata.claim_text || nodeData.label
            : nodeData.type === "decision_contract"
            ? nodeData.metadata.decision_objective || nodeData.label
            : nodeData.type === "source_passage"
            ? nodeData.metadata.passage_text || nodeData.label
            : nodeData.label}
        </p>

        {/* Node-specific metadata footer */}
        {nodeData.type === "decision_requirement" && nodeData.metadata.requirement_type && (
          <div className="flex items-center justify-between pt-1 border-t border-dark-700/40 text-[10px] text-slate-400">
            <span className="font-mono text-blue-400">{nodeData.metadata.requirement_type}</span>
            <span className="capitalize">{nodeData.metadata.status || "unverified"}</span>
          </div>
        )}

        {nodeData.type === "atomic_claim" && (
          <div className="flex items-center justify-between pt-1 border-t border-dark-700/40 text-[10px] text-slate-400">
            <span className="font-mono text-emerald-400">
              Confidence: {Math.round((nodeData.metadata.confidence || 0.9) * 100)}%
            </span>
            <span className="text-[9px] text-slate-500 truncate max-w-[100px]">
              {nodeData.metadata.extraction_method?.replace(/_/g, " ")}
            </span>
          </div>
        )}

        {nodeData.type === "source_passage" && nodeData.metadata.sha256_hash && (
          <div className="flex items-center justify-between pt-1 border-t border-dark-700/40 text-[9px] font-mono text-slate-400">
            <span>SHA-256</span>
            <span className="text-amber-400/80">
              {nodeData.metadata.sha256_hash.substring(0, 10)}...
            </span>
          </div>
        )}

        {nodeData.type === "source_document" && (
          <div className="flex items-center justify-between pt-1 border-t border-dark-700/40 text-[9px] text-slate-400">
            <span className="truncate max-w-[180px] font-mono text-indigo-300">
              {nodeData.metadata.original_url || nodeData.metadata.title}
            </span>
            <span className="capitalize text-emerald-400">
              {nodeData.metadata.extraction_status}
            </span>
          </div>
        )}
      </div>

      {/* Bottom Handle for Outgoing Edges */}
      <Handle
        type="source"
        position={Position.Bottom}
        className="!w-2.5 !h-2.5 !bg-secondary-400 !border-2 !border-dark-900 rounded-full transition-transform hover:scale-125"
      />
    </div>
  );
});

CustomGraphNode.displayName = "CustomGraphNode";
