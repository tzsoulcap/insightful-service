from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.batch import Batch, ProcessPdf


async def create_batch(
    session: AsyncSession,
    *,
    dataset_id: str,
    dataset_name: str,
    created_by: str,
    total_files: int,
    scheduled_at: datetime | None = None,
) -> Batch:
    batch = Batch(
        dataset_id=dataset_id,
        dataset_name=dataset_name,
        created_by=created_by,
        total_files=total_files,
        scheduled_at=scheduled_at,
    )
    session.add(batch)
    await session.flush()
    return batch


async def create_process_pdf(
    session: AsyncSession,
    *,
    batch_id: str,
    filename: str,
    original_file_path: str,
) -> ProcessPdf:
    item = ProcessPdf(
        batch_id=batch_id,
        filename=filename,
        original_file_path=original_file_path,
    )
    session.add(item)
    await session.flush()
    return item


async def update_process_pdf(
    session: AsyncSession,
    item: ProcessPdf,
    *,
    status: str | None = None,
    current_step: str | None = ...,  # type: ignore[assignment]
    pdf_type: str | None = ...,  # type: ignore[assignment]
    error_msg: str | None = ...,  # type: ignore[assignment]
    dify_document_id: str | None = ...,  # type: ignore[assignment]
    dify_batch: str | None = ...,  # type: ignore[assignment]
) -> None:
    if status is not None:
        item.status = status
    if current_step is not ...:
        item.current_step = current_step
    if pdf_type is not ...:
        item.pdf_type = pdf_type
    if error_msg is not ...:
        item.error_msg = error_msg
    if dify_document_id is not ...:
        item.dify_document_id = dify_document_id
    if dify_batch is not ...:
        item.dify_batch = dify_batch
    item.updated_at = datetime.now(timezone.utc)
    await session.flush()


async def update_batch_status(
    session: AsyncSession,
    batch: Batch,
    *,
    status: str,
    started_at: datetime | None = ...,  # type: ignore[assignment]
    completed_at: datetime | None = ...,  # type: ignore[assignment]
) -> None:
    batch.status = status
    if started_at is not ...:
        batch.started_at = started_at
    if completed_at is not ...:
        batch.completed_at = completed_at
    batch.updated_at = datetime.now(timezone.utc)
    await session.flush()


async def get_batch(session: AsyncSession, batch_id: str) -> Batch | None:
    result = await session.execute(
        select(Batch).where(Batch.id == batch_id).options(selectinload(Batch.files))
    )
    return result.scalar_one_or_none()


async def get_process_pdf(
    session: AsyncSession, file_id: str, batch_id: str | None = None
) -> ProcessPdf | None:
    conditions = [ProcessPdf.id == file_id]
    if batch_id is not None:
        conditions.append(ProcessPdf.batch_id == batch_id)
    result = await session.execute(select(ProcessPdf).where(*conditions))
    return result.scalar_one_or_none()


async def reset_process_pdf_for_retry(session: AsyncSession, item: ProcessPdf) -> None:
    """Reset a failed file back to pending so it can be re-processed."""
    item.status = "pending"
    item.current_step = None
    item.error_msg = None
    item.retry_count = (item.retry_count or 0) + 1
    item.updated_at = datetime.now(timezone.utc)
    await session.flush()


async def list_batches(
    session: AsyncSession,
    page: int = 1,
    limit: int = 20,
    status_filter: str | None = None,
) -> tuple[list[Batch], int]:
    conditions = []
    if status_filter:
        conditions.append(Batch.status == status_filter)

    count_q = select(func.count()).select_from(Batch)
    if conditions:
        count_q = count_q.where(*conditions)
    total: int = (await session.execute(count_q)).scalar_one()

    data_q = select(Batch)
    if conditions:
        data_q = data_q.where(*conditions)
    data_q = data_q.order_by(Batch.created_at.desc()).offset((page - 1) * limit).limit(limit)
    batches = list((await session.execute(data_q)).scalars().all())

    return batches, total


async def get_pending_batches(session: AsyncSession) -> list[Batch]:
    result = await session.execute(
        select(Batch).where(Batch.status.in_(["pending", "processing"]))
    )
    return list(result.scalars().all())


_BATCH_SORT_FIELDS: dict[str, object] = {
    "created_at": Batch.created_at,
    "updated_at": Batch.updated_at,
    "scheduled_at": Batch.scheduled_at,
    "started_at": Batch.started_at,
    "completed_at": Batch.completed_at,
    "status": Batch.status,
    "total_files": Batch.total_files,
}


async def list_batches_by_dataset(
    session: AsyncSession,
    dataset_id: str,
    page: int = 1,
    limit: int = 20,
    sort: str = "created_at:desc",
    status_filter: str | None = None,
) -> tuple[list[Batch], int]:
    conditions = [Batch.dataset_id == dataset_id]
    if status_filter:
        conditions.append(Batch.status == status_filter)

    count_q = select(func.count()).select_from(Batch).where(*conditions)
    total: int = (await session.execute(count_q)).scalar_one()

    # Parse sort param: "column:asc" or "column:desc"
    sort_parts = sort.split(":")
    sort_col_name = sort_parts[0] if sort_parts else "created_at"
    sort_direction = sort_parts[1].lower() if len(sort_parts) > 1 else "desc"
    sort_col = _BATCH_SORT_FIELDS.get(sort_col_name, Batch.created_at)
    order_expr = sort_col.asc() if sort_direction == "asc" else sort_col.desc()  # type: ignore[union-attr]

    data_q = (
        select(Batch)
        .where(*conditions)
        .options(selectinload(Batch.files))
        .order_by(order_expr)
        .offset((page - 1) * limit)
        .limit(limit)
    )
    batches = list((await session.execute(data_q)).scalars().all())
    return batches, total


async def get_process_pdfs_by_batch(session: AsyncSession, batch_id: str) -> list[ProcessPdf]:
    result = await session.execute(
        select(ProcessPdf)
        .where(ProcessPdf.batch_id == batch_id)
        .order_by(ProcessPdf.created_at.asc())
    )
    return list(result.scalars().all())
