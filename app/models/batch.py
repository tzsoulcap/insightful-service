import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Batch(Base):
    __tablename__ = "batch"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    dataset_id: Mapped[str] = mapped_column(String(255), nullable=False)
    dataset_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    total_files: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)

    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    files: Mapped[list["ProcessPdf"]] = relationship(
        "ProcessPdf", back_populates="batch", cascade="all, delete-orphan", lazy="selectin"
    )


class ProcessPdf(Base):
    __tablename__ = "process_pdf"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    batch_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("batch.id", ondelete="CASCADE"), nullable=False, index=True
    )
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    original_file_path: Mapped[str] = mapped_column(Text, nullable=False)

    pdf_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    current_step: Mapped[str | None] = mapped_column(String(30), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)

    dify_document_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    dify_batch: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    batch: Mapped["Batch"] = relationship("Batch", back_populates="files")
