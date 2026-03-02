import logging
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth import get_current_user
from src.core.database import get_postgres_session
from src.models.postgres.users import UserModel
from src.repositories.day_summaries import DaySummaryRepository
from src.schemas.day_summaries import DaySummaryResponse, DaySummaryTrendsResponse
from src.services.day_boundary import logical_date_for_timestamp
from src.services.day_summary_service import generate_day_summary

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/day-summaries", tags=["day-summaries"])

MAX_TREND_DAYS = 90


def get_day_summary_repository(
    postgres_session: AsyncSession = Depends(get_postgres_session),
) -> DaySummaryRepository:
    return DaySummaryRepository(postgres_session)


@router.get("/{target_date}", response_model=DaySummaryResponse)
async def get_day_summary(
    target_date: date,
    current_user: UserModel = Depends(get_current_user),
    repo: DaySummaryRepository = Depends(get_day_summary_repository),
):
    summary = await repo.get_by_user_and_date(current_user.id, target_date)
    if not summary:
        raise HTTPException(status_code=404, detail="Day summary not found")
    return DaySummaryResponse.model_validate(summary)


@router.get("", response_model=DaySummaryTrendsResponse)
async def get_day_summary_trends(
    start: date = Query(...),
    end: date = Query(...),
    current_user: UserModel = Depends(get_current_user),
    repo: DaySummaryRepository = Depends(get_day_summary_repository),
):
    if (end - start).days > MAX_TREND_DAYS:
        raise HTTPException(status_code=400, detail=f"Date range must not exceed {MAX_TREND_DAYS} days")
    if end < start:
        raise HTTPException(status_code=400, detail="end must be after start")

    summaries = await repo.get_by_date_range(current_user.id, start, end)
    return DaySummaryTrendsResponse(
        summaries=[DaySummaryResponse.model_validate(s) for s in summaries],
        start=start,
        end=end,
    )


@router.post("/{target_date}/generate", response_model=DaySummaryResponse)
async def force_generate_day_summary(
    target_date: date,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_postgres_session),
):
    cfg = current_user.session_config or {}
    day_start_hour = cfg.get("day_start_hour", 0)
    day_tz = cfg.get("timezone", "UTC")
    logical_today = logical_date_for_timestamp(datetime.now(timezone.utc), day_start_hour, day_tz)
    is_partial = target_date >= logical_today

    try:
        summary = await generate_day_summary(
            user_id=current_user.id,
            target_date=target_date,
            session=session,
            user_session_config=current_user.session_config,
            is_partial=is_partial,
        )
    except Exception:
        logger.exception("Failed to generate day summary for user %s, date %s", current_user.id, target_date)
        raise HTTPException(status_code=500, detail="Internal server error")

    if not summary:
        raise HTTPException(status_code=404, detail="No timeline data for this date")

    return DaySummaryResponse.model_validate(summary)
