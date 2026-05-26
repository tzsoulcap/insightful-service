from datetime import datetime

from pydantic import BaseModel


# ── Process PDF item ──────────────────────────────────────────────────────────

class ProcessPdfResponse(BaseModel):
    id: str
    filename: str
    pdf_type: str | None = None
    status: str
    current_step: str | None = None
    retry_count: int = 0
    error_msg: str | None = None
    dify_document_id: str | None = None
    dify_batch: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Batch ─────────────────────────────────────────────────────────────────────

class BatchResponse(BaseModel):
    id: str
    dataset_id: str
    dataset_name: str
    status: str
    total_files: int
    created_by: str | None = None
    scheduled_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    files: list[ProcessPdfResponse] = []

    model_config = {"from_attributes": True}


class BatchSummaryResponse(BaseModel):
    id: str
    dataset_id: str
    dataset_name: str
    status: str
    total_files: int
    created_by: str | None = None
    scheduled_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BatchListResponse(BaseModel):
    data: list[BatchSummaryResponse]
    total: int
    page: int
    limit: int
    has_more: bool
