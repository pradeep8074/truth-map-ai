import datetime
import hashlib
from typing import Dict, Any, List
import pymupdf

from backend.config import MAX_PDF_SIZE
from backend.security import sanitize_text
from backend.services.freshness_service import extract_pdf_date_metadata


class PDFParsingError(Exception):
    pass


def parse_pdf_document(file_bytes: bytes, filename: str) -> Dict[str, Any]:
    """
    Parses a PDF document using PyMuPDF.
    Preserves page numbers, checks for encryption, and detects scanned/empty documents.
    """
    if len(file_bytes) > MAX_PDF_SIZE:
        raise PDFParsingError(f"File size ({len(file_bytes)} bytes) exceeds maximum limit of {MAX_PDF_SIZE} bytes.")

    if not file_bytes.startswith(b"%PDF-"):
        raise PDFParsingError("Invalid file header: File is not a valid PDF document.")

    content_hash = hashlib.sha256(file_bytes).hexdigest()
    retrieved_at = datetime.datetime.now(datetime.timezone.utc).isoformat()

    try:
        doc = pymupdf.open(stream=file_bytes, filetype="pdf")
    except Exception as e:
        raise PDFParsingError(f"PyMuPDF failed to open PDF document: {str(e)}")

    try:
        if doc.is_encrypted:
            raise PDFParsingError("Password-protected or encrypted PDFs cannot be processed without credentials.")

        total_pages = len(doc)
        if total_pages == 0:
            raise PDFParsingError("The PDF document contains 0 pages.")

        metadata = doc.metadata or {}
        title = metadata.get("title") or filename
        author = metadata.get("author") or "Unknown Author"

        page_records: List[Dict[str, Any]] = []
        total_extracted_text_len = 0
        all_text_blocks: List[str] = []

        for page_num in range(1, total_pages + 1):
            page = doc[page_num - 1]
            page_text = page.get_text("text") or ""
            clean_page_text = sanitize_text(page_text)
            
            total_extracted_text_len += len(clean_page_text)
            page_records.append({
                "page_number": page_num,
                "text": clean_page_text,
            })
            if clean_page_text:
                all_text_blocks.append(f"--- Page {page_num} ---\n{clean_page_text}")

        full_extracted_text = "\n\n".join(all_text_blocks)

        # Inspect first 2 pages for explicit publication markers
        first_pages_sample = "\n".join([p["text"] for p in page_records[:2]])
        date_meta = extract_pdf_date_metadata(metadata, first_pages_sample)

        # Check for scanned or image-only PDF
        is_scanned = False
        warning_message = None
        # If average extractable text per page is under 40 characters
        if total_extracted_text_len < 50 or (total_extracted_text_len / total_pages) < 30:
            is_scanned = True
            warning_message = (
                f"Scanned or image-only PDF detected ({total_pages} pages, only {total_extracted_text_len} characters extracted). "
                "Optical Character Recognition (OCR) is required to parse rasterized text. "
                "No OCR was performed in this pipeline stage."
            )

        return {
            "title": title,
            "publisher": author,
            "publication_date": date_meta["publication_date"],
            "source_modified_date": date_meta["source_modified_date"],
            "date_source": date_meta["date_source"],
            "date_extraction_method": date_meta["date_extraction_method"],
            "date_confidence": date_meta["date_confidence"],
            "date_validation_status": date_meta["date_validation_status"],
            "retrieved_at": retrieved_at,
            "content_hash": content_hash,
            "total_pages": total_pages,
            "is_scanned": is_scanned,
            "warning": warning_message,
            "pages": page_records,
            "extracted_text": full_extracted_text,
        }
    finally:
        doc.close()
