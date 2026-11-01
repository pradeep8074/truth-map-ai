import hashlib
import re
import uuid
from typing import List, Dict, Any, Optional


def normalize_for_fingerprint(text: str) -> str:
    """
    Normalizes text for reproducible SHA-256 fingerprinting:
    - Lowercase
    - Strips leading/trailing whitespace
    - Replaces internal multiple whitespace/newlines with a single space
    """
    if not text:
        return ""
    return re.sub(r"\s+", " ", text.strip().lower())


def compute_sha256(text: str) -> str:
    """Computes SHA-256 hash of normalized text."""
    normalized = normalize_for_fingerprint(text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def segment_into_passages(
    full_text: str,
    source_id: str,
    page_number: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Segments raw text into structured passage records.
    Preserves exact paragraph indices and character start/end offsets.
    Filters out empty or trivial boilerplate (<20 chars).
    """
    if not full_text:
        return []

    passages: List[Dict[str, Any]] = []
    
    # Split by double newline or single newline if paragraphs are structured
    raw_paragraphs = re.split(r"\n\s*\n|\r\n\s*\r\n", full_text)
    current_offset = 0

    para_idx = 0
    for para in raw_paragraphs:
        cleaned_para = para.strip()
        
        # Locate paragraph offset within source text
        start_offset = full_text.find(para, current_offset)
        if start_offset == -1:
            start_offset = current_offset
        end_offset = start_offset + len(para)
        current_offset = end_offset

        # Skip very short fragments (headers, page numbers, single words)
        if len(cleaned_para) < 20:
            continue

        # If a paragraph is unusually long (>1200 chars), split into logical multi-sentence chunks
        if len(cleaned_para) > 1200:
            sentences = re.split(r"(?<=[.!?])\s+", cleaned_para)
            chunk = ""
            chunk_start = start_offset
            for s in sentences:
                if len(chunk) + len(s) > 800 and len(chunk) > 200:
                    passages.append({
                        "id": str(uuid.uuid4()),
                        "source_id": source_id,
                        "passage_text": chunk.strip(),
                        "page_number": page_number,
                        "paragraph_index": para_idx,
                        "start_offset": chunk_start,
                        "end_offset": chunk_start + len(chunk),
                        "sha256_hash": compute_sha256(chunk),
                    })
                    chunk_start += len(chunk) + 1
                    chunk = s + " "
                else:
                    chunk += s + " "
            if chunk.strip():
                passages.append({
                    "id": str(uuid.uuid4()),
                    "source_id": source_id,
                    "passage_text": chunk.strip(),
                    "page_number": page_number,
                    "paragraph_index": para_idx,
                    "start_offset": chunk_start,
                    "end_offset": chunk_start + len(chunk),
                    "sha256_hash": compute_sha256(chunk),
                })
        else:
            passages.append({
                "id": str(uuid.uuid4()),
                "source_id": source_id,
                "passage_text": cleaned_para,
                "page_number": page_number,
                "paragraph_index": para_idx,
                "start_offset": start_offset,
                "end_offset": end_offset,
                "sha256_hash": compute_sha256(cleaned_para),
            })
        para_idx += 1

    return passages
