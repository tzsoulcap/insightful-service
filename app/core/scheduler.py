import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.services.batch_worker import run_batch, run_single_file

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


def schedule_batch(batch_id: str, run_date: datetime | None = None) -> None:
    """Schedule a batch to run at the given time, or immediately if None."""
    if run_date is None:
        run_date = datetime.now(timezone.utc)
    scheduler.add_job(
        run_batch,
        trigger="date",
        run_date=run_date,
        args=[batch_id],
        id=f"batch-{batch_id}",
        replace_existing=True,
        max_instances=1,
    )
    logger.info("Scheduled batch %s at %s", batch_id, run_date)


def schedule_single_file(batch_id: str, file_id: str) -> None:
    """Schedule an immediate retry for a single file."""
    scheduler.add_job(
        run_single_file,
        trigger="date",
        run_date=datetime.now(timezone.utc),
        args=[batch_id, file_id],
        id=f"retry-{file_id}",
        replace_existing=True,
        max_instances=1,
    )
    logger.info("Scheduled retry for file %s in batch %s", file_id, batch_id)


async def recover_pending_batches() -> None:
    """Re-schedule batches that were pending or processing when the server stopped."""
    from app.core.database import async_session
    from app.services.batch_service import get_pending_batches

    async with async_session() as session:
        batches = await get_pending_batches(session)
        for batch in batches:
            if batch.status == "processing":
                batch.status = "pending"
                batch.updated_at = datetime.now(timezone.utc)
                await session.commit()
            run_date = batch.scheduled_at or datetime.now(timezone.utc)
            if run_date < datetime.now(timezone.utc):
                run_date = datetime.now(timezone.utc)
            schedule_batch(batch.id, run_date)
    logger.info("Recovery complete — re-scheduled %d batch(es)", len(batches))
