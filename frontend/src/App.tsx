import { Routes, Route, Navigate } from "react-router-dom";
import { AppShell } from "@/components/layout/AppShell";
import { DashboardPage } from "@/pages/DashboardPage";
import { InvestigationPage } from "@/pages/InvestigationPage";
import { DecisionContractPage } from "@/pages/DecisionContractPage";
import { EvidenceExplorerPage } from "@/pages/EvidenceExplorerPage";
import { EvidenceGraphPage } from "@/pages/EvidenceGraphPage";
import { ConflictPage } from "@/pages/ConflictPage";
import { EvidenceSufficiencyPage } from "@/pages/EvidenceSufficiencyPage";
import { TemporalPage } from "@/pages/TemporalPage";
import { StressTestPage } from "@/pages/StressTestPage";
import { FragilityPage } from "@/pages/FragilityPage";
import { VerificationPage } from "@/pages/VerificationPage";
import { ReportsPage } from "@/pages/ReportsPage";
import { SettingsPage } from "@/pages/SettingsPage";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<AppShell />}>
        {/* Main Dashboard / Command Center */}
        <Route index element={<DashboardPage />} />

        {/* 11 Functional Enterprise Intelligence Modules */}
        <Route path="investigations" element={<InvestigationPage />} />
        <Route path="decision-contract" element={<DecisionContractPage />} />
        <Route path="evidence-explorer" element={<EvidenceExplorerPage />} />
        <Route path="evidence-graph" element={<EvidenceGraphPage />} />
        <Route path="conflict-intelligence" element={<ConflictPage />} />
        <Route path="evidence-sufficiency" element={<EvidenceSufficiencyPage />} />
        <Route path="temporal-intelligence" element={<TemporalPage />} />
        <Route path="stress-test" element={<StressTestPage />} />
        <Route path="stress-testing" element={<StressTestPage />} />
        <Route path="fragility-index" element={<FragilityPage />} />
        <Route path="verification-navigator" element={<VerificationPage />} />
        <Route path="reports" element={<ReportsPage />} />

        {/* System Settings */}
        <Route path="settings" element={<SettingsPage />} />

        {/* Fallback to Dashboard */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
