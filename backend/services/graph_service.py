import re
import uuid
import datetime
import logging
from typing import Dict, Any, List, Optional, Tuple, Set
from pydantic import BaseModel, Field

from backend.config import GEMINI_API_KEY, GEMINI_MODEL
from backend.models import (
    GraphNodeModel,
    GraphEdgeModel,
    GraphSummaryModel,
    EvidenceGraphResponse,
    EvidenceGraphStatusResponse,
)

logger = logging.getLogger(__name__)

STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "if", "because", "as", "what",
    "which", "this", "that", "these", "those", "then", "just", "so", "than",
    "such", "both", "through", "about", "for", "is", "of", "while", "during",
    "to", "from", "in", "out", "on", "off", "again", "further", "then", "once",
    "here", "there", "when", "where", "why", "how", "all", "any", "both",
    "each", "few", "more", "most", "other", "some", "such", "no", "nor", "not",
    "only", "own", "same", "so", "than", "too", "very", "can", "will", "should",
    "now", "be", "been", "being", "have", "has", "had", "do", "does", "did",
}


# ==========================================
# Pydantic Schemas for Structured Gemini Output
# ==========================================

class GeminiCandidateRelevance(BaseModel):
    requirement_id: str = Field(..., description="Target Decision Requirement ID")
    claim_id: str = Field(..., description="Source Atomic Claim ID")
    passage_id: Optional[str] = Field(default=None, description="Underlying Source Passage ID")
    relevance: str = Field(..., description="One of: DIRECTLY_RELEVANT, PARTIALLY_RELEVANT, CONTEXTUAL, NOT_RELEVANT")
    explanation: str = Field(..., description="Concise evidentiary justification explaining why and how this claim relates to the requirement condition")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score from 0.0 to 1.0")


class GeminiGraphAnalysisPayload(BaseModel):
    relationships: List[GeminiCandidateRelevance] = Field(default_factory=list)


def extract_keywords(text: str) -> Set[str]:
    """Tokenizes and filters out punctuation and stop words."""
    words = re.findall(r"[a-zA-Z0-9%]+", text.lower())
    return {w for w in words if w not in STOPWORDS and len(w) > 2}


def compute_fallback_relevance(
    requirement: Dict[str, Any],
    claim: Dict[str, Any]
) -> Tuple[str, str, float]:
    """
    Deterministic keyword & semantic overlap analyzer when Gemini is unavailable.
    Does not invent facts or claims. Computes literal lexical and thematic overlap.
    """
    req_text = f"{requirement.get('title', '')} {requirement.get('description', '')} {requirement.get('verification_criteria', '')}"
    claim_text = claim.get("claim_text", "")

    req_tokens = extract_keywords(req_text)
    claim_tokens = extract_keywords(claim_text)

    if not req_tokens or not claim_tokens:
        return "NOT_RELEVANT", "Insufficient textual overlap for candidate mapping.", 0.1

    overlap = req_tokens.intersection(claim_tokens)
    overlap_ratio = len(overlap) / max(len(claim_tokens), 1)

    matched_list = sorted(list(overlap))[:5]
    terms_str = ", ".join(f"'{t}'" for t in matched_list)

    # Check for domain-specific alignment (e.g. numeric metrics matching quantitative requirements)
    is_quant_req = requirement.get("requirement_type", "").upper() in {"QUANTITATIVE", "COMPARATIVE"}
    has_quant_claim = claim.get("category", "").lower() in {"statistical", "temporal"} or bool(re.search(r"\d+", claim_text))

    if overlap_ratio >= 0.28 or (overlap_ratio >= 0.18 and is_quant_req and has_quant_claim):
        return (
            "DIRECTLY_RELEVANT",
            f"Deterministic token alignment on key domain terms ({terms_str}) directly addresses requirement criteria.",
            round(min(0.70 + (overlap_ratio * 0.25), 0.92), 2),
        )
    elif overlap_ratio >= 0.14 or len(overlap) >= 2:
        return (
            "PARTIALLY_RELEVANT",
            f"Partial lexical and semantic overlap identified on terms ({terms_str}), providing supporting evidentiary context.",
            round(min(0.50 + (overlap_ratio * 0.20), 0.72), 2),
        )
    elif overlap_ratio >= 0.06 or len(overlap) >= 1:
        return (
            "CONTEXTUAL",
            f"Peripheral contextual relationship detected through shared terms ({terms_str}).",
            round(min(0.35 + (overlap_ratio * 0.15), 0.50), 2),
        )
    else:
        return (
            "NOT_RELEVANT",
            "No substantial thematic or lexical overlap found with this requirement condition.",
            0.15,
        )


def build_evidence_graph_from_db(conn, investigation_id: str) -> EvidenceGraphResponse:
    """
    Assembles real nodes and edges from the SQLite database for the investigation:
    1. Decision Contract node (if compiled)
    2. Decision Requirement nodes
    3. Evidence Requirement nodes
    4. Atomic Claim nodes
    5. Source Passage nodes
    6. Source Document nodes
    7. Structural edges: HAS_REQUIREMENT, REQUIRES_EVIDENCE, EXTRACTED_FROM, BELONGS_TO_SOURCE
    8. Analyzed relational edges: RELATES_TO from evidence_relationships
    """
    cursor = conn.cursor()

    nodes: List[GraphNodeModel] = []
    edges: List[GraphEdgeModel] = []
    node_id_set: Set[str] = set()

    def add_node(node: GraphNodeModel):
        if node.id not in node_id_set:
            nodes.append(node)
            node_id_set.add(node.id)

    # 1. Fetch Decision Contract
    cursor.execute("""
        SELECT id, original_question, decision_objective, scope, compilation_method, created_at
        FROM decision_contracts
        WHERE investigation_id = ?;
    """, (investigation_id,))
    contract_row = cursor.fetchone()

    contract_id = None
    if contract_row:
        contract_id = contract_row["id"]
        c_node_id = f"contract_{contract_id}"
        add_node(GraphNodeModel(
            id=c_node_id,
            type="decision_contract",
            label="Decision Contract",
            record_id=contract_id,
            metadata={
                "decision_objective": contract_row["decision_objective"],
                "scope": contract_row["scope"],
                "original_question": contract_row["original_question"],
                "compilation_method": contract_row["compilation_method"],
                "created_at": contract_row["created_at"],
            }
        ))

        # 2. Fetch Requirements
        cursor.execute("""
            SELECT id, title, description, requirement_type, priority, verification_criteria, status, sort_order
            FROM contract_requirements
            WHERE contract_id = ?
            ORDER BY sort_order ASC;
        """, (contract_id,))
        req_rows = cursor.fetchall()

        # Fetch sufficiency assessments if available
        cursor.execute("""
            SELECT requirement_id, coverage_status, assessment_summary, confidence
            FROM evidence_sufficiency_assessments
            WHERE investigation_id = ?;
        """, (investigation_id,))
        suff_map = {r["requirement_id"]: dict(r) for r in cursor.fetchall()}

        for req in req_rows:
            req_id = req["id"]
            req_node_id = f"req_{req_id}"
            req_suff = suff_map.get(req_id, {})
            add_node(GraphNodeModel(
                id=req_node_id,
                type="decision_requirement",
                label=req["title"],
                record_id=req_id,
                metadata={
                    "title": req["title"],
                    "description": req["description"],
                    "requirement_type": req["requirement_type"],
                    "priority": req["priority"],
                    "verification_criteria": req["verification_criteria"],
                    "status": req["status"],
                    "coverage_status": req_suff.get("coverage_status", "UNASSESSED"),
                    "assessment_summary": req_suff.get("assessment_summary", ""),
                    "sufficiency_confidence": req_suff.get("confidence"),
                }
            ))

            # Edge: Contract -> Requirement
            edges.append(GraphEdgeModel(
                id=f"edge_{c_node_id}_{req_node_id}_has_req",
                source=c_node_id,
                target=req_node_id,
                relationship="HAS_REQUIREMENT",
                origin="structural",
                confidence=1.0,
                metadata={"priority": req["priority"]}
            ))

            # 3. Fetch Evidence Requirements for this Requirement
            cursor.execute("""
                SELECT id, evidence_type, rationale, preferred_source_types, temporal_scope, geographic_scope
                FROM contract_evidence_requirements
                WHERE requirement_id = ?;
            """, (req_id,))
            ev_req_rows = cursor.fetchall()

            for ev in ev_req_rows:
                ev_id = ev["id"]
                ev_node_id = f"evreq_{ev_id}"
                add_node(GraphNodeModel(
                    id=ev_node_id,
                    type="evidence_requirement",
                    label=ev["evidence_type"],
                    record_id=ev_id,
                    metadata={
                        "evidence_type": ev["evidence_type"],
                        "rationale": ev["rationale"],
                        "preferred_sources": ev["preferred_source_types"],
                        "temporal_scope": ev["temporal_scope"],
                        "geographic_scope": ev["geographic_scope"],
                    }
                ))

                # Edge: Requirement -> Evidence Requirement
                edges.append(GraphEdgeModel(
                    id=f"edge_{req_node_id}_{ev_node_id}_requires_ev",
                    source=req_node_id,
                    target=ev_node_id,
                    relationship="REQUIRES_EVIDENCE",
                    origin="structural",
                    confidence=1.0,
                    metadata={"rationale": ev["rationale"]}
                ))

    # 4. Fetch Sources
    cursor.execute("""
        SELECT id, source_type, original_url, title, publisher, publication_date, retrieved_at, extraction_status
        FROM sources
        WHERE investigation_id = ?;
    """, (investigation_id,))
    source_rows = cursor.fetchall()

    for src in source_rows:
        src_id = src["id"]
        src_node_id = f"source_{src_id}"
        display_label = src["title"] or (src["original_url"][:40] + "..." if src["original_url"] else f"Document {src_id[:8]}")
        add_node(GraphNodeModel(
            id=src_node_id,
            type="source_document",
            label=display_label,
            record_id=src_id,
            metadata={
                "title": src["title"],
                "source_type": src["source_type"],
                "original_url": src["original_url"],
                "publisher": src["publisher"],
                "publication_date": src["publication_date"],
                "retrieved_at": src["retrieved_at"],
                "extraction_status": src["extraction_status"],
            }
        ))

    # 5. Fetch Passages
    cursor.execute("""
        SELECT p.id, p.source_id, p.passage_text, p.page_number, p.paragraph_index, p.start_offset, p.end_offset, p.sha256_hash
        FROM passages p
        JOIN sources s ON p.source_id = s.id
        WHERE s.investigation_id = ?;
    """, (investigation_id,))
    passage_rows = cursor.fetchall()

    for pas in passage_rows:
        pas_id = pas["id"]
        pas_node_id = f"passage_{pas_id}"
        p_label = f"Passage (p. {pas['page_number']})" if pas["page_number"] else f"Passage §{pas['paragraph_index'] or 1}"
        add_node(GraphNodeModel(
            id=pas_node_id,
            type="source_passage",
            label=p_label,
            record_id=pas_id,
            metadata={
                "passage_text": pas["passage_text"],
                "page_number": pas["page_number"],
                "paragraph_index": pas["paragraph_index"],
                "start_offset": pas["start_offset"],
                "end_offset": pas["end_offset"],
                "sha256_hash": pas["sha256_hash"],
                "source_id": pas["source_id"],
            }
        ))

        # Edge: Passage -> Source
        src_node_id = f"source_{pas['source_id']}"
        edges.append(GraphEdgeModel(
            id=f"edge_{pas_node_id}_{src_node_id}_belongs_to",
            source=pas_node_id,
            target=src_node_id,
            relationship="BELONGS_TO_SOURCE",
            origin="structural",
            confidence=1.0,
            metadata={"page_number": pas["page_number"]}
        ))

    # 6. Fetch Claims
    cursor.execute("""
        SELECT c.id, c.passage_id, c.source_id, c.claim_text, c.category, c.extraction_method, c.extraction_confidence, c.created_at
        FROM claims c
        WHERE c.investigation_id = ?;
    """, (investigation_id,))
    claim_rows = cursor.fetchall()

    for clm in claim_rows:
        clm_id = clm["id"]
        clm_node_id = f"claim_{clm_id}"
        c_label = clm["claim_text"][:50] + ("..." if len(clm["claim_text"]) > 50 else "")
        add_node(GraphNodeModel(
            id=clm_node_id,
            type="atomic_claim",
            label=c_label,
            record_id=clm_id,
            metadata={
                "claim_text": clm["claim_text"],
                "category": clm["category"] or "factual",
                "extraction_method": clm["extraction_method"],
                "confidence": clm["extraction_confidence"],
                "passage_id": clm["passage_id"],
                "source_id": clm["source_id"],
                "created_at": clm["created_at"],
            }
        ))

        # Edge: Claim -> Passage
        pas_node_id = f"passage_{clm['passage_id']}"
        edges.append(GraphEdgeModel(
            id=f"edge_{clm_node_id}_{pas_node_id}_extracted_from",
            source=clm_node_id,
            target=pas_node_id,
            relationship="EXTRACTED_FROM",
            origin="structural",
            confidence=1.0,
            metadata={"extraction_method": clm["extraction_method"]}
        ))

    # 7. Fetch Persisted Relational Edges (RELATES_TO)
    cursor.execute("""
        SELECT r.id, r.requirement_id, r.claim_id, r.passage_id, r.relevance, r.explanation, r.confidence, r.analysis_method, r.processing_mode, r.created_at
        FROM evidence_relationships r
        WHERE r.investigation_id = ?;
    """, (investigation_id,))
    rel_rows = cursor.fetchall()

    directly_relevant = 0
    partially_relevant = 0
    contextual = 0
    processing_mode = "pending"
    last_analyzed_at = None

    for rel in rel_rows:
        req_node_id = f"req_{rel['requirement_id']}"
        clm_node_id = f"claim_{rel['claim_id']}"
        relevance = rel["relevance"].upper()

        if relevance == "DIRECTLY_RELEVANT":
            directly_relevant += 1
        elif relevance == "PARTIALLY_RELEVANT":
            partially_relevant += 1
        elif relevance == "CONTEXTUAL":
            contextual += 1

        processing_mode = rel["processing_mode"]
        last_analyzed_at = rel["created_at"]

        # Only draw graph edges for relevant links
        if relevance in {"DIRECTLY_RELEVANT", "PARTIALLY_RELEVANT", "CONTEXTUAL"}:
            edges.append(GraphEdgeModel(
                id=f"edge_{clm_node_id}_{req_node_id}_relates_to",
                source=clm_node_id,
                target=req_node_id,
                relationship="RELATES_TO",
                origin=rel["processing_mode"],
                confidence=rel["confidence"],
                metadata={
                    "relevance": relevance,
                    "explanation": rel["explanation"],
                    "passage_id": rel["passage_id"],
                    "analysis_method": rel["analysis_method"],
                }
            ))

    # 8. Fetch Evidence Conflicts (CONFLICTS_WITH)
    cursor.execute("""
        SELECT id, claim_a_id, claim_b_id, conflict_type, severity, explanation, confidence, resolution_status, processing_mode
        FROM evidence_conflicts
        WHERE investigation_id = ?;
    """, (investigation_id,))
    conflict_rows = cursor.fetchall()

    for conf in conflict_rows:
        ca_node_id = f"claim_{conf['claim_a_id']}"
        cb_node_id = f"claim_{conf['claim_b_id']}"
        if ca_node_id in node_id_set and cb_node_id in node_id_set:
            edges.append(GraphEdgeModel(
                id=f"edge_{ca_node_id}_{cb_node_id}_conflicts_with",
                source=ca_node_id,
                target=cb_node_id,
                relationship="CONFLICTS_WITH",
                origin=conf["processing_mode"] or "analysis",
                confidence=conf["confidence"],
                metadata={
                    "conflict_id": conf["id"],
                    "conflict_type": conf["conflict_type"],
                    "severity": conf["severity"],
                    "explanation": conf["explanation"],
                    "resolution_status": conf["resolution_status"],
                }
            ))

    # 9. Fetch Decision Stress Scenarios (Component 07)
    cursor.execute("""
        SELECT s.id, s.category, s.title, s.description, s.trigger_condition, s.severity,
               s.affected_requirement_ids, s.related_claim_ids, s.related_conflict_ids,
               e.scenario_overall_outcome
        FROM decision_stress_scenarios s
        LEFT JOIN decision_stress_evaluations e ON s.id = e.scenario_id
        WHERE s.investigation_id = ?;
    """, (investigation_id,))
    scenario_rows = cursor.fetchall()

    for sc in scenario_rows:
        sc_id = sc["id"]
        sc_node_id = f"scenario_{sc_id}"
        add_node(GraphNodeModel(
            id=sc_node_id,
            type="stress_scenario",
            label=f"Scenario: {sc['title'][:40]}",
            record_id=sc_id,
            metadata={
                "category": sc["category"],
                "severity": sc["severity"],
                "evaluation_status": "evaluated" if sc["scenario_overall_outcome"] else "unevaluated",
                "evaluation_outcome": sc["scenario_overall_outcome"],
                "trigger_condition": sc["trigger_condition"],
            }
        ))

        # Edges to affected requirements
        import json
        try:
            aff_req_ids = json.loads(sc["affected_requirement_ids"] or "[]")
        except Exception:
            aff_req_ids = []
        for r_id in aff_req_ids:
            r_node_id = f"req_{r_id}"
            if r_node_id in node_id_set:
                edges.append(GraphEdgeModel(
                    id=f"edge_{sc_node_id}_{r_node_id}_challenges",
                    source=sc_node_id,
                    target=r_node_id,
                    relationship="CHALLENGES",
                    origin="stress_testing",
                    confidence=1.0,
                    metadata={"category": sc["category"], "severity": sc["severity"]}
                ))

        # Edges to contested claims
        try:
            cont_claim_ids = json.loads(sc["related_claim_ids"] or "[]")
        except Exception:
            cont_claim_ids = []
        for c_id in cont_claim_ids:
            c_node_id = f"claim_{c_id}"
            if c_node_id in node_id_set:
                edges.append(GraphEdgeModel(
                    id=f"edge_{sc_node_id}_{c_node_id}_contests",
                    source=sc_node_id,
                    target=c_node_id,
                    relationship="CONTESTS",
                    origin="stress_testing",
                    confidence=1.0,
                    metadata={"category": sc["category"]}
                ))

    # Authoritative processing mode & last analyzed timestamp from latest audit run
    cursor.execute("""
        SELECT processing_mode, analysis_status, created_at
        FROM evidence_graph_runs
        WHERE investigation_id = ?
        ORDER BY created_at DESC LIMIT 1;
    """, (investigation_id,))
    run_row = cursor.fetchone()
    if run_row:
        processing_mode = run_row["processing_mode"]
        last_analyzed_at = run_row["created_at"]

    summary = GraphSummaryModel(
        total_nodes=len(nodes),
        total_edges=len(edges),
        contract_nodes=sum(1 for n in nodes if n.type == "decision_contract"),
        requirement_nodes=sum(1 for n in nodes if n.type == "decision_requirement"),
        evidence_requirement_nodes=sum(1 for n in nodes if n.type == "evidence_requirement"),
        claim_nodes=sum(1 for n in nodes if n.type == "atomic_claim"),
        passage_nodes=sum(1 for n in nodes if n.type == "source_passage"),
        source_nodes=sum(1 for n in nodes if n.type == "source_document"),
        scenario_nodes=sum(1 for n in nodes if n.type == "stress_scenario"),
        directly_relevant_links=directly_relevant,
        partially_relevant_links=partially_relevant,
        contextual_links=contextual,
    )

    return EvidenceGraphResponse(
        investigation_id=investigation_id,
        nodes=nodes,
        edges=edges,
        processing_mode=processing_mode,
        last_analyzed_at=last_analyzed_at,
        summary=summary,
    )


async def analyze_claim_requirement_relationships(
    conn,
    investigation_id: str
) -> EvidenceGraphResponse:
    """
    Analyzes candidate claim-to-requirement relationships:
    1. Loads decision requirements and extracted claims with passages.
    2. Runs Gemini LLM semantic analysis with strict forensic guardrails.
    3. Falls back to deterministic keyword/token overlap analyzer if Gemini is unavailable or errors.
    4. Persists the evaluated relationships in evidence_relationships table.
    5. Returns the updated assembled Evidence Graph.
    """
    cursor = conn.cursor()

    # Verify investigation exists
    cursor.execute("SELECT id, research_question FROM investigations WHERE id = ?;", (investigation_id,))
    inv = cursor.fetchone()
    if not inv:
        raise ValueError(f"Investigation {investigation_id} not found")

    # Fetch Decision Contract
    cursor.execute("""
        SELECT id, decision_objective FROM decision_contracts WHERE investigation_id = ?;
    """, (investigation_id,))
    contract = cursor.fetchone()
    if not contract:
        # Cannot run requirement analysis without a Decision Contract
        return build_evidence_graph_from_db(conn, investigation_id)

    contract_id = contract["id"]

    # Fetch Requirements
    cursor.execute("""
        SELECT id, title, description, requirement_type, verification_criteria
        FROM contract_requirements
        WHERE contract_id = ?;
    """, (contract_id,))
    requirements = [dict(r) for r in cursor.fetchall()]

    # Fetch Claims with their supporting Passages
    cursor.execute("""
        SELECT c.id, c.passage_id, c.source_id, c.claim_text, c.category, c.extraction_confidence, p.passage_text
        FROM claims c
        JOIN passages p ON c.passage_id = p.id
        WHERE c.investigation_id = ?;
    """, (investigation_id,))
    claims = [dict(c) for c in cursor.fetchall()]

    if not requirements or not claims:
        # No candidate pairs to analyze
        return build_evidence_graph_from_db(conn, investigation_id)

    analyzed_relationships: List[Dict[str, Any]] = []
    processing_mode = "fallback"
    analysis_method = "deterministic_keyword_overlap"

    # Attempt Gemini LLM Analysis if API key configured
    if GEMINI_API_KEY:
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=GEMINI_API_KEY)

            # Build compact prompt
            req_prompt_list = [
                {
                    "requirement_id": r["id"],
                    "title": r["title"],
                    "description": r["description"],
                    "criteria": r["verification_criteria"],
                    "type": r["requirement_type"]
                }
                for r in requirements
            ]

            claim_prompt_list = [
                {
                    "claim_id": c["id"],
                    "passage_id": c["passage_id"],
                    "claim_text": c["claim_text"],
                    "category": c["category"],
                    "passage_excerpt": c["passage_text"][:250]
                }
                for c in claims
            ]

            prompt = (
                "You are the Evidence Intelligence Graph Engine for TRUTHMAP AI.\n"
                "Your task is to analyze candidate relationships between Decision Requirements and extracted Atomic Claims.\n\n"
                "CRITICAL FORENSIC RULES:\n"
                "1. RELEVANCE IS NOT PROOF: Classifying a claim as DIRECTLY_RELEVANT or PARTIALLY_RELEVANT indicates topical and evidentiary connection, NOT that the claim is verified, true, sufficient, or conclusive.\n"
                "2. NO INVENTED RELATIONSHIPS OR IDENTIFIERS: Only use the exact requirement_id and claim_id provided.\n"
                "3. CLASSIFICATIONS: DIRECTLY_RELEVANT, PARTIALLY_RELEVANT, CONTEXTUAL, or NOT_RELEVANT.\n"
                "4. TRACEABILITY: Ensure each relationship references the supporting passage_id from the claim.\n"
                "5. CONFIDENCE: Assign a calibration score between 0.0 and 1.0 based solely on evidentiary alignment.\n\n"
                "DECISION OBJECTIVE:\n"
                f"\"{contract['decision_objective']}\"\n\n"
                f"DECISION REQUIREMENTS ({len(requirements)} items):\n"
                f"{json_dump_compact(req_prompt_list)}\n\n"
                f"EXTRACTED ATOMIC CLAIMS ({len(claims)} items):\n"
                f"{json_dump_compact(claim_prompt_list)}\n\n"
                "Return ONLY a valid JSON object matching:\n"
                "{\n"
                "  \"relationships\": [\n"
                "    {\n"
                "      \"requirement_id\": \"...\",\n"
                "      \"claim_id\": \"...\",\n"
                "      \"passage_id\": \"...\",\n"
                "      \"relevance\": \"DIRECTLY_RELEVANT\",\n"
                "      \"explanation\": \"Specific evidentiary justification\",\n"
                "      \"confidence\": 0.90\n"
                "    }\n"
                "  ]\n"
                "}"
            )

            # Define candidate models list with graceful fallback across active endpoints
            candidate_models = [GEMINI_MODEL]
            for fallback_model in ["gemini-flash-lite-latest", "gemini-3.5-flash-lite", "gemini-3-flash-preview"]:
                if fallback_model not in candidate_models:
                    candidate_models.append(fallback_model)

            response = None
            used_model = None
            last_model_error = None

            for model_candidate in candidate_models:
                try:
                    res = client.models.generate_content(
                        model=model_candidate,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            temperature=0.1,
                            max_output_tokens=4000,
                        )
                    )
                    if res and res.text:
                        response = res
                        used_model = model_candidate
                        break
                except Exception as m_err:
                    last_model_error = m_err
                    logger.warning("Gemini model '%s' failed during graph analysis: %s. Attempting next candidate.", model_candidate, m_err)

            if not response or not response.text:
                if last_model_error:
                    raise last_model_error
                raise RuntimeError("No response returned from Gemini models")

            payload = GeminiGraphAnalysisPayload.model_validate_json(response.text)
            valid_req_ids = {r["id"] for r in requirements}
            valid_claim_ids = {c["id"]: c["passage_id"] for c in claims}

            for item in payload.relationships:
                if item.requirement_id in valid_req_ids and item.claim_id in valid_claim_ids:
                    rel_str = item.relevance.upper().strip()
                    if rel_str not in {"DIRECTLY_RELEVANT", "PARTIALLY_RELEVANT", "CONTEXTUAL", "NOT_RELEVANT"}:
                        rel_str = "CONTEXTUAL"

                    pas_id = item.passage_id or valid_claim_ids[item.claim_id]
                    analyzed_relationships.append({
                        "requirement_id": item.requirement_id,
                        "claim_id": item.claim_id,
                        "passage_id": pas_id,
                        "relevance": rel_str,
                        "explanation": item.explanation,
                        "confidence": round(float(item.confidence), 2),
                    })

            if analyzed_relationships:
                processing_mode = "gemini"
                analysis_method = f"gemini_relevance_analyzer:{used_model}"

        except Exception as e:
            logger.warning("Gemini evidence graph analysis failed: %s. Executing deterministic fallback.", e)
            analyzed_relationships = []

    # Execute deterministic fallback if Gemini was skipped or failed
    if not analyzed_relationships:
        processing_mode = "fallback"
        analysis_method = "deterministic_keyword_overlap"

        for req in requirements:
            for clm in claims:
                relevance, explanation, confidence = compute_fallback_relevance(req, clm)
                analyzed_relationships.append({
                    "requirement_id": req["id"],
                    "claim_id": clm["id"],
                    "passage_id": clm["passage_id"],
                    "relevance": relevance,
                    "explanation": explanation,
                    "confidence": confidence,
                })

    # Persist relationships in SQLite database
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    relevant_links_count = 0

    for rel in analyzed_relationships:
        rel_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO evidence_relationships (
                id, investigation_id, requirement_id, claim_id, passage_id,
                relevance, explanation, confidence, analysis_method, processing_mode, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(investigation_id, requirement_id, claim_id) DO UPDATE SET
                passage_id = excluded.passage_id,
                relevance = excluded.relevance,
                explanation = excluded.explanation,
                confidence = excluded.confidence,
                analysis_method = excluded.analysis_method,
                processing_mode = excluded.processing_mode,
                created_at = excluded.created_at;
        """, (
            rel_id,
            investigation_id,
            rel["requirement_id"],
            rel["claim_id"],
            rel.get("passage_id"),
            rel["relevance"],
            rel["explanation"],
            rel["confidence"],
            analysis_method,
            processing_mode,
            now,
        ))

        if rel["relevance"] in {"DIRECTLY_RELEVANT", "PARTIALLY_RELEVANT", "CONTEXTUAL"}:
            relevant_links_count += 1

    # Record graph run audit log
    run_id = str(uuid.uuid4())
    cursor.execute("""
        INSERT INTO evidence_graph_runs (
            id, investigation_id, processing_mode, analysis_status, analyzed_pairs_count, relevant_links_count, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?);
    """, (
        run_id,
        investigation_id,
        processing_mode,
        "completed",
        len(analyzed_relationships),
        relevant_links_count,
        now,
    ))

    conn.commit()

    return build_evidence_graph_from_db(conn, investigation_id)


def get_evidence_graph_status(conn, investigation_id: str) -> EvidenceGraphStatusResponse:
    """Fast database status summary for the Evidence Graph."""
    cursor = conn.cursor()

    # Check investigation
    cursor.execute("SELECT id FROM investigations WHERE id = ?;", (investigation_id,))
    if not cursor.fetchone():
        raise ValueError(f"Investigation {investigation_id} not found")

    # Counts
    cursor.execute("SELECT COUNT(*) FROM sources WHERE investigation_id = ?;", (investigation_id,))
    sources_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM claims WHERE investigation_id = ?;", (investigation_id,))
    claims_count = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(r.id)
        FROM contract_requirements r
        JOIN decision_contracts c ON r.contract_id = c.id
        WHERE c.investigation_id = ?;
    """, (investigation_id,))
    reqs_count = cursor.fetchone()[0]

    cursor.execute("""
        SELECT
            COUNT(*),
            SUM(CASE WHEN relevance = 'DIRECTLY_RELEVANT' THEN 1 ELSE 0 END),
            SUM(CASE WHEN relevance = 'PARTIALLY_RELEVANT' THEN 1 ELSE 0 END),
            SUM(CASE WHEN relevance = 'CONTEXTUAL' THEN 1 ELSE 0 END)
        FROM evidence_relationships
        WHERE investigation_id = ?;
    """, (investigation_id,))
    rel_stats = cursor.fetchone()

    total_rels = rel_stats[0] or 0
    directly_relevant = rel_stats[1] or 0
    partially_relevant = rel_stats[2] or 0
    contextual = rel_stats[3] or 0

    cursor.execute("""
        SELECT processing_mode, analysis_status
        FROM evidence_graph_runs
        WHERE investigation_id = ?
        ORDER BY created_at DESC LIMIT 1;
    """, (investigation_id,))
    run_row = cursor.fetchone()

    processing_mode = run_row["processing_mode"] if run_row else "pending"
    last_status = run_row["analysis_status"] if run_row else "none"

    # Total nodes and edges approximate for fast response
    total_nodes = (1 if reqs_count > 0 else 0) + reqs_count + claims_count + sources_count
    total_edges = reqs_count + (directly_relevant + partially_relevant + contextual) + claims_count

    return EvidenceGraphStatusResponse(
        investigation_id=investigation_id,
        total_nodes=total_nodes,
        total_edges=total_edges,
        requirements_represented=reqs_count,
        claims_represented=claims_count,
        sources_represented=sources_count,
        processing_mode=processing_mode,
        last_analysis_status=last_status,
        relationships_count=total_rels,
        directly_relevant_count=directly_relevant,
        partially_relevant_count=partially_relevant,
        contextual_count=contextual,
    )


def json_dump_compact(data: Any) -> str:
    """Helper to dump JSON string without excessive spaces."""
    import json
    return json.dumps(data, separators=(",", ":"))
