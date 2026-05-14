from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter(prefix="/version", tags=["Version"])


@router.get("", summary="Get current API version")
async def get_version() -> dict:
    settings = get_settings()
    return {"version": settings.APP_VERSION}
