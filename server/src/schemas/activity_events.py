import json
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, field_validator, Field


class ActivityEventType(str, Enum):
    ACTIVE_WINDOW = "active_window"
    IDLE_START = "idle_start"
    IDLE_END = "idle_end"


class ActivityEventCreate(BaseModel):
    client_event_id: UUID
    timestamp: datetime
    event_type: ActivityEventType
    app_name: str = Field(min_length=1, max_length=255)
    window_title: str = Field(max_length=2000)
    url: Optional[str] = Field(default=None, max_length=2000)
    metadata: Optional[dict[str, Any]] = Field(default=None, validation_alias="metadata_")

    @field_validator("timestamp")
    @classmethod
    def timestamp_must_be_tz_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("Timestamp must be timezone-aware (include UTC offset)")
        return v

    @field_validator("metadata")
    @classmethod
    def metadata_max_size(cls, v: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
        if v is not None and len(json.dumps(v)) > 4096:
            raise ValueError("Metadata must be ≤4KB when serialized")
        return v


class ActivityEventBatchRequest(BaseModel):
    events: list[ActivityEventCreate] = Field(min_length=1, max_length=1000)


class ActivityEventResponse(BaseModel):
    id: UUID
    user_id: UUID
    client_event_id: UUID
    timestamp: datetime
    event_type: ActivityEventType
    app_name: str
    window_title: str
    url: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ActivityEventBatchResponse(BaseModel):
    inserted_count: int


class ActivityEventListResponse(BaseModel):
    events: list[ActivityEventResponse]
    total_count: int
    limit: int
    offset: int
