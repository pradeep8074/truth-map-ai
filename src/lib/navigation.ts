import {
  LayoutDashboard,
  PlusCircle,
  FileCheck2,
  FolderSearch,
  Network,
  AlertTriangle,
  CheckCircle2,
  History,
  ShieldAlert,
  TrendingDown,
  Compass,
  FileText,
  Settings,
  LucideIcon
} from "lucide-react";

export interface NavItem {
  id: string;
  name: string;
  path: string;
  icon: LucideIcon;
  badge?: string;
  description: string;
  category: "core" | "analysis" | "stress-test" | "reporting" | "system";
}

export const NAVIGATION_ITEMS: NavItem[] = [
  {
    id: "dashboard",
    name: "Command Center",
    path: "/",
    icon: LayoutDashboard,
    description: "Overview of active investigations, indexed documents, and decision criteria.",
    category: "core",
  },
  {
    id: "investigation",
    name: "Start an Investigation",
    path: "/investigations",
    icon: PlusCircle,
    badge: "Core",
    description: "Add web links and PDF documents to extract key claims and verify sources.",
    category: "core",
  },
  {
    id: "decision-contract",
    name: "Decision Criteria",
    path: "/decision-contract",
    icon: FileCheck2,
    description: "Define what you need to decide, required evidence, and key assumptions.",
    category: "core",
  },
  {
    id: "evidence-explorer",
    name: "Evidence Explorer",
    path: "/evidence-explorer",
    icon: FolderSearch,
    description: "Browse extracted claims, source quotes, and verification details.",
    category: "analysis",
  },
  {
    id: "evidence-graph",
    name: "Evidence Map",
    path: "/evidence-graph",
    icon: Network,
    description: "Interactive visual map connecting evidence to your decision criteria.",
    category: "analysis",
  },
  {
    id: "conflict-intelligence",
    name: "Conflicting Evidence",
    path: "/conflict-intelligence",
    icon: AlertTriangle,
    description: "Find disagreements, contradictory statements, and numerical differences between sources.",
    category: "analysis",
  },
  {
    id: "evidence-sufficiency",
    name: "Evidence Coverage",
    path: "/evidence-sufficiency",
    icon: CheckCircle2,
    badge: "Engine",
    description: "Check whether available evidence satisfies each requirement and see what is missing.",
    category: "analysis",
  },
  {
    id: "temporal-intelligence",
    name: "Timeline & Freshness",
    path: "/temporal-intelligence",
    icon: History,
    description: "Track source publication dates and check whether evidence is outdated.",
    category: "analysis",
  },
  {
    id: "stress-test",
    name: "Test Your Decision",
    path: "/stress-test",
    icon: ShieldAlert,
    badge: "Engine",
    description: "Test how your decision holds up if key assumptions fail or evidence changes.",
    category: "stress-test",
  },
  {
    id: "fragility-index",
    name: "Decision Risk Score",
    path: "/fragility-index",
    icon: TrendingDown,
    badge: "Active",
    description: "Clear 0–100 risk score measuring how fragile your decision is based on gaps and conflicts.",
    category: "stress-test",
  },
  {
    id: "verification-navigator",
    name: "Find Missing Evidence",
    path: "/verification-navigator",
    icon: Compass,
    badge: "Active",
    description: "Search for evidence to fill missing gaps and update your investigation.",
    category: "analysis",
  },
  {
    id: "reports",
    name: "Investigation Reports",
    path: "/reports",
    icon: FileText,
    badge: "Active",
    description: "Generate comprehensive, audit-ready summary reports with full source citations.",
    category: "reporting",
  },
];

export const SYSTEM_NAV_ITEMS: NavItem[] = [
  {
    id: "settings",
    name: "System Settings",
    path: "/settings",
    icon: Settings,
    description: "View backend status, database settings, and system configuration.",
    category: "system",
  },
];

export function getNavItemByPath(pathname: string): NavItem | undefined {
  const allItems = [...NAVIGATION_ITEMS, ...SYSTEM_NAV_ITEMS];
  // Match exact or prefix
  if (pathname === "/") {
    return allItems.find((item) => item.path === "/");
  }
  return allItems.find(
    (item) => item.path !== "/" && pathname.startsWith(item.path)
  );
}
