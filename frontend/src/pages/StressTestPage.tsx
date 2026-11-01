import { useState, useEffect, useMemo } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import {
  listInvestigations,
  getInvestigationStressTests,
  generateInvestigationStressScenarios,
  evaluateInvestigationStressScenario,
  Investigation,
  StressScenario,
  StressTestingBaseline,
  StressTestingSummary,
  DecisionOutcome,
  StressScenarioCategory,
  StressSeverity,
} from "@/lib/api";
import {
  ShieldAlert,
  Sparkles,
  RefreshCw,
  Search,
  Layers,
  AlertTriangle,
  CheckCircle2,
  HelpCircle,
  FileCheck2,
  Network,
  X,
  Flame,
  ArrowRight,
  Info,
  GitCompare,
  Zap,
  Play,
} from "lucide-react";
import { Button } from "@/components/ui/Button";

// Category display metadata
const CATEGORY_META: Record<
  StressScenarioCategory,
  { label: string; bg: string; text: string; border: string }
> = {
  ASSUMPTION_FAILURE: {
    label: "Assumption Failure",
    bg: "bg-amber-500/10",
    text: "text-amber-400",
    border: "border-amber-500/30",
  },
  RISK_MATERIALIZATION: {
    label: "Risk Materialization",
    bg: "bg-rose-500/10",
    text: "text-rose-400",
    border: "border-rose-500/30",
  },
  EVIDENCE_WEAKENING: {
    label: "Evidence Weakening",
    bg: "bg-orange-500/10",
    text: "text-orange-400",
    border: "border-orange-500/30",
  },
  CONFLICT_RESOLUTION: {
    label: "Conflict Resolution",
    bg: "bg-purple-500/10",
    text: "text-purple-400",
    border: "border-purple-500/30",
  },
  EXTERNAL_CONDITION_CHANGE: {
    label: "External Shift",
    bg: "bg-blue-500/10",
    text: "text-blue-400",
    border: "border-blue-500/30",
  },
  MISSING_EVIDENCE: {
    label: "Missing Evidence Discovery",
    bg: "bg-cyan-500/10",
    text: "text-cyan-400",
    border: "border-cyan-500/30",
  },
};

// Severity badge metadata
const SEVERITY_META: Record<StressSeverity, { bg: string; text: string; border: string }> = {
  CRITICAL: { bg: "bg-rose-500/15", text: "text-rose-400", border: "border-rose-500/30" },
  HIGH: { bg: "bg-orange-500/15", text: "text-orange-400", border: "border-orange-500/30" },
  MEDIUM: { bg: "bg-amber-500/15", text: "text-amber-400", border: "border-amber-500/30" },
  LOW: { bg: "bg-slate-500/15", text: "text-slate-400", border: "border-slate-500/30" },
};

// Outcome badge metadata
const OUTCOME_META: Record<
  DecisionOutcome,
  { label: string; bg: string; text: string; border: string }
> = {
  ROBUST: {
    label: "ROBUST",
    bg: "bg-emerald-500/15",
    text: "text-emerald-400",
    border: "border-emerald-500/30",
  },
  CONDITIONALLY_ROBUST: {
    label: "CONDITIONALLY ROBUST",
    bg: "bg-cyan-500/15",
    text: "text-cyan-400",
    border: "border-cyan-500/30",
  },
  VULNERABLE: {
    label: "VULNERABLE",
    bg: "bg-amber-500/15",
    text: "text-amber-400",
    border: "border-amber-500/30",
  },
  HIGHLY_VULNERABLE: {
    label: "HIGHLY VULNERABLE",
    bg: "bg-rose-500/15",
    text: "text-rose-400",
    border: "border-rose-500/30",
  },
  INDETERMINATE: {
    label: "INDETERMINATE",
    bg: "bg-slate-500/15",
    text: "text-slate-400",
    border: "border-slate-500/30",
  },
  NOT_EVALUABLE: {
    label: "NOT EVALUABLE",
    bg: "bg-zinc-500/15",
    text: "text-zinc-400",
    border: "border-zinc-500/30",
  },
};

export function StressTestPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();

  // Navigation & Data State
  const [investigations, setInvestigations] = useState<Investigation[]>([]);
  const [selectedInvId, setSelectedInvId] = useState<string | null>(null);
  const [baseline, setBaseline] = useState<StressTestingBaseline | null>(null);
  const [summary, setSummary] = useState<StressTestingSummary | null>(null);
  const [scenarios, setScenarios] = useState<StressScenario[]>([]);
  const [processingMode, setProcessingMode] = useState<"gemini" | "fallback" | "pending">("pending");
  const [lastGeneratedAt, setLastGeneratedAt] = useState<string | null>(null);

  // Inspector & Selection State
  const [selectedScenarioId, setSelectedScenarioId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"explorer" | "matrix">("explorer");

  // Loading & Action State
  const [isLoading, setIsLoading] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [evaluatingScenarioId, setEvaluatingScenarioId] = useState<string | null>(null);
  const [isEvaluatingAll, setIsEvaluatingAll] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Filters
  const [searchQuery, setSearchQuery] = useState("");
  const [categoryFilter, setCategoryFilter] = useState<string>("ALL");
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

  // 2. Fetch Stress Tests when investigation changes
  useEffect(() => {
    if (!selectedInvId) return;

    let isMounted = true;
    async function fetchStressTests() {
      setIsLoading(true);
      setErrorMessage(null);
      try {
        const data = await getInvestigationStressTests(selectedInvId!);
        if (!isMounted) return;
        setBaseline(data.baseline);
        setSummary(data.summary);
        setScenarios(data.scenarios);
        setProcessingMode(data.processing_mode);
        setLastGeneratedAt(data.last_generated_at || null);

        if (data.scenarios.length > 0) {
          setSelectedScenarioId((prev) => (prev && data.scenarios.some((s) => s.id === prev) ? prev : data.scenarios[0].id));
        } else {
          setSelectedScenarioId(null);
        }
      } catch (err: any) {
        if (isMounted) setErrorMessage(err.message || "Failed to load stress tests");
      } finally {
        if (isMounted) setIsLoading(false);
      }
    }

    fetchStressTests();
    return () => {
      isMounted = false;
    };
  }, [selectedInvId]);

  // Selected scenario item
  const selectedScenario = useMemo(() => {
    return scenarios.find((s) => s.id === selectedScenarioId) || null;
  }, [scenarios, selectedScenarioId]);

  // Filtered Scenarios
  const filteredScenarios = useMemo(() => {
    return scenarios.filter((s) => {
      if (categoryFilter !== "ALL" && s.category !== categoryFilter) return false;
      if (severityFilter !== "ALL" && s.severity !== severityFilter) return false;
      if (statusFilter !== "ALL" && s.evaluation_status !== statusFilter) return false;

      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const matchesTitle = s.title.toLowerCase().includes(q);
        const matchesDesc = s.description.toLowerCase().includes(q);
        const matchesTrigger = s.trigger_condition.toLowerCase().includes(q);
        const matchesReqs = s.affected_requirement_titles.some((t) => t.toLowerCase().includes(q));
        if (!matchesTitle && !matchesDesc && !matchesTrigger && !matchesReqs) return false;
      }
      return true;
    });
  }, [scenarios, categoryFilter, severityFilter, statusFilter, searchQuery]);

  // Evaluated scenarios for comparative matrix
  const evaluatedScenarios = useMemo(() => {
    return scenarios.filter((s) => s.evaluation_status === "evaluated" && s.evaluation);
  }, [scenarios]);

  // All distinct requirements from evaluated scenarios
  const allMatrixRequirements = useMemo(() => {
    const map = new Map<string, string>();
    evaluatedScenarios.forEach((s) => {
      s.evaluation?.requirement_evaluations.forEach((re) => {
        if (!map.has(re.requirement_id)) {
          map.set(re.requirement_id, re.requirement_title);
        }
      });
    });
    return Array.from(map.entries()).map(([id, title]) => ({ id, title }));
  }, [evaluatedScenarios]);

  // Generate Scenarios
  const handleGenerateScenarios = async () => {
    if (!selectedInvId || isGenerating) return;
    setIsGenerating(true);
    setErrorMessage(null);

    try {
      const result = await generateInvestigationStressScenarios(selectedInvId);
      setBaseline(result.baseline);
      setSummary(result.summary);
      setScenarios(result.scenarios);
      setProcessingMode(result.processing_mode);
      setLastGeneratedAt(result.last_generated_at || null);

      if (result.scenarios.length > 0) {
        setSelectedScenarioId(result.scenarios[0].id);
      }
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to generate stress-test scenarios");
    } finally {
      setIsGenerating(false);
    }
  };

  // Evaluate Single Scenario
  const handleEvaluateScenario = async (scenarioId: string) => {
    if (!selectedInvId || evaluatingScenarioId) return;
    setEvaluatingScenarioId(scenarioId);
    setErrorMessage(null);

    try {
      const updated = await evaluateInvestigationStressScenario(selectedInvId, scenarioId);
      setScenarios((prev) => prev.map((s) => (s.id === scenarioId ? updated : s)));

      // Refresh full summary and baseline
      const fresh = await getInvestigationStressTests(selectedInvId);
      setBaseline(fresh.baseline);
      setSummary(fresh.summary);
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to evaluate stress scenario");
    } finally {
      setEvaluatingScenarioId(null);
    }
  };

  // Evaluate All Unevaluated Scenarios
  const handleEvaluateAll = async () => {
    if (!selectedInvId || isEvaluatingAll) return;
    const unevaluated = scenarios.filter((s) => s.evaluation_status === "unevaluated");
    if (unevaluated.length === 0) return;

    setIsEvaluatingAll(true);
    setErrorMessage(null);

    try {
      for (const s of unevaluated) {
        setEvaluatingScenarioId(s.id);
        const updated = await evaluateInvestigationStressScenario(selectedInvId, s.id);
        setScenarios((prev) => prev.map((item) => (item.id === s.id ? updated : item)));
      }
      const fresh = await getInvestigationStressTests(selectedInvId);
      setBaseline(fresh.baseline);
      setSummary(fresh.summary);
    } catch (err: any) {
      setErrorMessage(err.message || "Evaluation sequence encountered an error");
    } finally {
      setIsEvaluatingAll(false);
      setEvaluatingScenarioId(null);
    }
  };

  return (
    <div className="flex flex-col gap-6 max-w-7xl mx-auto p-4 md:p-6 w-full">
      {/* 1. Header & Investigation Switcher */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-dark-700/60">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-400">
              <ShieldAlert className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-white flex items-center gap-2.5">
                Test Your Decision
                {lastGeneratedAt && (
                  <span className="text-[11px] font-mono text-slate-500">
                    Updated {new Date(lastGeneratedAt).toLocaleTimeString()}
                  </span>
                )}
              </h1>
              <p className="text-xs text-slate-400 mt-0.5">
                Test how your decision holds up if key assumptions fail or evidence changes.
              </p>
            </div>
          </div>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-2.5 flex-wrap">
          {/* Investigation Switcher */}
          <select
            value={selectedInvId || ""}
            onChange={(e) => {
              setSelectedInvId(e.target.value);
              setSearchParams({ inv: e.target.value });
            }}
            className="bg-slate-900 border border-slate-700 text-slate-100 text-xs rounded-lg px-3 py-2 font-medium focus:outline-none focus:border-rose-500 focus:ring-1 focus:ring-rose-500 cursor-pointer shadow-sm"
          >
            {investigations.map((inv) => (
              <option key={inv.id} value={inv.id} className="bg-slate-900 text-slate-100 py-1.5">
                {inv.research_question ? inv.research_question.slice(0, 48) + "..." : inv.id.slice(0, 8)}
              </option>
            ))}
          </select>

          {/* Processing Mode Badge */}
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

          {/* Generate Scenarios Button */}
          <Button
            onClick={handleGenerateScenarios}
            disabled={!selectedInvId || isGenerating || isLoading}
            className="bg-gradient-to-r from-rose-600 to-amber-600 hover:from-rose-500 hover:to-amber-500 text-white font-medium text-xs px-3.5 py-2 flex items-center gap-2 shadow-lg shadow-rose-950/20"
          >
            {isGenerating ? (
              <>
                <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                <span>Generating Scenarios...</span>
              </>
            ) : (
              <>
                <Sparkles className="w-3.5 h-3.5" />
                <span>Generate Scenarios</span>
              </>
            )}
          </Button>

          {/* Evaluate All Button */}
          {scenarios.some((s) => s.evaluation_status === "unevaluated") && (
            <Button
              onClick={handleEvaluateAll}
              disabled={!selectedInvId || isEvaluatingAll || isGenerating}
              variant="outline"
              className="border-rose-500/30 text-rose-300 hover:bg-rose-500/10 text-xs px-3 py-2 flex items-center gap-1.5"
            >
              {isEvaluatingAll ? (
                <>
                  <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                  <span>Testing Scenarios...</span>
                </>
              ) : (
                <>
                  <Play className="w-3.5 h-3.5" />
                  <span>Run Stress Tests</span>
                </>
              )}
            </Button>
          )}
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
        {/* Baseline Outcome */}
        <div className="p-3.5 bg-dark-900/70 border border-dark-700/60 rounded-xl relative overflow-hidden">
          <div className="flex items-center justify-between text-slate-400 text-xs mb-1">
            <span>Baseline Outcome</span>
            <ShieldAlert className="w-4 h-4 text-slate-400" />
          </div>
          <div className="mt-1">
            {baseline ? (
              <span
                className={`text-xs px-2 py-1 rounded font-mono font-bold border inline-block ${
                  OUTCOME_META[baseline.baseline_outcome]?.bg || "bg-dark-800"
                } ${OUTCOME_META[baseline.baseline_outcome]?.text || "text-slate-300"} ${
                  OUTCOME_META[baseline.baseline_outcome]?.border || "border-dark-700"
                }`}
              >
                {OUTCOME_META[baseline.baseline_outcome]?.label || baseline.baseline_outcome}
              </span>
            ) : (
              <span className="text-sm font-mono text-slate-500">PENDING</span>
            )}
          </div>
          <div className="text-[11px] text-slate-500 mt-2">Current status before stress tests</div>
        </div>

        {/* Total Scenarios */}
        <div className="p-3.5 bg-dark-900/70 border border-dark-700/60 rounded-xl relative overflow-hidden">
          <div className="flex items-center justify-between text-slate-400 text-xs mb-1">
            <span>Total Scenarios</span>
            <Layers className="w-4 h-4 text-slate-400" />
          </div>
          <div className="text-2xl font-bold font-mono text-white">
            {summary?.total_scenarios ?? scenarios.length}
          </div>
          <div className="text-[11px] text-slate-500 mt-1">Across 6 risk categories</div>
        </div>

        {/* Evaluated Scenarios */}
        <div className="p-3.5 bg-dark-900/70 border border-dark-700/60 rounded-xl relative overflow-hidden">
          <div className="flex items-center justify-between text-slate-400 text-xs mb-1">
            <span>Evaluated</span>
            <CheckCircle2 className="w-4 h-4 text-slate-400" />
          </div>
          <div className="text-2xl font-bold font-mono text-cyan-400">
            {summary?.evaluated_scenarios ?? 0}
            <span className="text-xs text-slate-500 font-normal ml-1">
              / {summary?.total_scenarios ?? scenarios.length}
            </span>
          </div>
          <div className="text-[11px] text-slate-500 mt-1">Simulations run</div>
        </div>

        {/* Vulnerable Scenarios */}
        <div className="p-3.5 bg-dark-900/70 border border-rose-500/20 rounded-xl relative overflow-hidden">
          <div className="flex items-center justify-between text-rose-400 text-xs mb-1">
            <span>Vulnerable</span>
            <Flame className="w-4 h-4 text-rose-400" />
          </div>
          <div className="text-2xl font-bold font-mono text-rose-400">
            {summary?.vulnerable_scenarios ?? 0}
          </div>
          <div className="text-[11px] text-slate-500 mt-1">Down-revised or failed</div>
        </div>

        {/* Critical & High Severity */}
        <div className="p-3.5 bg-dark-900/70 border border-orange-500/20 rounded-xl relative overflow-hidden">
          <div className="flex items-center justify-between text-orange-400 text-xs mb-1">
            <span>High Severity</span>
            <AlertTriangle className="w-4 h-4 text-orange-400" />
          </div>
          <div className="text-2xl font-bold font-mono text-orange-400">
            {(summary?.critical_severity_count ?? 0) + (summary?.high_severity_count ?? 0)}
          </div>
          <div className="text-[11px] text-slate-500 mt-1">Critical & High vectors</div>
        </div>

        {/* Indeterminate Scenarios */}
        <div className="p-3.5 bg-dark-900/70 border border-slate-700/60 rounded-xl relative overflow-hidden">
          <div className="flex items-center justify-between text-slate-400 text-xs mb-1">
            <span>Indeterminate</span>
            <HelpCircle className="w-4 h-4 text-slate-400" />
          </div>
          <div className="text-2xl font-bold font-mono text-slate-300">
            {summary?.indeterminate_scenarios ?? 0}
          </div>
          <div className="text-[11px] text-slate-500 mt-1">Evidentiary ambiguity</div>
        </div>
      </div>

      {/* 3. Baseline Grounding Callout */}
      {baseline && (
        <div className="p-3.5 rounded-xl bg-dark-900/50 border border-dark-700/60 text-xs flex flex-col md:flex-row items-start md:items-center justify-between gap-3">
          <div className="flex items-start gap-2.5">
            <Info className="w-4 h-4 text-cyan-400 shrink-0 mt-0.5" />
            <div>
              <span className="text-slate-300 font-medium">Grounding Baseline: </span>
              <span className="text-slate-400">{baseline.baseline_rationale}</span>
            </div>
          </div>
          <div className="flex items-center gap-3 shrink-0 text-slate-400">
            <span>
              Requirements: <strong className="text-white font-mono">{baseline.total_requirements}</strong>
            </span>
            <span>•</span>
            <span>
              Conflicts: <strong className="text-amber-400 font-mono">{baseline.active_conflicts}</strong>
            </span>
            <span>•</span>
            <span>
              Gaps: <strong className="text-rose-400 font-mono">{baseline.unresolved_gaps}</strong>
            </span>
          </div>
        </div>
      )}

      {/* 4. Tab Navigation */}
      <div className="flex items-center gap-2 border-b border-dark-700/60 pb-2">
        <button
          onClick={() => setActiveTab("explorer")}
          className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
            activeTab === "explorer"
              ? "bg-rose-500/15 border border-rose-500/30 text-rose-300"
              : "text-slate-400 hover:text-white hover:bg-dark-800"
          }`}
        >
          <ShieldAlert className="w-3.5 h-3.5" />
          <span>Scenario Explorer ({filteredScenarios.length})</span>
        </button>

        <button
          onClick={() => setActiveTab("matrix")}
          className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
            activeTab === "matrix"
              ? "bg-rose-500/15 border border-rose-500/30 text-rose-300"
              : "text-slate-400 hover:text-white hover:bg-dark-800"
          }`}
        >
          <GitCompare className="w-3.5 h-3.5" />
          <span>Comparative Stress Matrix ({evaluatedScenarios.length} Evaluated)</span>
        </button>
      </div>

      {/* TAB 1: SCENARIO EXPLORER */}
      {activeTab === "explorer" && (
        <div className="flex flex-col gap-4">
          {/* Filter Toolbar */}
          <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-3 p-3 bg-dark-900/50 border border-dark-700/50 rounded-xl">
            {/* Search Input */}
            <div className="relative flex-1">
              <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
              <input
                type="text"
                placeholder="Search scenarios by title, trigger event, or requirement..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full bg-dark-900 border border-dark-700 text-slate-200 text-xs rounded-lg pl-9 pr-3 py-2 placeholder-slate-500 focus:outline-none focus:border-rose-500"
              />
              {searchQuery && (
                <button
                  onClick={() => setSearchQuery("")}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-200"
                >
                  <X className="w-3 h-3" />
                </button>
              )}
            </div>

            {/* Filter Dropdowns */}
            <div className="flex items-center gap-2 flex-wrap">
              {/* Category Filter */}
              <select
                value={categoryFilter}
                onChange={(e) => setCategoryFilter(e.target.value)}
                className="bg-slate-900 border border-slate-700 text-slate-100 text-xs rounded-lg px-2.5 py-2 font-medium focus:outline-none focus:border-rose-500 cursor-pointer"
              >
                <option value="ALL" className="bg-slate-900 text-slate-100">All Categories</option>
                <option value="ASSUMPTION_FAILURE" className="bg-slate-900 text-slate-100">Assumption Failure</option>
                <option value="RISK_MATERIALIZATION" className="bg-slate-900 text-slate-100">Risk Materialization</option>
                <option value="EVIDENCE_WEAKENING" className="bg-slate-900 text-slate-100">Evidence Weakening</option>
                <option value="CONFLICT_RESOLUTION" className="bg-slate-900 text-slate-100">Conflict Resolution</option>
                <option value="EXTERNAL_CONDITION_CHANGE" className="bg-slate-900 text-slate-100">External Shift</option>
                <option value="MISSING_EVIDENCE" className="bg-slate-900 text-slate-100">Missing Evidence</option>
              </select>

              {/* Severity Filter */}
              <select
                value={severityFilter}
                onChange={(e) => setSeverityFilter(e.target.value)}
                className="bg-slate-900 border border-slate-700 text-slate-100 text-xs rounded-lg px-2.5 py-2 font-medium focus:outline-none focus:border-rose-500 cursor-pointer"
              >
                <option value="ALL" className="bg-slate-900 text-slate-100">All Severities</option>
                <option value="CRITICAL" className="bg-slate-900 text-slate-100">Critical</option>
                <option value="HIGH" className="bg-slate-900 text-slate-100">High</option>
                <option value="MEDIUM" className="bg-slate-900 text-slate-100">Medium</option>
                <option value="LOW" className="bg-slate-900 text-slate-100">Low</option>
              </select>

              {/* Status Filter */}
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="bg-slate-900 border border-slate-700 text-slate-100 text-xs rounded-lg px-2.5 py-2 font-medium focus:outline-none focus:border-rose-500 cursor-pointer"
              >
                <option value="ALL" className="bg-slate-900 text-slate-100">All Statuses</option>
                <option value="evaluated" className="bg-slate-900 text-slate-100">Evaluated</option>
                <option value="unevaluated" className="bg-slate-900 text-slate-100">Unevaluated</option>
              </select>

              {/* Clear Filters */}
              {(categoryFilter !== "ALL" || severityFilter !== "ALL" || statusFilter !== "ALL" || searchQuery) && (
                <button
                  onClick={() => {
                    setCategoryFilter("ALL");
                    setSeverityFilter("ALL");
                    setStatusFilter("ALL");
                    setSearchQuery("");
                  }}
                  className="text-xs text-rose-400 hover:text-rose-300 px-2 py-1 rounded"
                >
                  Reset
                </button>
              )}
            </div>
          </div>

          {/* Main Explorer Split Feed */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
            {/* Left Column: Scenario Cards (5 cols) */}
            <div className="lg:col-span-5 flex flex-col gap-2.5 max-h-[750px] overflow-y-auto pr-1">
              {filteredScenarios.length === 0 ? (
                <div className="p-8 text-center bg-dark-900/40 border border-dark-700/40 rounded-xl text-slate-500 text-xs flex flex-col items-center gap-2">
                  <ShieldAlert className="w-8 h-8 text-slate-600" />
                  <span>No stress-test scenarios match current filters.</span>
                  {scenarios.length === 0 && (
                    <Button
                      onClick={handleGenerateScenarios}
                      disabled={isGenerating}
                      className="mt-2 text-xs bg-rose-600 hover:bg-rose-500 text-white"
                    >
                      Generate Initial Scenarios
                    </Button>
                  )}
                </div>
              ) : (
                filteredScenarios.map((sc) => {
                  const isSelected = sc.id === selectedScenarioId;
                  const cat = CATEGORY_META[sc.category] || {
                    label: sc.category,
                    bg: "bg-slate-500/10",
                    text: "text-slate-400",
                    border: "border-slate-500/30",
                  };
                  const sev = SEVERITY_META[sc.severity] || SEVERITY_META.MEDIUM;
                  const isEvaluated = sc.evaluation_status === "evaluated" && sc.evaluation;

                  return (
                    <div
                      key={sc.id}
                      onClick={() => setSelectedScenarioId(sc.id)}
                      className={`p-3.5 rounded-xl border transition-all cursor-pointer text-left ${
                        isSelected
                          ? "bg-dark-800/90 border-rose-500/50 shadow-md shadow-rose-950/20 ring-1 ring-rose-500/30"
                          : "bg-dark-900/60 border-dark-700/50 hover:bg-dark-800/50 hover:border-dark-600"
                      }`}
                    >
                      {/* Top Badges Row */}
                      <div className="flex items-center justify-between gap-2 mb-2">
                        <span className={`text-[10px] px-2 py-0.5 rounded font-mono border ${cat.bg} ${cat.text} ${cat.border}`}>
                          {cat.label}
                        </span>
                        <div className="flex items-center gap-1.5">
                          <span className={`text-[10px] px-1.5 py-0.5 rounded font-mono border ${sev.bg} ${sev.text} ${sev.border}`}>
                            {sc.severity}
                          </span>
                          {isEvaluated ? (
                            <span
                              className={`text-[10px] px-1.5 py-0.5 rounded font-mono border ${
                                OUTCOME_META[sc.evaluation!.scenario_overall_outcome]?.bg || "bg-dark-800"
                              } ${OUTCOME_META[sc.evaluation!.scenario_overall_outcome]?.text || "text-slate-300"} ${
                                OUTCOME_META[sc.evaluation!.scenario_overall_outcome]?.border || "border-dark-700"
                              }`}
                            >
                              {sc.evaluation!.scenario_overall_outcome}
                            </span>
                          ) : (
                            <span className="text-[10px] px-1.5 py-0.5 rounded font-mono bg-dark-800 border border-dark-700 text-slate-500">
                              Unevaluated
                            </span>
                          )}
                        </div>
                      </div>

                      {/* Title */}
                      <h4 className="text-xs font-semibold text-white line-clamp-1 mb-1">
                        {sc.title}
                      </h4>

                      {/* Trigger Condition Snippet */}
                      <p className="text-[11px] text-slate-400 line-clamp-2 mb-2">
                        {sc.trigger_condition}
                      </p>

                      {/* Affected Requirements & Meta */}
                      <div className="flex items-center justify-between text-[10px] text-slate-500 pt-2 border-t border-dark-800/80">
                        <span className="truncate max-w-[200px]">
                          Affects: {sc.affected_requirement_titles.length > 0 ? sc.affected_requirement_titles[0] : "General baseline"}
                          {sc.affected_requirement_titles.length > 1 && ` +${sc.affected_requirement_titles.length - 1}`}
                        </span>
                        <span className="font-mono text-slate-600 shrink-0">
                          {sc.processing_mode === "gemini" ? "Gemini" : "Fallback"}
                        </span>
                      </div>
                    </div>
                  );
                })
              )}
            </div>

            {/* Right Column: Scenario Inspector (7 cols) */}
            <div className="lg:col-span-7 bg-dark-900/70 border border-dark-700/60 rounded-xl p-5 sticky top-6">
              {selectedScenario ? (
                <div className="flex flex-col gap-5">
                  {/* Inspector Header */}
                  <div className="flex flex-col gap-2 pb-4 border-b border-dark-700/60">
                    <div className="flex items-center justify-between gap-2 flex-wrap">
                      <div className="flex items-center gap-2">
                        <span
                          className={`text-xs px-2.5 py-0.5 rounded font-mono border ${
                            CATEGORY_META[selectedScenario.category]?.bg || "bg-dark-800"
                          } ${CATEGORY_META[selectedScenario.category]?.text || "text-slate-300"} ${
                            CATEGORY_META[selectedScenario.category]?.border || "border-dark-700"
                          }`}
                        >
                          {CATEGORY_META[selectedScenario.category]?.label || selectedScenario.category}
                        </span>
                        <span
                          className={`text-xs px-2 py-0.5 rounded font-mono border ${
                            SEVERITY_META[selectedScenario.severity]?.bg || "bg-dark-800"
                          } ${SEVERITY_META[selectedScenario.severity]?.text || "text-slate-300"} ${
                            SEVERITY_META[selectedScenario.severity]?.border || "border-dark-700"
                          }`}
                        >
                          Severity: {selectedScenario.severity}
                        </span>
                      </div>

                      {/* Evaluation Trigger Button */}
                      <Button
                        onClick={() => handleEvaluateScenario(selectedScenario.id)}
                        disabled={evaluatingScenarioId === selectedScenario.id}
                        className={`text-xs px-3 py-1.5 flex items-center gap-1.5 ${
                          selectedScenario.evaluation_status === "evaluated"
                            ? "bg-dark-800 hover:bg-dark-700 text-slate-200 border border-dark-600"
                            : "bg-rose-600 hover:bg-rose-500 text-white"
                        }`}
                      >
                        {evaluatingScenarioId === selectedScenario.id ? (
                          <>
                            <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                            <span>Evaluating...</span>
                          </>
                        ) : selectedScenario.evaluation_status === "evaluated" ? (
                          <>
                            <RefreshCw className="w-3.5 h-3.5" />
                            <span>Re-Evaluate</span>
                          </>
                        ) : (
                          <>
                            <Zap className="w-3.5 h-3.5" />
                            <span>Evaluate Scenario</span>
                          </>
                        )}
                      </Button>
                    </div>

                    <h2 className="text-base font-bold text-white mt-1">
                      {selectedScenario.title}
                    </h2>
                    <p className="text-xs text-slate-300 leading-relaxed">
                      {selectedScenario.description}
                    </p>
                  </div>

                  {/* Trigger Condition Box */}
                  <div className="p-3 bg-dark-800/80 border border-dark-700/60 rounded-lg">
                    <div className="text-[11px] font-semibold text-rose-400 uppercase tracking-wider mb-1 flex items-center gap-1.5">
                      <Zap className="w-3 h-3" />
                      <span>Trigger Condition</span>
                    </div>
                    <p className="text-xs text-slate-200 font-mono">
                      {selectedScenario.trigger_condition}
                    </p>
                  </div>

                  {/* Evaluated Outcome Findings */}
                  {selectedScenario.evaluation ? (
                    <div className="flex flex-col gap-4">
                      {/* Outcome Shift Banner */}
                      <div className="p-4 rounded-xl bg-dark-800/90 border border-dark-700 flex flex-col gap-2">
                        <div className="flex items-center justify-between text-xs">
                          <span className="text-slate-400 font-medium">Outcome Shift:</span>
                          <span className="font-mono text-[11px] px-2 py-0.5 rounded bg-dark-900 border border-dark-700 text-amber-400">
                            {selectedScenario.evaluation.outcome_shift}
                          </span>
                        </div>

                        <div className="flex items-center gap-3 my-1">
                          <div className="flex-1 p-2.5 rounded-lg bg-dark-900/80 border border-dark-700/80 text-center">
                            <div className="text-[10px] text-slate-500 uppercase font-mono">Baseline</div>
                            <div
                              className={`text-xs font-mono font-bold mt-0.5 ${
                                OUTCOME_META[selectedScenario.evaluation.baseline_overall_outcome]?.text || "text-slate-200"
                              }`}
                            >
                              {selectedScenario.evaluation.baseline_overall_outcome}
                            </div>
                          </div>

                          <ArrowRight className="w-4 h-4 text-slate-500 shrink-0" />

                          <div className="flex-1 p-2.5 rounded-lg bg-dark-900/80 border border-rose-500/30 text-center">
                            <div className="text-[10px] text-rose-400 uppercase font-mono">Scenario Stressed</div>
                            <div
                              className={`text-xs font-mono font-bold mt-0.5 ${
                                OUTCOME_META[selectedScenario.evaluation.scenario_overall_outcome]?.text || "text-rose-400"
                              }`}
                            >
                              {selectedScenario.evaluation.scenario_overall_outcome}
                            </div>
                          </div>
                        </div>

                        <p className="text-xs text-slate-300 mt-1 leading-relaxed">
                          {selectedScenario.evaluation.impact_explanation}
                        </p>
                      </div>

                      {/* Requirement Shift Breakdown Table */}
                      <div>
                        <div className="text-xs font-semibold text-slate-200 mb-2 flex items-center justify-between">
                          <span>Requirement Coverage Shifts ({selectedScenario.evaluation.requirement_evaluations.length})</span>
                          <span className="text-[11px] text-slate-500 font-normal">Baseline vs Stressed</span>
                        </div>
                        <div className="border border-dark-700/80 rounded-lg overflow-hidden">
                          <table className="w-full text-left text-xs">
                            <thead className="bg-dark-800 text-slate-400 font-mono text-[11px]">
                              <tr>
                                <th className="p-2.5">Requirement</th>
                                <th className="p-2.5">Baseline</th>
                                <th className="p-2.5">Stressed</th>
                                <th className="p-2.5">Shift Reason</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-dark-800 bg-dark-900/50">
                              {selectedScenario.evaluation.requirement_evaluations.map((re) => {
                                const isDegraded = re.status_shift === "DEGRADED";
                                return (
                                  <tr key={re.requirement_id} className={isDegraded ? "bg-rose-500/5" : ""}>
                                    <td className="p-2.5 font-medium text-slate-200 max-w-[180px] truncate">
                                      {re.requirement_title}
                                    </td>
                                    <td className="p-2.5 font-mono text-[11px] text-slate-400">
                                      {re.baseline_status}
                                    </td>
                                    <td className="p-2.5 font-mono text-[11px]">
                                      <span
                                        className={`px-1.5 py-0.5 rounded ${
                                          isDegraded
                                            ? "bg-rose-500/20 text-rose-400 font-bold"
                                            : "text-slate-300"
                                        }`}
                                      >
                                        {re.scenario_status}
                                      </span>
                                    </td>
                                    <td className="p-2.5 text-[11px] text-slate-400">
                                      {re.degradation_reason || "Consistent with baseline"}
                                    </td>
                                  </tr>
                                );
                              })}
                            </tbody>
                          </table>
                        </div>
                      </div>

                      {/* Key Vulnerabilities & Mitigations (2 cols) */}
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                        <div className="p-3 bg-dark-800/60 border border-dark-700/60 rounded-lg">
                          <div className="font-semibold text-rose-400 mb-1.5 flex items-center gap-1.5">
                            <Flame className="w-3.5 h-3.5" />
                            <span>Key Vulnerabilities</span>
                          </div>
                          <ul className="list-disc list-inside space-y-1 text-slate-300 text-[11px]">
                            {selectedScenario.evaluation.key_vulnerabilities.map((v, idx) => (
                              <li key={idx} className="leading-snug">
                                {v}
                              </li>
                            ))}
                          </ul>
                        </div>

                        <div className="p-3 bg-dark-800/60 border border-dark-700/60 rounded-lg">
                          <div className="font-semibold text-emerald-400 mb-1.5 flex items-center gap-1.5">
                            <CheckCircle2 className="w-3.5 h-3.5" />
                            <span>Recommended Mitigations</span>
                          </div>
                          <ul className="list-disc list-inside space-y-1 text-slate-300 text-[11px]">
                            {selectedScenario.evaluation.recommended_actions.map((act, idx) => (
                              <li key={idx} className="leading-snug">
                                {act}
                              </li>
                            ))}
                          </ul>
                        </div>
                      </div>
                    </div>
                  ) : (
                    /* Unevaluated Scenario Spec */
                    <div className="flex flex-col gap-3.5 p-4 rounded-xl bg-dark-800/40 border border-dark-700/50">
                      <div>
                        <span className="text-xs font-semibold text-slate-300">Expected Decision Impact:</span>
                        <p className="text-xs text-slate-400 mt-0.5 leading-relaxed">
                          {selectedScenario.expected_impact}
                        </p>
                      </div>

                      {selectedScenario.challenged_assumptions.length > 0 && (
                        <div>
                          <span className="text-xs font-semibold text-amber-400">Challenged Assumptions:</span>
                          <ul className="list-disc list-inside text-xs text-slate-400 mt-1 space-y-0.5">
                            {selectedScenario.challenged_assumptions.map((ass, idx) => (
                              <li key={idx}>{ass}</li>
                            ))}
                          </ul>
                        </div>
                      )}

                      <div>
                        <span className="text-xs font-semibold text-cyan-400">Evidence Required to Close Gap / Refute:</span>
                        <p className="text-xs text-slate-400 mt-0.5 font-mono">
                          {selectedScenario.evidence_needed}
                        </p>
                      </div>

                      <div className="pt-2 border-t border-dark-700/40">
                        <Button
                          onClick={() => handleEvaluateScenario(selectedScenario.id)}
                          disabled={evaluatingScenarioId === selectedScenario.id}
                          className="w-full bg-rose-600 hover:bg-rose-500 text-white text-xs py-2 flex items-center justify-center gap-2"
                        >
                          <Zap className="w-3.5 h-3.5" />
                          <span>Run Stress Simulation for this Scenario</span>
                        </Button>
                      </div>
                    </div>
                  )}

                  {/* Traceability Cross-Navigation Links */}
                  <div className="pt-4 border-t border-dark-700/60 flex items-center justify-between text-xs text-slate-400 flex-wrap gap-2">
                    <span className="text-[11px] text-slate-500">Cross-Module Traceability:</span>
                    <div className="flex items-center gap-3">
                      <button
                        onClick={() => navigate(`/decision-contract?inv=${selectedInvId}`)}
                        className="hover:text-rose-400 flex items-center gap-1 transition-colors"
                      >
                        <FileCheck2 className="w-3 h-3" />
                        <span>Contract</span>
                      </button>
                      <button
                        onClick={() => navigate(`/evidence-graph?inv=${selectedInvId}`)}
                        className="hover:text-cyan-400 flex items-center gap-1 transition-colors"
                      >
                        <Network className="w-3 h-3" />
                        <span>Graph</span>
                      </button>
                      <button
                        onClick={() => navigate(`/conflict-intelligence?inv=${selectedInvId}`)}
                        className="hover:text-amber-400 flex items-center gap-1 transition-colors"
                      >
                        <AlertTriangle className="w-3 h-3" />
                        <span>Conflicts</span>
                      </button>
                      <button
                        onClick={() => navigate(`/evidence-sufficiency?inv=${selectedInvId}`)}
                        className="hover:text-emerald-400 flex items-center gap-1 transition-colors"
                      >
                        <CheckCircle2 className="w-3 h-3" />
                        <span>Sufficiency</span>
                      </button>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="p-8 text-center text-slate-500 text-xs">
                  Select a scenario from the list to inspect stress parameters.
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: COMPARATIVE STRESS MATRIX */}
      {activeTab === "matrix" && (
        <div className="flex flex-col gap-4">
          <div className="p-4 bg-dark-900/60 border border-dark-700/60 rounded-xl">
            <div className="flex items-center justify-between mb-3">
              <div>
                <h3 className="text-sm font-bold text-white flex items-center gap-2">
                  <GitCompare className="w-4 h-4 text-rose-400" />
                  <span>Comparative Requirement Degradation Matrix</span>
                </h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  Side-by-side comparison of baseline requirement coverage against each simulated stress scenario.
                </p>
              </div>

              {scenarios.some((s) => s.evaluation_status === "unevaluated") && (
                <Button
                  onClick={handleEvaluateAll}
                  disabled={isEvaluatingAll}
                  className="text-xs bg-rose-600 hover:bg-rose-500 text-white flex items-center gap-1.5"
                >
                  <Zap className="w-3.5 h-3.5" />
                  <span>Evaluate Remaining Scenarios</span>
                </Button>
              )}
            </div>

            {evaluatedScenarios.length === 0 ? (
              <div className="p-12 text-center text-slate-500 text-xs flex flex-col items-center gap-3">
                <GitCompare className="w-8 h-8 text-slate-600" />
                <span>No scenarios have been evaluated yet. Run scenario evaluations to populate the comparative matrix.</span>
                <Button
                  onClick={handleEvaluateAll}
                  disabled={isEvaluatingAll || scenarios.length === 0}
                  className="mt-2 text-xs bg-rose-600 hover:bg-rose-500 text-white"
                >
                  Evaluate All Scenarios
                </Button>
              </div>
            ) : (
              <div className="overflow-x-auto border border-dark-700 rounded-lg">
                <table className="w-full text-left text-xs border-collapse">
                  <thead>
                    <tr className="bg-dark-800 text-slate-300 font-mono text-[11px] border-b border-dark-700">
                      <th className="p-3 sticky left-0 bg-dark-800 z-10 min-w-[200px] border-r border-dark-700">
                        Requirement
                      </th>
                      <th className="p-3 min-w-[120px] bg-dark-800/90 text-cyan-400 border-r border-dark-700">
                        Baseline
                      </th>
                      {evaluatedScenarios.map((sc) => (
                        <th key={sc.id} className="p-3 min-w-[160px] border-r border-dark-700">
                          <div className="font-semibold text-white truncate max-w-[150px]">{sc.title}</div>
                          <div className="text-[10px] text-slate-400 font-normal">
                            {CATEGORY_META[sc.category]?.label || sc.category}
                          </div>
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-dark-800 bg-dark-900/60">
                    {allMatrixRequirements.map((req) => {
                      // Find baseline status from first evaluation
                      const baseItem = evaluatedScenarios[0]?.evaluation?.requirement_evaluations.find(
                        (re) => re.requirement_id === req.id
                      );
                      const baseStatus = baseItem?.baseline_status || "PENDING";

                      return (
                        <tr key={req.id} className="hover:bg-dark-800/40 transition-colors">
                          <td className="p-3 font-medium text-slate-200 sticky left-0 bg-dark-900/95 z-10 border-r border-dark-700">
                            {req.title}
                          </td>
                          <td className="p-3 font-mono text-[11px] border-r border-dark-700">
                            <span className="px-1.5 py-0.5 rounded bg-dark-800 text-slate-300">
                              {baseStatus}
                            </span>
                          </td>
                          {evaluatedScenarios.map((sc) => {
                            const reqEval = sc.evaluation?.requirement_evaluations.find(
                              (re) => re.requirement_id === req.id
                            );
                            const status = reqEval?.scenario_status || baseStatus;
                            const isDegraded = reqEval?.status_shift === "DEGRADED";

                            return (
                              <td
                                key={sc.id}
                                className={`p-3 font-mono text-[11px] border-r border-dark-700 ${
                                  isDegraded ? "bg-rose-500/10" : ""
                                }`}
                              >
                                <span
                                  className={`px-1.5 py-0.5 rounded ${
                                    isDegraded
                                      ? "bg-rose-500/25 text-rose-300 font-bold border border-rose-500/40"
                                      : "text-slate-400"
                                  }`}
                                >
                                  {status}
                                </span>
                              </td>
                            );
                          })}
                        </tr>
                      );
                    })}

                    {/* Overall Decision Outcome Row */}
                    <tr className="bg-dark-800/80 font-bold border-t-2 border-dark-700 text-xs">
                      <td className="p-3 sticky left-0 bg-dark-800 z-10 border-r border-dark-700 text-white">
                        Overall Decision Outcome
                      </td>
                      <td className="p-3 border-r border-dark-700 font-mono">
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] border ${
                            OUTCOME_META[baseline?.baseline_outcome || "INDETERMINATE"]?.bg || "bg-dark-900"
                          } ${OUTCOME_META[baseline?.baseline_outcome || "INDETERMINATE"]?.text || "text-slate-300"} ${
                            OUTCOME_META[baseline?.baseline_outcome || "INDETERMINATE"]?.border || "border-dark-700"
                          }`}
                        >
                          {baseline?.baseline_outcome || "PENDING"}
                        </span>
                      </td>
                      {evaluatedScenarios.map((sc) => {
                        const outcome = sc.evaluation?.scenario_overall_outcome || "INDETERMINATE";
                        return (
                          <td key={sc.id} className="p-3 border-r border-dark-700 font-mono">
                            <span
                              className={`px-2 py-0.5 rounded text-[10px] border ${
                                OUTCOME_META[outcome]?.bg || "bg-dark-900"
                              } ${OUTCOME_META[outcome]?.text || "text-slate-300"} ${
                                OUTCOME_META[outcome]?.border || "border-dark-700"
                              }`}
                            >
                              {outcome}
                            </span>
                          </td>
                        );
                      })}
                    </tr>
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
