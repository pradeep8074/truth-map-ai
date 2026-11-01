import { useNavigate } from "react-router-dom";
import { FolderSearch, Plus, ShieldCheck, Terminal, ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Investigation } from "@/lib/api";

interface RecentInvestigationsProps {
  investigations?: Investigation[];
}

export function RecentInvestigations({ investigations = [] }: RecentInvestigationsProps) {
  const navigate = useNavigate();

  return (
    <div className="rounded-lg border border-brand-border bg-brand-surface overflow-hidden shadow-subtle">
      {/* Header */}
      <div className="flex items-center justify-between p-4 px-5 border-b border-brand-border/60 bg-[#141F33]">
        <div className="flex items-center gap-2.5">
          <FolderSearch className="w-4 h-4 text-brand-teal" />
          <h3 className="text-sm font-semibold text-brand-text">Recent Investigations</h3>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-mono text-brand-textDim">
            {investigations.length} recorded
          </span>
        </div>
      </div>

      {/* If No investigations: Polished Empty State */}
      {investigations.length === 0 ? (
        <div className="p-8 lg:p-12 flex flex-col items-center justify-center text-center">
          <div className="w-12 h-12 rounded-xl bg-[#111B2E] border border-brand-border flex items-center justify-center text-brand-teal mb-4 shadow-subtle">
            <ShieldCheck className="w-6 h-6" />
          </div>

          <h4 className="text-sm font-semibold text-brand-text mb-1">
            No Investigations Yet
          </h4>
          <p className="text-xs text-brand-textMuted max-w-md leading-relaxed mb-6">
            Your workspace has no active investigations. Start an investigation to add documents, extract claims, and evaluate decision criteria.
          </p>

          <div className="flex flex-wrap items-center justify-center gap-3">
            <Button
              size="sm"
              onClick={() => navigate("/investigations")}
              leftIcon={<Plus className="w-3.5 h-3.5" />}
            >
              Start an Investigation
            </Button>

            <Button
              size="sm"
              variant="outline"
              onClick={() => navigate("/decision-contract")}
              leftIcon={<Terminal className="w-3.5 h-3.5" />}
            >
              Set Decision Criteria
            </Button>
          </div>

          {/* Telemetry metadata footer note */}
          <div className="mt-8 pt-4 border-t border-brand-border/40 w-full max-w-lg flex items-center justify-between text-[11px] font-mono text-brand-textDim">
            <span>STATUS: READY</span>
            <span>DOCUMENTS: 0 ADDED</span>
            <span>DATA: 100% VERIFIED</span>
          </div>
        </div>
      ) : (
        /* Real Investigations List */
        <div className="divide-y divide-brand-border/40">
          {investigations.map((inv) => (
            <div
              key={inv.id}
              onClick={() => navigate("/investigations")}
              className="p-4 px-5 hover:bg-brand-surfaceHover/70 transition-colors cursor-pointer flex items-center justify-between gap-4 group"
            >
              <div className="space-y-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-semibold text-brand-text truncate group-hover:text-brand-accent transition-colors">
                    {inv.research_question}
                  </span>
                  <Badge variant="teal" size="sm">
                    {inv.status.toUpperCase()}
                  </Badge>
                </div>
                <div className="text-[11px] font-mono text-brand-textDim flex items-center gap-3">
                  <span>ID: {inv.id.substring(0, 8)}...</span>
                  <span>SOURCES: {inv.sources_count}</span>
                  <span>CLAIMS: {inv.claims_count}</span>
                  <span className="hidden sm:inline">CREATED: {inv.created_at.substring(0, 10)}</span>
                </div>
              </div>

              <div className="shrink-0 text-brand-textDim group-hover:text-brand-accent transition-colors">
                <ArrowRight className="w-4 h-4" />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
