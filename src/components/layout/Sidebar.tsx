import { NavLink } from "react-router-dom";
import { NAVIGATION_ITEMS, SYSTEM_NAV_ITEMS, NavItem } from "@/lib/navigation";
import { cn } from "@/lib/utilities";
import { Tooltip } from "@/components/ui/Tooltip";
import {
  ChevronLeft,
  ChevronRight,
  Shield,
  Activity,
  User,
  X,
} from "lucide-react";

interface SidebarProps {
  isCollapsed: boolean;
  onToggleCollapse: () => void;
  isMobileOpen: boolean;
  onCloseMobile: () => void;
}

export function Sidebar({
  isCollapsed,
  onToggleCollapse,
  isMobileOpen,
  onCloseMobile,
}: SidebarProps) {
  const renderNavLinks = (items: NavItem[]) => {
    return items.map((item) => {
      const Icon = item.icon;

      const linkContent = (
        <NavLink
          key={item.id}
          to={item.path}
          onClick={onCloseMobile}
          className={({ isActive }) =>
            cn(
              "group relative flex items-center rounded-md font-medium text-xs transition-all duration-150 select-none",
              isCollapsed
                ? "justify-center w-10 h-10 mx-auto"
                : "px-3 py-2 gap-3 mx-2",
              isActive
                ? "bg-brand-surface text-brand-text font-semibold shadow-subtle border border-brand-borderHighlight/30"
                : "text-brand-textMuted hover:text-brand-text hover:bg-brand-surface/60 border border-transparent"
            )
          }
        >
          {({ isActive }) => (
            <>
              {/* Active left indicator bar (when expanded) */}
              {isActive && !isCollapsed && (
                <span className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-5 bg-brand-accent rounded-r" />
              )}

              {/* Active indicator dot (when collapsed) */}
              {isActive && isCollapsed && (
                <span className="absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full bg-brand-accent shadow-glow-blue" />
              )}

              <Icon
                className={cn(
                  "w-4 h-4 shrink-0 transition-colors",
                  isActive
                    ? "text-brand-accent"
                    : "text-brand-textMuted group-hover:text-brand-text"
                )}
              />

              {!isCollapsed && (
                <div className="flex items-center justify-between w-full min-w-0">
                  <span className="truncate">{item.name}</span>
                  {item.badge && (
                    <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-brand-accent/15 text-brand-accent border border-brand-accent/25 shrink-0 ml-1.5">
                      {item.badge}
                    </span>
                  )}
                </div>
              )}
            </>
          )}
        </NavLink>
      );

      if (isCollapsed) {
        return (
          <Tooltip key={item.id} content={item.name} side="right">
            {linkContent}
          </Tooltip>
        );
      }

      return linkContent;
    });
  };

  return (
    <>
      {/* Mobile Backdrop */}
      {isMobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-[#0B1220]/80 backdrop-blur-sm lg:hidden"
          onClick={onCloseMobile}
        />
      )}

      {/* Sidebar Container */}
      <aside
        className={cn(
          "fixed top-0 bottom-0 left-0 z-40 flex flex-col bg-[#111B2E] border-r border-brand-border transition-all duration-200 ease-in-out",
          // Desktop width
          isCollapsed ? "lg:w-16" : "lg:w-64",
          // Mobile responsive slide-in
          isMobileOpen
            ? "translate-x-0 w-64 shadow-2xl"
            : "-translate-x-full lg:translate-x-0"
        )}
      >
        {/* Brand Header */}
        <div className="h-14 flex items-center justify-between px-3 border-b border-brand-border/70 shrink-0">
          <div
            className={cn(
              "flex items-center gap-2.5 overflow-hidden transition-all",
              isCollapsed && "lg:justify-center lg:w-full"
            )}
          >
            <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-gradient-to-br from-brand-accent to-brand-teal p-0.5 shrink-0 shadow-glow-blue">
              <div className="w-full h-full bg-[#111B2E] rounded-[6px] flex items-center justify-center">
                <Shield className="w-4 h-4 text-brand-teal" />
              </div>
            </div>

            {(!isCollapsed || isMobileOpen) && (
              <div className="flex flex-col min-w-0">
                <span className="text-sm font-bold tracking-wider font-mono text-brand-text truncate">
                  TRUTHMAP<span className="text-brand-accent">.AI</span>
                </span>
                <span className="text-[9px] font-mono tracking-widest text-brand-teal uppercase">
                  Evidence Intelligence
                </span>
              </div>
            )}
          </div>

          {/* Mobile close button */}
          <button
            onClick={onCloseMobile}
            className="lg:hidden p-1.5 text-brand-textMuted hover:text-brand-text hover:bg-brand-surface rounded-md"
            aria-label="Close menu"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Section Label */}
        {!isCollapsed && (
          <div className="px-5 pt-3 pb-1 text-[10px] font-mono uppercase tracking-wider text-brand-textDim/80 font-semibold">
            Investigation Tools
          </div>
        )}

        {/* Navigation Items (Scrollable) */}
        <div className="flex-1 overflow-y-auto py-2 space-y-1">
          {renderNavLinks(NAVIGATION_ITEMS)}
        </div>

        {/* System & Settings Section */}
        <div className="pt-2 pb-2 border-t border-brand-border/60 shrink-0 space-y-1">
          {!isCollapsed && (
            <div className="px-5 pb-1 text-[10px] font-mono uppercase tracking-wider text-brand-textDim/80 font-semibold">
              System
            </div>
          )}
          {renderNavLinks(SYSTEM_NAV_ITEMS)}
        </div>

        {/* User Profile & Collapse Toggle */}
        <div className="p-2 border-t border-brand-border/70 bg-[#0E1726] shrink-0">
          <div
            className={cn(
              "flex items-center rounded-md p-1.5 transition-colors",
              isCollapsed ? "justify-center" : "gap-3 justify-between"
            )}
          >
            <div className="flex items-center gap-2.5 min-w-0">
              <div className="relative flex items-center justify-center w-8 h-8 rounded-full bg-brand-surface border border-brand-border shrink-0">
                <User className="w-4 h-4 text-brand-accent" />
                <span className="absolute bottom-0 right-0 w-2 h-2 rounded-full bg-status-supported border border-[#111B2E]" />
              </div>

              {!isCollapsed && (
                <div className="flex flex-col min-w-0">
                  <span className="text-xs font-semibold text-brand-text truncate">
                    Analyst Workspace
                  </span>
                  <span className="text-[10px] font-mono text-brand-teal truncate flex items-center gap-1">
                    <Activity className="w-2.5 h-2.5" /> ONLINE · VERIFIED
                  </span>
                </div>
              )}
            </div>

            {/* Collapse / Expand Toggle Button (Desktop only) */}
            <button
              onClick={onToggleCollapse}
              className="hidden lg:flex items-center justify-center w-7 h-7 rounded-md text-brand-textMuted hover:text-brand-text hover:bg-brand-surface border border-transparent hover:border-brand-border transition-colors cursor-pointer"
              title={isCollapsed ? "Expand Sidebar" : "Collapse Sidebar"}
              aria-label={isCollapsed ? "Expand Sidebar" : "Collapse Sidebar"}
            >
              {isCollapsed ? (
                <ChevronRight className="w-4 h-4" />
              ) : (
                <ChevronLeft className="w-4 h-4" />
              )}
            </button>
          </div>
        </div>
      </aside>
    </>
  );
}
