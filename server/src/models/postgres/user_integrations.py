import uuid

from sqlalchemy import (
    Column, String, Boolean, DateTime, ForeignKey, UniqueConstraint, Index,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func

from src.core.database import Base


class UserIntegrationModel(Base):
    __tablename__ = "user_integrations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider = Column(String(50), nullable=False)
    external_user_id = Column(String(255), nullable=True)
    credentials = Column(JSONB, nullable=True)
    is_enabled = Column(Boolean, default=True, server_default="true")
    connected_at = Column(DateTime(timezone=True), server_default=func.now())
    last_used_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("user_id", "provider", name="uq_user_integrations_user_provider"),
        Index("ix_user_integrations_user_id", "user_id"),
    )
