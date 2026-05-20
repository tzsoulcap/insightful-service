import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_dify_service, get_user_id
from app.core.config import Settings, get_settings
from app.core.dify_database import get_dify_db
from app.schemas.conversation import (
    ConversationDetailResponse,
    ConversationsResponse,
    MessagesResponse,
    RenameConversationRequest,
)
from app.services.dify import DifyService
from app.services.enrichment_service import enrich_messages

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/conversations", tags=["Conversations"])

_GET_USER_CONVERSATION_IDS = text("""
    SELECT c.id
    FROM conversations c
    WHERE c.from_end_user_id = (
        SELECT id FROM end_users WHERE external_user_id = :user_id
    )
""")


@router.get("/messages", response_model=MessagesResponse)
async def get_messages(
    conversation_id: str,
    request: Request,
    user_id: Annotated[str, Depends(get_user_id)],
    service: Annotated[DifyService, Depends(get_dify_service)],
    session: Annotated[AsyncSession, Depends(get_dify_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    first_id: str | None = None,
    limit: int = 20,
) -> MessagesResponse:
    try:
        data = await service.get_messages(
            conversation_id=conversation_id,
            user=user_id,
            first_id=first_id,
            limit=max(1, min(limit, 100)),
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to retrieve messages from Dify",
        )

    # Batch enrich all retriever_resources with page_number, file_name, pdf_url
    await enrich_messages(
        data=data,
        session=session,
        settings=settings,
        pdf_url_builder=lambda fk: str(request.url_for("view_pdf", file_key=fk)),
    )

    return MessagesResponse(**data)


@router.get("", response_model=ConversationsResponse)
async def get_conversations(
    user_id: Annotated[str, Depends(get_user_id)],
    service: Annotated[DifyService, Depends(get_dify_service)],
    last_id: str | None = None,
    limit: int = 20,
    sort_by: Literal["created_at", "-created_at", "updated_at", "-updated_at"] = "-updated_at",
) -> ConversationsResponse:
    # print(f"Fetching conversations for user {user_id} with last_id={last_id}, limit={limit}, sort_by={sort_by}...")
    try:
        data = await service.get_conversations(
            user=user_id,
            last_id=last_id,
            limit=max(1, min(limit, 100)),
            sort_by=sort_by,
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to retrieve conversations from Dify",
        )
    return ConversationsResponse(**data)


@router.delete("", status_code=status.HTTP_200_OK)
async def delete_all_conversations(
    user_id: Annotated[str, Depends(get_user_id)],
    service: Annotated[DifyService, Depends(get_dify_service)],
    session: Annotated[AsyncSession, Depends(get_dify_db)],
) -> dict:
    # 1. Fetch all conversation IDs from Dify's Postgres
    try:
        result = await session.execute(_GET_USER_CONVERSATION_IDS, {"user_id": user_id})
        conversation_ids = [str(row.id) for row in result.all()]
    except Exception as exc:
        logger.error("DB error fetching conversations for user %s: %s", user_id, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to fetch conversations from database",
        )

    if not conversation_ids:
        return {"deleted": 0, "failed": 0, "conversation_ids": []}

    # 2. Delete each conversation via Dify API
    deleted, failed = [], []
    for conv_id in conversation_ids:
        try:
            await service.delete_conversation(conversation_id=conv_id, user=user_id)
            deleted.append(conv_id)
        except Exception as exc:
            logger.warning("Failed to delete conversation %s: %s", conv_id, exc)
            failed.append(conv_id)

    return {
        "deleted": len(deleted),
        "failed": len(failed),
        "failed_ids": failed,
    }


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: str,
    user_id: Annotated[str, Depends(get_user_id)],
    service: Annotated[DifyService, Depends(get_dify_service)],
) -> Response:
    try:
        await service.delete_conversation(conversation_id=conversation_id, user=user_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to delete conversation from Dify",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{conversation_id}/name", response_model=ConversationDetailResponse)
async def rename_conversation(
    conversation_id: str,
    body: RenameConversationRequest,
    user_id: Annotated[str, Depends(get_user_id)],
    service: Annotated[DifyService, Depends(get_dify_service)],
) -> ConversationDetailResponse:
    try:
        data = await service.rename_conversation(
            conversation_id=conversation_id,
            user=user_id,
            name=body.name,
            auto_generate=body.auto_generate,
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to rename conversation in Dify",
        )
    return ConversationDetailResponse(**data)
