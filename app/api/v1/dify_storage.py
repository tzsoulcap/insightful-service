import os
import shutil
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import get_current_user
from app.core.config import Settings, get_settings
from app.core.dify_database import get_dify_db
from app.models.user import User

router = APIRouter(prefix="/dify-images", tags=["Dify Storage"])


class DeleteDifyImagesResponse(BaseModel):
    dataset_id: str
    tenant_id: str
    deleted_db_segment_attachments: int
    deleted_db_upload_files: int
    deleted_files: int
    image_dir: str


def _require_admin(current_user: User) -> None:
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )


# ── DELETE /dify-images ───────────────────────────────────────────────────────

@router.delete("", response_model=DeleteDifyImagesResponse)
async def delete_dify_images(
    tenant_id: str,
    dataset_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    dify_session: Annotated[AsyncSession, Depends(get_dify_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> DeleteDifyImagesResponse:
    _require_admin(current_user)

    # ── 1. Delete segment_attachment_bindings ─────────────────────────────────
    result_sab = await dify_session.execute(
        text("DELETE FROM segment_attachment_bindings WHERE dataset_id = :dataset_id"),
        {"dataset_id": dataset_id},
    )
    deleted_sab: int = result_sab.rowcount  # type: ignore[assignment]

    # ── 2. Delete upload_files (non-PDF) ──────────────────────────────────────
    result_uf = await dify_session.execute(
        text("DELETE FROM upload_files WHERE extension <> 'pdf'"),
    )
    deleted_uf: int = result_uf.rowcount  # type: ignore[assignment]

    await dify_session.commit()

    # ── 3. Delete files from storage volume ───────────────────────────────────
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
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to delete '{entry.path}': {exc}",
                )

    return DeleteDifyImagesResponse(
        dataset_id=dataset_id,
        tenant_id=tenant_id,
        deleted_db_segment_attachments=deleted_sab,
        deleted_db_upload_files=deleted_uf,
        deleted_files=deleted_files,
        image_dir=image_dir,
    )
