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
