import React from "react";
import { cn } from "@/lib/utilities";

export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?:
    | "supported"
    | "conflict"
    | "gap"
    | "unverified"
    | "info"
    | "teal"
    | "outline"
    | "neutral";
  size?: "sm" | "md";
  showDot?: boolean;
}

export function Badge({
  className,
  variant = "neutral",
  size = "sm",
  showDot = false,
  children,
  ...props
}: BadgeProps) {
  const variantStyles = {
    supported:
      "bg-status-supported/10 text-emerald-400 border border-status-supported/30",
    conflict:
      "bg-status-conflict/10 text-rose-400 border border-status-conflict/30",
    gap:
      "bg-status-gap/10 text-amber-400 border border-status-gap/30",
    unverified:
      "bg-status-unverified/10 text-slate-400 border border-status-unverified/30",
    info:
      "bg-brand-accent/10 text-blue-400 border border-brand-accent/30",
    teal:
      "bg-brand-teal/10 text-teal-300 border border-brand-teal/30",
    outline:
      "bg-transparent text-slate-300 border border-brand-border",
    neutral:
      "bg-brand-surfaceHover text-slate-300 border border-brand-border",
  };

  const dotColors = {
    supported: "bg-status-supported",
    conflict: "bg-status-conflict",
    gap: "bg-status-gap",
    unverified: "bg-status-unverified",
    info: "bg-brand-accent",
    teal: "bg-brand-teal",
    outline: "bg-slate-400",
    neutral: "bg-slate-400",
  };

  const sizeStyles = {
    sm: "text-[11px] font-medium px-2 py-0.5 rounded-full gap-1.5",
    md: "text-xs font-medium px-2.5 py-1 rounded-full gap-1.5",
  };

  return (
    <div
      className={cn(
        "inline-flex items-center tracking-tight transition-colors select-none font-mono",
        variantStyles[variant],
        sizeStyles[size],
        className
      )}
      {...props}
    >
      {showDot && (
        <span
          className={cn(
            "w-1.5 h-1.5 rounded-full animate-pulse",
            dotColors[variant]
          )}
        />
      )}
      {children}
    </div>
  );
}
