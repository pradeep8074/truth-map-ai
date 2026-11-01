import { useState, useEffect } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import {
  listInvestigations,
  getInvestigationSources,
  getInvestigationClaims,
  getSourcePassages,
  Investigation,
  Source,
  Claim,
  Passage,
} from "@/lib/api";
import {
  FolderSearch,
  Globe,
  FileText,
  Fingerprint,
  RefreshCw,
  Layers,
  ChevronDown,
  ChevronUp,
  Search,
  PlusCircle,
  ShieldCheck,
  Calendar,
  Clock,
} from "lucide-react";

function getFreshnessBadgeVariant(status?: string): "supported" | "gap" | "unverified" | "conflict" | "neutral" {
  if (status === "Date Available") return "supported";
  if (status === "Potentially Outdated") return "gap";
  if (status === "Undated Source") return "unverified";
  if (status === "Date Requires Review") return "gap";
  if (status === "Date Unavailable") return "conflict";
  return "neutral";
}

export function EvidenceExplorerPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();

  const [investigations, setInvestigations] = useState<Investigation[]>([]);
  const [selectedInvId, setSelectedInvId] = useState<string | null>(null);
  const [sources, setSources] = useState<Source[]>([]);
  const [claims, setClaims] = useState<Claim[]>([]);
  const [activeTab, setActiveTab] = useState<"claims" | "sources">("claims");

  const [isLoading, setIsLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [categoryFilter, setCategoryFilter] = useState<string>("ALL");

  // Passage inspection modal
  const [inspectingSource, setInspectingSource] = useState<Source | null>(null);
  const [passages, setPassages] = useState<Passage[]>([]);
  const [isLoadingPassages, setIsLoadingPassages] = useState(false);
  const [expandedClaimId, setExpandedClaimId] = useState<string | null>(null);

  // 1. Fetch investigations on mount
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

  // 2. Fetch sources and claims when investigation changes
  useEffect(() => {
    if (!selectedInvId) {
      setSources([]);
      setClaims([]);
      return;
    }

    setIsLoading(true);
    Promise.all([
      getInvestigationSources(selectedInvId),
      getInvestigationClaims(selectedInvId),
    ])
      .then(([srcs, clms]) => {
        setSources(srcs);
        setClaims(clms);
      })
      .catch((err) => {
        console.error("Failed to load evidence records", err);
      })
      .finally(() => {
        setIsLoading(false);
      });
  }, [selectedInvId]);

  const handleSelectInvestigation = (id: string) => {
    setSelectedInvId(id);
    setSearchParams({ invId: id });
  };

  const handleInspectPassages = async (source: Source) => {
    setInspectingSource(source);
    setIsLoadingPassages(true);
    try {
      const p = await getSourcePassages(source.id);
      setPassages(p);
    } catch (err) {
      console.error("Failed to load passages", err);
    } finally {
      setIsLoadingPassages(false);
    }
  };

  // Filter claims
  const filteredClaims = claims.filter((c) => {
    const matchesSearch =
      !searchQuery.trim() ||
      c.claim_text.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (c.source_title || "").toLowerCase().includes(searchQuery.toLowerCase());
    const matchesCat =
      categoryFilter === "ALL" ||
      (c.category || "").toUpperCase() === categoryFilter.toUpperCase();
    return matchesSearch && matchesCat;
  });

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-4 border-b border-brand-border/60">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-brand-text flex items-center gap-2.5">
            <FolderSearch className="w-6 h-6 text-brand-teal" />
            Evidence Explorer
          </h1>
          <p className="text-xs sm:text-sm text-brand-textMuted mt-1">
            Browse extracted claims, source quotes, and verification details.
          </p>
        </div>

        {selectedInvId && (
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              if (selectedInvId) {
                setIsLoading(true);
                Promise.all([
                  getInvestigationSources(selectedInvId),
                  getInvestigationClaims(selectedInvId),
                ]).then(([srcs, clms]) => {
                  setSources(srcs);
                  setClaims(clms);
                  setIsLoading(false);
                });
              }
            }}
            leftIcon={<RefreshCw className="w-3.5 h-3.5" />}
          >
            Refresh Evidence
          </Button>
        )}
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

        <div className="flex items-center gap-2 shrink-0">
          <span className="text-[11px] font-mono text-brand-textDim">
            {sources.length} Sources · {claims.length} Claims
          </span>
        </div>
      </div>

      {/* Empty State */}
      {sources.length === 0 && claims.length === 0 && !isLoading ? (
        <div className="p-12 rounded-xl border border-brand-border bg-brand-surface text-center space-y-4">
          <div className="w-12 h-12 rounded-xl bg-[#111B2E] border border-brand-border flex items-center justify-center text-brand-teal mx-auto">
            <ShieldCheck className="w-6 h-6" />
          </div>
          <h3 className="text-sm font-semibold text-brand-text">
            No Evidence Records Ingested
          </h3>
          <p className="text-xs text-brand-textMuted max-w-md mx-auto leading-relaxed">
            This investigation has no ingested sources or extracted claims. Ingest live webpage URLs or PDF documents in New Investigation to extract verifiable evidence.
          </p>
          <Button
            size="sm"
            onClick={() => navigate("/investigations")}
            leftIcon={<PlusCircle className="w-3.5 h-3.5" />}
          >
            Go to New Investigation
          </Button>
        </div>
      ) : (
        <div className="space-y-4">
          {/* Tabs & Filters */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-2 border-b border-brand-border/60">
            <div className="flex items-center gap-2">
              <button
                onClick={() => setActiveTab("claims")}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold font-mono transition-colors ${
                  activeTab === "claims"
                    ? "bg-brand-accent/20 text-brand-accent border border-brand-accent/40"
                    : "text-brand-textMuted hover:text-brand-text bg-brand-surface"
                }`}
              >
                Key Claims ({claims.length})
              </button>
              <button
                onClick={() => setActiveTab("sources")}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold font-mono transition-colors ${
                  activeTab === "sources"
                    ? "bg-brand-accent/20 text-brand-accent border border-brand-accent/40"
                    : "text-brand-textMuted hover:text-brand-text bg-brand-surface"
                }`}
              >
                Sources ({sources.length})
              </button>
            </div>

            {activeTab === "claims" && (
              <div className="flex items-center gap-2">
                <div className="relative">
                  <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-brand-textDim" />
                  <input
                    type="text"
                    placeholder="Filter claims..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="pl-8 pr-3 py-1 rounded bg-[#111B2E] border border-brand-border text-xs text-brand-text placeholder:text-brand-textDim focus:outline-none focus:border-brand-accent font-mono"
                  />
                </div>
                <select
                  value={categoryFilter}
                  onChange={(e) => setCategoryFilter(e.target.value)}
                  className="px-2 py-1 rounded bg-[#111B2E] border border-brand-border text-xs text-brand-text font-mono focus:outline-none"
                >
                  <option value="ALL">All Categories</option>
                  <option value="STATISTICAL">Statistical</option>
                  <option value="EMPIRICAL">Empirical</option>
                  <option value="POLICY">Policy</option>
                  <option value="METHODOLOGICAL">Methodological</option>
                  <option value="FACTUAL">Factual</option>
                </select>
              </div>
            )}
          </div>

          {/* Active Tab Content */}
          {activeTab === "claims" ? (
            <div className="space-y-3">
              {filteredClaims.length === 0 ? (
                <div className="p-8 rounded-xl bg-brand-surface border border-brand-border text-center text-xs text-brand-textMuted font-mono">
                  No claims match the search filter.
                </div>
              ) : (
                filteredClaims.map((c) => (
                  <div
                    key={c.id}
                    className="p-4 rounded-xl border border-brand-border bg-brand-surface space-y-2.5"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="space-y-1 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <Badge variant="teal" size="sm">
                            {(c.category || "GENERAL").toUpperCase()}
                          </Badge>
                          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#111B2E] text-brand-textDim border border-brand-border">
                            CONFIDENCE: {(c.extraction_confidence * 100).toFixed(0)}%
                          </span>
                          <span className="text-[10px] font-mono text-brand-textDim">
                            METHOD: {c.extraction_method}
                          </span>
                        </div>
                        <p className="text-xs text-brand-text font-medium leading-relaxed pt-1">
                          "{c.claim_text}"
                        </p>
                      </div>

                      <button
                        onClick={() =>
                          setExpandedClaimId(expandedClaimId === c.id ? null : c.id)
                        }
                        className="text-brand-textDim hover:text-brand-accent p-1 transition-colors"
                        title="Toggle provenance passage"
                      >
                        {expandedClaimId === c.id ? (
                          <ChevronUp className="w-4 h-4" />
                        ) : (
                          <ChevronDown className="w-4 h-4" />
                        )}
                      </button>
                    </div>

                    <div className="pt-2 border-t border-brand-border/40 flex flex-wrap items-center justify-between gap-2 text-[11px] font-mono text-brand-textDim">
                      <span className="truncate max-w-sm">
                        SOURCE: {c.source_title || "Document"}
                      </span>
                      <span>CLAIM ID: {c.id.slice(0, 8)}...</span>
                    </div>

                    {/* Expanded Passage Provenance */}
                    {expandedClaimId === c.id && c.passage_text && (
                      <div className="mt-2 p-3 rounded-lg bg-[#111B2E] border border-brand-border/80 space-y-1.5 text-xs">
                        <span className="text-[10px] font-mono font-semibold text-brand-teal uppercase block">
                          Supporting Passage Context:
                        </span>
                        <p className="text-slate-300 leading-relaxed italic">
                          "{c.passage_text}"
                        </p>
                        {c.passage_sha256 && (
                          <span className="text-[10px] font-mono text-brand-textDim block pt-1">
                            SHA-256: {c.passage_sha256.slice(0, 24)}...
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>
          ) : (
            /* Sources Tab */
            <div className="space-y-3">
              {sources.map((s) => (
                <div
                  key={s.id}
                  className="p-4 rounded-xl border border-brand-border bg-brand-surface space-y-3"
                >
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

                      {/* Explicit separate display of Publication Date, Ingestion Date & Freshness Status */}
                      <div className="flex flex-wrap items-center gap-2 pt-1 text-[11px] font-mono">
                        <Badge variant={getFreshnessBadgeVariant(s.freshness_status)} size="sm">
                          {s.freshness_status || "Undated Source"}
                        </Badge>
                        <span className="text-brand-text flex items-center gap-1 bg-[#111B2E] px-2 py-0.5 rounded border border-brand-border">
                          <Calendar className="w-3 h-3 text-brand-teal" />
                          Published: <strong className="text-white">{s.publication_date || "Undated"}</strong>
                        </span>
                        <span className="text-brand-textMuted flex items-center gap-1 bg-[#111B2E] px-2 py-0.5 rounded border border-brand-border">
                          <Clock className="w-3 h-3 text-brand-textDim" />
                          Ingested: {s.retrieved_at ? s.retrieved_at.split("T")[0] : "Recorded"}
                        </span>
                        {s.days_old !== undefined && s.days_old !== null && (
                          <span className="text-brand-textDim">({s.days_old} days ago)</span>
                        )}
                      </div>

                      {/* Status Explanation */}
                      {s.freshness_explanation && (
                        <p className="text-[11px] text-brand-textMuted leading-relaxed pt-0.5">
                          {s.freshness_explanation}
                        </p>
                      )}
                    </div>

                    <Button
                      size="xs"
                      variant="outline"
                      onClick={() => handleInspectPassages(s)}
                      leftIcon={<Fingerprint className="w-3.5 h-3.5" />}
                      className="shrink-0"
                    >
                      Inspect Verification
                    </Button>
                  </div>

                  {/* Provenance footer */}
                  <div className="pt-2 border-t border-brand-border/40 text-[11px] font-mono text-brand-textDim flex flex-wrap items-center justify-between gap-3">
                    <div className="flex items-center gap-3">
                      <span>TYPE: {s.source_type.toUpperCase()}</span>
                      <span>PASSAGES: {s.passages_count || 0}</span>
                      <span>CLAIMS: {s.claims_count || 0}</span>
                      {s.date_source && <span>DATE SOURCE: {s.date_source}</span>}
                    </div>
                    {s.content_hash && (
                      <span>SHA-256: {s.content_hash.slice(0, 16)}...</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Provenance Modal */}
      {inspectingSource && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
          <div className="rounded-xl border border-brand-border bg-brand-surface max-w-2xl w-full max-h-[85vh] flex flex-col overflow-hidden shadow-modal animate-slide-down">
            <div className="p-4 px-6 border-b border-brand-border/60 bg-[#141F33] flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Fingerprint className="w-4 h-4 text-brand-teal" />
                <h3 className="text-xs font-semibold text-brand-text font-mono truncate max-w-md">
                  Source Verification: {inspectingSource.title || inspectingSource.original_url}
                </h3>
              </div>
              <button
                onClick={() => setInspectingSource(null)}
                className="text-brand-textDim hover:text-brand-text text-sm font-bold"
              >
                ✕
              </button>
            </div>

            <div className="p-6 overflow-y-auto space-y-4 flex-1">
              {/* Date Metadata & Freshness Verification Panel (Part 2.3) */}
              <div className="p-4 rounded-xl bg-[#111B2E] border border-brand-border space-y-3">
                <div className="flex items-center justify-between pb-2 border-b border-brand-border/60">
                  <div className="flex items-center gap-2">
                    <Calendar className="w-4 h-4 text-brand-teal" />
                    <span className="text-xs font-semibold text-brand-text font-mono uppercase tracking-wider">
                      Date Provenance &amp; Freshness Verification
                    </span>
                  </div>
                  <Badge variant={getFreshnessBadgeVariant(inspectingSource.freshness_status)} size="sm">
                    {inspectingSource.freshness_status || "Undated Source"}
                  </Badge>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5 text-[11px] font-mono">
                  <div className="p-2 rounded bg-brand-surface/60 border border-brand-border/40">
                    <span className="text-brand-textDim block text-[10px]">PUBLICATION DATE</span>
                    <strong className="text-white">{inspectingSource.publication_date || "Undated"}</strong>
                  </div>
                  <div className="p-2 rounded bg-brand-surface/60 border border-brand-border/40">
                    <span className="text-brand-textDim block text-[10px]">INGESTION TIMESTAMP</span>
                    <strong className="text-slate-300">{inspectingSource.retrieved_at.split(".")[0]}</strong>
                  </div>
                  <div className="p-2 rounded bg-brand-surface/60 border border-brand-border/40">
                    <span className="text-brand-textDim block text-[10px]">MODIFIED DATE</span>
                    <span className="text-slate-300">{inspectingSource.source_modified_date || "N/A"}</span>
                  </div>
                  <div className="p-2 rounded bg-brand-surface/60 border border-brand-border/40">
                    <span className="text-brand-textDim block text-[10px]">EXTRACTION ORIGIN</span>
                    <span className="text-brand-teal truncate block">{inspectingSource.date_source || "N/A"}</span>
                  </div>
                  <div className="p-2 rounded bg-brand-surface/60 border border-brand-border/40">
                    <span className="text-brand-textDim block text-[10px]">EXTRACTION METHOD</span>
                    <span className="text-slate-300">{inspectingSource.date_extraction_method || "N/A"}</span>
                  </div>
                  <div className="p-2 rounded bg-brand-surface/60 border border-brand-border/40">
                    <span className="text-brand-textDim block text-[10px]">VALIDATION STATUS</span>
                    <span className="text-amber-400">{inspectingSource.date_validation_status || "MISSING"}</span>
                  </div>
                </div>

                {inspectingSource.freshness_explanation && (
                  <p className="text-[11px] text-brand-textMuted leading-relaxed pt-1 border-t border-brand-border/40">
                    {inspectingSource.freshness_explanation}
                  </p>
                )}
              </div>

              <div className="text-xs font-semibold text-brand-text font-mono uppercase tracking-wider pt-2 flex items-center gap-2">
                <Fingerprint className="w-3.5 h-3.5 text-brand-accent" /> Segmented Passages &amp; Cryptographic Hashes:
              </div>
              {isLoadingPassages ? (
                <div className="py-8 text-center text-xs text-brand-textMuted font-mono">
                  Loading source quotes and verification...
                </div>
              ) : passages.length === 0 ? (
                <div className="py-6 text-center text-xs text-brand-textMuted font-mono">
                  No passages segmented for this source.
                </div>
              ) : (
                passages.map((p) => (
                  <div
                    key={p.id}
                    className="p-3.5 rounded-lg bg-[#111B2E] border border-brand-border/60 space-y-2 text-xs"
                  >
                    <p className="text-slate-200 leading-relaxed font-sans">
                      {p.passage_text}
                    </p>
                    <div className="pt-2 border-t border-brand-border/40 flex flex-wrap items-center justify-between text-[10px] font-mono text-brand-textDim gap-2">
                      <span>
                        {p.page_number ? `PAGE: ${p.page_number}` : "WEB ARTICLE"} · PARA: {p.paragraph_index} · OFFSETS: [{p.start_offset}:{p.end_offset}]
                      </span>
                      <span className="text-brand-teal">
                        SHA-256: {p.sha256_hash.slice(0, 16)}...
                      </span>
                    </div>
                  </div>
                ))
              )}
            </div>

            <div className="p-3 px-6 bg-[#0E1726] border-t border-brand-border/60 flex justify-end">
              <Button size="xs" variant="outline" onClick={() => setInspectingSource(null)}>
                Close
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
