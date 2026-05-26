import os
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import get_current_user
from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.core.scheduler import schedule_batch
from app.models.user import User
from app.schemas.batch import BatchListResponse, BatchResponse, BatchSummaryResponse
from app.services.batch_service import (
    create_batch,
    create_process_pdf,
    get_batch,
    list_batches,
)

router = APIRouter(prefix="/batches", tags=["Batches"])

_MAX_FILES = 10
_MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


# ── POST /batches ─────────────────────────────────────────────────────────────

@router.post("", response_model=BatchResponse, status_code=status.HTTP_201_CREATED)
async def create_batch_endpoint(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    files: list[UploadFile] = File(...),
    dataset_id: str = Form(...),
    dataset_name: str = Form(...),
    scheduled_at: datetime | None = Form(None),
) -> BatchResponse:
    # ── Validate file count ──
    if len(files) > _MAX_FILES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Maximum {_MAX_FILES} files allowed",
        )
    if len(files) == 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one file is required",
        )

    # ── Validate each file ──
    for f in files:
        if not f.filename or not f.filename.lower().endswith(".pdf"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"File '{f.filename}' is not a PDF",
            )
        content = await f.read()
        if len(content) > _MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"File '{f.filename}' exceeds 10 MB limit",
            )
        await f.seek(0)

    # ── Create batch record ──
    batch = await create_batch(
        session,
        dataset_id=dataset_id,
        dataset_name=dataset_name,
        created_by=current_user.id,
        total_files=len(files),
        scheduled_at=scheduled_at,
    )

    # ── Save files to disk + create process_pdf records ──
    storage_dir = os.path.join(settings.PDF_STORAGE_PATH, dataset_name)
    os.makedirs(storage_dir, exist_ok=True)

    for f in files:
        item = await create_process_pdf(
            session,
            batch_id=batch.id,
            filename=f.filename or "unknown.pdf",
            original_file_path="",  # placeholder, updated below
        )
        # Write file using process_pdf.id as filename to avoid collisions
        file_path = os.path.join(storage_dir, f"{item.id}.pdf")
        content = await f.read()
        with open(file_path, "wb") as out:
            out.write(content)
        item.original_file_path = file_path
        item.updated_at = batch.created_at  # keep consistent

    await session.commit()
    await session.refresh(batch)

    # ── Schedule background task ──
    schedule_batch(batch.id, scheduled_at)

    return BatchResponse.model_validate(batch)


# ── GET /batches ──────────────────────────────────────────────────────────────

@router.get("", response_model=BatchListResponse)
async def list_batches_endpoint(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    page: int = 1,
    limit: int = 20,
    status: str | None = None,
) -> BatchListResponse:
    clamped_limit = max(1, min(limit, 100))
    batches, total = await list_batches(
        session, page=page, limit=clamped_limit, status_filter=status
    )
    return BatchListResponse(
        data=[BatchSummaryResponse.model_validate(b) for b in batches],
        total=total,
        page=page,
        limit=clamped_limit,
        has_more=(page * clamped_limit) < total,
    )


# ── GET /batches/{batch_id} ──────────────────────────────────────────────────

@router.get("/{batch_id}", response_model=BatchResponse)
async def get_batch_endpoint(
    batch_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> BatchResponse:
    batch = await get_batch(session, batch_id)
    if batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")
    return BatchResponse.model_validate(batch)
