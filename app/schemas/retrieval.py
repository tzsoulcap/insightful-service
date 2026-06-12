import uuid
from typing import Any

from pydantic import BaseModel


class AllowedKnowledgeBase(BaseModel):
    knowledge_id: uuid.UUID
    dify_dataset_id: str
    dify_dataset_name: str


class ChunkMetadata(BaseModel):
    index_node_id: str = ""
    index_node_hash: str = ""
    word_count: int = 0
    tokens: int = 0


class NormalizedChunk(BaseModel):
    knowledge_id: uuid.UUID
    dify_dataset_id: str
    dify_dataset_name: str
    dify_document_id: str
    dify_document_name: str
    dify_segment_id: str
    segment_position: int
    content: str
    score: float
    metadata: ChunkMetadata
