import datetime as dt
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ActivitySessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    app_name: str
    window_title: str
    window_titles: Optional[list[str]] = None
    url: Optional[str] = None
    icon: Optional[str] = None
    brand_color: Optional[str] = None
    start_time: dt.datetime
    end_time: dt.datetime
    date: dt.date


class ActivitySessionListResponse(BaseModel):
    sessions: list[ActivitySessionResponse]
    total_count: int
    limit: int
    offset: int
