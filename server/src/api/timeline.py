import logging
from datetime import date, timedelta
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
    start_date = date
    if date_range == DateRange.WEEK:
        end_date = date + timedelta(days=6)
    else:
        end_date = date

    entries = await repo.get_by_date_range(
        current_user.id, start_date, end_date, limit, offset, category=category,
    )
    total_count = await repo.count_by_date_range(
        current_user.id, start_date, end_date, category=category,
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

    # Cross-validate effective end > start
    effective_start = body.start_time if body.start_time is not None else entry.start_time
    effective_end = body.end_time if body.end_time is not None else entry.end_time
    if effective_end <= effective_start:
        raise HTTPException(status_code=400, detail="end_time must be after start_time")
    if body.date is not None or body.start_time is not None:
        if body.date is not None:
            effective_date = body.date
        elif body.start_time is not None:
            effective_date = body.start_time.date()
        else:
            effective_date = entry.date
        if effective_date != effective_start.date():
            raise HTTPException(status_code=400, detail="date must match the date of start_time")

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
