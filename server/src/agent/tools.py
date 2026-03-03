import logging
from dataclasses import dataclass
from datetime import date, datetime, time, timezone

from pydantic import BaseModel, Field
from pydantic_ai import RunContext

from src.agent.deps import AgentDeps
from src.schemas.timeline_entries import TimelineEntryBulkItem
from src.services.activity_session_generator import compute_sessions
from src.services.day_boundary import day_range_utc, logical_date_for_timestamp

logger = logging.getLogger(__name__)


class TimelineEntry(BaseModel):
    id: str | None = Field(default=None, description="Existing entry UUID to update, or null to create new")
    date: str = Field(description="Date in YYYY-MM-DD format")
    start_time: str = Field(description="Start time as ISO 8601 datetime with timezone")
    end_time: str = Field(description="End time as ISO 8601 datetime with timezone")
    label: str = Field(description="Concise human-readable label (2-5 words)")
    description: str | None = Field(default=None, description="Optional longer description")
    category: str | None = Field(default=None, description="One of the user's configured categories")
    color: str | None = Field(default=None, description="Hex color like #3B82F6")
    confidence: float | None = Field(default=None, description="Confidence score 0.0-1.0")
    source_summary: str | None = Field(default=None, description="Brief note on which apps/titles informed this label")


async def _emit(ctx: RunContext[AgentDeps], event_type: str, data: dict):
    if ctx.deps.event_queue:
        await ctx.deps.event_queue.put((event_type, data))


async def get_activity_sessions(ctx: RunContext[AgentDeps], target_date: str) -> list[dict]:
    await _emit(ctx, "tool_call", {"name": "get_activity_sessions", "args": {"date": target_date}})

    try:
        d = date.fromisoformat(target_date)
    except ValueError:
        return [{"error": f"Invalid date format: {target_date}. Use YYYY-MM-DD."}]

    cfg = ctx.deps.user_session_config or {}
    day_start_hour = cfg.get("day_start_hour", 0)
    day_tz = cfg.get("timezone", "UTC")

    range_start, range_end = day_range_utc(d, day_start_hour, day_tz)
    range_start_aware = range_start.replace(tzinfo=timezone.utc)
    range_end_aware = range_end.replace(tzinfo=timezone.utc)

    events = await ctx.deps.activity_repo.get_by_time_range(
        ctx.deps.user_id, range_start_aware, range_end_aware, limit=100_000, offset=0,
    )

    if not events:
        await _emit(ctx, "tool_result", {"name": "get_activity_sessions", "summary": "No activity data found"})
        return []

    latest_day_end = datetime.combine(
        events[-1].timestamp.date(), time.max, tzinfo=timezone.utc,
    )
    cap_time = min(datetime.now(timezone.utc), latest_day_end)
    sessions = compute_sessions(
        events,
        cap_time,
        merge_gap_seconds=cfg.get("merge_gap_seconds", 300),
        min_session_seconds=cfg.get("min_session_seconds", 5),
        noise_threshold_seconds=cfg.get("noise_threshold_seconds", 120),
        day_start_hour=day_start_hour,
        day_timezone=day_tz,
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
    await _emit(ctx, "tool_call", {"name": "get_existing_timeline", "args": {"date": target_date}})

    try:
        d = date.fromisoformat(target_date)
    except ValueError:
        return [{"error": f"Invalid date format: {target_date}. Use YYYY-MM-DD."}]

    cfg = ctx.deps.user_session_config or {}
    day_start_hour = cfg.get("day_start_hour", 0)
    day_tz = cfg.get("timezone", "UTC")

    range_start, range_end = day_range_utc(d, day_start_hour, day_tz)
    range_start_aware = range_start.replace(tzinfo=timezone.utc)
    range_end_aware = range_end.replace(tzinfo=timezone.utc)

    entries = await ctx.deps.timeline_repo.get_by_time_range(
        ctx.deps.user_id, range_start_aware, range_end_aware, limit=500, offset=0,
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


@dataclass
class _TimeSlot:
    start: datetime
    end: datetime
    label: str
    is_proposed: bool
    is_user_edited: bool


def _detect_overlaps(
    proposed: list[TimelineEntryBulkItem],
    existing_untouched: list,
) -> list[str]:
    slots: list[_TimeSlot] = []

    for item in proposed:
        slots.append(_TimeSlot(
            start=item.start_time,
            end=item.end_time,
            label=item.label or "Untitled",
            is_proposed=True,
            is_user_edited=False,
        ))

    for entry in existing_untouched:
        slots.append(_TimeSlot(
            start=entry.start_time,
            end=entry.end_time,
            label=entry.label or "Untitled",
            is_proposed=False,
            is_user_edited=getattr(entry, "edited_by_user", False),
        ))

    slots.sort(key=lambda s: s.start)

    errors: list[str] = []
    active: list[_TimeSlot] = []
    for slot in slots:
        active = [s for s in active if s.end > slot.start]
        for other in active:
            if not other.is_proposed and not slot.is_proposed:
                continue

            overlap_seconds = (min(other.end, slot.end) - max(other.start, slot.start)).total_seconds()
            if overlap_seconds <= 0:
                continue
            overlap_min = int(overlap_seconds // 60)

            a, b = other, slot
            a_start = a.start.strftime("%H:%M")
            a_end = a.end.strftime("%H:%M")
            b_start = b.start.strftime("%H:%M")
            b_end = b.end.strftime("%H:%M")

            if b.is_user_edited:
                errors.append(
                    f"OVERLAP: '{a.label}' ({a_start}-{a_end}) overlaps with "
                    f"'{b.label}' ({b_start}-{b_end}, USER-EDITED, cannot be modified) "
                    f"by {overlap_min}min. You must adjust '{a.label}'."
                )
            elif a.is_user_edited:
                errors.append(
                    f"OVERLAP: '{a.label}' ({a_start}-{a_end}, USER-EDITED, cannot be modified) "
                    f"overlaps with '{b.label}' ({b_start}-{b_end}) "
                    f"by {overlap_min}min. You must adjust '{b.label}'."
                )
            else:
                errors.append(
                    f"OVERLAP: '{a.label}' ({a_start}-{a_end}) overlaps with "
                    f"'{b.label}' ({b_start}-{b_end}) "
                    f"by {overlap_min}min. Adjust end_time of '{a.label}' or start_time of '{b.label}'."
                )

        active.append(slot)

    return errors


async def save_timeline_entries(ctx: RunContext[AgentDeps], entries: list[TimelineEntry]) -> dict:
    await _emit(ctx, "tool_call", {"name": "save_timeline_entries", "args": {"count": len(entries)}})

    from uuid import UUID

    cfg = ctx.deps.user_session_config or {}
    day_start_hour = cfg.get("day_start_hour", 0)
    day_tz = cfg.get("timezone", "UTC")

    bulk_items = []
    for entry in entries:
        try:
            start_time = datetime.fromisoformat(entry.start_time)
            end_time = datetime.fromisoformat(entry.end_time)
            entry_date = logical_date_for_timestamp(start_time, day_start_hour, day_tz)

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

    all_starts = [item.start_time for item in bulk_items]
    all_ends = [item.end_time for item in bulk_items]
    range_start = min(all_starts)
    range_end = max(all_ends)

    existing_entries = await ctx.deps.timeline_repo.get_by_time_range(
        ctx.deps.user_id,
        range_start,
        range_end,
        limit=500,
        offset=0,
        include_overlap=True,
    )

    proposed_ids = {item.id for item in bulk_items if item.id is not None}
    existing_untouched = [e for e in existing_entries if e.id not in proposed_ids]

    overlaps = _detect_overlaps(bulk_items, existing_untouched)
    if overlaps:
        await _emit(ctx, "tool_result", {
            "name": "save_timeline_entries",
            "summary": f"Rejected: {len(overlaps)} overlapping entries",
        })
        return {
            "created": 0,
            "updated": 0,
            "skipped": 0,
            "errors": overlaps,
        }

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


class MemoryInput(BaseModel):
    content: str = Field(description="The classification rule or correction to remember for future timeline generation")


async def save_memory(ctx: RunContext[AgentDeps], memory: MemoryInput) -> dict:
    await _emit(ctx, "tool_call", {"name": "save_memory", "args": {"content": memory.content}})

    if not ctx.deps.memory_repo:
        return {"error": "Memory storage not available"}

    await ctx.deps.memory_repo.create(
        user_id=ctx.deps.user_id,
        content=memory.content,
        source="chat",
    )

    await _emit(ctx, "tool_result", {"name": "save_memory", "summary": "Memory saved"})
    return {"status": "saved", "content": memory.content}
