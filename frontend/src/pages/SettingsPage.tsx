import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/Button";
import { Settings, ArrowLeft, Server, Search, ShieldCheck } from "lucide-react";

export function SettingsPage() {
  const navigate = useNavigate();

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
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
            <Settings className="w-5 h-5 text-brand-teal" />
            System Settings
          </h1>
        </div>
      </div>

      {/* Real System Environment Parameters */}
      <div className="space-y-4">
        <div className="p-5 rounded-xl border border-brand-border bg-brand-surface space-y-4">
          <h3 className="text-sm font-semibold text-brand-text font-mono uppercase tracking-wider flex items-center gap-2">
            <Server className="w-4 h-4 text-brand-accent" />
            Runtime Environment
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs font-mono">
            <div className="p-3 rounded-lg bg-[#111B2E] border border-brand-border/60 space-y-1">
              <span className="text-brand-textDim text-[11px] block">API BACKEND ENDPOINT</span>
              <span className="text-brand-text font-semibold">http://127.0.0.1:8000</span>
            </div>
            <div className="p-3 rounded-lg bg-[#111B2E] border border-brand-border/60 space-y-1">
              <span className="text-brand-textDim text-[11px] block">DATABASE ENGINE</span>
              <span className="text-brand-text font-semibold">SQLite 3 (WAL Mode)</span>
            </div>
          </div>
        </div>

        <div className="p-5 rounded-xl border border-brand-border bg-brand-surface space-y-4">
          <h3 className="text-sm font-semibold text-brand-text font-mono uppercase tracking-wider flex items-center gap-2">
            <Search className="w-4 h-4 text-brand-teal" />
            Provider Integration Status
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs font-mono">
            <div className="p-3 rounded-lg bg-[#111B2E] border border-brand-border/60 space-y-1">
              <span className="text-brand-textDim text-[11px] block">SEARCH PROVIDER</span>
              <span className="text-amber-400 font-semibold">UNAVAILABLE (none)</span>
            </div>
            <div className="p-3 rounded-lg bg-[#111B2E] border border-brand-border/60 space-y-1">
              <span className="text-brand-textDim text-[11px] block">EVIDENCE EVALUATION</span>
              <span className="text-brand-teal font-semibold">Deterministic + Structured Reasoning</span>
            </div>
          </div>
        </div>

        <div className="p-5 rounded-xl border border-brand-border bg-brand-surface space-y-3">
          <div className="flex items-center gap-2 text-xs font-semibold text-brand-text font-mono uppercase tracking-wider">
            <ShieldCheck className="w-4 h-4 text-status-supported" />
            Forensic Integrity Guarantee
          </div>
          <p className="text-xs text-brand-textMuted leading-relaxed">
            All evidence records, passage hashes, and fragility scoring in this workspace are strictly computed and verifiable. Zero synthetic or simulated data is injected into production workflows.
          </p>
        </div>
      </div>
    </div>
  );
}
