import React, { useState, useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import {
  listInvestigations,
  getNavigatorQueue,
  generateVerificationPlan,
  updatePlanQueries,
  submitManualCandidate,
  reviewCandidateSource,
  evaluateGap,
  commitGapReassessment,
  getSourceImpactSummary,
  getNavigatorAuditTrail,
  Investigation,
  NavigatorQueueResponse,
  GapQueueItem,
  GapVerificationPlan,
  GapCandidateSource,
  GapReassessment,
  SourceImpactSummary,
  OrchestrationAuditLogItem,
} from "@/lib/api";
import {
  Compass,
  Search,
  AlertTriangle,
  Copy,
  Plus,
  RefreshCw,
  Clock,
  Zap,
  Edit2,
  Trash2,
  Check,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/Button";

export function VerificationPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const currentInvId = searchParams.get("investigation_id") || "";

  const [investigations, setInvestigations] = useState<Investigation[]>([]);
  const [selectedInvId, setSelectedInvId] = useState<string>(currentInvId);
  const [loading, setLoading] = useState<boolean>(true);
  const [actionLoading, setActionLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [copiedQuery, setCopiedQuery] = useState<string | null>(null);

  // Tabs: queue (Workflow A), impacts (Workflow B), audit
  const [activeTab, setActiveTab] = useState<"queue" | "impacts" | "audit">("queue");

  // Workflow A State
  const [queueData, setQueueData] = useState<NavigatorQueueResponse | null>(null);
  const [selectedGap, setSelectedGap] = useState<GapQueueItem | null>(null);
  const [activePlan, setActivePlan] = useState<GapVerificationPlan | null>(null);
  const [candidates, setCandidates] = useState<GapCandidateSource[]>([]);
  const [activeReassessment, setActiveReassessment] = useState<GapReassessment | null>(null);

  // Custom Analyst Instructions & Query Editing
  const [customInstructions, setCustomInstructions] = useState<string>("");
  const [newManualQuery, setNewManualQuery] = useState<string>("");
  const [editingQueryIdx, setEditingQueryIdx] = useState<number | null>(null);
  const [editingQueryText, setEditingQueryText] = useState<string>("");
  const [isSavingQueries, setIsSavingQueries] = useState<boolean>(false);

  // Manual Candidate Form
  const [manualUrl, setManualUrl] = useState<string>("");
  const [manualTitle, setManualTitle] = useState<string>("");
  const [manualSnippet, setManualSnippet] = useState<string>("");

  // Reassessment Sign-off Form
  const [analystDecision, setAnalystDecision] = useState<string>("APPROVED");
  const [analystFinalState, setAnalystFinalState] = useState<string>("RESOLVED");
  const [analystNotes, setAnalystNotes] = useState<string>("");

  // Workflow B State (Source Impact Summaries)
  const [impactSummaries, setImpactSummaries] = useState<SourceImpactSummary[]>([]);

  // Audit Log State
  const [auditLog, setAuditLog] = useState<OrchestrationAuditLogItem[]>([]);

  // 1. Initial Load: Investigations
  useEffect(() => {
    async function init() {
      try {
        const invs = await listInvestigations();
        setInvestigations(invs);
        if (invs.length > 0) {
          const target = invs.find((i) => i.id === currentInvId) || invs[0];
          setSelectedInvId(target.id);
          if (target.id !== currentInvId) {
            setSearchParams({ investigation_id: target.id });
          }
        }
      } catch (err: any) {
        setError(err.message || "Failed to load investigations");
      } finally {
        setLoading(false);
      }
    }
    init();
  }, [currentInvId, setSearchParams]);

  // 2. Load Investigation Data
  useEffect(() => {
    if (!selectedInvId) return;

    let isMounted = true;
    async function loadData() {
      setLoading(true);
      setError(null);
      try {
        const [qRes, auditRes] = await Promise.allSettled([
          getNavigatorQueue(selectedInvId),
          getNavigatorAuditTrail(selectedInvId),
        ]);

        if (!isMounted) return;

        if (qRes.status === "fulfilled") {
          setQueueData(qRes.value);
          if (qRes.value.queue.length > 0) {
            setSelectedGap(qRes.value.queue[0]);
          } else {
            setSelectedGap(null);
          }
        } else {
          setQueueData(null);
        }

        if (auditRes.status === "fulfilled") {
          setAuditLog(auditRes.value);
        } else {
          setAuditLog([]);
        }

        // Fetch sources for this investigation and check impacts
        const inv = investigations.find((i) => i.id === selectedInvId);
        if (inv) {
          // Fetch impact summaries for known sources
          const sourcesRes = await fetch(`/api/investigations/${selectedInvId}/sources`).catch(() => null);
          if (sourcesRes && sourcesRes.ok) {
            const sourcesList = await sourcesRes.json();
            const summaries: SourceImpactSummary[] = [];
            for (const s of sourcesList.slice(0, 5)) {
              try {
                const imp = await getSourceImpactSummary(selectedInvId, s.id);
                if (imp) summaries.push(imp);
              } catch {
                // Ignore missing impact
              }
            }
            if (isMounted) setImpactSummaries(summaries);
          }
        }
      } catch (err: any) {
        if (isMounted) setError(err.message || "Failed to load navigator data");
      } finally {
        if (isMounted) setLoading(false);
      }
    }
    loadData();

    return () => {
      isMounted = false;
    };
  }, [selectedInvId, investigations]);

  const handleSelectInvestigation = (id: string) => {
    setSelectedInvId(id);
    setSearchParams({ investigation_id: id });
  };

  // Generate or load plan for selected gap
  const handleGeneratePlan = async () => {
    if (!selectedInvId || !selectedGap) return;
    setActionLoading(true);
    setError(null);
    try {
      const inst = customInstructions.trim();
      const plan = inst
        ? await generateVerificationPlan(selectedInvId, selectedGap.gap_id, inst)
        : await generateVerificationPlan(selectedInvId, selectedGap.gap_id);
      setActivePlan(plan);
      if (plan.candidates && plan.candidates.length > 0) {
        setCandidates(plan.candidates);
      }
    } catch (err: any) {
      setError(err.message || "Failed to generate plan");
    } finally {
      setActionLoading(false);
    }
  };

  // Add manual query to active plan
  const handleAddManualQuery = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedInvId || !activePlan || !newManualQuery.trim()) return;
    const updatedQueries = [...activePlan.search_queries, newManualQuery.trim()];
    setIsSavingQueries(true);
    setError(null);
    try {
      const updatedPlan = await updatePlanQueries(selectedInvId, activePlan.id, updatedQueries);
      setActivePlan(updatedPlan);
      setNewManualQuery("");
    } catch (err: any) {
      setError(err.message || "Failed to add manual query");
    } finally {
      setIsSavingQueries(false);
    }
  };

  // Save edited query
  const handleSaveEditedQuery = async (idx: number) => {
    if (!selectedInvId || !activePlan || !editingQueryText.trim()) return;
    const updatedQueries = [...activePlan.search_queries];
    updatedQueries[idx] = editingQueryText.trim();
    setIsSavingQueries(true);
    setError(null);
    try {
      const updatedPlan = await updatePlanQueries(selectedInvId, activePlan.id, updatedQueries);
      setActivePlan(updatedPlan);
      setEditingQueryIdx(null);
      setEditingQueryText("");
    } catch (err: any) {
      setError(err.message || "Failed to update query");
    } finally {
      setIsSavingQueries(false);
    }
  };

  // Delete query
  const handleDeleteQuery = async (idx: number) => {
    if (!selectedInvId || !activePlan) return;
    const updatedQueries = activePlan.search_queries.filter((_, i) => i !== idx);
    if (updatedQueries.length === 0) {
      setError("At least one verification query must be retained. You can edit the existing query instead.");
      return;
    }
    setIsSavingQueries(true);
    setError(null);
    try {
      const updatedPlan = await updatePlanQueries(selectedInvId, activePlan.id, updatedQueries);
      setActivePlan(updatedPlan);
    } catch (err: any) {
      setError(err.message || "Failed to delete query");
    } finally {
      setIsSavingQueries(false);
    }
  };

  // Submit manual candidate URL
  const handleAddCandidate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedInvId || !activePlan || !manualUrl) return;
    setActionLoading(true);
    setError(null);
    try {
      const cand = await submitManualCandidate(selectedInvId, activePlan.id, {
        url: manualUrl.trim(),
        title: manualTitle.trim() || undefined,
        snippet: manualSnippet.trim() || undefined,
      });
      setCandidates([cand, ...candidates]);
      setManualUrl("");
      setManualTitle("");
      setManualSnippet("");
    } catch (err: any) {
      setError(err.message || "Failed to submit candidate URL");
    } finally {
      setActionLoading(false);
    }
  };

  // Review candidate URL (Gate 1)
  const handleReviewCandidate = async (candidateId: string, action: "APPROVE" | "REJECT") => {
    if (!selectedInvId) return;
    setActionLoading(true);
    try {
      const updated = await reviewCandidateSource(selectedInvId, candidateId, action);
      setCandidates(candidates.map((c) => (c.id === candidateId ? updated : c)));
    } catch (err: any) {
      setError(err.message || "Failed to review candidate");
    } finally {
      setActionLoading(false);
    }
  };

  // Evaluate Gap (PROPOSAL ONLY)
  const handleEvaluateGap = async () => {
    if (!selectedInvId || !selectedGap) return;
    setActionLoading(true);
    setError(null);
    try {
      const reassess = await evaluateGap(selectedInvId, selectedGap.gap_id);
      setActiveReassessment(reassess);
      setAnalystFinalState(reassess.proposed_resolution_state);
      setAnalystNotes(`Analyst evaluated evidence claims against verification criteria for '${selectedGap.requirement_title}'.`);
    } catch (err: any) {
      setError(err.message || "Failed to evaluate gap");
    } finally {
      setActionLoading(false);
    }
  };

  // Commit Reassessment (Gate 2 - Sign off)
  const handleCommitReassessment = async () => {
    if (!selectedInvId || !activeReassessment) return;
    if (!analystNotes.trim()) {
      setError("Mandatory reviewer notes are required before committing a verification decision.");
      return;
    }
    setActionLoading(true);
    setError(null);
    try {
      const committed = await commitGapReassessment(selectedInvId, activeReassessment.id, {
        analyst_decision: analystDecision,
        analyst_final_state: analystFinalState,
        analyst_notes: analystNotes.trim(),
        analyst_id: "Forensic Analyst",
      });
      setActiveReassessment(committed);
      // Refresh queue
      const qRes = await getNavigatorQueue(selectedInvId);
      setQueueData(qRes);
      // Refresh audit
      const aud = await getNavigatorAuditTrail(selectedInvId);
      setAuditLog(aud);
    } catch (err: any) {
      setError(err.message || "Failed to commit reassessment");
    } finally {
      setActionLoading(false);
    }
  };

  const handleCopyQuery = (query: string) => {
    navigator.clipboard.writeText(query);
    setCopiedQuery(query);
    setTimeout(() => setCopiedQuery(null), 2500);
  };

  const selectedInv = investigations.find((i) => i.id === selectedInvId);

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-16 font-sans">
      {/* 1. Header & Investigation Selector */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-5">
        <div>
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-lg bg-sky-950/60 border border-sky-800/60 text-sky-400 shadow-sm">
              <Compass className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-xl font-bold text-slate-100 tracking-tight">Verification Navigator & Update Orchestrator</h1>
                <span className="text-xs px-2 py-0.5 rounded font-mono font-medium bg-indigo-950/80 text-indigo-300 border border-indigo-800/80">
                  Evidence Verification
                </span>
                {loading && (
                  <span className="text-[10px] px-2 py-0.5 rounded font-mono text-slate-400 bg-slate-800 animate-pulse">
                    Loading...
                  </span>
                )}
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                {selectedInv?.research_question ? (
                  <span className="text-slate-300 font-medium">"{selectedInv.research_question}" • </span>
                ) : null}
                Search for evidence to close missing gaps and review how new sources affect your decision.
              </p>
            </div>
          </div>
        </div>

        {/* Investigation Selector */}
        <div className="flex items-center gap-2.5">
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
        </div>
      </div>

      {/* Error Callout */}
      {error && (
        <div className="p-4 rounded-lg bg-rose-950/40 border border-rose-800/60 text-rose-300 text-xs flex items-start gap-3">
          <AlertTriangle className="w-4 h-4 text-rose-400 mt-0.5 shrink-0" />
          <div className="flex-1">
            <p className="font-semibold text-rose-200">Execution Notice</p>
            <p className="mt-0.5 text-rose-300/90 font-mono">{error}</p>
          </div>
        </div>
      )}

      {/* 2. Top-Level Tab Navigation */}
      <div className="flex items-center gap-2 border-b border-slate-800">
        <button
          onClick={() => setActiveTab("queue")}
          className={`px-4 py-2.5 text-xs font-mono font-medium border-b-2 flex items-center gap-2 transition ${
            activeTab === "queue"
              ? "border-sky-500 text-sky-400 bg-sky-950/20"
              : "border-transparent text-slate-400 hover:text-slate-200"
          }`}
        >
          <Search className="w-3.5 h-3.5" />
          Workflow A: Gap Verification Queue ({queueData?.total_gaps || 0})
        </button>

        <button
          onClick={() => setActiveTab("impacts")}
          className={`px-4 py-2.5 text-xs font-mono font-medium border-b-2 flex items-center gap-2 transition ${
            activeTab === "impacts"
              ? "border-sky-500 text-sky-400 bg-sky-950/20"
              : "border-transparent text-slate-400 hover:text-slate-200"
          }`}
        >
          <Zap className="w-3.5 h-3.5" />
          Workflow B: Source Impact Feed ({impactSummaries.length})
        </button>

        <button
          onClick={() => setActiveTab("audit")}
          className={`px-4 py-2.5 text-xs font-mono font-medium border-b-2 flex items-center gap-2 transition ${
            activeTab === "audit"
              ? "border-sky-500 text-sky-400 bg-sky-950/20"
              : "border-transparent text-slate-400 hover:text-slate-200"
          }`}
        >
          <Clock className="w-3.5 h-3.5" />
          Orchestration Audit Log ({auditLog.length})
        </button>
      </div>

      {/* 3. TAB 1: WORKFLOW A — GAP VERIFICATION STUDIO */}
      {activeTab === "queue" && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          {/* Left Column: Gap Queue (5 cols) */}
          <div className="lg:col-span-5 space-y-3">
            <div className="flex items-center justify-between text-xs text-slate-400 mb-1">
              <span className="font-semibold text-slate-300">Unresolved Negative-Space Gaps</span>
              <span className="font-mono text-[11px] text-slate-500">Sorted by Projected DFI Impact</span>
            </div>

            {queueData?.queue && queueData.queue.length > 0 ? (
              <div className="space-y-2.5 max-h-[750px] overflow-y-auto pr-1">
                {queueData.queue.map((item) => {
                  const isSelected = selectedGap?.gap_id === item.gap_id;
                  return (
                    <div
                      key={item.gap_id}
                      onClick={() => {
                        setSelectedGap(item);
                        setActivePlan(null);
                        setCandidates([]);
                        setActiveReassessment(null);
                      }}
                      className={`p-3.5 rounded-xl border cursor-pointer transition text-left ${
                        isSelected
                          ? "bg-slate-900 border-sky-500/80 shadow-md ring-1 ring-sky-500/40"
                          : "bg-slate-900/40 border-slate-800 hover:border-slate-700 hover:bg-slate-900/60"
                      }`}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <span
                          className={`text-[10px] font-mono font-semibold px-2 py-0.5 rounded border ${
                            item.priority === "CRITICAL"
                              ? "bg-rose-950/80 text-rose-300 border-rose-800/80"
                              : item.priority === "HIGH"
                              ? "bg-orange-950/80 text-orange-300 border-orange-800/80"
                              : "bg-amber-950/80 text-amber-300 border-amber-800/80"
                          }`}
                        >
                          {item.priority}
                        </span>

                        <span className="text-[10px] font-mono font-semibold px-2 py-0.5 rounded bg-emerald-950/80 text-emerald-300 border border-emerald-800/80">
                          -{item.projected_dfi_reduction.toFixed(1)} DFI
                        </span>
                      </div>

                      <h4 className="text-xs font-bold text-slate-200 mt-2 line-clamp-1">
                        {item.requirement_title}
                      </h4>

                      <p className="text-[11px] text-slate-400 mt-1 line-clamp-2 leading-relaxed">
                        {item.gap_description}
                      </p>

                      <div className="mt-2.5 pt-2 border-t border-slate-800/80 flex items-center justify-between text-[10px] font-mono text-slate-500">
                        <span>Status: <code className="text-slate-300">{item.current_coverage_status}</code></span>
                        <span className="text-sky-400 font-medium">{item.verification_state}</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="p-8 rounded-xl bg-slate-900/40 border border-slate-800 text-center text-slate-400 text-xs font-mono">
                Zero unresolved evidence gaps recorded. All contract requirements show complete sufficiency.
              </div>
            )}
          </div>

          {/* Right Column: Active Gap Workspace (7 cols) */}
          <div className="lg:col-span-7 space-y-4">
            {selectedGap ? (
              <div className="p-5 rounded-2xl bg-slate-900/80 border border-slate-800 space-y-5">
                {/* Active Gap Header */}
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-sky-950 text-sky-300 border border-sky-800/80 font-bold uppercase">
                      Target Gap Under Verification
                    </span>
                    <span className="text-[10px] font-mono text-slate-400">{selectedGap.gap_id.slice(0, 8)}</span>
                  </div>
                  <h3 className="text-sm font-bold text-slate-100 mt-1.5">{selectedGap.requirement_title}</h3>
                  <p className="text-xs text-slate-300 mt-1 leading-relaxed bg-slate-950/60 p-3 rounded-lg border border-slate-800/80">
                    <span className="text-slate-400 font-semibold block mb-0.5">Missing Evidentiary Predicate:</span>
                    {selectedGap.evidence_needed}
                  </p>
                </div>

                {/* Search Provider Status & Custom Analyst Directives Banner */}
                <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800 text-xs space-y-2.5">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2.5">
                      <div className="w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
                      <div>
                        <span className="text-slate-300 font-semibold block text-[11px]">
                          Autonomous Search Provider: UNAVAILABLE
                        </span>
                        <span className="text-slate-500 text-[10px]">
                          Provider set to <code className="text-slate-400 font-mono">none</code>. Dynamic context-driven formulation & manual entry mode active.
                        </span>
                      </div>
                    </div>
                    <Button
                      onClick={handleGeneratePlan}
                      disabled={actionLoading}
                      className="bg-sky-600 hover:bg-sky-500 text-white text-xs px-3 py-1.5 flex items-center gap-1.5 font-medium shrink-0"
                    >
                      <RefreshCw className={`w-3 h-3 ${actionLoading ? "animate-spin" : ""}`} />
                      {activePlan ? "Re-formulate Plan" : "Formulate Plan"}
                    </Button>
                  </div>

                  <div className="pt-2 border-t border-slate-800/80">
                    <label className="text-[11px] font-semibold text-slate-400 block mb-1">
                      Analyst Instructions / Scope Focus (Optional):
                    </label>
                    <input
                      type="text"
                      placeholder="e.g. Focus on specific audit disclosures or regulatory telemetry"
                      value={customInstructions}
                      onChange={(e) => setCustomInstructions(e.target.value)}
                      className="w-full bg-slate-900 border border-slate-800 text-slate-200 text-xs rounded-lg px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-sky-500 font-mono placeholder:text-slate-600"
                    />
                  </div>
                </div>

                {/* Formulated Search Strategy & Dynamic Queries */}
                {activePlan && (
                  <div className="p-4 rounded-xl bg-slate-950/80 border border-slate-800 space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-[11px] font-bold text-slate-300 uppercase tracking-wide">
                        Formulated Verification Queries
                      </span>
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-300">
                        Target Tier: {activePlan.target_authority_tier}
                      </span>
                    </div>

                    {activePlan.missing_context_warning && (
                      <div className="p-2.5 rounded-lg bg-amber-950/40 border border-amber-800/80 text-amber-300 text-xs flex items-start gap-2">
                        <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                        <div>
                          <span className="font-semibold block text-[11px]">Context Limitation</span>
                          <span className="text-[10px] text-amber-200/90">{activePlan.missing_context_warning}</span>
                        </div>
                      </div>
                    )}

                    <p className="text-[11px] text-slate-400 leading-relaxed">
                      Queries generated dynamically from live requirement and gap parameters. You can edit queries inline, remove them, or add custom manual queries:
                    </p>

                    <div className="space-y-1.5">
                      {activePlan.search_queries.map((q, idx) => (
                        <div
                          key={idx}
                          className="flex items-center justify-between gap-2 p-2 rounded-lg bg-slate-900 border border-slate-800 text-xs font-mono text-slate-300"
                        >
                          {editingQueryIdx === idx ? (
                            <div className="flex items-center gap-1.5 flex-1">
                              <input
                                type="text"
                                value={editingQueryText}
                                onChange={(e) => setEditingQueryText(e.target.value)}
                                className="flex-1 bg-slate-950 border border-sky-500 text-slate-100 px-2 py-1 rounded text-xs focus:outline-none font-mono"
                                autoFocus
                              />
                              <button
                                onClick={() => handleSaveEditedQuery(idx)}
                                disabled={isSavingQueries || !editingQueryText.trim()}
                                className="p-1 rounded bg-sky-600 hover:bg-sky-500 text-white transition"
                                title="Save changes"
                              >
                                <Check className="w-3.5 h-3.5" />
                              </button>
                              <button
                                onClick={() => {
                                  setEditingQueryIdx(null);
                                  setEditingQueryText("");
                                }}
                                className="p-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-slate-200 transition"
                                title="Cancel edit"
                              >
                                <X className="w-3.5 h-3.5" />
                              </button>
                            </div>
                          ) : (
                            <>
                              <span className="truncate flex-1">{q}</span>
                              <div className="flex items-center gap-1 shrink-0">
                                <button
                                  onClick={() => handleCopyQuery(q)}
                                  className="p-1 rounded hover:bg-slate-800 text-slate-400 hover:text-slate-200 transition"
                                  title="Copy query"
                                >
                                  <Copy className="w-3.5 h-3.5" />
                                </button>
                                <button
                                  onClick={() => {
                                    setEditingQueryIdx(idx);
                                    setEditingQueryText(q);
                                  }}
                                  className="p-1 rounded hover:bg-slate-800 text-slate-400 hover:text-sky-300 transition"
                                  title="Edit query"
                                >
                                  <Edit2 className="w-3.5 h-3.5" />
                                </button>
                                <button
                                  onClick={() => handleDeleteQuery(idx)}
                                  disabled={isSavingQueries || activePlan.search_queries.length <= 1}
                                  className="p-1 rounded hover:bg-slate-800 text-slate-400 hover:text-rose-400 transition disabled:opacity-30 disabled:hover:text-slate-400"
                                  title={activePlan.search_queries.length <= 1 ? "At least one query required" : "Delete query"}
                                >
                                  <Trash2 className="w-3.5 h-3.5" />
                                </button>
                              </div>
                            </>
                          )}
                        </div>
                      ))}
                      {copiedQuery && (
                        <p className="text-[10px] text-emerald-400 font-mono text-right">Query copied to clipboard!</p>
                      )}
                    </div>

                    {/* Manual Custom Query Addition Form */}
                    <form onSubmit={handleAddManualQuery} className="pt-2 border-t border-slate-800/80 flex items-center gap-2">
                      <input
                        type="text"
                        placeholder="Type custom verification query..."
                        value={newManualQuery}
                        onChange={(e) => setNewManualQuery(e.target.value)}
                        className="bg-slate-900 border border-slate-800 text-slate-200 text-xs rounded-lg px-3 py-1.5 font-mono flex-1 focus:outline-none focus:ring-1 focus:ring-sky-500 placeholder:text-slate-600"
                      />
                      <Button
                        type="submit"
                        disabled={isSavingQueries || !newManualQuery.trim()}
                        className="bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs px-3 py-1.5 font-medium shrink-0"
                      >
                        <Plus className="w-3.5 h-3.5 mr-1" />
                        Add Query
                      </Button>
                    </form>

                    {/* Manual URL Submission Form */}
                    <form onSubmit={handleAddCandidate} className="pt-2 border-t border-slate-800/80 space-y-2">
                      <span className="text-[11px] font-bold text-slate-300 block">Submit Candidate Source URL for Triage</span>
                      <div className="flex items-center gap-2">
                        <input
                          type="url"
                          required
                          placeholder="https://example.gov/filing.pdf"
                          value={manualUrl}
                          onChange={(e) => setManualUrl(e.target.value)}
                          className="bg-slate-900 border border-slate-700/80 text-slate-200 text-xs rounded-lg px-3 py-2 font-mono flex-1 focus:outline-none focus:ring-1 focus:ring-sky-500"
                        />
                        <Button
                          type="submit"
                          disabled={actionLoading || !manualUrl}
                          className="bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs px-3.5 py-2 font-medium"
                        >
                          <Plus className="w-3.5 h-3.5 mr-1" />
                          Submit Candidate
                        </Button>
                      </div>
                    </form>
                  </div>
                )}

                {/* Candidate Review (HITL Gate 1) */}
                {candidates.length > 0 && (
                  <div className="p-4 rounded-xl bg-slate-950/80 border border-slate-800 space-y-3">
                    <span className="text-[11px] font-bold text-slate-300 uppercase tracking-wide block">
                      Candidate Triage Queue (HITL Gate 1)
                    </span>

                    <div className="space-y-2">
                      {candidates.map((cand) => (
                        <div key={cand.id} className="p-3 rounded-lg bg-slate-900 border border-slate-800 space-y-2">
                          <div className="flex items-center justify-between text-xs">
                            <span className="font-semibold text-slate-200 truncate max-w-sm">{cand.title}</span>
                            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-300">
                              {cand.authority_tier}
                            </span>
                          </div>
                          <p className="text-[11px] text-slate-400 truncate font-mono">{cand.url}</p>
                          <p className="text-[10px] text-slate-500 leading-relaxed">{cand.snippet}</p>

                          <div className="flex items-center justify-between pt-1">
                            <span className="text-[10px] font-mono text-slate-400">
                              Relevance: <code className="text-sky-300 font-semibold">{cand.relevance_score.toFixed(1)}/100</code>
                            </span>
                            {cand.review_status === "PENDING_REVIEW" ? (
                              <div className="flex items-center gap-2">
                                <Button
                                  onClick={() => handleReviewCandidate(cand.id, "APPROVE")}
                                  disabled={actionLoading}
                                  className="bg-emerald-600 hover:bg-emerald-500 text-white text-[11px] px-2.5 py-1 font-medium"
                                >
                                  Approve for Ingestion
                                </Button>
                                <Button
                                  onClick={() => handleReviewCandidate(cand.id, "REJECT")}
                                  disabled={actionLoading}
                                  className="bg-slate-800 hover:bg-slate-700 text-rose-300 text-[11px] px-2.5 py-1 font-medium"
                                >
                                  Reject
                                </Button>
                              </div>
                            ) : (
                              <span
                                className={`text-[10px] font-mono px-2 py-0.5 rounded font-semibold ${
                                  cand.review_status === "APPROVED"
                                    ? "bg-emerald-950 text-emerald-300 border border-emerald-800"
                                    : "bg-rose-950 text-rose-300 border border-rose-800"
                                }`}
                              >
                                {cand.review_status}
                              </span>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Forensic Reassessment (HITL Gate 2) */}
                <div className="p-4 rounded-xl bg-slate-950/80 border border-slate-800 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] font-bold text-slate-300 uppercase tracking-wide">
                      Forensic Gap Reassessment (HITL Gate 2)
                    </span>
                    <Button
                      onClick={handleEvaluateGap}
                      disabled={actionLoading}
                      className="bg-sky-600 hover:bg-sky-500 text-white text-xs px-3 py-1 font-medium"
                    >
                      Compute Proposed Reassessment
                    </Button>
                  </div>

                  {activeReassessment ? (
                    <div className="space-y-3 pt-2">
                      <div className="p-3.5 rounded-lg bg-slate-900 border border-slate-800 space-y-2">
                        <div className="flex items-center justify-between text-xs">
                          <span className="text-slate-400">Proposed Resolution State:</span>
                          <span
                            className={`font-mono font-bold px-2 py-0.5 rounded text-[11px] ${
                              activeReassessment.proposed_resolution_state === "RESOLVED"
                                ? "bg-emerald-950 text-emerald-300 border border-emerald-700"
                                : activeReassessment.proposed_resolution_state === "PARTIALLY_ADDRESSED"
                                ? "bg-amber-950 text-amber-300 border border-amber-700"
                                : "bg-slate-800 text-slate-300 border border-slate-700"
                            }`}
                          >
                            {activeReassessment.proposed_resolution_state}
                          </span>
                        </div>

                        <div className="grid grid-cols-2 gap-2 text-[11px] font-mono text-slate-400 pt-1">
                          <div>
                            Predicate Match: <code className="text-slate-200">{activeReassessment.predicate_fulfillment_score.toFixed(1)}/100</code>
                          </div>
                          <div>
                            Evidence Score: <code className="text-slate-200">{activeReassessment.composite_evidence_score.toFixed(1)}/100</code>
                          </div>
                        </div>

                        <div className="p-2.5 rounded bg-rose-950/30 border border-rose-800/60 text-rose-300 text-[11px] leading-relaxed">
                          <span className="font-semibold block mb-0.5">Mandatory Epistemic Safeguard:</span>
                          The system never automatically marks a gap RESOLVED. The proposed state represents an empirical recommendation requiring your explicit sign-off.
                        </div>
                      </div>

                      {/* Sign-off Form */}
                      <div className="p-3.5 rounded-lg bg-slate-900 border border-slate-800 space-y-2.5">
                        <span className="text-xs font-bold text-slate-200 block">Analyst Decision & Forensic Notes</span>
                        <div className="grid grid-cols-2 gap-2 text-xs">
                          <div>
                            <label className="text-[10px] text-slate-400 block mb-1">Decision</label>
                            <select
                              value={analystDecision}
                              onChange={(e) => setAnalystDecision(e.target.value)}
                              className="bg-slate-900 border border-slate-700 text-slate-100 text-xs rounded p-1.5 w-full font-mono cursor-pointer"
                            >
                              <option value="APPROVED" className="bg-slate-900 text-slate-100">APPROVE Proposed State</option>
                              <option value="OVERRIDDEN" className="bg-slate-900 text-slate-100">OVERRIDE to Different State</option>
                              <option value="REJECTED" className="bg-slate-900 text-slate-100">REJECT Resolution</option>
                            </select>
                          </div>
                          <div>
                            <label className="text-[10px] text-slate-400 block mb-1">Effective Final State</label>
                            <select
                              value={analystFinalState}
                              onChange={(e) => setAnalystFinalState(e.target.value)}
                              className="bg-slate-900 border border-slate-700 text-slate-100 text-xs rounded p-1.5 w-full font-mono cursor-pointer"
                            >
                              <option value="RESOLVED" className="bg-slate-900 text-slate-100">RESOLVED</option>
                              <option value="PARTIALLY_ADDRESSED" className="bg-slate-900 text-slate-100">PARTIALLY_ADDRESSED</option>
                              <option value="UNCHANGED" className="bg-slate-900 text-slate-100">UNCHANGED</option>
                              <option value="WORSENED" className="bg-slate-900 text-slate-100">WORSENED</option>
                            </select>
                          </div>
                        </div>

                        <div>
                          <label className="text-[10px] text-slate-400 block mb-1">Forensic Sign-off Notes (Mandatory)</label>
                          <textarea
                            rows={2}
                            required
                            value={analystNotes}
                            onChange={(e) => setAnalystNotes(e.target.value)}
                            placeholder="Enter justification for this resolution decision..."
                            className="bg-slate-950 border border-slate-700 text-slate-200 text-xs rounded p-2 w-full font-sans focus:outline-none focus:ring-1 focus:ring-sky-500"
                          />
                        </div>

                        <Button
                          onClick={handleCommitReassessment}
                          disabled={actionLoading || !analystNotes.trim()}
                          className="bg-emerald-600 hover:bg-emerald-500 text-white text-xs px-4 py-2 w-full font-semibold shadow"
                        >
                          Commit Resolution Decision to Database
                        </Button>
                      </div>
                    </div>
                  ) : (
                    <p className="text-[11px] text-slate-500 italic">
                      Click 'Compute Proposed Reassessment' to evaluate newly ingested claims against this gap's criteria.
                    </p>
                  )}
                </div>
              </div>
            ) : (
              <div className="p-12 rounded-2xl bg-slate-900/40 border border-slate-800 text-center text-slate-400 text-xs font-mono">
                Select an unresolved gap from the queue to formulate verification queries and review candidates.
              </div>
            )}
          </div>
        </div>
      )}

      {/* 4. TAB 2: WORKFLOW B — SOURCE IMPACT FEED */}
      {activeTab === "impacts" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <p>
              Every newly ingested source automatically propagates through the 8-stage Central Orchestrator,
              updating requirements, assumptions, contradictions, and Decision Fragility.
            </p>
            <span className="font-mono text-slate-300">
              Summaries Available: {impactSummaries.length}
            </span>
          </div>

          {impactSummaries.length > 0 ? (
            <div className="space-y-4">
              {impactSummaries.map((imp) => (
                <div key={imp.orchestration_run_id} className="p-5 rounded-2xl bg-slate-900 border border-slate-800 space-y-4">
                  {/* Summary Header */}
                  <div className="flex flex-col md:flex-row md:items-center justify-between gap-2 border-b border-slate-800/80 pb-3">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-bold text-slate-200">{imp.source_title}</span>
                        <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
                          {imp.authority_tier}
                        </span>
                        {imp.is_duplicate && (
                          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-950 text-amber-300 border border-amber-800">
                            Duplicate Skipped
                          </span>
                        )}
                      </div>
                      <p className="text-[11px] text-slate-400 font-mono mt-0.5 truncate">{imp.source_url_or_filename}</p>
                    </div>

                    <div className="flex items-center gap-3">
                      <div className="text-right">
                        <span className="text-[10px] text-slate-500 font-mono block">DFI Shift</span>
                        <span
                          className={`text-xs font-bold font-mono ${
                            imp.delta_dfi < 0 ? "text-emerald-400" : imp.delta_dfi > 0 ? "text-rose-400" : "text-slate-300"
                          }`}
                        >
                          {imp.old_dfi_score.toFixed(1)} → {imp.new_dfi_score.toFixed(1)} ({imp.delta_dfi > 0 ? `+${imp.delta_dfi.toFixed(1)}` : imp.delta_dfi.toFixed(1)})
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Impact Matrix Grid */}
                  <div className="grid grid-cols-1 md:grid-cols-4 gap-3 text-xs">
                    <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800/80">
                      <span className="text-[10px] text-slate-400 block font-mono">Claims Extracted</span>
                      <span className="text-base font-bold text-slate-200 mt-1 block">{imp.total_claims_extracted}</span>
                      <span className="text-[10px] text-slate-500">
                        {Object.entries(imp.claims_by_category || {}).map(([k, v]) => `${v} ${k}`).join(", ")}
                      </span>
                    </div>

                    <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800/80">
                      <span className="text-[10px] text-slate-400 block font-mono">Requirements Affected</span>
                      <span className="text-base font-bold text-slate-200 mt-1 block">{(imp.affected_requirements || []).length}</span>
                      <span className="text-[10px] text-emerald-400">
                        {(imp.gaps_resolved || []).length} Proposed Resolved
                      </span>
                    </div>

                    <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800/80">
                      <span className="text-[10px] text-slate-400 block font-mono">Assumptions Affected</span>
                      <span className="text-base font-bold text-slate-200 mt-1 block">{(imp.affected_assumptions || []).length}</span>
                      <span className="text-[10px] text-slate-400">Validation preserved</span>
                    </div>

                    <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800/80">
                      <span className="text-[10px] text-slate-400 block font-mono">Contradictions</span>
                      <span className="text-base font-bold text-slate-200 mt-1 block">{(imp.new_conflicts_detected || []).length}</span>
                      <span className="text-[10px] text-slate-500">Cross-examined in C05</span>
                    </div>
                  </div>

                  {/* Stage-by-Stage Selective Orchestrator Audit */}
                  <div className="space-y-1.5 pt-1">
                    <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wide font-mono block">
                      Selective Orchestration Stage Breakdown
                    </span>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-[10px] font-mono">
                      {Object.entries(imp.stages_execution).map(([stage, rec]) => (
                        <div
                          key={stage}
                          className={`p-2 rounded border ${
                            rec.status === "COMPLETED"
                              ? "bg-slate-950/80 border-slate-800 text-slate-300"
                              : rec.status === "NOT_AFFECTED"
                              ? "bg-slate-950/40 border-slate-800/50 text-slate-500"
                              : "bg-rose-950/30 border-rose-800 text-rose-300"
                          }`}
                        >
                          <div className="flex items-center justify-between">
                            <span className="font-bold">{stage.replace("STAGE_", "S")}</span>
                            <span className={rec.status === "COMPLETED" ? "text-emerald-400" : "text-slate-500"}>
                              {rec.status}
                            </span>
                          </div>
                          {rec.skipped_reason && (
                            <p className="text-[9px] text-slate-500 mt-0.5 line-clamp-1">{rec.skipped_reason}</p>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* AI Forensic Synthesis Box */}
                  <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800 text-xs text-slate-300 leading-relaxed font-sans">
                    <span className="text-[10px] font-bold text-purple-400 uppercase font-mono block mb-1">
                      Orchestrator Forensic Narrative (Grounded in Verified Evidence)
                    </span>
                    {imp.executive_impact_narrative}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="p-12 rounded-2xl bg-slate-900/40 border border-slate-800 text-center text-slate-400 text-xs font-mono">
              Zero sources integrated yet. Add a URL or PDF to observe automatic investigation-wide orchestration.
            </div>
          )}
        </div>
      )}

      {/* 5. TAB 3: AUDIT LEDGER */}
      {activeTab === "audit" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <p>Immutable, append-only verification and orchestration audit trail.</p>
            <span className="font-mono text-slate-300">Total Events: {auditLog.length}</span>
          </div>

          {auditLog.length > 0 ? (
            <div className="overflow-x-auto rounded-xl border border-slate-800">
              <table className="w-full text-left text-xs text-slate-300">
                <thead className="bg-slate-900/80 text-[10px] font-mono text-slate-400 uppercase border-b border-slate-800">
                  <tr>
                    <th className="py-2.5 px-3">Timestamp</th>
                    <th className="py-2.5 px-3">Event Type</th>
                    <th className="py-2.5 px-3">Actor</th>
                    <th className="py-2.5 px-3">Audit Details</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/80 font-mono text-[11px]">
                  {auditLog.map((log) => (
                    <tr key={log.id} className="hover:bg-slate-900/40">
                      <td className="py-2.5 px-3 text-slate-400 whitespace-nowrap">{log.created_at.slice(0, 19).replace("T", " ")}</td>
                      <td className="py-2.5 px-3 text-sky-400 font-semibold">{log.event_type}</td>
                      <td className="py-2.5 px-3 text-slate-300">{log.actor}</td>
                      <td className="py-2.5 px-3 text-slate-400 truncate max-w-md">{JSON.stringify(log.details)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="p-12 rounded-2xl bg-slate-900/40 border border-slate-800 text-center text-slate-400 text-xs font-mono">
              Zero audit events recorded yet.
            </div>
          )}
        </div>
      )}
    </div>
  );
}
