import { useState, useEffect } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import {
  listInvestigations,
  getDecisionContract,
  compileDecisionContract,
  recompileDecisionContract,
  updateDecisionContract,
  Investigation,
  DecisionContract,
  Requirement,
} from "@/lib/api";
import {
  FileCheck2,
  RefreshCw,
  Save,
  Download,
  AlertCircle,
  HelpCircle,
  CheckCircle2,
  Layers,
  Search,
  PlusCircle,
  ChevronRight,
  Shield,
  Edit3,
  Scale,
  Sparkles,
} from "lucide-react";

export function DecisionContractPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();

  // State
  const [investigations, setInvestigations] = useState<Investigation[]>([]);
  const [selectedInvId, setSelectedInvId] = useState<string | null>(null);
  const [contract, setContract] = useState<DecisionContract | null>(null);

  const [isLoading, setIsLoading] = useState(false);
  const [isCompiling, setIsCompiling] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successBanner, setSuccessBanner] = useState<string | null>(null);

  // Editable local state
  const [editObjective, setEditObjective] = useState("");
  const [editScope, setEditScope] = useState("");
  const [isEditingHeader, setIsEditingHeader] = useState(false);

  // Selected investigation details
  const activeInvestigation = investigations.find((i) => i.id === selectedInvId);

  // 1. Fetch investigations list on mount
  useEffect(() => {
    let isMounted = true;
    listInvestigations()
      .then((data) => {
        if (!isMounted) return;
        setInvestigations(data);
        const urlId = searchParams.get("invId");
        if (urlId && data.some((i) => i.id === urlId)) {
          setSelectedInvId(urlId);
        } else if (data.length > 0) {
          setSelectedInvId(data[0].id);
        }
      })
      .catch((err) => {
        console.error("Failed to load investigations list", err);
      });
    return () => {
      isMounted = false;
    };
  }, [searchParams]);

  // 2. Fetch contract when selected investigation changes
  useEffect(() => {
    if (!selectedInvId) {
      setContract(null);
      return;
    }

    setIsLoading(true);
    setErrorMessage(null);
    setSuccessBanner(null);

    getDecisionContract(selectedInvId)
      .then((c) => {
        setContract(c);
        setEditObjective(c.decision_objective);
        setEditScope(c.scope || "");
      })
      .catch(() => {
        // Contract not compiled yet for this investigation
        setContract(null);
      })
      .finally(() => {
        setIsLoading(false);
      });
  }, [selectedInvId]);

  // Handle Switch Investigation
  const handleSelectInvestigation = (id: string) => {
    setSelectedInvId(id);
    setSearchParams({ invId: id });
    setIsEditingHeader(false);
  };

  // Compile Contract
  const handleCompile = async () => {
    if (!selectedInvId) return;
    setIsCompiling(true);
    setErrorMessage(null);
    try {
      const compiled = await compileDecisionContract(selectedInvId);
      setContract(compiled);
      setEditObjective(compiled.decision_objective);
      setEditScope(compiled.scope || "");
      setSuccessBanner("Decision Contract compiled successfully from research hypothesis.");
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to compile contract.");
    } finally {
      setIsCompiling(false);
    }
  };

  // Recompile Contract
  const handleRecompile = async () => {
    if (!selectedInvId) return;
    setIsCompiling(true);
    setErrorMessage(null);
    try {
      const recompiled = await recompileDecisionContract(selectedInvId);
      setContract(recompiled);
      setEditObjective(recompiled.decision_objective);
      setEditScope(recompiled.scope || "");
      setIsEditingHeader(false);
      setSuccessBanner("Contract recompiled in place against inquiry parameters.");
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to recompile contract.");
    } finally {
      setIsCompiling(false);
    }
  };

  // Save Edits to Contract
  const handleSaveChanges = async () => {
    if (!selectedInvId || !contract) return;
    setIsSaving(true);
    setErrorMessage(null);
    try {
      const updated = await updateDecisionContract(selectedInvId, {
        decision_objective: editObjective,
        scope: editScope,
        requirements: contract.requirements,
        constraints: contract.constraints,
        assumptions: contract.assumptions,
        unresolved_questions: contract.unresolved_questions,
      });
      setContract(updated);
      setIsEditingHeader(false);
      setSuccessBanner("Decision Contract modifications saved to database.");
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to save contract changes.");
    } finally {
      setIsSaving(false);
    }
  };

  // Export Contract JSON
  const handleExportJSON = () => {
    if (!contract) return;
    const jsonStr = JSON.stringify(contract, null, 2);
    const blob = new Blob([jsonStr], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `decision_contract_${contract.investigation_id.substring(0, 8)}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // Helper for requirement badge color
  const getReqTypeVariant = (type: Requirement["requirement_type"]) => {
    switch (type) {
      case "CAUSAL":
        return "conflict";
      case "QUANTITATIVE":
      case "COMPARATIVE":
        return "info";
      case "ELIGIBILITY":
      case "IMPLEMENTATION":
        return "supported";
      case "RISK":
        return "gap";
      default:
        return "neutral";
    }
  };

  const getPriorityVariant = (priority: Requirement["priority"]) => {
    switch (priority) {
      case "CRITICAL":
        return "conflict";
      case "HIGH":
        return "gap";
      case "MEDIUM":
        return "info";
      default:
        return "neutral";
    }
  };

  return (
    <div className="space-y-8 max-w-6xl mx-auto">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-4 border-b border-brand-border/60">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-brand-text">
            Decision Criteria
          </h1>
          <p className="text-xs sm:text-sm text-brand-textMuted mt-1">
            Define what you need to decide, required evidence, and key assumptions before evaluating sources.
          </p>
        </div>

        {/* Global Contract Action Buttons */}
        {contract && (
          <div className="flex flex-wrap items-center gap-2.5">
            <Button
              variant="outline"
              size="sm"
              onClick={handleRecompile}
              isLoading={isCompiling}
              leftIcon={<RefreshCw className="w-3.5 h-3.5" />}
              title="Re-run compiler against research question"
            >
              Regenerate
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={handleExportJSON}
              leftIcon={<Download className="w-3.5 h-3.5" />}
              title="Download Contract JSON"
            >
              Export JSON
            </Button>
            <Button
              variant="primary"
              size="sm"
              onClick={handleSaveChanges}
              isLoading={isSaving}
              leftIcon={<Save className="w-3.5 h-3.5" />}
              className="shadow-glow-blue"
            >
              Save Changes
            </Button>
          </div>
        )}
      </div>

      {/* Investigation Selector Bar */}
      <div className="rounded-xl border border-brand-border bg-brand-surface p-4 shadow-subtle flex flex-col md:flex-row md:items-center justify-between gap-3">
        <div className="flex items-center gap-2.5 min-w-0">
          <Layers className="w-4 h-4 text-brand-teal shrink-0" />
          <span className="text-xs font-semibold text-brand-text font-mono uppercase tracking-wider shrink-0">
            Target Investigation:
          </span>

          {investigations.length === 0 ? (
            <span className="text-xs text-brand-textDim italic">
              No investigations recorded in database
            </span>
          ) : (
            <select
              value={selectedInvId || ""}
              onChange={(e) => handleSelectInvestigation(e.target.value)}
              className="rounded-md border border-slate-700 bg-slate-900 px-3 py-1.5 text-xs text-slate-100 font-medium focus:border-brand-accent focus:outline-none max-w-md truncate cursor-pointer shadow-sm"
            >
              {investigations.map((inv) => (
                <option key={inv.id} value={inv.id} className="bg-slate-900 text-slate-100 py-1.5">
                  {inv.research_question} ({inv.has_contract ? "Compiled" : "Awaiting Compilation"})
                </option>
              ))}
            </select>
          )}
        </div>

        <div className="flex items-center gap-3 shrink-0">
          <Button
            size="xs"
            variant="ghost"
            onClick={() => navigate("/investigations")}
            leftIcon={<PlusCircle className="w-3.5 h-3.5" />}
          >
            Create New Inquiry
          </Button>
        </div>
      </div>

      {/* Alerts */}
      {errorMessage && (
        <div className="p-3.5 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-start gap-2.5 animate-fade-in">
          <AlertCircle className="w-4 h-4 shrink-0 mt-0.5 text-rose-400" />
          <div className="leading-relaxed">{errorMessage}</div>
        </div>
      )}

      {successBanner && (
        <div className="p-3.5 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-xs flex items-center justify-between gap-2.5 animate-fade-in">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-400" />
            <span>{successBanner}</span>
          </div>
          <button
            onClick={() => setSuccessBanner(null)}
            className="text-emerald-400 hover:text-emerald-200 text-xs cursor-pointer"
          >
            ✕
          </button>
        </div>
      )}

      {/* Loading State */}
      {isLoading && (
        <div className="rounded-xl border border-brand-border bg-brand-surface p-12 text-center flex flex-col items-center justify-center space-y-2">
          <RefreshCw className="w-6 h-6 animate-spin text-brand-accent" />
          <span className="text-xs font-mono text-brand-textDim">
            Retrieving Decision Contract records from SQLite...
          </span>
        </div>
      )}

      {/* Empty State: No Investigation in DB */}
      {!isLoading && investigations.length === 0 && (
        <div className="rounded-xl border border-dashed border-brand-border bg-brand-surface/30 p-12 text-center flex flex-col items-center justify-center">
          <div className="w-12 h-12 rounded-xl bg-[#111B2E] border border-brand-border flex items-center justify-center text-brand-textDim mb-3">
            <Search className="w-6 h-6" />
          </div>
          <h3 className="text-sm font-semibold text-brand-text mb-1">
            No Investigations Available
          </h3>
          <p className="text-xs text-brand-textMuted max-w-md leading-relaxed mb-4">
            A decision contract is compiled from an active research investigation. Launch your
            first investigation to formulate your inquiry.
          </p>
          <Button
            size="sm"
            onClick={() => navigate("/investigations")}
            leftIcon={<PlusCircle className="w-3.5 h-3.5" />}
          >
            Launch First Investigation
          </Button>
        </div>
      )}

      {/* Awaiting Compilation State: Investigation Selected but Contract Not Yet Compiled */}
      {!isLoading && selectedInvId && !contract && investigations.length > 0 && (
        <div className="rounded-xl border border-brand-border bg-brand-surface p-8 sm:p-12 text-center flex flex-col items-center justify-center space-y-4">
          <div className="w-14 h-14 rounded-2xl bg-[#111B2E] border border-brand-border flex items-center justify-center text-brand-teal shadow-elevated">
            <FileCheck2 className="w-7 h-7" />
          </div>

          <div className="space-y-1.5 max-w-xl">
            <h3 className="text-base font-semibold text-brand-text">
              Decision Criteria Not Yet Generated
            </h3>
            <p className="text-xs text-brand-textMuted leading-relaxed">
              Investigation: &ldquo;{activeInvestigation?.research_question}&rdquo;
            </p>
            <p className="text-xs text-brand-textDim leading-relaxed">
              Generate structured decision requirements, evidence needs, scope constraints, and assumptions.
            </p>
          </div>

          <Button
            onClick={handleCompile}
            isLoading={isCompiling}
            size="md"
            leftIcon={<Sparkles className="w-4 h-4" />}
            className="shadow-glow-blue"
          >
            Generate Decision Criteria
          </Button>
        </div>
      )}

      {/* COMPILED CONTRACT WORKSPACE */}
      {!isLoading && contract && (
        <div className="space-y-8 animate-fade-in">
          {/* Section 1: Objective & Scope Card */}
          <div className="rounded-xl border border-brand-border bg-brand-surface p-6 shadow-subtle space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-brand-border/60">
              <div className="flex items-center gap-2">
                <Scale className="w-4 h-4 text-brand-accent" />
                <h2 className="text-sm font-semibold text-brand-text font-mono uppercase tracking-wider">
                  Decision Objective & Scope
                </h2>
              </div>

              <div className="flex items-center gap-2">
                <Badge variant={contract.processing_mode === 'gemini' ? 'info' : 'teal'} size="sm">
                  MODE: {contract.processing_mode === 'gemini' ? 'GEMINI AI' : 'FALLBACK ENGINE'}
                </Badge>
                <Badge variant="neutral" size="sm" className="hidden sm:inline-flex">
                  {contract.compilation_method.toUpperCase()}
                </Badge>
                <span className="text-[11px] font-mono text-brand-textDim hidden md:inline">
                  UPDATED: {contract.updated_at.substring(0, 19).replace("T", " ")} UTC
                </span>
              </div>
            </div>

            {/* Editable or Display View of Objective & Scope */}
            {isEditingHeader ? (
              <div className="space-y-3">
                <div className="space-y-1">
                  <label className="text-[11px] font-mono text-brand-textDim uppercase">
                    Decision Objective:
                  </label>
                  <textarea
                    value={editObjective}
                    onChange={(e) => setEditObjective(e.target.value)}
                    rows={2}
                    className="w-full rounded-md border border-brand-border bg-[#111B2E] p-2.5 text-xs text-brand-text focus:border-brand-accent focus:outline-none"
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-[11px] font-mono text-brand-textDim uppercase">
                    Evaluation Scope Boundary:
                  </label>
                  <input
                    type="text"
                    value={editScope}
                    onChange={(e) => setEditScope(e.target.value)}
                    className="w-full rounded-md border border-brand-border bg-[#111B2E] px-3 py-1.5 text-xs text-brand-text focus:border-brand-accent focus:outline-none"
                  />
                </div>
                <div className="flex items-center justify-end gap-2 pt-1">
                  <Button size="xs" variant="ghost" onClick={() => setIsEditingHeader(false)}>
                    Cancel
                  </Button>
                  <Button size="xs" variant="primary" onClick={handleSaveChanges}>
                    Apply Edits
                  </Button>
                </div>
              </div>
            ) : (
              <div className="space-y-3">
                <div className="p-3.5 rounded-lg bg-[#111B2E] border border-brand-border/80 flex items-start justify-between gap-3">
                  <div className="space-y-1">
                    <div className="text-xs font-semibold text-brand-text leading-relaxed">
                      {contract.decision_objective}
                    </div>
                    <div className="text-[11px] font-mono text-brand-teal">
                      SCOPE: {contract.scope || "Empirical Decision Boundary"}
                    </div>
                  </div>
                  <button
                    onClick={() => setIsEditingHeader(true)}
                    className="text-brand-textDim hover:text-brand-accent p-1 cursor-pointer shrink-0"
                    title="Edit objective"
                  >
                    <Edit3 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Section 2: Decomposed Contract Requirements */}
          <div className="space-y-4">
            <div className="flex items-center justify-between pb-1 border-b border-brand-border/60">
              <div className="flex items-center gap-2">
                <FileCheck2 className="w-4 h-4 text-brand-teal" />
                <h3 className="text-sm font-semibold text-brand-text font-mono uppercase tracking-wider">
                  Decomposed Verification Requirements ({contract.requirements.length})
                </h3>
              </div>
              <span className="text-[11px] font-mono text-brand-textDim">
                Must be independently satisfied
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {contract.requirements.map((req, idx) => (
                <div
                  key={req.requirement_id}
                  className="rounded-lg border border-brand-border bg-brand-surface p-5 shadow-subtle hover:border-slate-600 transition-all space-y-3.5 flex flex-col justify-between"
                >
                  <div className="space-y-2">
                    {/* Header Pills */}
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <span className="flex items-center justify-center w-5 h-5 rounded bg-[#111B2E] border border-brand-border text-brand-accent font-mono text-[11px] font-bold">
                          {idx + 1}
                        </span>
                        <Badge variant={getReqTypeVariant(req.requirement_type)} size="sm">
                          {req.requirement_type}
                        </Badge>
                      </div>

                      <div className="flex items-center gap-1.5">
                        <Badge variant={getPriorityVariant(req.priority)} size="sm">
                          {req.priority}
                        </Badge>
                        <Badge variant="unverified" size="sm">
                          {req.status.toUpperCase()}
                        </Badge>
                      </div>
                    </div>

                    {/* Title & Description */}
                    <h4 className="text-xs font-semibold text-brand-text pt-1">
                      {req.title}
                    </h4>
                    <p className="text-xs text-brand-textMuted leading-relaxed">
                      {req.description}
                    </p>
                  </div>

                  {/* Verification Criteria & Evidence Needed */}
                  <div className="space-y-2 pt-2 border-t border-brand-border/40">
                    <div className="text-[11px] font-mono text-brand-textDim">
                      <span className="text-brand-text font-semibold uppercase">Criteria:</span>{" "}
                      {req.verification_criteria}
                    </div>

                    {/* Evidence Needed Pills */}
                    {req.evidence_needed && req.evidence_needed.length > 0 && (
                      <div className="p-2.5 rounded bg-[#111B2E] border border-brand-border/60 text-[11px] space-y-1">
                        <div className="font-mono text-brand-teal text-[10px] uppercase font-semibold">
                          Required Evidence Artifact:
                        </div>
                        <div className="text-slate-200">
                          {req.evidence_needed[0].evidence_type}
                        </div>
                        <div className="text-[10px] font-mono text-brand-textDim truncate">
                          SOURCES: {req.evidence_needed[0].preferred_source_types.join(", ")}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Section 3: Constraints & Assumptions Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Constraints */}
            <div className="rounded-xl border border-brand-border bg-brand-surface p-5 shadow-subtle space-y-3">
              <div className="flex items-center gap-2 pb-2 border-b border-brand-border/60">
                <Shield className="w-4 h-4 text-brand-accent" />
                <h4 className="text-xs font-semibold text-brand-text font-mono uppercase tracking-wider">
                  Scope Boundaries &amp; Constraints ({contract.constraints.length})
                </h4>
              </div>

              <div className="space-y-2.5">
                {contract.constraints.map((c) => (
                  <div
                    key={c.constraint_id}
                    className="p-3 rounded bg-[#111B2E] border border-brand-border/60 text-xs flex items-start gap-2.5"
                  >
                    <ChevronRight className="w-3.5 h-3.5 text-brand-accent shrink-0 mt-0.5" />
                    <div>
                      <span className="text-slate-200 leading-relaxed">{c.description}</span>
                      <div className="text-[10px] font-mono text-brand-textDim mt-1 uppercase">
                        TYPE: {c.constraint_type}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Assumptions */}
            <div className="rounded-xl border border-brand-border bg-brand-surface p-5 shadow-subtle space-y-3">
              <div className="flex items-center gap-2 pb-2 border-b border-brand-border/60">
                <HelpCircle className="w-4 h-4 text-brand-teal" />
                <h4 className="text-xs font-semibold text-brand-text font-mono uppercase tracking-wider">
                  Working Assumptions ({contract.assumptions.length})
                </h4>
              </div>

              <div className="space-y-2.5">
                {contract.assumptions.map((a) => (
                  <div
                    key={a.assumption_id}
                    className="p-3 rounded bg-[#111B2E] border border-brand-border/60 text-xs flex items-start justify-between gap-2.5"
                  >
                    <div className="space-y-1">
                      <div className="text-slate-200 leading-relaxed">{a.description}</div>
                      <div className="flex items-center gap-2 pt-0.5">
                        <span className="text-[10px] font-mono uppercase px-1.5 py-0.5 rounded bg-brand-bg text-brand-textMuted border border-brand-border/60">
                          {a.source === 'user_provided' ? 'USER PROVIDED' : 'AI INFERRED'}
                        </span>
                        <span className="text-[10px] font-mono text-brand-textDim uppercase">
                          STATUS: {a.validation_status}
                        </span>
                      </div>
                    </div>
                    <Badge variant="teal" size="sm" className="shrink-0">
                      {(a.confidence * 100).toFixed(0)}% CONF
                    </Badge>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Section 4: Ambiguity & Actionable Clarification Questions */}
          <div className="rounded-xl border border-brand-border bg-brand-surface p-5 shadow-subtle space-y-4">
            <div className="flex items-center justify-between pb-2 border-b border-brand-border/60">
              <div className="flex items-center gap-2">
                <AlertCircle className="w-4 h-4 text-amber-400" />
                <h4 className="text-xs font-semibold text-brand-text font-mono uppercase tracking-wider">
                  Ambiguity Detection &amp; Actionable Clarifications ({contract.unresolved_questions.length})
                </h4>
              </div>
              <span className="text-[11px] font-mono text-brand-textDim">
                Dimensions required before final gating
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {contract.unresolved_questions.map((u) => {
                const isRequired = u.clarification_type === "required";
                return (
                  <div
                    key={u.question_id}
                    className={`p-3.5 rounded-lg border text-xs space-y-2 ${
                      isRequired
                        ? "bg-[#141B2D] border-amber-500/30 text-amber-200"
                        : "bg-[#111B2E] border-brand-border/60 text-slate-300"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <Badge
                        variant={isRequired ? "gap" : "unverified"}
                        size="sm"
                        showDot={isRequired}
                      >
                        {u.clarification_type.replace("_", " ").toUpperCase()}
                      </Badge>
                      <span className="text-[10px] font-mono uppercase text-brand-textDim">
                        DIMENSION: {u.dimension}
                      </span>
                    </div>

                    <p className="text-xs leading-relaxed text-slate-200">
                      {u.question}
                    </p>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Platform Non-Negotiable Honesty Note */}
          <div className="p-4 rounded-lg bg-[#0E1726] border border-brand-border text-xs flex items-start gap-3">
            <div className="p-1.5 rounded bg-brand-surface border border-brand-border text-brand-teal shrink-0 mt-0.5">
              <Shield className="w-4 h-4" />
            </div>
            <div className="space-y-1">
              <div className="font-semibold text-brand-text">
                TruthMap Contract Principle:
              </div>
              <p className="text-brand-textMuted leading-relaxed">
                A Decision Contract formalizes the evidentiary prerequisites and causal discipline required before making a high-stakes decision. The compiler structures and tests the inquiry; it does not answer it or claim factual truth.
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
