import os
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import get_current_user
from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.core.scheduler import schedule_batch, schedule_single_file
from app.models.user import User
from app.schemas.batch import (
    BatchByDatasetResponse,
    BatchListResponse,
    BatchResponse,
    BatchSummaryResponse,
    BatchTrackItem,
    ProcessPdfItem,
    ProcessPdfListResponse,
)
from app.services.batch_service import (
    create_batch,
    create_process_pdf,
    get_batch,
    get_process_pdf,
    get_process_pdfs_by_batch,
    list_batches,
    list_batches_by_dataset,
    reset_process_pdf_for_retry,
)
from app.models.batch import Batch

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
    storage_dir = os.path.join(settings.PDF_STORAGE_PATH, dataset_id)
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


# ── GET /batches/by-dataset/{dataset_id} ─────────────────────────────────────

_FAILED_STATUSES = {"error", "upload_failed"}
_TERMINAL_STATUSES = {"error", "uploaded", "pending", "upload_failed"}


def _build_track_item(batch: Batch) -> BatchTrackItem:
    files = batch.files
    success_count = sum(1 for f in files if f.status == "uploaded")
    failed_count = sum(1 for f in files if f.status in _FAILED_STATUSES)
    pending_count = sum(1 for f in files if f.status == "pending")
    processing_count = sum(1 for f in files if f.status not in _TERMINAL_STATUSES)
    return BatchTrackItem(
        id=batch.id,
        status=batch.status,
        created_by=batch.created_by,
        total_files=batch.total_files,
        success_count=success_count,
        failed_count=failed_count,
        processing_count=processing_count,
        pending_count=pending_count,
        scheduled_at=batch.scheduled_at,
        started_at=batch.started_at,
        completed_at=batch.completed_at,
        created_at=batch.created_at,
        updated_at=batch.updated_at,
    )


@router.get("/by-dataset/{dataset_id}", response_model=BatchByDatasetResponse)
async def list_batches_by_dataset_endpoint(
    dataset_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    page: int = 1,
    limit: int = 20,
    sort: str = "created_at:desc",
    status: str | None = None,
) -> BatchByDatasetResponse:
    clamped_limit = max(1, min(limit, 100))
    batches, total = await list_batches_by_dataset(
        session, dataset_id=dataset_id, page=page, limit=clamped_limit, sort=sort, status_filter=status
    )
    dataset_name = batches[0].dataset_name if batches else ""
    return BatchByDatasetResponse(
        dataset_id=dataset_id,
        dataset_name=dataset_name,
        data=[_build_track_item(b) for b in batches],
        has_more=(page * clamped_limit) < total,
        limit=clamped_limit,
        total=total,
        page=page,
    )


# ── GET /batches/{batch_id}/files ─────────────────────────────────────────────

@router.get("/{batch_id}/files", response_model=ProcessPdfListResponse)
async def list_process_pdfs_endpoint(
    batch_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ProcessPdfListResponse:
    batch = await get_batch(session, batch_id)
    if batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")
    files = await get_process_pdfs_by_batch(session, batch_id)
    return ProcessPdfListResponse(
        batch_id=batch_id,
        data=[ProcessPdfItem.model_validate(f) for f in files],
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

# ── POST /batches/{batch_id}/files/{file_id}/retry ────────────────────────────

_RETRYABLE_STATUSES = {"error", "upload_failed"}


@router.post("/{batch_id}/files/{file_id}/retry", response_model=ProcessPdfItem, status_code=status.HTTP_202_ACCEPTED)
async def retry_process_pdf_endpoint(
    batch_id: str,
    file_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ProcessPdfItem:
    batch = await get_batch(session, batch_id)
    if batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")

    item = await get_process_pdf(session, file_id, batch_id=batch_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found in this batch")

    if item.status not in _RETRYABLE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"File status '{item.status}' is not retryable (must be one of: {', '.join(sorted(_RETRYABLE_STATUSES))})",
        )

    await reset_process_pdf_for_retry(session, item)
    await session.commit()
    await session.refresh(item)

    schedule_single_file(batch_id, file_id)

    return ProcessPdfItem.model_validate(item)