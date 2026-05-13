from typing import Any

from pydantic import BaseModel


# ── Shared sub-models ─────────────────────────────────────────────────────────

class KnowledgeBaseItem(BaseModel):
    id: str
    name: str
    description: str | None = None
    provider: str | None = None
    permission: str | None = None
    data_source_type: str | None = None
    indexing_technique: str | None = None
    app_count: int = 0
    document_count: int = 0
    word_count: int = 0
    created_by: str | None = None
    author_name: str | None = None
    created_at: int | None = None
    updated_by: str | None = None
    updated_at: int | None = None
    embedding_model: str | None = None
    embedding_model_provider: str | None = None
    embedding_available: bool | None = None
    retrieval_model_dict: dict[str, Any] | None = None
    tags: list[Any] = []
    doc_form: str | None = None
    built_in_field_enabled: bool | None = None
    is_published: bool | None = None
    total_documents: int | None = None
    total_available_documents: int | None = None
    enable_api: bool | None = None
    is_multimodal: bool | None = None

    model_config = {"extra": "allow"}


class KnowledgeBaseListResponse(BaseModel):
    data: list[KnowledgeBaseItem]
    has_more: bool
    limit: int
    total: int
    page: int


class VectorSetting(BaseModel):
    vector_weight: float = 0.6
    embedding_provider_name: str = "langgenius/ollama/ollama"
    embedding_model_name: str = "jina-v5-retrieval"


class KeywordSetting(BaseModel):
    keyword_weight: float = 0.4


class RetrievalWeights(BaseModel):
    weight_type: str = "customized"
    vector_setting: VectorSetting = VectorSetting()
    keyword_setting: KeywordSetting = KeywordSetting()


class RetrievalModel(BaseModel):
    search_method: str = "hybrid_search"
    reranking_enable: bool = False
    reranking_mode: str = "weighted_score"
    top_k: int = 5
    score_threshold_enabled: bool = False
    score_threshold: float = 0
    weights: RetrievalWeights = RetrievalWeights()


class CreateKnowledgeBaseRequest(BaseModel):
    name: str
    description: str = ""
    indexing_technique: str = "high_quality"
    permission: str = "all_team_members"
    provider: str = "vendor"
    embedding_model: str = "jina-v5-retrieval"
    embedding_model_provider: str = "langgenius/ollama/ollama"
    retrieval_model: RetrievalModel = RetrievalModel()


# ── Document ──────────────────────────────────────────────────────────────────

class DocumentItem(BaseModel):
    id: str
    position: int | None = None
    data_source_type: str | None = None
    data_source_info: dict[str, Any] | None = None
    data_source_detail_dict: dict[str, Any] | None = None
    dataset_process_rule_id: str | None = None
    name: str | None = None
    created_from: str | None = None
    created_by: str | None = None
    created_at: int | None = None
    tokens: int = 0
    indexing_status: str | None = None
    error: str | None = None
    enabled: bool = True
    disabled_at: int | None = None
    disabled_by: str | None = None
    archived: bool = False
    display_status: str | None = None
    word_count: int = 0
    hit_count: int = 0
    doc_form: str | None = None

    model_config = {"extra": "allow"}


class DocumentListResponse(BaseModel):
    data: list[DocumentItem]
    has_more: bool
    limit: int
    total: int
    page: int


class CreateDocumentByTextRequest(BaseModel):
    name: str
    text: str
    indexing_technique: str | None = None
    doc_form: str = "text_model"
    doc_language: str = "English"
    original_document_id: str | None = None


class CreateDocumentResponse(BaseModel):
    document: DocumentItem
    batch: str


# ── Indexing Status ───────────────────────────────────────────────────────────

class IndexingStatusItem(BaseModel):
    id: str
    indexing_status: str | None = None
    processing_started_at: int | None = None
    parsing_completed_at: int | None = None
    cleaning_completed_at: int | None = None
    splitting_completed_at: int | None = None
    completed_at: int | None = None
    paused_at: int | None = None
    error: str | None = None
    stopped_at: int | None = None
    completed_segments: int | None = None
    total_segments: int | None = None

    model_config = {"extra": "allow"}


class IndexingStatusResponse(BaseModel):
    data: list[IndexingStatusItem]
