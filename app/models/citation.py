import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Double,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ChatMessageCitation(Base):
    __tablename__ = "chat_message_citations"
    __table_args__ = (
        UniqueConstraint(
            "dify_message_id", "position", name="chat_message_citations_message_position_unique"
        ),
        CheckConstraint("position > 0", name="chk_chat_message_citations_position"),
        CheckConstraint(
            "page_no IS NULL OR page_no > 0", name="chk_chat_message_citations_page_no"
        ),
        CheckConstraint("score IS NULL OR score >= 0", name="chk_chat_message_citations_score"),
        CheckConstraint(
            "retrieval_rank IS NULL OR retrieval_rank > 0",
            name="chk_chat_message_citations_retrieval_rank",
        ),
        Index("chat_message_citations_message_idx", "dify_message_id"),
        Index("chat_message_citations_conversation_idx", "dify_conversation_id"),
        Index("chat_message_citations_user_conversation_idx", "user_id", "dify_conversation_id"),
        Index("chat_message_citations_knowledge_idx", "knowledge_id"),
        Index("chat_message_citations_process_pdf_idx", "process_pdf_id"),
        Index("chat_message_citations_segment_idx", "dify_segment_id"),
        Index("chat_message_citations_document_idx", "dify_document_id"),
        Index("chat_message_citations_dataset_idx", "dify_dataset_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Dify message linkage
    dify_conversation_id: Mapped[str] = mapped_column(Text, nullable=False)
    dify_message_id: Mapped[str] = mapped_column(Text, nullable=False)

    # App ownership
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Optional normalized links
    knowledge_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("knowledge_bases.id", ondelete="SET NULL"),
        nullable=True,
    )
    process_pdf_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("process_pdf.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Ordering in source panel
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    # Dify Knowledge identity
    dify_dataset_id: Mapped[str] = mapped_column(Text, nullable=False)
    dify_dataset_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    dify_document_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    dify_document_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    dify_segment_id: Mapped[str] = mapped_column(Text, nullable=False)
    segment_position: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Retrieval result
    score: Mapped[float | None] = mapped_column(Double, nullable=True)
    retrieval_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    search_method: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Content snapshot
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Nullable snapshot/fallback fields
    file_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_no: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Flexible metadata (column name kept as 'metadata' in DB)
    extra_metadata: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped["User"] = relationship("User", lazy="raise")
    knowledge: Mapped["KnowledgeBase | None"] = relationship("KnowledgeBase", lazy="raise")
    process_pdf: Mapped["ProcessPdf | None"] = relationship("ProcessPdf", lazy="raise")


from app.models.batch import ProcessPdf  # noqa: E402, F401
from app.models.knowledge_base import KnowledgeBase  # noqa: E402, F401
from app.models.user import User  # noqa: E402, F401
