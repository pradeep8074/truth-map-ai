import re
import uuid
import datetime
import json
import logging
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from backend.config import GEMINI_API_KEY, GEMINI_MODEL

logger = logging.getLogger(__name__)


# ==========================================
# Pydantic Schemas for Structured Gemini Output
# ==========================================

class GeminiEvidenceRequirementSchema(BaseModel):
    evidence_type: str = Field(..., description="Required evidence artifact type (e.g. Official Regulatory Documentation, Institutional Enrollment Records, Peer-Reviewed Impact Study)")
    rationale: str = Field(..., description="Why this evidence artifact is indispensable for proving or falsifying the condition")
    preferred_sources: List[str] = Field(default_factory=list, description="Recommended source classifications (e.g. ['official_documentation', 'institutional_data', 'peer_reviewed_studies'])")
    temporal_scope: Optional[str] = Field(default="Observation Window")
    geographic_scope: Optional[str] = Field(default="Target Jurisdiction")


class GeminiRequirementSchema(BaseModel):
    title: str = Field(..., description="Concise requirement title")
    description: str = Field(..., description="Detailed verification condition describing what must be empirically proven")
    requirement_type: str = Field(..., description="One of: FACTUAL, QUANTITATIVE, COMPARATIVE, CAUSAL, TEMPORAL, GEOGRAPHIC, ELIGIBILITY, RISK, IMPLEMENTATION")
    priority: str = Field(..., description="One of: CRITICAL, HIGH, MEDIUM, LOW")
    verification_criteria: str = Field(..., description="Objective, testable pass/fail verification standard")
    evidence_type: Optional[str] = Field(default="Empirical Documentation")
    evidence_rationale: Optional[str] = Field(default="Required for objective condition verification")
    preferred_sources: Optional[List[str]] = Field(default_factory=list)


class GeminiConstraintSchema(BaseModel):
    description: str = Field(..., description="Scope boundary or causal discipline constraint")
    constraint_type: str = Field(default="scope_boundary", description="scope_boundary, causal_discipline, or negative_presumption")


class GeminiAssumptionSchema(BaseModel):
    description: str = Field(..., description="Working assumption necessary to evaluate the decision question")
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    source: str = Field(default="ai_inferred", description="Origin of assumption (must be 'ai_inferred' for model generation)")


class GeminiUnresolvedQuestionSchema(BaseModel):
    question: str = Field(..., description="Actionable clarification question resolving an ambiguity in the user inquiry")
    clarification_type: str = Field(default="required", description="required, optional, or assumption_review")
    dimension: str = Field(..., description="geographic, temporal, population, metric, or baseline")


class GeminiDecisionContractSchema(BaseModel):
    decision_objective: str = Field(..., description="Formal, explicit decision mandate derived from the question")
    scope: str = Field(default="Target domain empirical evaluation", description="Operational boundaries and empirical target domain")
    requirements: List[GeminiRequirementSchema] = Field(default_factory=list)
    constraints: List[GeminiConstraintSchema] = Field(default_factory=list)
    assumptions: List[GeminiAssumptionSchema] = Field(default_factory=list)
    unresolved_questions: List[GeminiUnresolvedQuestionSchema] = Field(default_factory=list)


def normalize_question(raw_question: str) -> str:
    """Normalizes whitespace, trims punctuation, and formats the inquiry."""
    if not raw_question:
        return ""
    q = re.sub(r"\s+", " ", raw_question.strip())
    # Ensure ends with single question mark if it was a question, or period
    if not q.endswith(("?", ".")):
        q += "?"
    return q


def extract_decision_objective(question: str) -> str:
    """Extracts an actionable decision objective from a research inquiry."""
    clean = question.strip()
    if clean.endswith("?"):
        clean = clean[:-1].strip()

    # Pattern: Does/Do/Can/Will/Is/Are X [verb] Y?
    match_aux = re.match(
        r"^(?:Does|Do|Can|Will|Is|Are|Has|Have)\s+(.+?)\s+(improve|reduce|increase|cause|lead to|affect|impact|enhance|facilitate|worsen|result in)\s+(.+)$",
        clean,
        re.IGNORECASE
    )
    if match_aux:
        subject = match_aux.group(1).strip()
        verb = match_aux.group(2).lower()
        outcome = match_aux.group(3).strip()
        return f"Evaluate whether {subject} {verb}s {outcome} and assess the evidentiary sufficiency of the decision criteria."

    # Pattern: Should [actor] [action]?
    match_should = re.match(r"^Should\s+(.+)$", clean, re.IGNORECASE)
    if match_should:
        action = match_should.group(1).strip()
        return f"Determine whether {action} is justified based on verifiable evidentiary prerequisites and risk tolerance."

    # Pattern: How does X affect Y?
    match_how = re.match(r"^(?:How does|What is the impact of)\s+(.+)$", clean, re.IGNORECASE)
    if match_how:
        subject = match_how.group(1).strip()
        return f"Quantify the empirical relationship and causal impact of {subject} across defined verification benchmarks."

    # Fallback
    return f"Evaluate the empirical validity, causal assumptions, and decision risk of: {clean}."


def detect_ambiguities(question: str) -> List[Dict[str, Any]]:
    """Detects missing or ambiguous dimensions in the inquiry and generates clarification questions."""
    ambiguities: List[Dict[str, Any]] = []

    # 1. Geographic Ambiguity
    has_geo = bool(re.search(
        r"\b(in|across|within)\s+[A-Z][a-z]+|\b(India|US|USA|UK|Europe|State|District|National|Global)\b",
        question
    ))
    if not has_geo:
        ambiguities.append({
            "question_id": str(uuid.uuid4()),
            "question": "Which geographic jurisdiction, administrative level, or regional territory governs this decision inquiry?",
            "clarification_type": "required",
            "dimension": "geographic",
        })

    # 2. Temporal Ambiguity
    has_time = bool(re.search(r"\b(19\d\d|20\d\d|fiscal year|annual|Q[1-4]|decade)\b", question, re.IGNORECASE))
    if not has_time:
        ambiguities.append({
            "question_id": str(uuid.uuid4()),
            "question": "What active evaluation timeframe or baseline observation period (e.g., 2022–2025) should constrain the evidence?",
            "clarification_type": "required",
            "dimension": "temporal",
        })

    # 3. Population / Subgroup Ambiguity
    ambiguities.append({
        "question_id": str(uuid.uuid4()),
        "question": "What specific socioeconomic, demographic, or institutional boundaries define the target beneficiary group?",
        "clarification_type": "optional",
        "dimension": "population",
    })

    # 4. Metric / Success Threshold Ambiguity
    ambiguities.append({
        "question_id": str(uuid.uuid4()),
        "question": "What quantifiable KPI, effect size, or statutory threshold defines acceptable 'improvement' or 'success'?",
        "clarification_type": "required",
        "dimension": "metric",
    })

    # 5. Baseline / Counterfactual Ambiguity
    ambiguities.append({
        "question_id": str(uuid.uuid4()),
        "question": "What counterfactual baseline or comparison group will be used to isolate the intervention from confounding macro trends?",
        "clarification_type": "assumption_review",
        "dimension": "baseline",
    })

    return ambiguities


def compile_contract_deterministic(investigation_id: str, original_question: str) -> Dict[str, Any]:
    """
    Deterministic compilation engine that transforms a raw research inquiry
    into a structured, testable decision contract without hallucinating facts.
    """
    contract_id = str(uuid.uuid4())
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    norm_q = normalize_question(original_question)
    objective = extract_decision_objective(norm_q)

    # 1. Generate core decomposed requirements
    req1_id = str(uuid.uuid4())
    req2_id = str(uuid.uuid4())
    req3_id = str(uuid.uuid4())
    req4_id = str(uuid.uuid4())
    req5_id = str(uuid.uuid4())
    req6_id = str(uuid.uuid4())

    requirements = [
        {
            "requirement_id": req1_id,
            "title": "Establish Programme Baseline & Eligibility Criteria",
            "description": "Formulate the statutory, institutional, or regulatory rules defining eligibility thresholds and target group boundaries.",
            "requirement_type": "ELIGIBILITY",
            "priority": "HIGH",
            "verification_criteria": "Official scheme guidelines, policy charters, or statutory mandates defining criteria.",
            "status": "unverified",
            "evidence_needed": [
                {
                    "evidence_requirement_id": str(uuid.uuid4()),
                    "requirement_id": req1_id,
                    "evidence_type": "Official Programme Guidelines & Mandates",
                    "rationale": "Required to verify that target beneficiaries meet qualification rules before evaluating outcomes.",
                    "preferred_source_types": ["government_filings", "official_documentation"],
                    "temporal_scope": "Current Policy Cycle",
                    "geographic_scope": "Jurisdiction of Origin",
                }
            ],
        },
        {
            "requirement_id": req2_id,
            "title": "Determine Target Population Size & Eligible Baseline Cohort",
            "description": "Establish the total population of qualified beneficiaries and calculate baseline participation prior to intervention.",
            "requirement_type": "QUANTITATIVE",
            "priority": "HIGH",
            "verification_criteria": "Census data, administrative registries, or institutional databases establishing cohort size.",
            "status": "unverified",
            "evidence_needed": [
                {
                    "evidence_requirement_id": str(uuid.uuid4()),
                    "requirement_id": req2_id,
                    "evidence_type": "Administrative Cohort & Demographic Records",
                    "rationale": "Establishes the denominator necessary to evaluate participation percentages and reach.",
                    "preferred_source_types": ["institutional_data", "government_databases"],
                    "temporal_scope": "Pre-Intervention Baseline",
                    "geographic_scope": "Target Region",
                }
            ],
        },
        {
            "requirement_id": req3_id,
            "title": "Verify Direct Participation & Benefit Uptake Outcomes",
            "description": "Audit participation rates, disbursement records, and verifiable service uptake among the target cohort.",
            "requirement_type": "IMPLEMENTATION",
            "priority": "CRITICAL",
            "verification_criteria": "Official disbursement statistics, student enrollment records, or validated operational logs.",
            "status": "unverified",
            "evidence_needed": [
                {
                    "evidence_requirement_id": str(uuid.uuid4()),
                    "requirement_id": req3_id,
                    "evidence_type": "Disbursement & Enrollment Data",
                    "rationale": "Verifies that intended benefits reached target recipients rather than leaking or stalling.",
                    "preferred_source_types": ["official_documentation", "audited_reports"],
                    "temporal_scope": "Active Implementation Period",
                    "geographic_scope": "Participating Districts",
                }
            ],
        },
        {
            "requirement_id": req4_id,
            "title": "Establish Comparative Control or Counterfactual Baseline",
            "description": "Identify an unexposed comparison group or historical baseline to distinguish natural trends from intervention effects.",
            "requirement_type": "COMPARATIVE",
            "priority": "CRITICAL",
            "verification_criteria": "Parallel cohort data, pre/post intervention metrics, or matched demographic control group.",
            "status": "unverified",
            "evidence_needed": [
                {
                    "evidence_requirement_id": str(uuid.uuid4()),
                    "requirement_id": req4_id,
                    "evidence_type": "Quasi-Experimental or Comparative Study Data",
                    "rationale": "Prevents attributing general macroeconomic improvement to the isolated programme.",
                    "preferred_source_types": ["peer_reviewed_literature", "research_studies"],
                    "temporal_scope": "Synchronous Comparative Window",
                    "geographic_scope": "Comparable Non-Recipient Regions",
                }
            ],
        },
        {
            "requirement_id": req5_id,
            "title": "Isolate Causal Impact from Extraneous Confounders",
            "description": "Evaluate empirical proof of causal attribution, isolating programme effects from macroeconomic shifts or confounding policies.",
            "requirement_type": "CAUSAL",
            "priority": "CRITICAL",
            "verification_criteria": "Regression discontinuity, difference-in-differences, or econometric impact assessments.",
            "status": "unverified",
            "evidence_needed": [
                {
                    "evidence_requirement_id": str(uuid.uuid4()),
                    "requirement_id": req5_id,
                    "evidence_type": "Econometric & Independent Impact Evaluations",
                    "rationale": "Ensures decisions are not made on correlational coincidences or flawed self-reporting.",
                    "preferred_source_types": ["academic_journals", "independent_evaluations"],
                    "temporal_scope": "Longitudinal Impact Window",
                    "geographic_scope": "National or Sub-national Study Zones",
                }
            ],
        },
        {
            "requirement_id": req6_id,
            "title": "Identify Participation Friction, Attrition, and Displacement Risks",
            "description": "Assess structural barriers, drop-out rates, or adverse incentives that threaten long-term outcome sustainability.",
            "requirement_type": "RISK",
            "priority": "MEDIUM",
            "verification_criteria": "Field audit reports, participant attrition logs, or regulatory compliance assessments.",
            "status": "unverified",
            "evidence_needed": [
                {
                    "evidence_requirement_id": str(uuid.uuid4()),
                    "requirement_id": req6_id,
                    "evidence_type": "Auditor General / Field Review Reports",
                    "rationale": "Surfaces hidden failure modes that undermine ostensibly successful initial numbers.",
                    "preferred_source_types": ["audit_reports", "compliance_reviews"],
                    "temporal_scope": "Recent Audit Cycles",
                    "geographic_scope": "Field Survey Areas",
                }
            ],
        },
    ]

    # Flatten evidence requirements for top-level collection
    all_evidence_reqs = []
    for r in requirements:
        all_evidence_reqs.extend(r["evidence_needed"])

    # Constraints
    constraints = [
        {
            "constraint_id": str(uuid.uuid4()),
            "description": "Distinguish correlation from causation: aggregate adoption growth cannot be treated as definitive causal proof.",
            "constraint_type": "causal_discipline",
        },
        {
            "constraint_id": str(uuid.uuid4()),
            "description": "Scope boundary: Confine factual verification strictly to the target demographic and subject domain of the inquiry.",
            "constraint_type": "scope_boundary",
        },
        {
            "constraint_id": str(uuid.uuid4()),
            "description": "Negative presumption: Do not assume that statutory availability of a benefit guarantees improved real-world outcomes.",
            "constraint_type": "negative_presumption",
        },
    ]

    # Assumptions
    assumptions = [
        {
            "assumption_id": str(uuid.uuid4()),
            "description": "The programme or intervention is actively operational and possesses an auditable administrative record.",
            "confidence": 0.85,
            "source": "ai_inferred",
            "validation_status": "pending",
        },
        {
            "assumption_id": str(uuid.uuid4()),
            "description": "The research question aims to stress-test tangible access outcomes rather than purely subjective participant satisfaction.",
            "confidence": 0.80,
            "source": "ai_inferred",
            "validation_status": "pending",
        },
    ]

    # Ambiguities / Unresolved Questions
    unresolved_questions = detect_ambiguities(norm_q)

    return {
        "contract_id": contract_id,
        "investigation_id": investigation_id,
        "original_question": original_question,
        "normalized_question": norm_q,
        "decision_objective": objective,
        "scope": "Target population empirical evaluation",
        "compilation_method": "deterministic_contract_compiler",
        "processing_mode": "fallback",
        "created_at": now,
        "updated_at": now,
        "requirements": requirements,
        "evidence_requirements": all_evidence_reqs,
        "constraints": constraints,
        "assumptions": assumptions,
        "unresolved_questions": unresolved_questions,
    }


async def compile_decision_contract(investigation_id: str, research_question: str) -> Dict[str, Any]:
    """
    Orchestrates the decision contract compiler pipeline:
    Attempts structured LLM compilation using Gemini if GEMINI_API_KEY is available;
    otherwise executes the comprehensive deterministic fallback engine.
    Ensures that processing_mode ('gemini' vs 'fallback') is explicitly recorded.
    """
    if GEMINI_API_KEY:
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=GEMINI_API_KEY)
            prompt = (
                "You are a principal decision systems architect for TRUTHMAP AI, an enterprise decision stress-testing platform.\n"
                "Your objective is to compile an explicit, testable, and falsifiable Decision Contract from the user's inquiry.\n\n"
                "STRICT FORENSIC COMPILATION RULES:\n"
                "1. PRESERVE THE INQUIRY: Decompose the exact question without substituting a different topic.\n"
                "2. NO INVENTED FACTS: Do NOT assert empirical facts, conclusions, or outcomes as established truth. The contract specifies what MUST BE PROVEN, not what has happened.\n"
                "3. OBJECTIVE DECISION MANDATE: Clearly state the evaluation objective and operational scope.\n"
                "4. REQUIREMENT DECOMPOSITION: Generate 4 to 6 explicit typed requirements covering ELIGIBILITY, QUANTITATIVE, IMPLEMENTATION, COMPARATIVE, CAUSAL, and RISK.\n"
                "5. EVIDENCE MAPPING: For every requirement, specify the concrete evidence artifact type and preferred sources.\n"
                "6. EXPLICIT CONSTRAINTS: Define scope boundaries and strict causal discipline (e.g. 'Distinguish correlation from causation', 'Do not assume availability implies uptake').\n"
                "7. AI-INFERRED ASSUMPTIONS: Label all assumptions as 'ai_inferred' and state only reasonable methodological assumptions.\n"
                "8. AMBIGUITY DETECTION: Identify missing dimensions (geographic jurisdiction, observation timeframe, cohort definition, outcome metric, counterfactual baseline) and formulate actionable clarification questions.\n\n"
                "Return ONLY a valid JSON object matching this schema:\n"
                "{\n"
                "  \"decision_objective\": \"Clear decision mandate\",\n"
                "  \"scope\": \"Operational scope boundaries\",\n"
                "  \"requirements\": [\n"
                "    {\n"
                "      \"title\": \"Short title\",\n"
                "      \"description\": \"Detailed requirement condition\",\n"
                "      \"requirement_type\": \"ELIGIBILITY\",\n"
                "      \"priority\": \"HIGH\",\n"
                "      \"verification_criteria\": \"Objective pass/fail criteria\",\n"
                "      \"evidence_type\": \"Artifact required\",\n"
                "      \"evidence_rationale\": \"Why required\",\n"
                "      \"preferred_sources\": [\"official_documentation\"]\n"
                "    }\n"
                "  ],\n"
                "  \"constraints\": [{\"description\": \"...\", \"constraint_type\": \"scope_boundary\"}],\n"
                "  \"assumptions\": [{\"description\": \"...\", \"confidence\": 0.85, \"source\": \"ai_inferred\"}],\n"
                "  \"unresolved_questions\": [{\"question\": \"...\", \"clarification_type\": \"required\", \"dimension\": \"geographic\"}]\n"
                "}\n\n"
                f"USER RESEARCH QUESTION:\n\"{research_question}\"\n"
            )

            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1,
                    max_output_tokens=3500,
                )
            )

            if response.text:
                contract_data = GeminiDecisionContractSchema.model_validate_json(response.text)
                contract_id = str(uuid.uuid4())
                now = datetime.datetime.now(datetime.timezone.utc).isoformat()
                norm_q = normalize_question(research_question)

                reqs = []
                ev_reqs = []
                for r in contract_data.requirements:
                    req_id = str(uuid.uuid4())
                    ev_id = str(uuid.uuid4())
                    ev_item = {
                        "evidence_requirement_id": ev_id,
                        "requirement_id": req_id,
                        "evidence_type": r.evidence_type or "Empirical Documentation",
                        "rationale": r.evidence_rationale or "Required for objective condition verification",
                        "preferred_source_types": r.preferred_sources if r.preferred_sources else ["official_documentation", "peer_reviewed_studies"],
                        "temporal_scope": "Observation Window",
                        "geographic_scope": "Target Jurisdiction",
                    }
                    ev_reqs.append(ev_item)

                    valid_req_type = r.requirement_type.upper().strip()
                    if valid_req_type not in {"FACTUAL", "QUANTITATIVE", "COMPARATIVE", "CAUSAL", "TEMPORAL", "GEOGRAPHIC", "ELIGIBILITY", "RISK", "IMPLEMENTATION"}:
                        valid_req_type = "FACTUAL"

                    valid_priority = r.priority.upper().strip()
                    if valid_priority not in {"CRITICAL", "HIGH", "MEDIUM", "LOW"}:
                        valid_priority = "HIGH"

                    reqs.append({
                        "requirement_id": req_id,
                        "title": r.title.strip(),
                        "description": r.description.strip(),
                        "requirement_type": valid_req_type,
                        "priority": valid_priority,
                        "verification_criteria": r.verification_criteria.strip(),
                        "status": "unverified",
                        "evidence_needed": [ev_item],
                    })

                constraints = [
                    {
                        "constraint_id": str(uuid.uuid4()),
                        "description": c.description.strip(),
                        "constraint_type": c.constraint_type.strip() if c.constraint_type else "scope_boundary",
                    }
                    for c in contract_data.constraints
                ]

                assumptions = [
                    {
                        "assumption_id": str(uuid.uuid4()),
                        "description": a.description.strip(),
                        "confidence": float(a.confidence),
                        "source": "ai_inferred",
                        "validation_status": "pending",
                    }
                    for a in contract_data.assumptions
                ]

                unresolved = [
                    {
                        "question_id": str(uuid.uuid4()),
                        "question": u.question.strip(),
                        "clarification_type": u.clarification_type.strip() if u.clarification_type else "required",
                        "dimension": u.dimension.strip() if u.dimension else "metric",
                    }
                    for u in contract_data.unresolved_questions
                ]

                if reqs:
                    return {
                        "contract_id": contract_id,
                        "investigation_id": investigation_id,
                        "original_question": research_question,
                        "normalized_question": norm_q,
                        "decision_objective": contract_data.decision_objective.strip() or extract_decision_objective(norm_q),
                        "scope": contract_data.scope.strip() or "Target Population Empirical Evaluation",
                        "compilation_method": "gemini_contract_compiler",
                        "processing_mode": "gemini",
                        "created_at": now,
                        "updated_at": now,
                        "requirements": reqs,
                        "evidence_requirements": ev_reqs,
                        "constraints": constraints,
                        "assumptions": assumptions,
                        "unresolved_questions": unresolved,
                    }

        except Exception as e:
            logger.warning(
                "Gemini contract compilation unavailable or failed: %s. Falling back to deterministic compiler.",
                str(e)
            )

    # Deterministic fallback compiler
    return compile_contract_deterministic(investigation_id, research_question)
