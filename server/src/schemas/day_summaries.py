from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CategoryBreakdownItem(BaseModel):
    category: str
    type: str
    minutes: float


class AppBreakdownItem(BaseModel):
    app: str
    minutes: float


class DaySummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    date: date
    total_active_minutes: float
    productive_minutes: float
    neutral_minutes: float
    distraction_minutes: float
    uncategorized_minutes: float
    focus_score: float | None
    distraction_score: float | None
    longest_focus_minutes: float
    context_switches: int
    session_count: int
    top_app: str | None
    top_category: str | None
    category_breakdown: list[CategoryBreakdownItem] | None
    app_breakdown: list[AppBreakdownItem] | None
    narrative: str | None
    is_partial: bool
    created_at: datetime
    updated_at: datetime


class DaySummaryTrendsResponse(BaseModel):
    summaries: list[DaySummaryResponse]
    start: date
    end: date
