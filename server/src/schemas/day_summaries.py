from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CategoryBreakdownItem(BaseModel):
    category: str
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
    longest_focus_minutes: float
    context_switches: int
    session_count: int
    top_app: str | None
    top_category: str | None
    category_breakdown: list[CategoryBreakdownItem] | None
    app_breakdown: list[AppBreakdownItem] | None
    deep_work_minutes: float
    shallow_work_minutes: float
    reactive_minutes: float
    avg_focus_score: float | None
    fragmentation_index: float | None
    switches_per_hour: float | None
    focus_sessions_25min: int
    focus_sessions_90min: int
    productivity_score: float | None
    overall_productivity_score: float | None
    work_minutes: float
    narrative: str | None
    is_partial: bool
    created_at: datetime
    updated_at: datetime


class DaySummaryTrendsResponse(BaseModel):
    summaries: list[DaySummaryResponse]
    start: date
    end: date
