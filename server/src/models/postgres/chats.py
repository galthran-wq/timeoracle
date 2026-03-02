import uuid

from sqlalchemy import Column, String, DateTime, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func

from src.core.database import Base


class ChatModel(Base):
    __tablename__ = "chats"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    trigger = Column(String(20), nullable=False)
    llm_model = Column(String(100), nullable=False)
    messages = Column(JSONB, server_default="[]")
    total_input_tokens = Column(Integer, nullable=False, server_default="0")
    total_output_tokens = Column(Integer, nullable=False, server_default="0")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
