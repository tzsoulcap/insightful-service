import json
import logging
import uuid
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_dify_service, get_retrieval_service
from app.api.v1.auth import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.repositories.knowledge_base import KnowledgeBaseRepository
from app.schemas.chat import ChatRequest
from app.schemas.retrieval import AllowedKnowledgeBase, NormalizedChunk
from app.services.citation_service import CitationService
from app.services.dify import DifyService
from app.services.retrieval_service import RetrievalService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Chat"])


# ── Synthetic SSE stream for early-exit cases ─────────────────────────────────

async def _no_access_stream() -> AsyncGenerator[str, None]:
    event = {
        "event": "message",
        "answer": "ยังไม่พบคลังความรู้ที่คุณมีสิทธิ์เข้าถึง",
        "conversation_id": None,
        "message_id": None,
    }
    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
    end_event = {"event": "message_end", "id": None, "conversation_id": None, "metadata": {}}
    yield f"data: {json.dumps(end_event)}\n\n"
    citation_event = {
        "event": "message_citation",
        "conversation_id": None,
        "message_id": None,
        "citations": [],
    }
    yield f"data: {json.dumps(citation_event)}\n\n"


# ── RAG streaming wrapper ─────────────────────────────────────────────────────

async def _rag_chat_stream(
    dify_service: DifyService,
    query: str,
    user: str,
    conversation_id: str | None,
    inputs: dict,
    auto_generate_name: bool,
    selected_chunks: list[NormalizedChunk],
    db: AsyncSession,
    user_id: uuid.UUID,
) -> AsyncGenerator[str, None]:
    final_conversation_id: str | None = None
    final_message_id: str | None = None

    async for line in dify_service.chat_stream(
        query=query,
        user=user,
        conversation_id=conversation_id,
        inputs=inputs,
        auto_generate_name=auto_generate_name,
    ):
        yield line
        # Intercept message_end to capture IDs for citations
        if line.startswith("data:"):
            try:
                data = json.loads(line[5:].strip())
                if data.get("event") == "message_end":
                    final_conversation_id = data.get("conversation_id")
                    final_message_id = data.get("id")
            except (json.JSONDecodeError, AttributeError):
                pass

    logger.info(
        "Chat stream ended: conversation_id=%s message_id=%s selected_chunks=%d",
        final_conversation_id,
        final_message_id,
        len(selected_chunks),
    )

    # Save citations if we have a valid message_id
    saved_citations: list[dict] = []
    if final_message_id and final_conversation_id and selected_chunks:
        citation_service = CitationService(db)
        saved = await citation_service.save_message_citations(
            dify_conversation_id=final_conversation_id,
            dify_message_id=final_message_id,
            user_id=user_id,
            selected_chunks=selected_chunks,
        )
        saved_citations = [
            {
                "position": c.position,
                "dify_dataset_id": c.dify_dataset_id,
                "dify_dataset_name": c.dify_dataset_name,
                "dify_document_id": c.dify_document_id,
                "dify_document_name": c.dify_document_name,
                "dify_segment_id": c.dify_segment_id,
                "segment_position": c.segment_position,
                "score": c.score,
                "file_name": c.file_name,
                "file_path": c.file_path,
                "page_no": c.page_no,
                "content": c.content,
            }
            for c in saved
        ]

    # Emit citation event
    citation_event = {
        "event": "message_citation",
        "conversation_id": final_conversation_id,
        "message_id": final_message_id,
        "citations": saved_citations,
    }
    yield f"data: {json.dumps(citation_event, ensure_ascii=False)}\n\n"


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.post("/chat")
async def chat(
    body: ChatRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    retrieval_service: Annotated[RetrievalService, Depends(get_retrieval_service)],
    dify_service: Annotated[DifyService, Depends(get_dify_service)],
) -> StreamingResponse:
    # 1. Resolve user's allowed knowledge bases
    kb_repo = KnowledgeBaseRepository(db)
    rows = await kb_repo.get_allowed_knowledge_bases(current_user.id)
    allowed_kbs = [
        AllowedKnowledgeBase(
            knowledge_id=r[0],
            dify_dataset_id=r[1],
            dify_dataset_name=r[2],
        )
        for r in rows
    ]

    logger.info(
        "Chat request: user_id=%s allowed_datasets=%d query_len=%d",
        current_user.id,
        len(allowed_kbs),
        len(body.query),
    )

    if not allowed_kbs:
        return StreamingResponse(
            _no_access_stream(), media_type="text/event-stream"
        )

    # 2. Retrieve chunks from allowed datasets
    selected_chunks, retrieved_context = await retrieval_service.retrieve_allowed_context(
        allowed_kbs, body.query
    )

    logger.info(
        "Retrieval done: selected_chunks=%d context_len=%d",
        len(selected_chunks),
        len(retrieved_context),
    )

    # 3. Build Dify inputs — inject retrieved_context
    inputs: dict = dict(body.inputs or {})
    inputs["retrieved_context"] = retrieved_context

    # 4. Stream from Dify Chatflow
    dify_user = str(current_user.id)

    event_stream = _rag_chat_stream(
        dify_service=dify_service,
        query=body.query,
        user=dify_user,
        conversation_id=body.conversation_id,
        inputs=inputs,
        auto_generate_name=body.auto_generate_name,
        selected_chunks=selected_chunks,
        db=db,
        user_id=current_user.id,
    )

    return StreamingResponse(event_stream, media_type="text/event-stream")
