import React from "react";
import { cn } from "@/lib/utilities";

export interface InputProps
  extends React.InputHTMLAttributes<HTMLInputElement> {
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
}

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, type = "text", leftIcon, rightIcon, ...props }, ref) => {
    return (
      <div className="relative flex items-center w-full">
        {leftIcon && (
          <div className="absolute left-3 flex items-center pointer-events-none text-brand-textMuted">
            {leftIcon}
          </div>
        )}
        <input
          type={type}
          ref={ref}
          className={cn(
            "w-full rounded-md border border-brand-border bg-brand-surface/80 px-3.5 py-1.5 text-sm text-brand-text placeholder:text-brand-textDim/70 transition-all duration-150 focus:border-brand-accent focus:bg-brand-surface focus:outline-none focus:ring-1 focus:ring-brand-accent disabled:cursor-not-allowed disabled:opacity-50",
            leftIcon && "pl-9",
            rightIcon && "pr-9",
            className
          )}
          {...props}
        />
        {rightIcon && (
          <div className="absolute right-3 flex items-center text-brand-textMuted">
            {rightIcon}
          </div>
        )}
      </div>
    );
  }
);

Input.displayName = "Input";
