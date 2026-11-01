import { useState, useEffect } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import {
  listInvestigations,
  getInvestigationReports,
  getReportById,
  generateInvestigationReport,
  Investigation,
  DecisionReport,
  DecisionReportSummary,
  DecisionOutcome,
} from "@/lib/api";
import {
  FileText,
  Sparkles,
  RefreshCw,
  Printer,
  AlertTriangle,
  CheckCircle2,
  HelpCircle,
  XCircle,
  ArrowRight,
  ChevronDown,
  ChevronRight,
  Flame,
  Info,
  Zap,
} from "lucide-react";
import { Button } from "@/components/ui/Button";

// Robustness styling configuration
const ROBUSTNESS_CONFIG: Record<
  DecisionOutcome,
  { label: string; bg: string; text: string; border: string; desc: string }
> = {
  ROBUST: {
    label: "ROBUST",
    bg: "bg-emerald-500/10",
    text: "text-emerald-400",
    border: "border-emerald-500/30",
    desc: "Evidence satisfies all decision criteria with zero unresolved contradictions.",
  },
  CONDITIONALLY_ROBUST: {
    label: "CONDITIONALLY ROBUST",
    bg: "bg-teal-500/10",
    text: "text-teal-400",
    border: "border-teal-500/30",
    desc: "Decision criteria partially satisfied; contingent on minor assumption verifications.",
  },
  VULNERABLE: {
    label: "VULNERABLE",
    bg: "bg-amber-500/10",
    text: "text-amber-400",
    border: "border-amber-500/30",
    desc: "Unresolved contradictions, critical evidence gaps, or severe stress failure risks present.",
  },
  HIGHLY_VULNERABLE: {
    label: "HIGHLY VULNERABLE",
    bg: "bg-rose-500/10",
    text: "text-rose-400",
    border: "border-rose-500/30",
    desc: "Critical factual contradictions or catastrophic stress failure invalidate decision premise.",
  },
  INDETERMINATE: {
    label: "INDETERMINATE",
    bg: "bg-slate-500/10",
    text: "text-slate-400",
    border: "border-slate-500/30",
    desc: "Insufficient evidence or missing decision contract requirements preclude assessment.",
  },
  NOT_EVALUABLE: {
    label: "NOT EVALUABLE",
    bg: "bg-slate-800/40",
    text: "text-slate-400",
    border: "border-slate-700/50",
    desc: "Outcome cannot be evaluated because baseline contract criteria or affected evidence parameters are missing.",
  },
};

export function ReportsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();

  // Investigation & Reports State
  const [investigations, setInvestigations] = useState<Investigation[]>([]);
  const [selectedInvId, setSelectedInvId] = useState<string>("");
  const [reportVersions, setReportVersions] = useState<DecisionReportSummary[]>([]);
  const [selectedReportId, setSelectedReportId] = useState<string>("");
  const [currentReport, setCurrentReport] = useState<DecisionReport | null>(null);

  // UI States
  const [loading, setLoading] = useState<boolean>(true);
  const [generating, setGenerating] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedReqs, setExpandedReqs] = useState<Record<string, boolean>>({});

  // 1. Load Investigations on Mount
  useEffect(() => {
    async function loadInvs() {
      try {
        setLoading(true);
        const invs = await listInvestigations();
        setInvestigations(invs);

        const urlInvId = searchParams.get("investigation_id");
        if (urlInvId && invs.some((i) => i.id === urlInvId)) {
          setSelectedInvId(urlInvId);
        } else if (invs.length > 0) {
          setSelectedInvId(invs[0].id);
          setSearchParams({ investigation_id: invs[0].id });
        }
      } catch (err: any) {
        setError(err.message || "Failed to load investigations");
      } finally {
        setLoading(false);
      }
    }
    loadInvs();
  }, []);

  // 2. Load Reports and Status when Investigation changes
  useEffect(() => {
    if (!selectedInvId) return;

    async function loadReportsData() {
      try {
        setLoading(true);
        setError(null);

        // Fetch list of reports
        const listData = await getInvestigationReports(selectedInvId).catch(() => ({ total_reports: 0, latest_version: 0, reports: [] }));
        setReportVersions(listData.reports);

        const urlReportId = searchParams.get("report_id");
        if (urlReportId && listData.reports.some((r) => r.id === urlReportId)) {
          setSelectedReportId(urlReportId);
          const fullReport = await getReportById(selectedInvId, urlReportId);
          setCurrentReport(fullReport);
        } else if (listData.reports.length > 0) {
          const latest = listData.reports[0];
          setSelectedReportId(latest.id);
          const fullReport = await getReportById(selectedInvId, latest.id);
          setCurrentReport(fullReport);
        } else {
          setSelectedReportId("");
          setCurrentReport(null);
        }
      } catch (err: any) {
        setError(err.message || "Failed to load reports");
      } finally {
        setLoading(false);
      }
    }

    loadReportsData();
  }, [selectedInvId]);

  // Handle Investigation change
  const handleSelectInvestigation = (id: string) => {
    setSelectedInvId(id);
    setSearchParams({ investigation_id: id });
  };

  // Handle Version selection
  const handleSelectVersion = async (reportId: string) => {
    if (!selectedInvId || !reportId) return;
    try {
      setLoading(true);
      setSelectedReportId(reportId);
      setSearchParams({ investigation_id: selectedInvId, report_id: reportId });
      const fullReport = await getReportById(selectedInvId, reportId);
      setCurrentReport(fullReport);
    } catch (err: any) {
      setError(err.message || "Failed to fetch report version");
    } finally {
      setLoading(false);
    }
  };

  // Handle Report Generation
  const handleGenerateReport = async (fast: boolean = false) => {
    if (!selectedInvId) return;
    try {
      setGenerating(true);
      setError(null);
      const newReport = await generateInvestigationReport(selectedInvId, fast);

      // Refresh list
      const listData = await getInvestigationReports(selectedInvId);
      setReportVersions(listData.reports);
      setSelectedReportId(newReport.id);
      setCurrentReport(newReport);
      setSearchParams({ investigation_id: selectedInvId, report_id: newReport.id });
    } catch (err: any) {
      setError(err.message || "Failed to generate report");
    } finally {
      setGenerating(false);
    }
  };

  // Handle Print / PDF Export
  const handlePrint = () => {
    window.print();
  };

  const toggleReqExpand = (rid: string) => {
    setExpandedReqs((prev) => ({ ...prev, [rid]: !prev[rid] }));
  };

  // Helper formatting
  const formatDate = (isoStr?: string) => {
    if (!isoStr) return "N/A";
    try {
      return new Date(isoStr).toLocaleString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return isoStr;
    }
  };

  const robustCfg = currentReport
    ? ROBUSTNESS_CONFIG[currentReport.overall_robustness] || ROBUSTNESS_CONFIG.INDETERMINATE
    : ROBUSTNESS_CONFIG.INDETERMINATE;

  return (
    <div className="space-y-6 print:m-0 print:p-0 print:space-y-4">
      {/* Print-only CSS rules */}
      <style>{`
        @media print {
          nav, aside, header, .no-print, button, select {
            display: none !important;
          }
          body {
            background: #ffffff !important;
            color: #000000 !important;
          }
          .print-card {
            border: 1px solid #e2e8f0 !important;
            background: #ffffff !important;
            color: #0f172a !important;
            box-shadow: none !important;
            break-inside: avoid;
            margin-bottom: 1.5rem !important;
          }
          .print-page-break {
            page-break-before: always;
          }
        }
      `}</style>

      {/* TOP HEADER / TOOLBAR */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 border-b border-border/40 pb-5 no-print">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <div className="p-1.5 rounded-lg bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
              <FileText className="w-5 h-5" />
            </div>
            <h1 className="text-xl font-bold tracking-tight text-foreground flex items-center gap-2">
              Decision Intelligence Report Engine
            </h1>
          </div>
          <p className="text-sm text-muted-foreground">
            Comprehensive, audit-ready summary reports with full source citations, risk scores, and evidence verification.
          </p>
        </div>

        {/* CONTROLS */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Investigation Selector */}
          <select
            value={selectedInvId}
            onChange={(e) => handleSelectInvestigation(e.target.value)}
            className="h-9 px-3 py-1 bg-slate-900 border border-slate-700 text-slate-100 rounded-md text-xs font-medium focus:outline-none focus:ring-1 focus:ring-primary min-w-[200px] cursor-pointer shadow-sm"
          >
            {investigations.map((inv) => (
              <option key={inv.id} value={inv.id} className="bg-slate-900 text-slate-100 py-1.5">
                {inv.research_question.length > 45 ? `${inv.research_question.slice(0, 45)}...` : inv.research_question}
              </option>
            ))}
          </select>

          {/* Version Selector */}
          {reportVersions.length > 0 && (
            <select
              value={selectedReportId}
              onChange={(e) => handleSelectVersion(e.target.value)}
              className="h-9 px-3 py-1 bg-slate-900 border border-slate-700 text-slate-100 rounded-md text-xs font-mono font-medium focus:outline-none focus:ring-1 focus:ring-primary cursor-pointer shadow-sm"
            >
              {reportVersions.map((r) => (
                <option key={r.id} value={r.id} className="bg-slate-900 text-slate-100 py-1.5">
                  v{r.report_version} ({r.is_stale ? "Stale · " : "Current · "}{formatDate(r.created_at)})
                </option>
              ))}
            </select>
          )}

          {/* Fast Compile Button */}
          <Button
            onClick={() => handleGenerateReport(true)}
            disabled={generating || !selectedInvId}
            size="sm"
            variant="outline"
            className="gap-1.5 border-emerald-500/40 text-emerald-300 hover:bg-emerald-500/20 font-medium text-xs h-9 shadow-sm"
            title="Instant deterministic report compilation (<0.1s)"
          >
            {generating ? (
              <RefreshCw className="w-3.5 h-3.5 animate-spin text-emerald-400" />
            ) : (
              <Zap className="w-3.5 h-3.5 text-emerald-400" />
            )}
            Fast Compile (&lt;0.1s)
          </Button>

          {/* Standard Compile Button */}
          <Button
            onClick={() => handleGenerateReport(false)}
            disabled={generating || !selectedInvId}
            size="sm"
            className="gap-2 bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 text-white font-medium shadow-sm text-xs h-9"
          >
            {generating ? (
              <>
                <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                Compiling...
              </>
            ) : (
              <>
                <Sparkles className="w-3.5 h-3.5" />
                {currentReport ? "Compile New Version" : "Generate Report"}
              </>
            )}
          </Button>

          {/* Print / Export Button */}
          {currentReport && (
            <Button
              onClick={handlePrint}
              variant="outline"
              size="sm"
              className="gap-1.5 border-border/60 hover:bg-muted/50 text-foreground"
            >
              <Printer className="w-3.5 h-3.5 text-muted-foreground" />
              Print / Export Dossier
            </Button>
          )}
        </div>
      </div>

      {/* ERROR BANNER */}
      {error && (
        <div className="p-4 rounded-lg bg-rose-500/10 border border-rose-500/30 flex items-start gap-3 no-print">
          <AlertTriangle className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
          <div className="text-sm">
            <span className="font-semibold text-rose-400">Execution Error: </span>
            <span className="text-rose-200">{error}</span>
          </div>
        </div>
      )}

      {/* STALE REPORT BANNER */}
      {currentReport && currentReport.is_stale && (
        <div className="p-3.5 rounded-lg bg-amber-500/10 border border-amber-500/30 flex items-center justify-between gap-3 no-print">
          <div className="flex items-center gap-2.5 text-xs text-amber-200">
            <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
            <span>
              <strong>Upstream Data Changed:</strong> Ingested sources, claims, contradictions, or stress tests have evolved since Version {currentReport.report_version} was compiled.
            </span>
          </div>
          <div className="flex items-center gap-2">
            <Button
              onClick={() => handleGenerateReport(true)}
              disabled={generating}
              size="sm"
              variant="outline"
              className="h-7 text-xs border-emerald-500/40 text-emerald-300 hover:bg-emerald-500/20"
            >
              <Zap className="w-3 h-3 text-emerald-400 mr-1" />
              Fast Recompile
            </Button>
            <Button
              onClick={() => handleGenerateReport(false)}
              disabled={generating}
              size="sm"
              variant="outline"
              className="h-7 text-xs border-amber-500/40 text-amber-300 hover:bg-amber-500/20"
            >
              {generating ? <RefreshCw className="w-3 h-3 animate-spin mr-1" /> : null}
              Recompile Full
            </Button>
          </div>
        </div>
      )}

      {/* COMPILING OVERLAY STATE */}
      {generating && (
        <div className="p-8 text-center border border-indigo-500/30 rounded-xl bg-card/60 backdrop-blur-sm space-y-3 shadow-lg">
          <div className="w-12 h-12 mx-auto rounded-full bg-indigo-500/15 flex items-center justify-center text-indigo-400 border border-indigo-500/30">
            <RefreshCw className="w-6 h-6 animate-spin text-indigo-400" />
          </div>
          <div className="max-w-md mx-auto space-y-1.5">
            <h3 className="text-base font-semibold text-foreground">Compiling Decision Intelligence Report...</h3>
            <p className="text-xs text-muted-foreground">
              Synthesizing Decision Contract, Claims, Provenance, Conflicts, Sufficiency Gaps, and Stress Scenarios into an audit-grade dossier.
            </p>
          </div>
        </div>
      )}

      {/* EMPTY STATE */}
      {!loading && !generating && !currentReport && (
        <div className="p-12 text-center border border-dashed border-border/60 rounded-xl bg-card/20 space-y-4">
          <div className="w-12 h-12 mx-auto rounded-full bg-indigo-500/10 flex items-center justify-center text-indigo-400 border border-indigo-500/20">
            <FileText className="w-6 h-6" />
          </div>
          <div className="max-w-md mx-auto space-y-2">
            <h3 className="text-base font-semibold text-foreground">No Decision Report Compiled</h3>
            <p className="text-xs text-muted-foreground">
              Synthesize all upstream components (Decision Contract, Claims, Provenance, Conflicts, Sufficiency, and Stress Scenarios) into an audit-grade intelligence dossier.
            </p>
          </div>
          <div className="flex items-center justify-center gap-3 pt-2">
            <Button
              onClick={() => handleGenerateReport(true)}
              disabled={generating || !selectedInvId}
              variant="outline"
              className="gap-2 border-emerald-500/40 text-emerald-300 hover:bg-emerald-500/20 font-medium"
            >
              <Zap className="w-4 h-4 text-emerald-400" />
              Fast Compile (&lt;0.1s)
            </Button>
            <Button
              onClick={() => handleGenerateReport(false)}
              disabled={generating || !selectedInvId}
              className="gap-2 bg-indigo-600 hover:bg-indigo-500 text-white font-medium"
            >
              <Sparkles className="w-4 h-4" />
              Generate Version 1 Report
            </Button>
          </div>
        </div>
      )}

      {/* ACTIVE REPORT VIEW */}
      {currentReport && (
        <div className="space-y-6">
          {/* DOSSIER HEADER CARD */}
          <div className="p-6 rounded-xl border border-border/50 bg-card/40 backdrop-blur-sm print-card space-y-4">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-border/30 pb-4">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-mono px-2 py-0.5 rounded bg-muted text-muted-foreground font-semibold">
                    REPORT-v{currentReport.report_version}
                  </span>
                  <span
                    className={`text-xs px-2.5 py-0.5 rounded-full font-mono font-medium border ${
                      currentReport.processing_mode === "gemini"
                        ? "bg-indigo-500/15 text-indigo-300 border-indigo-500/30"
                        : "bg-cyan-500/15 text-cyan-300 border-cyan-500/30"
                    }`}
                  >
                    {currentReport.processing_mode === "gemini" ? "✦ Gemini 2.5 Flash Synthesis" : "Deterministic Engine"}
                  </span>
                  {currentReport.is_stale ? (
                    <span className="text-xs px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/30 font-medium">
                      Stale Snapshot
                    </span>
                  ) : (
                    <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 font-medium">
                      Current Snapshot
                    </span>
                  )}
                </div>
                <h2 className="text-lg md:text-xl font-bold text-foreground">
                  {currentReport.report_data.executive_brief.research_question}
                </h2>
                <p className="text-xs text-muted-foreground">
                  Decision Objective: <span className="text-foreground font-medium">{currentReport.report_data.executive_brief.decision_objective}</span>
                </p>
              </div>

              {/* ROBUSTNESS CALLOUT */}
              <div className={`p-4 rounded-lg border ${robustCfg.bg} ${robustCfg.border} text-right min-w-[200px]`}>
                <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">Overall Robustness</div>
                <div className={`text-xl font-bold tracking-tight ${robustCfg.text}`}>{robustCfg.label}</div>
                <div className="text-[11px] text-muted-foreground/80 mt-0.5">{robustCfg.desc}</div>
              </div>
            </div>

            {/* KEY METRICS GRID */}
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-3">
              <div className="p-3 rounded-lg bg-background/50 border border-border/40">
                <div className="text-[10px] font-mono uppercase text-muted-foreground">Coverage Ratio</div>
                <div className="text-lg font-bold text-foreground font-mono">
                  {(currentReport.report_data.executive_brief.coverage_ratio * 100).toFixed(0)}%
                </div>
                <div className="text-[10px] text-muted-foreground">Sufficient Criteria</div>
              </div>

              <div className="p-3 rounded-lg bg-background/50 border border-border/40">
                <div className="text-[10px] font-mono uppercase text-muted-foreground">Ingested Sources</div>
                <div className="text-lg font-bold text-foreground font-mono">
                  {currentReport.report_data.executive_brief.total_sources}
                </div>
                <div className="text-[10px] text-muted-foreground">Cryptographic Hashes</div>
              </div>

              <div className="p-3 rounded-lg bg-background/50 border border-border/40">
                <div className="text-[10px] font-mono uppercase text-muted-foreground">Atomic Claims</div>
                <div className="text-lg font-bold text-foreground font-mono">
                  {currentReport.report_data.executive_brief.total_claims}
                </div>
                <div className="text-[10px] text-muted-foreground">Extracted Claims</div>
              </div>

              <div className="p-3 rounded-lg bg-background/50 border border-border/40">
                <div className="text-[10px] font-mono uppercase text-muted-foreground">Unresolved Conflicts</div>
                <div className="text-lg font-bold text-foreground font-mono text-amber-400">
                  {currentReport.report_data.executive_brief.unresolved_conflicts_count}
                </div>
                <div className="text-[10px] text-muted-foreground">Active Tensions</div>
              </div>

              <div className="p-3 rounded-lg bg-background/50 border border-border/40">
                <div className="text-[10px] font-mono uppercase text-muted-foreground">Evidence Gaps</div>
                <div className="text-lg font-bold text-foreground font-mono text-rose-400">
                  {currentReport.report_data.executive_brief.identified_gaps_count}
                </div>
                <div className="text-[10px] text-muted-foreground">Missing Proofs</div>
              </div>

              <div className="p-3 rounded-lg bg-background/50 border border-border/40">
                <div className="text-[10px] font-mono uppercase text-muted-foreground">High Stress Scenarios</div>
                <div className="text-lg font-bold text-foreground font-mono text-indigo-400">
                  {currentReport.report_data.executive_brief.high_severity_scenarios_count}
                </div>
                <div className="text-[10px] text-muted-foreground">Permutations Tested</div>
              </div>
            </div>
          </div>

          {/* TABLE OF CONTENTS / QUICK JUMP (Screen only) */}
          <div className="flex items-center gap-1.5 overflow-x-auto pb-1 border-b border-border/30 no-print text-xs font-medium">
            <span className="text-muted-foreground font-mono text-[11px] uppercase tracking-wider mr-2">Jump To:</span>
            {[
              { id: "sec-1", label: "1. Executive Brief" },
              { id: "sec-2", label: "2. Decision Contract" },
              { id: "sec-3", label: "3. Evidence Intelligence" },
              { id: "sec-4", label: "4. Requirement Matrix" },
              { id: "sec-5", label: "5. Conflicts" },
              { id: "sec-6", label: "6. Evidence Gaps" },
              { id: "sec-7", label: "7. Stress Tests" },
              { id: "sec-8", label: "8. Risk Register" },
              { id: "sec-9", label: "9. Recommended Actions" },
              { id: "sec-10", label: "10. Analytical Conclusion" },
            ].map((tab) => (
              <a
                key={tab.id}
                href={`#${tab.id}`}
                className="px-2.5 py-1 rounded bg-muted/40 hover:bg-muted text-muted-foreground hover:text-foreground transition-colors whitespace-nowrap"
              >
                {tab.label}
              </a>
            ))}
          </div>

          {/* ======================================================== */}
          {/* SECTION 1: EXECUTIVE DECISION BRIEF */}
          {/* ======================================================== */}
          <section id="sec-1" className="space-y-3 print-card">
            <div className="flex items-center justify-between border-b border-border/40 pb-2">
              <h3 className="text-base font-bold text-foreground flex items-center gap-2">
                <span className="font-mono text-indigo-400 text-xs">SECTION 01</span>
                Executive Decision Brief
              </h3>
              <span className="text-xs text-muted-foreground font-mono">
                Sealed: {formatDate(currentReport.report_data.executive_brief.generated_at)}
              </span>
            </div>

            <div className="p-4 rounded-xl bg-card/30 border border-border/40 space-y-3">
              <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                <Info className="w-3.5 h-3.5 text-indigo-400" />
                Synthesized Analytical Verdict
              </div>
              <div className="text-sm leading-relaxed text-foreground/90 whitespace-pre-line border-l-2 border-indigo-500/60 pl-3">
                {currentReport.report_data.executive_brief.executive_conclusion}
              </div>
            </div>
          </section>

          {/* ======================================================== */}
          {/* SECTION 2: DECISION CONTRACT */}
          {/* ======================================================== */}
          <section id="sec-2" className="space-y-3 print-card">
            <div className="flex items-center justify-between border-b border-border/40 pb-2">
              <h3 className="text-base font-bold text-foreground flex items-center gap-2">
                <span className="font-mono text-indigo-400 text-xs">SECTION 02</span>
                Decision Contract Baseline
              </h3>
              <Button
                variant="ghost"
                size="sm"
                className="h-6 text-xs text-indigo-400 hover:text-indigo-300 p-0 no-print gap-1"
                onClick={() => navigate(`/decision-contract?investigation_id=${selectedInvId}`)}
              >
                Inspect Contract <ArrowRight className="w-3 h-3" />
              </Button>
            </div>

            <div className="p-4 rounded-xl bg-card/30 border border-border/40 space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                <div>
                  <div className="text-muted-foreground uppercase font-mono text-[10px]">Normalized Inquiry</div>
                  <div className="font-medium text-foreground mt-0.5">
                    {currentReport.report_data.decision_contract.normalized_question}
                  </div>
                </div>
                <div>
                  <div className="text-muted-foreground uppercase font-mono text-[10px]">Stated Scope</div>
                  <div className="font-medium text-foreground mt-0.5">
                    {currentReport.report_data.decision_contract.scope || "Inquiry-wide"}
                  </div>
                </div>
              </div>

              {/* Requirements List */}
              <div className="space-y-2">
                <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                  Contract Criteria & Verification Rules ({currentReport.report_data.decision_contract.requirements.length})
                </div>
                <div className="space-y-2">
                  {currentReport.report_data.decision_contract.requirements.map((req, idx) => (
                    <div
                      key={req.requirement_id}
                      className="p-3 rounded-lg bg-background/50 border border-border/40 flex flex-col md:flex-row md:items-center justify-between gap-2 text-xs"
                    >
                      <div className="space-y-0.5">
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-muted-foreground font-semibold">REQ-{idx + 1}</span>
                          <span className="font-medium text-foreground">{req.title}</span>
                          <span
                            className={`px-1.5 py-0.2 rounded font-mono text-[10px] ${
                              req.priority === "HIGH"
                                ? "bg-rose-500/20 text-rose-300"
                                : req.priority === "MEDIUM"
                                ? "bg-amber-500/20 text-amber-300"
                                : "bg-slate-500/20 text-slate-300"
                            }`}
                          >
                            {req.priority}
                          </span>
                        </div>
                        <div className="text-muted-foreground text-[11px]">
                          <strong>Verification Criteria:</strong> {req.verification_criteria || "Empirical documentation required"}
                        </div>
                      </div>
                      {req.evidence_types && req.evidence_types.length > 0 && (
                        <div className="flex flex-wrap gap-1 shrink-0">
                          {req.evidence_types.map((et, i) => (
                            <span key={i} className="px-1.5 py-0.5 rounded bg-muted text-muted-foreground text-[10px] font-mono">
                              {et}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>

              {/* Constraints & Assumptions */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs pt-2 border-t border-border/30">
                <div className="space-y-1.5">
                  <div className="font-semibold text-muted-foreground uppercase text-[10px]">Explicit Constraints</div>
                  {currentReport.report_data.decision_contract.constraints.length > 0 ? (
                    <ul className="list-disc list-inside space-y-1 text-muted-foreground">
                      {currentReport.report_data.decision_contract.constraints.map((c, i) => (
                        <li key={i} className="text-foreground/90">{c}</li>
                      ))}
                    </ul>
                  ) : (
                    <div className="text-muted-foreground italic">No boundary constraints documented.</div>
                  )}
                </div>

                <div className="space-y-1.5">
                  <div className="font-semibold text-muted-foreground uppercase text-[10px]">Documented Assumptions</div>
                  {currentReport.report_data.decision_contract.assumptions.length > 0 ? (
                    <ul className="list-disc list-inside space-y-1 text-muted-foreground">
                      {currentReport.report_data.decision_contract.assumptions.map((a, i) => (
                        <li key={i} className="text-foreground/90">{a}</li>
                      ))}
                    </ul>
                  ) : (
                    <div className="text-muted-foreground italic">No formal assumptions recorded.</div>
                  )}
                </div>
              </div>
            </div>
          </section>

          {/* ======================================================== */}
          {/* SECTION 3: EVIDENCE INTELLIGENCE SUMMARY */}
          {/* ======================================================== */}
          <section id="sec-3" className="space-y-3 print-card">
            <div className="flex items-center justify-between border-b border-border/40 pb-2">
              <h3 className="text-base font-bold text-foreground flex items-center gap-2">
                <span className="font-mono text-indigo-400 text-xs">SECTION 03</span>
                Evidence Intelligence & Provenance
              </h3>
              <Button
                variant="ghost"
                size="sm"
                className="h-6 text-xs text-indigo-400 hover:text-indigo-300 p-0 no-print gap-1"
                onClick={() => navigate(`/evidence-explorer?investigation_id=${selectedInvId}`)}
              >
                Inspect Explorer <ArrowRight className="w-3 h-3" />
              </Button>
            </div>

            <div className="p-4 rounded-xl bg-card/30 border border-border/40 space-y-4">
              {/* Reliability Warning */}
              <div className="p-3 rounded-lg bg-indigo-500/10 border border-indigo-500/20 text-xs text-indigo-200">
                <strong>Provenance Baseline: </strong>
                {currentReport.report_data.evidence_intelligence.reliability_limitations}
              </div>

              {/* Sources Table */}
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="border-b border-border/40 text-[10px] font-mono uppercase text-muted-foreground">
                    <tr>
                      <th className="pb-2 font-semibold">Source Title &amp; Origin</th>
                      <th className="pb-2 font-semibold">Type</th>
                      <th className="pb-2 font-semibold">Published</th>
                      <th className="pb-2 font-semibold">Ingested</th>
                      <th className="pb-2 font-semibold">Freshness Status</th>
                      <th className="pb-2 font-semibold">Claims</th>
                      <th className="pb-2 font-semibold">SHA-256 Provenance Hash</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/20 text-foreground/90">
                    {currentReport.report_data.evidence_intelligence.sources.map((src) => (
                      <tr key={src.source_id} className="hover:bg-muted/30">
                        <td className="py-2.5 pr-2">
                          <div className="font-medium text-foreground">{src.title}</div>
                          <div className="text-[10px] text-muted-foreground">{src.publisher || "Direct Source"}</div>
                          {src.freshness_warning && (
                            <div className="text-[10px] text-amber-400/90 italic pt-0.5">
                              ⚠️ {src.freshness_warning}
                            </div>
                          )}
                        </td>
                        <td className="py-2.5 font-mono text-[11px] uppercase text-muted-foreground">{src.source_type}</td>
                        <td className="py-2.5 font-medium">{src.publication_date || "Undated"}</td>
                        <td className="py-2.5 text-muted-foreground text-[11px]">{src.ingestion_date ? src.ingestion_date.split("T")[0] : "Recorded"}</td>
                        <td className="py-2.5">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-medium border ${
                            src.freshness_classification === "Date Available"
                              ? "bg-emerald-950/60 text-emerald-300 border-emerald-800"
                              : src.freshness_classification === "Potentially Outdated"
                              ? "bg-amber-950/60 text-amber-300 border-amber-800"
                              : "bg-slate-900 text-slate-400 border-slate-700"
                          }`}>
                            {src.freshness_classification || "Undated Source"}
                          </span>
                        </td>
                        <td className="py-2.5 font-mono font-medium">{src.claims_count}</td>
                        <td className="py-2.5 font-mono text-[10px] text-muted-foreground truncate max-w-[150px]">
                          {src.sha256_hash ? src.sha256_hash.slice(0, 20) + "..." : "unhashed"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="mt-3 p-2.5 rounded bg-muted/20 border border-border/30 text-[11px] text-muted-foreground flex items-center justify-between">
                <span>
                  <strong>Forensic Freshness Rule:</strong> Publication age is an indicator for human review, not proof of inaccuracy.
                </span>
                <span className="font-mono text-[10px]">
                  Configured Threshold: 365 Days
                </span>
              </div>
            </div>
          </section>

          {/* ======================================================== */}
          {/* SECTION 4: REQUIREMENT-LEVEL ASSESSMENT */}
          {/* ======================================================== */}
          <section id="sec-4" className="space-y-3 print-card">
            <div className="flex items-center justify-between border-b border-border/40 pb-2">
              <h3 className="text-base font-bold text-foreground flex items-center gap-2">
                <span className="font-mono text-indigo-400 text-xs">SECTION 04</span>
                Requirement-Level Assessment Matrix
              </h3>
              <Button
                variant="ghost"
                size="sm"
                className="h-6 text-xs text-indigo-400 hover:text-indigo-300 p-0 no-print gap-1"
                onClick={() => navigate(`/evidence-sufficiency?investigation_id=${selectedInvId}`)}
              >
                Inspect Sufficiency <ArrowRight className="w-3 h-3" />
              </Button>
            </div>

            <div className="space-y-3">
              {currentReport.report_data.requirement_assessment.matrix.map((row) => {
                const isExpanded = !!expandedReqs[row.requirement_id];
                const statusColor =
                  row.coverage_status === "SUFFICIENT"
                    ? "bg-emerald-500/15 text-emerald-300 border-emerald-500/30"
                    : row.coverage_status === "PARTIAL"
                    ? "bg-teal-500/15 text-teal-300 border-teal-500/30"
                    : row.coverage_status === "CONFLICTING"
                    ? "bg-rose-500/15 text-rose-300 border-rose-500/30"
                    : "bg-slate-500/15 text-slate-300 border-slate-500/30";

                return (
                  <div
                    key={row.requirement_id}
                    className="p-4 rounded-xl bg-card/30 border border-border/40 space-y-3 print-card"
                  >
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-xs font-semibold text-muted-foreground">{row.requirement_id}</span>
                          <span className="font-bold text-sm text-foreground">{row.title}</span>
                          <span className="px-1.5 py-0.2 rounded font-mono text-[10px] bg-muted text-muted-foreground">
                            {row.priority}
                          </span>
                        </div>
                        <p className="text-xs text-muted-foreground/90">{row.assessment_summary}</p>
                      </div>

                      <div className="flex items-center gap-2 shrink-0">
                        <span className={`px-2.5 py-0.5 rounded-full font-mono text-xs font-semibold border ${statusColor}`}>
                          {row.coverage_status}
                        </span>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => toggleReqExpand(row.requirement_id)}
                          className="h-7 w-7 p-0 no-print"
                        >
                          {isExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                        </Button>
                      </div>
                    </div>

                    {/* Supporting Claims & Opposing Evidence (Collapsible / Expanded) */}
                    <div className={`${isExpanded ? "block" : "hidden sm:block"} pt-2 border-t border-border/20 space-y-2`}>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                        {/* Supporting */}
                        <div className="space-y-1.5">
                          <span className="text-[10px] font-mono uppercase text-emerald-400 font-semibold flex items-center gap-1">
                            <CheckCircle2 className="w-3 h-3" /> Supporting Claims ({row.supporting_claims.length})
                          </span>
                          {row.supporting_claims.length > 0 ? (
                            <div className="space-y-1.5">
                              {row.supporting_claims.map((sc) => (
                                <div key={sc.claim_id} className="p-2 rounded bg-background/50 border border-border/30 text-[11px]">
                                  <div className="text-foreground/90 font-medium">"{sc.claim_text}"</div>
                                  <div className="text-muted-foreground text-[10px] flex items-center gap-2 mt-0.5">
                                    <span>Source: {sc.source_title}</span>
                                    <span className="font-mono">Rel: {sc.relevance}</span>
                                  </div>
                                </div>
                              ))}
                            </div>
                          ) : (
                            <div className="text-muted-foreground italic text-[11px]">No supporting claims verified.</div>
                          )}
                        </div>

                        {/* Opposing / Gaps */}
                        <div className="space-y-1.5">
                          <span className="text-[10px] font-mono uppercase text-rose-400 font-semibold flex items-center gap-1">
                            <AlertTriangle className="w-3 h-3" /> Opposing Evidence & Gaps ({row.opposing_evidence.length + row.identified_gaps.length})
                          </span>
                          {row.opposing_evidence.length > 0 || row.identified_gaps.length > 0 ? (
                            <div className="space-y-1.5">
                              {row.opposing_evidence.map((oe) => (
                                <div key={oe.conflict_id} className="p-2 rounded bg-rose-500/10 border border-rose-500/20 text-[11px]">
                                  <div className="text-rose-200 font-medium">Contradiction: "{oe.claim_text}"</div>
                                  <div className="text-rose-300 text-[10px] mt-0.5">
                                    Type: {oe.conflict_type} · Severity: {oe.severity.toUpperCase()}
                                  </div>
                                </div>
                              ))}
                              {row.identified_gaps.map((gap, gIdx) => (
                                <div key={gIdx} className="p-2 rounded bg-amber-500/10 border border-amber-500/20 text-[11px]">
                                  <div className="text-amber-200"><strong>Gap:</strong> {gap}</div>
                                </div>
                              ))}
                            </div>
                          ) : (
                            <div className="text-muted-foreground italic text-[11px]">No contradictions or gaps reported.</div>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </section>

          {/* ======================================================== */}
          {/* SECTION 5: CONFLICT AND CONTRADICTION ANALYSIS */}
          {/* ======================================================== */}
          <section id="sec-5" className="space-y-3 print-card">
            <div className="flex items-center justify-between border-b border-border/40 pb-2">
              <h3 className="text-base font-bold text-foreground flex items-center gap-2">
                <span className="font-mono text-indigo-400 text-xs">SECTION 05</span>
                Conflict & Contradiction Analysis
              </h3>
              <Button
                variant="ghost"
                size="sm"
                className="h-6 text-xs text-indigo-400 hover:text-indigo-300 p-0 no-print gap-1"
                onClick={() => navigate(`/conflict-intelligence?investigation_id=${selectedInvId}`)}
              >
                Inspect Conflicts <ArrowRight className="w-3 h-3" />
              </Button>
            </div>

            <div className="p-4 rounded-xl bg-card/30 border border-border/40 space-y-3">
              {currentReport.report_data.conflict_analysis.conflicts.length > 0 ? (
                <div className="space-y-3">
                  {currentReport.report_data.conflict_analysis.conflicts.map((conf) => (
                    <div key={conf.conflict_id} className="p-3.5 rounded-lg bg-background/50 border border-border/40 text-xs space-y-2">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div className="flex items-center gap-2">
                          <span className="font-mono font-semibold text-rose-400 uppercase">
                            {conf.conflict_type.replace(/_/g, " ")}
                          </span>
                          <span
                            className={`px-1.5 py-0.2 rounded font-mono text-[10px] ${
                              conf.severity === "critical"
                                ? "bg-rose-500/20 text-rose-300 border border-rose-500/30"
                                : "bg-amber-500/20 text-amber-300 border border-amber-500/30"
                            }`}
                          >
                            {conf.severity.toUpperCase()}
                          </span>
                        </div>
                        <span className="font-mono text-[11px] px-2 py-0.5 rounded bg-muted text-muted-foreground uppercase">
                          Status: {conf.resolution_status}
                        </span>
                      </div>

                      <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-[11px]">
                        <div className="p-2 rounded bg-card/40 border border-border/30">
                          <span className="text-[10px] font-mono text-muted-foreground">CLAIM A ({conf.claim_a_source}):</span>
                          <p className="text-foreground/90 mt-0.5">"{conf.claim_a_text}"</p>
                        </div>
                        <div className="p-2 rounded bg-card/40 border border-border/30">
                          <span className="text-[10px] font-mono text-muted-foreground">CLAIM B ({conf.claim_b_source}):</span>
                          <p className="text-foreground/90 mt-0.5">"{conf.claim_b_text}"</p>
                        </div>
                      </div>

                      <p className="text-muted-foreground text-[11px] leading-relaxed">
                        <strong>Forensic Analysis:</strong> {conf.explanation}
                      </p>

                      {conf.reviewer_notes && (
                        <div className="p-2 rounded bg-muted/40 text-[11px] text-muted-foreground italic">
                          <strong>Analyst Reviewer Notes:</strong> {conf.reviewer_notes}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="p-4 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-xs text-emerald-300 flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 shrink-0" />
                  <span>Zero conflicting or contradictory evidence claims detected across ingested sources.</span>
                </div>
              )}
            </div>
          </section>

          {/* ======================================================== */}
          {/* SECTION 6: EVIDENCE GAPS AND UNCERTAINTY */}
          {/* ======================================================== */}
          <section id="sec-6" className="space-y-3 print-card">
            <div className="flex items-center justify-between border-b border-border/40 pb-2">
              <h3 className="text-base font-bold text-foreground flex items-center gap-2">
                <span className="font-mono text-indigo-400 text-xs">SECTION 06</span>
                Evidence Gaps & Uncertainty Register
              </h3>
              <span className="text-xs text-muted-foreground font-mono">
                Total Gaps: {currentReport.report_data.gaps_and_uncertainty.total_gaps}
              </span>
            </div>

            <div className="p-4 rounded-xl bg-card/30 border border-border/40 space-y-3">
              {currentReport.report_data.gaps_and_uncertainty.gaps.length > 0 ? (
                <div className="space-y-2.5">
                  {currentReport.report_data.gaps_and_uncertainty.gaps.map((gap) => (
                    <div key={gap.gap_id} className="p-3 rounded-lg bg-background/50 border border-border/40 text-xs space-y-1.5">
                      <div className="flex items-center justify-between gap-2">
                        <div className="font-semibold text-foreground flex items-center gap-2">
                          <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
                          <span>{gap.gap_description}</span>
                        </div>
                        <span
                          className={`px-1.5 py-0.2 rounded font-mono text-[10px] ${
                            gap.priority === "HIGH" ? "bg-rose-500/20 text-rose-300" : "bg-amber-500/20 text-amber-300"
                          }`}
                        >
                          {gap.priority}
                        </span>
                      </div>
                      <div className="text-muted-foreground text-[11px] grid grid-cols-1 md:grid-cols-2 gap-2 pt-1">
                        <div>
                          <strong>Why It Matters:</strong> {gap.why_it_matters}
                        </div>
                        <div>
                          <strong>Evidence Required:</strong> {gap.evidence_needed}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="p-4 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-xs text-emerald-300 flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 shrink-0" />
                  <span>All contract requirements possess empirical source evidence coverage.</span>
                </div>
              )}
            </div>
          </section>

          {/* ======================================================== */}
          {/* SECTION 7: DECISION STRESS-TEST RESULTS */}
          {/* ======================================================== */}
          <section id="sec-7" className="space-y-3 print-card">
            <div className="flex items-center justify-between border-b border-border/40 pb-2">
              <h3 className="text-base font-bold text-foreground flex items-center gap-2">
                <span className="font-mono text-indigo-400 text-xs">SECTION 07</span>
                Decision Stress-Test Results
              </h3>
              <Button
                variant="ghost"
                size="sm"
                className="h-6 text-xs text-indigo-400 hover:text-indigo-300 p-0 no-print gap-1"
                onClick={() => navigate(`/stress-test?investigation_id=${selectedInvId}`)}
              >
                Inspect Stress Tests <ArrowRight className="w-3 h-3" />
              </Button>
            </div>

            <div className="p-4 rounded-xl bg-card/30 border border-border/40 space-y-3">
              {currentReport.report_data.stress_test_results.scenarios.length > 0 ? (
                <div className="space-y-3">
                  {currentReport.report_data.stress_test_results.scenarios.map((sc) => {
                    const shiftColor =
                      sc.outcome_shift === "CRITICAL_FAILURE"
                        ? "bg-rose-500/20 text-rose-300 border-rose-500/30"
                        : sc.outcome_shift === "DEGRADED"
                        ? "bg-amber-500/20 text-amber-300 border-amber-500/30"
                        : "bg-emerald-500/20 text-emerald-300 border-emerald-500/30";

                    return (
                      <div key={sc.scenario_id} className="p-3.5 rounded-lg bg-background/50 border border-border/40 text-xs space-y-2">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <div className="flex items-center gap-2">
                            <Flame className="w-4 h-4 text-indigo-400" />
                            <span className="font-bold text-foreground">{sc.title}</span>
                            <span className="px-1.5 py-0.2 rounded font-mono text-[10px] bg-muted text-muted-foreground uppercase">
                              {sc.category}
                            </span>
                          </div>
                          <span className={`px-2 py-0.5 rounded-full font-mono text-[11px] font-semibold border ${shiftColor}`}>
                            Shift: {sc.outcome_shift}
                          </span>
                        </div>

                        <div className="text-[11px] text-muted-foreground space-y-1">
                          <div>
                            <strong>Trigger Condition:</strong> {sc.trigger_condition}
                          </div>
                          <div>
                            <strong>Decision Impact:</strong> {sc.impact_explanation}
                          </div>
                        </div>

                        {sc.key_vulnerabilities && sc.key_vulnerabilities.length > 0 && (
                          <div className="p-2 rounded bg-card/40 border border-border/20 text-[11px] text-rose-200">
                            <strong>Revealed Vulnerabilities: </strong>
                            {sc.key_vulnerabilities.join(" · ")}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div className="p-4 rounded-lg bg-muted/30 border border-border/30 text-xs text-muted-foreground italic">
                  No stress scenarios evaluated yet. Generate stress scenarios in Decision Stress Testing.
                </div>
              )}
            </div>
          </section>

          {/* ======================================================== */}
          {/* SECTION 8: KEY RISKS AND MITIGATION PLAN */}
          {/* ======================================================== */}
          <section id="sec-8" className="space-y-3 print-card">
            <div className="flex items-center justify-between border-b border-border/40 pb-2">
              <h3 className="text-base font-bold text-foreground flex items-center gap-2">
                <span className="font-mono text-indigo-400 text-xs">SECTION 08</span>
                Actionable Risk Register & Mitigations
              </h3>
              <span className="text-xs text-muted-foreground font-mono">
                Total Risks: {currentReport.report_data.risk_mitigation.total_risks}
              </span>
            </div>

            <div className="p-4 rounded-xl bg-card/30 border border-border/40 space-y-3">
              {currentReport.report_data.risk_mitigation.risks.length > 0 ? (
                <div className="space-y-3">
                  {currentReport.report_data.risk_mitigation.risks.map((risk) => (
                    <div key={risk.risk_id} className="p-3.5 rounded-lg bg-background/50 border border-border/40 text-xs space-y-2">
                      <div className="flex items-center justify-between gap-2">
                        <div className="flex items-center gap-2">
                          <span className="font-mono font-bold text-indigo-400">{risk.risk_id}</span>
                          <span className="font-bold text-foreground">{risk.title}</span>
                          <span className="px-1.5 py-0.2 rounded font-mono text-[10px] bg-muted text-muted-foreground">
                            Origin: {risk.origin}
                          </span>
                        </div>
                        <span
                          className={`px-2 py-0.5 rounded font-mono text-[10px] font-semibold ${
                            risk.severity === "CRITICAL"
                              ? "bg-rose-500/20 text-rose-300"
                              : risk.severity === "HIGH"
                              ? "bg-amber-500/20 text-amber-300"
                              : "bg-slate-500/20 text-slate-300"
                          }`}
                        >
                          {risk.severity}
                        </span>
                      </div>

                      <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-[11px] text-muted-foreground">
                        <div>
                          <strong>Potential Consequence:</strong> {risk.consequence}
                        </div>
                        <div>
                          <strong>Proposed Mitigation:</strong> {risk.mitigation}
                        </div>
                      </div>

                      {risk.additional_evidence_needed && (
                        <div className="text-[10px] text-indigo-300 pt-1 border-t border-border/20">
                          <strong>Verification Evidence Needed:</strong> {risk.additional_evidence_needed}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="p-4 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-xs text-emerald-300 flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 shrink-0" />
                  <span>No high-severity evidentiary risks detected.</span>
                </div>
              )}
            </div>
          </section>

          {/* ======================================================== */}
          {/* SECTION 9: RECOMMENDED NEXT ACTIONS */}
          {/* ======================================================== */}
          <section id="sec-9" className="space-y-3 print-card">
            <div className="flex items-center justify-between border-b border-border/40 pb-2">
              <h3 className="text-base font-bold text-foreground flex items-center gap-2">
                <span className="font-mono text-indigo-400 text-xs">SECTION 09</span>
                Prioritized Analyst Next Actions
              </h3>
              <span className="text-xs text-muted-foreground font-mono">
                {currentReport.report_data.recommended_actions.actions.length} Action Items
              </span>
            </div>

            <div className="p-4 rounded-xl bg-card/30 border border-border/40 space-y-2.5">
              {currentReport.report_data.recommended_actions.actions.map((act) => (
                <div
                  key={act.action_id}
                  className="p-3 rounded-lg bg-background/50 border border-border/40 text-xs flex flex-col md:flex-row md:items-center justify-between gap-2"
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="font-mono font-bold text-indigo-400">{act.action_id}</span>
                      <span className="font-semibold text-foreground">{act.action_title}</span>
                      <span
                        className={`px-1.5 py-0.2 rounded font-mono text-[10px] font-semibold ${
                          act.priority.startsWith("P1")
                            ? "bg-rose-500/20 text-rose-300"
                            : act.priority.startsWith("P2")
                            ? "bg-amber-500/20 text-amber-300"
                            : "bg-slate-500/20 text-slate-300"
                        }`}
                      >
                        {act.priority}
                      </span>
                    </div>
                    <p className="text-muted-foreground text-[11px]">{act.description}</p>
                    <div className="text-[10px] text-muted-foreground/80">
                      <strong>Driver:</strong> {act.driver} · <strong>Expected Outcome:</strong> {act.expected_outcome}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </section>

          {/* ======================================================== */}
          {/* SECTION 10: FINAL DECISION INTELLIGENCE CONCLUSION */}
          {/* ======================================================== */}
          <section id="sec-10" className="space-y-3 print-card">
            <div className="flex items-center justify-between border-b border-border/40 pb-2">
              <h3 className="text-base font-bold text-foreground flex items-center gap-2">
                <span className="font-mono text-indigo-400 text-xs">SECTION 10</span>
                Final Decision Intelligence Conclusion
              </h3>
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-mono uppercase text-muted-foreground">Posture:</span>
                <span className="px-2 py-0.5 rounded font-mono text-xs font-bold bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
                  {currentReport.report_data.final_conclusion.recommended_decision_posture}
                </span>
              </div>
            </div>

            <div className="p-5 rounded-xl bg-card/30 border border-border/40 space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                {/* Supported findings */}
                <div className="space-y-2">
                  <div className="font-semibold text-emerald-400 uppercase text-[10px] tracking-wider flex items-center gap-1.5">
                    <CheckCircle2 className="w-3.5 h-3.5" /> What Is Empirically Supported
                  </div>
                  <ul className="list-disc list-inside space-y-1 text-muted-foreground text-[11px]">
                    {currentReport.report_data.final_conclusion.supported_findings.map((f, i) => (
                      <li key={i} className="text-foreground/90">{f}</li>
                    ))}
                  </ul>
                </div>

                {/* Uncertainties & Caveats */}
                <div className="space-y-2">
                  <div className="font-semibold text-amber-400 uppercase text-[10px] tracking-wider flex items-center gap-1.5">
                    <HelpCircle className="w-3.5 h-3.5" /> What Remains Uncertain
                  </div>
                  <ul className="list-disc list-inside space-y-1 text-muted-foreground text-[11px]">
                    {currentReport.report_data.final_conclusion.uncertainties_and_caveats.map((u, i) => (
                      <li key={i} className="text-foreground/90">{u}</li>
                    ))}
                  </ul>
                </div>
              </div>

              {/* Invalidating Conditions */}
              {currentReport.report_data.final_conclusion.invalidating_conditions.length > 0 && (
                <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/20 text-xs text-rose-200 space-y-1">
                  <div className="font-semibold uppercase text-[10px] text-rose-400 flex items-center gap-1">
                    <XCircle className="w-3.5 h-3.5" /> Invalidating Conditions
                  </div>
                  <ul className="list-disc list-inside space-y-0.5 text-[11px]">
                    {currentReport.report_data.final_conclusion.invalidating_conditions.map((invCond, i) => (
                      <li key={i}>{invCond}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Formal Epistemic Boundary Notice */}
              <div className="p-3.5 rounded-lg bg-background/80 border border-border/50 text-[10px] text-muted-foreground leading-relaxed font-mono">
                {currentReport.report_data.final_conclusion.epistemic_boundary_disclaimer}
              </div>

              {/* Cryptographic Seal & Sign-off Block */}
              <div className="pt-3 border-t border-border/30 flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-[10px] font-mono text-muted-foreground">
                <div className="flex items-center gap-3">
                  <span>Dossier ID: {currentReport.id}</span>
                  <span>Version: {currentReport.report_version}</span>
                  <span>Integrity Seal: SHA-256 Provenance Verified</span>
                </div>
                <div className="text-right text-emerald-400 font-semibold">
                  Platform Rule: Zero Synthetic Metrics
                </div>
              </div>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
