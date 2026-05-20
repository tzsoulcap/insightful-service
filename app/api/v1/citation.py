import asyncio
import logging
import os
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.dify_database import get_dify_db
from app.services.citation_service import (
    SEGMENT_QUERY,
    collection_name_for_dataset,
    get_page_from_weaviate,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["Citation"])


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
    file_name: str = row.file_name
    file_key: str = row.file_key

    # 2. Fetch page number from Weaviate
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

    # 3. Build PDF viewer URL
    pdf_url = str(request.url_for("view_pdf", file_key=file_key))

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
    storage_root = os.path.realpath(settings.DIFY_STORAGE_PATH)
    raw_path = os.path.join(settings.DIFY_STORAGE_PATH, file_key)
    resolved_path = os.path.realpath(raw_path)

    # logging.info("Dify storage root: %s", storage_root)
    # logging.info("Storage root is %s", storage_root)
    # logging.info("Raw file path is %s", raw_path)
    # logging.info("Resolved file path is %s", resolved_path)

    # Guard against path traversal
    if not resolved_path.startswith(storage_root + os.sep) and resolved_path != storage_root:
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
