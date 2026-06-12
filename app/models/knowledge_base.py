import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class KnowledgeBase(Base):
    __tablename__ = "knowledge_bases"
    __table_args__ = (
        UniqueConstraint("dify_dataset_id", name="knowledge_bases_dify_dataset_unique"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dify_dataset_id: Mapped[str] = mapped_column(Text, nullable=False)
    dify_dataset_name: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    permissions: Mapped[list["KnowledgePermission"]] = relationship(
        "KnowledgePermission",
        back_populates="knowledge",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class KnowledgePermission(Base):
    __tablename__ = "knowledge_permissions"
    __table_args__ = (
        CheckConstraint(
            "(group_id IS NOT NULL AND user_id IS NULL) OR (group_id IS NULL AND user_id IS NOT NULL)",
            name="chk_knowledge_permissions_target",
        ),
        CheckConstraint(
            "permission_level IN ('read', 'write', 'admin')",
            name="chk_knowledge_permissions_level",
        ),
        UniqueConstraint("knowledge_id", "group_id", name="uq_knowledge_permissions_group"),
        UniqueConstraint("knowledge_id", "user_id", name="uq_knowledge_permissions_user"),
        Index("knowledge_permissions_knowledge_idx", "knowledge_id"),
        Index("knowledge_permissions_group_idx", "group_id"),
        Index("knowledge_permissions_user_idx", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    knowledge_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
        nullable=False,
    )
    group_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("groups.id", ondelete="CASCADE"),
        nullable=True,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
    )
    permission_level: Mapped[str] = mapped_column(Text, nullable=False)

    knowledge: Mapped["KnowledgeBase"] = relationship("KnowledgeBase", back_populates="permissions")
    group: Mapped["Group | None"] = relationship("Group", lazy="raise")
    user: Mapped["User | None"] = relationship("User", lazy="raise")


from app.models.group import Group  # noqa: E402, F401
from app.models.user import User  # noqa: E402, F401
