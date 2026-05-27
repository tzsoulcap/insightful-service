import os
import shutil
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.api.v1.auth import get_current_user
from app.core.config import Settings, get_settings
from app.models.user import User
from app.services.dify_cleanup import cleanup_dify_images

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
    settings: Annotated[Settings, Depends(get_settings)],
) -> DeleteDifyImagesResponse:
    _require_admin(current_user)

    result = await cleanup_dify_images(dataset_id, settings, tenant_id=tenant_id)

    return DeleteDifyImagesResponse(
        dataset_id=result["dataset_id"],
        tenant_id=result["tenant_id"] or tenant_id,
        deleted_db_segment_attachments=result["deleted_db_segment_attachments"],
        deleted_db_upload_files=result["deleted_db_upload_files"],
        deleted_files=result["deleted_files"],
        image_dir=result["image_dir"] or "",
    )
