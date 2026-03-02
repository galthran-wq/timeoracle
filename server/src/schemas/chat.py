from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    chat_id: Optional[str] = None


class GenerateRequest(BaseModel):
    date: date


class GenerateResponse(BaseModel):
    message: str
    chat_id: str


class ChatMessageItem(BaseModel):
    role: str
    content: str


class ChatSummary(BaseModel):
    id: UUID
    trigger: str
    created_at: datetime
    total_input_tokens: int
    total_output_tokens: int
    preview: str

    class Config:
        from_attributes = True


class ChatDetail(ChatSummary):
    messages: list[ChatMessageItem]


class ChatListResponse(BaseModel):
    chats: list[ChatSummary]
    total_count: int
