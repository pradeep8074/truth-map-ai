import { useState, useRef, useEffect } from "react";
import { Breadcrumbs } from "./Breadcrumbs";
import {
  Search,
  Bell,
  Menu,
  CheckCircle2,
  Cpu,
  Radio,
  Sliders,
  LogOut,
  ChevronDown
} from "lucide-react";

interface TopbarProps {
  onOpenMobileSidebar: () => void;
  onOpenCommandPalette: () => void;
}

export function Topbar({
  onOpenMobileSidebar,
  onOpenCommandPalette,
}: TopbarProps) {
  const [showNotifications, setShowNotifications] = useState(false);
  const [showProfileMenu, setShowProfileMenu] = useState(false);
  const notifRef = useRef<HTMLDivElement>(null);
  const profileRef = useRef<HTMLDivElement>(null);

  // Close dropdowns on outside click
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (notifRef.current && !notifRef.current.contains(event.target as Node)) {
        setShowNotifications(false);
      }
      if (profileRef.current && !profileRef.current.contains(event.target as Node)) {
        setShowProfileMenu(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <header className="sticky top-0 z-30 h-14 bg-[#111B2E]/90 backdrop-blur-md border-b border-brand-border flex items-center justify-between px-4 lg:px-6 transition-all">
      {/* Left Area: Mobile Menu Toggle + Breadcrumbs */}
      <div className="flex items-center gap-3 min-w-0">
        <button
          onClick={onOpenMobileSidebar}
          className="lg:hidden p-1.5 rounded-md text-brand-textMuted hover:text-brand-text hover:bg-brand-surface border border-brand-border transition-colors"
          aria-label="Open mobile menu"
        >
          <Menu className="w-5 h-5" />
        </button>

        <Breadcrumbs />
      </div>

      {/* Right Area: Global Search Trigger + Actions + Profile */}
      <div className="flex items-center gap-2.5 sm:gap-4 shrink-0">
        {/* Global Search & Command Palette Trigger */}
        <button
          onClick={onOpenCommandPalette}
          className="flex items-center gap-2.5 px-3 py-1.5 rounded-md bg-brand-surface hover:bg-brand-surfaceHover border border-brand-border hover:border-brand-borderHighlight/40 text-xs text-brand-textMuted hover:text-brand-text transition-all shadow-subtle group"
          title="Search or jump to module (Ctrl+K)"
        >
          <Search className="w-3.5 h-3.5 text-brand-textMuted group-hover:text-brand-accent transition-colors" />
          <span className="hidden md:inline">Quick search & navigation...</span>
          <span className="md:hidden">Search</span>
          <div className="flex items-center gap-1 font-mono text-[10px] text-brand-textDim bg-[#0B1220] px-1.5 py-0.5 rounded border border-brand-border/60">
            <span>Ctrl</span>
            <span>K</span>
          </div>
        </button>

        {/* System Status (Desktop) */}
        <div className="hidden xl:flex items-center gap-2 px-2.5 py-1 rounded bg-[#0E1726] border border-brand-border text-[11px] font-mono text-brand-textMuted">
          <span className="w-1.5 h-1.5 rounded-full bg-status-supported animate-pulse" />
          <span className="text-slate-300">SYSTEM STATUS</span>
          <span className="text-brand-border">|</span>
          <span className="text-brand-teal">ONLINE · READY</span>
        </div>

        {/* Notification Bell Dropdown */}
        <div className="relative" ref={notifRef}>
          <button
            onClick={() => setShowNotifications((prev) => !prev)}
            className="relative p-2 rounded-md text-brand-textMuted hover:text-brand-text hover:bg-brand-surface border border-transparent hover:border-brand-border transition-colors"
            title="System Status & Alerts"
            aria-label="Notifications"
          >
            <Bell className="w-4 h-4" />
            <span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-brand-accent" />
          </button>

          {showNotifications && (
            <div className="absolute right-0 mt-2 w-80 rounded-lg border border-brand-border bg-brand-surface shadow-modal p-3 z-50 animate-slide-down">
              <div className="flex items-center justify-between pb-2 border-b border-brand-border/60">
                <span className="text-xs font-semibold font-mono text-brand-text flex items-center gap-1.5">
                  <Radio className="w-3.5 h-3.5 text-brand-teal" /> SYSTEM STATUS
                </span>
                <span className="text-[10px] font-mono text-brand-textDim">0 active alerts</span>
              </div>
              <div className="py-3 space-y-2 text-xs">
                <div className="p-2 rounded bg-[#111B2E] border border-brand-border/60 flex items-start gap-2">
                  <CheckCircle2 className="w-4 h-4 text-status-supported shrink-0 mt-0.5" />
                  <div>
                    <div className="font-medium text-brand-text">Forensic Engine Ready</div>
                    <div className="text-[11px] text-brand-textMuted">
                      Cryptographic ledger and evaluation pipelines active.
                    </div>
                  </div>
                </div>
                <div className="p-2 rounded bg-[#111B2E] border border-brand-border/60 flex items-start gap-2">
                  <Cpu className="w-4 h-4 text-brand-accent shrink-0 mt-0.5" />
                  <div>
                    <div className="font-medium text-brand-text">Honesty Telemetry Active</div>
                    <div className="text-[11px] text-brand-textMuted">
                      No synthetic data or mocked claims in production metrics.
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* User Profile Dropdown Placeholder */}
        <div className="relative" ref={profileRef}>
          <button
            onClick={() => setShowProfileMenu((prev) => !prev)}
            className="flex items-center gap-2 p-1 pl-1.5 pr-2 rounded-md hover:bg-brand-surface border border-transparent hover:border-brand-border transition-colors text-left"
            aria-label="User Profile"
          >
            <div className="w-7 h-7 rounded-full bg-gradient-to-tr from-brand-accent to-brand-teal p-0.5 shrink-0">
              <div className="w-full h-full bg-[#111B2E] rounded-full flex items-center justify-center text-xs font-bold font-mono text-brand-text">
                R1
              </div>
            </div>
            <div className="hidden md:flex flex-col">
              <span className="text-xs font-medium text-brand-text leading-tight">
                Researcher 01
              </span>
              <span className="text-[10px] font-mono text-brand-textDim leading-tight">
                Clearance L4
              </span>
            </div>
            <ChevronDown className="w-3.5 h-3.5 text-brand-textDim hidden md:inline" />
          </button>

          {showProfileMenu && (
            <div className="absolute right-0 mt-2 w-56 rounded-lg border border-brand-border bg-brand-surface shadow-modal p-2 z-50 animate-slide-down text-xs">
              <div className="px-3 py-2 border-b border-brand-border/60">
                <div className="font-semibold text-brand-text">Forensic Intelligence Workspace</div>
                <div className="text-[11px] font-mono text-brand-teal mt-0.5">Analyst ID: RES-7409</div>
              </div>
              <div className="py-1">
                <button
                  onClick={() => {
                    setShowProfileMenu(false);
                    onOpenCommandPalette();
                  }}
                  className="w-full flex items-center gap-2 px-3 py-2 rounded text-brand-textMuted hover:text-brand-text hover:bg-brand-surfaceHover transition-colors"
                >
                  <Search className="w-3.5 h-3.5" />
                  <span>Command Center Search</span>
                </button>
                <div className="flex items-center justify-between px-3 py-2 text-brand-textMuted">
                  <span className="flex items-center gap-2">
                    <Sliders className="w-3.5 h-3.5" />
                    <span>Integrity Engine</span>
                  </span>
                  <span className="font-mono text-[10px] text-status-supported">VERIFIED</span>
                </div>
              </div>
              <div className="pt-1 border-t border-brand-border/60">
                <div className="flex items-center gap-2 px-3 py-1.5 text-brand-textDim text-[11px]">
                  <LogOut className="w-3 h-3" />
                  <span>Session Active (Local)</span>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
