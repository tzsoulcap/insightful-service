from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, description="User input / question content")
    conversation_id: str | None = Field(None, description="Conversation ID to continue previous chat")
    inputs: dict = Field(default_factory=dict, description="Additional variable inputs for Dify app")
    user: str | None = Field(None, description="Override user identifier sent to Dify")
    auto_generate_name: bool = Field(False, description="Auto-generate conversation title")


class ChatResponse(BaseModel):
    event: str
    task_id: str | None = None
    message_id: str | None = None
    conversation_id: str | None = None
    answer: str | None = None
    created_at: int | None = None
    metadata: dict | None = None
