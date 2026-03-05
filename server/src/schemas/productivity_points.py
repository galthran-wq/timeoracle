from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class ProductivityPointResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    interval_start: datetime
    focus_score: float | None
    depth: str | None
    category: str | None
    color: str | None
    is_work: bool
    productivity_score: float | None


class AggregatedBucket(BaseModel):
    bucket_start: datetime
    avg_productivity_score: float | None
    avg_performance_score: float | None
    point_count: int
    work_point_count: int
    dominant_category: str | None
    dominant_color: str | None


class AggregatedCurveResponse(BaseModel):
    start: date
    end: date
    bucket_minutes: int
    buckets: list[AggregatedBucket]
    overall_score: float | None
    performance_score: float | None


class ProductivityCurveResponse(BaseModel):
    date: date
    points: list[ProductivityPointResponse]
    day_score: float | None
    overall_score: float | None
    work_minutes: float
