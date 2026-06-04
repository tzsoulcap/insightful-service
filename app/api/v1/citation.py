import asyncio
import logging
import os
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.database import async_session as _sqlite_session
from app.core.dify_database import get_dify_db
from app.services.citation_service import (
    SEGMENT_QUERY,
    collection_name_for_dataset,
    get_page_from_weaviate,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Citation"])

_PDF_BY_DOC_ID = text("""
    SELECT filename, original_file_path
    FROM process_pdf
    WHERE dify_document_id = :doc_id
    LIMIT 1
""")


@router.get("/resolve-citation/{segment_id}")
async def resolve_citation(
    segment_id: str,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_dify_db)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    # 1. Query Postgres: segment → document → upload_file
    try:
        result = await session.execute(SEGMENT_QUERY, {"segment_id": segment_id})
    except SQLAlchemyError as exc:
        logger.error("DB error in resolve_citation (segment_id=%s): %s", segment_id, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database error: {exc}",
        )

    row = result.first()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Segment '{segment_id}' not found",
        )

    dataset_id: str = str(row.dataset_id)
    index_node_id: str = str(row.index_node_id)
    document_id: str = str(row.document_id)

    # 2. Query SQLite for file info via dify_document_id
    file_name = ""
    file_key = ""
    try:
        async with _sqlite_session() as sqlite_session:
            pdf_result = await sqlite_session.execute(
                _PDF_BY_DOC_ID, {"doc_id": document_id}
            )
            pdf_row = pdf_result.first()
            if pdf_row:
                file_name = pdf_row.filename
                pdf_root = os.path.realpath(settings.PDF_STORAGE_PATH)
                abs_path = os.path.realpath(pdf_row.original_file_path)
                file_key = os.path.relpath(abs_path, pdf_root)
    except Exception as exc:
        logger.warning("SQLite file lookup failed (document_id=%s): %s", document_id, exc)

    # 3. Fetch page number from Weaviate
    collection_name = collection_name_for_dataset(dataset_id)
    try:
        page_number = await asyncio.to_thread(
            get_page_from_weaviate, settings, collection_name, index_node_id
        )
    except Exception as exc:
        logger.warning(
            "Weaviate lookup failed (collection=%s, index_node_id=%s): %s",
            collection_name, index_node_id, exc,
        )
        page_number = None

    # 4. Build PDF viewer URL
    pdf_url = str(request.url_for("view_pdf", file_key=file_key)) if file_key else None

    return {
        "segment_id": segment_id,
        "page_number": page_number,
        "file_name": file_name,
        "pdf_url": pdf_url,
    }


@router.get("/pdf/view/{file_key:path}", name="view_pdf")
async def view_pdf(
    file_key: str,
    settings: Annotated[Settings, Depends(get_settings)],
) -> FileResponse:
    # Resolve against PDF_STORAGE_PATH (our service) first, then DIFY_STORAGE_PATH (legacy)
    resolved_path: str | None = None
    for storage_base in [settings.PDF_STORAGE_PATH, settings.DIFY_STORAGE_PATH]:
        storage_root = os.path.realpath(storage_base)
        candidate = os.path.realpath(os.path.join(storage_base, file_key))
        within_root = candidate.startswith(storage_root + os.sep) or candidate == storage_root
        if within_root:
            resolved_path = candidate
            break

    if resolved_path is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    if not os.path.isfile(resolved_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PDF file not found on disk",
        )

    return FileResponse(
        path=resolved_path,
        media_type="application/pdf",
        headers={"Content-Disposition": "inline"},
    )
