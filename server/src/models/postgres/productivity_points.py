import uuid

from sqlalchemy import Column, String, Date, DateTime, Float, Boolean, ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from src.core.database import Base


class ProductivityPointModel(Base):
    __tablename__ = "productivity_points"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    date = Column(Date, nullable=False)
    interval_start = Column(DateTime(timezone=True), nullable=False)
    focus_score = Column(Float, nullable=True)
    depth = Column(String(20), nullable=True)
    productivity_score = Column(Float, nullable=True)
    category = Column(String(100), nullable=True)
    color = Column(String(7), nullable=True)
    is_work = Column(Boolean, server_default="false", nullable=False)
    timeline_entry_id = Column(
        UUID(as_uuid=True),
        ForeignKey("timeline_entries.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "interval_start", name="uq_productivity_points_user_interval"),
        Index("ix_productivity_points_user_date", "user_id", "date"),
    )
