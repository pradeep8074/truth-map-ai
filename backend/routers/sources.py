import uuid
import datetime
import logging
from typing import List
from fastapi import APIRouter, HTTPException, UploadFile, File
from backend.database import get_db
from backend.models import (
    SourceAddRequest,
    SourceResponse,
    PassageResponse,
)
from backend.services.web_scraper import fetch_webpage, WebScrapingError
from backend.services.pdf_parser import parse_pdf_document, PDFParsingError
from backend.services.provenance import segment_into_passages
from backend.services.claim_extractor import extract_claims_from_passage
from backend.services.freshness_service import classify_source_freshness

logger = logging.getLogger(__name__)

router = APIRouter(tags=["sources"])


async def ingest_single_url(investigation_id: str, url: str) -> dict:
    """Ingests a single URL, extracts passages and claims, and persists to DB."""
    source_id = str(uuid.uuid4())
    retrieved_at = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # Create initial pending source entry
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO sources (
                id, investigation_id, source_type, original_url, title,
                publisher, publication_date, retrieved_at, content_hash,
                extraction_status, extracted_text, error_message
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source_id, investigation_id, "web", url, url,
                None, None, retrieved_at, None,
                "pending", None, None
            )
        )
        conn.commit()

    try:
        scraped = await fetch_webpage(url)
        extracted_text = scraped["extracted_text"]
        
        # Segment into passages with character offsets and SHA-256 fingerprints
        passages = segment_into_passages(extracted_text, source_id, page_number=None)

        all_claims = []
        for p in passages[:15]:
            claims = await extract_claims_from_passage(
                passage_text=p["passage_text"],
                source_id=source_id,
                passage_id=p["id"],
                investigation_id=investigation_id
            )
            all_claims.extend(claims)

        # Classify freshness and determine source origin deterministically
        is_demo_url = any(d in url.lower() for d in ["localhost", "127.0.0.1", "example.com", "test.local", "fixture"])
        source_origin = "DEMONSTRATION_DOCUMENT" if is_demo_url else "ACTUAL_PUBLIC_SOURCE"
        
        freshness = classify_source_freshness(
            scraped.get("publication_date"),
            date_validation_status=scraped.get("date_validation_status")
        )
        freshness_status = freshness["status"]
        freshness_explanation = freshness["explanation"]

        # Persist extracted data atomically
        with get_db() as conn:
            # 1. Update source
            conn.execute(
                """
                UPDATE sources SET
                    title = ?,
                    publisher = ?,
                    publication_date = ?,
                    source_modified_date = ?,
                    date_source = ?,
                    date_extraction_method = ?,
                    date_confidence = ?,
                    date_validation_status = ?,
                    freshness_status = ?,
                    freshness_explanation = ?,
                    source_origin = ?,
                    content_hash = ?,
                    extraction_status = ?,
                    extracted_text = ?,
                    error_message = NULL
                WHERE id = ?
                """,
                (
                    scraped["title"],
                    scraped["publisher"],
                    scraped["publication_date"],
                    scraped.get("source_modified_date"),
                    scraped.get("date_source"),
                    scraped.get("date_extraction_method"),
                    scraped.get("date_confidence", 0.0),
                    scraped.get("date_validation_status", "MISSING"),
                    freshness_status,
                    freshness_explanation,
                    source_origin,
                    scraped["content_hash"],
                    "completed",
                    extracted_text,
                    source_id
                )
            )

            # 2. Insert passages
            for p in passages:
                conn.execute(
                    """
                    INSERT INTO passages (
                        id, source_id, passage_text, page_number,
                        paragraph_index, start_offset, end_offset, sha256_hash
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        p["id"], p["source_id"], p["passage_text"], p["page_number"],
                        p["paragraph_index"], p["start_offset"], p["end_offset"], p["sha256_hash"]
                    )
                )

            # 3. Insert claims
            for c in all_claims:
                conn.execute(
                    """
                    INSERT INTO claims (
                        id, investigation_id, source_id, passage_id,
                        claim_text, category, extraction_method, extraction_confidence, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        c["id"], c["investigation_id"], c["source_id"], c["passage_id"],
                        c["claim_text"], c.get("category", "factual"), c["extraction_method"], c["extraction_confidence"], c["created_at"]
                    )
                )

            conn.commit()

        # Trigger Component 10 automatic orchestration across downstream components
        try:
            from backend.services.orchestrator_service import orchestrate_source_integration
            with get_db() as o_conn:
                orchestrate_source_integration(o_conn, investigation_id, source_id, trigger_workflow="DIRECT_SOURCE_INTEGRATION")
        except Exception as o_err:
            logger.warning(f"Automatic orchestration skipped for source {source_id}: {o_err}")

        return {"source_id": source_id, "status": "completed", "error": None}

    except Exception as e:
        error_msg = str(e)
        with get_db() as conn:
            conn.execute(
                """
                UPDATE sources SET
                    extraction_status = 'failed',
                    error_message = ?
                WHERE id = ?
                """,
                (error_msg, source_id)
            )
            conn.commit()
        return {"source_id": source_id, "status": "failed", "error": error_msg}


async def ingest_urls_task(investigation_id: str, urls: List[str]):
    """Background task to ingest a list of URLs and update investigation status."""
    for url in urls:
        if url.strip():
            await ingest_single_url(investigation_id, url.strip())

    # Update overall investigation status
    with get_db() as conn:
        conn.execute("UPDATE investigations SET status = 'ready' WHERE id = ?", (investigation_id,))
        conn.commit()


@router.post("/api/investigations/{investigation_id}/sources", response_model=List[SourceResponse])
async def add_sources_to_investigation(
    investigation_id: str,
    payload: SourceAddRequest
):
    """
    Ingests and processes one or more live web URLs into an existing investigation.
    Runs extraction synchronously and returns the populated source records.
    """
    # Verify investigation exists
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM investigations WHERE id = ?", (investigation_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail=f"Investigation '{investigation_id}' not found.")

    for url in payload.urls:
        if url.strip():
            await ingest_single_url(investigation_id, url.strip())

    # Return updated list of sources for this investigation
    from backend.routers.investigations import get_investigation_sources
    return await get_investigation_sources(investigation_id)


@router.post("/api/investigations/{investigation_id}/documents", response_model=List[SourceResponse])
async def upload_pdf_documents(
    investigation_id: str,
    files: List[UploadFile] = File(...)
):
    """
    Uploads and processes one or more PDF documents for an investigation.
    Preserves page numbers, checks for encryption, detects scanned/empty documents,
    and extracts atomic claims.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM investigations WHERE id = ?", (investigation_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail=f"Investigation '{investigation_id}' not found.")

    processed_sources = []

    for file in files:
        source_id = str(uuid.uuid4())
        retrieved_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        filename = file.filename or "uploaded_document.pdf"

        try:
            file_bytes = await file.read()
            doc_data = parse_pdf_document(file_bytes, filename)

            status = "warning" if doc_data["is_scanned"] else "completed"
            error_message = doc_data["warning"]

            # Classify freshness and determine document origin deterministically
            is_demo = any(marker in filename.lower() for marker in ["helios", "demo", "sample", "simulation", "test", "fixture"])
            source_origin = "DEMONSTRATION_DOCUMENT" if is_demo else "USER_PROVIDED_DOCUMENT"

            freshness = classify_source_freshness(
                doc_data.get("publication_date"),
                date_validation_status=doc_data.get("date_validation_status")
            )
            freshness_status = freshness["status"]
            freshness_explanation = freshness["explanation"]

            with get_db() as conn:
                conn.execute(
                    """
                    INSERT INTO sources (
                        id, investigation_id, source_type, original_url, title,
                        publisher, publication_date, source_modified_date, date_source,
                        date_extraction_method, date_confidence, date_validation_status,
                        freshness_status, freshness_explanation, source_origin, retrieved_at, content_hash,
                        extraction_status, extracted_text, error_message
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        source_id, investigation_id, "pdf", filename, doc_data["title"],
                        doc_data["publisher"], doc_data.get("publication_date"),
                        doc_data.get("source_modified_date"), doc_data.get("date_source"),
                        doc_data.get("date_extraction_method"), doc_data.get("date_confidence", 0.0),
                        doc_data.get("date_validation_status", "MISSING"),
                        freshness_status, freshness_explanation, source_origin, retrieved_at,
                        doc_data["content_hash"], status, doc_data["extracted_text"], error_message
                    )
                )

                # Segment each page into passages
                all_claims = []
                for page in doc_data["pages"][:10]:
                    page_passages = segment_into_passages(
                        full_text=page["text"],
                        source_id=source_id,
                        page_number=page["page_number"]
                    )

                    for p in page_passages:
                        conn.execute(
                            """
                            INSERT INTO passages (
                                id, source_id, passage_text, page_number,
                                paragraph_index, start_offset, end_offset, sha256_hash
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                p["id"], p["source_id"], p["passage_text"], p["page_number"],
                                p["paragraph_index"], p["start_offset"], p["end_offset"], p["sha256_hash"]
                            )
                        )

                        # Extract claims for passage up to 30 claims per document
                        if len(all_claims) < 30:
                            claims = await extract_claims_from_passage(
                                passage_text=p["passage_text"],
                                source_id=source_id,
                                passage_id=p["id"],
                                investigation_id=investigation_id
                            )
                            all_claims.extend(claims)

                for c in all_claims:
                    conn.execute(
                        """
                        INSERT INTO claims (
                            id, investigation_id, source_id, passage_id,
                            claim_text, category, extraction_method, extraction_confidence, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            c["id"], c["investigation_id"], c["source_id"], c["passage_id"],
                            c["claim_text"], c.get("category", "factual"), c["extraction_method"], c["extraction_confidence"], c["created_at"]
                        )
                    )

                conn.commit()

                # Trigger Component 10 automatic orchestration across downstream components
                try:
                    from backend.services.orchestrator_service import orchestrate_source_integration
                    with get_db() as o_conn:
                        orchestrate_source_integration(o_conn, investigation_id, source_id, trigger_workflow="DIRECT_SOURCE_INTEGRATION")
                except Exception as o_err:
                    logger.warning(f"Automatic orchestration skipped for PDF source {source_id}: {o_err}")

        except PDFParsingError as e:
            with get_db() as conn:
                conn.execute(
                    """
                    INSERT INTO sources (
                        id, investigation_id, source_type, original_url, title,
                        publisher, publication_date, retrieved_at, content_hash,
                        extraction_status, extracted_text, error_message
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        source_id, investigation_id, "pdf", filename, filename,
                        None, None, retrieved_at, None,
                        "failed", None, str(e)
                    )
                )
                conn.commit()

                # Trigger Component 10 automatic orchestration across downstream components
                try:
                    from backend.services.orchestrator_service import orchestrate_source_integration
                    with get_db() as o_conn:
                        orchestrate_source_integration(o_conn, investigation_id, source_id, trigger_workflow="DIRECT_SOURCE_INTEGRATION")
                except Exception as o_err:
                    logger.warning(f"Automatic orchestration skipped for PDF source {source_id}: {o_err}")
        except Exception as e:
            with get_db() as conn:
                conn.execute(
                    """
                    INSERT INTO sources (
                        id, investigation_id, source_type, original_url, title,
                        publisher, publication_date, retrieved_at, content_hash,
                        extraction_status, extracted_text, error_message
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        source_id, investigation_id, "pdf", filename, filename,
                        None, None, retrieved_at, None,
                        "failed", None, f"Unexpected error during PDF ingestion: {str(e)}"
                    )
                )
                conn.commit()

                # Trigger Component 10 automatic orchestration across downstream components
                try:
                    from backend.services.orchestrator_service import orchestrate_source_integration
                    with get_db() as o_conn:
                        orchestrate_source_integration(o_conn, investigation_id, source_id, trigger_workflow="DIRECT_SOURCE_INTEGRATION")
                except Exception as o_err:
                    logger.warning(f"Automatic orchestration skipped for PDF source {source_id}: {o_err}")

    from backend.routers.investigations import get_investigation_sources
    return await get_investigation_sources(investigation_id)


@router.get("/api/sources/{source_id}/passages", response_model=List[PassageResponse])
async def get_source_passages(source_id: str):
    """
    Returns all passages and provenance metadata (page number, character offsets, SHA-256)
    for a specific source.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM passages
            WHERE source_id = ?
            ORDER BY COALESCE(page_number, 0) ASC, paragraph_index ASC
        """, (source_id,))
        rows = cursor.fetchall()

        if not rows:
            # Check if source exists
            cursor.execute("SELECT id FROM sources WHERE id = ?", (source_id,))
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail=f"Source '{source_id}' not found.")

        return [
            PassageResponse(
                id=row["id"],
                source_id=row["source_id"],
                passage_text=row["passage_text"],
                page_number=row["page_number"],
                paragraph_index=row["paragraph_index"],
                start_offset=row["start_offset"],
                end_offset=row["end_offset"],
                sha256_hash=row["sha256_hash"],
            )
            for row in rows
        ]
