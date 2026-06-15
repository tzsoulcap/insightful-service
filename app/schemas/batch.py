import uuid

from pydantic import BaseModel

from app.schemas.common import DatetimeTZ7


# ── Process PDF item ──────────────────────────────────────────────────────────

class ProcessPdfResponse(BaseModel):
    id: uuid.UUID
    filename: str
    pdf_type: str | None = None
    status: str
    current_step: str | None = None
    retry_count: int = 0
    error_msg: str | None = None
    dify_document_id: str | None = None
    dify_batch: str | None = None
    created_at: DatetimeTZ7
    updated_at: DatetimeTZ7

    model_config = {"from_attributes": True}


# ── Batch ─────────────────────────────────────────────────────────────────────

class BatchResponse(BaseModel):
    id: uuid.UUID
    dataset_id: str
    dataset_name: str
    status: str
    total_files: int
    created_by: uuid.UUID | None = None
    scheduled_at: DatetimeTZ7 | None = None
    started_at: DatetimeTZ7 | None = None
    completed_at: DatetimeTZ7 | None = None
    created_at: DatetimeTZ7
    updated_at: DatetimeTZ7
    files: list[ProcessPdfResponse] = []

    model_config = {"from_attributes": True}


class BatchSummaryResponse(BaseModel):
    id: uuid.UUID
    dataset_id: str
    dataset_name: str
    status: str
    total_files: int
    created_by: uuid.UUID | None = None
    scheduled_at: DatetimeTZ7 | None = None
    started_at: DatetimeTZ7 | None = None
    completed_at: DatetimeTZ7 | None = None
    created_at: DatetimeTZ7
    updated_at: DatetimeTZ7

    model_config = {"from_attributes": True}


class BatchListResponse(BaseModel):
    data: list[BatchSummaryResponse]
    total: int
    page: int
    limit: int
    has_more: bool


# ── List by dataset ───────────────────────────────────────────────────────────

class BatchTrackItem(BaseModel):
    id: uuid.UUID
    status: str
    created_by: uuid.UUID | None = None
    total_files: int
    success_count: int
    failed_count: int
    processing_count: int
    pending_count: int
    scheduled_at: DatetimeTZ7 | None = None
    started_at: DatetimeTZ7 | None = None
    completed_at: DatetimeTZ7 | None = None
    created_at: DatetimeTZ7
    updated_at: DatetimeTZ7


class BatchByDatasetResponse(BaseModel):
    dataset_id: str
    dataset_name: str
    data: list[BatchTrackItem]
    has_more: bool
    limit: int
    total: int
    page: int


# ── Process PDF list ──────────────────────────────────────────────────────────

class ProcessPdfItem(BaseModel):
    id: uuid.UUID
    filename: str
    pdf_type: str | None = None
    status: str
    current_step: str | None = None
    error_msg: str | None = None
    updated_at: DatetimeTZ7

    model_config = {"from_attributes": True}


class ProcessPdfListResponse(BaseModel):
    batch_id: uuid.UUID
    data: list[ProcessPdfItem]
