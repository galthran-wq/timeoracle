from datetime import date, datetime, time, timedelta, timezone
from uuid import UUID, uuid5

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth import get_current_user
from src.core.database import get_postgres_session
from src.models.postgres.users import UserModel
from src.repositories.activity_events import ActivityEventRepository
from src.schemas.activity_sessions import (
    ActivitySessionListResponse,
    ActivitySessionResponse,
)
from src.services.activity_session_generator import compute_sessions
from src.services.icon_resolver import resolve_session_icon

router = APIRouter(prefix="/api/activity/sessions", tags=["activity-sessions"])

_SESSION_ID_NAMESPACE = UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")


def _get_event_repo(
    session: AsyncSession = Depends(get_postgres_session),
) -> ActivityEventRepository:
    return ActivityEventRepository(session)


@router.get("", response_model=ActivitySessionListResponse)
async def list_sessions(
    date: date = Query(description="Start date (YYYY-MM-DD)"),
    range: str = Query(default="day", pattern="^(day|week)$"),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    current_user: UserModel = Depends(get_current_user),
    event_repo: ActivityEventRepository = Depends(_get_event_repo),
):
    start_date = date
    end_date = date + timedelta(days=6) if range == "week" else date

    day_start = datetime.combine(start_date, time.min, tzinfo=timezone.utc)
    day_end = datetime.combine(end_date, time.max, tzinfo=timezone.utc)

    events = await event_repo.get_by_time_range(
        current_user.id, day_start, day_end, limit=100_000, offset=0,
    )

    if events:
        latest_day_end = datetime.combine(
            events[-1].timestamp.date(), time.max, tzinfo=timezone.utc,
        )
        cap_time = min(datetime.now(timezone.utc), latest_day_end)
    else:
        cap_time = datetime.now(timezone.utc)

    cfg = current_user.session_config or {}
    sessions = compute_sessions(
        events,
        cap_time,
        merge_gap_seconds=cfg.get("merge_gap_seconds", 300),
        min_session_seconds=cfg.get("min_session_seconds", 5),
        noise_threshold_seconds=cfg.get("noise_threshold_seconds", 120),
    )

    total_count = len(sessions)
    page = sessions[offset:offset + limit]

    result = []
    for s in page:
        icon_url, brand_color = resolve_session_icon(s["app_name"], s.get("url"))
        result.append(ActivitySessionResponse(
            id=uuid5(
                _SESSION_ID_NAMESPACE,
                f"{current_user.id}:{s['start_time'].isoformat()}:{s['app_name']}",
            ),
            user_id=current_user.id,
            app_name=s["app_name"],
            window_title=s["window_title"],
            window_titles=s.get("window_titles"),
            url=s.get("url"),
            icon=icon_url,
            brand_color=brand_color,
            start_time=s["start_time"],
            end_time=s["end_time"],
            date=s["date"],
        ))

    return ActivitySessionListResponse(
        sessions=result,
        total_count=total_count,
        limit=limit,
        offset=offset,
    )
