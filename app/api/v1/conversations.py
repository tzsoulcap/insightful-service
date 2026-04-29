import asyncio
import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
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
from app.services.citation_service import (
    SEGMENT_QUERY,
    collection_name_for_dataset,
    get_page_from_weaviate,
)
from app.services.dify import DifyService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/conversations", tags=["Conversations"])


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

    # Enrich each retriever_resource with page_number, file_name, pdf_url
    for message in data.get("data", []):
        for resource in message.get("retriever_resources", []):
            segment_id = resource.get("segment_id")
            if not segment_id:
                continue

            try:
                result = await session.execute(SEGMENT_QUERY, {"segment_id": segment_id})
                row = result.first()
            except Exception as exc:
                logger.warning("DB lookup failed for segment %s: %s", segment_id, exc)
                continue

            if row is None:
                continue

            file_key: str = row.file_key
            col_name = collection_name_for_dataset(str(row.dataset_id))

            try:
                page_number = await asyncio.to_thread(
                    get_page_from_weaviate, settings, col_name, str(row.index_node_id)
                )
            except Exception as exc:
                logger.warning(
                    "Weaviate lookup failed for segment %s: %s", segment_id, exc
                )
                page_number = None

            resource["enriched_metadata"] = {
                "page_number": page_number,
                "file_name": row.file_name,
                "pdf_url": str(request.url_for("view_pdf", file_key=file_key)),
            }

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
