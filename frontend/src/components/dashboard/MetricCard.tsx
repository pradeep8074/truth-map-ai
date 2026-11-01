import React from "react";
import { cn } from "@/lib/utilities";
import { Badge } from "@/components/ui/Badge";

interface MetricCardProps {
  title: string;
  value: string | number;
  subtext: string;
  icon: React.ReactNode;
  statusBadge?: {
    label: string;
    variant: "supported" | "conflict" | "gap" | "unverified" | "info" | "neutral" | "teal";
  };
  className?: string;
}

export function MetricCard({
  title,
  value,
  subtext,
  icon,
  statusBadge,
  className,
}: MetricCardProps) {
  return (
    <div
      className={cn(
        "relative overflow-hidden rounded-lg border border-brand-border bg-brand-surface p-5 shadow-subtle hover:border-slate-600 transition-all duration-150 group",
        className
      )}
    >
      {/* Subtle top indicator bar */}
      <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-transparent via-brand-borderHighlight/40 to-transparent group-hover:via-brand-borderHighlight transition-all" />

      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-brand-textMuted tracking-tight uppercase font-mono">
          {title}
        </span>
        <div className="p-2 rounded-md bg-[#111B2E] border border-brand-border text-brand-textMuted group-hover:text-brand-accent transition-colors">
          {icon}
        </div>
      </div>

      <div className="mt-4 flex items-baseline gap-3">
        <div className="text-3xl font-bold font-mono tracking-tight text-brand-text">
          {value}
        </div>
        {statusBadge && (
          <Badge variant={statusBadge.variant} size="sm">
            {statusBadge.label}
          </Badge>
        )}
      </div>

      <div className="mt-2 text-xs text-brand-textDim truncate font-mono">
        {subtext}
      </div>
    </div>
  );
}
