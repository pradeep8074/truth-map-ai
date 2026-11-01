import { useState, useEffect, useMemo } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Button } from "@/components/ui/Button";
import {
  listInvestigations,
  getInvestigationSources,
  getInvestigationClaims,
  getInvestigationConflicts,
  Investigation,
  Source,
  Claim,
  ConflictItem,
} from "@/lib/api";
import {
  History,
  ArrowLeft,
  Calendar,
  AlertTriangle,
  TrendingDown,
  Layers,
  ArrowUpDown,
  HelpCircle,
  ExternalLink,
  Globe,
  FileText,
} from "lucide-react";

export function TemporalPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const [investigations, setInvestigations] = useState<Investigation[]>([]);
  const [selectedInvId, setSelectedInvId] = useState<string | null>(null);
  const [sources, setSources] = useState<Source[]>([]);
  const [claims, setClaims] = useState<Claim[]>([]);
  const [conflicts, setConflicts] = useState<ConflictItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  // Filters & Controls
  const [statusFilter, setStatusFilter] = useState<string>("ALL");
  const [sortOrder, setSortOrder] = useState<"desc" | "asc">("desc");
  const [halfLifeDays, setHalfLifeDays] = useState<number>(365);
  const [selectedSourceId, setSelectedSourceId] = useState<string | null>(null);

  // 1. Fetch investigations
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
        console.error("Failed to load investigations", err);
      });
    return () => {
      isMounted = false;
    };
  }, [searchParams]);

  // 2. Fetch sources, claims, and conflicts for selected investigation
  useEffect(() => {
    if (!selectedInvId) {
      setSources([]);
      setClaims([]);
      setConflicts([]);
      return;
    }

    setIsLoading(true);
    Promise.all([
      getInvestigationSources(selectedInvId),
      getInvestigationClaims(selectedInvId),
      getInvestigationConflicts(selectedInvId).then((r) => r.conflicts).catch(() => []),
    ])
      .then(([srcs, clms, confls]) => {
        setSources(srcs);
        setClaims(clms);
        setConflicts(confls);
      })
      .catch((err) => {
        console.error("Failed to load temporal data", err);
      })
      .finally(() => {
        setIsLoading(false);
      });
  }, [selectedInvId]);

  const handleSelectInvestigation = (id: string) => {
    setSelectedInvId(id);
    setSearchParams({ invId: id });
  };

  // Calculate decay factor for each source
  const calculateDecay = (daysOld?: number | null) => {
    if (daysOld === undefined || daysOld === null) return 0.70; // unverified provisional decay
    if (daysOld <= 0) return 1.0;
    const decayRate = Math.LN2 / Math.max(1, halfLifeDays);
    const val = Math.exp(-decayRate * daysOld);
    return Math.max(0.10, Math.min(1.00, Number(val.toFixed(3))));
  };

  // Separate dated sources and undated sources
  const datedSources = useMemo(() => {
    return sources.filter((s) => s.publication_date && s.publication_date.trim().length > 0);
  }, [sources]);

  const undatedSources = useMemo(() => {
    return sources.filter((s) => !s.publication_date || s.publication_date.trim().length === 0);
  }, [sources]);

  // Chronologically sorted dated sources
  const sortedDatedSources = useMemo(() => {
    return [...datedSources].sort((a, b) => {
      const timeA = new Date(a.publication_date || "").getTime() || 0;
      const timeB = new Date(b.publication_date || "").getTime() || 0;
      return sortOrder === "desc" ? timeB - timeA : timeA - timeB;
    });
  }, [datedSources, sortOrder]);

  // Filtered list
  const filteredSources = useMemo(() => {
    if (statusFilter === "ALL") return sortedDatedSources;
    if (statusFilter === "UNDATED") return undatedSources;
    return sortedDatedSources.filter((s) => s.freshness_status === statusFilter);
  }, [sortedDatedSources, undatedSources, statusFilter]);

  // Temporal conflicts
  const temporalConflicts = useMemo(() => {
    return conflicts.filter((c) => c.conflict_type === "TEMPORAL_CONFLICT");
  }, [conflicts]);

  // Counts
  const datedCount = datedSources.length;
  const undatedCount = undatedSources.length;
  const outdatedCount = sources.filter((s) => s.freshness_status === "Potentially Outdated").length;
  const reviewCount = sources.filter(
    (s) => s.freshness_status === "Date Requires Review" || s.freshness_status === "Date Unavailable"
  ).length;

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-4 border-b border-brand-border/60">
        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            size="sm"
            onClick={() => navigate("/")}
            leftIcon={<ArrowLeft className="w-3.5 h-3.5" />}
          >
            Command Center
          </Button>
          <div className="h-4 w-[1px] bg-brand-border" />
          <h1 className="text-xl font-bold tracking-tight text-brand-text flex items-center gap-2">
            <History className="w-5 h-5 text-brand-teal" />
            Timeline &amp; Freshness Intelligence
          </h1>
        </div>

        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="outline"
            onClick={() => navigate("/evidence-explorer")}
            leftIcon={<ExternalLink className="w-3.5 h-3.5" />}
          >
            Evidence Explorer
          </Button>
        </div>
      </div>

      {/* Target Investigation Selector */}
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
                  {inv.research_question}
                </option>
              ))}
            </select>
          )}
        </div>

        <div className="flex items-center gap-3 shrink-0 text-[11px] font-mono text-brand-textDim">
          <span>{sources.length} Total Sources</span>
          <span>·</span>
          <span>{claims.length} Extracted Claims</span>
        </div>
      </div>

      {/* KPI Cards — Derived 100% from real source records */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="p-4 rounded-xl bg-brand-surface border border-brand-border space-y-1">
          <span className="text-[10px] font-mono text-brand-textDim uppercase flex items-center gap-1.5">
            <Calendar className="w-3.5 h-3.5 text-brand-teal" /> Dated Sources
          </span>
          <div className="text-2xl font-bold font-mono text-brand-text">
            {datedCount} <span className="text-xs text-brand-textDim font-normal">/ {sources.length}</span>
          </div>
          <span className="text-[10px] text-brand-textDim block">Tracked on timeline</span>
        </div>

        <div className="p-4 rounded-xl bg-brand-surface border border-brand-border space-y-1">
          <span className="text-[10px] font-mono text-brand-textDim uppercase flex items-center gap-1.5">
            <HelpCircle className="w-3.5 h-3.5 text-amber-400" /> Undated Sources
          </span>
          <div className="text-2xl font-bold font-mono text-amber-400">
            {undatedCount}
          </div>
          <span className="text-[10px] text-brand-textDim block">Missing publication date</span>
        </div>

        <div className="p-4 rounded-xl bg-brand-surface border border-brand-border space-y-1">
          <span className="text-[10px] font-mono text-brand-textDim uppercase flex items-center gap-1.5">
            <TrendingDown className="w-3.5 h-3.5 text-amber-400" /> Potentially Outdated
          </span>
          <div className="text-2xl font-bold font-mono text-amber-400">
            {outdatedCount}
          </div>
          <span className="text-[10px] text-brand-textDim block">&gt;365 days old threshold</span>
        </div>

        <div className="p-4 rounded-xl bg-brand-surface border border-brand-border space-y-1">
          <span className="text-[10px] font-mono text-brand-textDim uppercase flex items-center gap-1.5">
            <AlertTriangle className="w-3.5 h-3.5 text-rose-400" /> Temporal Conflicts
          </span>
          <div className="text-2xl font-bold font-mono text-rose-400">
            {temporalConflicts.length}
          </div>
          <span className="text-[10px] text-brand-textDim block">
            {reviewCount > 0 ? `${reviewCount} date review(s) needed` : "Chronological clashes"}
          </span>
        </div>
      </div>

      {/* Interactive Temporal Half-Life Decay Control */}
      <div className="p-5 rounded-xl border border-brand-border bg-brand-surface space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-brand-border/60">
          <div className="flex items-center gap-2">
            <TrendingDown className="w-4 h-4 text-brand-accent" />
            <h3 className="text-sm font-semibold text-brand-text">
              Exponential Evidence Confidence Decay Model (D(t) = e<sup>-λt</sup>)
            </h3>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-mono text-brand-textDim">Half-Life Window (T<sub>half</sub>):</span>
            <div className="flex items-center rounded-lg border border-brand-border bg-[#111B2E] p-0.5 text-xs font-mono">
              <button
                onClick={() => setHalfLifeDays(180)}
                className={`px-2.5 py-1 rounded transition-colors ${
                  halfLifeDays === 180
                    ? "bg-brand-accent text-white font-semibold"
                    : "text-brand-textDim hover:text-brand-text"
                }`}
              >
                180d (Fast Tech)
              </button>
              <button
                onClick={() => setHalfLifeDays(365)}
                className={`px-2.5 py-1 rounded transition-colors ${
                  halfLifeDays === 365
                    ? "bg-brand-accent text-white font-semibold"
                    : "text-brand-textDim hover:text-brand-text"
                }`}
              >
                365d (Standard)
              </button>
              <button
                onClick={() => setHalfLifeDays(730)}
                className={`px-2.5 py-1 rounded transition-colors ${
                  halfLifeDays === 730
                    ? "bg-brand-accent text-white font-semibold"
                    : "text-brand-textDim hover:text-brand-text"
                }`}
              >
                730d (Macro/Policy)
              </button>
            </div>
          </div>
        </div>
        <p className="text-xs text-brand-textMuted leading-relaxed">
          Confidence attenuates exponentially as evidence ages without newer corroboration. Older sources are not discarded or deemed false, but their effective evidentiary weight is scaled down to reflect potential regulatory or environmental shifts.
        </p>
      </div>

      {/* Temporal Conflicts Banner (if any detected) */}
      {temporalConflicts.length > 0 && (
        <div className="p-4 rounded-xl border border-rose-500/30 bg-rose-950/20 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-rose-300 font-semibold text-xs">
              <AlertTriangle className="w-4 h-4 text-rose-400" />
              {temporalConflicts.length} Active Temporal Conflict(s) Detected
            </div>
            <Button
              size="xs"
              variant="outline"
              onClick={() => navigate("/conflict-intelligence")}
              className="text-xs border-rose-800 text-rose-300 hover:bg-rose-950"
            >
              Resolve in Conflicting Evidence
            </Button>
          </div>
          <div className="space-y-2">
            {temporalConflicts.map((c) => (
              <div key={c.conflict_id} className="p-3 rounded-lg bg-[#111B2E] border border-rose-900/40 text-xs space-y-1">
                <div className="text-slate-300">{c.explanation}</div>
                <div className="text-[10px] font-mono text-brand-textDim">
                  SEVERITY: {c.severity} · STATUS: {c.resolution_status}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Controls Bar: Filters & Sort */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-2 border-b border-brand-border/60">
        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={() => setStatusFilter("ALL")}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold font-mono transition-colors ${
              statusFilter === "ALL"
                ? "bg-brand-accent/20 text-brand-accent border border-brand-accent/40"
                : "text-brand-textMuted hover:text-brand-text bg-brand-surface"
            }`}
          >
            All Dated Sources ({datedCount})
          </button>
          <button
            onClick={() => setStatusFilter("Date Available")}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold font-mono transition-colors ${
              statusFilter === "Date Available"
                ? "bg-emerald-950/60 text-emerald-400 border border-emerald-700"
                : "text-brand-textMuted hover:text-brand-text bg-brand-surface"
            }`}
          >
            Fresh (≤365d)
          </button>
          <button
            onClick={() => setStatusFilter("Potentially Outdated")}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold font-mono transition-colors ${
              statusFilter === "Potentially Outdated"
                ? "bg-amber-950/60 text-amber-400 border border-amber-700"
                : "text-brand-textMuted hover:text-brand-text bg-brand-surface"
            }`}
          >
            Potentially Outdated ({outdatedCount})
          </button>
          <button
            onClick={() => setStatusFilter("UNDATED")}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold font-mono transition-colors ${
              statusFilter === "UNDATED"
                ? "bg-slate-800 text-slate-200 border border-slate-600"
                : "text-brand-textMuted hover:text-brand-text bg-brand-surface"
            }`}
          >
            Undated Repository ({undatedCount})
          </button>
        </div>

        <button
          onClick={() => setSortOrder(sortOrder === "desc" ? "asc" : "desc")}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-mono text-brand-textMuted hover:text-brand-text bg-brand-surface border border-brand-border self-start sm:self-auto"
        >
          <ArrowUpDown className="w-3.5 h-3.5" />
          {sortOrder === "desc" ? "Newest First" : "Oldest First"}
        </button>
      </div>

      {/* Main Content Area */}
      {sources.length === 0 && !isLoading ? (
        <div className="p-12 rounded-xl border border-brand-border bg-brand-surface text-center space-y-4">
          <div className="w-12 h-12 rounded-xl bg-[#111B2E] border border-brand-border flex items-center justify-center text-brand-teal mx-auto">
            <History className="w-6 h-6" />
          </div>
          <h3 className="text-sm font-semibold text-brand-text">
            No Sources Ingested for this Investigation
          </h3>
          <p className="text-xs text-brand-textMuted max-w-md mx-auto leading-relaxed">
            Ingest live webpage URLs or PDF documents in New Investigation to evaluate timeline vintage and time-decay curves.
          </p>
          <Button size="sm" onClick={() => navigate("/investigations")}>
            Go to New Investigation
          </Button>
        </div>
      ) : statusFilter === "UNDATED" ? (
        /* Undated Sources Repository */
        <div className="space-y-3">
          <div className="p-3 bg-amber-950/30 border border-amber-800/50 rounded-lg text-xs text-amber-300 flex items-center gap-2">
            <HelpCircle className="w-4 h-4 text-amber-400 shrink-0" />
            <span>
              These {undatedCount} source(s) lack explicit publication dates in their HTML/PDF metadata. Verify vintage manually before citing time-sensitive facts.
            </span>
          </div>

          {undatedSources.map((s) => (
            <div
              key={s.id}
              className="p-4 rounded-xl border border-brand-border bg-brand-surface space-y-2"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    {s.source_type === "web" ? (
                      <Globe className="w-4 h-4 text-brand-teal" />
                    ) : (
                      <FileText className="w-4 h-4 text-brand-accent" />
                    )}
                    <h4 className="text-xs font-semibold text-brand-text">
                      {s.title || s.original_url}
                    </h4>
                    <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-slate-900 text-slate-400 border border-slate-700">
                      Undated Source
                    </span>
                  </div>
                  <div className="text-[11px] font-mono text-brand-textDim">
                    INGESTED: {s.retrieved_at.split("T")[0]} · PASSAGES: {s.passages_count} · CLAIMS: {s.claims_count}
                  </div>
                </div>

                <Button
                  size="xs"
                  variant="outline"
                  onClick={() => navigate(`/evidence-explorer?invId=${selectedInvId}`)}
                >
                  View Claims
                </Button>
              </div>
            </div>
          ))}
        </div>
      ) : (
        /* Chronological Timeline */
        <div className="relative pl-6 space-y-6 before:absolute before:left-2.5 before:top-3 before:bottom-3 before:w-[2px] before:bg-brand-border">
          {filteredSources.length === 0 ? (
            <div className="p-8 text-center text-xs text-brand-textMuted border border-dashed border-brand-border rounded-xl">
              No sources match the selected freshness filter.
            </div>
          ) : (
            filteredSources.map((s) => {
              const decayFactor = calculateDecay(s.days_old);
              const relatedClaims = claims.filter((c) => c.source_id === s.id);
              const isSelected = selectedSourceId === s.id;

              return (
                <div key={s.id} className="relative group">
                  {/* Timeline Dot */}
                  <div className={`absolute -left-[27px] top-4 w-3.5 h-3.5 rounded-full border-2 bg-brand-surface ${
                    s.freshness_status === "Date Available"
                      ? "border-emerald-500 bg-emerald-950"
                      : s.freshness_status === "Potentially Outdated"
                      ? "border-amber-500 bg-amber-950"
                      : "border-sky-500 bg-sky-950"
                  }`} />

                  {/* Card Container */}
                  <div className="p-4 rounded-xl border border-brand-border bg-brand-surface space-y-3 hover:border-slate-600 transition-colors">
                    <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
                      <div className="space-y-1.5 flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          {s.source_type === "web" ? (
                            <Globe className="w-4 h-4 text-brand-teal shrink-0" />
                          ) : (
                            <FileText className="w-4 h-4 text-brand-accent shrink-0" />
                          )}
                          <h4 className="text-xs font-semibold text-brand-text truncate">
                            {s.title || s.original_url}
                          </h4>
                        </div>

                        {/* Dates & Freshness Badge */}
                        <div className="flex flex-wrap items-center gap-2 text-[11px] font-mono">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-semibold border ${
                            s.freshness_status === "Date Available"
                              ? "bg-emerald-950/60 text-emerald-400 border-emerald-800"
                              : s.freshness_status === "Potentially Outdated"
                              ? "bg-amber-950/60 text-amber-400 border-amber-800"
                              : "bg-sky-950/60 text-sky-400 border-sky-800"
                          }`}>
                            {s.freshness_status}
                          </span>
                          <span className="text-white flex items-center gap-1 bg-[#111B2E] px-2 py-0.5 rounded border border-brand-border">
                            <Calendar className="w-3 h-3 text-brand-teal" />
                            Published: <strong>{s.publication_date}</strong>
                          </span>
                          {s.days_old !== undefined && s.days_old !== null && (
                            <span className="text-brand-textDim">
                              ({s.days_old} days elapsed)
                            </span>
                          )}
                          <span className="text-brand-textDim">
                            Ingested: {s.retrieved_at.split("T")[0]}
                          </span>
                        </div>

                        {/* Status explanation */}
                        {s.freshness_explanation && (
                          <p className="text-[11px] text-brand-textMuted leading-relaxed">
                            {s.freshness_explanation}
                          </p>
                        )}
                      </div>

                      {/* Decay Factor Meter */}
                      <div className="shrink-0 p-2.5 rounded-lg bg-[#111B2E] border border-brand-border text-right min-w-[140px] space-y-1">
                        <span className="text-[10px] font-mono text-brand-textDim block">
                          CONFIDENCE RETENTION
                        </span>
                        <div className="text-base font-bold font-mono text-brand-text flex items-center justify-end gap-1.5">
                          <span className={decayFactor >= 0.7 ? "text-emerald-400" : "text-amber-400"}>
                            {(decayFactor * 100).toFixed(0)}%
                          </span>
                          <span className="text-[10px] text-brand-textDim font-normal">
                            (D={decayFactor.toFixed(2)})
                          </span>
                        </div>
                        <div className="w-full bg-slate-800 rounded-full h-1.5 overflow-hidden">
                          <div
                            className={`h-full ${
                              decayFactor >= 0.7 ? "bg-emerald-500" : "bg-amber-500"
                            }`}
                            style={{ width: `${decayFactor * 100}%` }}
                          />
                        </div>
                      </div>
                    </div>

                    {/* Associated Claims Accordion / Preview */}
                    <div className="pt-2 border-t border-brand-border/40 flex items-center justify-between text-[11px] font-mono text-brand-textDim">
                      <span>{relatedClaims.length} extracted claims linked to this publication vintage</span>
                      <button
                        onClick={() => setSelectedSourceId(isSelected ? null : s.id)}
                        className="text-brand-accent hover:text-brand-accentHover font-semibold cursor-pointer"
                      >
                        {isSelected ? "Hide Claims ▲" : "View Claims ▼"}
                      </button>
                    </div>

                    {isSelected && (
                      <div className="mt-2 space-y-2 pt-2 border-t border-brand-border/30">
                        {relatedClaims.length === 0 ? (
                          <div className="text-xs text-brand-textDim italic">No claims extracted for this source.</div>
                        ) : (
                          relatedClaims.map((c) => (
                            <div key={c.id} className="p-2.5 rounded bg-[#111B2E] border border-brand-border/60 text-xs text-slate-300">
                              &ldquo;{c.claim_text}&rdquo;
                              <div className="text-[10px] font-mono text-brand-textDim mt-1 flex items-center gap-2">
                                <span>CONFIDENCE: {(c.extraction_confidence * 100).toFixed(0)}%</span>
                                <span>·</span>
                                <span>ID: {c.id.slice(0, 8)}...</span>
                              </div>
                            </div>
                          ))
                        )}
                      </div>
                    )}
                  </div>
                </div>
              );
            })
          )}
        </div>
      )}
    </div>
  );
}
