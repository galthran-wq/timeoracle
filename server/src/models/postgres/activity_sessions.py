import uuid

from sqlalchemy import Column, String, Text, DateTime, Date, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func

from src.core.database import Base


class ActivitySessionModel(Base):
    __tablename__ = "activity_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    app_name = Column(String(255), nullable=False)
    window_title = Column(String(2000), nullable=False)
    window_titles = Column(JSONB, nullable=True)
    url = Column(String(2000), nullable=True)
    icon = Column(Text, nullable=True)
    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=False)
    date = Column(Date, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_activity_sessions_user_date", "user_id", "date"),
        Index("ix_activity_sessions_user_start", "user_id", "start_time"),
    )
