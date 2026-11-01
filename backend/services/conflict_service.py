import re
import uuid
import datetime
import logging
from typing import Dict, Any, List, Optional, Tuple, Set

from backend.config import GEMINI_API_KEY, GEMINI_MODEL
from backend.models import (
    ConflictItemModel,
    ConflictSummaryModel,
    ConflictListResponse,
    ConflictStatusResponse,
    GeminiConflictAnalysisPayload,
)

logger = logging.getLogger(__name__)

STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "if", "because", "as", "what",
    "which", "this", "that", "these", "those", "then", "just", "so", "than",
    "such", "both", "through", "about", "for", "is", "of", "while", "during",
    "to", "from", "in", "out", "on", "off", "again", "further", "then", "once",
    "here", "there", "when", "where", "why", "how", "all", "any", "both",
    "each", "few", "more", "most", "other", "some", "such", "no", "nor", "not",
    "only", "own", "same", "too", "very", "can", "will", "should",
    "now", "be", "been", "being", "have", "has", "had", "do", "does", "did",
}

POSITIVE_POLARITY = {
    "increase", "increased", "increases", "increasing", "growth", "grow", "grew",
    "improve", "improved", "improves", "improving", "improvement", "positive",
    "higher", "exceeded", "surpassed", "expanded", "effective", "gain", "gained",
    "benefit", "beneficial", "success", "successful", "achieved",
}

NEGATIVE_POLARITY = {
    "decrease", "decreased", "decreases", "decreasing", "decline", "declined", "declining",
    "drop", "dropped", "dropping", "reduce", "reduced", "reduces", "reduction",
    "deteriorate", "deteriorated", "worse", "worsened", "negative", "lower",
    "fell", "fall", "falling", "deficit", "loss", "ineffective", "failure", "failed",
    "stagnant", "zero", "none", "negligible",
}


def extract_keywords(text: str) -> Set[str]:
    """Tokenizes and filters out punctuation and stop words."""
    words = re.findall(r"[a-zA-Z0-9%]+", text.lower())
    return {w for w in words if w not in STOPWORDS and len(w) > 2}


def extract_numbers(text: str) -> List[Tuple[float, str]]:
    """Extracts numerical quantities and percentages from text."""
    results: List[Tuple[float, str]] = []
    # Percentage
    for m in re.finditer(r"(\d+(?:\.\d+)?)\s*(%|percent)", text, re.IGNORECASE):
        results.append((float(m.group(1)), "percent"))
    # Hours / time
    for m in re.finditer(r"(\d+(?:\.\d+)?)\s*(hours?|hrs?)", text, re.IGNORECASE):
        results.append((float(m.group(1)), "hours"))
    # Currency / amounts
    for m in re.finditer(r"(?:\$|rs\.?|inr)\s*(\d+(?:\.\d+)?)", text, re.IGNORECASE):
        results.append((float(m.group(1)), "currency"))
    for m in re.finditer(r"(\d+(?:\.\d+)?)\s*(crore|million|billion|lakh)", text, re.IGNORECASE):
        unit = m.group(2).lower()
        results.append((float(m.group(1)), unit))
    return results


def generate_candidate_pairs(
    claims: List[Dict[str, Any]],
    relationships: List[Dict[str, Any]]
) -> List[Tuple[Dict[str, Any], Dict[str, Any], int]]:
    """
    Selects and prioritizes candidate claim pairs for conflict analysis:
    Filters out trivially unrelated pairs to avoid combinatorial explosions.
    """
    if len(claims) < 2:
        return []

    # Map each claim to requirement IDs it relates to
    claim_to_reqs: Dict[str, Set[str]] = {}
    for r in relationships:
        cid = r.get("claim_id")
        reqid = r.get("requirement_id")
        if cid and reqid:
            claim_to_reqs.setdefault(cid, set()).add(reqid)

    candidates: List[Tuple[Dict[str, Any], Dict[str, Any], int]] = []

    for i in range(len(claims)):
        for j in range(i + 1, len(claims)):
            c1 = claims[i]
            c2 = claims[j]

            # Compare alphabetically by ID for consistency
            if c1["id"] > c2["id"]:
                c1, c2 = c2, c1

            text1 = c1.get("claim_text", "")
            text2 = c2.get("claim_text", "")

            tokens1 = extract_keywords(text1)
            tokens2 = extract_keywords(text2)

            overlap = tokens1.intersection(tokens2)
            nums1 = extract_numbers(text1)
            nums2 = extract_numbers(text2)

            reqs1 = claim_to_reqs.get(c1["id"], set())
            reqs2 = claim_to_reqs.get(c2["id"], set())
            shared_reqs = reqs1.intersection(reqs2)

            pos1 = bool(tokens1.intersection(POSITIVE_POLARITY))
            neg1 = bool(tokens1.intersection(NEGATIVE_POLARITY))
            pos2 = bool(tokens2.intersection(POSITIVE_POLARITY))
            neg2 = bool(tokens2.intersection(NEGATIVE_POLARITY))

            has_polar_mismatch = (pos1 and neg2) or (neg1 and pos2)
            has_numerical_figures = bool(nums1 and nums2)

            priority = 0
            if has_polar_mismatch and overlap:
                priority += 6
            if has_numerical_figures and overlap:
                priority += 5
            if shared_reqs:
                priority += 4
            if len(overlap) >= 2:
                priority += 2 + len(overlap)

            # Keep candidate if priority threshold met or from differing sources on shared topic
            is_different_source = c1.get("source_id") != c2.get("source_id")
            if priority >= 4 or (is_different_source and len(overlap) >= 2):
                candidates.append((c1, c2, priority))

    # Sort descending by priority and bound to top 25 candidate pairs
    candidates.sort(key=lambda x: x[2], reverse=True)
    return candidates[:25]


METRIC_KEYWORDS = {
    "margin", "margins", "cap", "caps", "revenue", "irr", "rate", "rates",
    "subsidy", "subsidies", "tariff", "tariffs", "expenditure", "capex",
    "cost", "costs", "capacity", "installations", "hours", "debt",
    "guarantee", "guarantees", "valuation", "shares", "equity", "ownership",
    "enrollment", "retention", "survival", "efficacy", "ratio", "tier",
    "gdp", "inflation", "profit", "ebitda", "headcount", "salary"
}


def extract_metric_context(text: str) -> Set[str]:
    """Extracts nouns or descriptive words indicating what metric is being quantified."""
    tokens = extract_keywords(text)
    return tokens.intersection(METRIC_KEYWORDS)


def extract_years(text: str) -> Set[str]:
    """Extracts 4-digit calendar years from text."""
    return set(re.findall(r"\b(19\d\d|20\d\d)\b", text))


def compute_fallback_conflict(
    claim_a: Dict[str, Any],
    claim_b: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """
    Conservative deterministic fallback contradiction and numerical disparity detector.
    Enforces entity, metric, and temporal compatibility checks to prevent false positives.
    Distinct metrics (e.g. operating margin % vs ownership cap %) are never flagged as conflicts.
    """
    text_a = claim_a.get("claim_text", "")
    text_b = claim_b.get("claim_text", "")

    tokens_a = extract_keywords(text_a)
    tokens_b = extract_keywords(text_b)
    overlap = tokens_a.intersection(tokens_b)

    if not overlap:
        return None

    terms_str = ", ".join(f"'{t}'" for t in sorted(list(overlap))[:4])
    nums_a = extract_numbers(text_a)
    nums_b = extract_numbers(text_b)
    years_a = extract_years(text_a)
    years_b = extract_years(text_b)

    # 1. Numerical Discrepancy Check
    if nums_a and nums_b:
        val_a, unit_a = nums_a[0]
        val_b, unit_b = nums_b[0]

        # Check metric concept compatibility
        metrics_a = extract_metric_context(text_a)
        metrics_b = extract_metric_context(text_b)
        shared_metrics = metrics_a.intersection(metrics_b)

        # Both claims must have matching units AND share metric concepts
        if unit_a == unit_b and abs(val_a - val_b) > 0.001:
            # If they measure completely different metrics (e.g. margin vs ownership cap), they are NOT in conflict!
            if metrics_a and metrics_b and not shared_metrics:
                return None

            # If years are distinct and they do not share the exact same metric, it's temporal, not a conflict
            if years_a and years_b and not years_a.intersection(years_b) and not shared_metrics:
                return None

            # Check if they share enough context to refer to the same subject
            if shared_metrics or len(overlap) >= 3:
                ratio = max(val_a, val_b) / max(min(val_a, val_b), 0.001)
                severity = "CRITICAL" if ratio >= 1.5 else "HIGH" if ratio >= 1.2 else "MEDIUM"

                # If years differ but metrics match, it's a temporal conflict/evolution
                if years_a and years_b and not years_a.intersection(years_b):
                    return {
                        "conflict_type": "TEMPORAL_CONFLICT",
                        "severity": "MEDIUM",
                        "explanation": f"Temporal metric evolution detected for shared metric ({', '.join(shared_metrics) or terms_str}): Claim A reports {val_a} {unit_a} in {list(years_a)[0]} vs Claim B reporting {val_b} {unit_b} in {list(years_b)[0]}.",
                        "contextual_differences": "Measurement occurred across different calendar years; divergence may reflect longitudinal market or policy shifts rather than factual error.",
                        "confidence": 0.80,
                        "recommended_action": "Verify whether the change reflects natural longitudinal progression or conflicting accounting methodologies.",
                    }

                return {
                    "conflict_type": "NUMERICAL_CONFLICT",
                    "severity": severity,
                    "explanation": f"Numerical disparity detected on identical metric ({', '.join(shared_metrics) or terms_str}): Claim A reports {val_a} {unit_a} whereas Claim B reports {val_b} {unit_b}.",
                    "contextual_differences": "Variations in sampling methodology, measurement windows, regional cohorts, or calculation baselines may account for divergent values.",
                    "confidence": 0.85,
                    "recommended_action": f"Reconcile measurement protocols and baseline years for {unit_a} metrics across both reporting bodies.",
                }

    # 2. Polar Directional Clashes
    pos_a = bool(tokens_a.intersection(POSITIVE_POLARITY))
    neg_a = bool(tokens_a.intersection(NEGATIVE_POLARITY))
    pos_b = bool(tokens_b.intersection(POSITIVE_POLARITY))
    neg_b = bool(tokens_b.intersection(NEGATIVE_POLARITY))

    if (pos_a and neg_b) or (neg_a and pos_b):
        substantive_overlap = overlap - POSITIVE_POLARITY - NEGATIVE_POLARITY
        # Substantive overlap must contain at least 2 common tokens to be comparing the same subject
        if len(substantive_overlap) >= 2:
            return {
                "conflict_type": "DIRECT_CONTRADICTION",
                "severity": "HIGH",
                "explanation": f"Direct polarity clash detected on shared subject ({', '.join(sorted(list(substantive_overlap))[:3])}): one source asserts an increase/improvement while the other reports a decrease/adverse trend.",
                "contextual_differences": "Differing administrative jurisdictions, intervention cohorts, or study timelines may reflect local variations rather than an irreconcilable factual error.",
                "confidence": 0.82,
                "recommended_action": "Verify whether both sources examine identical geographical cohorts and overlapping observation windows.",
            }

    return None


def get_investigation_conflicts(conn, investigation_id: str) -> ConflictListResponse:
    """
    Loads all persisted evidence conflicts for an investigation with full provenance metadata:
    Joins claim texts, source titles/URLs, passage excerpts, page numbers, and SHA-256 hashes.
    """
    cursor = conn.cursor()

    query = """
        SELECT
            c.id AS conflict_id,
            c.investigation_id,
            c.claim_a_id,
            c.claim_b_id,
            c.conflict_type,
            c.severity,
            c.explanation,
            c.contextual_differences,
            c.confidence,
            c.resolution_status,
            c.reviewer_notes,
            c.recommended_action,
            c.analysis_method,
            c.processing_mode,
            c.created_at,
            c.updated_at,
            ca.claim_text AS claim_a_text,
            ca.category AS claim_a_category,
            ca.source_id AS source_a_id,
            cb.claim_text AS claim_b_text,
            cb.category AS claim_b_category,
            cb.source_id AS source_b_id,
            sa.title AS source_a_title,
            sa.original_url AS source_a_url,
            sb.title AS source_b_title,
            sb.original_url AS source_b_url,
            pa.passage_text AS passage_a_text,
            pa.page_number AS passage_a_page,
            pa.sha256_hash AS passage_a_hash,
            pb.passage_text AS passage_b_text,
            pb.page_number AS passage_b_page,
            pb.sha256_hash AS passage_b_hash
        FROM evidence_conflicts c
        JOIN claims ca ON c.claim_a_id = ca.id
        JOIN claims cb ON c.claim_b_id = cb.id
        LEFT JOIN sources sa ON ca.source_id = sa.id
        LEFT JOIN sources sb ON cb.source_id = sb.id
        LEFT JOIN passages pa ON ca.passage_id = pa.id
        LEFT JOIN passages pb ON cb.passage_id = pb.id
        WHERE c.investigation_id = ?
        ORDER BY
            CASE c.severity
                WHEN 'CRITICAL' THEN 1
                WHEN 'HIGH' THEN 2
                WHEN 'MEDIUM' THEN 3
                ELSE 4
            END ASC,
            c.confidence DESC;
    """
    cursor.execute(query, (investigation_id,))
    rows = cursor.fetchall()

    conflicts: List[ConflictItemModel] = []
    direct_count = 0
    num_count = 0
    temp_count = 0
    context_count = 0
    method_count = 0
    scope_count = 0
    analyst_review_count = 0
    unres_count = 0
    crit_count = 0
    high_count = 0
    med_count = 0
    low_count = 0
    under_review_count = 0
    resolved_count = 0

    for r in rows:
        c_type = r["conflict_type"].upper()
        sev = r["severity"].upper()
        res_stat = r["resolution_status"].lower()

        if c_type == "DIRECT_CONTRADICTION":
            direct_count += 1
        elif c_type == "NUMERICAL_CONFLICT":
            num_count += 1
        elif c_type == "TEMPORAL_CONFLICT":
            temp_count += 1
        elif c_type == "CONTEXTUAL_TENSION":
            context_count += 1
        elif c_type == "METHODOLOGICAL_DISAGREEMENT":
            method_count += 1
        elif c_type == "SCOPE_MISMATCH":
            scope_count += 1
        elif c_type == "RELATED_INFORMATION_REQUIRING_ANALYST_REVIEW":
            analyst_review_count += 1
        else:
            unres_count += 1

        if sev == "CRITICAL":
            crit_count += 1
        elif sev == "HIGH":
            high_count += 1
        elif sev == "MEDIUM":
            med_count += 1
        else:
            low_count += 1

        if res_stat == "under_review":
            under_review_count += 1
        elif res_stat == "resolved":
            resolved_count += 1

        conflicts.append(ConflictItemModel(
            conflict_id=r["conflict_id"],
            investigation_id=r["investigation_id"],
            claim_a_id=r["claim_a_id"],
            claim_b_id=r["claim_b_id"],
            claim_a_text=r["claim_a_text"],
            claim_b_text=r["claim_b_text"],
            claim_a_category=r["claim_a_category"],
            claim_b_category=r["claim_b_category"],
            source_a_id=r["source_a_id"],
            source_b_id=r["source_b_id"],
            source_a_title=r["source_a_title"],
            source_b_title=r["source_b_title"],
            source_a_url=r["source_a_url"],
            source_b_url=r["source_b_url"],
            passage_a_text=r["passage_a_text"],
            passage_b_text=r["passage_b_text"],
            passage_a_page=r["passage_a_page"],
            passage_b_page=r["passage_b_page"],
            passage_a_hash=r["passage_a_hash"],
            passage_b_hash=r["passage_b_hash"],
            conflict_type=c_type,
            severity=sev,
            explanation=r["explanation"],
            contextual_differences=r["contextual_differences"],
            confidence=r["confidence"],
            resolution_status=r["resolution_status"],
            reviewer_notes=r["reviewer_notes"] or "",
            recommended_action=r["recommended_action"],
            analysis_method=r["analysis_method"],
            processing_mode=r["processing_mode"],
            created_at=r["created_at"],
            updated_at=r["updated_at"],
        ))

    # Retrieve overall run processing mode
    cursor.execute("""
        SELECT processing_mode, created_at
        FROM evidence_conflict_runs
        WHERE investigation_id = ?
        ORDER BY created_at DESC LIMIT 1;
    """, (investigation_id,))
    run_row = cursor.fetchone()

    processing_mode = run_row["processing_mode"] if run_row else ("gemini" if any(c.processing_mode == "gemini" for c in conflicts) else "pending")
    last_analyzed_at = run_row["created_at"] if run_row else (conflicts[0].created_at if conflicts else None)

    summary = ConflictSummaryModel(
        total_conflicts=len(conflicts),
        direct_contradictions=direct_count,
        numerical_conflicts=num_count,
        temporal_conflicts=temp_count,
        contextual_tensions=context_count,
        methodological_disagreements=method_count,
        scope_mismatches=scope_count,
        analyst_review_needed=analyst_review_count,
        unresolved_conflicts=unres_count,
        critical_severity=crit_count,
        high_severity=high_count,
        medium_severity=med_count,
        low_severity=low_count,
        under_review_count=under_review_count,
        resolved_count=resolved_count,
    )

    return ConflictListResponse(
        investigation_id=investigation_id,
        conflicts=conflicts,
        summary=summary,
        processing_mode=processing_mode,
        last_analyzed_at=last_analyzed_at,
    )


async def analyze_investigation_conflicts(conn, investigation_id: str) -> ConflictListResponse:
    """
    Orchestrates the conflict detection pipeline:
    1. Generates candidate claim pairs.
    2. Runs Gemini LLM contradiction reasoning with structured Pydantic validation.
    3. Gracefully executes deterministic polar/numerical fallback if Gemini is unavailable.
    4. Persists conflict findings into SQLite.
    5. Returns the updated ConflictListResponse.
    """
    cursor = conn.cursor()

    # Verify investigation exists
    cursor.execute("SELECT id, research_question FROM investigations WHERE id = ?;", (investigation_id,))
    inv = cursor.fetchone()
    if not inv:
        raise ValueError(f"Investigation {investigation_id} not found")

    # Fetch Decision Objective
    cursor.execute("SELECT decision_objective FROM decision_contracts WHERE investigation_id = ?;", (investigation_id,))
    c_row = cursor.fetchone()
    decision_objective = c_row["decision_objective"] if c_row else inv["research_question"]

    # Fetch Claims with passage & source info
    claims_query = """
        SELECT
            c.id, c.claim_text, c.category, c.source_id, c.passage_id,
            s.title AS source_title, p.passage_text, p.page_number
        FROM claims c
        LEFT JOIN sources s ON c.source_id = s.id
        LEFT JOIN passages p ON c.passage_id = p.id
        WHERE c.investigation_id = ?;
    """
    cursor.execute(claims_query, (investigation_id,))
    claims = [dict(r) for r in cursor.fetchall()]

    if len(claims) < 2:
        return get_investigation_conflicts(conn, investigation_id)

    # Fetch existing graph relationships to guide pair generation
    cursor.execute("SELECT claim_id, requirement_id FROM evidence_relationships WHERE investigation_id = ?;", (investigation_id,))
    relationships = [dict(r) for r in cursor.fetchall()]

    candidate_pairs = generate_candidate_pairs(claims, relationships)
    if not candidate_pairs:
        return get_investigation_conflicts(conn, investigation_id)

    detected_conflicts: List[Dict[str, Any]] = []
    processing_mode = "fallback"
    analysis_method = "deterministic_polar_numerical_scanner"
    gemini_completed = False

    # Attempt Gemini LLM Analysis if API key configured
    if GEMINI_API_KEY:
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=GEMINI_API_KEY)

            # Build compact prompt representing candidate pairs
            pairs_data = []
            for c1, c2, priority in candidate_pairs:
                pairs_data.append({
                    "pair_id": f"{c1['id']}__{c2['id']}",
                    "claim_a": {
                        "id": c1["id"],
                        "text": c1["claim_text"],
                        "category": c1.get("category"),
                        "source": c1.get("source_title"),
                        "excerpt": (c1.get("passage_text") or "")[:200],
                    },
                    "claim_b": {
                        "id": c2["id"],
                        "text": c2["claim_text"],
                        "category": c2.get("category"),
                        "source": c2.get("source_title"),
                        "excerpt": (c2.get("passage_text") or "")[:200],
                    }
                })

            prompt = (
                "You are the Forensic Contradiction & Conflict Detection Engine for TRUTHMAP AI.\n"
                "Your objective is to identify genuine contradictions, numerical disparities, temporal clashes, or contextual tensions between pairs of claims.\n\n"
                "MANDATORY FORENSIC INTEGRITY RULES:\n"
                "1. NEVER SELECT A WINNING SOURCE: A contradiction is NOT proof that either claim is false. Do not decide who is correct.\n"
                "2. NO INVENTED EVIDENCE: Only analyze the exact claim text and passage excerpts provided. Do not invent dates, percentages, or facts.\n"
                "3. ACCURATE CLASSIFICATION: Choose exactly one:\n"
                "   - DIRECT_CONTRADICTION: Mutually exclusive factual assertions about the exact same entity and timeframe under identical conditions.\n"
                "   - NUMERICAL_CONFLICT: Materially incompatible numerical figures for the EXACT SAME metric, entity, and observation period.\n"
                "   - TEMPORAL_CONFLICT: Disagreement over events, milestones, or statuses over time for the same subject.\n"
                "   - SCOPE_MISMATCH: Apparent discrepancy explained by different administrative levels, geographic regions, or cohort definitions.\n"
                "   - CONTEXTUAL_TENSION: Strategic or regulatory tension between two compatible true facts (e.g. an ownership cap limiting an acquisition).\n"
                "   - METHODOLOGICAL_DISAGREEMENT: Different conclusions stemming from different analytical models or accounting standards.\n"
                "   - UNRESOLVED_CONFLICT: Incompatible claims lacking sufficient context to determine the root cause.\n"
                "4. SEVERITY: CRITICAL, HIGH, MEDIUM, LOW.\n"
                "5. STRICT LOGICAL COMPATIBILITY CHECK:\n"
                "   - If two statements can both simultaneously be true in the real world (e.g. historical operating margins were 21.5% in 2024 AND a government regulatory ownership cap is 49% in 2026), they are NOT in direct contradiction or numerical conflict!\n"
                "   - Distinct metrics (e.g. margins vs ownership caps, capex vs subsidies) are complementary facts, NOT conflicts. Do NOT report conflicts for distinct metrics.\n"
                "   - If claims are compatible, complementary, or describe distinct facts, DO NOT return a conflict for that pair.\n"
                "6. ACTIONABLE VERIFICATION: Suggest concrete evidence audits to test or falsify the discrepancy.\n\n"
                f"DECISION MANDATE:\n\"{decision_objective}\"\n\n"
                f"CANDIDATE CLAIM PAIRS ({len(pairs_data)} pairs):\n"
                f"{json_dump_compact(pairs_data)}\n\n"
                "Return ONLY a valid JSON object matching:\n"
                "{\n"
                "  \"conflicts\": [\n"
                "    {\n"
                "      \"claim_a_id\": \"...\",\n"
                "      \"claim_b_id\": \"...\",\n"
                "      \"conflict_type\": \"DIRECT_CONTRADICTION\",\n"
                "      \"severity\": \"HIGH\",\n"
                "      \"explanation\": \"Detailed factual description of the clash\",\n"
                "      \"contextual_differences\": \"Potential confounding variables (dates, populations)\",\n"
                "      \"confidence\": 0.88,\n"
                "      \"recommended_action\": \"Empirical audit requirement\"\n"
                "    }\n"
                "  ]\n"
                "}"
            )

            candidate_models = [GEMINI_MODEL]
            for fallback_model in ["gemini-flash-lite-latest", "gemini-3.5-flash-lite", "gemini-3-flash-preview"]:
                if fallback_model not in candidate_models:
                    candidate_models.append(fallback_model)

            response = None
            used_model = None
            last_err = None

            for model_cand in candidate_models:
                try:
                    res = client.models.generate_content(
                        model=model_cand,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            temperature=0.1,
                            max_output_tokens=4000,
                        )
                    )
                    if res and res.text:
                        response = res
                        used_model = model_cand
                        break
                except Exception as m_err:
                    last_err = m_err
                    logger.warning("Gemini conflict model '%s' failed: %s. Trying next candidate.", model_cand, m_err)

            gemini_completed = False
            if response and response.text:
                import json
                try:
                    raw_data = json.loads(response.text)
                    items = []
                    if isinstance(raw_data, dict):
                        items = raw_data.get("conflicts", [])
                    elif isinstance(raw_data, list):
                        items = raw_data

                    claim_id_set = {c["id"] for c in claims}

                    for item in items:
                        if not isinstance(item, dict):
                            continue
                        c_type = (item.get("conflict_type") or "").upper().strip()
                        if c_type in {"NONE", "COMPATIBLE", "NO_CONFLICT", "ORTHOGONAL", ""}:
                            continue

                        claim_a_id = item.get("claim_a_id")
                        claim_b_id = item.get("claim_b_id")
                        if claim_a_id in claim_id_set and claim_b_id in claim_id_set:
                            ca_id, cb_id = claim_a_id, claim_b_id
                            if ca_id > cb_id:
                                ca_id, cb_id = cb_id, ca_id

                            valid_types = {
                                "DIRECT_CONTRADICTION", "NUMERICAL_CONFLICT", "TEMPORAL_CONFLICT",
                                "CONTEXTUAL_TENSION", "METHODOLOGICAL_DISAGREEMENT", "UNRESOLVED_CONFLICT",
                                "SCOPE_MISMATCH", "RELATED_INFORMATION_REQUIRING_ANALYST_REVIEW"
                            }
                            if c_type not in valid_types:
                                c_type = "UNRESOLVED_CONFLICT"

                            sev = (item.get("severity") or "MEDIUM").upper().strip()
                            if sev not in {"CRITICAL", "HIGH", "MEDIUM", "LOW"}:
                                sev = "MEDIUM"

                            try:
                                conf_val = round(float(item.get("confidence", 0.85)), 2)
                            except (TypeError, ValueError):
                                conf_val = 0.85

                            detected_conflicts.append({
                                "claim_a_id": ca_id,
                                "claim_b_id": cb_id,
                                "conflict_type": c_type,
                                "severity": sev,
                                "explanation": item.get("explanation") or "Gemini detected semantic tension between claims.",
                                "contextual_differences": item.get("contextual_differences") or "Unspecified contextual variance.",
                                "confidence": conf_val,
                                "recommended_action": item.get("recommended_action") or "Reconcile reporting methodology between opposing sources.",
                            })

                    gemini_completed = True
                    processing_mode = "gemini"
                    analysis_method = f"gemini_conflict_engine:{used_model}"

                except Exception as parse_err:
                    logger.warning("Failed to parse Gemini conflict JSON: %s. Executing fallback.", parse_err)
                    gemini_completed = False

        except Exception as e:
            logger.warning("Gemini conflict analysis failed: %s. Executing deterministic fallback.", e)
            detected_conflicts = []
            gemini_completed = False

    # Execute deterministic fallback if Gemini was skipped or failed OR if Gemini detected 0 conflicts but candidates exist
    if not gemini_completed or (len(detected_conflicts) == 0 and len(candidate_pairs) > 0):
        if not gemini_completed:
            processing_mode = "fallback"
            analysis_method = "deterministic_polar_numerical_scanner"
        else:
            analysis_method = f"gemini_augmented_deterministic:{used_model}"

        existing_pairs = {(c["claim_a_id"], c["claim_b_id"]) for c in detected_conflicts}

        for c1, c2, _ in candidate_pairs:
            ca_id, cb_id = c1["id"], c2["id"]
            if ca_id > cb_id:
                ca_id, cb_id = cb_id, ca_id
            if (ca_id, cb_id) in existing_pairs:
                continue

            fb = compute_fallback_conflict(c1, c2)
            if fb:
                detected_conflicts.append({
                    "claim_a_id": ca_id,
                    "claim_b_id": cb_id,
                    "conflict_type": fb["conflict_type"],
                    "severity": fb["severity"],
                    "explanation": fb["explanation"],
                    "contextual_differences": fb["contextual_differences"],
                    "confidence": fb["confidence"],
                    "recommended_action": fb["recommended_action"],
                })
                existing_pairs.add((ca_id, cb_id))

    # Persist findings in SQLite database
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()

    for item in detected_conflicts:
        conflict_id = f"conf_{uuid.uuid4().hex[:12]}"
        cursor.execute("""
            INSERT INTO evidence_conflicts (
                id, investigation_id, claim_a_id, claim_b_id, conflict_type,
                severity, explanation, contextual_differences, confidence,
                resolution_status, reviewer_notes, recommended_action,
                analysis_method, processing_mode, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'unresolved', '', ?, ?, ?, ?, ?)
            ON CONFLICT(investigation_id, claim_a_id, claim_b_id) DO UPDATE SET
                conflict_type = excluded.conflict_type,
                severity = excluded.severity,
                explanation = excluded.explanation,
                contextual_differences = excluded.contextual_differences,
                confidence = excluded.confidence,
                recommended_action = excluded.recommended_action,
                analysis_method = excluded.analysis_method,
                processing_mode = excluded.processing_mode,
                updated_at = excluded.updated_at;
        """, (
            conflict_id,
            investigation_id,
            item["claim_a_id"],
            item["claim_b_id"],
            item["conflict_type"],
            item["severity"],
            item["explanation"],
            item.get("contextual_differences") or "",
            item["confidence"],
            item["recommended_action"],
            analysis_method,
            processing_mode,
            now,
            now,
        ))

    # Audit log run
    run_id = str(uuid.uuid4())
    cursor.execute("""
        INSERT INTO evidence_conflict_runs (
            id, investigation_id, processing_mode, analysis_status,
            pairs_analyzed_count, conflicts_detected_count, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?);
    """, (
        run_id,
        investigation_id,
        processing_mode,
        "completed",
        len(candidate_pairs),
        len(detected_conflicts),
        now,
    ))

    conn.commit()

    return get_investigation_conflicts(conn, investigation_id)


def update_conflict_resolution(
    conn,
    investigation_id: str,
    conflict_id: str,
    resolution_status: Optional[str] = None,
    reviewer_notes: Optional[str] = None
) -> ConflictItemModel:
    """Updates reviewer status and forensic notes on a specific conflict finding."""
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM evidence_conflicts
        WHERE id = ? AND investigation_id = ?;
    """, (conflict_id, investigation_id))
    existing = cursor.fetchone()
    if not existing:
        raise ValueError(f"Conflict '{conflict_id}' not found in investigation '{investigation_id}'")

    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    new_status = (resolution_status or existing["resolution_status"]).lower().strip()
    if new_status not in {"unresolved", "under_review", "resolved"}:
        new_status = existing["resolution_status"]

    new_notes = reviewer_notes if reviewer_notes is not None else existing["reviewer_notes"]

    cursor.execute("""
        UPDATE evidence_conflicts
        SET resolution_status = ?, reviewer_notes = ?, updated_at = ?
        WHERE id = ? AND investigation_id = ?;
    """, (new_status, new_notes, now, conflict_id, investigation_id))
    conn.commit()

    # Re-query full model
    all_conflicts = get_investigation_conflicts(conn, investigation_id)
    for c in all_conflicts.conflicts:
        if c.conflict_id == conflict_id:
            return c

    raise RuntimeError("Failed to retrieve updated conflict record")


def get_conflict_status(conn, investigation_id: str) -> ConflictStatusResponse:
    """Fast lightweight status summary for conflicts."""
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM investigations WHERE id = ?;", (investigation_id,))
    if not cursor.fetchone():
        raise ValueError(f"Investigation {investigation_id} not found")

    cursor.execute("""
        SELECT
            COUNT(*),
            SUM(CASE WHEN conflict_type = 'DIRECT_CONTRADICTION' THEN 1 ELSE 0 END),
            SUM(CASE WHEN conflict_type = 'NUMERICAL_CONFLICT' THEN 1 ELSE 0 END),
            SUM(CASE WHEN conflict_type = 'CONTEXTUAL_TENSION' THEN 1 ELSE 0 END),
            SUM(CASE WHEN conflict_type = 'UNRESOLVED_CONFLICT' THEN 1 ELSE 0 END)
        FROM evidence_conflicts
        WHERE investigation_id = ?;
    """, (investigation_id,))
    stats = cursor.fetchone()

    total_conflicts = stats[0] or 0
    direct_count = stats[1] or 0
    num_count = stats[2] or 0
    context_count = stats[3] or 0
    unres_count = stats[4] or 0

    cursor.execute("""
        SELECT processing_mode, analysis_status, created_at
        FROM evidence_conflict_runs
        WHERE investigation_id = ?
        ORDER BY created_at DESC LIMIT 1;
    """, (investigation_id,))
    run_row = cursor.fetchone()

    processing_mode = run_row["processing_mode"] if run_row else "pending"
    last_status = run_row["analysis_status"] if run_row else "none"
    last_analyzed = run_row["created_at"] if run_row else None

    return ConflictStatusResponse(
        investigation_id=investigation_id,
        total_conflicts=total_conflicts,
        direct_contradictions=direct_count,
        numerical_conflicts=num_count,
        contextual_tensions=context_count,
        unresolved_conflicts=unres_count,
        processing_mode=processing_mode,
        last_analysis_status=last_status,
        last_analyzed_at=last_analyzed,
    )


def json_dump_compact(data: Any) -> str:
    """Helper to dump JSON string without excessive whitespace."""
    import json
    return json.dumps(data, separators=(",", ":"))
