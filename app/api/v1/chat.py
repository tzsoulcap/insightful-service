from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from app.api.deps import get_dify_service, get_repository, get_user_id
from app.repositories.user_permission import UserPermissionRepository
from app.schemas.chat import ChatRequest
from app.services.dify import DifyService

router = APIRouter(tags=["Chat"])


@router.post("/chat")
async def chat(
    body: ChatRequest,
    user_id: Annotated[str, Depends(get_user_id)],
    repo: Annotated[UserPermissionRepository, Depends(get_repository)],
    service: Annotated[DifyService, Depends(get_dify_service)],
) -> StreamingResponse:
    # 1. Lookup permitted dataset_ids for this user
    # print(f"Looking up dataset permissions for user {user_id}...")
    dataset_ids = await repo.get_dataset_ids(user_id)
    # print(f"User {user_id} has access to datasets: {dataset_ids}")
    if not dataset_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User has no dataset permissions configured",
        )

    # 2. Build the user identifier sent to Dify (allow override via body.user)
    dify_user = body.user or user_id

    # print(f"User {user_id} (Dify user: {dify_user}) is querying datasets {dataset_ids} with query: {body.query}")

    # 3. Stream response from Dify
    event_stream = service.chat_stream(
        query=body.query,
        dataset_ids=dataset_ids,
        user=dify_user,
        conversation_id=body.conversation_id,
        inputs=body.inputs,
    )

    return StreamingResponse(event_stream, media_type="text/event-stream")
