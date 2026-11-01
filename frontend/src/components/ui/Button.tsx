import React from "react";
import { cn } from "@/lib/utilities";
import { Loader2 } from "lucide-react";

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "outline" | "ghost" | "accent" | "destructive";
  size?: "xs" | "sm" | "md" | "lg" | "icon";
  isLoading?: boolean;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      className,
      variant = "primary",
      size = "md",
      isLoading = false,
      leftIcon,
      rightIcon,
      disabled,
      children,
      ...props
    },
    ref
  ) => {
    const baseStyles =
      "inline-flex items-center justify-center font-medium transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-accent focus-visible:ring-offset-2 focus-visible:ring-offset-brand-bg disabled:opacity-50 disabled:pointer-events-none select-none cursor-pointer";

    const variantStyles = {
      primary:
        "bg-brand-accent text-white hover:bg-brand-accentHover shadow-subtle border border-blue-400/20 active:scale-[0.98]",
      secondary:
        "bg-brand-surface text-brand-text hover:bg-brand-surfaceHover border border-brand-border hover:border-brand-borderHighlight/50 active:scale-[0.98]",
      outline:
        "bg-transparent text-brand-textMuted hover:text-brand-text hover:bg-brand-surface border border-brand-border hover:border-slate-600 active:scale-[0.98]",
      ghost:
        "bg-transparent text-brand-textMuted hover:text-brand-text hover:bg-brand-surface/60 active:bg-brand-surface",
      accent:
        "bg-brand-teal text-slate-950 font-semibold hover:bg-brand-tealHover shadow-subtle active:scale-[0.98]",
      destructive:
        "bg-status-conflict/90 text-white hover:bg-status-conflict border border-red-500/30 active:scale-[0.98]",
    };

    const sizeStyles = {
      xs: "text-xs px-2 py-1 rounded gap-1.5 h-7",
      sm: "text-xs px-2.5 py-1.5 rounded-md gap-1.5 h-8",
      md: "text-sm px-3.5 py-2 rounded-md gap-2 h-9",
      lg: "text-sm md:text-base px-5 py-2.5 rounded-lg gap-2.5 h-11",
      icon: "p-2 rounded-md h-9 w-9",
    };

    return (
      <button
        ref={ref}
        disabled={disabled || isLoading}
        className={cn(
          baseStyles,
          variantStyles[variant],
          sizeStyles[size],
          className
        )}
        {...props}
      >
        {isLoading ? (
          <Loader2 className="w-4 h-4 animate-spin shrink-0" />
        ) : (
          leftIcon && <span className="shrink-0">{leftIcon}</span>
        )}
        {children}
        {!isLoading && rightIcon && <span className="shrink-0">{rightIcon}</span>}
      </button>
    );
  }
);

Button.displayName = "Button";
