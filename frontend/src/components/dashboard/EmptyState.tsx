import React from "react";
import { cn } from "@/lib/utilities";
import { Button } from "@/components/ui/Button";

interface EmptyStateProps {
  icon: React.ReactNode;
  title: string;
  description: string;
  actionLabel?: string;
  onAction?: () => void;
  className?: string;
  secondaryAction?: React.ReactNode;
}

export function EmptyState({
  icon,
  title,
  description,
  actionLabel,
  onAction,
  className,
  secondaryAction,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center text-center p-8 lg:p-12 rounded-lg border border-dashed border-brand-border bg-brand-surface/40",
        className
      )}
    >
      <div className="flex items-center justify-center w-12 h-12 rounded-xl bg-brand-surface border border-brand-border text-brand-textMuted mb-4 shadow-subtle">
        {icon}
      </div>
      <h4 className="text-sm font-semibold text-brand-text mb-1">{title}</h4>
      <p className="text-xs text-brand-textMuted max-w-md leading-relaxed mb-6">
        {description}
      </p>
      {(actionLabel || secondaryAction) && (
        <div className="flex flex-wrap items-center justify-center gap-3">
          {actionLabel && onAction && (
            <Button size="sm" onClick={onAction}>
              {actionLabel}
            </Button>
          )}
          {secondaryAction}
        </div>
      )}
    </div>
  );
}
