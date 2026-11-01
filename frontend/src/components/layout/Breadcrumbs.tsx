import { useLocation, Link } from "react-router-dom";
import { getNavItemByPath } from "@/lib/navigation";
import { ChevronRight, Shield } from "lucide-react";

export function Breadcrumbs() {
  const location = useLocation();
  const currentNav = getNavItemByPath(location.pathname);

  const categoryLabels: Record<string, string> = {
    core: "Core Operations",
    analysis: "Evidence Intelligence",
    "stress-test": "Stress Testing",
    reporting: "Governance & Output",
    system: "System Administration",
  };

  return (
    <nav className="flex items-center gap-2 text-xs font-medium" aria-label="Breadcrumb">
      <Link
        to="/"
        className="flex items-center gap-1.5 text-brand-textDim hover:text-brand-text transition-colors"
      >
        <Shield className="w-3.5 h-3.5 text-brand-teal" />
        <span className="font-mono font-semibold tracking-wider">TRUTHMAP AI</span>
      </Link>

      <ChevronRight className="w-3 h-3 text-brand-border shrink-0" />

      {currentNav && currentNav.path !== "/" && (
        <>
          <span className="text-brand-textDim hidden sm:inline">
            {categoryLabels[currentNav.category] || "Workspace"}
          </span>
          <ChevronRight className="w-3 h-3 text-brand-border shrink-0 hidden sm:inline" />
        </>
      )}

      <span className="text-brand-text truncate font-semibold">
        {currentNav?.name || "Command Center"}
      </span>
    </nav>
  );
}
