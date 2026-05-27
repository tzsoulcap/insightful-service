import logging
import os
import shutil

from sqlalchemy import text

from app.core.config import Settings
from app.core.dify_database import dify_async_session

logger = logging.getLogger(__name__)


async def cleanup_dify_images(
    dataset_id: str,
    settings: Settings,
    tenant_id: str | None = None,
) -> dict:
    """
    Clean up Dify image records and storage files for a dataset.

    - Deletes rows in segment_attachment_bindings for dataset_id
    - Deletes non-PDF rows in upload_files
    - Deletes all files under {DIFY_STORAGE_PATH}/image_files/{tenant_id}/

    If tenant_id is not provided, it is resolved from the Dify `datasets` table.
    Returns a summary dict. Errors during file deletion are logged but do not raise.
    """
    async with dify_async_session() as session:
        # ── Resolve tenant_id if not provided ────────────────────────────────
        if tenant_id is None:
            row = (await session.execute(
                text("SELECT tenant_id FROM datasets WHERE id = :dataset_id"),
                {"dataset_id": dataset_id},
            )).first()
            if row is None:
                logger.warning(
                    "Dataset %s not found in Dify DB — skipping image cleanup", dataset_id
                )
                return {
                    "dataset_id": dataset_id,
                    "tenant_id": None,
                    "deleted_db_segment_attachments": 0,
                    "deleted_db_upload_files": 0,
                    "deleted_files": 0,
                    "image_dir": None,
                    "skipped": True,
                }
            tenant_id = str(row[0])

        # ── DB: delete segment_attachment_bindings ────────────────────────────
        result_sab = await session.execute(
            text("DELETE FROM segment_attachment_bindings WHERE dataset_id = :dataset_id"),
            {"dataset_id": dataset_id},
        )

        # ── DB: delete non-PDF upload_files ───────────────────────────────────
        result_uf = await session.execute(
            text("DELETE FROM upload_files WHERE extension <> 'pdf'"),
        )

        await session.commit()

    deleted_sab: int = result_sab.rowcount  # type: ignore[assignment]
    deleted_uf: int = result_uf.rowcount  # type: ignore[assignment]

    # ── File system: delete image files ──────────────────────────────────────
    image_dir = os.path.join(settings.DIFY_STORAGE_PATH, "image_files", tenant_id)
    deleted_files = 0

    if os.path.isdir(image_dir):
        for entry in os.scandir(image_dir):
            try:
                if entry.is_file() or entry.is_symlink():
                    os.remove(entry.path)
                    deleted_files += 1
                elif entry.is_dir():
                    shutil.rmtree(entry.path)
                    deleted_files += 1
            except OSError as exc:
                logger.error("Failed to delete '%s': %s", entry.path, exc)
    else:
        logger.warning("Image dir not found, skipping file deletion: %s", image_dir)

    logger.info(
        "Dify image cleanup: dataset=%s tenant=%s sab=%d uf=%d files=%d",
        dataset_id, tenant_id, deleted_sab, deleted_uf, deleted_files,
    )

    return {
        "dataset_id": dataset_id,
        "tenant_id": tenant_id,
        "deleted_db_segment_attachments": deleted_sab,
        "deleted_db_upload_files": deleted_uf,
        "deleted_files": deleted_files,
        "image_dir": image_dir,
        "skipped": False,
    }
