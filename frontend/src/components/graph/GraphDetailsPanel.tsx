import { useState } from "react";
import {
  X,
  ExternalLink,
  Copy,
  Check,
  Hash,
  ArrowRight,
} from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import type { GraphNode, GraphEdge } from "@/lib/api";

interface GraphDetailsPanelProps {
  node: GraphNode | null;
  edges: GraphEdge[];
  allNodes: GraphNode[];
  onClose: () => void;
  onSelectNode: (nodeId: string) => void;
}

export function GraphDetailsPanel({
  node,
  edges,
  allNodes,
  onClose,
  onSelectNode,
}: GraphDetailsPanelProps) {
  const [copied, setCopied] = useState(false);

  if (!node) return null;

  const handleCopyId = () => {
    navigator.clipboard.writeText(node.record_id);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Find incoming and outgoing edges for this node
  const incomingEdges = edges.filter((e) => e.target === node.id);
  const outgoingEdges = edges.filter((e) => e.source === node.id);

  const nodeMap = new Map(allNodes.map((n) => [n.id, n]));

  return (
    <aside className="w-96 bg-dark-900/95 backdrop-blur border-l border-dark-700/80 flex flex-col h-full shadow-2xl z-20">
      {/* Header */}
      <div className="p-4 border-b border-dark-700 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2">
          <Badge variant="info" className="uppercase font-mono text-[10px] tracking-wider">
            {node.type.replace(/_/g, " ")}
          </Badge>
          <span className="text-xs font-mono text-slate-400">
            {node.record_id.substring(0, 8)}...
          </span>
        </div>
        <button
          onClick={onClose}
          className="text-slate-400 hover:text-slate-200 p-1 rounded hover:bg-dark-800 transition"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Scrollable details */}
      <div className="p-4 overflow-y-auto space-y-5 flex-1 text-left">
        {/* Title / Label */}
        <div>
          <label className="text-[11px] font-mono uppercase tracking-wider text-slate-400 block mb-1">
            Display Label
          </label>
          <h3 className="text-sm font-semibold text-slate-100 leading-snug">
            {node.label}
          </h3>
        </div>

        {/* Database Primary Key */}
        <div className="bg-dark-800/80 p-2.5 rounded-lg border border-dark-700/60">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-mono text-slate-400">Database Record ID</span>
            <Button
              variant="ghost"
              size="sm"
              onClick={handleCopyId}
              className="h-6 px-1.5 text-[10px] text-slate-300 gap-1 hover:text-primary-400"
            >
              {copied ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
              {copied ? "Copied" : "Copy"}
            </Button>
          </div>
          <p className="font-mono text-xs text-slate-300 break-all select-all mt-1">
            {node.record_id}
          </p>
        </div>

        {/* TYPE SPECIFIC DETAILS */}

        {/* 1. DECISION CONTRACT */}
        {node.type === "decision_contract" && (
          <div className="space-y-4">
            <div>
              <label className="text-[11px] font-mono uppercase tracking-wider text-slate-400 block mb-1">
                Formal Decision Objective
              </label>
              <div className="p-3 bg-dark-800/60 rounded-md border border-dark-700/60 text-xs text-slate-200 leading-relaxed">
                {node.metadata.decision_objective}
              </div>
            </div>

            {node.metadata.original_question && (
              <div>
                <label className="text-[11px] font-mono uppercase tracking-wider text-slate-400 block mb-1">
                  Original Research Question
                </label>
                <p className="text-xs text-slate-300 italic">"{node.metadata.original_question}"</p>
              </div>
            )}

            {node.metadata.scope && (
              <div>
                <label className="text-[11px] font-mono uppercase tracking-wider text-slate-400 block mb-1">
                  Operational Scope
                </label>
                <p className="text-xs text-slate-300">{node.metadata.scope}</p>
              </div>
            )}
          </div>
        )}

        {/* 2. DECISION REQUIREMENT */}
        {node.type === "decision_requirement" && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-2">
              <div className="bg-dark-800/60 p-2 rounded border border-dark-700/60">
                <span className="text-[10px] font-mono text-slate-400 block">Type</span>
                <span className="text-xs font-mono font-medium text-blue-400">
                  {node.metadata.requirement_type}
                </span>
              </div>
              <div className="bg-dark-800/60 p-2 rounded border border-dark-700/60">
                <span className="text-[10px] font-mono text-slate-400 block">Priority</span>
                <span className="text-xs font-mono font-medium text-amber-400">
                  {node.metadata.priority}
                </span>
              </div>
            </div>

            <div>
              <label className="text-[11px] font-mono uppercase tracking-wider text-slate-400 block mb-1">
                Requirement Condition
              </label>
              <p className="text-xs text-slate-200 leading-relaxed bg-dark-800/60 p-3 rounded border border-dark-700/60">
                {node.metadata.description}
              </p>
            </div>

            <div>
              <label className="text-[11px] font-mono uppercase tracking-wider text-slate-400 block mb-1">
                Verification Criteria
              </label>
              <div className="p-3 bg-blue-950/20 border border-blue-900/40 rounded-md text-xs text-blue-200/90 leading-relaxed">
                {node.metadata.verification_criteria}
              </div>
            </div>
          </div>
        )}

        {/* 3. EVIDENCE REQUIREMENT */}
        {node.type === "evidence_requirement" && (
          <div className="space-y-4">
            <div>
              <label className="text-[11px] font-mono uppercase tracking-wider text-slate-400 block mb-1">
                Required Evidence Artifact Type
              </label>
              <p className="text-xs font-medium text-teal-300">{node.metadata.evidence_type}</p>
            </div>

            <div>
              <label className="text-[11px] font-mono uppercase tracking-wider text-slate-400 block mb-1">
                Evidentiary Rationale
              </label>
              <p className="text-xs text-slate-200 leading-relaxed bg-dark-800/60 p-3 rounded border border-dark-700/60">
                {node.metadata.rationale}
              </p>
            </div>

            {node.metadata.preferred_sources && (
              <div>
                <label className="text-[11px] font-mono uppercase tracking-wider text-slate-400 block mb-1">
                  Preferred Sources
                </label>
                <div className="flex flex-wrap gap-1">
                  {Array.isArray(node.metadata.preferred_sources)
                    ? node.metadata.preferred_sources.map((s: string, i: number) => (
                        <span
                          key={i}
                          className="text-[10px] font-mono bg-teal-950/40 text-teal-300 border border-teal-800/40 px-2 py-0.5 rounded"
                        >
                          {s}
                        </span>
                      ))
                    : <span className="text-xs text-slate-300">{node.metadata.preferred_sources}</span>}
                </div>
              </div>
            )}
          </div>
        )}

        {/* 4. ATOMIC CLAIM */}
        {node.type === "atomic_claim" && (
          <div className="space-y-4">
            <div>
              <label className="text-[11px] font-mono uppercase tracking-wider text-slate-400 block mb-1">
                Full Atomic Claim Text
              </label>
              <blockquote className="p-3 bg-emerald-950/20 border-l-2 border-emerald-500 rounded-r text-xs text-emerald-200 leading-relaxed">
                "{node.metadata.claim_text || node.label}"
              </blockquote>
            </div>

            <div className="grid grid-cols-2 gap-2">
              <div className="bg-dark-800/60 p-2.5 rounded border border-dark-700/60">
                <span className="text-[10px] font-mono text-slate-400 block">Claim Category</span>
                <span className="text-xs font-mono uppercase text-emerald-400 font-bold">
                  {node.metadata.category || "factual"}
                </span>
              </div>
              <div className="bg-dark-800/60 p-2.5 rounded border border-dark-700/60">
                <span className="text-[10px] font-mono text-slate-400 block">Extraction Confidence</span>
                <span className="text-xs font-mono font-bold text-emerald-300">
                  {Math.round((node.metadata.confidence || 0.9) * 100)}%
                </span>
              </div>
            </div>

            <div className="bg-dark-800/40 p-2.5 rounded border border-dark-700/40 text-[11px] text-slate-400 space-y-1">
              <div className="flex justify-between">
                <span>Extraction Method</span>
                <span className="font-mono text-slate-300">{node.metadata.extraction_method}</span>
              </div>
              <div className="flex justify-between">
                <span>Passage ID</span>
                <span className="font-mono text-slate-300">{node.metadata.passage_id?.substring(0, 10)}...</span>
              </div>
            </div>
          </div>
        )}

        {/* 5. SOURCE PASSAGE */}
        {node.type === "source_passage" && (
          <div className="space-y-4">
            <div>
              <label className="text-[11px] font-mono uppercase tracking-wider text-slate-400 block mb-1">
                Original Passage Text (Exact Provenance)
              </label>
              <div className="p-3 bg-amber-950/20 border-l-2 border-amber-500 rounded-r text-xs font-serif text-amber-200/90 leading-relaxed whitespace-pre-wrap">
                {node.metadata.passage_text}
              </div>
            </div>

            <div className="grid grid-cols-2 gap-2 text-xs">
              <div className="bg-dark-800/60 p-2 rounded border border-dark-700/60">
                <span className="text-[10px] font-mono text-slate-400 block">Location</span>
                <span className="font-mono text-amber-300">
                  {node.metadata.page_number
                    ? `Page ${node.metadata.page_number}`
                    : `Paragraph §${node.metadata.paragraph_index || 1}`}
                </span>
              </div>
              <div className="bg-dark-800/60 p-2 rounded border border-dark-700/60">
                <span className="text-[10px] font-mono text-slate-400 block">Offsets</span>
                <span className="font-mono text-slate-300 text-[11px]">
                  {node.metadata.start_offset ?? 0} → {node.metadata.end_offset ?? "end"}
                </span>
              </div>
            </div>

            {node.metadata.sha256_hash && (
              <div>
                <label className="text-[11px] font-mono uppercase tracking-wider text-slate-400 block mb-1">
                  Cryptographic Provenance Hash
                </label>
                <div className="flex items-center gap-1.5 p-2 bg-dark-800/80 rounded border border-dark-700 font-mono text-[10px] text-amber-400/90 break-all">
                  <Hash className="w-3.5 h-3.5 shrink-0 text-amber-500" />
                  <span>{node.metadata.sha256_hash}</span>
                </div>
              </div>
            )}
          </div>
        )}

        {/* 6. SOURCE DOCUMENT */}
        {node.type === "source_document" && (
          <div className="space-y-4">
            <div>
              <label className="text-[11px] font-mono uppercase tracking-wider text-slate-400 block mb-1">
                Document / URL Title
              </label>
              <p className="text-xs font-semibold text-slate-200">{node.metadata.title || "Untitled Document"}</p>
            </div>

            {node.metadata.original_url && (
              <div>
                <label className="text-[11px] font-mono uppercase tracking-wider text-slate-400 block mb-1">
                  Origin URL
                </label>
                <a
                  href={node.metadata.original_url}
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center gap-1 text-xs text-primary-400 hover:text-primary-300 break-all underline"
                >
                  <ExternalLink className="w-3.5 h-3.5 shrink-0" />
                  <span>{node.metadata.original_url}</span>
                </a>
              </div>
            )}

            <div className="grid grid-cols-2 gap-2 text-xs">
              <div className="bg-dark-800/60 p-2 rounded border border-dark-700/60">
                <span className="text-[10px] font-mono text-slate-400 block">Source Type</span>
                <span className="font-mono uppercase text-indigo-400">{node.metadata.source_type}</span>
              </div>
              <div className="bg-dark-800/60 p-2 rounded border border-dark-700/60">
                <span className="text-[10px] font-mono text-slate-400 block">Extraction</span>
                <span className="font-mono capitalize text-emerald-400">{node.metadata.extraction_status}</span>
              </div>
            </div>

            {node.metadata.retrieved_at && (
              <div className="text-[10px] font-mono text-slate-400">
                <span>Ingested: </span>
                <span className="text-slate-300">
                  {new Date(node.metadata.retrieved_at).toLocaleString()}
                </span>
              </div>
            )}
          </div>
        )}

        {/* CONNECTED GRAPH EDGES SECTION */}
        <div className="pt-4 border-t border-dark-700 space-y-3">
          <label className="text-[11px] font-mono uppercase tracking-wider text-slate-400 flex items-center justify-between">
            <span>Connected Graph Edges</span>
            <span className="text-primary-400 font-bold">
              {incomingEdges.length + outgoingEdges.length}
            </span>
          </label>

          {/* Relational / Outgoing Edges */}
          {outgoingEdges.length > 0 && (
            <div className="space-y-2">
              <span className="text-[10px] font-mono text-slate-500 uppercase">Target Links</span>
              {outgoingEdges.map((edge) => {
                const targetNode = nodeMap.get(edge.target);
                return (
                  <div
                    key={edge.id}
                    onClick={() => onSelectNode(edge.target)}
                    className="p-2.5 bg-dark-800/80 hover:bg-dark-750 border border-dark-700/80 rounded-lg cursor-pointer transition flex flex-col gap-1 text-xs"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-dark-700 text-slate-300">
                        {edge.relationship}
                      </span>
                      {edge.origin && (
                        <span
                          className={`text-[9px] font-mono font-bold uppercase px-1 rounded ${
                            edge.origin === "gemini"
                              ? "text-primary-400 bg-primary-950/40"
                              : "text-slate-400 bg-dark-700"
                          }`}
                        >
                          {edge.origin}
                        </span>
                      )}
                    </div>
                    {targetNode && (
                      <div className="flex items-center gap-1.5 text-slate-200 mt-1">
                        <ArrowRight className="w-3 h-3 text-slate-500 shrink-0" />
                        <span className="truncate">{targetNode.label}</span>
                      </div>
                    )}
                    {edge.metadata?.explanation && (
                      <p className="text-[11px] text-slate-400 mt-1 italic border-l border-dark-600 pl-2">
                        {edge.metadata.explanation}
                      </p>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          {/* Incoming Edges */}
          {incomingEdges.length > 0 && (
            <div className="space-y-2">
              <span className="text-[10px] font-mono text-slate-500 uppercase">Incoming Links</span>
              {incomingEdges.map((edge) => {
                const sourceNode = nodeMap.get(edge.source);
                return (
                  <div
                    key={edge.id}
                    onClick={() => onSelectNode(edge.source)}
                    className="p-2.5 bg-dark-800/80 hover:bg-dark-750 border border-dark-700/80 rounded-lg cursor-pointer transition flex flex-col gap-1 text-xs"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-dark-700 text-slate-300">
                        {edge.relationship}
                      </span>
                      {edge.metadata?.relevance && (
                        <span
                          className={`text-[9px] font-mono font-bold uppercase px-1 rounded ${
                            edge.metadata.relevance === "DIRECTLY_RELEVANT"
                              ? "text-emerald-400 bg-emerald-950/40"
                              : edge.metadata.relevance === "PARTIALLY_RELEVANT"
                              ? "text-amber-400 bg-amber-950/40"
                              : "text-purple-400 bg-purple-950/40"
                          }`}
                        >
                          {edge.metadata.relevance.replace(/_/g, " ")}
                        </span>
                      )}
                    </div>
                    {sourceNode && (
                      <div className="flex items-center gap-1.5 text-slate-200 mt-1">
                        <ArrowRight className="w-3 h-3 text-slate-500 shrink-0 rotate-180" />
                        <span className="truncate">{sourceNode.label}</span>
                      </div>
                    )}
                    {edge.metadata?.explanation && (
                      <p className="text-[11px] text-slate-400 mt-1 italic border-l border-dark-600 pl-2">
                        {edge.metadata.explanation}
                      </p>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </aside>
  );
}
