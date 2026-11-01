import React, { useState } from "react";
import { cn } from "@/lib/utilities";

export interface TooltipProps {
  content: React.ReactNode;
  children: React.ReactNode;
  side?: "right" | "top" | "bottom" | "left";
  disabled?: boolean;
  className?: string;
}

export function Tooltip({
  content,
  children,
  side = "right",
  disabled = false,
  className,
}: TooltipProps) {
  const [isVisible, setIsVisible] = useState(false);

  if (disabled) {
    return <>{children}</>;
  }

  const positionStyles = {
    right: "left-full top-1/2 -translate-y-1/2 ml-2.5",
    left: "right-full top-1/2 -translate-y-1/2 mr-2.5",
    top: "bottom-full left-1/2 -translate-x-1/2 mb-2",
    bottom: "top-full left-1/2 -translate-x-1/2 mt-2",
  };

  return (
    <div
      className="relative flex items-center"
      onMouseEnter={() => setIsVisible(true)}
      onMouseLeave={() => setIsVisible(false)}
      onFocus={() => setIsVisible(true)}
      onBlur={() => setIsVisible(false)}
    >
      {children}
      {isVisible && (
        <div
          role="tooltip"
          className={cn(
            "absolute z-50 whitespace-nowrap rounded-md bg-[#172338] px-2.5 py-1 text-xs font-medium text-slate-100 shadow-elevated border border-[#263449] pointer-events-none animate-fade-in",
            positionStyles[side],
            className
          )}
        >
          {content}
        </div>
      )}
    </div>
  );
}
