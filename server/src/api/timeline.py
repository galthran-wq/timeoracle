import logging
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth import get_current_user
from src.core.database import get_postgres_session
from src.models.postgres.users import UserModel
from src.repositories.timeline_entries import TimelineEntryRepository
from src.schemas.timeline_entries import (
    TimelineEntryBulkError,
    TimelineEntryBulkRequest,
    TimelineEntryBulkResponse,
    TimelineEntryCreate,
    TimelineEntryListResponse,
    TimelineEntryResponse,
    TimelineEntryUpdate,
)
from src.services.day_boundary import day_range_utc, week_range_utc, logical_date_for_timestamp

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/timeline", tags=["timeline"])


class DateRange(str, Enum):
    DAY = "day"
    WEEK = "week"


def get_timeline_repository(
    postgres_session: AsyncSession = Depends(get_postgres_session),
) -> TimelineEntryRepository:
    return TimelineEntryRepository(postgres_session)


@router.post("", response_model=TimelineEntryResponse, status_code=status.HTTP_201_CREATED)
async def create_entry(
    body: TimelineEntryCreate,
    current_user: UserModel = Depends(get_current_user),
    repo: TimelineEntryRepository = Depends(get_timeline_repository),
):
    cfg = current_user.session_config or {}
    day_start_hour = cfg.get("day_start_hour", 0)
    day_tz = cfg.get("timezone", "UTC")
    logical = logical_date_for_timestamp(body.start_time, day_start_hour, day_tz)
    if body.date != logical:
        body = body.model_copy(update={"date": logical})
    try:
        entry = await repo.create(current_user.id, body)
        return TimelineEntryResponse.model_validate(entry)
    except Exception:
        logger.exception("Failed to create timeline entry for user %s", current_user.id)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/bulk", response_model=TimelineEntryBulkResponse)
async def bulk_upsert_entries(
    body: TimelineEntryBulkRequest,
    current_user: UserModel = Depends(get_current_user),
    repo: TimelineEntryRepository = Depends(get_timeline_repository),
):
    try:
        created, updated, skipped, errors = await repo.bulk_upsert(
            current_user.id, body.entries
        )
        return TimelineEntryBulkResponse(
            created=created,
            updated=updated,
            skipped=skipped,
            errors=[TimelineEntryBulkError(**e) for e in errors],
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        logger.exception("Failed bulk upsert for user %s", current_user.id)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("", response_model=TimelineEntryListResponse)
async def list_entries(
    date: date = Query(..., description="Start date for the query"),
    date_range: DateRange = Query(default=DateRange.DAY, description="day or week", alias="range"),
    category: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    current_user: UserModel = Depends(get_current_user),
    repo: TimelineEntryRepository = Depends(get_timeline_repository),
):
    cfg = current_user.session_config or {}
    day_start_hour = cfg.get("day_start_hour", 0)
    day_tz = cfg.get("timezone", "UTC")

    if date_range == DateRange.WEEK:
        range_start, range_end = week_range_utc(date, day_start_hour, day_tz)
    else:
        range_start, range_end = day_range_utc(date, day_start_hour, day_tz)

    range_start_aware = range_start.replace(tzinfo=timezone.utc)
    range_end_aware = range_end.replace(tzinfo=timezone.utc)

    entries = await repo.get_by_time_range(
        current_user.id, range_start_aware, range_end_aware, limit, offset, category=category,
    )
    total_count = await repo.count_by_time_range(
        current_user.id, range_start_aware, range_end_aware, category=category,
    )

    return TimelineEntryListResponse(
        entries=[TimelineEntryResponse.model_validate(e) for e in entries],
        total_count=total_count,
        limit=limit,
        offset=offset,
    )


@router.patch("/{entry_id}", response_model=TimelineEntryResponse)
async def update_entry(
    entry_id: UUID,
    body: TimelineEntryUpdate,
    current_user: UserModel = Depends(get_current_user),
    repo: TimelineEntryRepository = Depends(get_timeline_repository),
):
    entry = await repo.get_by_id(entry_id)
    if not entry or entry.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Timeline entry not found")

    effective_start = body.start_time if body.start_time is not None else entry.start_time
    effective_end = body.end_time if body.end_time is not None else entry.end_time
    if effective_end <= effective_start:
        raise HTTPException(status_code=400, detail="end_time must be after start_time")

    cfg = current_user.session_config or {}
    day_start_hour = cfg.get("day_start_hour", 0)
    day_tz = cfg.get("timezone", "UTC")

    if body.start_time is not None:
        logical = logical_date_for_timestamp(effective_start, day_start_hour, day_tz)
        body = body.model_copy(update={"date": logical})

    try:
        updated = await repo.update(entry, body)
        return TimelineEntryResponse.model_validate(updated)
    except Exception:
        logger.exception("Failed to update timeline entry %s", entry_id)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_entry(
    entry_id: UUID,
    current_user: UserModel = Depends(get_current_user),
    repo: TimelineEntryRepository = Depends(get_timeline_repository),
):
    entry = await repo.get_by_id(entry_id)
    if not entry or entry.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Timeline entry not found")

    try:
        await repo.delete(entry)
    except Exception:
        logger.exception("Failed to delete timeline entry %s", entry_id)
        raise HTTPException(status_code=500, detail="Internal server error")
