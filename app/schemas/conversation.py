from pydantic import BaseModel


class MessageFile(BaseModel):
    id: str
    type: str
    url: str
    belongs_to: str


class MessageFeedback(BaseModel):
    rating: str | None = None


class EnrichedMetadata(BaseModel):
    page_number: int | None = None
    file_name: str | None = None
    pdf_url: str | None = None


class RetrieverResource(BaseModel):
    position: int
    dataset_id: str
    dataset_name: str
    document_id: str
    document_name: str
    segment_id: str
    score: float
    content: str
    enriched_metadata: EnrichedMetadata | None = None


class MessageItem(BaseModel):
    id: str
    conversation_id: str
    inputs: dict = {}
    query: str
    answer: str
    message_files: list[MessageFile] = []
    feedback: MessageFeedback | None = None
    retriever_resources: list[RetrieverResource] = []
    created_at: int


class MessagesResponse(BaseModel):
    limit: int
    has_more: bool
    data: list[MessageItem]


class ConversationItem(BaseModel):
    id: str
    name: str
    inputs: dict = {}
    status: str
    introduction: str | None = None
    created_at: int
    updated_at: int


class ConversationsResponse(BaseModel):
    limit: int
    has_more: bool
    data: list[ConversationItem]


class RenameConversationRequest(BaseModel):
    name: str | None = None
    auto_generate: bool = False
    user: str


class ConversationDetailResponse(BaseModel):
    id: str
    name: str
    inputs: dict = {}
    status: str
    introduction: str | None = None
    created_at: int
    updated_at: int
