import { useState, useRef } from "react";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import {
  createInvestigation,
  uploadPdfsToInvestigation,
  getInvestigationSources,
  getInvestigationClaims,
  getSourcePassages,
  Source,
  Claim,
  Passage,
} from "@/lib/api";
import {
  PlusCircle,
  Globe,
  FileText,
  Trash2,
  Plus,
  Loader2,
  AlertTriangle,
  FileCode,
  Fingerprint,
  ChevronDown,
  ChevronUp,
  Search,
  Upload,
  RefreshCw,
  Layers,
  ArrowRight
} from "lucide-react";

export function InvestigationPage() {
  // Input form state
  const [researchQuestion, setResearchQuestion] = useState("");
  const [urls, setUrls] = useState<string[]>([""]);
  const [selectedPdfs, setSelectedPdfs] = useState<File[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  // Active investigation state
  const [activeInvestigationId, setActiveInvestigationId] = useState<string | null>(null);
  const [sources, setSources] = useState<Source[]>([]);
  const [claims, setClaims] = useState<Claim[]>([]);
  const [activeTab, setActiveTab] = useState<"sources" | "claims">("sources");

  // Provenance inspector modal state
  const [inspectingSource, setInspectingSource] = useState<Source | null>(null);
  const [passages, setPassages] = useState<Passage[]>([]);
  const [isLoadingPassages, setIsLoadingPassages] = useState(false);

  // Expanded claims for passage view
  const [expandedClaimId, setExpandedClaimId] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  // URL input management
  const handleUrlChange = (index: number, value: string) => {
    const updated = [...urls];
    updated[index] = value;
    setUrls(updated);
  };

  const addUrlField = () => {
    setUrls([...urls, ""]);
  };

  const removeUrlField = (index: number) => {
    if (urls.length === 1) {
      setUrls([""]);
    } else {
      setUrls(urls.filter((_, i) => i !== index));
    }
  };

  // PDF file upload management
  const handlePdfChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const newFiles = Array.from(e.target.files).filter((file) => {
        if (!file.name.toLowerCase().endsWith(".pdf")) {
          alert(`File '${file.name}' is not a PDF.`);
          return false;
        }
        if (file.size > 25 * 1024 * 1024) {
          alert(`File '${file.name}' exceeds the 25MB limit.`);
          return false;
        }
        return true;
      });
      setSelectedPdfs((prev) => [...prev, ...newFiles]);
    }
  };

  const removePdf = (index: number) => {
    setSelectedPdfs(selectedPdfs.filter((_, i) => i !== index));
  };

  // Validation
  const isValidUrl = (urlStr: string) => {
    if (!urlStr.trim()) return true;
    try {
      const u = new URL(urlStr.trim());
      return u.protocol === "http:" || u.protocol === "https:";
    } catch {
      return false;
    }
  };

  // Submit pipeline
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitError(null);

    const cleanQuestion = researchQuestion.trim();
    if (cleanQuestion.length < 5) {
      setSubmitError("Please provide a specific research question (minimum 5 characters).");
      return;
    }

    const validUrls = urls.map((u) => u.trim()).filter((u) => u.length > 0);
    for (const u of validUrls) {
      if (!isValidUrl(u)) {
        setSubmitError(`Invalid URL format: '${u}'. Must start with http:// or https://`);
        return;
      }
    }

    if (validUrls.length === 0 && selectedPdfs.length === 0) {
      setSubmitError("Please provide at least one source (live webpage URL or PDF document) to ingest.");
      return;
    }

    setIsSubmitting(true);

    try {
      // 1. Create Investigation
      const invRes = await createInvestigation(cleanQuestion, validUrls);
      const invId = invRes.investigation_id;
      setActiveInvestigationId(invId);

      // 2. Upload PDFs if provided
      if (selectedPdfs.length > 0) {
        await uploadPdfsToInvestigation(invId, selectedPdfs);
      }

      // 3. Poll/Fetch sources and claims
      const updatedSources = await getInvestigationSources(invId);
      const updatedClaims = await getInvestigationClaims(invId);

      setSources(updatedSources);
      setClaims(updatedClaims);
      if (updatedClaims.length > 0) {
        setActiveTab("claims");
      }
    } catch (err: any) {
      setSubmitError(err.message || "Failed to initialize investigation and ingest sources.");
    } finally {
      setIsSubmitting(false);
    }
  };

  // Reload current investigation data
  const refreshInvestigationData = async () => {
    if (!activeInvestigationId) return;
    try {
      const s = await getInvestigationSources(activeInvestigationId);
      const c = await getInvestigationClaims(activeInvestigationId);
      setSources(s);
      setClaims(c);
    } catch (err) {
      console.error("Failed to refresh investigation data", err);
    }
  };

  // Inspect source passages
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

  return (
    <div className="space-y-8 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-4 border-b border-brand-border/60">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-brand-text">
            Start an Investigation
          </h1>
          <p className="text-xs sm:text-sm text-brand-textMuted mt-1">
            Add web links and PDF documents to extract key claims and verify sources.
          </p>
        </div>

        {activeInvestigationId && (
          <Button
            variant="outline"
            size="sm"
            onClick={refreshInvestigationData}
            leftIcon={<RefreshCw className="w-3.5 h-3.5" />}
          >
            Refresh Evidence
          </Button>
        )}
      </div>

      {/* Main Grid: Form on Top or Left, Results Below */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Left Form: Ingestion Control (5 Cols) */}
        <div className="lg:col-span-5 space-y-6">
          <form
            onSubmit={handleSubmit}
            className="rounded-xl border border-brand-border bg-brand-surface p-6 shadow-subtle space-y-5"
          >
            <div className="flex items-center gap-2 pb-3 border-b border-brand-border/60">
              <PlusCircle className="w-4 h-4 text-brand-accent" />
              <h2 className="text-sm font-semibold text-brand-text font-mono uppercase tracking-wider">
                Investigation Setup
              </h2>
            </div>

            {/* Research Question Input */}
            <div className="space-y-2">
              <label className="text-xs font-semibold text-brand-text flex items-center justify-between">
                <span>Investigation Question</span>
                <span className="text-[10px] font-mono text-brand-textDim">Required</span>
              </label>
              <textarea
                value={researchQuestion}
                onChange={(e) => setResearchQuestion(e.target.value)}
                placeholder="What decision or question do you want to investigate? (e.g. Should we approve the vendor contract based on compliance and security standards?)"
                rows={3}
                className="w-full rounded-md border border-brand-border bg-[#111B2E] p-3 text-xs text-brand-text placeholder:text-brand-textDim/60 focus:border-brand-accent focus:outline-none focus:ring-1 focus:ring-brand-accent resize-none"
              />
            </div>

            {/* Web URLs Section */}
            <div className="space-y-2.5">
              <div className="flex items-center justify-between">
                <label className="text-xs font-semibold text-brand-text flex items-center gap-1.5">
                  <Globe className="w-3.5 h-3.5 text-brand-teal" />
                  <span>Web Links</span>
                </label>
                <button
                  type="button"
                  onClick={addUrlField}
                  className="text-[11px] font-mono text-brand-accent hover:text-brand-accentHover flex items-center gap-1 cursor-pointer"
                >
                  <Plus className="w-3.5 h-3.5" /> Add URL
                </button>
              </div>

              <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
                {urls.map((url, idx) => (
                  <div key={idx} className="flex items-center gap-2">
                    <input
                      type="url"
                      value={url}
                      onChange={(e) => handleUrlChange(idx, e.target.value)}
                      placeholder="https://example.org/article-or-report"
                      className="flex-1 rounded-md border border-brand-border bg-[#111B2E] px-3 py-1.5 text-xs text-brand-text placeholder:text-brand-textDim/60 focus:border-brand-accent focus:outline-none font-mono"
                    />
                    <button
                      type="button"
                      onClick={() => removeUrlField(idx)}
                      className="p-1.5 text-brand-textDim hover:text-rose-400 hover:bg-[#111B2E] rounded transition-colors"
                      title="Remove URL"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ))}
              </div>
            </div>

            {/* PDF Upload Section */}
            <div className="space-y-2.5">
              <label className="text-xs font-semibold text-brand-text flex items-center gap-1.5">
                <FileText className="w-3.5 h-3.5 text-brand-accent" />
                <span>PDF Documents (Max 25MB each)</span>
              </label>

              <div
                onClick={() => fileInputRef.current?.click()}
                className="border border-dashed border-brand-border rounded-lg p-4 bg-[#111B2E]/50 hover:bg-[#111B2E] transition-colors cursor-pointer text-center flex flex-col items-center justify-center gap-1"
              >
                <Upload className="w-5 h-5 text-brand-textDim mb-1" />
                <span className="text-xs font-medium text-brand-text">
                  Click to select PDF files
                </span>
                <span className="text-[10px] font-mono text-brand-textDim">
                  Extracts text and page numbers from documents
                </span>
                <input
                  ref={fileInputRef}
                  type="file"
                  multiple
                  accept=".pdf,application/pdf"
                  onChange={handlePdfChange}
                  className="hidden"
                />
              </div>

              {/* Selected PDF Pills */}
              {selectedPdfs.length > 0 && (
                <div className="space-y-1.5">
                  {selectedPdfs.map((file, idx) => (
                    <div
                      key={idx}
                      className="flex items-center justify-between p-2 rounded bg-[#111B2E] border border-brand-border text-xs"
                    >
                      <div className="flex items-center gap-2 truncate">
                        <FileCode className="w-3.5 h-3.5 text-brand-teal shrink-0" />
                        <span className="truncate text-brand-text font-mono text-[11px]">
                          {file.name}
                        </span>
                        <span className="text-[10px] font-mono text-brand-textDim shrink-0">
                          ({(file.size / (1024 * 1024)).toFixed(2)} MB)
                        </span>
                      </div>
                      <button
                        type="button"
                        onClick={() => removePdf(idx)}
                        className="text-brand-textDim hover:text-rose-400 p-1"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Error Message */}
            {submitError && (
              <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-start gap-2">
                <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5 text-rose-400" />
                <div className="leading-relaxed">{submitError}</div>
              </div>
            )}

            {/* Submit Action */}
            <Button
              type="submit"
              disabled={isSubmitting}
              isLoading={isSubmitting}
              className="w-full shadow-glow-blue"
              size="md"
              leftIcon={<PlusCircle className="w-4 h-4" />}
            >
              {isSubmitting ? "Extracting Claims..." : "Start Investigation & Extract Claims"}
            </Button>

            {/* Security Guarantee Note */}
            <div className="pt-2 border-t border-brand-border/40 text-[10px] font-mono text-brand-textDim flex items-center justify-between">
              <span>SECURE INGESTION</span>
              <span>VERIFIED SOURCE HASHES</span>
            </div>
          </form>
        </div>

        {/* Right Output: Ingested Sources & Claims Viewer (7 Cols) */}
        <div className="lg:col-span-7 space-y-4">
          {/* Status Header & Tabs */}
          <div className="rounded-xl border border-brand-border bg-brand-surface p-4 shadow-subtle flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <Layers className="w-4 h-4 text-brand-teal" />
              <h3 className="text-sm font-semibold text-brand-text font-mono uppercase tracking-wider">
                Extracted Evidence
              </h3>
            </div>

            {/* Navigation Tabs */}
            <div className="flex items-center gap-1.5 p-1 bg-[#111B2E] rounded-lg border border-brand-border text-xs">
              <button
                onClick={() => setActiveTab("sources")}
                className={`px-3 py-1 rounded-md font-mono text-xs transition-colors cursor-pointer ${
                  activeTab === "sources"
                    ? "bg-brand-surface text-brand-text font-semibold border border-brand-borderHighlight/40"
                    : "text-brand-textMuted hover:text-brand-text"
                }`}
              >
                Sources ({sources.length})
              </button>
              <button
                onClick={() => setActiveTab("claims")}
                className={`px-3 py-1 rounded-md font-mono text-xs transition-colors cursor-pointer ${
                  activeTab === "claims"
                    ? "bg-brand-surface text-brand-text font-semibold border border-brand-borderHighlight/40"
                    : "text-brand-textMuted hover:text-brand-text"
                }`}
              >
                Key Claims ({claims.length})
              </button>
            </div>
          </div>

          {/* Zero State if nothing created yet */}
          {!activeInvestigationId && !isSubmitting && (
            <div className="rounded-xl border border-dashed border-brand-border bg-brand-surface/30 p-12 text-center flex flex-col items-center justify-center">
              <div className="w-12 h-12 rounded-xl bg-[#111B2E] border border-brand-border flex items-center justify-center text-brand-textDim mb-3">
                <Search className="w-6 h-6" />
              </div>
              <h4 className="text-sm font-semibold text-brand-text mb-1">
                Ready to Start
              </h4>
              <p className="text-xs text-brand-textMuted max-w-md leading-relaxed">
                Enter your question, add web links or PDF documents, and click
                &ldquo;Start Investigation &amp; Extract Claims&rdquo; to begin.
              </p>
            </div>
          )}

          {/* Loading Indicator */}
          {isSubmitting && (
            <div className="rounded-xl border border-brand-border bg-brand-surface p-12 text-center flex flex-col items-center justify-center space-y-3">
              <Loader2 className="w-8 h-8 text-brand-accent animate-spin" />
              <div className="text-sm font-semibold text-brand-text">
                Processing Documents & Extracting Claims...
              </div>
              <div className="text-xs font-mono text-brand-teal max-w-sm">
                Reading web pages · Parsing PDF text · Extracting claims · Verifying citations
              </div>
            </div>
          )}

          {/* TAB 1: Sources List */}
          {activeInvestigationId && activeTab === "sources" && !isSubmitting && (
            <div className="space-y-3">
              {sources.length === 0 ? (
                <div className="p-8 text-center text-xs text-brand-textMuted border border-dashed border-brand-border rounded-lg">
                  No sources ingested for this investigation yet.
                </div>
              ) : (
                sources.map((src) => (
                  <div
                    key={src.id}
                    className="p-4 rounded-lg border border-brand-border bg-brand-surface hover:border-slate-600 transition-colors space-y-3"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex items-start gap-2.5 min-w-0">
                        <div className="p-1.5 rounded bg-[#111B2E] border border-brand-border text-brand-textMuted shrink-0 mt-0.5">
                          {src.source_type === "web" ? (
                            <Globe className="w-4 h-4 text-brand-teal" />
                          ) : (
                            <FileText className="w-4 h-4 text-brand-accent" />
                          )}
                        </div>
                        <div className="min-w-0">
                          <h4 className="text-xs font-semibold text-brand-text truncate">
                            {src.title || src.original_url}
                          </h4>
                          <div className="text-[11px] font-mono text-brand-textDim truncate">
                            {src.publisher || "Domain authority"} · {src.original_url}
                          </div>
                          <div className="flex flex-wrap items-center gap-2 pt-1 text-[11px] font-mono">
                            <span className="text-brand-text">
                              Published: <strong className="text-white">{src.publication_date || "Undated"}</strong>
                            </span>
                            <span className="text-brand-textDim">
                              · Ingested: {src.retrieved_at ? src.retrieved_at.split("T")[0] : ""}
                            </span>
                          </div>
                        </div>
                      </div>

                      {/* Extraction & Freshness Status Badges */}
                      <div className="shrink-0 flex flex-wrap items-center gap-1.5">
                        {src.freshness_status && (
                          <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-medium border ${
                            src.freshness_status === "Date Available"
                              ? "bg-emerald-950/60 text-emerald-400 border-emerald-800"
                              : src.freshness_status === "Potentially Outdated"
                              ? "bg-amber-950/60 text-amber-400 border-amber-800"
                              : "bg-slate-900 text-slate-400 border-slate-700"
                          }`}>
                            {src.freshness_status}
                          </span>
                        )}
                        {src.extraction_status === "completed" && (
                          <Badge variant="supported" size="sm" showDot>
                            EXTRACTED
                          </Badge>
                        )}
                        {src.extraction_status === "warning" && (
                          <Badge variant="gap" size="sm" showDot>
                            OCR REQUIRED
                          </Badge>
                        )}
                        {src.extraction_status === "failed" && (
                          <Badge variant="conflict" size="sm" showDot>
                            FAILED
                          </Badge>
                        )}
                        {src.extraction_status === "pending" && (
                          <Badge variant="unverified" size="sm" showDot>
                            PROCESSING
                          </Badge>
                        )}
                      </div>
                    </div>

                    {/* Warning or Error Callout */}
                    {src.error_message && (
                      <div className="p-2.5 rounded bg-[#111B2E] border border-amber-500/30 text-[11px] text-amber-300 flex items-start gap-2">
                        <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-0.5 text-amber-400" />
                        <div>{src.error_message}</div>
                      </div>
                    )}

                    {/* Metadata Footer */}
                    <div className="pt-2 border-t border-brand-border/40 flex flex-wrap items-center justify-between text-[11px] font-mono text-brand-textDim gap-2">
                      <div className="flex items-center gap-3">
                        <span>PASSAGES: {src.passages_count}</span>
                        <span>CLAIMS: {src.claims_count}</span>
                        {src.content_hash && (
                          <span className="hidden sm:inline">
                            HASH: {src.content_hash.substring(0, 10)}...
                          </span>
                        )}
                      </div>

                      <button
                        onClick={() => handleInspectPassages(src)}
                        className="text-brand-accent hover:text-brand-accentHover font-semibold flex items-center gap-1 cursor-pointer"
                      >
                        Inspect Provenance <ArrowRight className="w-3 h-3" />
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>
          )}

          {/* TAB 2: Extracted Claims */}
          {activeInvestigationId && activeTab === "claims" && !isSubmitting && (
            <div className="space-y-3">
              {claims.length === 0 ? (
                <div className="p-8 text-center text-xs text-brand-textMuted border border-dashed border-brand-border rounded-lg">
                  No claims extracted yet. Ensure the ingested sources contain readable text.
                </div>
              ) : (
                claims.map((claim) => {
                  const isExpanded = expandedClaimId === claim.id;
                  return (
                    <div
                      key={claim.id}
                      className="p-4 rounded-lg border border-brand-border bg-brand-surface space-y-2.5 transition-all"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="space-y-1 min-w-0">
                          <div className="text-xs font-semibold text-brand-text leading-relaxed">
                            {claim.claim_text}
                          </div>
                          <div className="text-[11px] font-mono text-brand-teal flex items-center gap-2">
                            <span>{claim.source_title || "Primary Source"}</span>
                            {claim.page_number && (
                              <span className="text-brand-textDim">
                                · Page {claim.page_number}
                              </span>
                            )}
                          </div>
                        </div>

                        <div className="flex items-center gap-2 shrink-0">
                          {claim.processing_mode && (
                            <Badge variant={claim.processing_mode === 'gemini' ? 'info' : 'neutral'} size="sm">
                              {claim.processing_mode === 'gemini' ? 'GEMINI' : 'FALLBACK'}
                            </Badge>
                          )}
                          {claim.category && (
                            <Badge variant="neutral" size="sm">
                              {claim.category.toUpperCase()}
                            </Badge>
                          )}
                          <Badge variant="teal" size="sm">
                            {(claim.extraction_confidence * 100).toFixed(0)}% CONF
                          </Badge>
                        </div>
                      </div>

                      {/* Extraction Method & Expandable Passage */}
                      <div className="pt-2 border-t border-brand-border/40 flex items-center justify-between text-[11px] font-mono text-brand-textDim">
                        <div className="flex items-center gap-1.5">
                          <FileCode className="w-3.5 h-3.5 text-brand-accent" />
                          <span>METHOD: {claim.extraction_method}</span>
                        </div>

                        <button
                          onClick={() => setExpandedClaimId(isExpanded ? null : claim.id)}
                          className="text-brand-textMuted hover:text-brand-text flex items-center gap-1 cursor-pointer"
                        >
                          {isExpanded ? (
                            <>
                              Hide Passage <ChevronUp className="w-3 h-3" />
                            </>
                          ) : (
                            <>
                              View Passage <ChevronDown className="w-3 h-3" />
                            </>
                          )}
                        </button>
                      </div>

                      {/* Collapsible Source Passage */}
                      {isExpanded && claim.passage_text && (
                        <div className="p-3 rounded bg-[#111B2E] border border-brand-border/60 text-xs text-brand-textMuted space-y-1.5 animate-fade-in font-sans">
                          <div className="text-[10px] font-mono uppercase text-brand-textDim font-semibold">
                            Source Citation Coordinates:
                          </div>
                          <blockquote className="border-l-2 border-brand-accent pl-2.5 italic text-slate-300">
                            &ldquo;{claim.passage_text}&rdquo;
                          </blockquote>
                        </div>
                      )}
                    </div>
                  );
                })
              )}
            </div>
          )}
        </div>
      </div>

      {/* Provenance Inspector Modal Dialog */}
      {inspectingSource && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div
            className="fixed inset-0 bg-[#0B1220]/80 backdrop-blur-sm"
            onClick={() => setInspectingSource(null)}
          />
          <div className="relative z-50 w-full max-w-3xl max-h-[85vh] overflow-hidden rounded-xl border border-brand-border bg-brand-surface shadow-modal flex flex-col animate-fade-in">
            {/* Modal Header */}
            <div className="flex items-center justify-between p-4 px-6 border-b border-brand-border/60 bg-[#141F33]">
              <div className="flex items-center gap-2.5">
                <Fingerprint className="w-4 h-4 text-brand-teal" />
                <h3 className="text-sm font-semibold text-brand-text font-mono truncate max-w-md">
                  Provenance Ledger: {inspectingSource.title || inspectingSource.original_url}
                </h3>
              </div>
              <button
                onClick={() => setInspectingSource(null)}
                className="text-brand-textMuted hover:text-brand-text p-1 cursor-pointer"
              >
                ✕
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-6 overflow-y-auto space-y-4 flex-1">
              <div className="p-3 rounded bg-[#111B2E] border border-brand-border text-xs font-mono space-y-1 text-brand-textDim">
                <div>SOURCE ID: {inspectingSource.id}</div>
                <div>TYPE: {inspectingSource.source_type.toUpperCase()}</div>
                <div>CONTENT SHA-256: {inspectingSource.content_hash || "N/A"}</div>
              </div>

              <div className="text-xs font-semibold text-brand-text uppercase font-mono tracking-wider">
                Extracted Passages ({passages.length})
              </div>

              {isLoadingPassages ? (
                <div className="py-8 text-center text-xs text-brand-textMuted flex items-center justify-center gap-2">
                  <Loader2 className="w-4 h-4 animate-spin text-brand-accent" />
                  <span>Loading passage coordinates...</span>
                </div>
              ) : passages.length === 0 ? (
                <div className="py-6 text-center text-xs text-brand-textMuted">
                  No passages segmented for this source.
                </div>
              ) : (
                <div className="space-y-3">
                  {passages.map((p) => (
                    <div
                      key={p.id}
                      className="p-3.5 rounded bg-[#111B2E] border border-brand-border/60 space-y-2 text-xs"
                    >
                      <div className="text-slate-200 leading-relaxed font-sans">
                        {p.passage_text}
                      </div>

                      <div className="pt-2 border-t border-brand-border/40 flex flex-wrap items-center justify-between font-mono text-[10px] text-brand-textDim gap-2">
                        <span>
                          {p.page_number ? `PAGE: ${p.page_number}` : "WEB ARTICLE"} · PARA: {p.paragraph_index} · OFFSETS: [{p.start_offset}:{p.end_offset}]
                        </span>
                        <span className="text-brand-teal">
                          SHA-256: {p.sha256_hash.substring(0, 16)}...
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Modal Footer */}
            <div className="p-3 px-6 bg-[#0E1726] border-t border-brand-border/60 flex items-center justify-between text-[11px] font-mono text-brand-textDim">
              <span>TRUTHMAP FORENSIC LEDGER</span>
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
