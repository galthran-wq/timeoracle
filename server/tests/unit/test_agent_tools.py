import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agent.deps import AgentDeps
from src.agent.tools import (
    TimelineEntry,
    get_activity_sessions,
    get_existing_timeline,
    save_timeline_entries,
)


@dataclass
class FakeEvent:
    event_type: str
    timestamp: datetime
    app_name: str = "Firefox"
    window_title: str = "Home"
    url: str | None = None


@dataclass
class FakeTimelineEntry:
    id: uuid.UUID
    label: str
    category: str | None
    start_time: datetime
    end_time: datetime
    edited_by_user: bool
    source: str


def _make_ctx(
    activity_events=None,
    timeline_entries=None,
    bulk_upsert_result=(0, 0, 0, []),
    user_session_config=None,
    event_queue=None,
):
    user_id = uuid.uuid4()

    activity_repo = MagicMock()
    activity_repo.get_by_time_range = AsyncMock(return_value=activity_events or [])

    timeline_repo = MagicMock()
    timeline_repo.get_by_time_range = AsyncMock(return_value=timeline_entries or [])
    timeline_repo.bulk_upsert = AsyncMock(return_value=bulk_upsert_result)

    deps = AgentDeps(
        user_id=user_id,
        session=MagicMock(),
        activity_repo=activity_repo,
        timeline_repo=timeline_repo,
        chat_repo=MagicMock(),
        target_date=date(2026, 3, 1),
        chat_id=uuid.uuid4(),
        user_session_config=user_session_config,
        event_queue=event_queue,
    )

    ctx = MagicMock()
    ctx.deps = deps
    return ctx


class TestGetActivitySessions:
    async def test_returns_empty_for_no_events(self):
        ctx = _make_ctx(activity_events=[])
        result = await get_activity_sessions(ctx, "2026-03-01")
        assert result == []

    async def test_returns_sessions_from_events(self):
        base = datetime(2026, 3, 1, 14, 0, tzinfo=timezone.utc)
        events = [
            FakeEvent("active_window", base, "VSCode", "main.py"),
            FakeEvent("active_window", base + timedelta(minutes=30), "Firefox", "GitHub"),
            FakeEvent("active_window", base + timedelta(minutes=60), "Terminal", "bash"),
        ]
        ctx = _make_ctx(activity_events=events)
        result = await get_activity_sessions(ctx, "2026-03-01")

        assert len(result) >= 2
        assert result[0]["app_name"] == "VSCode"
        assert "start_time" in result[0]
        assert "end_time" in result[0]
        assert "date" in result[0]

    async def test_invalid_date_returns_error(self):
        ctx = _make_ctx()
        result = await get_activity_sessions(ctx, "not-a-date")
        assert len(result) == 1
        assert "error" in result[0]

    async def test_uses_session_config(self):
        base = datetime(2026, 3, 1, 14, 0, tzinfo=timezone.utc)
        events = [
            FakeEvent("active_window", base, "VSCode", "main.py"),
            FakeEvent("active_window", base + timedelta(minutes=30), "Firefox", "End"),
        ]
        ctx = _make_ctx(
            activity_events=events,
            user_session_config={"merge_gap_seconds": 600},
        )
        result = await get_activity_sessions(ctx, "2026-03-01")
        assert len(result) >= 1

    async def test_queries_correct_time_range(self):
        ctx = _make_ctx()
        await get_activity_sessions(ctx, "2026-03-01")

        call_args = ctx.deps.activity_repo.get_by_time_range.call_args
        start = call_args[0][1]
        end = call_args[0][2]
        assert start == datetime(2026, 3, 1, 0, 0, tzinfo=timezone.utc)
        assert end == datetime(2026, 3, 2, 0, 0, tzinfo=timezone.utc)

    async def test_emits_events_to_queue(self):
        import asyncio
        queue = asyncio.Queue()
        ctx = _make_ctx(event_queue=queue)
        await get_activity_sessions(ctx, "2026-03-01")

        events = []
        while not queue.empty():
            events.append(await queue.get())
        assert any(e[0] == "tool_call" for e in events)
        assert any(e[0] == "tool_result" for e in events)


class TestGetExistingTimeline:
    async def test_returns_empty_for_no_entries(self):
        ctx = _make_ctx(timeline_entries=[])
        result = await get_existing_timeline(ctx, "2026-03-01")
        assert result == []

    async def test_returns_formatted_entries(self):
        entry_id = uuid.uuid4()
        base = datetime(2026, 3, 1, 14, 0, tzinfo=timezone.utc)
        entries = [
            FakeTimelineEntry(
                id=entry_id,
                label="Coding in VSCode",
                category="Work",
                start_time=base,
                end_time=base + timedelta(hours=1),
                edited_by_user=False,
                source="ai_generated",
            )
        ]
        ctx = _make_ctx(timeline_entries=entries)
        result = await get_existing_timeline(ctx, "2026-03-01")

        assert len(result) == 1
        assert result[0]["id"] == str(entry_id)
        assert result[0]["label"] == "Coding in VSCode"
        assert result[0]["edited_by_user"] is False

    async def test_invalid_date_returns_error(self):
        ctx = _make_ctx()
        result = await get_existing_timeline(ctx, "garbage")
        assert len(result) == 1
        assert "error" in result[0]


class TestSaveTimelineEntries:
    async def test_saves_valid_entries(self):
        ctx = _make_ctx(bulk_upsert_result=(2, 0, 0, []))
        entries = [
            TimelineEntry(
                date="2026-03-01",
                start_time="2026-03-01T14:00:00+00:00",
                end_time="2026-03-01T15:00:00+00:00",
                label="Coding",
                category="Work",
                color="#3B82F6",
                confidence=0.9,
            ),
            TimelineEntry(
                date="2026-03-01",
                start_time="2026-03-01T15:00:00+00:00",
                end_time="2026-03-01T16:00:00+00:00",
                label="Email",
                category="Communication",
                color="#8B5CF6",
                confidence=0.85,
            ),
        ]
        result = await save_timeline_entries(ctx, entries)

        assert result["created"] == 2
        ctx.deps.timeline_repo.bulk_upsert.assert_called_once()
        call_args = ctx.deps.timeline_repo.bulk_upsert.call_args
        assert len(call_args[0][1]) == 2  # 2 bulk items
        assert call_args[1]["chat_id"] == ctx.deps.chat_id

    async def test_skips_invalid_entries(self):
        ctx = _make_ctx(bulk_upsert_result=(1, 0, 0, []))
        entries = [
            TimelineEntry(
                date="not-a-date",
                start_time="garbage",
                end_time="garbage",
                label="Bad",
            ),
            TimelineEntry(
                date="2026-03-01",
                start_time="2026-03-01T14:00:00+00:00",
                end_time="2026-03-01T15:00:00+00:00",
                label="Good",
            ),
        ]
        result = await save_timeline_entries(ctx, entries)
        call_args = ctx.deps.timeline_repo.bulk_upsert.call_args
        assert len(call_args[0][1]) == 1

    async def test_returns_error_when_all_invalid(self):
        ctx = _make_ctx()
        entries = [
            TimelineEntry(
                date="bad",
                start_time="bad",
                end_time="bad",
                label="Invalid",
            ),
        ]
        result = await save_timeline_entries(ctx, entries)
        assert result["created"] == 0
        assert "No valid entries" in result["errors"]
        ctx.deps.timeline_repo.bulk_upsert.assert_not_called()

    async def test_passes_entry_id_for_updates(self):
        entry_id = uuid.uuid4()
        ctx = _make_ctx(bulk_upsert_result=(0, 1, 0, []))
        entries = [
            TimelineEntry(
                id=str(entry_id),
                date="2026-03-01",
                start_time="2026-03-01T14:00:00+00:00",
                end_time="2026-03-01T15:00:00+00:00",
                label="Updated",
            ),
        ]
        result = await save_timeline_entries(ctx, entries)
        assert result["updated"] == 1
        call_args = ctx.deps.timeline_repo.bulk_upsert.call_args
        bulk_item = call_args[0][1][0]
        assert bulk_item.id == entry_id
