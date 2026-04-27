from sqlalchemy import Column, Integer, String, UniqueConstraint

from app.core.database import Base


class UserPermission(Base):
    __tablename__ = "user_permissions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, nullable=False, index=True)
    dataset_id = Column(String, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "dataset_id", name="uq_user_dataset"),
    )
