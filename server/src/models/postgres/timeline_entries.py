import uuid

from sqlalchemy import Column, String, Text, Date, DateTime, Float, Boolean, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from src.core.database import Base


class TimelineEntryModel(Base):
    __tablename__ = "timeline_entries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    date = Column(Date, nullable=False)
    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=False)
    label = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(100), nullable=True)
    color = Column(String(7), nullable=True)
    source = Column(String(20), server_default="manual", nullable=False)
    source_summary = Column(Text, nullable=True)
    confidence = Column(Float, nullable=True)
    chat_id = Column(
        UUID(as_uuid=True),
        ForeignKey("chats.id", ondelete="SET NULL"),
        nullable=True,
    )
    edited_by_user = Column(Boolean, server_default="false", nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_timeline_entries_user_date", "user_id", "date"),
        Index("ix_timeline_entries_user_start_time", "user_id", "start_time"),
    )
