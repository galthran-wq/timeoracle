import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth import get_current_user
from src.core.database import get_postgres_session

from src.models.postgres.users import UserModel
from src.repositories.activity_events import ActivityEventRepository
from src.schemas.activity_events import (
    ActivityEventBatchRequest,
    ActivityEventBatchResponse,
    ActivityEventListResponse,
    ActivityEventResponse,
    ActivityEventType,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/activity", tags=["activity"])


def get_activity_repository(
    postgres_session: AsyncSession = Depends(get_postgres_session),
) -> ActivityEventRepository:
    return ActivityEventRepository(postgres_session)


@router.post("/events", response_model=ActivityEventBatchResponse, status_code=status.HTTP_201_CREATED)
async def ingest_events(
    request: ActivityEventBatchRequest,
    current_user: UserModel = Depends(get_current_user),
    repo: ActivityEventRepository = Depends(get_activity_repository),
):
    errors = repo.validate_batch(request.events)
    if errors:
        raise HTTPException(
            status_code=400,
            detail={"message": "Batch validation failed", "errors": errors},
        )

    under_limit = await repo.check_daily_limit(current_user.id, len(request.events))
    if not under_limit:
        raise HTTPException(
            status_code=429,
            detail="Daily event limit exceeded. Max 100,000 events per 24h.",
        )

    try:
        inserted_count = await repo.bulk_create(current_user.id, request.events)
        return ActivityEventBatchResponse(inserted_count=inserted_count)
    except Exception:
        logger.exception("Failed to ingest activity events for user %s", current_user.id)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/events", response_model=ActivityEventListResponse)
async def list_events(
    start: datetime,
    end: datetime,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    event_type: ActivityEventType | None = None,
    app_name: str | None = None,
    current_user: UserModel = Depends(get_current_user),
    repo: ActivityEventRepository = Depends(get_activity_repository),
):
    if end <= start:
        raise HTTPException(status_code=400, detail="'end' must be after 'start'")

    if (end - start) > timedelta(days=31):
        raise HTTPException(status_code=400, detail="Time range must not exceed 31 days")

    event_type_value = event_type.value if event_type else None

    events = await repo.get_by_time_range(
        current_user.id, start, end, limit, offset,
        event_type=event_type_value, app_name=app_name,
    )
    total_count = await repo.count_by_time_range(
        current_user.id, start, end,
        event_type=event_type_value, app_name=app_name,
    )

    return ActivityEventListResponse(
        events=[ActivityEventResponse.model_validate(e) for e in events],
        total_count=total_count,
        limit=limit,
        offset=offset,
    )


@router.get("/status")
async def daemon_status(
    current_user: UserModel = Depends(get_current_user),
    repo: ActivityEventRepository = Depends(get_activity_repository),
):
    latest = await repo.get_latest(current_user.id, limit=1)
    last_event_at = latest[0].timestamp if latest else None
    events_today = await repo.count_events_today(current_user.id)

    return {"last_event_at": last_event_at, "events_today": events_today}
