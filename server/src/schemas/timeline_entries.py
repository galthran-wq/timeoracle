import re
from datetime import date, datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class TimelineEntrySource(str, Enum):
    MANUAL = "manual"
    AI_GENERATED = "ai_generated"


def _validate_tz_aware(v: datetime, field_name: str) -> datetime:
    if v.tzinfo is None:
        raise ValueError(f"{field_name} must be timezone-aware (include UTC offset)")
    return v


def _validate_color(v: Optional[str]) -> Optional[str]:
    if v is not None and not re.match(r"^#[0-9A-Fa-f]{6}$", v):
        raise ValueError("color must be hex format like '#3B82F6'")
    return v


class TimelineEntryCreate(BaseModel):
    date: date
    start_time: datetime
    end_time: datetime
    label: str = Field(min_length=1, max_length=255)
    description: Optional[str] = None
    category: Optional[str] = Field(default=None, max_length=100)
    color: Optional[str] = Field(default=None, max_length=7)

    @field_validator("start_time")
    @classmethod
    def start_time_tz_aware(cls, v: datetime) -> datetime:
        return _validate_tz_aware(v, "start_time")

    @field_validator("end_time")
    @classmethod
    def end_time_tz_aware(cls, v: datetime) -> datetime:
        return _validate_tz_aware(v, "end_time")

    @field_validator("color")
    @classmethod
    def color_hex_format(cls, v: Optional[str]) -> Optional[str]:
        return _validate_color(v)

    @model_validator(mode="after")
    def end_after_start(self):
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self

    @model_validator(mode="after")
    def date_matches_start(self):
        if self.start_time.date() != self.date:
            raise ValueError("date must match the date of start_time")
        return self


class TimelineEntryUpdate(BaseModel):
    date: Optional[date] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    label: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = None
    category: Optional[str] = Field(default=None, max_length=100)
    color: Optional[str] = Field(default=None, max_length=7)

    @field_validator("start_time")
    @classmethod
    def start_time_tz_aware(cls, v: Optional[datetime]) -> Optional[datetime]:
        if v is not None:
            return _validate_tz_aware(v, "start_time")
        return v

    @field_validator("end_time")
    @classmethod
    def end_time_tz_aware(cls, v: Optional[datetime]) -> Optional[datetime]:
        if v is not None:
            return _validate_tz_aware(v, "end_time")
        return v

    @field_validator("color")
    @classmethod
    def color_hex_format(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return _validate_color(v)
        return v

    @model_validator(mode="after")
    def required_fields_not_null(self):
        for field in {"date", "start_time", "end_time", "label"}:
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class TimelineEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    date: date
    start_time: datetime
    end_time: datetime
    label: str
    description: Optional[str] = None
    category: Optional[str] = None
    color: Optional[str] = None
    source: str
    source_summary: Optional[str] = None
    confidence: Optional[float] = None
    edited_by_user: bool
    created_at: datetime
    updated_at: datetime


class TimelineEntryListResponse(BaseModel):
    entries: list[TimelineEntryResponse]
    total_count: int
    limit: int
    offset: int


class TimelineEntryBulkItem(TimelineEntryCreate):
    id: Optional[UUID] = None
    source_summary: Optional[str] = None
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class TimelineEntryBulkRequest(BaseModel):
    entries: list[TimelineEntryBulkItem] = Field(min_length=1, max_length=100)


class TimelineEntryBulkError(BaseModel):
    index: int
    message: str


class TimelineEntryBulkResponse(BaseModel):
    created: int
    updated: int
    skipped: int
    errors: list[TimelineEntryBulkError]
