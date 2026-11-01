import React, { useState, useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import {
  listInvestigations,
  getLatestFragility,
  getFragilityStatus,
  runFragilityAnalysis,
  simulateSensitivity,
  getSensitivityResults,
  getFragilityRecommendations,
  getFragilityMethodology,
  Investigation,
  DecisionFragilityResult,
  FragilityStatus,
  SensitivityExperimentResult,
  EvidenceImprovementRecommendation,
  FragilityMethodology,
  SensitivitySimulationRequest,
} from "@/lib/api";
import {
  TrendingDown,
  ShieldAlert,
  AlertTriangle,
  RefreshCw,
  Sparkles,
  Layers,
  Sliders,
  Award,
  BookOpen,
  Info,
  Scale,
  Activity,
} from "lucide-react";
import { Button } from "@/components/ui/Button";

export function FragilityPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const currentInvId = searchParams.get("investigation_id") || "";

  const [investigations, setInvestigations] = useState<Investigation[]>([]);
  const [selectedInvId, setSelectedInvId] = useState<string>(currentInvId);
  const [loading, setLoading] = useState<boolean>(true);
  const [analyzing, setAnalyzing] = useState<boolean>(false);
  const [simulating, setSimulating] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const [result, setResult] = useState<DecisionFragilityResult | null>(null);
  const [status, setStatus] = useState<FragilityStatus | null>(null);
  const [simulations, setSimulations] = useState<SensitivityExperimentResult[]>([]);
  const [recommendations, setRecommendations] = useState<EvidenceImprovementRecommendation[]>([]);
  const [methodology, setMethodology] = useState<FragilityMethodology | null>(null);

  const [activeTab, setActiveTab] = useState<"ledger" | "simulator" | "recommendations" | "methodology">("ledger");

  // Simulation Form State
  const [simType, setSimType] = useState<SensitivitySimulationRequest["experiment_type"]>("SIM_GAP_CORROBORATION");
  const [simTargetId, setSimTargetId] = useState<string>("");
  const [simTargetType, setSimTargetType] = useState<"requirement" | "conflict" | "assumption">("requirement");
  const [simStatusParam, setSimStatusParam] = useState<string>("SUFFICIENT");

  // Initial load: investigations list & methodology
  useEffect(() => {
    async function init() {
      try {
        const [invs, meth] = await Promise.all([
          listInvestigations(),
          getFragilityMethodology().catch(() => null),
        ]);
        setInvestigations(invs);
        setMethodology(meth);

        if (invs.length > 0) {
          const target = invs.find((i) => i.id === currentInvId) || invs[0];
          setSelectedInvId(target.id);
          if (target.id !== currentInvId) {
            setSearchParams({ investigation_id: target.id });
          }
        }
      } catch (err: any) {
        setError(err.message || "Failed to initialize platform data");
      } finally {
        setLoading(false);
      }
    }
    init();
  }, [currentInvId, setSearchParams]);

  // Load Fragility data for selected investigation
  useEffect(() => {
    if (!selectedInvId) return;

    let isMounted = true;
    async function loadData() {
      setLoading(true);
      setError(null);
      try {
        const [fragRes, statusRes, simRes, recsRes] = await Promise.allSettled([
          getLatestFragility(selectedInvId),
          getFragilityStatus(selectedInvId),
          getSensitivityResults(selectedInvId),
          getFragilityRecommendations(selectedInvId),
        ]);

        if (!isMounted) return;

        if (statusRes.status === "fulfilled") {
          setStatus(statusRes.value);
        } else {
          setStatus(null);
        }

        if (fragRes.status === "fulfilled") {
          setResult(fragRes.value);
          // Set default target ID for simulation form if available
          if (fragRes.value.attribution_ledger.length > 0) {
            setSimTargetId(fragRes.value.attribution_ledger[0].entity_id);
          }
        } else {
          setResult(null);
        }

        if (simRes.status === "fulfilled") {
          setSimulations(simRes.value.experiments);
        } else {
          setSimulations([]);
        }

        if (recsRes.status === "fulfilled") {
          setRecommendations(recsRes.value.recommendations);
        } else {
          setRecommendations([]);
        }
      } catch (err: any) {
        if (isMounted) setError(err.message || "Failed to load fragility data");
      } finally {
        if (isMounted) setLoading(false);
      }
    }
    loadData();

    return () => {
      isMounted = false;
    };
  }, [selectedInvId]);

  const handleSelectInvestigation = (id: string) => {
    setSelectedInvId(id);
    setSearchParams({ investigation_id: id });
  };

  const handleRunAnalysis = async () => {
    if (!selectedInvId) return;
    setAnalyzing(true);
    setError(null);
    try {
      const res = await runFragilityAnalysis(selectedInvId, true);
      setResult(res.result);
      // Reload status, recommendations and simulations
      const [statusRes, simRes, recsRes] = await Promise.allSettled([
        getFragilityStatus(selectedInvId),
        getSensitivityResults(selectedInvId),
        getFragilityRecommendations(selectedInvId),
      ]);
      if (statusRes.status === "fulfilled") setStatus(statusRes.value);
      if (simRes.status === "fulfilled") setSimulations(simRes.value.experiments);
      if (recsRes.status === "fulfilled") setRecommendations(recsRes.value.recommendations);
    } catch (err: any) {
      setError(err.message || "Failed to execute fragility analysis");
    } finally {
      setAnalyzing(false);
    }
  };

  const handleRunSimulation = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedInvId || !simTargetId) return;
    setSimulating(true);
    setError(null);
    try {
      const simReq: SensitivitySimulationRequest = {
        experiment_type: simType,
        target_entity_id: simTargetId,
        target_entity_type: simTargetType,
        hypothetical_parameters:
          simType === "SIM_EVIDENCE_WEAKENING"
            ? { target_status: simStatusParam }
            : simType === "SIM_CONFLICT_RESOLUTION"
            ? { resolution_status: "resolved_claim_a" }
            : {},
      };
      const exp = await simulateSensitivity(selectedInvId, simReq);
      setSimulations([exp, ...simulations]);
    } catch (err: any) {
      setError(err.message || "Simulation failed");
    } finally {
      setSimulating(false);
    }
  };

  // Helper styling for classifications
  const getClassificationStyle = (cls: string, guardrail: boolean) => {
    if (guardrail) {
      return {
        bg: "bg-rose-950/80",
        border: "border-rose-500",
        text: "text-rose-300",
        pill: "bg-rose-500/20 text-rose-300 border-rose-500/40",
      };
    }
    if (cls.includes("LOW")) {
      return {
        bg: "bg-emerald-950/60",
        border: "border-emerald-700/60",
        text: "text-emerald-400",
        pill: "bg-emerald-500/20 text-emerald-300 border-emerald-500/40",
      };
    }
    if (cls.includes("MODERATE")) {
      return {
        bg: "bg-amber-950/60",
        border: "border-amber-700/60",
        text: "text-amber-400",
        pill: "bg-amber-500/20 text-amber-300 border-amber-500/40",
      };
    }
    if (cls.includes("HIGH")) {
      return {
        bg: "bg-orange-950/60",
        border: "border-orange-700/60",
        text: "text-orange-400",
        pill: "bg-orange-500/20 text-orange-300 border-orange-500/40",
      };
    }
    return {
      bg: "bg-rose-950/60",
      border: "border-rose-700/60",
      text: "text-rose-400",
      pill: "bg-rose-500/20 text-rose-300 border-rose-500/40",
    };
  };

  const selectedInv = investigations.find((i) => i.id === selectedInvId);

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-16">
      {/* 1. Header & Investigation Selector */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-5">
        <div>
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-lg bg-sky-950/60 border border-sky-800/60 text-sky-400 shadow-sm">
              <TrendingDown className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-xl font-bold text-slate-100 tracking-tight">Decision Fragility Index</h1>
                {loading && (
                  <span className="text-[10px] px-2 py-0.5 rounded font-mono text-slate-400 bg-slate-800 animate-pulse">
                    Loading...
                  </span>
                )}
                {result && !loading && (
                  <span
                    className={`text-xs px-2 py-0.5 rounded font-mono font-medium border ${
                      result.processing_mode === "gemini"
                        ? "bg-purple-950/70 text-purple-300 border-purple-800/60"
                        : "bg-slate-800 text-slate-300 border-slate-700"
                    }`}
                  >
                    {result.processing_mode === "gemini" ? "Gemini Synthesized" : "Deterministic Math"}
                  </span>
                )}
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                {selectedInv?.research_question ? (
                  <span className="text-slate-300 font-medium">"{selectedInv.research_question}" • </span>
                ) : null}
                Measures decision vulnerability from 0 (solid) to 100 (fragile) based on evidence gaps, conflicts, and assumptions.
              </p>
            </div>
          </div>
        </div>

        {/* Action Controls */}
        <div className="flex flex-wrap items-center gap-2.5">
          <select
            value={selectedInvId}
            onChange={(e) => handleSelectInvestigation(e.target.value)}
            className="bg-slate-900 border border-slate-700 text-slate-100 text-xs rounded-lg px-3 py-2 font-mono focus:outline-none focus:ring-1 focus:ring-sky-500 max-w-xs cursor-pointer shadow-sm"
          >
            {investigations.map((inv) => (
              <option key={inv.id} value={inv.id} className="bg-slate-900 text-slate-100 py-1.5">
                {inv.research_question ? inv.research_question.slice(0, 45) : inv.id}
              </option>
            ))}
          </select>

          <Button
            onClick={handleRunAnalysis}
            disabled={analyzing || !selectedInvId}
            className="bg-sky-600 hover:bg-sky-500 text-white text-xs px-3.5 py-2 flex items-center gap-1.5 shadow-sm font-medium"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${analyzing ? "animate-spin" : ""}`} />
            {analyzing ? "Evaluating..." : result ? "Recalculate Risk Score" : "Calculate Risk Score"}
          </Button>
        </div>
      </div>

      {/* Error Callout */}
      {error && (
        <div className="p-4 rounded-lg bg-rose-950/40 border border-rose-800/60 text-rose-300 text-xs flex items-start gap-3">
          <AlertTriangle className="w-4 h-4 text-rose-400 mt-0.5 shrink-0" />
          <div className="flex-1">
            <p className="font-semibold text-rose-200">Analysis Error</p>
            <p className="mt-0.5 text-rose-300/90 font-mono">{error}</p>
          </div>
        </div>
      )}

      {/* 2. Hero Diagnostic Score Card */}
      {result ? (
        <div className="space-y-4">
          {/* Stale Upstream Evaluation Warning Banner */}
          {(result.is_stale || status?.is_stale) && (
            <div className="p-4 rounded-xl bg-amber-950/60 border-2 border-amber-600/80 text-amber-100 shadow-md flex items-start gap-4">
              <div className="p-2 rounded-lg bg-amber-800/80 text-amber-100 shrink-0">
                <RefreshCw className="w-5 h-5" />
              </div>
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <h3 className="text-sm font-bold tracking-wide uppercase text-amber-200">
                    Stale Fragility Evaluation Detected
                  </h3>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-900 border border-amber-500 text-amber-200">
                    INDETERMINATE / STALE
                  </span>
                </div>
                <p className="text-xs text-amber-200/90 mt-1 leading-relaxed">
                  Upstream contract specifications, evidence records, or sufficiency assessments have been modified since this fragility evaluation was computed. The displayed score may not reflect the latest state.
                </p>
                <div className="mt-2 flex items-center gap-3">
                  <Button
                    onClick={handleRunAnalysis}
                    disabled={analyzing}
                    className="bg-amber-600 hover:bg-amber-500 text-slate-900 text-xs px-3 py-1 font-semibold"
                  >
                    {analyzing ? "Re-evaluating..." : "Re-calculate DFI Now"}
                  </Button>
                </div>
              </div>
            </div>
          )}

          {/* Critical Guardrail Banner if Active */}
          {result.guardrail_active && (
            <div className="p-4 rounded-xl bg-gradient-to-r from-rose-950 via-rose-900/60 to-rose-950 border-2 border-rose-500 text-rose-100 shadow-lg shadow-rose-950/50 flex items-start gap-4 animate-pulse">
              <div className="p-2 rounded-lg bg-rose-800/80 text-rose-100 shrink-0">
                <ShieldAlert className="w-6 h-6" />
              </div>
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <h3 className="text-sm font-bold tracking-wide uppercase text-rose-200">
                    Critical Deficit Guardrail Triggered
                  </h3>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-rose-900 border border-rose-400 text-rose-200">
                    FOUNDATION UNGROUNDED
                  </span>
                </div>
                <p className="text-xs text-rose-200/90 mt-1 leading-relaxed">
                  {result.guardrail_reason ||
                    "One or more CRITICAL decision contract requirements lack substantiating evidence (NO_EVIDENCE) or suffer from unresolved contradictions (CONFLICTING)."}
                </p>
                <p className="text-[11px] text-rose-300/80 mt-1.5 font-mono">
                  Guardrail policy: This override prevents fragile decisions with ungrounded foundations from being
                  classified as low or moderate risk, regardless of mathematical score.
                </p>
              </div>
            </div>
          )}

          {/* Provisional Assessment Banner */}
          {result.is_provisional && !result.guardrail_active && (
            <div className="p-3.5 rounded-xl bg-amber-950/40 border border-amber-700/60 text-amber-200 text-xs flex items-start gap-3">
              <Info className="w-4 h-4 text-amber-400 mt-0.5 shrink-0" />
              <div className="flex-1">
                <p className="font-semibold text-amber-300">Provisional Evaluation Notice</p>
                <p className="mt-0.5 text-amber-300/80 leading-relaxed">
                  Upstream diagnostic analyses (Conflict Engine or Stress Testing) have not yet
                  been executed for this investigation. Unassessed dimensions are held at 0.0 in the raw calculation, but
                  policy mandates that provisional scores cannot be classified below Moderate Fragility until complete
                  evidentiary verification is performed.
                </p>
              </div>
            </div>
          )}

          {/* Unsubstantiated Critical Requirements Warning (Clarification 2) */}
          {result.unsubstantiated_critical_requirements &&
            result.unsubstantiated_critical_requirements.length > 0 && (
              <div className="p-3.5 rounded-xl bg-slate-900/90 border border-orange-800/60 text-orange-200 text-xs flex items-start gap-3">
                <AlertTriangle className="w-4 h-4 text-orange-400 mt-0.5 shrink-0" />
                <div className="flex-1">
                  <p className="font-semibold text-orange-300">
                    Mandatory Substantiation Warning: {result.unsubstantiated_critical_requirements.length} Critical
                    Requirement(s) Not Fully Substantiated
                  </p>
                  <p className="mt-0.5 text-slate-300 text-[11px]">
                    The following critical decision requirement(s) hold INSUFFICIENT or PARTIAL evidence status and
                    lack multi-source corroboration:
                  </p>
                  <ul className="mt-1.5 space-y-1 list-disc list-inside font-mono text-[11px] text-orange-300/90">
                    {result.unsubstantiated_critical_requirements.map((item, idx) => (
                      <li key={idx}>{item}</li>
                    ))}
                  </ul>
                </div>
              </div>
            )}

          {/* Main Hero Diagnostic Display */}
          <div
            className={`p-6 rounded-2xl border ${
              getClassificationStyle(result.classification, result.guardrail_active).bg
            } ${getClassificationStyle(result.classification, result.guardrail_active).border} shadow-xl backdrop-blur-sm`}
          >
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-center">
              {/* Left: DFI Gauge & Classification */}
              <div className="lg:col-span-5 flex flex-col items-center lg:items-start text-center lg:text-left border-b lg:border-b-0 lg:border-r border-slate-800/80 lg:pr-6 pb-6 lg:pb-0">
                <span className="text-xs font-mono font-semibold uppercase tracking-wider text-slate-400">
                  Decision Fragility Index (DFI)
                </span>

                <div className="flex items-baseline gap-2 mt-2">
                  <span className="text-6xl font-black font-mono tracking-tight text-slate-100">
                    {result.dfi_score.toFixed(1)}
                  </span>
                  <span className="text-lg font-mono text-slate-500">/ 100.0</span>
                </div>

                <div className="mt-3">
                  <span
                    className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-mono font-bold tracking-wide uppercase border ${
                      getClassificationStyle(result.classification, result.guardrail_active).pill
                    }`}
                  >
                    <Scale className="w-3.5 h-3.5" />
                    {result.classification}
                  </span>
                </div>

                <p className="text-xs text-slate-400 mt-3 leading-relaxed max-w-sm">
                  {result.dfi_score <= 25.0
                    ? "Decision premise exhibits robust multi-source grounding and stable resilience to tested stressors."
                    : result.dfi_score <= 50.0
                    ? "Moderate sensitivity to unresolved evidentiary gaps, assumptions, or minor contradictory claims."
                    : result.dfi_score <= 75.0
                    ? "Elevated decision fragility: Material gaps or unresolved contradictions create significant structural risk."
                    : "Extreme structural fragility: Core decision foundations are unsupported, contradictory, or vulnerable to shock."}
                </p>
              </div>

              {/* Right: Quick Diagnostic Highlights */}
              <div className="lg:col-span-7 grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800 text-center">
                  <span className="text-[10px] font-mono text-slate-400 uppercase tracking-wider block">Coverage D1</span>
                  <span className="text-xl font-bold font-mono text-slate-100 mt-1 block">
                    {result.d1_coverage.toFixed(1)}
                  </span>
                  <span className="text-[10px] text-slate-500 font-mono">Weight: 30%</span>
                </div>

                <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800 text-center">
                  <span className="text-[10px] font-mono text-slate-400 uppercase tracking-wider block">Assumptions D2</span>
                  <span className="text-xl font-bold font-mono text-slate-100 mt-1 block">
                    {result.d2_assumptions.toFixed(1)}
                  </span>
                  <span className="text-[10px] text-slate-500 font-mono">Weight: 15%</span>
                </div>

                <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800 text-center">
                  <span className="text-[10px] font-mono text-slate-400 uppercase tracking-wider block">Conflicts D3</span>
                  <span className="text-xl font-bold font-mono text-slate-100 mt-1 block">
                    {result.d3_conflicts.toFixed(1)}
                  </span>
                  <span className="text-[10px] text-slate-500 font-mono">Weight: 25%</span>
                </div>

                <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800 text-center">
                  <span className="text-[10px] font-mono text-slate-400 uppercase tracking-wider block">Stress Shifts D4</span>
                  <span className="text-xl font-bold font-mono text-slate-100 mt-1 block">
                    {result.d4_stress.toFixed(1)}
                  </span>
                  <span className="text-[10px] text-slate-500 font-mono">Weight: 20%</span>
                </div>

                <div className="col-span-2 sm:col-span-4 p-3.5 rounded-xl bg-slate-900/40 border border-slate-800 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Activity className="w-4 h-4 text-sky-400" />
                    <span className="text-xs text-slate-300 font-medium">
                      Concentration Concentration (D5, 10%):
                    </span>
                    <span className="text-xs font-mono font-bold text-sky-300">
                      {result.d5_concentration.toFixed(1)} / 100.0
                    </span>
                  </div>
                  <span className="text-[11px] font-mono text-slate-400">
                    {result.dimensions?.d5_concentration?.metrics?.concentration_label || "UNCONCENTRATED"}
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* 3. 5-Dimension Detailed Breakdown Cards */}
          <div className="grid grid-cols-1 md:grid-cols-5 gap-3.5">
            {Object.entries(result.dimensions || {}).map(([dimKey, dim]) => (
              <div
                key={dimKey}
                className="p-4 rounded-xl bg-slate-900/70 border border-slate-800 flex flex-col justify-between hover:border-slate-700 transition"
              >
                <div>
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] font-mono font-bold text-slate-400 uppercase">
                      {dim.dimension_key.replace("_", " ").toUpperCase()}
                    </span>
                    <span
                      className={`text-[9px] font-mono px-1.5 py-0.5 rounded border ${
                        dim.status === "ASSESSED"
                          ? "bg-slate-800 text-slate-300 border-slate-700"
                          : dim.status === "NOT_APPLICABLE"
                          ? "bg-slate-800/50 text-slate-500 border-slate-800"
                          : "bg-amber-950/60 text-amber-400 border-amber-800/60"
                      }`}
                    >
                      {dim.status}
                    </span>
                  </div>

                  <h4 className="text-xs font-semibold text-slate-200 mt-1">{dim.dimension_name}</h4>

                  <div className="flex items-baseline gap-1 mt-3">
                    <span className="text-2xl font-bold font-mono text-slate-100">{dim.score.toFixed(1)}</span>
                    <span className="text-[10px] text-slate-500 font-mono">/ 100</span>
                  </div>

                  {/* Progress Bar */}
                  <div className="w-full bg-slate-800 rounded-full h-1.5 mt-2 overflow-hidden">
                    <div
                      className={`h-full rounded-full ${
                        dim.score <= 25 ? "bg-emerald-500" : dim.score <= 50 ? "bg-amber-500" : "bg-rose-500"
                      }`}
                      style={{ width: `${Math.min(100, Math.max(3, dim.score))}%` }}
                    />
                  </div>

                  <p className="text-[11px] text-slate-400 mt-2.5 leading-relaxed">
                    {dim.explanation}
                  </p>
                </div>

                <div className="mt-3 pt-2.5 border-t border-slate-800/80 flex items-center justify-between text-[10px] text-slate-400 font-mono">
                  <span>Weight: {(dim.weight * 100).toFixed(0)}%</span>
                  <span className="text-slate-200 font-semibold">+{dim.weighted_contribution.toFixed(1)} DFI</span>
                </div>
              </div>
            ))}
          </div>

          {/* 4. Tab Navigation */}
          <div className="flex items-center gap-2 border-b border-slate-800 pt-3">
            <button
              onClick={() => setActiveTab("ledger")}
              className={`px-4 py-2.5 text-xs font-mono font-medium border-b-2 flex items-center gap-2 transition ${
                activeTab === "ledger"
                  ? "border-sky-500 text-sky-400 bg-sky-950/20"
                  : "border-transparent text-slate-400 hover:text-slate-200"
              }`}
            >
              <Layers className="w-3.5 h-3.5" />
              Point Attribution Ledger ({result.attribution_ledger.length})
            </button>

            <button
              onClick={() => setActiveTab("simulator")}
              className={`px-4 py-2.5 text-xs font-mono font-medium border-b-2 flex items-center gap-2 transition ${
                activeTab === "simulator"
                  ? "border-sky-500 text-sky-400 bg-sky-950/20"
                  : "border-transparent text-slate-400 hover:text-slate-200"
              }`}
            >
              <Sliders className="w-3.5 h-3.5" />
              What-If Sensitivity Simulator ({simulations.length})
            </button>

            <button
              onClick={() => setActiveTab("recommendations")}
              className={`px-4 py-2.5 text-xs font-mono font-medium border-b-2 flex items-center gap-2 transition ${
                activeTab === "recommendations"
                  ? "border-sky-500 text-sky-400 bg-sky-950/20"
                  : "border-transparent text-slate-400 hover:text-slate-200"
              }`}
            >
              <Award className="w-3.5 h-3.5" />
              Actionable Evidence Improvements ({recommendations.length})
            </button>

            <button
              onClick={() => setActiveTab("methodology")}
              className={`px-4 py-2.5 text-xs font-mono font-medium border-b-2 flex items-center gap-2 transition ${
                activeTab === "methodology"
                  ? "border-sky-500 text-sky-400 bg-sky-950/20"
                  : "border-transparent text-slate-400 hover:text-slate-200"
              }`}
            >
              <BookOpen className="w-3.5 h-3.5" />
              Analytical Narrative & Methodology
            </button>
          </div>

          {/* 5. Tab Contents */}

          {/* TAB 1: ATTRIBUTION LEDGER */}
          {activeTab === "ledger" && (
            <div className="space-y-4">
              <div className="flex items-center justify-between text-xs text-slate-400">
                <p>
                  Every single point in the DFI score is mathematically tied to a specific requirement deficit,
                  assumption penalty, conflict record, or stress shift.
                </p>
                <span className="font-mono text-slate-300">
                  Total Active Drivers: {result.attribution_ledger.length}
                </span>
              </div>

              {result.attribution_ledger.length === 0 ? (
                <div className="p-8 rounded-xl bg-slate-900/40 border border-slate-800 text-center text-slate-400 text-xs font-mono">
                  Zero active penalty drivers recorded. All evaluated dimensions show complete sufficiency and zero contradictions.
                </div>
              ) : (
                <div className="overflow-x-auto rounded-xl border border-slate-800">
                  <table className="w-full text-left text-xs font-mono">
                    <thead className="bg-slate-900/90 text-slate-400 border-b border-slate-800 uppercase text-[10px]">
                      <tr>
                        <th className="py-3 px-4">Dimension</th>
                        <th className="py-3 px-4">Category</th>
                        <th className="py-3 px-4">Target Entity</th>
                        <th className="py-3 px-4 text-right">Base Penalty</th>
                        <th className="py-3 px-4 text-right">Multiplier</th>
                        <th className="py-3 px-4 text-right">Net DFI Points</th>
                        <th className="py-3 px-4">Forensic Rationale</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/60 bg-slate-900/40 text-slate-300">
                      {result.attribution_ledger.map((item, idx) => (
                        <tr key={item.item_id || idx} className="hover:bg-slate-850/50 transition">
                          <td className="py-3 px-4">
                            <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300 text-[10px] border border-slate-700">
                              {item.dimension.replace("_", " ").toUpperCase()}
                            </span>
                          </td>
                          <td className="py-3 px-4 text-slate-400">{item.category}</td>
                          <td className="py-3 px-4 font-semibold text-slate-200 max-w-xs truncate" title={item.entity_title}>
                            {item.entity_title}
                          </td>
                          <td className="py-3 px-4 text-right text-slate-300">{item.base_penalty.toFixed(1)}</td>
                          <td className="py-3 px-4 text-right text-slate-400">×{item.multiplier.toFixed(2)}</td>
                          <td className="py-3 px-4 text-right font-bold text-sky-400">
                            +{item.net_dfi_contribution.toFixed(1)} pts
                          </td>
                          <td className="py-3 px-4 text-slate-400 text-[11px] max-w-md truncate" title={item.rationale}>
                            {item.rationale}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {/* TAB 2: WHAT-IF SENSITIVITY SIMULATOR */}
          {activeTab === "simulator" && (
            <div className="space-y-6">
              {/* Epistemic Sandbox Isolation Notice */}
              <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-700 text-xs flex items-start gap-3">
                <Info className="w-4 h-4 text-sky-400 mt-0.5 shrink-0" />
                <div className="flex-1">
                  <p className="font-semibold text-slate-200">In-Memory Sandbox Guarantee</p>
                  <p className="mt-0.5 text-slate-400 leading-relaxed">
                    Sensitivity simulations evaluate hypothetical changes in evidence coverage, assumption validity,
                    or conflict adjudication strictly in-memory. Primary database records and empirical findings remain
                    completely untouched.
                  </p>
                </div>
              </div>

              {/* Simulation Trigger Form */}
              <form onSubmit={handleRunSimulation} className="p-5 rounded-xl bg-slate-900/90 border border-slate-800 space-y-4">
                <div className="flex items-center gap-2">
                  <Sliders className="w-4 h-4 text-sky-400" />
                  <h3 className="text-sm font-bold text-slate-200">Configure Counterfactual Experiment</h3>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                  <div>
                    <label className="block text-[11px] font-mono text-slate-400 mb-1">Experiment Type</label>
                    <select
                      value={simType}
                      onChange={(e) => {
                        const val = e.target.value as any;
                        setSimType(val);
                        if (val === "SIM_CONFLICT_RESOLUTION") setSimTargetType("conflict");
                        else if (val === "SIM_ASSUMPTION_FAILURE") setSimTargetType("assumption");
                        else setSimTargetType("requirement");
                      }}
                      className="w-full bg-slate-900 border border-slate-700 text-slate-100 text-xs rounded-lg px-3 py-2 font-mono focus:outline-none focus:ring-1 focus:ring-sky-500 cursor-pointer"
                    >
                      <option value="SIM_GAP_CORROBORATION" className="bg-slate-900 text-slate-100">Simulate Gap Corroboration</option>
                      <option value="SIM_EVIDENCE_WEAKENING" className="bg-slate-900 text-slate-100">Simulate Evidence Weakening</option>
                      <option value="SIM_CONFLICT_RESOLUTION" className="bg-slate-900 text-slate-100">Simulate Conflict Resolution</option>
                      <option value="SIM_ASSUMPTION_FAILURE" className="bg-slate-900 text-slate-100">Simulate Assumption Failure</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-[11px] font-mono text-slate-400 mb-1">Target Entity Type</label>
                    <select
                      value={simTargetType}
                      onChange={(e) => setSimTargetType(e.target.value as any)}
                      className="w-full bg-slate-900 border border-slate-700 text-slate-100 text-xs rounded-lg px-3 py-2 font-mono focus:outline-none focus:ring-1 focus:ring-sky-500 cursor-pointer"
                    >
                      <option value="requirement" className="bg-slate-900 text-slate-100">Requirement</option>
                      <option value="conflict" className="bg-slate-900 text-slate-100">Conflict</option>
                      <option value="assumption" className="bg-slate-900 text-slate-100">Assumption</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-[11px] font-mono text-slate-400 mb-1">Target Entity ID</label>
                    <input
                      type="text"
                      value={simTargetId}
                      onChange={(e) => setSimTargetId(e.target.value)}
                      placeholder="e.g. req-0 or conflict-id"
                      required
                      className="w-full bg-slate-900 border border-slate-700 text-slate-100 text-xs rounded-lg px-3 py-2 font-mono focus:outline-none focus:ring-1 focus:ring-sky-500"
                    />
                  </div>

                  {simType === "SIM_EVIDENCE_WEAKENING" && (
                    <div>
                      <label className="block text-[11px] font-mono text-slate-400 mb-1">Simulated Status</label>
                      <select
                        value={simStatusParam}
                        onChange={(e) => setSimStatusParam(e.target.value)}
                        className="w-full bg-slate-900 border border-slate-700 text-slate-100 text-xs rounded-lg px-3 py-2 font-mono focus:outline-none focus:ring-1 focus:ring-sky-500 cursor-pointer"
                      >
                        <option value="NO_EVIDENCE" className="bg-slate-900 text-slate-100">NO_EVIDENCE (Deficit 1.00)</option>
                        <option value="CONFLICTING" className="bg-slate-900 text-slate-100">CONFLICTING (Deficit 0.85)</option>
                        <option value="INSUFFICIENT" className="bg-slate-900 text-slate-100">INSUFFICIENT (Deficit 0.75)</option>
                        <option value="PARTIAL">PARTIAL (Deficit 0.40)</option>
                      </select>
                    </div>
                  )}

                  <div className="flex items-end">
                    <Button
                      type="submit"
                      disabled={simulating || !simTargetId}
                      className="w-full bg-sky-600 hover:bg-sky-500 text-white text-xs py-2 shadow-sm font-medium"
                    >
                      {simulating ? "Simulating..." : "Run Simulation"}
                    </Button>
                  </div>
                </div>
              </form>

              {/* Simulation History Table */}
              <div className="space-y-3">
                <h4 className="text-xs font-mono font-bold text-slate-300 uppercase tracking-wider">
                  Hypothetical Sensitivity Experiments ({simulations.length})
                </h4>

                {simulations.length === 0 ? (
                  <div className="p-8 rounded-xl bg-slate-900/40 border border-slate-800 text-center text-slate-400 text-xs font-mono">
                    No counterfactual simulations run yet. Use the form above to evaluate hypothetical evidentiary variations.
                  </div>
                ) : (
                  <div className="overflow-x-auto rounded-xl border border-slate-800">
                    <table className="w-full text-left text-xs font-mono">
                      <thead className="bg-slate-900/90 text-slate-400 border-b border-slate-800 uppercase text-[10px]">
                        <tr>
                          <th className="py-3 px-4">Experiment Type</th>
                          <th className="py-3 px-4">Target Entity</th>
                          <th className="py-3 px-4 text-right">Baseline DFI</th>
                          <th className="py-3 px-4 text-right">Simulated DFI</th>
                          <th className="py-3 px-4 text-right">Delta (Δ DFI)</th>
                          <th className="py-3 px-4">Simulated Classification</th>
                          <th className="py-3 px-4">Narrative Impact</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800/60 bg-slate-900/40 text-slate-300">
                        {simulations.map((sim) => (
                          <tr key={sim.id} className="hover:bg-slate-850/50 transition">
                            <td className="py-3 px-4">
                              <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300 text-[10px] border border-slate-700">
                                {sim.experiment_type}
                              </span>
                            </td>
                            <td className="py-3 px-4 font-semibold text-slate-200">{sim.target_entity_title}</td>
                            <td className="py-3 px-4 text-right text-slate-400">{sim.baseline_dfi.toFixed(1)}</td>
                            <td className="py-3 px-4 text-right font-bold text-slate-100">{sim.simulated_dfi.toFixed(1)}</td>
                            <td className="py-3 px-4 text-right">
                              <span
                                className={`px-2 py-0.5 rounded text-[11px] font-bold ${
                                  sim.delta_dfi < 0
                                    ? "bg-emerald-950/80 text-emerald-400 border border-emerald-800/60"
                                    : sim.delta_dfi > 0
                                    ? "bg-rose-950/80 text-rose-400 border border-rose-800/60"
                                    : "bg-slate-800 text-slate-400"
                                }`}
                              >
                                {sim.delta_dfi > 0 ? `+${sim.delta_dfi.toFixed(1)}` : sim.delta_dfi.toFixed(1)}
                              </span>
                            </td>
                            <td className="py-3 px-4 text-slate-300">{sim.simulated_classification}</td>
                            <td className="py-3 px-4 text-slate-400 text-[11px] max-w-sm truncate" title={sim.narrative_impact}>
                              {sim.narrative_impact}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* TAB 3: ACTIONABLE RECOMMENDATIONS */}
          {activeTab === "recommendations" && (
            <div className="space-y-4">
              <div className="flex items-center justify-between text-xs text-slate-400">
                <p>
                  Recommendations are ranked deterministically by projected DFI reduction (
                  <code className="text-slate-300 font-mono">Δ DFI reduction</code>), prioritizing actions that
                  yield the largest drop in decision vulnerability.
                </p>
                <span className="font-mono text-slate-300">
                  Total Recommendations: {recommendations.length}
                </span>
              </div>

              {recommendations.length === 0 ? (
                <div className="p-8 rounded-xl bg-slate-900/40 border border-slate-800 text-center text-slate-400 text-xs font-mono">
                  No active improvement recommendations. Current evidence base is fully corroborative.
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {recommendations.map((rec) => (
                    <div
                      key={rec.id}
                      className="p-5 rounded-xl bg-slate-900/80 border border-slate-800 hover:border-slate-700 transition flex flex-col justify-between"
                    >
                      <div>
                        <div className="flex items-center justify-between gap-2">
                          <span
                            className={`text-[10px] font-mono px-2 py-0.5 rounded font-bold border ${
                              rec.priority === "HIGH"
                                ? "bg-rose-950/80 text-rose-300 border-rose-800"
                                : rec.priority === "MEDIUM"
                                ? "bg-amber-950/80 text-amber-300 border-amber-800"
                                : "bg-slate-800 text-slate-300 border-slate-700"
                            }`}
                          >
                            PRIORITY: {rec.priority}
                          </span>

                          <span className="px-2.5 py-1 rounded-full text-xs font-mono font-bold bg-emerald-950/80 text-emerald-400 border border-emerald-800/80">
                            -{rec.projected_dfi_reduction.toFixed(1)} DFI Reduction
                          </span>
                        </div>

                        <h4 className="text-sm font-bold text-slate-100 mt-2.5">{rec.title}</h4>
                        <p className="text-xs text-slate-300 mt-1 leading-relaxed">{rec.description}</p>

                        <div className="mt-3.5 space-y-1.5">
                          <span className="text-[10px] font-mono uppercase text-slate-400 tracking-wider">
                            Recommended Forensic Action Steps:
                          </span>
                          <ul className="space-y-1">
                            {rec.action_steps.map((step, sIdx) => (
                              <li key={sIdx} className="text-xs text-slate-300/90 flex items-start gap-2">
                                <span className="text-sky-400 mt-0.5">•</span>
                                <span>{step}</span>
                              </li>
                            ))}
                          </ul>
                        </div>
                      </div>

                      <div className="mt-4 pt-3 border-t border-slate-800/80 flex items-center justify-between text-[11px] font-mono text-slate-400">
                        <span>Action Type: {rec.recommendation_type}</span>
                        <span>Effort: {rec.effort_estimate}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* TAB 4: METHODOLOGY & NARRATIVE */}
          {activeTab === "methodology" && (
            <div className="space-y-6">
              {/* Executive Explanation Narrative */}
              <div className="p-5 rounded-xl bg-slate-900/80 border border-slate-800 space-y-3">
                <div className="flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-purple-400" />
                  <h3 className="text-sm font-bold text-slate-200">
                    Forensic Explanation Narrative
                  </h3>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700">
                    Mode: {result.processing_mode}
                  </span>
                </div>

                <div className="text-xs text-slate-300 leading-relaxed font-mono whitespace-pre-line bg-slate-950/60 p-4 rounded-lg border border-slate-850">
                  {result.explanation_text}
                </div>
              </div>

              {/* Formal Methodology Parameters */}
              {methodology && (
                <div className="p-5 rounded-xl bg-slate-900/60 border border-slate-800 space-y-4">
                  <div className="flex items-center gap-2">
                    <Scale className="w-4 h-4 text-sky-400" />
                    <h3 className="text-sm font-bold text-slate-200">
                      Methodology Specification: {methodology.version}
                    </h3>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs font-mono">
                    <div className="p-3.5 rounded-lg bg-slate-950/40 border border-slate-800 space-y-2">
                      <span className="text-[11px] font-bold text-slate-300 uppercase">Dimension Weights</span>
                      <ul className="space-y-1 text-slate-400 text-[11px]">
                        <li>• Evidence Coverage (D1): {(methodology.weights.d1_coverage * 100).toFixed(0)}%</li>
                        <li>• Contract Assumptions (D2): {(methodology.weights.d2_assumptions * 100).toFixed(0)}%</li>
                        <li>• Evidence Conflicts (D3): {(methodology.weights.d3_conflicts * 100).toFixed(0)}%</li>
                        <li>• Stress Shifts (D4): {(methodology.weights.d4_stress * 100).toFixed(0)}%</li>
                        <li>• Concentration (D5): {(methodology.weights.d5_concentration * 100).toFixed(0)}%</li>
                      </ul>
                    </div>

                    <div className="p-3.5 rounded-lg bg-slate-950/40 border border-slate-800 space-y-2">
                      <span className="text-[11px] font-bold text-slate-300 uppercase">Guardrail & Provisional Policies</span>
                      <p className="text-[11px] text-slate-400 leading-relaxed">
                        {methodology.guardrail_criteria}
                      </p>
                      <p className="text-[11px] text-slate-400 leading-relaxed pt-1">
                        {methodology.provisional_policy}
                      </p>
                    </div>
                  </div>

                  <div className="p-3.5 rounded-lg bg-slate-950/60 border border-slate-800 text-[11px] font-mono text-slate-400 leading-relaxed">
                    <span className="text-slate-300 font-semibold block mb-1">Epistemic Boundary Disclaimer:</span>
                    {methodology.epistemic_disclaimer}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      ) : (
        /* Empty / Initial State */
        <div className="p-12 rounded-2xl bg-slate-900/40 border border-slate-800 text-center space-y-4">
          <div className="w-12 h-12 rounded-xl bg-sky-950/60 border border-sky-800/60 text-sky-400 flex items-center justify-center mx-auto">
            <TrendingDown className="w-6 h-6" />
          </div>
          <div>
            <div className="flex items-center justify-center gap-2 mb-1">
              <h3 className="text-base font-bold text-slate-200">
                {status?.is_indeterminate ? "Evaluation Status: INDETERMINATE" : "No Fragility Index Evaluated Yet"}
              </h3>
              {status?.is_indeterminate && (
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-950 text-amber-300 border border-amber-700/60 font-semibold">
                  PREREQUISITE REQUIRED
                </span>
              )}
            </div>
            <p className="text-xs text-slate-400 max-w-md mx-auto mt-1 leading-relaxed">
              {status?.indeterminate_reason ||
                "Compute the deterministic Decision Fragility Index to quantify decision sensitivity across evidence coverage, assumptions, conflicts, and stress permutations."}
            </p>
          </div>
          <Button
            onClick={handleRunAnalysis}
            disabled={analyzing || !selectedInvId}
            className="bg-sky-600 hover:bg-sky-500 text-white text-xs px-5 py-2.5 shadow-md font-medium"
          >
            {analyzing ? "Evaluating Platform Metrics..." : "Run Fragility Analysis Now"}
          </Button>
        </div>
      )}
    </div>
  );
}
