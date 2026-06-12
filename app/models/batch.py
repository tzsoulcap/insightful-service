import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Batch(Base):
    __tablename__ = "batch"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'processing', 'completed', 'failed')",
            name="chk_batch_status",
        ),
        CheckConstraint("total_files >= 0", name="chk_batch_total_files_non_negative"),
        Index("batch_knowledge_idx", "knowledge_id"),
        Index("batch_dataset_idx", "dataset_id"),
        Index("batch_status_idx", "status"),
        Index("batch_created_by_idx", "created_by"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    knowledge_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("knowledge_bases.id", ondelete="SET NULL"),
        nullable=True,
    )
    dataset_id: Mapped[str] = mapped_column(Text, nullable=False)
    dataset_name: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    total_files: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    knowledge: Mapped["KnowledgeBase | None"] = relationship("KnowledgeBase", lazy="raise")
    files: Mapped[list["ProcessPdf"]] = relationship(
        "ProcessPdf", back_populates="batch", cascade="all, delete-orphan", lazy="selectin"
    )


class ProcessPdf(Base):
    __tablename__ = "process_pdf"
    __table_args__ = (
        CheckConstraint(
            "pdf_type IS NULL OR pdf_type IN ('NORMAL_TEXT', 'SCANNED_PDF', 'CORRUPT_ENCODING')",
            name="chk_process_pdf_pdf_type",
        ),
        CheckConstraint(
            "status IN ("
            "'pending', 'processing', 'success', 'uploading', 'uploaded', "
            "'error', 'upload_failed', 'completed', 'failed'"
            ")",
            name="chk_process_pdf_status",
        ),
        CheckConstraint(
            "current_step IS NULL OR current_step IN "
            "('rasterizing', 'ocr', 'formatting', 'correcting', 'embedding')",
            name="chk_process_pdf_current_step",
        ),
        CheckConstraint("retry_count >= 0", name="chk_process_pdf_retry_count_non_negative"),
        Index("process_pdf_batch_idx", "batch_id"),
        Index("process_pdf_dify_document_idx", "dify_document_id"),
        Index("process_pdf_batch_document_idx", "batch_id", "dify_document_id"),
        Index("process_pdf_status_idx", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("batch.id", ondelete="CASCADE"),
        nullable=False,
    )
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    original_file_path: Mapped[str] = mapped_column(Text, nullable=False)
    pdf_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    current_step: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)
    dify_document_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    dify_batch: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    batch: Mapped["Batch"] = relationship("Batch", back_populates="files")


# Avoid circular import — import here so KnowledgeBase is resolvable in Batch
from app.models.knowledge_base import KnowledgeBase  # noqa: E402, F401
