import mimetypes
import os
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.dify_database import get_dify_db

router = APIRouter(tags=["Image Proxy"])


@router.get("/image-proxy/{file_id}")
async def image_proxy(
    file_id: str,
    session: Annotated[AsyncSession, Depends(get_dify_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> FileResponse:
    # 1. Query Dify Postgres for file metadata
    try:
        result = await session.execute(
            text("SELECT key, extension FROM upload_files WHERE id = :file_id"),
            {"file_id": file_id},
        )
    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection error",
        )

    row = result.first()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File with id '{file_id}' not found",
        )

    key: str = row.key
    extension: str = row.extension

    # 2. Construct full path and guard against path traversal
    storage_root = os.path.realpath(settings.DIFY_STORAGE_PATH)
    raw_path = os.path.join(settings.DIFY_STORAGE_PATH, key)
    resolved_path = os.path.realpath(raw_path)

    if not resolved_path.startswith(storage_root + os.sep) and resolved_path != storage_root:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    # 3. Verify file exists on disk
    if not os.path.isfile(resolved_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found on disk",
        )

    # 4. Determine media type from extension (.jpg, .png, etc.)
    dot_ext = extension if extension.startswith(".") else f".{extension}"
    media_type, _ = mimetypes.guess_type(f"file{dot_ext}")
    if media_type is None:
        media_type = "application/octet-stream"

    return FileResponse(path=resolved_path, media_type=media_type)
