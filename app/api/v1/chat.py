from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.deps import get_dify_service, get_user_id
from app.schemas.chat import ChatRequest
from app.services.dify import DifyService

router = APIRouter(tags=["Chat"])


@router.post("/chat")
async def chat(
    body: ChatRequest,
    user_id: Annotated[str, Depends(get_user_id)],
    service: Annotated[DifyService, Depends(get_dify_service)],
) -> StreamingResponse:
    dify_user = body.user or user_id

    event_stream = service.chat_stream(
        query=body.query,
        user=dify_user,
        conversation_id=body.conversation_id,
        inputs=body.inputs,
        auto_generate_name=body.auto_generate_name,
    )

    return StreamingResponse(event_stream, media_type="text/event-stream")
