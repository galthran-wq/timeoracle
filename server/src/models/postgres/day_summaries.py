import uuid

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql import func

from src.core.database import Base


class DaySummaryModel(Base):
    __tablename__ = "day_summaries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    date = Column(Date, nullable=False)
    total_active_minutes = Column(Float, server_default="0", nullable=False)
    productive_minutes = Column(Float, server_default="0", nullable=False)
    neutral_minutes = Column(Float, server_default="0", nullable=False)
    distraction_minutes = Column(Float, server_default="0", nullable=False)
    uncategorized_minutes = Column(Float, server_default="0", nullable=False)
    focus_score = Column(Float, nullable=True)
    distraction_score = Column(Float, nullable=True)
    longest_focus_minutes = Column(Float, server_default="0", nullable=False)
    context_switches = Column(Integer, server_default="0", nullable=False)
    session_count = Column(Integer, server_default="0", nullable=False)
    top_app = Column(String(255), nullable=True)
    top_category = Column(String(100), nullable=True)
    category_breakdown = Column(JSONB, nullable=True)
    app_breakdown = Column(JSONB, nullable=True)
    narrative = Column(Text, nullable=True)
    is_partial = Column(Boolean, server_default="false", nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "date", name="uq_day_summaries_user_date"),
        Index("ix_day_summaries_user_date", "user_id", "date"),
    )
