import pytest
import pymupdf
from backend.services.pdf_parser import parse_pdf_document, PDFParsingError


def create_in_memory_pdf(pages_text: list[str]) -> bytes:
    """Helper to generate in-memory test PDFs using PyMuPDF."""
    doc = pymupdf.open()
    for text in pages_text:
        page = doc.new_page(width=595, height=842)
        if text:
            page.insert_text((50, 72), text, fontsize=12)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def test_pdf_parsing_preserves_pages_and_text():
    page1 = "TruthMap AI forensic analysis report. Section 1 covers factual premises."
    page2 = "Section 2 provides empirical findings with 94.2% statistical confidence."
    pdf_bytes = create_in_memory_pdf([page1, page2])

    result = parse_pdf_document(pdf_bytes, "audit_sample.pdf")

    assert result["total_pages"] == 2
    assert not result["is_scanned"]
    assert result["warning"] is None
    assert len(result["pages"]) == 2
    assert result["pages"][0]["page_number"] == 1
    assert "Section 1" in result["pages"][0]["text"]
    assert result["pages"][1]["page_number"] == 2
    assert "Section 2" in result["pages"][1]["text"]
    assert len(result["content_hash"]) == 64


def test_pdf_scanned_detection_warning():
    # PDF with blank/image-only pages (0 text)
    pdf_bytes = create_in_memory_pdf(["", ""])
    result = parse_pdf_document(pdf_bytes, "scanned_doc.pdf")

    assert result["total_pages"] == 2
    assert result["is_scanned"] is True
    assert result["warning"] is not None
    assert "OCR" in result["warning"]
    assert "No OCR was performed" in result["warning"]


def test_invalid_header_rejection():
    with pytest.raises(PDFParsingError) as exc_info:
        parse_pdf_document(b"NOT_A_REAL_PDF_HEADER", "fake.pdf")
    assert "Invalid file header" in str(exc_info.value)
