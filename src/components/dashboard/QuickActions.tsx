import { useNavigate } from "react-router-dom";
import { PlusCircle, Network, FileText, ArrowUpRight } from "lucide-react";

export function QuickActions() {
  const navigate = useNavigate();

  const actions = [
    {
      title: "Start an Investigation",
      description: "Add web links and PDF documents to extract key claims and verify sources.",
      icon: PlusCircle,
      path: "/investigations",
      badge: "Quick Start",
      color: "from-blue-500/20 to-blue-600/5",
      borderColor: "border-blue-500/30",
      accentText: "text-blue-400",
    },
    {
      title: "View Evidence Map",
      description: "See how extracted claims and sources connect to your decision criteria.",
      icon: Network,
      path: "/evidence-graph",
      badge: "Visual Map",
      color: "from-teal-500/20 to-teal-600/5",
      borderColor: "border-teal-500/30",
      accentText: "text-teal-400",
    },
    {
      title: "Investigation Reports",
      description: "Read complete summary reports with source citations and risk scores.",
      icon: FileText,
      path: "/reports",
      badge: "Reports",
      color: "from-purple-500/20 to-purple-600/5",
      borderColor: "border-purple-500/30",
      accentText: "text-purple-400",
    },
  ];

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      {actions.map((action) => {
        const Icon = action.icon;
        return (
          <div
            key={action.title}
            onClick={() => navigate(action.path)}
            className="relative flex flex-col justify-between p-5 rounded-lg border border-brand-border bg-brand-surface hover:bg-brand-surfaceHover/90 cursor-pointer transition-all duration-150 group shadow-subtle hover:border-slate-600"
          >
            <div>
              <div className="flex items-center justify-between mb-3">
                <div className="p-2 rounded-md bg-[#111B2E] border border-brand-border text-brand-textMuted group-hover:text-brand-accent transition-colors">
                  <Icon className="w-4 h-4" />
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#111B2E] text-brand-textMuted border border-brand-border">
                    {action.badge}
                  </span>
                  <ArrowUpRight className="w-4 h-4 text-brand-textDim group-hover:text-brand-text transition-colors transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
                </div>
              </div>
              <h4 className="text-sm font-semibold text-brand-text mb-1">
                {action.title}
              </h4>
              <p className="text-xs text-brand-textMuted leading-relaxed">
                {action.description}
              </p>
            </div>

            <div className="mt-4 pt-3 border-t border-brand-border/40 flex items-center justify-between text-[11px] font-mono text-brand-textDim">
              <span>Quick Navigate</span>
              <span className={action.accentText}>Open Module →</span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
