import logging
from datetime import date, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.postgres.day_summaries import DaySummaryModel
from src.repositories.activity_events import ActivityEventRepository
from src.repositories.day_summaries import DaySummaryRepository
from src.repositories.timeline_entries import TimelineEntryRepository
from src.services.activity_session_generator import compute_sessions
from src.services.day_boundary import day_range_utc
from src.services.day_summary_computer import compute_day_summary

logger = logging.getLogger(__name__)


async def generate_day_summary(
    user_id: UUID,
    target_date: date,
    session: AsyncSession,
    user_session_config: dict | None = None,
    is_partial: bool = True,
) -> DaySummaryModel | None:
    cfg = user_session_config or {}
    day_start_hour = cfg.get("day_start_hour", 0)
    day_tz = cfg.get("timezone", "UTC")

    range_start, range_end = day_range_utc(target_date, day_start_hour, day_tz)
    range_start_aware = range_start.replace(tzinfo=timezone.utc)
    range_end_aware = range_end.replace(tzinfo=timezone.utc)

    repo = DaySummaryRepository(session)
    timeline_repo = TimelineEntryRepository(session)

    existing = await repo.get_by_user_and_date(user_id, target_date)

    max_entry_updated = await timeline_repo.get_max_updated_at_in_range(
        user_id, range_start_aware, range_end_aware,
    )

    if max_entry_updated is None:
        if existing:
            await repo.delete(existing)
        return None

    if existing and existing.updated_at and max_entry_updated <= existing.updated_at:
        if is_partial or not existing.is_partial:
            return existing

    entries = await timeline_repo.get_by_time_range(
        user_id, range_start_aware, range_end_aware, limit=1000, offset=0,
    )

    activity_repo = ActivityEventRepository(session)
    events = await activity_repo.get_by_time_range(
        user_id, range_start_aware, range_end_aware, limit=50000, offset=0,
    )

    sessions = compute_sessions(
        events,
        range_end_aware,
        merge_gap_seconds=cfg.get("merge_gap_seconds", 300),
        min_session_seconds=cfg.get("min_session_seconds", 5),
        noise_threshold_seconds=cfg.get("noise_threshold_seconds", 120),
        day_start_hour=day_start_hour,
        day_timezone=day_tz,
    )

    user_categories = cfg.get("categories")
    metrics = compute_day_summary(entries, sessions, user_categories)

    narrative = None
    if not is_partial:
        if existing and existing.narrative and not existing.is_partial:
            narrative = existing.narrative
        else:
            from src.services.narrative_generator import generate_day_narrative
            entry_dicts = [
                {"label": e.label, "category": e.category}
                for e in entries[:15]
            ]
            narrative = await generate_day_narrative(
                date_str=target_date.isoformat(),
                metrics=metrics,
                timeline_entries=entry_dicts,
                model=cfg.get("llm_model"),
            )
    elif existing and existing.narrative:
        narrative = existing.narrative

    return await repo.upsert(
        user_id=user_id,
        target_date=target_date,
        is_partial=is_partial,
        narrative=narrative,
        **metrics,
    )
