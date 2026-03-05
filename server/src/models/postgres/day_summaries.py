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
    longest_focus_minutes = Column(Float, server_default="0", nullable=False)
    context_switches = Column(Integer, server_default="0", nullable=False)
    session_count = Column(Integer, server_default="0", nullable=False)
    top_app = Column(String(255), nullable=True)
    top_category = Column(String(100), nullable=True)
    category_breakdown = Column(JSONB, nullable=True)
    app_breakdown = Column(JSONB, nullable=True)
    deep_work_minutes = Column(Float, server_default="0", nullable=False)
    shallow_work_minutes = Column(Float, server_default="0", nullable=False)
    reactive_minutes = Column(Float, server_default="0", nullable=False)
    avg_focus_score = Column(Float, nullable=True)
    fragmentation_index = Column(Float, nullable=True)
    switches_per_hour = Column(Float, nullable=True)
    focus_sessions_25min = Column(Integer, server_default="0", nullable=False)
    focus_sessions_90min = Column(Integer, server_default="0", nullable=False)
    productivity_score = Column(Float, nullable=True)
    overall_productivity_score = Column(Float, nullable=True)
    work_minutes = Column(Float, server_default="0", nullable=False)
    narrative = Column(Text, nullable=True)
    is_partial = Column(Boolean, server_default="false", nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "date", name="uq_day_summaries_user_date"),
        Index("ix_day_summaries_user_date", "user_id", "date"),
    )
