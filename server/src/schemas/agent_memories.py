from pydantic import BaseModel, ConfigDict, Field
from uuid import UUID
from datetime import datetime
from typing import Optional


class AgentMemoryCreate(BaseModel):
    content: str = Field(min_length=1, max_length=1000)


class AgentMemoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    content: str
    source: str
    source_entry_id: Optional[UUID] = None
    is_active: bool
    created_at: datetime


class AgentMemoryListResponse(BaseModel):
    memories: list[AgentMemoryResponse]
    total_count: int
