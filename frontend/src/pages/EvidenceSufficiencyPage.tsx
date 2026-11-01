import { useState, useEffect, useMemo } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import {
  listInvestigations,
  getInvestigationSufficiency,
  analyzeInvestigationSufficiency,
  Investigation,
  RequirementSufficiencyAssessment,
  SufficiencySummary,
  CoverageStatus,
} from "@/lib/api";
import {
  CheckCircle2,
  AlertTriangle,
  Layers,
  Sparkles,
  RefreshCw,
  Search,
  ExternalLink,
  FileText,
  ShieldAlert,
  ArrowRight,
  Info,
  Clock,
  Network,
  X,
  Compass,
} from "lucide-react";
import { Button } from "@/components/ui/Button";

export function EvidenceSufficiencyPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();

  // Navigation & Data State
  const [investigations, setInvestigations] = useState<Investigation[]>([]);
  const [selectedInvId, setSelectedInvId] = useState<string | null>(null);
  const [assessments, setAssessments] = useState<RequirementSufficiencyAssessment[]>([]);
  const [summary, setSummary] = useState<SufficiencySummary | null>(null);
  const [decisionObjective, setDecisionObjective] = useState<string | null>(null);
  const [processingMode, setProcessingMode] = useState<"gemini" | "fallback" | "pending">("pending");
  const [lastAnalyzedAt, setLastAnalyzedAt] = useState<string | null>(null);

  // Inspector & Selection State
  const [selectedReqId, setSelectedReqId] = useState<string | null>(null);

  // Loading & Action State
  const [isLoading, setIsLoading] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Filter States
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("ALL");
  const [priorityFilter, setPriorityFilter] = useState<string>("ALL");

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

  // 2. Fetch Sufficiency when investigation changes
  useEffect(() => {
    if (!selectedInvId) return;

    let isMounted = true;
    async function fetchSufficiency() {
      setIsLoading(true);
      setErrorMessage(null);
      try {
        const data = await getInvestigationSufficiency(selectedInvId!);
        if (!isMounted) return;
        setAssessments(data.assessments);
        setSummary(data.summary);
        setDecisionObjective(data.decision_objective || null);
        setProcessingMode(data.processing_mode);
        setLastAnalyzedAt(data.last_analyzed_at || null);

        if (data.assessments.length > 0) {
          setSelectedReqId(data.assessments[0].requirement_id);
        } else {
          setSelectedReqId(null);
        }
      } catch (err: any) {
        if (isMounted) setErrorMessage(err.message || "Failed to load sufficiency data");
      } finally {
        if (isMounted) setIsLoading(false);
      }
    }

    fetchSufficiency();
    return () => {
      isMounted = false;
    };
  }, [selectedInvId]);

  // Selected assessment item
  const selectedAssessment = useMemo(() => {
    return assessments.find((a) => a.requirement_id === selectedReqId) || null;
  }, [assessments, selectedReqId]);

  // Trigger Sufficiency Analysis
  const handleAnalyze = async () => {
    if (!selectedInvId || isAnalyzing) return;
    setIsAnalyzing(true);
    setErrorMessage(null);

    try {
      const result = await analyzeInvestigationSufficiency(selectedInvId);
      setAssessments(result.assessments);
      setSummary(result.summary);
      setDecisionObjective(result.decision_objective || null);
      setProcessingMode(result.processing_mode);
      setLastAnalyzedAt(result.last_analyzed_at || null);

      if (result.assessments.length > 0) {
        setSelectedReqId(result.assessments[0].requirement_id);
      }
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to analyze sufficiency");
    } finally {
      setIsAnalyzing(false);
    }
  };

  // Filtered requirements list
  const filteredAssessments = useMemo(() => {
    return assessments.filter((a) => {
      if (statusFilter !== "ALL" && a.coverage_status !== statusFilter) return false;
      if (priorityFilter !== "ALL" && a.priority.toUpperCase() !== priorityFilter) return false;

      if (searchQuery.trim()) {
        const query = searchQuery.toLowerCase();
        const matchesTitle = (a.requirement_title || "").toLowerCase().includes(query);
        const matchesDesc = (a.requirement_description || "").toLowerCase().includes(query);
        const matchesCrit = (a.verification_criteria || "").toLowerCase().includes(query);
        const matchesSum = (a.assessment_summary || "").toLowerCase().includes(query);
        const matchesGaps = (a.gaps || []).some(
          (g) =>
            (g.gap_description || "").toLowerCase().includes(query) ||
            (g.evidence_needed || "").toLowerCase().includes(query)
        );
        if (!matchesTitle && !matchesDesc && !matchesCrit && !matchesSum && !matchesGaps) {
          return false;
        }
      }
      return true;
    });
  }, [assessments, statusFilter, priorityFilter, searchQuery]);

  // Status Badge Helper
  const getStatusBadge = (status: CoverageStatus) => {
    switch (status) {
      case "SUFFICIENT":
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 flex items-center gap-1">
            <CheckCircle2 className="w-3 h-3" />
            <span>SUFFICIENT</span>
          </span>
        );
      case "PARTIAL":
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-amber-500/15 text-amber-400 border border-amber-500/30 flex items-center gap-1">
            <Clock className="w-3 h-3" />
            <span>PARTIAL</span>
          </span>
        );
      case "INSUFFICIENT":
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-orange-500/15 text-orange-400 border border-orange-500/30 flex items-center gap-1">
            <AlertTriangle className="w-3 h-3" />
            <span>INSUFFICIENT</span>
          </span>
        );
      case "NO_EVIDENCE":
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-slate-800 text-slate-400 border border-slate-700 flex items-center gap-1">
            <span>NO EVIDENCE</span>
          </span>
        );
      case "CONFLICTING":
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-rose-500/20 text-rose-400 border border-rose-500/30 flex items-center gap-1">
            <ShieldAlert className="w-3 h-3" />
            <span>CONFLICTING</span>
          </span>
        );
      default:
        return <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-slate-800 text-slate-400">{status}</span>;
    }
  };

  const getPriorityBadge = (priority: string) => {
    const p = (priority || "").toUpperCase();
    if (p === "CRITICAL") {
      return <span className="px-1.5 py-0.5 rounded text-[10px] font-mono font-semibold bg-rose-500/20 text-rose-400 border border-rose-500/30">CRITICAL</span>;
    }
    if (p === "HIGH") {
      return <span className="px-1.5 py-0.5 rounded text-[10px] font-mono font-semibold bg-orange-500/20 text-orange-400 border border-orange-500/30">HIGH</span>;
    }
    if (p === "MEDIUM") {
      return <span className="px-1.5 py-0.5 rounded text-[10px] font-mono font-semibold bg-amber-500/20 text-amber-400 border border-amber-500/30">MEDIUM</span>;
    }
    return <span className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-slate-800 text-slate-400 border border-slate-700">LOW</span>;
  };

  return (
    <div className="space-y-6 pb-12">
      {/* 1. Header Toolbar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-dark-700/60 pb-5">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="p-2 bg-emerald-500/10 border border-emerald-500/20 rounded-lg text-emerald-400">
              <CheckCircle2 className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
                Evidence Coverage
              </h1>
              <p className="text-xs text-slate-400 mt-0.5">
                Check whether available evidence satisfies each decision requirement, and see what is missing.
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
            className="bg-gradient-to-r from-emerald-600 to-cyan-600 hover:from-emerald-500 hover:to-cyan-500 text-white font-medium text-xs px-3.5 py-2 flex items-center gap-2 shadow-lg shadow-emerald-950/20"
          >
            {isAnalyzing ? (
              <>
                <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                <span>Checking Coverage...</span>
              </>
            ) : (
              <>
                <Sparkles className="w-3.5 h-3.5" />
                <span>Check Evidence Coverage</span>
              </>
            )}
          </Button>
        </div>
      </div>

      {/* Error Banner */}
      {errorMessage && (
        <div className="p-3 bg-rose-500/10 border border-rose-500/20 rounded-lg flex items-center gap-2.5 text-xs text-rose-300">
          <AlertTriangle className="w-4 h-4 shrink-0 text-rose-400" />
          <span>{errorMessage}</span>
          <button onClick={() => setErrorMessage(null)} className="ml-auto text-rose-400 hover:text-rose-200">
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* 2. Overview KPI Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-6 gap-3">
        <div className="p-3.5 bg-dark-900/70 border border-dark-700/60 rounded-xl relative overflow-hidden">
          <div className="flex items-center justify-between text-slate-400 text-xs mb-1">
            <span>Requirements</span>
            <Layers className="w-4 h-4 text-slate-400" />
          </div>
          <div className="text-2xl font-bold font-mono text-white">
            {summary?.total_requirements ?? assessments.length}
          </div>
          <div className="text-[11px] text-slate-500 mt-1">Decision requirements</div>
        </div>

        <div className="p-3.5 bg-dark-900/70 border border-emerald-500/20 rounded-xl relative overflow-hidden">
          <div className="flex items-center justify-between text-emerald-400 text-xs mb-1">
            <span>Supported</span>
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-2xl font-bold font-mono text-emerald-400">
            {summary?.sufficient_count ?? 0}
          </div>
          <div className="text-[11px] text-slate-500 mt-1">Well-supported</div>
        </div>

        <div className="p-3.5 bg-dark-900/70 border border-amber-500/20 rounded-xl relative overflow-hidden">
          <div className="flex items-center justify-between text-amber-400 text-xs mb-1">
            <span>Partially Supported</span>
            <Clock className="w-4 h-4 text-amber-400" />
          </div>
          <div className="text-2xl font-bold font-mono text-amber-400">
            {summary?.partial_count ?? 0}
          </div>
          <div className="text-[11px] text-slate-500 mt-1">Needs more evidence</div>
        </div>

        <div className="p-3.5 bg-dark-900/70 border border-orange-500/20 rounded-xl relative overflow-hidden">
          <div className="flex items-center justify-between text-orange-400 text-xs mb-1">
            <span>Missing Evidence</span>
            <AlertTriangle className="w-4 h-4 text-orange-400" />
          </div>
          <div className="text-2xl font-bold font-mono text-orange-400">
            {(summary?.insufficient_count ?? 0) + (summary?.no_evidence_count ?? 0)}
          </div>
          <div className="text-[11px] text-slate-500 mt-1">
            {summary?.no_evidence_count ?? 0} have no evidence
          </div>
        </div>

        <div className="p-3.5 bg-dark-900/70 border border-rose-500/20 rounded-xl relative overflow-hidden">
          <div className="flex items-center justify-between text-rose-400 text-xs mb-1">
            <span>Conflicting</span>
            <ShieldAlert className="w-4 h-4 text-rose-400" />
          </div>
          <div className="text-2xl font-bold font-mono text-rose-400">
            {summary?.conflicting_count ?? 0}
          </div>
          <div className="text-[11px] text-slate-500 mt-1">Blocked by conflicts</div>
        </div>

        <div className="p-3.5 bg-dark-900/70 border border-indigo-500/20 rounded-xl relative overflow-hidden">
          <div className="flex items-center justify-between text-indigo-400 text-xs mb-1">
            <span>Evidence Gaps</span>
            <Compass className="w-4 h-4 text-indigo-400" />
          </div>
          <div className="text-2xl font-bold font-mono text-indigo-400">
            {summary?.total_gaps ?? 0}
          </div>
          <div className="text-[11px] text-slate-500 mt-1">
            {summary?.high_priority_gaps ?? 0} high priority
          </div>
        </div>
      </div>

      {/* Decision Objective & Coverage Calculation Card */}
      {decisionObjective && (
        <div className="p-3.5 bg-dark-900/40 border border-dark-700/60 rounded-xl flex flex-col md:flex-row md:items-center justify-between gap-3 text-xs">
          <div className="space-y-0.5">
            <span className="text-[10px] font-mono text-slate-500 uppercase tracking-wider">
              Decision Contract Objective
            </span>
            <p className="text-slate-200 font-medium">"{decisionObjective}"</p>
          </div>

          {summary && summary.overall_coverage_ratio !== undefined && (
            <div className="shrink-0 flex items-center gap-3 bg-dark-800/80 px-3 py-1.5 rounded-lg border border-dark-700">
              <span className="text-[11px] text-slate-400 font-mono">Coverage Completeness:</span>
              <span className="text-sm font-bold font-mono text-cyan-400">
                {Math.round(summary.overall_coverage_ratio * 100)}%
              </span>
            </div>
          )}
        </div>
      )}

      {/* 3. Filter and Search Toolbar */}
      <div className="p-3 bg-dark-900/50 border border-dark-700/60 rounded-xl flex flex-wrap items-center justify-between gap-3 text-xs">
        {/* Search */}
        <div className="relative flex-1 min-w-[200px] max-w-sm">
          <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            placeholder="Search requirements, criteria, or evidence gaps..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-dark-800 border border-dark-700/80 rounded-lg pl-8 pr-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500"
          />
        </div>

        {/* Filter Dropdowns */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Status Filter */}
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-slate-100 font-medium focus:outline-none focus:border-cyan-500 cursor-pointer"
          >
            <option value="ALL" className="bg-slate-900 text-slate-100">All Coverage Statuses</option>
            <option value="SUFFICIENT" className="bg-slate-900 text-slate-100">Sufficient</option>
            <option value="PARTIAL" className="bg-slate-900 text-slate-100">Partial</option>
            <option value="INSUFFICIENT" className="bg-slate-900 text-slate-100">Insufficient</option>
            <option value="NO_EVIDENCE" className="bg-slate-900 text-slate-100">No Evidence</option>
            <option value="CONFLICTING" className="bg-slate-900 text-slate-100">Conflicting</option>
          </select>

          {/* Priority Filter */}
          <select
            value={priorityFilter}
            onChange={(e) => setPriorityFilter(e.target.value)}
            className="bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-slate-100 font-medium focus:outline-none focus:border-cyan-500 cursor-pointer"
          >
            <option value="ALL" className="bg-slate-900 text-slate-100">All Priorities</option>
            <option value="CRITICAL" className="bg-slate-900 text-slate-100">Critical</option>
            <option value="HIGH" className="bg-slate-900 text-slate-100">High</option>
            <option value="MEDIUM" className="bg-slate-900 text-slate-100">Medium</option>
            <option value="LOW" className="bg-slate-900 text-slate-100">Low</option>
          </select>

          {(statusFilter !== "ALL" || priorityFilter !== "ALL" || searchQuery) && (
            <button
              onClick={() => {
                setStatusFilter("ALL");
                setPriorityFilter("ALL");
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
        {/* Left Side: Requirement Coverage Feed (5 cols on lg) */}
        <div className="lg:col-span-5 space-y-3">
          <div className="flex items-center justify-between px-1 text-xs text-slate-400 font-medium">
            <span>Contract Requirements ({filteredAssessments.length})</span>
            {lastAnalyzedAt && (
              <span className="text-[11px] text-slate-500 font-mono">
                Audit: {new Date(lastAnalyzedAt).toLocaleTimeString()}
              </span>
            )}
          </div>

          {isLoading ? (
            <div className="p-8 text-center bg-dark-900/50 border border-dark-700/60 rounded-xl space-y-3">
              <RefreshCw className="w-6 h-6 animate-spin text-cyan-400 mx-auto" />
              <p className="text-xs text-slate-400">Loading sufficiency assessments...</p>
            </div>
          ) : filteredAssessments.length === 0 ? (
            <div className="p-8 text-center bg-dark-900/40 border border-dark-700/60 rounded-xl space-y-3">
              <Compass className="w-8 h-8 text-emerald-400/80 mx-auto" />
              <div className="text-sm font-semibold text-slate-200">
                {assessments.length === 0 ? "No Contract Requirements Found" : "No Matching Requirements"}
              </div>
              <p className="text-xs text-slate-400 max-w-sm mx-auto">
                {assessments.length === 0
                  ? "Compile a Decision Contract in Decision Contract Studio or click 'Run Sufficiency Audit' above to evaluate evidence coverage."
                  : "No requirements match your current search and filter criteria."}
              </p>
            </div>
          ) : (
            <div className="space-y-2.5 max-h-[750px] overflow-y-auto pr-1">
              {filteredAssessments.map((asm) => {
                const isSelected = asm.requirement_id === selectedReqId;
                return (
                  <div
                    key={asm.requirement_id}
                    onClick={() => setSelectedReqId(asm.requirement_id)}
                    className={`p-3.5 rounded-xl border transition cursor-pointer relative ${
                      isSelected
                        ? "bg-dark-800/90 border-cyan-500 shadow-lg shadow-cyan-950/20 ring-1 ring-cyan-500/50"
                        : "bg-dark-900/60 border-dark-700/70 hover:bg-dark-850 hover:border-dark-600"
                    }`}
                  >
                    {/* Top Row: Badges */}
                    <div className="flex items-center justify-between gap-2 mb-1.5">
                      <div className="flex items-center gap-1.5 flex-wrap">
                        {getStatusBadge(asm.coverage_status)}
                        {getPriorityBadge(asm.priority)}
                      </div>
                      <div className="flex items-center gap-1.5 text-[10px] font-mono text-slate-400">
                        <span>{asm.supporting_claims.length} claims</span>
                        {asm.gaps.length > 0 && (
                          <span className="px-1.5 py-0.5 rounded bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                            {asm.gaps.length} gaps
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Title */}
                    <h4 className="text-xs font-semibold text-white line-clamp-1 mb-1">
                      {asm.requirement_title}
                    </h4>

                    {/* Assessment Summary Snippet */}
                    <p className="text-[11px] text-slate-400 line-clamp-2 leading-relaxed">
                      {asm.assessment_summary}
                    </p>

                    {/* Conflict Alert Banner if affected */}
                    {asm.unresolved_conflict_count > 0 && (
                      <div className="mt-2 p-1.5 rounded bg-rose-500/10 border border-rose-500/20 text-[10px] text-rose-300 flex items-center gap-1">
                        <ShieldAlert className="w-3 h-3 text-rose-400 shrink-0" />
                        <span className="truncate">
                          Contested by {asm.unresolved_conflict_count} unresolved conflict(s)
                        </span>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Right Side: Deep-Dive Requirement Inspector (7 cols on lg) */}
        <div className="lg:col-span-7">
          {selectedAssessment ? (
            <div className="p-5 bg-dark-900/80 border border-dark-700/80 rounded-2xl space-y-6 shadow-xl sticky top-4 max-h-[850px] overflow-y-auto">
              {/* Header */}
              <div className="flex items-start justify-between gap-3 border-b border-dark-700/60 pb-4">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    {getStatusBadge(selectedAssessment.coverage_status)}
                    {getPriorityBadge(selectedAssessment.priority)}
                    <span className="text-[10px] font-mono text-slate-500">
                      ID: {selectedAssessment.requirement_id.slice(0, 8)}
                    </span>
                  </div>
                  <h3 className="text-base font-bold text-white">
                    {selectedAssessment.requirement_title}
                  </h3>
                  <p className="text-xs text-slate-400 mt-1 leading-relaxed">
                    {selectedAssessment.requirement_description}
                  </p>
                </div>
              </div>

              {/* Verification Criteria */}
              <div className="p-3.5 bg-dark-950/70 border border-dark-800 rounded-xl space-y-1">
                <span className="text-[10px] font-mono text-cyan-400 uppercase tracking-wider font-semibold">
                  Verification Criteria
                </span>
                <p className="text-xs text-slate-300 font-medium">
                  {selectedAssessment.verification_criteria}
                </p>
              </div>

              {/* Forensic Sufficiency Assessment */}
              <div className="space-y-3 bg-dark-950/50 p-4 rounded-xl border border-dark-800">
                <div>
                  <div className="text-[11px] font-mono text-emerald-400 uppercase font-semibold mb-1 flex items-center gap-1.5">
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    <span>Sufficiency Assessment</span>
                  </div>
                  <p className="text-xs text-slate-200 leading-relaxed">
                    {selectedAssessment.assessment_summary}
                  </p>
                </div>

                {selectedAssessment.limitations && (
                  <div className="pt-3 border-t border-dark-800">
                    <div className="text-[11px] font-mono text-amber-400 uppercase font-semibold mb-1 flex items-center gap-1.5">
                      <AlertTriangle className="w-3.5 h-3.5" />
                      <span>Evidence Limitations & Weaknesses</span>
                    </div>
                    <p className="text-xs text-slate-300 leading-relaxed">
                      {selectedAssessment.limitations}
                    </p>
                  </div>
                )}

                {selectedAssessment.missing_information && (
                  <div className="pt-3 border-t border-dark-800">
                    <div className="text-[11px] font-mono text-orange-400 uppercase font-semibold mb-1 flex items-center gap-1.5">
                      <Compass className="w-3.5 h-3.5" />
                      <span>Missing Information & Unanswered Criteria</span>
                    </div>
                    <p className="text-xs text-slate-300 leading-relaxed">
                      {selectedAssessment.missing_information}
                    </p>
                  </div>
                )}

                <div className="pt-3 border-t border-dark-800">
                  <div className="text-[11px] font-mono text-cyan-400 uppercase font-semibold mb-1 flex items-center gap-1.5">
                    <Info className="w-3.5 h-3.5" />
                    <span>Recommended Next Evidence to Obtain</span>
                  </div>
                  <p className="text-xs text-slate-300 leading-relaxed">
                    {selectedAssessment.recommended_action}
                  </p>
                </div>

                {/* Audit Trail */}
                <div className="pt-3 border-t border-dark-800 flex flex-wrap items-center justify-between text-[10px] font-mono text-slate-500">
                  <span>Engine: {selectedAssessment.analysis_method}</span>
                  <span>Confidence: {Math.round(selectedAssessment.confidence * 100)}%</span>
                  <span>Mode: {selectedAssessment.processing_mode.toUpperCase()}</span>
                </div>
              </div>

              {/* Actionable Evidence Gaps */}
              {selectedAssessment.gaps.length > 0 && (
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-slate-200 uppercase font-mono flex items-center gap-1.5">
                      <Compass className="w-4 h-4 text-indigo-400" />
                      <span>Actionable Evidence Gaps ({selectedAssessment.gaps.length})</span>
                    </span>
                    <span className="text-[10px] text-slate-500">Actionable omissions</span>
                  </div>

                  <div className="space-y-2.5">
                    {selectedAssessment.gaps.map((gap) => (
                      <div
                        key={gap.id}
                        className="p-3 bg-dark-950/70 border border-indigo-500/20 rounded-xl space-y-2"
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-xs font-semibold text-slate-200">
                            {gap.gap_description}
                          </span>
                          {getPriorityBadge(gap.priority)}
                        </div>

                        <div className="text-xs text-slate-400 leading-relaxed">
                          <span className="text-slate-500 font-mono text-[10px] uppercase block mb-0.5">
                            Why It Matters:
                          </span>
                          {gap.why_it_matters}
                        </div>

                        <div className="p-2 bg-dark-900 rounded-lg border border-dark-800 text-[11px] text-cyan-300">
                          <span className="text-slate-500 font-mono text-[10px] uppercase block mb-0.5">
                            Evidence Needed:
                          </span>
                          {gap.evidence_needed}
                        </div>

                        {gap.suggested_source_type && (
                          <div className="text-[10px] font-mono text-indigo-300 flex items-center gap-1">
                            <span className="text-slate-500">Suggested Target:</span>
                            <span>{gap.suggested_source_type}</span>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Supporting Claims & Passages */}
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-slate-200 uppercase font-mono flex items-center gap-1.5">
                    <FileText className="w-4 h-4 text-cyan-400" />
                    <span>Supporting Evidence Claims ({selectedAssessment.supporting_claims.length})</span>
                  </span>
                  <span className="text-[10px] text-slate-500">Ground-truth citations</span>
                </div>

                {selectedAssessment.supporting_claims.length === 0 ? (
                  <div className="p-4 bg-dark-950/40 border border-dark-800 rounded-xl text-xs text-slate-500 text-center italic">
                    Zero extracted claims currently substantiate this requirement.
                  </div>
                ) : (
                  <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
                    {selectedAssessment.supporting_claims.map((claim) => (
                      <div
                        key={claim.claim_id}
                        className="p-3 bg-dark-950/80 border border-dark-800 rounded-xl space-y-2"
                      >
                        <div className="flex items-center justify-between text-xs">
                          <span className="text-[10px] font-mono text-cyan-400 flex items-center gap-1 truncate max-w-[200px]">
                            <span className="w-1.5 h-1.5 rounded-full bg-cyan-400" />
                            {claim.source_title || "Primary Source"}
                          </span>
                          <span className="text-[10px] font-mono text-slate-500">
                            {claim.relevance.replace("_", " ")}
                          </span>
                        </div>

                        <p className="text-xs text-slate-200 font-medium">
                          "{claim.claim_text}"
                        </p>

                        {claim.passage_text && (
                          <p className="text-[11px] text-slate-400 italic bg-dark-900/60 p-2 rounded-lg border border-dark-800">
                            "{claim.passage_text}"
                          </p>
                        )}

                        <div className="flex items-center justify-between text-[10px] font-mono text-slate-500 pt-1 border-t border-dark-800/80">
                          {claim.page_number && <span>Page {claim.page_number}</span>}
                          {claim.sha256_hash && (
                            <span title={claim.sha256_hash}>
                              SHA: {claim.sha256_hash.slice(0, 8)}...
                            </span>
                          )}
                          {claim.source_url && (
                            <a
                              href={claim.source_url}
                              target="_blank"
                              rel="noreferrer"
                              className="text-cyan-400 hover:text-cyan-300 flex items-center gap-0.5 ml-auto"
                            >
                              <span>Source</span>
                              <ExternalLink className="w-2.5 h-2.5" />
                            </a>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Related Conflicts from Conflict Engine */}
              {selectedAssessment.related_conflicts.length > 0 && (
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-rose-400 uppercase font-mono flex items-center gap-1.5">
                      <ShieldAlert className="w-4 h-4 text-rose-400" />
                      <span>Contested Evidence Conflicts ({selectedAssessment.related_conflicts.length})</span>
                    </span>
                    <button
                      onClick={() => navigate(`/conflict-intelligence?inv=${selectedInvId}`)}
                      className="text-[11px] text-rose-400 hover:text-rose-300 font-mono flex items-center gap-1"
                    >
                      <span>Open Conflict Explorer</span>
                      <ArrowRight className="w-3 h-3" />
                    </button>
                  </div>

                  <div className="space-y-2">
                    {selectedAssessment.related_conflicts.map((conf) => (
                      <div
                        key={conf.conflict_id}
                        className="p-3 bg-rose-500/10 border border-rose-500/20 rounded-xl space-y-1.5 text-xs"
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-mono text-[10px] text-rose-400 font-bold">
                            {conf.conflict_type.replace(/_/g, " ")}
                          </span>
                          <span className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-dark-900 border border-dark-800 text-slate-300">
                            {conf.resolution_status.toUpperCase()}
                          </span>
                        </div>
                        <p className="text-slate-300 text-xs">
                          {conf.explanation}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Navigation Action Footer */}
              <div className="pt-4 border-t border-dark-800 flex items-center justify-between">
                <Button
                  onClick={() => navigate(`/evidence-graph?inv=${selectedInvId}`)}
                  className="bg-dark-800 hover:bg-dark-750 text-slate-300 text-xs px-3 py-1.5 flex items-center gap-1.5"
                >
                  <Network className="w-3.5 h-3.5 text-cyan-400" />
                  <span>View in Evidence Graph</span>
                </Button>

                {selectedAssessment.related_conflicts.length > 0 && (
                  <Button
                    onClick={() => navigate(`/conflict-intelligence?inv=${selectedInvId}`)}
                    className="bg-rose-950/40 hover:bg-rose-900/50 text-rose-300 border border-rose-500/30 text-xs px-3 py-1.5 flex items-center gap-1.5"
                  >
                    <ShieldAlert className="w-3.5 h-3.5 text-rose-400" />
                    <span>Inspect Conflicts</span>
                  </Button>
                )}
              </div>
            </div>
          ) : (
            <div className="p-12 text-center bg-dark-900/30 border border-dark-700/60 rounded-2xl">
              <Compass className="w-10 h-10 text-slate-600 mx-auto mb-3" />
              <h3 className="text-sm font-semibold text-slate-300">No Requirement Selected</h3>
              <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
                Select a requirement from the feed to examine sufficiency findings, evidence gaps, and supporting ground-truth citations.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
