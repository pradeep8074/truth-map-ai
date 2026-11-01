from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


# ==========================================
# Component 02 Models (Ingestion & Claims)
# ==========================================

class InvestigationCreateRequest(BaseModel):
    research_question: str = Field(..., min_length=5, description="The core inquiry or decision hypothesis to evaluate")
    urls: List[str] = Field(default_factory=list, description="Initial list of web URLs to ingest")


class SourceAddRequest(BaseModel):
    urls: List[str] = Field(..., min_length=1, description="List of web URLs to add to an investigation")


class InvestigationCreateResponse(BaseModel):
    investigation_id: str
    status: str
    message: Optional[str] = None


class PassageResponse(BaseModel):
    id: str
    source_id: str
    passage_text: str
    page_number: Optional[int] = None
    paragraph_index: Optional[int] = None
    start_offset: Optional[int] = None
    end_offset: Optional[int] = None
    sha256_hash: str


class ClaimResponse(BaseModel):
    id: str
    investigation_id: str
    source_id: str
    passage_id: str
    claim_text: str
    category: str = "factual"
    extraction_method: str
    processing_mode: str = "fallback"  # "gemini" or "fallback"
    extraction_confidence: float
    created_at: str
    passage_text: Optional[str] = None
    page_number: Optional[int] = None
    source_title: Optional[str] = None
    source_type: Optional[str] = None


class SourceResponse(BaseModel):
    id: str
    investigation_id: str
    source_type: str
    source_origin: str = "UNKNOWN"
    original_url: Optional[str] = None
    title: Optional[str] = None
    publisher: Optional[str] = None
    publication_date: Optional[str] = None
    source_modified_date: Optional[str] = None
    date_source: Optional[str] = None
    date_extraction_method: Optional[str] = None
    date_confidence: float = 0.0
    date_validation_status: str = "MISSING"
    freshness_status: str = "Undated Source"
    freshness_explanation: str = ""
    days_old: Optional[int] = None
    retrieved_at: str
    content_hash: Optional[str] = None
    extraction_status: str
    passages_count: int = 0
    claims_count: int = 0
    error_message: Optional[str] = None


class WorkspaceFreshnessSummary(BaseModel):
    total_sources: int
    dated_sources: int
    undated_sources: int
    potentially_outdated_sources: int
    sources_requiring_review: int
    freshness_threshold_days: int = 365
    reference_date: str



class InvestigationResponse(BaseModel):
    id: str
    research_question: str
    status: str
    created_at: str
    sources_count: int
    claims_count: int
    requirements_count: int = 0
    has_contract: bool = False
    sources: List[SourceResponse] = Field(default_factory=list)


# ==========================================
# Component 03 Models (Decision Contract)
# ==========================================

class EvidenceRequirementModel(BaseModel):
    evidence_requirement_id: str
    requirement_id: str
    evidence_type: str
    rationale: str
    preferred_source_types: List[str] = Field(default_factory=list)
    temporal_scope: Optional[str] = None
    geographic_scope: Optional[str] = None


class RequirementModel(BaseModel):
    requirement_id: str
    title: str
    description: str
    requirement_type: str = Field(..., description="FACTUAL, QUANTITATIVE, COMPARATIVE, CAUSAL, TEMPORAL, GEOGRAPHIC, ELIGIBILITY, RISK, IMPLEMENTATION")
    priority: str = Field(..., description="CRITICAL, HIGH, MEDIUM, LOW")
    verification_criteria: str
    status: str = Field(default="unverified", description="unverified, partially_satisfied, satisfied")
    evidence_needed: List[EvidenceRequirementModel] = Field(default_factory=list)


class ConstraintModel(BaseModel):
    constraint_id: str
    description: str
    constraint_type: str = Field(default="scope_boundary", description="scope_boundary, causal_discipline, negative_presumption")


class AssumptionModel(BaseModel):
    assumption_id: str
    description: str
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    source: str = Field(default="ai_inferred", description="'user_provided' or 'ai_inferred'")
    validation_status: str = Field(default="pending", description="pending, validated, refuted")


class UnresolvedQuestionModel(BaseModel):
    question_id: str
    question: str
    clarification_type: str = Field(..., description="required, optional, assumption_review")
    dimension: str = Field(..., description="geographic, temporal, population, metric, baseline, causal")


class DecisionContractModel(BaseModel):
    contract_id: str
    investigation_id: str
    original_question: str
    normalized_question: str
    decision_objective: str
    scope: Optional[str] = None
    compilation_method: str
    processing_mode: str = Field(default="fallback", description="'gemini' or 'fallback'")
    created_at: str
    updated_at: str
    requirements: List[RequirementModel] = Field(default_factory=list)
    evidence_requirements: List[EvidenceRequirementModel] = Field(default_factory=list)
    constraints: List[ConstraintModel] = Field(default_factory=list)
    assumptions: List[AssumptionModel] = Field(default_factory=list)
    unresolved_questions: List[UnresolvedQuestionModel] = Field(default_factory=list)


class ContractUpdateRequest(BaseModel):
    decision_objective: Optional[str] = None
    scope: Optional[str] = None
    requirements: Optional[List[RequirementModel]] = None
    constraints: Optional[List[ConstraintModel]] = None
    assumptions: Optional[List[AssumptionModel]] = None
    unresolved_questions: Optional[List[UnresolvedQuestionModel]] = None


# ==========================================
# Component 04 Models (Evidence Dependency Graph)
# ==========================================

class GraphNodeModel(BaseModel):
    id: str = Field(..., description="Stable node ID: e.g. contract_{id}, req_{id}, claim_{id}")
    type: str = Field(..., description="decision_contract, decision_requirement, evidence_requirement, atomic_claim, source_passage, source_document")
    label: str = Field(..., description="Display label for visualization")
    record_id: str = Field(..., description="Underlying database record primary key")
    metadata: dict = Field(default_factory=dict, description="Arbitrary attributes (category, confidence, status, snippet)")


class GraphEdgeModel(BaseModel):
    id: str = Field(..., description="Stable edge ID: e.g. edge_{source}_{target}_{rel}")
    source: str = Field(..., description="Source node ID")
    target: str = Field(..., description="Target node ID")
    relationship: str = Field(..., description="HAS_REQUIREMENT, REQUIRES_EVIDENCE, RELATES_TO, EXTRACTED_FROM, BELONGS_TO_SOURCE")
    origin: str = Field(default="structural", description="structural, gemini, or fallback")
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    metadata: dict = Field(default_factory=dict, description="Edge metadata (explanation, classification)")


class GraphSummaryModel(BaseModel):
    total_nodes: int = 0
    total_edges: int = 0
    contract_nodes: int = 0
    requirement_nodes: int = 0
    evidence_requirement_nodes: int = 0
    claim_nodes: int = 0
    passage_nodes: int = 0
    source_nodes: int = 0
    scenario_nodes: int = 0
    directly_relevant_links: int = 0
    partially_relevant_links: int = 0
    contextual_links: int = 0


class EvidenceGraphResponse(BaseModel):
    investigation_id: str
    nodes: List[GraphNodeModel] = Field(default_factory=list)
    edges: List[GraphEdgeModel] = Field(default_factory=list)
    processing_mode: str = Field(default="pending", description="'gemini', 'fallback', or 'pending'")
    last_analyzed_at: Optional[str] = None
    summary: GraphSummaryModel = Field(default_factory=GraphSummaryModel)


class EvidenceGraphStatusResponse(BaseModel):
    investigation_id: str
    total_nodes: int
    total_edges: int
    requirements_represented: int
    claims_represented: int
    sources_represented: int
    processing_mode: str  # 'gemini', 'fallback', or 'pending'
    last_analysis_status: str  # 'completed', 'pending', or 'none'
    relationships_count: int
    directly_relevant_count: int
    partially_relevant_count: int
    contextual_count: int


# ==========================================
# Component 05 Models (Conflict Detection Engine)
# ==========================================

class ConflictItemModel(BaseModel):
    conflict_id: str
    investigation_id: str
    claim_a_id: str
    claim_b_id: str
    claim_a_text: str
    claim_b_text: str
    claim_a_category: Optional[str] = None
    claim_b_category: Optional[str] = None
    source_a_id: Optional[str] = None
    source_b_id: Optional[str] = None
    source_a_title: Optional[str] = None
    source_b_title: Optional[str] = None
    source_a_url: Optional[str] = None
    source_b_url: Optional[str] = None
    passage_a_text: Optional[str] = None
    passage_b_text: Optional[str] = None
    passage_a_page: Optional[int] = None
    passage_b_page: Optional[int] = None
    passage_a_hash: Optional[str] = None
    passage_b_hash: Optional[str] = None
    conflict_type: str = Field(..., description="DIRECT_CONTRADICTION, NUMERICAL_CONFLICT, TEMPORAL_CONFLICT, CONTEXTUAL_TENSION, METHODOLOGICAL_DISAGREEMENT, UNRESOLVED_CONFLICT, SCOPE_MISMATCH, RELATED_INFORMATION_REQUIRING_ANALYST_REVIEW")
    severity: str = Field(..., description="CRITICAL, HIGH, MEDIUM, LOW")
    explanation: str
    contextual_differences: Optional[str] = None
    confidence: float = Field(..., ge=0.0, le=1.0)
    resolution_status: str = Field(default="unresolved", description="unresolved, under_review, resolved")
    reviewer_notes: Optional[str] = ""
    recommended_action: str
    analysis_method: str
    processing_mode: str = Field(default="fallback", description="'gemini' or 'fallback'")
    created_at: str
    updated_at: str


class ConflictSummaryModel(BaseModel):
    total_conflicts: int = 0
    direct_contradictions: int = 0
    numerical_conflicts: int = 0
    temporal_conflicts: int = 0
    contextual_tensions: int = 0
    methodological_disagreements: int = 0
    scope_mismatches: int = 0
    analyst_review_needed: int = 0
    unresolved_conflicts: int = 0
    critical_severity: int = 0
    high_severity: int = 0
    medium_severity: int = 0
    low_severity: int = 0
    under_review_count: int = 0
    resolved_count: int = 0


class ConflictListResponse(BaseModel):
    investigation_id: str
    conflicts: List[ConflictItemModel] = Field(default_factory=list)
    summary: ConflictSummaryModel = Field(default_factory=ConflictSummaryModel)
    processing_mode: str = Field(default="pending", description="'gemini', 'fallback', or 'pending'")
    last_analyzed_at: Optional[str] = None


class ConflictStatusResponse(BaseModel):
    investigation_id: str
    total_conflicts: int
    direct_contradictions: int
    numerical_conflicts: int
    contextual_tensions: int
    unresolved_conflicts: int
    processing_mode: str
    last_analysis_status: str
    last_analyzed_at: Optional[str] = None


class ConflictResolutionUpdateRequest(BaseModel):
    resolution_status: Optional[str] = Field(None, description="unresolved, under_review, resolved")
    reviewer_notes: Optional[str] = Field(None, description="Forensic notes added by the analyst")


class GeminiConflictFinding(BaseModel):
    claim_a_id: str = Field(..., description="First Claim ID")
    claim_b_id: str = Field(..., description="Second Claim ID")
    conflict_type: str = Field(..., description="DIRECT_CONTRADICTION, NUMERICAL_CONFLICT, TEMPORAL_CONFLICT, CONTEXTUAL_TENSION, METHODOLOGICAL_DISAGREEMENT, UNRESOLVED_CONFLICT")
    severity: str = Field(..., description="CRITICAL, HIGH, MEDIUM, LOW")
    explanation: str = Field(..., description="Forensic explanation of the specific factual, numerical, or contextual clash")
    contextual_differences: str = Field(..., description="Confounding factors or conditions (e.g. differing observation dates, cohort populations, administrative definitions) that may explain the divergence")
    confidence: float = Field(..., ge=0.0, le=1.0)
    recommended_action: str = Field(..., description="Actionable verification requirement to resolve or falsify the tension")


class GeminiConflictAnalysisPayload(BaseModel):
    conflicts: List[GeminiConflictFinding] = Field(default_factory=list)


# ==========================================
# Component 06 Models (Evidence Sufficiency & Gap Analysis)
# ==========================================

class EvidenceGapModel(BaseModel):
    id: str
    investigation_id: str
    requirement_id: str
    assessment_id: Optional[str] = None
    gap_description: str
    why_it_matters: str
    evidence_needed: str
    suggested_source_type: Optional[str] = "Authoritative Audit / Regulatory Filing"
    priority: str = Field(..., description="HIGH, MEDIUM, LOW")
    created_at: str


class SupportingClaimInfo(BaseModel):
    claim_id: str
    claim_text: str
    category: Optional[str] = None
    relevance: str = Field(..., description="DIRECTLY_RELEVANT, PARTIALLY_RELEVANT, CONTEXTUAL")
    relevance_explanation: Optional[str] = None
    extraction_confidence: float = 0.85
    source_id: Optional[str] = None
    source_title: Optional[str] = None
    source_type: Optional[str] = None
    source_url: Optional[str] = None
    passage_id: Optional[str] = None
    passage_text: Optional[str] = None
    page_number: Optional[int] = None
    sha256_hash: Optional[str] = None


class RelatedConflictInfo(BaseModel):
    conflict_id: str
    claim_a_id: str
    claim_b_id: str
    opposing_claim_text: str
    conflict_type: str
    severity: str
    explanation: str
    resolution_status: str = Field(..., description="unresolved, under_review, resolved")
    is_unresolved: bool


class RequirementSufficiencyAssessment(BaseModel):
    requirement_id: str
    investigation_id: str
    requirement_title: str
    requirement_description: str
    requirement_type: str
    priority: str
    verification_criteria: str
    coverage_status: str = Field(..., description="SUFFICIENT, PARTIAL, INSUFFICIENT, NO_EVIDENCE, CONFLICTING")
    assessment_summary: str
    supporting_claims: List[SupportingClaimInfo] = Field(default_factory=list)
    supporting_claim_ids: List[str] = Field(default_factory=list)
    supporting_passage_ids: List[str] = Field(default_factory=list)
    source_ids: List[str] = Field(default_factory=list)
    related_conflicts: List[RelatedConflictInfo] = Field(default_factory=list)
    related_conflict_ids: List[str] = Field(default_factory=list)
    unresolved_conflict_count: int = 0
    limitations: Optional[str] = ""
    missing_information: Optional[str] = ""
    recommended_action: str
    gaps: List[EvidenceGapModel] = Field(default_factory=list)
    confidence: float = Field(..., ge=0.0, le=1.0)
    analysis_method: str
    processing_mode: str = Field(default="fallback", description="'gemini' or 'fallback'")
    analyzed_at: str


class SufficiencySummaryModel(BaseModel):
    total_requirements: int = 0
    sufficient_count: int = 0
    partial_count: int = 0
    insufficient_count: int = 0
    no_evidence_count: int = 0
    conflicting_count: int = 0
    total_gaps: int = 0
    high_priority_gaps: int = 0
    medium_priority_gaps: int = 0
    low_priority_gaps: int = 0
    overall_coverage_ratio: float = 0.0
    coverage_explanation: str = ""


class SufficiencyResponse(BaseModel):
    investigation_id: str
    contract_id: Optional[str] = None
    decision_objective: Optional[str] = None
    assessments: List[RequirementSufficiencyAssessment] = Field(default_factory=list)
    summary: SufficiencySummaryModel = Field(default_factory=SufficiencySummaryModel)
    processing_mode: str = Field(default="pending", description="'gemini', 'fallback', or 'pending'")
    last_analyzed_at: Optional[str] = None


class SufficiencyStatusResponse(BaseModel):
    investigation_id: str
    total_requirements: int
    sufficient_count: int
    partial_count: int
    insufficient_count: int
    no_evidence_count: int
    conflicting_count: int
    total_gaps: int
    processing_mode: str
    last_analysis_status: str
    last_analyzed_at: Optional[str] = None


class GeminiSufficiencyGapItem(BaseModel):
    gap_description: str = Field(..., description="Clear description of the evidentiary omission")
    why_it_matters: str = Field(..., description="Impact of this gap on decision stability")
    evidence_needed: str = Field(..., description="Specific empirical or documentation requirements to close the gap")
    suggested_source_type: str = Field(default="Authoritative Audit / Regulatory Filing")
    priority: str = Field(default="HIGH", description="HIGH, MEDIUM, LOW")


class GeminiRequirementSufficiencyItem(BaseModel):
    requirement_id: str
    coverage_status: str = Field(..., description="SUFFICIENT, PARTIAL, INSUFFICIENT, NO_EVIDENCE, CONFLICTING")
    assessment_summary: str = Field(..., description="Concise forensic evaluation of evidence sufficiency")
    limitations: str = Field(default="", description="Key weaknesses, biases, or caveats in available evidence")
    missing_information: str = Field(default="", description="Critical unanswered questions or missing metrics")
    recommended_action: str = Field(..., description="Specific action items to substantiate the requirement")
    confidence: float = Field(default=0.85, ge=0.0, le=1.0)
    gaps: List[GeminiSufficiencyGapItem] = Field(default_factory=list)


class GeminiSufficiencyPayload(BaseModel):
    assessments: List[GeminiRequirementSufficiencyItem] = Field(default_factory=list)


# ==========================================
# Component 07: Decision Stress Testing Models
# ==========================================

class RequirementEvaluationItem(BaseModel):
    requirement_id: str
    requirement_title: str
    baseline_status: str = Field(..., description="SUFFICIENT, PARTIAL, INSUFFICIENT, NO_EVIDENCE, CONFLICTING")
    scenario_status: str = Field(..., description="SUFFICIENT, PARTIAL, INSUFFICIENT, NO_EVIDENCE, CONFLICTING")
    status_shift: str = Field(..., description="DEGRADED, UNMODIFIED, IMPROVED, BLOCKED")
    reason: str
    affected_claim_ids: List[str] = Field(default_factory=list)


class StressEvaluationModel(BaseModel):
    id: str
    scenario_id: str
    investigation_id: str
    baseline_overall_outcome: str = Field(..., description="ROBUST, CONDITIONALLY_ROBUST, VULNERABLE, HIGHLY_VULNERABLE, INDETERMINATE, NOT_EVALUABLE")
    scenario_overall_outcome: str = Field(..., description="ROBUST, CONDITIONALLY_ROBUST, VULNERABLE, HIGHLY_VULNERABLE, INDETERMINATE, NOT_EVALUABLE")
    outcome_shift: str = Field(..., description="CRITICAL_FAILURE, DEGRADED, STABLE, IMPROVED, INDETERMINATE, NOT_EVALUABLE")
    impact_explanation: str
    key_vulnerabilities: List[str] = Field(default_factory=list)
    uncertainty_factors: List[str] = Field(default_factory=list)
    recommended_actions: List[str] = Field(default_factory=list)
    requirement_evaluations: List[RequirementEvaluationItem] = Field(default_factory=list)
    processing_mode: str = Field(default="fallback", description="'gemini' or 'fallback'")
    evaluated_at: str


class StressScenarioModel(BaseModel):
    id: str
    investigation_id: str
    title: str
    category: str = Field(..., description="ASSUMPTION_FAILURE, RISK_MATERIALIZATION, EVIDENCE_WEAKENING, CONFLICT_RESOLUTION, EXTERNAL_CONDITION_CHANGE, MISSING_EVIDENCE")
    description: str
    trigger_condition: str
    challenged_assumptions: List[str] = Field(default_factory=list)
    affected_requirement_ids: List[str] = Field(default_factory=list)
    affected_requirement_titles: List[str] = Field(default_factory=list)
    related_claim_ids: List[str] = Field(default_factory=list)
    related_source_ids: List[str] = Field(default_factory=list)
    related_conflict_ids: List[str] = Field(default_factory=list)
    expected_impact: str
    severity: str = Field(..., description="CRITICAL, HIGH, MEDIUM, LOW")
    evidence_needed: str
    evaluation_status: str = Field(default="unevaluated", description="'unevaluated' or 'evaluated'")
    baseline_overall_outcome: Optional[str] = Field(None, description="Top-level projection of baseline outcome")
    scenario_overall_outcome: Optional[str] = Field(None, description="Top-level projection of scenario outcome")
    outcome_shift: Optional[str] = Field(None, description="Top-level projection of outcome shift")
    evaluation: Optional[StressEvaluationModel] = None
    processing_mode: str = Field(default="fallback", description="'gemini' or 'fallback'")
    created_at: str


class StressTestingBaselineModel(BaseModel):
    investigation_id: str
    decision_objective: str
    total_requirements: int
    baseline_outcome: str = Field(..., description="ROBUST, CONDITIONALLY_ROBUST, VULNERABLE, HIGHLY_VULNERABLE, INDETERMINATE, NOT_EVALUABLE")
    coverage_ratio: float = 0.0
    sufficient_count: int = 0
    partial_count: int = 0
    insufficient_count: int = 0
    no_evidence_count: int = 0
    conflicting_count: int = 0
    unresolved_conflicts_count: int = 0
    active_assumptions_count: int = 0
    identified_gaps_count: int = 0
    baseline_explanation: str = ""


class StressTestingSummaryModel(BaseModel):
    total_scenarios: int = 0
    evaluated_scenarios: int = 0
    vulnerable_scenarios: int = 0
    indeterminate_scenarios: int = 0
    critical_severity_count: int = 0
    high_severity_count: int = 0
    baseline_outcome: str = "INDETERMINATE"
    processing_mode: str = "fallback"


class StressTestListResponse(BaseModel):
    investigation_id: str
    baseline: StressTestingBaselineModel
    summary: StressTestingSummaryModel
    scenarios: List[StressScenarioModel] = Field(default_factory=list)
    processing_mode: str = Field(default="fallback", description="'gemini' or 'fallback'")
    last_generated_at: Optional[str] = None


class StressTestStatusResponse(BaseModel):
    investigation_id: str
    total_scenarios: int
    evaluated_scenarios: int
    baseline_outcome: str
    processing_mode: str
    last_run_status: str
    last_generated_at: Optional[str] = None


class GeminiGeneratedScenarioItem(BaseModel):
    title: str = Field(..., description="Concise, descriptive stress-test scenario title")
    category: str = Field(..., description="ASSUMPTION_FAILURE, RISK_MATERIALIZATION, EVIDENCE_WEAKENING, CONFLICT_RESOLUTION, EXTERNAL_CONDITION_CHANGE, MISSING_EVIDENCE")
    description: str = Field(..., description="Detailed description of the stress scenario")
    trigger_condition: str = Field(..., description="Precise event or operational condition triggering the scenario")
    challenged_assumptions: List[str] = Field(default_factory=list, description="Explicit contract assumptions challenged")
    affected_requirement_ids: List[str] = Field(default_factory=list, description="IDs of affected contract requirements")
    related_claim_ids: List[str] = Field(default_factory=list, description="IDs of affected or weakened claims")
    related_conflict_ids: List[str] = Field(default_factory=list, description="IDs of related conflicts")
    expected_impact: str = Field(..., description="Explanation of anticipated impact on the decision")
    severity: str = Field(default="HIGH", description="CRITICAL, HIGH, MEDIUM, LOW")
    evidence_needed: str = Field(..., description="Specific empirical evidence required to validate or falsify this scenario")


class GeminiScenarioGenerationPayload(BaseModel):
    scenarios: List[GeminiGeneratedScenarioItem] = Field(default_factory=list)


class GeminiEvaluatedRequirementItem(BaseModel):
    requirement_id: str
    scenario_status: str = Field(..., description="SUFFICIENT, PARTIAL, INSUFFICIENT, NO_EVIDENCE, CONFLICTING")
    status_shift: str = Field(..., description="DEGRADED, UNMODIFIED, IMPROVED, BLOCKED")
    reason: str = Field(..., description="Specific evidentiary reason for the status shift under this scenario")


class GeminiScenarioEvaluationPayload(BaseModel):
    scenario_overall_outcome: str = Field(..., description="ROBUST, CONDITIONALLY_ROBUST, VULNERABLE, HIGHLY_VULNERABLE, INDETERMINATE")
    outcome_shift: str = Field(..., description="CRITICAL_FAILURE, DEGRADED, STABLE, IMPROVED, INDETERMINATE")
    impact_explanation: str = Field(..., description="Forensic explanation of how the scenario impacts the overall decision")
    key_vulnerabilities: List[str] = Field(default_factory=list, description="Critical decision vulnerabilities revealed")
    uncertainty_factors: List[str] = Field(default_factory=list, description="Unresolved uncertainties or missing evidence parameters")
    recommended_actions: List[str] = Field(default_factory=list, description="Empirical next steps to mitigate or stress-test further")
    requirement_evaluations: List[GeminiEvaluatedRequirementItem] = Field(default_factory=list)


# ==========================================
# Component 08: Decision Intelligence Report Engine Models
# ==========================================

class ExecutiveBriefSection(BaseModel):
    investigation_id: str
    research_question: str
    decision_objective: str
    report_version: int
    generated_at: str
    overall_robustness: str = Field(..., description="ROBUST, CONDITIONALLY_ROBUST, VULNERABLE, HIGHLY_VULNERABLE, INDETERMINATE")
    coverage_ratio: float = 0.0
    total_sources: int = 0
    total_claims: int = 0
    unresolved_conflicts_count: int = 0
    identified_gaps_count: int = 0
    high_severity_scenarios_count: int = 0
    executive_conclusion: str = ""


class ContractRequirementSummary(BaseModel):
    requirement_id: str
    title: str
    priority: str
    verification_criteria: str
    evidence_types: List[str] = Field(default_factory=list)


class DecisionContractSummarySection(BaseModel):
    contract_id: str
    normalized_question: str
    decision_objective: str
    scope: str = ""
    requirements: List[ContractRequirementSummary] = Field(default_factory=list)
    constraints: List[str] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)
    unresolved_questions: List[str] = Field(default_factory=list)


class SourceProvenanceItem(BaseModel):
    source_id: str
    title: str
    source_origin: str = "UNKNOWN"
    publisher: str = ""
    publication_date: str = ""
    ingestion_date: str = ""
    freshness_classification: str = "Undated Source"
    date_extraction_origin: str = ""
    freshness_warning: str = ""
    original_url: str = ""
    source_type: str
    sha256_hash: str = ""
    extraction_status: str
    claims_count: int = 0


class EvidenceIntelligenceSection(BaseModel):
    total_sources: int = 0
    total_passages: int = 0
    total_claims: int = 0
    factual_claims_count: int = 0
    statistical_claims_count: int = 0
    sources: List[SourceProvenanceItem] = Field(default_factory=list)
    reliability_limitations: str = ""


class SupportingClaimItem(BaseModel):
    claim_id: str
    claim_text: str
    source_title: str
    source_id: str
    passage_hash: str
    relevance: str
    confidence: float


class OpposingEvidenceItem(BaseModel):
    conflict_id: str
    conflict_type: str
    severity: str
    claim_text: str
    source_title: str
    resolution_status: str


class RequirementAssessmentRow(BaseModel):
    requirement_id: str
    title: str
    priority: str
    coverage_status: str = Field(..., description="SUFFICIENT, PARTIAL, INSUFFICIENT, NO_EVIDENCE, CONFLICTING")
    supporting_claims: List[SupportingClaimItem] = Field(default_factory=list)
    opposing_evidence: List[OpposingEvidenceItem] = Field(default_factory=list)
    identified_gaps: List[str] = Field(default_factory=list)
    assessment_summary: str = ""
    confidence: float = 0.8


class RequirementAssessmentSection(BaseModel):
    matrix: List[RequirementAssessmentRow] = Field(default_factory=list)
    coverage_summary: Dict[str, int] = Field(default_factory=dict)


class ReportConflictItem(BaseModel):
    conflict_id: str
    conflict_type: str
    severity: str
    claim_a_id: str
    claim_a_text: str
    claim_a_source: str
    claim_b_id: str
    claim_b_text: str
    claim_b_source: str
    explanation: str
    resolution_status: str
    reviewer_notes: str = ""
    decision_impact: str = ""


class ConflictAnalysisSection(BaseModel):
    total_conflicts: int = 0
    unresolved_count: int = 0
    critical_count: int = 0
    conflicts: List[ReportConflictItem] = Field(default_factory=list)


class ReportGapItem(BaseModel):
    gap_id: str
    requirement_id: str
    requirement_title: str
    gap_description: str
    why_it_matters: str
    evidence_needed: str
    suggested_source_type: str = "Authoritative Audit / Regulatory Filing"
    priority: str = "HIGH"


class GapsAndUncertaintySection(BaseModel):
    total_gaps: int = 0
    high_priority_gaps: int = 0
    gaps: List[ReportGapItem] = Field(default_factory=list)


class ReportStressScenarioItem(BaseModel):
    scenario_id: str
    title: str
    category: str
    trigger_condition: str
    severity: str
    outcome_shift: str
    scenario_outcome: str
    impact_explanation: str
    key_vulnerabilities: List[str] = Field(default_factory=list)


class StressTestResultsSection(BaseModel):
    baseline_outcome: str = "INDETERMINATE"
    total_scenarios: int = 0
    vulnerable_scenarios: int = 0
    scenarios: List[ReportStressScenarioItem] = Field(default_factory=list)


class RiskRegisterItem(BaseModel):
    risk_id: str
    title: str
    origin: str = Field(..., description="Conflict, Evidence Gap, Stress Scenario, Contract Assumption")
    severity: str = Field(..., description="CRITICAL, HIGH, MEDIUM, LOW")
    affected_requirement: str = ""
    consequence: str = ""
    mitigation: str = ""
    additional_evidence_needed: str = ""


class RiskMitigationSection(BaseModel):
    total_risks: int = 0
    critical_risks: int = 0
    high_risks: int = 0
    risks: List[RiskRegisterItem] = Field(default_factory=list)


class RecommendedActionItem(BaseModel):
    action_id: str
    action_title: str
    description: str
    priority: str = Field(..., description="P1_IMMEDIATE, P2_HIGH, P3_MODERATE")
    driver: str = ""
    target_requirement: str = ""
    expected_outcome: str = ""


class RecommendedActionsSection(BaseModel):
    actions: List[RecommendedActionItem] = Field(default_factory=list)


class FinalConclusionSection(BaseModel):
    supported_findings: List[str] = Field(default_factory=list)
    uncertainties_and_caveats: List[str] = Field(default_factory=list)
    invalidating_conditions: List[str] = Field(default_factory=list)
    recommended_decision_posture: str = ""
    epistemic_boundary_disclaimer: str = (
        "EPISTEMIC BOUNDARY DISCLAIMER: Every finding reported herein is strictly conditioned on the evidence "
        "ingested and verified at the time of report generation. Analytical interpretations, assumption evaluations, "
        "and hypothetical stress models do not constitute verified empirical facts and must be corroborated "
        "independently before executing critical decisions."
    )


class DecisionReportPayload(BaseModel):
    executive_brief: ExecutiveBriefSection
    decision_contract: DecisionContractSummarySection
    evidence_intelligence: EvidenceIntelligenceSection
    requirement_assessment: RequirementAssessmentSection
    conflict_analysis: ConflictAnalysisSection
    gaps_and_uncertainty: GapsAndUncertaintySection
    stress_test_results: StressTestResultsSection
    risk_mitigation: RiskMitigationSection
    recommended_actions: RecommendedActionsSection
    final_conclusion: FinalConclusionSection


class DecisionReportModel(BaseModel):
    id: str
    investigation_id: str
    report_version: int
    report_status: str = "published"
    processing_mode: str = "fallback"
    overall_robustness: str
    executive_summary: str
    report_data: DecisionReportPayload
    snapshot_metadata: Dict[str, Any] = Field(default_factory=dict)
    is_stale: bool = False
    created_at: str
    updated_at: str


class DecisionReportSummaryModel(BaseModel):
    id: str
    investigation_id: str
    report_version: int
    report_status: str = "published"
    processing_mode: str = "fallback"
    overall_robustness: str
    executive_summary: str
    is_stale: bool = False
    created_at: str


class DecisionReportListResponse(BaseModel):
    investigation_id: str
    total_reports: int = 0
    latest_version: int = 0
    reports: List[DecisionReportSummaryModel] = Field(default_factory=list)


class DecisionReportStatusResponse(BaseModel):
    investigation_id: str
    has_report: bool = False
    latest_report_id: Optional[str] = None
    latest_version: int = 0
    latest_status: Optional[str] = None
    is_stale: bool = False
    overall_robustness: Optional[str] = None
    processing_mode: str = "none"
    last_generated_at: Optional[str] = None


class GeminiReportSynthesisPayload(BaseModel):
    executive_conclusion: str = Field(..., description="Objective, executive synthesis grounded in empirical evidence")
    reliability_limitations: str = Field(..., description="Documented data collection or source reliability caveats")
    risks: List[RiskRegisterItem] = Field(default_factory=list, description="Prioritized risk register items")
    actions: List[RecommendedActionItem] = Field(default_factory=list, description="Prioritized analyst actions")
    supported_findings: List[str] = Field(default_factory=list, description="Specific findings backed by multiple corroborating claims")
    uncertainties_and_caveats: List[str] = Field(default_factory=list, description="Identified evidence gaps and unverified assumptions")
    invalidating_conditions: List[str] = Field(default_factory=list, description="Empirical conditions that would invalidate this decision")
    recommended_decision_posture: str = Field(..., description="Defensible decision posture: PROCEED, PROCEED_WITH_SAFEGUARDS, DEFER, REJECT")


# ==========================================
# Component 09 Models (Decision Fragility Index & Sensitivity Scoring)
# ==========================================

class FragilityDimensionDetail(BaseModel):
    dimension_key: str  # "d1_coverage", "d2_assumptions", "d3_conflicts", "d4_stress", "d5_concentration"
    dimension_name: str
    score: float
    weight: float
    weighted_contribution: float
    status: str  # "ASSESSED", "NOT_ASSESSED", "NOT_APPLICABLE"
    explanation: str
    metrics: Dict[str, Any] = Field(default_factory=dict)


class AttributionLedgerItem(BaseModel):
    item_id: str
    dimension: str
    category: str  # "REQUIREMENT_GAP", "ASSUMPTION_UNCERTAINTY", "EVIDENCE_CONFLICT", "STRESS_VULNERABILITY", "SENSITIVITY_CONCENTRATION"
    entity_id: str
    entity_type: str  # "requirement", "assumption", "conflict", "scenario", "concentration"
    entity_title: str
    base_penalty: float
    multiplier: float
    net_dimension_points: float
    net_dfi_contribution: float
    rationale: str


class DecisionFragilityResultModel(BaseModel):
    id: str
    run_id: str
    investigation_id: str
    methodology_version: str = "v1.2.0-deterministic"
    dfi_score: float
    classification: str
    is_provisional: bool = False
    provisional_reasons: List[str] = Field(default_factory=list)
    guardrail_active: bool = False
    guardrail_reason: Optional[str] = None
    unsubstantiated_critical_requirements: List[str] = Field(default_factory=list)
    d1_coverage: float
    d2_assumptions: float
    d3_conflicts: float
    d4_stress: float
    d5_concentration: float
    dimensions: Dict[str, FragilityDimensionDetail] = Field(default_factory=dict)
    attribution_ledger: List[AttributionLedgerItem] = Field(default_factory=list)
    explanation_text: str = ""
    processing_mode: str = "fallback"  # "gemini" or "fallback"
    is_stale: bool = False
    created_at: str


class FragilityAnalysisResponse(BaseModel):
    status: str
    investigation_id: str
    run_id: str
    result: DecisionFragilityResultModel
    message: Optional[str] = None


class FragilityStatusResponse(BaseModel):
    investigation_id: str
    has_result: bool = False
    latest_run_id: Optional[str] = None
    dfi_score: Optional[float] = None
    classification: Optional[str] = None
    is_provisional: bool = False
    guardrail_active: bool = False
    guardrail_reason: Optional[str] = None
    has_unsubstantiated_critical: bool = False
    is_stale: bool = False
    is_indeterminate: bool = False
    indeterminate_reason: Optional[str] = None
    created_at: Optional[str] = None


class SensitivitySimulationRequest(BaseModel):
    experiment_type: str = Field(..., description="SIM_EVIDENCE_WEAKENING, SIM_GAP_CORROBORATION, SIM_CONFLICT_RESOLUTION, SIM_ASSUMPTION_FAILURE")
    target_entity_id: str = Field(..., description="ID of requirement, conflict, or assumption being modified hypothetically")
    target_entity_type: str = Field(..., description="requirement, conflict, or assumption")
    hypothetical_parameters: Dict[str, Any] = Field(default_factory=dict)


class SensitivityExperimentResult(BaseModel):
    id: str
    investigation_id: str
    experiment_type: str
    is_hypothetical: bool = True
    target_entity_id: str
    target_entity_type: str
    target_entity_title: str
    baseline_dfi: float
    simulated_dfi: float
    delta_dfi: float
    baseline_classification: str
    simulated_classification: str
    simulated_guardrail_active: bool = False
    simulated_guardrail_reason: Optional[str] = None
    simulation_parameters: Dict[str, Any] = Field(default_factory=dict)
    narrative_impact: str = ""
    created_at: str


class SensitivityAnalysisResponse(BaseModel):
    investigation_id: str
    baseline_dfi: float
    baseline_classification: str
    experiments: List[SensitivityExperimentResult] = Field(default_factory=list)


class EvidenceImprovementRecommendationItem(BaseModel):
    id: str
    investigation_id: str
    run_id: Optional[str] = None
    recommendation_type: str  # RESOLVE_CONFLICT, VERIFY_ASSUMPTION, FILL_CRITICAL_GAP, CORROBORATE_EVIDENCE
    target_entity_id: str
    target_entity_type: str
    title: str
    description: str
    projected_dfi_reduction: float
    is_hypothetical_projection: bool = True
    priority: str  # HIGH, MEDIUM, LOW
    effort_estimate: str  # LOW, MEDIUM, HIGH
    action_steps: List[str] = Field(default_factory=list)
    created_at: str


class FragilityRecommendationsResponse(BaseModel):
    investigation_id: str
    total_recommendations: int = 0
    max_projected_reduction: float = 0.0
    recommendations: List[EvidenceImprovementRecommendationItem] = Field(default_factory=list)


class FragilityMethodologyResponse(BaseModel):
    version: str = "v1.2.0-deterministic"
    weights: Dict[str, float]
    deficit_penalties: Dict[str, float]
    conflict_penalties: Dict[str, float]
    stress_shift_penalties: Dict[str, float]
    guardrail_criteria: str
    provisional_policy: str
    rounding_rule: str
    epistemic_disclaimer: str


# ==========================================
# Component 10 Models (Autonomous Gap Verification & Update Navigator)
# ==========================================

class StageExecutionRecord(BaseModel):
    status: str = Field(..., description="'COMPLETED', 'NOT_AFFECTED', 'NOT_RUN', 'FAILED'")
    skipped_reason: Optional[str] = None
    duration_ms: Optional[int] = None


class InvestigationOrchestrationRunModel(BaseModel):
    id: str
    investigation_id: str
    source_id: Optional[str] = None
    trigger_workflow: str = Field(..., description="'GAP_VERIFICATION' or 'DIRECT_SOURCE_INTEGRATION'")
    status: str = Field(..., description="'PENDING', 'RUNNING', 'SUCCESS', 'PARTIAL_SUCCESS', 'FAILED', 'DUPLICATE_SOURCE_SKIPPED'")
    current_stage: str
    failure_stage: Optional[str] = None
    error_message: Optional[str] = None
    stages_execution: Dict[str, StageExecutionRecord] = Field(default_factory=dict)
    created_at: str
    updated_at: str


class SourceImpactSummaryModel(BaseModel):
    orchestration_run_id: str
    investigation_id: str
    source_id: str
    source_title: str
    source_url_or_filename: str
    authority_tier: str = Field(..., description="'TIER_1', 'TIER_2', 'TIER_3', 'TIER_4'")
    is_duplicate: bool = False
    
    # 1. Extracted Claims Profile
    total_claims_extracted: int = 0
    claims_by_category: Dict[str, int] = Field(default_factory=dict)
    extracted_claim_previews: List[Dict[str, Any]] = Field(default_factory=list)
    
    # 2. Contract Entity Impacts (Observed Facts)
    affected_requirements: List[Dict[str, Any]] = Field(default_factory=list)
    affected_assumptions: List[Dict[str, Any]] = Field(default_factory=list)
    
    # 3. Contradiction Profile (Observed Facts)
    new_conflicts_detected: List[Dict[str, Any]] = Field(default_factory=list)
    conflicts_resolved_count: int = 0
    
    # 4. Evidence Gap Impacts (Observed Facts)
    gaps_resolved: List[str] = Field(default_factory=list)
    gaps_reduced: List[str] = Field(default_factory=list)
    gaps_unchanged: List[str] = Field(default_factory=list)
    gaps_worsened: List[str] = Field(default_factory=list)
    
    # 5. Stress Test & Fragility Impacts (Computed Metrics)
    baseline_outcome_shifted: bool = False
    old_baseline_outcome: str = "INDETERMINATE"
    new_baseline_outcome: str = "INDETERMINATE"
    old_dfi_score: float = 0.0
    new_dfi_score: float = 0.0
    delta_dfi: float = 0.0
    old_classification: str = ""
    new_classification: str = ""
    guardrail_status_changed: bool = False
    
    # 6. Report & Governance State
    report_invalidated: bool = True
    unresolved_items_remaining: int = 0
    pending_analyst_actions: List[str] = Field(default_factory=list)
    stages_execution: Dict[str, StageExecutionRecord] = Field(default_factory=dict)
    
    # 7. AI Analytical Synthesis (Explicitly Segregated)
    executive_impact_narrative: str = ""
    processing_mode: str = "fallback"  # "gemini" or "fallback"
    created_at: str


class GapVerificationPlanModel(BaseModel):
    id: str
    investigation_id: str
    gap_id: str
    requirement_id: str
    requirement_title: str = ""
    verification_objective: str
    required_evidence_type: str
    target_authority_tier: str
    search_queries: List[str] = Field(default_factory=list)
    search_provider_status: str = "UNAVAILABLE"  # "ACTIVE" or "UNAVAILABLE"
    status: str = "PLANNED"  # "PLANNED", "DISCOVERED", "COMPLETED", "ABANDONED", "REQUIRES_MANUAL_QUERIES"
    missing_context_warning: Optional[str] = None
    created_at: str


class PlanGenerationRequest(BaseModel):
    custom_instructions: Optional[str] = Field(None, description="Analyst instructions to guide context query formulation")
    manual_queries: Optional[List[str]] = Field(None, description="Explicit manual queries provided by the analyst")


class PlanQueriesUpdateRequest(BaseModel):
    queries: List[str] = Field(..., description="Analyst-provided or edited verification queries")


class GapCandidateSourceModel(BaseModel):
    id: str
    plan_id: str
    investigation_id: str
    url: str
    domain: str
    title: str
    snippet: str
    authority_tier: str = "TIER_3"
    relevance_score: float = 0.0
    discovery_mode: str = "MANUAL_ENTRY"  # "MANUAL_ENTRY" or "SEARCH_PROVIDER"
    relevance_rationale: str = ""
    review_status: str = "PENDING_REVIEW"  # "PENDING_REVIEW", "APPROVED", "REJECTED"
    rejection_reason: Optional[str] = None
    discovered_at: str


class GapReassessmentModel(BaseModel):
    id: str
    investigation_id: str
    gap_id: str
    orchestration_run_id: Optional[str] = None
    previous_state: str
    proposed_resolution_state: str
    analyst_decision: str = "PENDING_DECISION"  # "APPROVED", "OVERRIDDEN", "REJECTED", "PENDING_DECISION"
    analyst_final_state: Optional[str] = None
    analyst_notes: Optional[str] = None
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[str] = None
    matched_claim_ids: List[str] = Field(default_factory=list)
    predicate_fulfillment_score: float = 0.0
    composite_evidence_score: float = 0.0
    is_analyst_override: bool = False
    created_at: str


class GapReassessmentCommitRequest(BaseModel):
    analyst_decision: str = Field(..., description="'APPROVED', 'OVERRIDDEN', 'REJECTED'")
    analyst_final_state: str = Field(..., description="'RESOLVED', 'PARTIALLY_ADDRESSED', 'UNCHANGED', 'WORSENED'")
    analyst_notes: str = Field(..., description="Mandatory forensic rationale for this verification transition")
    analyst_id: str = Field(default="Analyst", description="Analyst identifier")


class CandidateReviewRequest(BaseModel):
    action: str = Field(..., description="'APPROVE' or 'REJECT'")
    rejection_reason: Optional[str] = None


class ManualCandidateRequest(BaseModel):
    url: str
    title: Optional[str] = None
    snippet: Optional[str] = None


class GapQueueItemModel(BaseModel):
    gap_id: str
    requirement_id: str
    requirement_title: str
    priority: str
    gap_description: str
    why_it_matters: str
    evidence_needed: str
    suggested_source_type: str
    current_coverage_status: str
    projected_dfi_reduction: float = 0.0
    verification_state: str = "OPEN"
    active_plan_id: Optional[str] = None
    latest_reassessment_id: Optional[str] = None


class OrchestrationAuditLogItemModel(BaseModel):
    id: str
    investigation_id: str
    orchestration_run_id: Optional[str] = None
    source_id: Optional[str] = None
    event_type: str
    actor: str
    details: Dict[str, Any] = Field(default_factory=dict)
    created_at: str


class NavigatorQueueResponse(BaseModel):
    investigation_id: str
    total_gaps: int = 0
    search_provider: str = "none"
    search_provider_active: bool = False
    queue: List[GapQueueItemModel] = Field(default_factory=list)






