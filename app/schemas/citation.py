import uuid

from pydantic import BaseModel, Field

from app.schemas.common import DatetimeTZ7


class CitationCreate(BaseModel):
    dify_conversation_id: str
    dify_message_id: str
    user_id: uuid.UUID
    tenant_id: str | None = None
    knowledge_id: uuid.UUID | None = None
    process_pdf_id: uuid.UUID | None = None
    position: int = Field(..., gt=0)
    dify_dataset_id: str
    dify_dataset_name: str | None = None
    dify_document_id: str | None = None
    dify_document_name: str | None = None
    dify_segment_id: str
    segment_position: int | None = None
    score: float | None = Field(None, ge=0)
    retrieval_rank: int | None = Field(None, gt=0)
    search_method: str | None = None
    content: str
    content_hash: str | None = None
    file_name: str | None = None
    file_path: str | None = None
    page_no: int | None = Field(None, gt=0)
    extra_metadata: dict = {}


class CitationResponse(BaseModel):
    id: uuid.UUID
    dify_conversation_id: str
    dify_message_id: str
    user_id: uuid.UUID
    knowledge_id: uuid.UUID | None = None
    process_pdf_id: uuid.UUID | None = None
    position: int
    dify_dataset_id: str
    dify_dataset_name: str | None = None
    dify_document_id: str | None = None
    dify_document_name: str | None = None
    dify_segment_id: str
    segment_position: int | None = None
    score: float | None = None
    retrieval_rank: int | None = None
    search_method: str | None = None
    content: str
    file_name: str | None = None
    file_path: str | None = None
    page_no: int | None = None
    extra_metadata: dict = {}
    created_at: DatetimeTZ7

    model_config = {"from_attributes": True}
