import { useState, useEffect, useMemo, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { NAVIGATION_ITEMS, SYSTEM_NAV_ITEMS, NavItem } from "@/lib/navigation";
import { cn } from "@/lib/utilities";
import { Search, ArrowRight, CornerDownLeft, Shield } from "lucide-react";

interface CommandPaletteProps {
  isOpen: boolean;
  onClose: () => void;
}

export function CommandPalette({ isOpen, onClose }: CommandPaletteProps) {
  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);

  const allItems: NavItem[] = useMemo(() => {
    return [...NAVIGATION_ITEMS, ...SYSTEM_NAV_ITEMS];
  }, []);

  const filteredItems = useMemo(() => {
    if (!query.trim()) return allItems;
    const q = query.toLowerCase();
    return allItems.filter(
      (item) =>
        item.name.toLowerCase().includes(q) ||
        item.description.toLowerCase().includes(q)
    );
  }, [allItems, query]);

  useEffect(() => {
    setSelectedIndex(0);
  }, [query]);

  useEffect(() => {
    if (isOpen) {
      setQuery("");
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [isOpen]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!isOpen) return;

      if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedIndex((prev) => (prev + 1) % (filteredItems.length || 1));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedIndex((prev) =>
          prev === 0 ? Math.max(0, filteredItems.length - 1) : prev - 1
        );
      } else if (e.key === "Enter" && filteredItems.length > 0) {
        e.preventDefault();
        const selected = filteredItems[selectedIndex];
        if (selected) {
          navigate(selected.path);
          onClose();
        }
      } else if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, selectedIndex, filteredItems, navigate, onClose]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-20 px-4">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-[#0B1220]/80 backdrop-blur-sm transition-opacity"
        onClick={onClose}
      />

      {/* Palette Box */}
      <div className="relative z-50 w-full max-w-2xl overflow-hidden rounded-xl border border-brand-border bg-[#111B2E] shadow-modal animate-slide-down">
        {/* Search Input Bar */}
        <div className="flex items-center px-4 py-3 border-b border-brand-border/60">
          <Search className="w-5 h-5 text-brand-textMuted mr-3 shrink-0" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Type a command or jump to an intelligence module..."
            className="w-full bg-transparent text-sm text-brand-text placeholder:text-brand-textDim/60 focus:outline-none"
          />
          <kbd className="hidden sm:inline-flex items-center px-2 py-0.5 text-[10px] font-mono text-brand-textMuted bg-brand-surface rounded border border-brand-border">
            ESC
          </kbd>
        </div>

        {/* Results List */}
        <div className="max-h-80 overflow-y-auto p-2 space-y-1">
          {filteredItems.length === 0 ? (
            <div className="py-8 text-center text-xs text-brand-textMuted">
              No intelligence modules or actions found matching &ldquo;{query}&rdquo;
            </div>
          ) : (
            filteredItems.map((item, index) => {
              const isSelected = index === selectedIndex;
              const Icon = item.icon;
              return (
                <div
                  key={item.id}
                  onClick={() => {
                    navigate(item.path);
                    onClose();
                  }}
                  onMouseEnter={() => setSelectedIndex(index)}
                  className={cn(
                    "flex items-center justify-between px-3 py-2.5 rounded-lg cursor-pointer transition-colors text-sm",
                    isSelected
                      ? "bg-brand-surface text-brand-text border border-brand-borderHighlight/40"
                      : "text-brand-textMuted hover:text-brand-text hover:bg-brand-surface/50 border border-transparent"
                  )}
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <div
                      className={cn(
                        "p-1.5 rounded-md shrink-0",
                        isSelected
                          ? "bg-brand-accent/20 text-brand-accent"
                          : "bg-brand-surface text-brand-textMuted"
                      )}
                    >
                      <Icon className="w-4 h-4" />
                    </div>
                    <div className="truncate">
                      <div className="font-medium text-brand-text flex items-center gap-2">
                        {item.name}
                        {item.badge && (
                          <span className="text-[10px] px-1.5 py-0.2 rounded font-mono bg-brand-accent/20 text-brand-accent border border-brand-accent/30">
                            {item.badge}
                          </span>
                        )}
                      </div>
                      <div className="text-xs text-brand-textMuted truncate">
                        {item.description}
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 shrink-0 ml-3">
                    <span className="text-[11px] font-mono text-brand-textDim hidden md:inline">
                      {item.path}
                    </span>
                    {isSelected ? (
                      <CornerDownLeft className="w-3.5 h-3.5 text-brand-accent" />
                    ) : (
                      <ArrowRight className="w-3.5 h-3.5 text-brand-textDim opacity-0 group-hover:opacity-100" />
                    )}
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Footer Meta */}
        <div className="flex items-center justify-between px-4 py-2 border-t border-brand-border/40 bg-brand-surface/40 text-[11px] text-brand-textMuted">
          <div className="flex items-center gap-1.5">
            <Shield className="w-3.5 h-3.5 text-brand-teal" />
            <span>TRUTHMAP AI · Enterprise Stress-Testing Environment</span>
          </div>
          <div className="flex items-center gap-3">
            <span className="flex items-center gap-1">
              <kbd className="px-1.5 py-0.5 font-mono text-[9px] bg-brand-surface rounded border border-brand-border">↑</kbd>
              <kbd className="px-1.5 py-0.5 font-mono text-[9px] bg-brand-surface rounded border border-brand-border">↓</kbd>
              <span>Navigate</span>
            </span>
            <span className="flex items-center gap-1">
              <kbd className="px-1.5 py-0.5 font-mono text-[9px] bg-brand-surface rounded border border-brand-border">↵</kbd>
              <span>Select</span>
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
