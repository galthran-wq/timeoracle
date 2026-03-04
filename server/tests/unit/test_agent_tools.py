import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agent.deps import AgentDeps
from src.agent.tools import (
    TimelineEntry,
    _detect_overlaps,
    get_activity_sessions,
    get_existing_timeline,
    save_timeline_entries,
)
from src.schemas.timeline_entries import TimelineEntryBulkItem


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
                start_time="2026-03-01T14:00:00+00:00",
                end_time="2026-03-01T15:00:00+00:00",
                label="Coding",
                category="Work",
                description="Test description",
            ),
            TimelineEntry(
                start_time="2026-03-01T15:00:00+00:00",
                end_time="2026-03-01T16:00:00+00:00",
                label="Email",
                category="Communication",
                description="Test description",
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
                start_time="garbage",
                end_time="garbage",
                label="Bad",
                description="Test",
            ),
            TimelineEntry(
                start_time="2026-03-01T14:00:00+00:00",
                end_time="2026-03-01T15:00:00+00:00",
                label="Good",
                description="Test",
            ),
        ]
        result = await save_timeline_entries(ctx, entries)
        call_args = ctx.deps.timeline_repo.bulk_upsert.call_args
        assert len(call_args[0][1]) == 1

    async def test_returns_error_when_all_invalid(self):
        ctx = _make_ctx()
        entries = [
            TimelineEntry(
                start_time="bad",
                end_time="bad",
                label="Invalid",
                description="Test",
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
                start_time="2026-03-01T14:00:00+00:00",
                end_time="2026-03-01T15:00:00+00:00",
                label="Updated",
                description="Test",
            ),
        ]
        result = await save_timeline_entries(ctx, entries)
        assert result["updated"] == 1
        call_args = ctx.deps.timeline_repo.bulk_upsert.call_args
        bulk_item = call_args[0][1][0]
        assert bulk_item.id == entry_id


@dataclass
class FakeExistingEntry:
    id: uuid.UUID
    label: str
    start_time: datetime
    end_time: datetime
    edited_by_user: bool = False


def _bulk_item(label, start_h, start_m, end_h, end_m, entry_id=None):
    return TimelineEntryBulkItem(
        id=entry_id,
        date=date(2026, 3, 1),
        start_time=datetime(2026, 3, 1, start_h, start_m, tzinfo=timezone.utc),
        end_time=datetime(2026, 3, 1, end_h, end_m, tzinfo=timezone.utc),
        label=label,
    )


class TestDetectOverlaps:
    def test_no_overlaps(self):
        items = [
            _bulk_item("Coding", 9, 0, 10, 0),
            _bulk_item("Email", 10, 0, 11, 0),
        ]
        assert _detect_overlaps(items, []) == []

    def test_adjacent_entries_ok(self):
        items = [
            _bulk_item("Coding", 9, 0, 10, 0),
            _bulk_item("Email", 10, 0, 11, 0),
        ]
        assert _detect_overlaps(items, []) == []

    def test_gap_between_entries_ok(self):
        items = [
            _bulk_item("Coding", 9, 0, 10, 0),
            _bulk_item("Email", 10, 30, 11, 0),
        ]
        assert _detect_overlaps(items, []) == []

    def test_detects_overlap_between_proposed(self):
        items = [
            _bulk_item("Coding", 9, 0, 10, 30),
            _bulk_item("Email", 10, 0, 11, 0),
        ]
        errors = _detect_overlaps(items, [])
        assert len(errors) == 1
        assert "Coding" in errors[0]
        assert "Email" in errors[0]
        assert "OVERLAP" in errors[0]

    def test_detects_overlap_with_existing_untouched(self):
        proposed = [_bulk_item("Coding", 9, 0, 10, 30)]
        existing = [FakeExistingEntry(
            id=uuid.uuid4(),
            label="Meeting",
            start_time=datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 3, 1, 11, 0, tzinfo=timezone.utc),
        )]
        errors = _detect_overlaps(proposed, existing)
        assert len(errors) == 1
        assert "Coding" in errors[0]
        assert "Meeting" in errors[0]

    def test_ignores_overlap_between_two_existing(self):
        existing = [
            FakeExistingEntry(
                id=uuid.uuid4(), label="A",
                start_time=datetime(2026, 3, 1, 9, 0, tzinfo=timezone.utc),
                end_time=datetime(2026, 3, 1, 10, 30, tzinfo=timezone.utc),
            ),
            FakeExistingEntry(
                id=uuid.uuid4(), label="B",
                start_time=datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc),
                end_time=datetime(2026, 3, 1, 11, 0, tzinfo=timezone.utc),
            ),
        ]
        proposed = [_bulk_item("Coding", 12, 0, 13, 0)]
        assert _detect_overlaps(proposed, existing) == []

    def test_user_edited_entry_message(self):
        proposed = [_bulk_item("Coding", 9, 0, 10, 30)]
        existing = [FakeExistingEntry(
            id=uuid.uuid4(),
            label="Meeting",
            start_time=datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 3, 1, 11, 0, tzinfo=timezone.utc),
            edited_by_user=True,
        )]
        errors = _detect_overlaps(proposed, existing)
        assert len(errors) == 1
        assert "USER-EDITED" in errors[0]
        assert "cannot be modified" in errors[0]
        assert "You must adjust 'Coding'" in errors[0]

    def test_overlap_includes_duration(self):
        items = [
            _bulk_item("Coding", 9, 0, 10, 30),
            _bulk_item("Email", 10, 0, 11, 0),
        ]
        errors = _detect_overlaps(items, [])
        assert "30min" in errors[0]


class TestSaveTimelineEntriesOverlapValidation:
    async def test_rejects_overlapping_new_entries(self):
        ctx = _make_ctx()
        entries = [
            TimelineEntry(
                start_time="2026-03-01T09:00:00+00:00",
                end_time="2026-03-01T10:30:00+00:00",
                label="Coding",
                description="Test",
            ),
            TimelineEntry(
                start_time="2026-03-01T10:00:00+00:00",
                end_time="2026-03-01T11:00:00+00:00",
                label="Email",
                description="Test",
            ),
        ]
        result = await save_timeline_entries(ctx, entries)
        assert result["created"] == 0
        assert len(result["errors"]) > 0
        assert "Coding" in result["errors"][0]
        assert "Email" in result["errors"][0]
        ctx.deps.timeline_repo.bulk_upsert.assert_not_called()

    async def test_accepts_non_overlapping_entries(self):
        ctx = _make_ctx(bulk_upsert_result=(2, 0, 0, []))
        entries = [
            TimelineEntry(
                start_time="2026-03-01T09:00:00+00:00",
                end_time="2026-03-01T10:00:00+00:00",
                label="Coding",
                description="Test",
            ),
            TimelineEntry(
                start_time="2026-03-01T10:00:00+00:00",
                end_time="2026-03-01T11:00:00+00:00",
                label="Email",
                description="Test",
            ),
        ]
        result = await save_timeline_entries(ctx, entries)
        assert result["created"] == 2
        ctx.deps.timeline_repo.bulk_upsert.assert_called_once()

    async def test_rejects_overlap_with_existing_db_entry(self):
        existing_id = uuid.uuid4()
        existing_entry = FakeExistingEntry(
            id=existing_id,
            label="Meeting",
            start_time=datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 3, 1, 11, 0, tzinfo=timezone.utc),
        )
        ctx = _make_ctx()
        ctx.deps.timeline_repo.get_by_time_range = AsyncMock(return_value=[existing_entry])

        entries = [
            TimelineEntry(
                start_time="2026-03-01T10:30:00+00:00",
                end_time="2026-03-01T11:30:00+00:00",
                label="Coding",
                description="Test",
            ),
        ]
        result = await save_timeline_entries(ctx, entries)
        assert result["created"] == 0
        assert len(result["errors"]) > 0
        ctx.deps.timeline_repo.bulk_upsert.assert_not_called()
