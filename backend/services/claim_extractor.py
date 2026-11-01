import re
import uuid
import datetime
import logging
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from backend.config import GEMINI_API_KEY, GEMINI_MODEL

logger = logging.getLogger(__name__)


class GeminiExtractedClaim(BaseModel):
    claim_text: str = Field(..., description="An atomic, independently verifiable factual proposition directly asserted in the passage.")
    category: str = Field(default="factual", description="One of: factual, statistical, causal, policy, temporal")
    confidence: float = Field(default=0.90, ge=0.0, le=1.0, description="Extraction confidence score between 0.0 and 1.0")


class GeminiClaimsPayload(BaseModel):
    claims: List[GeminiExtractedClaim] = Field(default_factory=list, description="List of atomic claims extracted strictly from the provided passage")


def classify_claim_category(text: str) -> str:
    """Classifies a claim into factual, statistical, causal, policy, or temporal."""
    lower = text.lower()
    if re.search(r"(\b\d+(\.\d+)?%|\$\d+|\b\d+\s*(crore|lakh|million|billion|trillion|percent|users|cases)\b)", lower):
        return "statistical"
    if any(k in lower for k in ["because", "causes", "caused by", "resulting in", "results in", "led to", "leads to", "due to", "as a result of"]):
        return "causal"
    if any(k in lower for k in ["policy", "guideline", "scheme", "mandate", "act", "law", "regulation", "eligible", "eligibility", "criteria"]):
        return "policy"
    if re.search(r"\b(in 19\d\d|in 20\d\d|since 19\d\d|since 20\d\d|between 20\d\d|by 20\d\d|during 20\d\d|fiscal year|quarter \d)\b", lower):
        return "temporal"
    return "factual"


def split_into_sentences(text: str) -> List[str]:
    """Splits text into sentences while protecting common abbreviations."""
    if not text:
        return []
    
    protected = text
    abbrevs = {
        "e.g.": "e_g_", "i.e.": "i_e_", "Mr.": "Mr_", "Dr.": "Dr_",
        "Ms.": "Ms_", "Prof.": "Prof_", "Inc.": "Inc_", "Ltd.": "Ltd_", "vs.": "vs_"
    }
    for k, v in abbrevs.items():
        protected = protected.replace(k, v)

    raw_sentences = re.split(r"(?<=[.!?])\s+", protected)
    sentences = []
    for s in raw_sentences:
        clean = s
        for k, v in abbrevs.items():
            clean = clean.replace(v, k)
        if clean.strip():
            sentences.append(clean.strip())
    return sentences


def extract_claims_deterministic(passage_text: str, source_id: str, passage_id: str, investigation_id: str) -> List[Dict[str, Any]]:
    """
    Deterministic proposition extractor that decomposes passage text into
    independently verifiable atomic factual propositions using grammatical
    and syntactic boundaries.
    """
    if not passage_text or len(passage_text.strip()) < 15:
        return []

    claims: List[Dict[str, Any]] = []
    raw_sentences = split_into_sentences(passage_text)

    for sentence in raw_sentences:
        clean_sentence = sentence.strip()
        if len(clean_sentence) < 20:
            continue

        # Strip leading discourse connectives
        clean_sentence = re.sub(
            r"^(Furthermore|Moreover|In addition|Consequently|However|Therefore|Notably|Significantly),\s*",
            "",
            clean_sentence,
            flags=re.IGNORECASE
        )

        # Check for compound contrasting or dual-clause statements (e.g. "while", "whereas", semicolons)
        split_clauses = re.split(r",\s*(?:while|whereas|although)\s*|;\s*", clean_sentence, flags=re.IGNORECASE)

        if len(split_clauses) > 1:
            for clause in split_clauses:
                c = clause.strip()
                if len(c) >= 15:
                    formatted_claim = c[0].upper() + c[1:]
                    if not formatted_claim.endswith((".", "!", "?")):
                        formatted_claim += "."
                    
                    has_numbers = bool(re.search(r"\b\d+\b", formatted_claim))
                    confidence = 0.85 if has_numbers else 0.78
                    category = classify_claim_category(formatted_claim)

                    claims.append({
                        "id": str(uuid.uuid4()),
                        "investigation_id": investigation_id,
                        "source_id": source_id,
                        "passage_id": passage_id,
                        "claim_text": formatted_claim,
                        "category": category,
                        "extraction_method": "deterministic_syntactic_decomposition",
                        "processing_mode": "fallback",
                        "extraction_confidence": confidence,
                        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    })
        else:
            formatted_claim = clean_sentence
            if not formatted_claim.endswith((".", "!", "?")):
                formatted_claim += "."

            has_numbers = bool(re.search(r"\b\d+\b", formatted_claim))
            confidence = 0.85 if has_numbers else 0.80
            category = classify_claim_category(formatted_claim)

            claims.append({
                "id": str(uuid.uuid4()),
                "investigation_id": investigation_id,
                "source_id": source_id,
                "passage_id": passage_id,
                "claim_text": formatted_claim,
                "category": category,
                "extraction_method": "deterministic_syntactic_decomposition",
                "processing_mode": "fallback",
                "extraction_confidence": confidence,
                "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            })

    return claims


async def extract_claims_from_passage(
    passage_text: str,
    source_id: str,
    passage_id: str,
    investigation_id: str
) -> List[Dict[str, Any]]:
    """
    Extracts atomic claims from a passage.
    Prefers Gemini structured LLM extraction if GEMINI_API_KEY is configured.
    Strictly grounds every claim to the exact passage to prevent hallucination.
    Gracefully falls back to deterministic syntactic extraction if Gemini is unavailable.
    """
    if not passage_text or len(passage_text.strip()) < 15:
        return []

    if GEMINI_API_KEY:
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=GEMINI_API_KEY)
            prompt = (
                "You are an evidence extraction engine for an enterprise decision stress-testing platform.\n"
                "Extract atomic factual claims strictly and exclusively from the provided passage.\n\n"
                "STRICT FORENSIC EXTRACTION RULES:\n"
                "1. Each claim must be an independent, atomic proposition that can be tested against evidence.\n"
                "2. Do NOT invent, assume, extrapolate, summarize, or synthesize missing numbers, names, or events.\n"
                "3. Do NOT invent quotations or citations.\n"
                "4. Retain exact numerical values, percentages, temporal markers, and proper nouns.\n"
                "5. Categorize each claim as: 'factual', 'statistical', 'causal', 'policy', or 'temporal'.\n"
                "6. If the passage is conversational, boilerplate, navigation, or contains no testable factual claims, return an empty list.\n\n"
                "Return ONLY a valid JSON object matching this schema:\n"
                "{\n"
                "  \"claims\": [\n"
                "    {\n"
                "      \"claim_text\": \"...\",\n"
                "      \"category\": \"statistical|causal|policy|temporal|factual\",\n"
                "      \"confidence\": 0.95\n"
                "    }\n"
                "  ]\n"
                "}\n\n"
                f"SOURCE PASSAGE:\n\"\"\"{passage_text}\"\"\"\n"
            )

            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.0,
                    max_output_tokens=1500,
                )
            )

            if response.text:
                payload = GeminiClaimsPayload.model_validate_json(response.text)
                if payload.claims:
                    extracted_claims = []
                    for c in payload.claims:
                        clean_text = c.claim_text.strip()
                        if len(clean_text) >= 10:
                            if not clean_text.endswith((".", "!", "?")):
                                clean_text += "."
                            clean_text = clean_text[0].upper() + clean_text[1:]
                            
                            valid_category = c.category.lower().strip()
                            if valid_category not in {"factual", "statistical", "causal", "policy", "temporal"}:
                                valid_category = classify_claim_category(clean_text)

                            extracted_claims.append({
                                "id": str(uuid.uuid4()),
                                "investigation_id": investigation_id,
                                "source_id": source_id,
                                "passage_id": passage_id,
                                "claim_text": clean_text,
                                "category": valid_category,
                                "extraction_method": "gemini_llm_structured",
                                "processing_mode": "gemini",
                                "extraction_confidence": round(min(max(float(c.confidence), 0.5), 0.98), 2),
                                "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                            })
                    if extracted_claims:
                        return extracted_claims

        except Exception as e:
            logger.warning(
                "Gemini claim extraction failed or unavailable: %s. Falling back to deterministic extractor.",
                str(e)
            )

    return extract_claims_deterministic(passage_text, source_id, passage_id, investigation_id)
