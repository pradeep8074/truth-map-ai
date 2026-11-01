export interface Source {
  id: string;
  investigation_id: string;
  source_type: "web" | "pdf";
  source_origin?: "ACTUAL_PUBLIC_SOURCE" | "USER_PROVIDED_DOCUMENT" | "DEMONSTRATION_DOCUMENT" | "SYNTHETIC_TEST_FIXTURE" | "UNKNOWN" | string;
  original_url?: string;
  title?: string;
  publisher?: string;
  publication_date?: string;
  source_modified_date?: string;
  date_source?: string;
  date_extraction_method?: string;
  date_confidence?: number;
  date_validation_status?: string;
  freshness_status?: "Date Available" | "Potentially Outdated" | "Undated Source" | "Date Unavailable" | "Date Requires Review" | string;
  freshness_explanation?: string;
  days_old?: number;
  retrieved_at: string;
  content_hash?: string;
  extraction_status: "pending" | "completed" | "warning" | "failed";
  passages_count: number;
  claims_count: number;
  error_message?: string;
}

export interface WorkspaceFreshnessSummary {
  total_sources: number;
  dated_sources: number;
  undated_sources: number;
  potentially_outdated_sources: number;
  sources_requiring_review: number;
  freshness_threshold_days: number;
  reference_date: string;
}

export interface Passage {
  id: string;
  source_id: string;
  passage_text: string;
  page_number?: number;
  paragraph_index?: number;
  start_offset?: number;
  end_offset?: number;
  sha256_hash: string;
}

export interface Claim {
  id: string;
  investigation_id: string;
  source_id: string;
  passage_id: string;
  claim_text: string;
  category?: string;
  extraction_method: string;
  processing_mode?: "gemini" | "fallback";
  extraction_confidence: number;
  created_at: string;
  passage_text?: string;
  page_number?: number;
  source_title?: string;
  source_type?: string;
  passage_sha256?: string;
}

export interface Investigation {
  id: string;
  research_question: string;
  status: string;
  created_at: string;
  sources_count: number;
  claims_count: number;
  requirements_count?: number;
  has_contract?: boolean;
  sources?: Source[];
}

// ==========================================
// Component 03 Types (Decision Contract)
// ==========================================

export interface EvidenceRequirement {
  evidence_requirement_id: string;
  requirement_id: string;
  evidence_type: string;
  rationale: string;
  preferred_source_types: string[];
  temporal_scope?: string;
  geographic_scope?: string;
}

export interface Requirement {
  requirement_id: string;
  title: string;
  description: string;
  requirement_type: "FACTUAL" | "QUANTITATIVE" | "COMPARATIVE" | "CAUSAL" | "TEMPORAL" | "GEOGRAPHIC" | "ELIGIBILITY" | "RISK" | "IMPLEMENTATION";
  priority: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";
  verification_criteria: string;
  status: string;
  evidence_needed: EvidenceRequirement[];
}

export interface Constraint {
  constraint_id: string;
  description: string;
  constraint_type: string;
}

export interface Assumption {
  assumption_id: string;
  description: string;
  confidence: number;
  source?: "ai_inferred" | "user_provided" | string;
  validation_status: string;
}

export interface UnresolvedQuestion {
  question_id: string;
  question: string;
  clarification_type: "required" | "optional" | "assumption_review";
  dimension: string;
}

export interface DecisionContract {
  contract_id: string;
  investigation_id: string;
  original_question: string;
  normalized_question: string;
  decision_objective: string;
  scope?: string;
  compilation_method: string;
  processing_mode?: "gemini" | "fallback";
  created_at: string;
  updated_at: string;
  requirements: Requirement[];
  evidence_requirements: EvidenceRequirement[];
  constraints: Constraint[];
  assumptions: Assumption[];
  unresolved_questions: UnresolvedQuestion[];
}

export interface ContractUpdateRequest {
  decision_objective?: string;
  scope?: string;
  requirements?: Requirement[];
  constraints?: Constraint[];
  assumptions?: Assumption[];
  unresolved_questions?: UnresolvedQuestion[];
}

const API_BASE = "/api";

export async function createInvestigation(research_question: string, urls: string[] = []): Promise<{ investigation_id: string; status: string; message?: string }> {
  const res = await fetch(`${API_BASE}/investigations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ research_question, urls: urls.filter(u => u.trim().length > 0) }),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ detail: "Failed to create investigation" }));
    throw new Error(errorData.detail || `Server returned ${res.status}`);
  }
  return res.json();
}

export async function uploadPdfsToInvestigation(investigationId: string, files: File[]): Promise<Source[]> {
  const formData = new FormData();
  files.forEach((file) => {
    formData.append("files", file);
  });

  const res = await fetch(`${API_BASE}/investigations/${investigationId}/documents`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ detail: "Failed to upload PDF documents" }));
    throw new Error(errorData.detail || `Server returned ${res.status}`);
  }
  return res.json();
}

export async function addUrlsToInvestigation(investigationId: string, urls: string[]): Promise<Source[]> {
  const res = await fetch(`${API_BASE}/investigations/${investigationId}/sources`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ urls: urls.filter(u => u.trim().length > 0) }),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ detail: "Failed to add URL sources" }));
    throw new Error(errorData.detail || `Server returned ${res.status}`);
  }
  return res.json();
}

export async function getInvestigation(id: string): Promise<Investigation> {
  const res = await fetch(`${API_BASE}/investigations/${id}`);
  if (!res.ok) {
    throw new Error(`Failed to fetch investigation ${id}`);
  }
  return res.json();
}

export async function listInvestigations(): Promise<Investigation[]> {
  const res = await fetch(`${API_BASE}/investigations`);
  if (!res.ok) {
    throw new Error("Failed to list investigations");
  }
  return res.json();
}

export async function getInvestigationSources(id: string): Promise<Source[]> {
  const res = await fetch(`${API_BASE}/investigations/${id}/sources`);
  if (!res.ok) {
    throw new Error("Failed to fetch sources");
  }
  return res.json();
}

export async function getWorkspaceFreshnessSummary(investigationId?: string): Promise<WorkspaceFreshnessSummary> {
  const url = investigationId
    ? `${API_BASE}/investigations/${investigationId}/freshness-summary`
    : `${API_BASE}/workspace/freshness-summary`;
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error("Failed to fetch freshness summary");
  }
  return res.json();
}

export async function getInvestigationClaims(id: string): Promise<Claim[]> {
  const res = await fetch(`${API_BASE}/investigations/${id}/claims`);
  if (!res.ok) {
    throw new Error("Failed to fetch claims");
  }
  return res.json();
}

export async function getSourcePassages(sourceId: string): Promise<Passage[]> {
  const res = await fetch(`${API_BASE}/sources/${sourceId}/passages`);
  if (!res.ok) {
    throw new Error("Failed to fetch source passages");
  }
  return res.json();
}

// ==========================================
// Decision Contract API Functions
// ==========================================

export async function compileDecisionContract(investigationId: string): Promise<DecisionContract> {
  const res = await fetch(`${API_BASE}/investigations/${investigationId}/contract/compile`, {
    method: "POST",
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ detail: "Failed to compile contract" }));
    throw new Error(errorData.detail || `Server returned ${res.status}`);
  }
  return res.json();
}

export async function getDecisionContract(investigationId: string): Promise<DecisionContract> {
  const res = await fetch(`${API_BASE}/investigations/${investigationId}/contract`);
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ detail: "Contract not found" }));
    throw new Error(errorData.detail || `Server returned ${res.status}`);
  }
  return res.json();
}

export async function updateDecisionContract(investigationId: string, payload: ContractUpdateRequest): Promise<DecisionContract> {
  const res = await fetch(`${API_BASE}/investigations/${investigationId}/contract`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ detail: "Failed to update contract" }));
    throw new Error(errorData.detail || `Server returned ${res.status}`);
  }
  return res.json();
}

export async function recompileDecisionContract(investigationId: string): Promise<DecisionContract> {
  const res = await fetch(`${API_BASE}/investigations/${investigationId}/contract/recompile`, {
    method: "POST",
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ detail: "Failed to recompile contract" }));
    throw new Error(errorData.detail || `Server returned ${res.status}`);
  }
  return res.json();
}

export async function checkBackendHealth(): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/health`, { signal: AbortSignal.timeout(3000) });
    return res.ok;
  } catch {
    return false;
  }
}

// ==========================================
// Component 04 Types & APIs (Evidence Dependency Graph)
// ==========================================

export type GraphNodeType =
  | "decision_contract"
  | "decision_requirement"
  | "evidence_requirement"
  | "atomic_claim"
  | "source_passage"
  | "source_document";

export type GraphRelationshipType =
  | "HAS_REQUIREMENT"
  | "REQUIRES_EVIDENCE"
  | "RELATES_TO"
  | "EXTRACTED_FROM"
  | "BELONGS_TO_SOURCE";

export interface GraphNode {
  id: string;
  type: GraphNodeType;
  label: string;
  record_id: string;
  metadata: Record<string, any>;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  relationship: GraphRelationshipType;
  origin: "structural" | "gemini" | "fallback";
  confidence?: number;
  metadata: Record<string, any>;
}

export interface GraphSummary {
  total_nodes: number;
  total_edges: number;
  contract_nodes: number;
  requirement_nodes: number;
  evidence_requirement_nodes: number;
  claim_nodes: number;
  passage_nodes: number;
  source_nodes: number;
  directly_relevant_links: number;
  partially_relevant_links: number;
  contextual_links: number;
}

export interface EvidenceGraphData {
  investigation_id: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
  processing_mode: "gemini" | "fallback" | "pending";
  last_analyzed_at?: string;
  summary: GraphSummary;
}

export interface EvidenceGraphStatus {
  investigation_id: string;
  total_nodes: number;
  total_edges: number;
  requirements_represented: number;
  claims_represented: number;
  sources_represented: number;
  processing_mode: "gemini" | "fallback" | "pending";
  last_analysis_status: "completed" | "pending" | "none";
  relationships_count: number;
  directly_relevant_count: number;
  partially_relevant_count: number;
  contextual_count: number;
}

export async function getEvidenceGraph(investigationId: string): Promise<EvidenceGraphData> {
  const res = await fetch(`${API_BASE}/investigations/${investigationId}/evidence-graph`);
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ detail: "Failed to load evidence graph" }));
    throw new Error(errorData.detail || `Server returned ${res.status}`);
  }
  return res.json();
}

export async function analyzeEvidenceGraph(investigationId: string): Promise<EvidenceGraphData> {
  const res = await fetch(`${API_BASE}/investigations/${investigationId}/evidence-graph/analyze`, {
    method: "POST",
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ detail: "Graph relevance analysis failed" }));
    throw new Error(errorData.detail || `Server returned ${res.status}`);
  }
  return res.json();
}

export async function getEvidenceGraphStatus(investigationId: string): Promise<EvidenceGraphStatus> {
  const res = await fetch(`${API_BASE}/investigations/${investigationId}/evidence-graph/status`);
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ detail: "Failed to load graph status" }));
    throw new Error(errorData.detail || `Server returned ${res.status}`);
  }
  return res.json();
}

// ==========================================
// Component 05 Types (Evidence Contradiction Engine)
// ==========================================

export type ConflictType =
  | "DIRECT_CONTRADICTION"
  | "NUMERICAL_CONFLICT"
  | "TEMPORAL_CONFLICT"
  | "CONTEXTUAL_TENSION"
  | "METHODOLOGICAL_DISAGREEMENT"
  | "UNRESOLVED_CONFLICT";

export type ConflictSeverity = "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";

export type ConflictResolutionStatus = "unresolved" | "under_review" | "resolved";

export interface ConflictItem {
  conflict_id: string;
  investigation_id: string;
  claim_a_id: string;
  claim_b_id: string;
  claim_a_text: string;
  claim_b_text: string;
  claim_a_category?: string;
  claim_b_category?: string;
  source_a_id?: string;
  source_b_id?: string;
  source_a_title?: string;
  source_b_title?: string;
  source_a_url?: string;
  source_b_url?: string;
  passage_a_text?: string;
  passage_b_text?: string;
  passage_a_page?: number;
  passage_b_page?: number;
  passage_a_hash?: string;
  passage_b_hash?: string;
  conflict_type: ConflictType;
  severity: ConflictSeverity;
  explanation: string;
  contextual_differences?: string;
  confidence: number;
  resolution_status: ConflictResolutionStatus;
  reviewer_notes?: string;
  recommended_action: string;
  analysis_method: string;
  processing_mode: "gemini" | "fallback";
  created_at: string;
  updated_at: string;
}

export interface ConflictSummary {
  total_conflicts: number;
  direct_contradictions: number;
  numerical_conflicts: number;
  temporal_conflicts: number;
  contextual_tensions: number;
  methodological_disagreements: number;
  scope_mismatches?: number;
  analyst_review_needed?: number;
  unresolved_conflicts: number;
  critical_severity: number;
  high_severity: number;
  medium_severity: number;
  low_severity: number;
  under_review_count: number;
  resolved_count: number;
}

export interface ConflictListResponse {
  investigation_id: string;
  conflicts: ConflictItem[];
  summary: ConflictSummary;
  processing_mode: "gemini" | "fallback" | "pending";
  last_analyzed_at?: string;
}

export interface ConflictStatus {
  investigation_id: string;
  total_conflicts: number;
  direct_contradictions: number;
  numerical_conflicts: number;
  contextual_tensions: number;
  unresolved_conflicts: number;
  processing_mode: "gemini" | "fallback" | "pending";
  last_analysis_status: "completed" | "pending" | "none";
  last_analyzed_at?: string;
}

export interface ConflictResolutionUpdateRequest {
  resolution_status?: ConflictResolutionStatus;
  reviewer_notes?: string;
}

export async function getInvestigationConflicts(investigationId: string): Promise<ConflictListResponse> {
  const res = await fetch(`${API_BASE}/investigations/${investigationId}/conflicts`);
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ detail: "Failed to load conflicts" }));
    throw new Error(errorData.detail || `Server returned ${res.status}`);
  }
  return res.json();
}

export async function analyzeInvestigationConflicts(investigationId: string): Promise<ConflictListResponse> {
  const res = await fetch(`${API_BASE}/investigations/${investigationId}/conflicts/analyze`, {
    method: "POST",
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ detail: "Conflict analysis failed" }));
    throw new Error(errorData.detail || `Server returned ${res.status}`);
  }
  return res.json();
}

export async function getConflictStatus(investigationId: string): Promise<ConflictStatus> {
  const res = await fetch(`${API_BASE}/investigations/${investigationId}/conflicts/status`);
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ detail: "Failed to load conflict status" }));
    throw new Error(errorData.detail || `Server returned ${res.status}`);
  }
  return res.json();
}

export async function updateConflictResolution(
  investigationId: string,
  conflictId: string,
  payload: ConflictResolutionUpdateRequest
): Promise<ConflictItem> {
  const res = await fetch(`${API_BASE}/investigations/${investigationId}/conflicts/${conflictId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ detail: "Failed to update conflict resolution" }));
    throw new Error(errorData.detail || `Server returned ${res.status}`);
  }
  return res.json();
}

// ==========================================
// Component 06 Types (Evidence Sufficiency & Gap Analysis)
// ==========================================

export type CoverageStatus =
  | "SUFFICIENT"
  | "PARTIAL"
  | "INSUFFICIENT"
  | "NO_EVIDENCE"
  | "CONFLICTING";

export type GapPriority = "HIGH" | "MEDIUM" | "LOW";

export interface EvidenceGap {
  id: string;
  investigation_id: string;
  requirement_id: string;
  assessment_id?: string;
  gap_description: string;
  why_it_matters: string;
  evidence_needed: string;
  suggested_source_type?: string;
  priority: GapPriority;
  created_at: string;
}

export interface SupportingClaimInfo {
  claim_id: string;
  claim_text: string;
  category?: string;
  relevance: "DIRECTLY_RELEVANT" | "PARTIALLY_RELEVANT" | "CONTEXTUAL";
  relevance_explanation?: string;
  extraction_confidence: number;
  source_id?: string;
  source_title?: string;
  source_type?: string;
  source_url?: string;
  passage_id?: string;
  passage_text?: string;
  page_number?: number;
  sha256_hash?: string;
}

export interface RelatedConflictInfo {
  conflict_id: string;
  claim_a_id: string;
  claim_b_id: string;
  opposing_claim_text: string;
  conflict_type: string;
  severity: string;
  explanation: string;
  resolution_status: "unresolved" | "under_review" | "resolved";
  is_unresolved: boolean;
}

export interface RequirementSufficiencyAssessment {
  requirement_id: string;
  investigation_id: string;
  requirement_title: string;
  requirement_description: string;
  requirement_type: string;
  priority: string;
  verification_criteria: string;
  coverage_status: CoverageStatus;
  assessment_summary: string;
  supporting_claims: SupportingClaimInfo[];
  supporting_claim_ids: string[];
  supporting_passage_ids: string[];
  source_ids: string[];
  related_conflicts: RelatedConflictInfo[];
  related_conflict_ids: string[];
  unresolved_conflict_count: number;
  limitations?: string;
  missing_information?: string;
  recommended_action: string;
  gaps: EvidenceGap[];
  confidence: number;
  analysis_method: string;
  processing_mode: "gemini" | "fallback";
  analyzed_at: string;
}

export interface SufficiencySummary {
  total_requirements: number;
  sufficient_count: number;
  partial_count: number;
  insufficient_count: number;
  no_evidence_count: number;
  conflicting_count: number;
  total_gaps: number;
  high_priority_gaps: number;
  medium_priority_gaps: number;
  low_priority_gaps: number;
  overall_coverage_ratio: number;
  coverage_explanation: string;
}

export interface SufficiencyResponse {
  investigation_id: string;
  contract_id?: string;
  decision_objective?: string;
  assessments: RequirementSufficiencyAssessment[];
  summary: SufficiencySummary;
  processing_mode: "gemini" | "fallback" | "pending";
  last_analyzed_at?: string;
}

export interface SufficiencyStatus {
  investigation_id: string;
  total_requirements: number;
  sufficient_count: number;
  partial_count: number;
  insufficient_count: number;
  no_evidence_count: number;
  conflicting_count: number;
  total_gaps: number;
  processing_mode: "gemini" | "fallback" | "pending";
  last_analysis_status: "completed" | "pending" | "none";
  last_analyzed_at?: string;
}

export async function getInvestigationSufficiency(investigationId: string): Promise<SufficiencyResponse> {
  const res = await fetch(`${API_BASE}/investigations/${investigationId}/sufficiency`);
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ detail: "Failed to load sufficiency assessments" }));
    throw new Error(errorData.detail || `Server returned ${res.status}`);
  }
  return res.json();
}

export async function analyzeInvestigationSufficiency(investigationId: string): Promise<SufficiencyResponse> {
  const res = await fetch(`${API_BASE}/investigations/${investigationId}/sufficiency/analyze`, {
    method: "POST",
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ detail: "Sufficiency analysis failed" }));
    throw new Error(errorData.detail || `Server returned ${res.status}`);
  }
  return res.json();
}

export async function getSufficiencyStatus(investigationId: string): Promise<SufficiencyStatus> {
  const res = await fetch(`${API_BASE}/investigations/${investigationId}/sufficiency/status`);
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ detail: "Failed to load sufficiency status" }));
    throw new Error(errorData.detail || `Server returned ${res.status}`);
  }
  return res.json();
}

export async function getRequirementSufficiencyDetail(
  investigationId: string,
  requirementId: string
): Promise<RequirementSufficiencyAssessment> {
  const res = await fetch(`${API_BASE}/investigations/${investigationId}/sufficiency/requirements/${requirementId}`);
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ detail: "Failed to load requirement sufficiency detail" }));
    throw new Error(errorData.detail || `Server returned ${res.status}`);
  }
  return res.json();
}

// ==========================================
// Component 07 Types (Decision Stress Testing Engine)
// ==========================================

export type StressScenarioCategory =
  | "ASSUMPTION_FAILURE"
  | "RISK_MATERIALIZATION"
  | "EVIDENCE_WEAKENING"
  | "CONFLICT_RESOLUTION"
  | "EXTERNAL_CONDITION_CHANGE"
  | "MISSING_EVIDENCE";

export type DecisionOutcome =
  | "ROBUST"
  | "CONDITIONALLY_ROBUST"
  | "VULNERABLE"
  | "HIGHLY_VULNERABLE"
  | "INDETERMINATE"
  | "NOT_EVALUABLE";

export type OutcomeShift =
  | "UNCHANGED"
  | "DOWNGRADED"
  | "CRITICAL_FAILURE"
  | "IMPROVED"
  | "INCONCLUSIVE"
  | "DEGRADED"
  | "STABLE"
  | "NOT_EVALUABLE";

export type StressSeverity = "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";

export interface RequirementEvaluationItem {
  requirement_id: string;
  requirement_title: string;
  baseline_status: CoverageStatus;
  scenario_status: CoverageStatus;
  status_shift: "UNMODIFIED" | "DEGRADED" | "IMPROVED";
  degradation_reason?: string;
}

export interface StressEvaluation {
  id: string;
  scenario_id: string;
  investigation_id: string;
  baseline_overall_outcome: DecisionOutcome;
  scenario_overall_outcome: DecisionOutcome;
  outcome_shift: OutcomeShift;
  impact_explanation: string;
  key_vulnerabilities: string[];
  uncertainty_factors: string[];
  recommended_actions: string[];
  requirement_evaluations: RequirementEvaluationItem[];
  processing_mode: "gemini" | "fallback";
  evaluated_at: string;
}

export interface StressScenario {
  id: string;
  investigation_id: string;
  title: string;
  category: StressScenarioCategory;
  description: string;
  trigger_condition: string;
  challenged_assumptions: string[];
  affected_requirement_ids: string[];
  affected_requirement_titles: string[];
  related_claim_ids: string[];
  related_source_ids: string[];
  related_conflict_ids: string[];
  expected_impact: string;
  severity: StressSeverity;
  evidence_needed: string;
  evaluation_status: "evaluated" | "unevaluated";
  baseline_overall_outcome?: DecisionOutcome;
  scenario_overall_outcome?: DecisionOutcome;
  outcome_shift?: OutcomeShift | string;
  evaluation?: StressEvaluation;
  processing_mode: "gemini" | "fallback";
  created_at: string;
}

export interface StressTestingBaseline {
  baseline_outcome: DecisionOutcome;
  total_requirements: number;
  sufficient_requirements: number;
  partial_requirements: number;
  insufficient_requirements: number;
  no_evidence_requirements: number;
  conflicting_requirements: number;
  active_conflicts: number;
  critical_conflicts: number;
  unresolved_gaps: number;
  baseline_rationale: string;
  key_dependencies: string[];
}

export interface StressTestingSummary {
  total_scenarios: number;
  evaluated_scenarios: number;
  vulnerable_scenarios: number;
  indeterminate_scenarios: number;
  critical_severity_count: number;
  high_severity_count: number;
  baseline_outcome: DecisionOutcome;
  processing_mode: "gemini" | "fallback" | "pending";
}

export interface StressTestListResponse {
  investigation_id: string;
  baseline: StressTestingBaseline;
  summary: StressTestingSummary;
  scenarios: StressScenario[];
  processing_mode: "gemini" | "fallback" | "pending";
  last_generated_at?: string;
}

export interface StressTestStatus {
  investigation_id: string;
  total_scenarios: number;
  evaluated_scenarios: number;
  baseline_outcome: DecisionOutcome;
  processing_mode: "gemini" | "fallback" | "pending";
  last_run_status: string;
  last_generated_at?: string;
}

export async function getInvestigationStressTests(
  investigationId: string,
  filters?: { category?: string; severity?: string; evaluation_status?: string }
): Promise<StressTestListResponse> {
  const params = new URLSearchParams();
  if (filters?.category) params.append("category", filters.category);
  if (filters?.severity) params.append("severity", filters.severity);
  if (filters?.evaluation_status) params.append("evaluation_status", filters.evaluation_status);
  const qStr = params.toString() ? `?${params.toString()}` : "";

  const res = await fetch(`${API_BASE}/investigations/${investigationId}/stress-tests${qStr}`);
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ detail: "Failed to load stress tests" }));
    throw new Error(errorData.detail || `Server returned ${res.status}`);
  }
  return res.json();
}

export async function generateInvestigationStressScenarios(investigationId: string): Promise<StressTestListResponse> {
  const res = await fetch(`${API_BASE}/investigations/${investigationId}/stress-tests/generate`, {
    method: "POST",
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ detail: "Scenario generation failed" }));
    throw new Error(errorData.detail || `Server returned ${res.status}`);
  }
  return res.json();
}

export async function evaluateInvestigationStressScenario(
  investigationId: string,
  scenarioId: string
): Promise<StressScenario> {
  const res = await fetch(`${API_BASE}/investigations/${investigationId}/stress-tests/${scenarioId}/evaluate`, {
    method: "POST",
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ detail: "Scenario evaluation failed" }));
    throw new Error(errorData.detail || `Server returned ${res.status}`);
  }
  return res.json();
}

export async function getStressScenarioDetail(
  investigationId: string,
  scenarioId: string
): Promise<StressScenario> {
  const res = await fetch(`${API_BASE}/investigations/${investigationId}/stress-tests/${scenarioId}`);
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ detail: "Failed to load scenario detail" }));
    throw new Error(errorData.detail || `Server returned ${res.status}`);
  }
  return res.json();
}

export async function getStressTestStatus(investigationId: string): Promise<StressTestStatus> {
  const res = await fetch(`${API_BASE}/investigations/${investigationId}/stress-tests/status`);
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ detail: "Failed to load stress test status" }));
    throw new Error(errorData.detail || `Server returned ${res.status}`);
  }
  return res.json();
}

// ==========================================
// Component 08 Types (Decision Intelligence Report Engine)
// ==========================================

export interface ExecutiveBriefSection {
  investigation_id: string;
  research_question: string;
  decision_objective: string;
  report_version: number;
  generated_at: string;
  overall_robustness: DecisionOutcome;
  coverage_ratio: number;
  total_sources: number;
  total_claims: number;
  unresolved_conflicts_count: number;
  identified_gaps_count: number;
  high_severity_scenarios_count: number;
  executive_conclusion: string;
}

export interface ContractRequirementSummary {
  requirement_id: string;
  title: string;
  priority: string;
  verification_criteria: string;
  evidence_types: string[];
}

export interface DecisionContractSummarySection {
  contract_id: string;
  normalized_question: string;
  decision_objective: string;
  scope: string;
  requirements: ContractRequirementSummary[];
  constraints: string[];
  assumptions: string[];
  unresolved_questions: string[];
}

export interface SourceProvenanceItem {
  source_id: string;
  title: string;
  source_origin?: string;
  publisher: string;
  publication_date: string;
  ingestion_date?: string;
  freshness_classification?: string;
  date_extraction_origin?: string;
  freshness_warning?: string;
  original_url?: string;
  source_type: string;
  sha256_hash: string;
  extraction_status: string;
  claims_count: number;
}

export interface EvidenceIntelligenceSection {
  total_sources: number;
  total_passages: number;
  total_claims: number;
  factual_claims_count: number;
  statistical_claims_count: number;
  sources: SourceProvenanceItem[];
  reliability_limitations: string;
}

export interface SupportingClaimItem {
  claim_id: string;
  claim_text: string;
  source_title: string;
  source_id: string;
  passage_hash: string;
  relevance: string;
  confidence: number;
}

export interface OpposingEvidenceItem {
  conflict_id: string;
  conflict_type: string;
  severity: string;
  claim_text: string;
  source_title: string;
  resolution_status: string;
}

export interface RequirementAssessmentRow {
  requirement_id: string;
  title: string;
  priority: string;
  coverage_status: CoverageStatus;
  supporting_claims: SupportingClaimItem[];
  opposing_evidence: OpposingEvidenceItem[];
  identified_gaps: string[];
  assessment_summary: string;
  confidence: number;
}

export interface RequirementAssessmentSection {
  matrix: RequirementAssessmentRow[];
  coverage_summary: Record<string, number>;
}

export interface ReportConflictItem {
  conflict_id: string;
  conflict_type: string;
  severity: string;
  claim_a_id: string;
  claim_a_text: string;
  claim_a_source: string;
  claim_b_id: string;
  claim_b_text: string;
  claim_b_source: string;
  explanation: string;
  resolution_status: string;
  reviewer_notes: string;
  decision_impact: string;
}

export interface ConflictAnalysisSection {
  total_conflicts: number;
  unresolved_count: number;
  critical_count: number;
  conflicts: ReportConflictItem[];
}

export interface ReportGapItem {
  gap_id: string;
  requirement_id: string;
  requirement_title: string;
  gap_description: string;
  why_it_matters: string;
  evidence_needed: string;
  suggested_source_type: string;
  priority: "HIGH" | "MEDIUM" | "LOW";
}

export interface GapsAndUncertaintySection {
  total_gaps: number;
  high_priority_gaps: number;
  gaps: ReportGapItem[];
}

export interface ReportStressScenarioItem {
  scenario_id: string;
  title: string;
  category: string;
  trigger_condition: string;
  severity: string;
  outcome_shift: string;
  scenario_outcome: string;
  impact_explanation: string;
  key_vulnerabilities: string[];
}

export interface StressTestResultsSection {
  baseline_outcome: DecisionOutcome;
  total_scenarios: number;
  vulnerable_scenarios: number;
  scenarios: ReportStressScenarioItem[];
}

export interface RiskRegisterItem {
  risk_id: string;
  title: string;
  origin: "Conflict" | "Evidence Gap" | "Stress Scenario" | "Contract Assumption" | string;
  severity: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW" | string;
  affected_requirement: string;
  consequence: string;
  mitigation: string;
  additional_evidence_needed: string;
}

export interface RiskMitigationSection {
  total_risks: number;
  critical_risks: number;
  high_risks: number;
  risks: RiskRegisterItem[];
}

export interface RecommendedActionItem {
  action_id: string;
  action_title: string;
  description: string;
  priority: "P1_IMMEDIATE" | "P2_HIGH" | "P3_MODERATE" | string;
  driver: string;
  target_requirement: string;
  expected_outcome: string;
}

export interface RecommendedActionsSection {
  actions: RecommendedActionItem[];
}

export interface FinalConclusionSection {
  supported_findings: string[];
  uncertainties_and_caveats: string[];
  invalidating_conditions: string[];
  recommended_decision_posture: string;
  epistemic_boundary_disclaimer: string;
}

export interface DecisionReportPayload {
  executive_brief: ExecutiveBriefSection;
  decision_contract: DecisionContractSummarySection;
  evidence_intelligence: EvidenceIntelligenceSection;
  requirement_assessment: RequirementAssessmentSection;
  conflict_analysis: ConflictAnalysisSection;
  gaps_and_uncertainty: GapsAndUncertaintySection;
  stress_test_results: StressTestResultsSection;
  risk_mitigation: RiskMitigationSection;
  recommended_actions: RecommendedActionsSection;
  final_conclusion: FinalConclusionSection;
}

export interface DecisionReport {
  id: string;
  investigation_id: string;
  report_version: number;
  report_status: string;
  processing_mode: "gemini" | "fallback";
  overall_robustness: DecisionOutcome;
  executive_summary: string;
  report_data: DecisionReportPayload;
  snapshot_metadata: Record<string, any>;
  is_stale: boolean;
  created_at: string;
  updated_at: string;
}

export interface DecisionReportSummary {
  id: string;
  investigation_id: string;
  report_version: number;
  report_status: string;
  processing_mode: "gemini" | "fallback";
  overall_robustness: DecisionOutcome;
  executive_summary: string;
  is_stale: boolean;
  created_at: string;
}

export interface DecisionReportListResponse {
  investigation_id: string;
  total_reports: number;
  latest_version: number;
  reports: DecisionReportSummary[];
}

export interface DecisionReportStatus {
  investigation_id: string;
  has_report: boolean;
  latest_report_id?: string;
  latest_version: number;
  latest_status?: string;
  is_stale: boolean;
  overall_robustness?: DecisionOutcome;
  processing_mode: "gemini" | "fallback" | "none";
  last_generated_at?: string;
}

export async function getInvestigationReports(investigationId: string): Promise<DecisionReportListResponse> {
  const res = await fetch(`${API_BASE}/investigations/${investigationId}/reports`);
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ detail: "Failed to load reports" }));
    throw new Error(errorData.detail || `Server returned ${res.status}`);
  }
  return res.json();
}

export async function getLatestInvestigationReport(investigationId: string): Promise<DecisionReport> {
  const res = await fetch(`${API_BASE}/investigations/${investigationId}/reports/latest`);
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ detail: "Failed to load latest report" }));
    throw new Error(errorData.detail || `Server returned ${res.status}`);
  }
  return res.json();
}

export async function getReportById(investigationId: string, reportId: string): Promise<DecisionReport> {
  const res = await fetch(`${API_BASE}/investigations/${investigationId}/reports/${reportId}`);
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ detail: "Failed to load report" }));
    throw new Error(errorData.detail || `Server returned ${res.status}`);
  }
  return res.json();
}

export async function generateInvestigationReport(investigationId: string, fast: boolean = false): Promise<DecisionReport> {
  const url = fast
    ? `${API_BASE}/investigations/${investigationId}/reports/generate?fast=true`
    : `${API_BASE}/investigations/${investigationId}/reports/generate`;
  const res = await fetch(url, {
    method: "POST",
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ detail: "Failed to generate report" }));
    throw new Error(errorData.detail || `Server returned ${res.status}`);
  }
  return res.json();
}

export async function getReportStatus(investigationId: string): Promise<DecisionReportStatus> {
  const res = await fetch(`${API_BASE}/investigations/${investigationId}/reports/status`);
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ detail: "Failed to load report status" }));
    throw new Error(errorData.detail || `Server returned ${res.status}`);
  }
  return res.json();
}

// ==========================================
// Component 09: Decision Fragility Index & Sensitivity
// ==========================================

export interface FragilityDimensionDetail {
  dimension_key: string;
  dimension_name: string;
  score: number;
  weight: number;
  weighted_contribution: number;
  status: "ASSESSED" | "NOT_ASSESSED" | "NOT_APPLICABLE";
  explanation: string;
  metrics: Record<string, any>;
}

export interface AttributionLedgerItem {
  item_id: string;
  dimension: string;
  category: string;
  entity_id: string;
  entity_type: string;
  entity_title: string;
  base_penalty: number;
  multiplier: number;
  net_dimension_points: number;
  net_dfi_contribution: number;
  rationale: string;
}

export interface DecisionFragilityResult {
  id: string;
  run_id: string;
  investigation_id: string;
  methodology_version: string;
  dfi_score: number;
  classification: string;
  is_provisional: boolean;
  provisional_reasons: string[];
  guardrail_active: boolean;
  guardrail_reason?: string;
  unsubstantiated_critical_requirements: string[];
  d1_coverage: number;
  d2_assumptions: number;
  d3_conflicts: number;
  d4_stress: number;
  d5_concentration: number;
  dimensions: Record<string, FragilityDimensionDetail>;
  attribution_ledger: AttributionLedgerItem[];
  explanation_text: string;
  processing_mode: "gemini" | "fallback";
  is_stale?: boolean;
  created_at: string;
}

export interface FragilityAnalysisResponse {
  status: string;
  investigation_id: string;
  run_id: string;
  result: DecisionFragilityResult;
  message?: string;
}

export interface FragilityStatus {
  investigation_id: string;
  has_result: boolean;
  latest_run_id?: string;
  dfi_score?: number;
  classification?: string;
  is_provisional: boolean;
  guardrail_active: boolean;
  guardrail_reason?: string;
  has_unsubstantiated_critical: boolean;
  is_stale: boolean;
  is_indeterminate: boolean;
  indeterminate_reason?: string;
  created_at?: string;
}

export interface SensitivitySimulationRequest {
  experiment_type: "SIM_EVIDENCE_WEAKENING" | "SIM_GAP_CORROBORATION" | "SIM_CONFLICT_RESOLUTION" | "SIM_ASSUMPTION_FAILURE";
  target_entity_id: string;
  target_entity_type: "requirement" | "conflict" | "assumption";
  hypothetical_parameters?: Record<string, any>;
}

export interface SensitivityExperimentResult {
  id: string;
  investigation_id: string;
  experiment_type: string;
  is_hypothetical: boolean;
  target_entity_id: string;
  target_entity_type: string;
  target_entity_title: string;
  baseline_dfi: number;
  simulated_dfi: number;
  delta_dfi: number;
  baseline_classification: string;
  simulated_classification: string;
  simulated_guardrail_active: boolean;
  simulated_guardrail_reason?: string;
  simulation_parameters: Record<string, any>;
  narrative_impact: string;
  created_at: string;
}

export interface SensitivityAnalysisResponse {
  investigation_id: string;
  baseline_dfi: number;
  baseline_classification: string;
  experiments: SensitivityExperimentResult[];
}

export interface EvidenceImprovementRecommendation {
  id: string;
  investigation_id: string;
  run_id?: string;
  recommendation_type: "RESOLVE_CONFLICT" | "VERIFY_ASSUMPTION" | "FILL_CRITICAL_GAP" | "CORROBORATE_EVIDENCE";
  target_entity_id: string;
  target_entity_type: string;
  title: string;
  description: string;
  projected_dfi_reduction: number;
  is_hypothetical_projection: boolean;
  priority: "HIGH" | "MEDIUM" | "LOW";
  effort_estimate: "LOW" | "MEDIUM" | "HIGH";
  action_steps: string[];
  created_at: string;
}

export interface FragilityRecommendationsResponse {
  investigation_id: string;
  total_recommendations: number;
  max_projected_reduction: number;
  recommendations: EvidenceImprovementRecommendation[];
}

export interface FragilityMethodology {
  version: string;
  weights: Record<string, number>;
  deficit_penalties: Record<string, number>;
  conflict_penalties: Record<string, number>;
  stress_shift_penalties: Record<string, number>;
  guardrail_criteria: string;
  provisional_policy: string;
  rounding_rule: string;
  epistemic_disclaimer: string;
}

export async function getLatestFragility(investigationId: string): Promise<DecisionFragilityResult> {
  const res = await fetch(`${API_BASE}/investigations/${investigationId}/fragility/latest`);
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ detail: "Failed to load fragility result" }));
    throw new Error(errorData.detail || `Server returned ${res.status}`);
  }
  return res.json();
}

export async function runFragilityAnalysis(investigationId: string, allowGemini: boolean = true): Promise<FragilityAnalysisResponse> {
  const res = await fetch(`${API_BASE}/investigations/${investigationId}/fragility/analyze?allow_gemini=${allowGemini}`, {
    method: "POST",
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ detail: "Fragility analysis failed" }));
    throw new Error(errorData.detail || `Server returned ${res.status}`);
  }
  return res.json();
}

export async function getFragilityStatus(investigationId: string): Promise<FragilityStatus> {
  const res = await fetch(`${API_BASE}/investigations/${investigationId}/fragility/status`);
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ detail: "Failed to load fragility status" }));
    throw new Error(errorData.detail || `Server returned ${res.status}`);
  }
  return res.json();
}

export async function simulateSensitivity(
  investigationId: string,
  req: SensitivitySimulationRequest
): Promise<SensitivityExperimentResult> {
  const res = await fetch(`${API_BASE}/investigations/${investigationId}/fragility/sensitivity/simulate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ detail: "Sensitivity simulation failed" }));
    throw new Error(errorData.detail || `Server returned ${res.status}`);
  }
  return res.json();
}

export async function getSensitivityResults(investigationId: string): Promise<SensitivityAnalysisResponse> {
  const res = await fetch(`${API_BASE}/investigations/${investigationId}/fragility/sensitivity/results`);
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ detail: "Failed to load sensitivity results" }));
    throw new Error(errorData.detail || `Server returned ${res.status}`);
  }
  return res.json();
}

export async function getFragilityRecommendations(investigationId: string): Promise<FragilityRecommendationsResponse> {
  const res = await fetch(`${API_BASE}/investigations/${investigationId}/fragility/recommendations`);
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ detail: "Failed to load fragility recommendations" }));
    throw new Error(errorData.detail || `Server returned ${res.status}`);
  }
  return res.json();
}

export async function getFragilityMethodology(): Promise<FragilityMethodology> {
  const res = await fetch(`${API_BASE}/fragility/methodology`);
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ detail: "Failed to load fragility methodology" }));
    throw new Error(errorData.detail || `Server returned ${res.status}`);
  }
  return res.json();
}

// ==========================================
// Component 10: Gap Verification & Update Navigator
// ==========================================

export interface StageExecutionRecord {
  status: "COMPLETED" | "NOT_AFFECTED" | "NOT_RUN" | "FAILED";
  skipped_reason?: string;
  duration_ms?: number;
}

export interface SourceImpactSummary {
  orchestration_run_id: string;
  investigation_id: string;
  source_id: string;
  source_title: string;
  source_url_or_filename: string;
  authority_tier: "TIER_1" | "TIER_2" | "TIER_3" | "TIER_4";
  is_duplicate: boolean;
  total_claims_extracted: number;
  claims_by_category: Record<string, number>;
  extracted_claim_previews: Array<{ claim_id: string; text: string; category: string }>;
  affected_requirements: Array<Record<string, any>>;
  affected_assumptions: Array<Record<string, any>>;
  new_conflicts_detected: Array<Record<string, any>>;
  conflicts_resolved_count: number;
  gaps_resolved: string[];
  gaps_reduced: string[];
  gaps_unchanged: string[];
  gaps_worsened: string[];
  baseline_outcome_shifted: boolean;
  old_baseline_outcome: string;
  new_baseline_outcome: string;
  old_dfi_score: number;
  new_dfi_score: number;
  delta_dfi: number;
  old_classification: string;
  new_classification: string;
  guardrail_status_changed: boolean;
  report_invalidated: boolean;
  unresolved_items_remaining: number;
  pending_analyst_actions: string[];
  stages_execution: Record<string, StageExecutionRecord>;
  executive_impact_narrative: string;
  processing_mode: "gemini" | "fallback";
  created_at: string;
}

export interface GapVerificationPlan {
  id: string;
  investigation_id: string;
  gap_id: string;
  requirement_id: string;
  requirement_title?: string;
  verification_objective: string;
  required_evidence_type: string;
  target_authority_tier: string;
  search_queries: string[];
  search_provider_status: "ACTIVE" | "UNAVAILABLE";
  status: string;
  missing_context_warning?: string | null;
  candidates?: GapCandidateSource[];
  created_at: string;
}

export interface GapCandidateSource {
  id: string;
  plan_id: string;
  investigation_id: string;
  url: string;
  domain: string;
  title: string;
  snippet: string;
  authority_tier: string;
  relevance_score: number;
  discovery_mode: "MANUAL_ENTRY" | "SEARCH_PROVIDER";
  relevance_rationale: string;
  review_status: "PENDING_REVIEW" | "APPROVED" | "REJECTED";
  rejection_reason?: string | null;
  discovered_at: string;
}

export interface GapReassessment {
  id: string;
  investigation_id: string;
  gap_id: string;
  orchestration_run_id?: string;
  previous_state: string;
  proposed_resolution_state: string;
  analyst_decision: "APPROVED" | "OVERRIDDEN" | "REJECTED" | "PENDING_DECISION";
  analyst_final_state?: string;
  analyst_notes?: string;
  reviewed_by?: string;
  reviewed_at?: string;
  matched_claim_ids: string[];
  predicate_fulfillment_score: number;
  composite_evidence_score: number;
  is_analyst_override: boolean;
  created_at: string;
}

export interface GapQueueItem {
  gap_id: string;
  requirement_id: string;
  requirement_title: string;
  priority: string;
  gap_description: string;
  why_it_matters: string;
  evidence_needed: string;
  suggested_source_type: string;
  current_coverage_status: string;
  projected_dfi_reduction: number;
  verification_state: string;
  has_active_plan?: boolean;
  active_plan_id?: string;
  latest_reassessment_id?: string;
}

export interface NavigatorQueueResponse {
  investigation_id: string;
  total_gaps: number;
  search_provider: string;
  search_provider_active: boolean;
  queue: GapQueueItem[];
}

export interface OrchestrationAuditLogItem {
  id: string;
  investigation_id: string;
  orchestration_run_id?: string;
  source_id?: string;
  event_type: string;
  actor: string;
  details: Record<string, any>;
  created_at: string;
}

export async function getNavigatorQueue(investigationId: string): Promise<NavigatorQueueResponse> {
  const res = await fetch(`${API_BASE}/investigations/${investigationId}/navigator/gaps/queue`);
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ detail: "Failed to load verification queue" }));
    throw new Error(errorData.detail || `Server returned ${res.status}`);
  }
  return res.json();
}

export async function generateVerificationPlan(
  investigationId: string,
  gapId: string,
  customInstructions?: string,
  manualQueries?: string[]
): Promise<GapVerificationPlan> {
  const body: { custom_instructions?: string; manual_queries?: string[] } = {};
  if (customInstructions) body.custom_instructions = customInstructions;
  if (manualQueries && manualQueries.length > 0) body.manual_queries = manualQueries;

  const res = await fetch(`${API_BASE}/investigations/${investigationId}/navigator/gaps/${gapId}/plan`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ detail: "Failed to generate verification plan" }));
    throw new Error(errorData.detail || `Server returned ${res.status}`);
  }
  return res.json();
}

export async function getVerificationPlan(investigationId: string, planId: string): Promise<GapVerificationPlan> {
  const res = await fetch(`${API_BASE}/investigations/${investigationId}/navigator/plans/${planId}`);
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ detail: "Failed to fetch verification plan" }));
    throw new Error(errorData.detail || `Server returned ${res.status}`);
  }
  return res.json();
}

export async function updatePlanQueries(
  investigationId: string,
  planId: string,
  queries: string[]
): Promise<GapVerificationPlan> {
  const res = await fetch(`${API_BASE}/investigations/${investigationId}/navigator/plans/${planId}/queries`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ queries }),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ detail: "Failed to update verification queries" }));
    throw new Error(errorData.detail || `Server returned ${res.status}`);
  }
  return res.json();
}

export async function submitManualCandidate(
  investigationId: string,
  planId: string,
  payload: { url: string; title?: string; snippet?: string }
): Promise<GapCandidateSource> {
  const res = await fetch(`${API_BASE}/investigations/${investigationId}/navigator/plans/${planId}/candidates/manual`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ detail: "Failed to submit candidate source" }));
    throw new Error(errorData.detail || `Server returned ${res.status}`);
  }
  return res.json();
}

export async function reviewCandidateSource(
  investigationId: string,
  candidateId: string,
  action: "APPROVE" | "REJECT",
  rejectionReason?: string
): Promise<GapCandidateSource> {
  const res = await fetch(`${API_BASE}/investigations/${investigationId}/navigator/candidates/${candidateId}/review`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action, rejection_reason: rejectionReason }),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ detail: "Failed to review candidate source" }));
    throw new Error(errorData.detail || `Server returned ${res.status}`);
  }
  return res.json();
}

export async function evaluateGap(investigationId: string, gapId: string): Promise<GapReassessment> {
  const res = await fetch(`${API_BASE}/investigations/${investigationId}/navigator/gaps/${gapId}/evaluate`, {
    method: "POST",
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ detail: "Failed to evaluate gap" }));
    throw new Error(errorData.detail || `Server returned ${res.status}`);
  }
  return res.json();
}

export async function commitGapReassessment(
  investigationId: string,
  reassessmentId: string,
  payload: { analyst_decision: string; analyst_final_state: string; analyst_notes: string; analyst_id?: string }
): Promise<GapReassessment> {
  const res = await fetch(`${API_BASE}/investigations/${investigationId}/navigator/reassessments/${reassessmentId}/commit`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ detail: "Failed to commit gap reassessment" }));
    throw new Error(errorData.detail || `Server returned ${res.status}`);
  }
  return res.json();
}

export async function getSourceImpactSummary(investigationId: string, sourceId: string): Promise<SourceImpactSummary> {
  const res = await fetch(`${API_BASE}/investigations/${investigationId}/navigator/sources/${sourceId}/impact`);
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ detail: "Failed to load source impact summary" }));
    throw new Error(errorData.detail || `Server returned ${res.status}`);
  }
  return res.json();
}

export async function orchestrateSource(investigationId: string, sourceId: string): Promise<SourceImpactSummary> {
  const res = await fetch(`${API_BASE}/investigations/${investigationId}/navigator/orchestrate/source/${sourceId}`, {
    method: "POST",
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ detail: "Failed to orchestrate source" }));
    throw new Error(errorData.detail || `Server returned ${res.status}`);
  }
  return res.json();
}

export async function getNavigatorAuditTrail(investigationId: string): Promise<OrchestrationAuditLogItem[]> {
  const res = await fetch(`${API_BASE}/investigations/${investigationId}/navigator/audit-trail`);
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ detail: "Failed to load audit trail" }));
    throw new Error(errorData.detail || `Server returned ${res.status}`);
  }
  return res.json();
}






