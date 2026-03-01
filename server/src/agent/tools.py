import logging
from datetime import date, datetime, time, timezone

from pydantic import BaseModel, Field
from pydantic_ai import RunContext

from src.agent.deps import AgentDeps
from src.schemas.timeline_entries import TimelineEntryBulkItem
from src.services.activity_session_generator import compute_sessions

logger = logging.getLogger(__name__)


class TimelineEntry(BaseModel):
    """A timeline entry to save."""
    id: str | None = Field(default=None, description="Existing entry UUID to update, or null to create new")
    date: str = Field(description="Date in YYYY-MM-DD format")
    start_time: str = Field(description="Start time as ISO 8601 datetime with timezone")
    end_time: str = Field(description="End time as ISO 8601 datetime with timezone")
    label: str = Field(description="Concise human-readable label (2-5 words)")
    description: str | None = Field(default=None, description="Optional longer description")
    category: str | None = Field(default=None, description="One of: Work, Communication, Research, Entertainment, Health, Personal, Admin")
    color: str | None = Field(default=None, description="Hex color like #3B82F6")
    confidence: float | None = Field(default=None, description="Confidence score 0.0-1.0")
    source_summary: str | None = Field(default=None, description="Brief note on which apps/titles informed this label")


async def _emit(ctx: RunContext[AgentDeps], event_type: str, data: dict):
    if ctx.deps.event_queue:
        await ctx.deps.event_queue.put((event_type, data))


async def get_activity_sessions(ctx: RunContext[AgentDeps], target_date: str) -> list[dict]:
    """Fetch computed activity sessions for a given date. Returns app names, window titles, URLs, and time ranges.

    Args:
        ctx: The run context with dependencies.
        target_date: Date in YYYY-MM-DD format.
    """
    await _emit(ctx, "tool_call", {"name": "get_activity_sessions", "args": {"date": target_date}})

    try:
        d = date.fromisoformat(target_date)
    except ValueError:
        return [{"error": f"Invalid date format: {target_date}. Use YYYY-MM-DD."}]

    day_start = datetime.combine(d, time.min, tzinfo=timezone.utc)
    day_end = datetime.combine(d, time.max, tzinfo=timezone.utc)

    events = await ctx.deps.activity_repo.get_by_time_range(
        ctx.deps.user_id, day_start, day_end, limit=100_000, offset=0,
    )

    if not events:
        await _emit(ctx, "tool_result", {"name": "get_activity_sessions", "summary": "No activity data found"})
        return []

    cap_time = min(datetime.now(timezone.utc), day_end)
    cfg = ctx.deps.user_session_config or {}
    sessions = compute_sessions(
        events,
        cap_time,
        merge_gap_seconds=cfg.get("merge_gap_seconds", 300),
        min_session_seconds=cfg.get("min_session_seconds", 5),
        noise_threshold_seconds=cfg.get("noise_threshold_seconds", 120),
    )

    result = []
    for s in sessions:
        result.append({
            "app_name": s["app_name"],
            "window_titles": s.get("window_titles", []),
            "url": s.get("url"),
            "start_time": s["start_time"].isoformat(),
            "end_time": s["end_time"].isoformat(),
            "date": str(s["date"]),
        })

    await _emit(ctx, "tool_result", {"name": "get_activity_sessions", "summary": f"Found {len(result)} sessions"})
    return result


async def get_existing_timeline(ctx: RunContext[AgentDeps], target_date: str) -> list[dict]:
    """Fetch existing timeline entries for a given date. Use this to avoid duplicates and respect user edits.

    Args:
        ctx: The run context with dependencies.
        target_date: Date in YYYY-MM-DD format.
    """
    await _emit(ctx, "tool_call", {"name": "get_existing_timeline", "args": {"date": target_date}})

    try:
        d = date.fromisoformat(target_date)
    except ValueError:
        return [{"error": f"Invalid date format: {target_date}. Use YYYY-MM-DD."}]

    entries = await ctx.deps.timeline_repo.get_by_date_range(
        ctx.deps.user_id, d, d, limit=500, offset=0,
    )

    result = []
    for e in entries:
        result.append({
            "id": str(e.id),
            "label": e.label,
            "category": e.category,
            "start_time": e.start_time.isoformat(),
            "end_time": e.end_time.isoformat(),
            "edited_by_user": e.edited_by_user,
            "source": e.source,
        })

    await _emit(ctx, "tool_result", {"name": "get_existing_timeline", "summary": f"Found {len(result)} existing entries"})
    return result


async def save_timeline_entries(ctx: RunContext[AgentDeps], entries: list[TimelineEntry]) -> dict:
    """Save timeline entries to the database. Creates new entries or updates existing ones. Entries edited by user are automatically skipped.

    Args:
        ctx: The run context with dependencies.
        entries: List of timeline entries to save.
    """
    await _emit(ctx, "tool_call", {"name": "save_timeline_entries", "args": {"count": len(entries)}})

    from uuid import UUID

    bulk_items = []
    for entry in entries:
        try:
            entry_date = date.fromisoformat(entry.date)
            start_time = datetime.fromisoformat(entry.start_time)
            end_time = datetime.fromisoformat(entry.end_time)

            entry_id = UUID(entry.id) if entry.id else None

            bulk_items.append(TimelineEntryBulkItem(
                id=entry_id,
                date=entry_date,
                start_time=start_time,
                end_time=end_time,
                label=entry.label,
                description=entry.description,
                category=entry.category,
                color=entry.color,
                confidence=entry.confidence,
                source_summary=entry.source_summary,
            ))
        except (ValueError, TypeError) as e:
            logger.warning("Skipping invalid entry: %s", e)
            continue

    if not bulk_items:
        await _emit(ctx, "tool_result", {"name": "save_timeline_entries", "summary": "No valid entries to save"})
        return {"created": 0, "updated": 0, "skipped": 0, "errors": ["No valid entries"]}

    created, updated, skipped, errors = await ctx.deps.timeline_repo.bulk_upsert(
        ctx.deps.user_id, bulk_items, chat_id=ctx.deps.chat_id,
    )

    summary = f"Created {created}, updated {updated}, skipped {skipped}"
    await _emit(ctx, "tool_result", {"name": "save_timeline_entries", "summary": summary})

    return {
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "errors": [e["message"] for e in errors] if errors else [],
    }
