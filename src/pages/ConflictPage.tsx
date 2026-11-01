import { useState, useEffect, useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import {
  listInvestigations,
  getInvestigationConflicts,
  analyzeInvestigationConflicts,
  updateConflictResolution,
  Investigation,
  ConflictItem,
  ConflictSummary,
  ConflictSeverity,
  ConflictResolutionStatus,
} from "@/lib/api";
import {
  AlertTriangle,
  ShieldAlert,
  Hash,
  Layers,
  CheckCircle2,
  Clock,
  Sparkles,
  RefreshCw,
  Search,
  ExternalLink,
  FileText,
  Save,
  Info,
  FileCheck,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/Button";

export function ConflictPage() {
  const [searchParams, setSearchParams] = useSearchParams();

  // Navigation & Data State
  const [investigations, setInvestigations] = useState<Investigation[]>([]);
  const [selectedInvId, setSelectedInvId] = useState<string | null>(null);
  const [conflicts, setConflicts] = useState<ConflictItem[]>([]);
  const [summary, setSummary] = useState<ConflictSummary | null>(null);
  const [processingMode, setProcessingMode] = useState<"gemini" | "fallback" | "pending">("pending");
  const [lastAnalyzedAt, setLastAnalyzedAt] = useState<string | null>(null);

  // Inspector & Selection State
  const [selectedConflictId, setSelectedConflictId] = useState<string | null>(null);
  const [editStatus, setEditStatus] = useState<ConflictResolutionStatus>("unresolved");
  const [editNotes, setEditNotes] = useState<string>("");
  const [isSavingResolution, setIsSavingResolution] = useState(false);
  const [saveSuccessMsg, setSaveSuccessMsg] = useState<string | null>(null);

  // Loading & Action State
  const [isLoading, setIsLoading] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Filter States
  const [searchQuery, setSearchQuery] = useState("");
  const [typeFilter, setTypeFilter] = useState<string>("ALL");
  const [severityFilter, setSeverityFilter] = useState<string>("ALL");
  const [statusFilter, setStatusFilter] = useState<string>("ALL");

  // 1. Initial Load of Investigations
  useEffect(() => {
    let isMounted = true;
    async function loadInvestigations() {
      try {
        const invs = await listInvestigations();
        if (!isMounted) return;
        setInvestigations(invs);

        const urlInv = searchParams.get("inv");
        if (urlInv && invs.some((i) => i.id === urlInv)) {
          setSelectedInvId(urlInv);
        } else if (invs.length > 0) {
          setSelectedInvId(invs[0].id);
          setSearchParams({ inv: invs[0].id });
        }
      } catch (err: any) {
        if (isMounted) setErrorMessage(err.message || "Failed to load investigations");
      }
    }
    loadInvestigations();
    return () => {
      isMounted = false;
    };
  }, []);

  // 2. Fetch Conflicts when investigation changes
  useEffect(() => {
    if (!selectedInvId) return;

    let isMounted = true;
    async function fetchConflicts() {
      setIsLoading(true);
      setErrorMessage(null);
      try {
        const data = await getInvestigationConflicts(selectedInvId!);
        if (!isMounted) return;
        setConflicts(data.conflicts);
        setSummary(data.summary);
        setProcessingMode(data.processing_mode);
        setLastAnalyzedAt(data.last_analyzed_at || null);

        // Pre-select first conflict if available
        if (data.conflicts.length > 0) {
          setSelectedConflictId(data.conflicts[0].conflict_id);
          setEditStatus(data.conflicts[0].resolution_status);
          setEditNotes(data.conflicts[0].reviewer_notes || "");
        } else {
          setSelectedConflictId(null);
        }
      } catch (err: any) {
        if (isMounted) setErrorMessage(err.message || "Failed to load conflicts");
      } finally {
        if (isMounted) setIsLoading(false);
      }
    }

    fetchConflicts();
    return () => {
      isMounted = false;
    };
  }, [selectedInvId]);

  // Sync selected conflict editor fields when selection changes
  const selectedConflict = useMemo(() => {
    return conflicts.find((c) => c.conflict_id === selectedConflictId) || null;
  }, [conflicts, selectedConflictId]);

  useEffect(() => {
    if (selectedConflict) {
      setEditStatus(selectedConflict.resolution_status);
      setEditNotes(selectedConflict.reviewer_notes || "");
    }
  }, [selectedConflictId]);

  // Trigger Conflict Analysis
  const handleAnalyze = async () => {
    if (!selectedInvId || isAnalyzing) return;
    setIsAnalyzing(true);
    setErrorMessage(null);
    setSaveSuccessMsg(null);

    try {
      const result = await analyzeInvestigationConflicts(selectedInvId);
      setConflicts(result.conflicts);
      setSummary(result.summary);
      setProcessingMode(result.processing_mode);
      setLastAnalyzedAt(result.last_analyzed_at || null);

      if (result.conflicts.length > 0) {
        setSelectedConflictId(result.conflicts[0].conflict_id);
      }
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to analyze conflicts");
    } finally {
      setIsAnalyzing(false);
    }
  };

  // Update Reviewer Resolution
  const handleSaveResolution = async () => {
    if (!selectedInvId || !selectedConflictId || isSavingResolution) return;
    setIsSavingResolution(true);
    setSaveSuccessMsg(null);
    setErrorMessage(null);

    try {
      const updated = await updateConflictResolution(selectedInvId, selectedConflictId, {
        resolution_status: editStatus,
        reviewer_notes: editNotes,
      });

      // Update in local state
      setConflicts((prev) =>
        prev.map((c) => (c.conflict_id === updated.conflict_id ? updated : c))
      );
      setSaveSuccessMsg("Resolution status and forensic notes saved successfully.");
      setTimeout(() => setSaveSuccessMsg(null), 4000);
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to update resolution");
    } finally {
      setIsSavingResolution(false);
    }
  };

  // Filtered conflicts list
  const filteredConflicts = useMemo(() => {
    return conflicts.filter((c) => {
      if (typeFilter !== "ALL" && c.conflict_type !== typeFilter) return false;
      if (severityFilter !== "ALL" && c.severity !== severityFilter) return false;
      if (statusFilter !== "ALL" && c.resolution_status !== statusFilter) return false;

      if (searchQuery.trim()) {
        const query = searchQuery.toLowerCase();
        const matchesA = c.claim_a_text.toLowerCase().includes(query);
        const matchesB = c.claim_b_text.toLowerCase().includes(query);
        const matchesExpl = c.explanation.toLowerCase().includes(query);
        const matchesSrcA = (c.source_a_title || "").toLowerCase().includes(query);
        const matchesSrcB = (c.source_b_title || "").toLowerCase().includes(query);
        if (!matchesA && !matchesB && !matchesExpl && !matchesSrcA && !matchesSrcB) {
          return false;
        }
      }
      return true;
    });
  }, [conflicts, typeFilter, severityFilter, statusFilter, searchQuery]);

  // Color helper functions
  const getSeverityBadge = (severity: ConflictSeverity) => {
    switch (severity) {
      case "CRITICAL":
        return <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-rose-500/20 text-rose-400 border border-rose-500/30">CRITICAL</span>;
      case "HIGH":
        return <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-orange-500/20 text-orange-400 border border-orange-500/30">HIGH</span>;
      case "MEDIUM":
        return <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-amber-500/20 text-amber-400 border border-amber-500/30">MEDIUM</span>;
      case "LOW":
        return <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-blue-500/20 text-blue-400 border border-blue-500/30">LOW</span>;
      default:
        return <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-slate-500/20 text-slate-400">{severity}</span>;
    }
  };

  const getStatusBadge = (status: ConflictResolutionStatus) => {
    switch (status) {
      case "resolved":
        return <span className="px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">RESOLVED</span>;
      case "under_review":
        return <span className="px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-amber-500/15 text-amber-400 border border-amber-500/30">UNDER REVIEW</span>;
      case "unresolved":
      default:
        return <span className="px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-slate-800 text-slate-400 border border-slate-700">UNRESOLVED</span>;
    }
  };

  const formatConflictTypeName = (type: string) => {
    return type.replace(/_/g, " ");
  };

  return (
    <div className="space-y-6 pb-12">
      {/* 1. Header Toolbar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-dark-700/60 pb-5">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="p-2 bg-rose-500/10 border border-rose-500/20 rounded-lg text-rose-400">
              <AlertTriangle className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
                Conflicting Evidence
              </h1>
              <p className="text-xs text-slate-400 mt-0.5">
                Find disagreements, contradictory statements, and numerical differences between sources.
              </p>
            </div>
          </div>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-3">
          {/* Investigation Switcher */}
          <select
            value={selectedInvId || ""}
            onChange={(e) => {
              setSelectedInvId(e.target.value);
              setSearchParams({ inv: e.target.value });
            }}
            className="bg-slate-900 border border-slate-700 text-slate-100 text-xs rounded-lg px-3 py-2 font-medium focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 cursor-pointer shadow-sm"
          >
            {investigations.map((inv) => (
              <option key={inv.id} value={inv.id} className="bg-slate-900 text-slate-100 py-1.5">
                {inv.research_question ? inv.research_question.slice(0, 48) + "..." : inv.id.slice(0, 8)}
              </option>
            ))}
          </select>

          {/* Processing Mode Pill */}
          {processingMode === "gemini" ? (
            <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-mono font-medium">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              <span>AI ANALYSIS ACTIVE</span>
            </div>
          ) : processingMode === "fallback" ? (
            <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-400 text-xs font-mono font-medium">
              <span className="w-2 h-2 rounded-full bg-amber-400" />
              <span>RULE-BASED ANALYSIS</span>
            </div>
          ) : (
            <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-dark-800 border border-dark-700 text-slate-400 text-xs font-mono">
              <span>NOT ANALYZED</span>
            </div>
          )}

          {/* Analyze Trigger */}
          <Button
            onClick={handleAnalyze}
            disabled={!selectedInvId || isAnalyzing || isLoading}
            className="bg-gradient-to-r from-rose-600 to-amber-600 hover:from-rose-500 hover:to-amber-500 text-white font-medium text-xs px-3.5 py-2 flex items-center gap-2 shadow-lg shadow-rose-900/20"
          >
            {isAnalyzing ? (
              <>
                <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                <span>Scanning Conflicts...</span>
              </>
            ) : (
              <>
                <Sparkles className="w-3.5 h-3.5" />
                <span>Detect Conflicts</span>
              </>
            )}
          </Button>
        </div>
      </div>

      {/* Error or Success Banners */}
      {errorMessage && (
        <div className="p-3 bg-rose-500/10 border border-rose-500/20 rounded-lg flex items-center gap-2.5 text-xs text-rose-300">
          <AlertTriangle className="w-4 h-4 shrink-0 text-rose-400" />
          <span>{errorMessage}</span>
          <button onClick={() => setErrorMessage(null)} className="ml-auto text-rose-400 hover:text-rose-200">
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {saveSuccessMsg && (
        <div className="p-3 bg-emerald-500/10 border border-emerald-500/20 rounded-lg flex items-center gap-2.5 text-xs text-emerald-300">
          <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-400" />
          <span>{saveSuccessMsg}</span>
        </div>
      )}

      {/* 2. Forensic Summary Metrics Cards */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <div className="p-3.5 bg-dark-900/70 border border-dark-700/60 rounded-xl relative overflow-hidden">
          <div className="flex items-center justify-between text-slate-400 text-xs mb-1">
            <span>Total Conflicts</span>
            <AlertTriangle className="w-4 h-4 text-slate-400" />
          </div>
          <div className="text-2xl font-bold font-mono text-white">
            {summary?.total_conflicts ?? conflicts.length}
          </div>
          <div className="text-[11px] text-slate-500 mt-1">Total conflicts found</div>
        </div>

        <div className="p-3.5 bg-dark-900/70 border border-rose-500/20 rounded-xl relative overflow-hidden">
          <div className="flex items-center justify-between text-rose-400 text-xs mb-1">
            <span>Direct Contradictions</span>
            <ShieldAlert className="w-4 h-4 text-rose-400" />
          </div>
          <div className="text-2xl font-bold font-mono text-rose-400">
            {summary?.direct_contradictions ?? 0}
          </div>
          <div className="text-[11px] text-slate-500 mt-1">Opposing statements</div>
        </div>

        <div className="p-3.5 bg-dark-900/70 border border-amber-500/20 rounded-xl relative overflow-hidden">
          <div className="flex items-center justify-between text-amber-400 text-xs mb-1">
            <span>Numerical Disparities</span>
            <Hash className="w-4 h-4 text-amber-400" />
          </div>
          <div className="text-2xl font-bold font-mono text-amber-400">
            {summary?.numerical_conflicts ?? 0}
          </div>
          <div className="text-[11px] text-slate-500 mt-1">Different numbers or rates</div>
        </div>

        <div className="p-3.5 bg-dark-900/70 border border-indigo-500/20 rounded-xl relative overflow-hidden">
          <div className="flex items-center justify-between text-indigo-400 text-xs mb-1">
            <span>Contextual Tensions</span>
            <Layers className="w-4 h-4 text-indigo-400" />
          </div>
          <div className="text-2xl font-bold font-mono text-indigo-400">
            {(summary?.contextual_tensions || 0) + (summary?.temporal_conflicts || 0) + (summary?.methodological_disagreements || 0)}
          </div>
          <div className="text-[11px] text-slate-500 mt-1">Context & timing differences</div>
        </div>

        <div className="p-3.5 bg-dark-900/70 border border-cyan-500/20 rounded-xl relative overflow-hidden">
          <div className="flex items-center justify-between text-cyan-400 text-xs mb-1">
            <span>Pending Review</span>
            <Clock className="w-4 h-4 text-cyan-400" />
          </div>
          <div className="text-2xl font-bold font-mono text-cyan-400">
            {summary?.unresolved_conflicts ?? conflicts.filter((c) => c.resolution_status === "unresolved").length}
          </div>
          <div className="text-[11px] text-slate-500 mt-1">
            {summary?.resolved_count ?? 0} resolved
          </div>
        </div>
      </div>

      {/* 3. Filter and Search Toolbar */}
      <div className="p-3 bg-dark-900/50 border border-dark-700/60 rounded-xl flex flex-wrap items-center justify-between gap-3 text-xs">
        {/* Search */}
        <div className="relative flex-1 min-w-[200px] max-w-sm">
          <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            placeholder="Search claims, sources, or explanations..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-dark-800 border border-dark-700/80 rounded-lg pl-8 pr-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500"
          />
        </div>

        {/* Filter Pills */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Classification Filter */}
          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            className="bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-slate-100 font-medium focus:outline-none focus:border-cyan-500 cursor-pointer"
          >
            <option value="ALL" className="bg-slate-900 text-slate-100">All Classifications</option>
            <option value="DIRECT_CONTRADICTION" className="bg-slate-900 text-slate-100">Direct Contradictions</option>
            <option value="NUMERICAL_CONFLICT" className="bg-slate-900 text-slate-100">Numerical Conflicts</option>
            <option value="TEMPORAL_CONFLICT" className="bg-slate-900 text-slate-100">Temporal Conflicts</option>
            <option value="CONTEXTUAL_TENSION" className="bg-slate-900 text-slate-100">Contextual Tensions</option>
            <option value="METHODOLOGICAL_DISAGREEMENT" className="bg-slate-900 text-slate-100">Methodological Disagreements</option>
            <option value="UNRESOLVED_CONFLICT" className="bg-slate-900 text-slate-100">Unresolved Conflicts</option>
          </select>

          {/* Severity Filter */}
          <select
            value={severityFilter}
            onChange={(e) => setSeverityFilter(e.target.value)}
            className="bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-slate-100 font-medium focus:outline-none focus:border-cyan-500 cursor-pointer"
          >
            <option value="ALL" className="bg-slate-900 text-slate-100">All Severities</option>
            <option value="CRITICAL" className="bg-slate-900 text-slate-100">Critical</option>
            <option value="HIGH" className="bg-slate-900 text-slate-100">High</option>
            <option value="MEDIUM" className="bg-slate-900 text-slate-100">Medium</option>
            <option value="LOW" className="bg-slate-900 text-slate-100">Low</option>
          </select>

          {/* Resolution Status Filter */}
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-slate-100 font-medium focus:outline-none focus:border-cyan-500 cursor-pointer"
          >
            <option value="ALL" className="bg-slate-900 text-slate-100">All Statuses</option>
            <option value="unresolved" className="bg-slate-900 text-slate-100">Unresolved</option>
            <option value="under_review" className="bg-slate-900 text-slate-100">Under Review</option>
            <option value="resolved" className="bg-slate-900 text-slate-100">Resolved</option>
          </select>

          {(typeFilter !== "ALL" || severityFilter !== "ALL" || statusFilter !== "ALL" || searchQuery) && (
            <button
              onClick={() => {
                setTypeFilter("ALL");
                setSeverityFilter("ALL");
                setStatusFilter("ALL");
                setSearchQuery("");
              }}
              className="px-2.5 py-1 rounded bg-dark-800 hover:bg-dark-700 text-slate-400 hover:text-slate-200 text-xs transition"
            >
              Reset Filters
            </button>
          )}
        </div>
      </div>

      {/* 4. Master-Detail Split Workspace */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Side: Conflict Feed (5 cols on lg) */}
        <div className="lg:col-span-5 space-y-3">
          <div className="flex items-center justify-between px-1 text-xs text-slate-400 font-medium">
            <span>Detected Conflicts ({filteredConflicts.length})</span>
            {lastAnalyzedAt && (
              <span className="text-[11px] text-slate-500 font-mono">
                Last run: {new Date(lastAnalyzedAt).toLocaleTimeString()}
              </span>
            )}
          </div>

          {isLoading ? (
            <div className="p-8 text-center bg-dark-900/50 border border-dark-700/60 rounded-xl space-y-3">
              <RefreshCw className="w-6 h-6 animate-spin text-cyan-400 mx-auto" />
              <p className="text-xs text-slate-400">Loading conflict evidence ledger...</p>
            </div>
          ) : filteredConflicts.length === 0 ? (
            <div className="p-8 text-center bg-dark-900/40 border border-dark-700/60 rounded-xl space-y-3">
              <FileCheck className="w-8 h-8 text-emerald-400/80 mx-auto" />
              <div className="text-sm font-semibold text-slate-200">
                {conflicts.length === 0 ? "No Conflicts Detected" : "No Matching Conflicts"}
              </div>
              <p className="text-xs text-slate-400 max-w-sm mx-auto">
                {conflicts.length === 0
                  ? "Click 'Detect Conflicts' above to initiate cross-document claim cross-examination with structured reasoning."
                  : "No conflicts match your current search and filter criteria."}
              </p>
            </div>
          ) : (
            <div className="space-y-2.5 max-h-[750px] overflow-y-auto pr-1">
              {filteredConflicts.map((c) => {
                const isSelected = c.conflict_id === selectedConflictId;
                return (
                  <div
                    key={c.conflict_id}
                    onClick={() => setSelectedConflictId(c.conflict_id)}
                    className={`p-3.5 rounded-xl border transition cursor-pointer relative ${
                      isSelected
                        ? "bg-dark-800/90 border-cyan-500 shadow-lg shadow-cyan-950/20 ring-1 ring-cyan-500/50"
                        : "bg-dark-900/60 border-dark-700/70 hover:bg-dark-850 hover:border-dark-600"
                    }`}
                  >
                    {/* Top Row: Badges */}
                    <div className="flex items-center justify-between gap-2 mb-2">
                      <div className="flex items-center gap-1.5 flex-wrap">
                        {getSeverityBadge(c.severity)}
                        <span className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-dark-700 text-slate-300">
                          {formatConflictTypeName(c.conflict_type)}
                        </span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        {getStatusBadge(c.resolution_status)}
                        <span className="text-[10px] font-mono text-slate-500">
                          {Math.round(c.confidence * 100)}%
                        </span>
                      </div>
                    </div>

                    {/* Claims Preview */}
                    <div className="space-y-1.5 text-xs">
                      <div className="p-2 rounded bg-dark-950/60 border border-dark-800">
                        <div className="text-[10px] text-cyan-400 font-mono flex items-center gap-1 mb-0.5 truncate">
                          <span className="w-1.5 h-1.5 rounded-full bg-cyan-400" />
                          <span>{c.source_a_title || "Source A"}</span>
                        </div>
                        <p className="text-slate-300 line-clamp-2 italic">
                          "{c.claim_a_text}"
                        </p>
                      </div>

                      <div className="p-2 rounded bg-dark-950/60 border border-dark-800">
                        <div className="text-[10px] text-rose-400 font-mono flex items-center gap-1 mb-0.5 truncate">
                          <span className="w-1.5 h-1.5 rounded-full bg-rose-400" />
                          <span>{c.source_b_title || "Source B"}</span>
                        </div>
                        <p className="text-slate-300 line-clamp-2 italic">
                          "{c.claim_b_text}"
                        </p>
                      </div>
                    </div>

                    {/* Explanation Snippet */}
                    <p className="text-[11px] text-slate-400 mt-2 line-clamp-2">
                      {c.explanation}
                    </p>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Right Side: Deep-Dive Forensic Inspector (7 cols on lg) */}
        <div className="lg:col-span-7">
          {selectedConflict ? (
            <div className="p-5 bg-dark-900/80 border border-dark-700/80 rounded-2xl space-y-6 shadow-xl sticky top-4">
              {/* Inspector Header */}
              <div className="flex items-start justify-between gap-3 border-b border-dark-700/60 pb-4">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    {getSeverityBadge(selectedConflict.severity)}
                    <span className="text-xs font-mono font-bold text-white uppercase tracking-wider">
                      {formatConflictTypeName(selectedConflict.conflict_type)}
                    </span>
                    <span className="text-[10px] font-mono text-slate-500">
                      ID: {selectedConflict.conflict_id.slice(0, 8)}
                    </span>
                  </div>
                  <h3 className="text-sm font-semibold text-slate-200">
                    Forensic Contradiction Dossier
                  </h3>
                </div>

                <div className="flex items-center gap-2">
                  {getStatusBadge(selectedConflict.resolution_status)}
                </div>
              </div>

              {/* Side-by-Side Claim Dossiers */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {/* Claim A Dossier */}
                <div className="p-3.5 bg-dark-950/80 border border-dark-800 rounded-xl space-y-3">
                  <div className="flex items-center justify-between text-xs border-b border-dark-800 pb-2">
                    <span className="font-mono text-cyan-400 text-[11px] font-semibold flex items-center gap-1">
                      <span className="w-2 h-2 rounded-full bg-cyan-400" />
                      CLAIM A
                    </span>
                    {selectedConflict.claim_a_category && (
                      <span className="px-1.5 py-0.5 rounded text-[10px] bg-dark-800 text-slate-400">
                        {selectedConflict.claim_a_category}
                      </span>
                    )}
                  </div>

                  <div>
                    <div className="text-[10px] text-slate-500 uppercase font-mono mb-1">Source Artifact</div>
                    <div className="text-xs font-medium text-slate-200 flex items-center gap-1.5">
                      <FileText className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
                      <span className="truncate">{selectedConflict.source_a_title || "Primary Source"}</span>
                      {selectedConflict.source_a_url && (
                        <a
                          href={selectedConflict.source_a_url}
                          target="_blank"
                          rel="noreferrer"
                          className="text-cyan-400 hover:text-cyan-300 ml-auto shrink-0"
                        >
                          <ExternalLink className="w-3 h-3" />
                        </a>
                      )}
                    </div>
                  </div>

                  <div>
                    <div className="text-[10px] text-slate-500 uppercase font-mono mb-1">Extracted Atomic Claim</div>
                    <p className="text-xs text-slate-100 font-medium bg-dark-900/80 p-2 rounded-lg border border-dark-800/80">
                      "{selectedConflict.claim_a_text}"
                    </p>
                  </div>

                  {selectedConflict.passage_a_text && (
                    <div>
                      <div className="text-[10px] text-slate-500 uppercase font-mono mb-1">Original Source Passage</div>
                      <p className="text-[11px] text-slate-400 italic bg-dark-900/40 p-2.5 rounded-lg border border-dark-800/50 max-h-28 overflow-y-auto">
                        "{selectedConflict.passage_a_text}"
                      </p>
                    </div>
                  )}

                  {/* Provenance Coordinates */}
                  <div className="pt-2 border-t border-dark-800/80 flex flex-wrap items-center gap-2 text-[10px] font-mono text-slate-400">
                    {selectedConflict.passage_a_page && (
                      <span className="px-1.5 py-0.5 rounded bg-dark-900 border border-dark-800">
                        Page {selectedConflict.passage_a_page}
                      </span>
                    )}
                    {selectedConflict.passage_a_hash && (
                      <span className="px-1.5 py-0.5 rounded bg-dark-900 border border-dark-800 truncate max-w-[120px]" title={selectedConflict.passage_a_hash}>
                        SHA: {selectedConflict.passage_a_hash.slice(0, 8)}...
                      </span>
                    )}
                  </div>
                </div>

                {/* Claim B Dossier */}
                <div className="p-3.5 bg-dark-950/80 border border-dark-800 rounded-xl space-y-3">
                  <div className="flex items-center justify-between text-xs border-b border-dark-800 pb-2">
                    <span className="font-mono text-rose-400 text-[11px] font-semibold flex items-center gap-1">
                      <span className="w-2 h-2 rounded-full bg-rose-400" />
                      CLAIM B
                    </span>
                    {selectedConflict.claim_b_category && (
                      <span className="px-1.5 py-0.5 rounded text-[10px] bg-dark-800 text-slate-400">
                        {selectedConflict.claim_b_category}
                      </span>
                    )}
                  </div>

                  <div>
                    <div className="text-[10px] text-slate-500 uppercase font-mono mb-1">Source Artifact</div>
                    <div className="text-xs font-medium text-slate-200 flex items-center gap-1.5">
                      <FileText className="w-3.5 h-3.5 text-rose-400 shrink-0" />
                      <span className="truncate">{selectedConflict.source_b_title || "Opposing Source"}</span>
                      {selectedConflict.source_b_url && (
                        <a
                          href={selectedConflict.source_b_url}
                          target="_blank"
                          rel="noreferrer"
                          className="text-rose-400 hover:text-rose-300 ml-auto shrink-0"
                        >
                          <ExternalLink className="w-3 h-3" />
                        </a>
                      )}
                    </div>
                  </div>

                  <div>
                    <div className="text-[10px] text-slate-500 uppercase font-mono mb-1">Extracted Atomic Claim</div>
                    <p className="text-xs text-slate-100 font-medium bg-dark-900/80 p-2 rounded-lg border border-dark-800/80">
                      "{selectedConflict.claim_b_text}"
                    </p>
                  </div>

                  {selectedConflict.passage_b_text && (
                    <div>
                      <div className="text-[10px] text-slate-500 uppercase font-mono mb-1">Original Source Passage</div>
                      <p className="text-[11px] text-slate-400 italic bg-dark-900/40 p-2.5 rounded-lg border border-dark-800/50 max-h-28 overflow-y-auto">
                        "{selectedConflict.passage_b_text}"
                      </p>
                    </div>
                  )}

                  {/* Provenance Coordinates */}
                  <div className="pt-2 border-t border-dark-800/80 flex flex-wrap items-center gap-2 text-[10px] font-mono text-slate-400">
                    {selectedConflict.passage_b_page && (
                      <span className="px-1.5 py-0.5 rounded bg-dark-900 border border-dark-800">
                        Page {selectedConflict.passage_b_page}
                      </span>
                    )}
                    {selectedConflict.passage_b_hash && (
                      <span className="px-1.5 py-0.5 rounded bg-dark-900 border border-dark-800 truncate max-w-[120px]" title={selectedConflict.passage_b_hash}>
                        SHA: {selectedConflict.passage_b_hash.slice(0, 8)}...
                      </span>
                    )}
                  </div>
                </div>
              </div>

              {/* Forensic Analysis & Explanations */}
              <div className="space-y-3 bg-dark-950/50 p-4 rounded-xl border border-dark-800">
                <div>
                  <div className="text-[11px] font-mono text-rose-400 uppercase font-semibold mb-1 flex items-center gap-1.5">
                    <AlertTriangle className="w-3.5 h-3.5" />
                    <span>Contradiction Rationale</span>
                  </div>
                  <p className="text-xs text-slate-200 leading-relaxed">
                    {selectedConflict.explanation}
                  </p>
                </div>

                {selectedConflict.contextual_differences && (
                  <div className="pt-3 border-t border-dark-800">
                    <div className="text-[11px] font-mono text-indigo-400 uppercase font-semibold mb-1 flex items-center gap-1.5">
                      <Layers className="w-3.5 h-3.5" />
                      <span>Contextual Variance & Confounding Factors</span>
                    </div>
                    <p className="text-xs text-slate-300 leading-relaxed">
                      {selectedConflict.contextual_differences}
                    </p>
                  </div>
                )}

                <div className="pt-3 border-t border-dark-800">
                  <div className="text-[11px] font-mono text-cyan-400 uppercase font-semibold mb-1 flex items-center gap-1.5">
                    <Info className="w-3.5 h-3.5" />
                    <span>Recommended Analyst Action</span>
                  </div>
                  <p className="text-xs text-slate-300 leading-relaxed">
                    {selectedConflict.recommended_action}
                  </p>
                </div>

                {/* Audit & Method Trail */}
                <div className="pt-3 border-t border-dark-800 flex flex-wrap items-center justify-between text-[10px] font-mono text-slate-500">
                  <span>Engine: {selectedConflict.analysis_method}</span>
                  <span>Confidence: {Math.round(selectedConflict.confidence * 100)}%</span>
                  <span>Evaluated via {selectedConflict.processing_mode.toUpperCase()}</span>
                </div>
              </div>

              {/* Analyst Resolution Workflow Controls */}
              <div className="p-4 bg-dark-950/70 border border-dark-800 rounded-xl space-y-3">
                <div className="flex items-center justify-between">
                  <div className="text-xs font-bold text-slate-200 uppercase font-mono">
                    Analyst Resolution & Audit Verdict
                  </div>
                  <span className="text-[11px] text-slate-500">Human forensic review</span>
                </div>

                {/* Status Toggle Buttons */}
                <div className="grid grid-cols-3 gap-2">
                  <button
                    type="button"
                    onClick={() => setEditStatus("unresolved")}
                    className={`py-2 px-3 rounded-lg text-xs font-mono font-medium border transition ${
                      editStatus === "unresolved"
                        ? "bg-rose-500/15 border-rose-500/50 text-rose-300"
                        : "bg-dark-900 border-dark-800 text-slate-400 hover:bg-dark-850"
                    }`}
                  >
                    Unresolved
                  </button>
                  <button
                    type="button"
                    onClick={() => setEditStatus("under_review")}
                    className={`py-2 px-3 rounded-lg text-xs font-mono font-medium border transition ${
                      editStatus === "under_review"
                        ? "bg-amber-500/15 border-amber-500/50 text-amber-300"
                        : "bg-dark-900 border-dark-800 text-slate-400 hover:bg-dark-850"
                    }`}
                  >
                    Under Review
                  </button>
                  <button
                    type="button"
                    onClick={() => setEditStatus("resolved")}
                    className={`py-2 px-3 rounded-lg text-xs font-mono font-medium border transition ${
                      editStatus === "resolved"
                        ? "bg-emerald-500/15 border-emerald-500/50 text-emerald-300"
                        : "bg-dark-900 border-dark-800 text-slate-400 hover:bg-dark-850"
                    }`}
                  >
                    Resolved
                  </button>
                </div>

                {/* Reviewer Notes Textarea */}
                <div>
                  <label className="block text-[11px] font-mono text-slate-400 mb-1">
                    Forensic Reviewer Notes & Justification:
                  </label>
                  <textarea
                    rows={3}
                    value={editNotes}
                    onChange={(e) => setEditNotes(e.target.value)}
                    placeholder="Enter audit notes on why this conflict was resolved, verified, or escalated..."
                    className="w-full bg-dark-900 border border-dark-800 rounded-lg p-2.5 text-xs text-slate-200 placeholder-slate-600 focus:outline-none focus:border-cyan-500"
                  />
                </div>

                {/* Save Button */}
                <div className="flex justify-end">
                  <Button
                    onClick={handleSaveResolution}
                    disabled={isSavingResolution}
                    className="bg-cyan-600 hover:bg-cyan-500 text-white text-xs px-3.5 py-2 flex items-center gap-1.5"
                  >
                    {isSavingResolution ? (
                      <>
                        <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                        <span>Saving Verdict...</span>
                      </>
                    ) : (
                      <>
                        <Save className="w-3.5 h-3.5" />
                        <span>Save Resolution Verdict</span>
                      </>
                    )}
                  </Button>
                </div>
              </div>
            </div>
          ) : (
            <div className="p-12 text-center bg-dark-900/30 border border-dark-700/60 rounded-2xl">
              <ShieldAlert className="w-10 h-10 text-slate-600 mx-auto mb-3" />
              <h3 className="text-sm font-semibold text-slate-300">No Conflict Selected</h3>
              <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
                Select an evidence contradiction from the feed to examine side-by-side excerpts, cryptographic provenance, and record resolution verdicts.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
