import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.postgres.users import UserModel
from src.repositories.activity_events import ActivityEventRepository
from src.repositories.activity_sessions import ActivitySessionRepository
from src.schemas.activity_events import ActivityEventCreate, ActivityEventType
from src.services.activity_session_generator import ActivitySessionGenerator


def _event(
    event_type: str,
    timestamp: datetime,
    app_name: str = "Firefox",
    window_title: str = "Home",
    url: str | None = None,
) -> ActivityEventCreate:
    return ActivityEventCreate(
        client_event_id=uuid.uuid4(),
        timestamp=timestamp,
        event_type=event_type,
        app_name=app_name,
        window_title=window_title,
        url=url,
    )


async def _seed_events(
    repo: ActivityEventRepository, user_id: uuid.UUID, events: list[ActivityEventCreate],
) -> None:
    await repo.bulk_create(user_id, events)


class TestActivitySessionGenerator:
    async def test_consecutive_windows_create_sessions(
        self, db_session: AsyncSession, test_user: UserModel,
    ):
        activity_repo = ActivityEventRepository(db_session)
        session_repo = ActivitySessionRepository(db_session)
        generator = ActivitySessionGenerator(activity_repo, session_repo)

        base = datetime(2026, 2, 23, 14, 0, tzinfo=timezone.utc)
        events = [
            _event("active_window", base, app_name="Firefox", window_title="GitHub"),
            _event("active_window", base + timedelta(minutes=15), app_name="VSCode", window_title="main.py"),
            _event("active_window", base + timedelta(minutes=45), app_name="Chrome", window_title="Docs"),
        ]
        await _seed_events(activity_repo, test_user.id, events)

        count = await generator.generate_for_date(test_user.id, date(2026, 2, 23))
        assert count == 3

        sessions = await session_repo.get_by_date_range(
            test_user.id, date(2026, 2, 23), date(2026, 2, 23), limit=100, offset=0,
        )
        assert len(sessions) == 3

        assert sessions[0].app_name == "Firefox"
        assert sessions[0].start_time == base
        assert sessions[0].end_time == base + timedelta(minutes=15)

        assert sessions[1].app_name == "VSCode"
        assert sessions[1].start_time == base + timedelta(minutes=15)
        assert sessions[1].end_time == base + timedelta(minutes=45)

        assert sessions[2].app_name == "Chrome"

    async def test_idle_gap_ends_session(
        self, db_session: AsyncSession, test_user: UserModel,
    ):
        activity_repo = ActivityEventRepository(db_session)
        session_repo = ActivitySessionRepository(db_session)
        generator = ActivitySessionGenerator(activity_repo, session_repo)

        base = datetime(2026, 2, 23, 14, 0, tzinfo=timezone.utc)
        events = [
            _event("active_window", base, app_name="VSCode", window_title="main.py"),
            _event("idle_start", base + timedelta(minutes=30)),
            _event("idle_end", base + timedelta(minutes=45)),
            _event("active_window", base + timedelta(minutes=45), app_name="Chrome", window_title="Search"),
        ]
        await _seed_events(activity_repo, test_user.id, events)

        count = await generator.generate_for_date(test_user.id, date(2026, 2, 23))
        assert count == 2

        sessions = await session_repo.get_by_date_range(
            test_user.id, date(2026, 2, 23), date(2026, 2, 23), limit=100, offset=0,
        )
        assert sessions[0].app_name == "VSCode"
        assert sessions[0].end_time == base + timedelta(minutes=30)

        assert sessions[1].app_name == "Chrome"
        assert sessions[1].start_time == base + timedelta(minutes=45)

    async def test_same_app_heartbeats_merge(
        self, db_session: AsyncSession, test_user: UserModel,
    ):
        activity_repo = ActivityEventRepository(db_session)
        session_repo = ActivitySessionRepository(db_session)
        generator = ActivitySessionGenerator(activity_repo, session_repo)

        base = datetime(2026, 2, 23, 14, 0, tzinfo=timezone.utc)
        events = [
            _event("active_window", base, app_name="VSCode", window_title="main.py"),
            _event("active_window", base + timedelta(minutes=5), app_name="VSCode", window_title="utils.py"),
            _event("active_window", base + timedelta(minutes=10), app_name="VSCode", window_title="test.py"),
            _event("active_window", base + timedelta(minutes=15), app_name="Firefox", window_title="Docs"),
        ]
        await _seed_events(activity_repo, test_user.id, events)

        count = await generator.generate_for_date(test_user.id, date(2026, 2, 23))
        assert count == 2

        sessions = await session_repo.get_by_date_range(
            test_user.id, date(2026, 2, 23), date(2026, 2, 23), limit=100, offset=0,
        )
        assert sessions[0].app_name == "VSCode"
        assert sessions[0].start_time == base
        assert sessions[0].end_time == base + timedelta(minutes=15)
        assert set(sessions[0].window_titles) == {"main.py", "utils.py", "test.py"}

    async def test_short_sessions_dropped(
        self, db_session: AsyncSession, test_user: UserModel,
    ):
        activity_repo = ActivityEventRepository(db_session)
        session_repo = ActivitySessionRepository(db_session)
        generator = ActivitySessionGenerator(activity_repo, session_repo)

        base = datetime(2026, 2, 23, 14, 0, tzinfo=timezone.utc)
        events = [
            _event("active_window", base, app_name="Firefox", window_title="Home"),
            # 2-second alt-tab to Terminal
            _event("active_window", base + timedelta(seconds=2), app_name="Terminal", window_title="bash"),
            # Back to Firefox
            _event("active_window", base + timedelta(seconds=4), app_name="Firefox", window_title="Home"),
            _event("active_window", base + timedelta(minutes=10), app_name="Chrome", window_title="Search"),
        ]
        await _seed_events(activity_repo, test_user.id, events)

        count = await generator.generate_for_date(test_user.id, date(2026, 2, 23))

        sessions = await session_repo.get_by_date_range(
            test_user.id, date(2026, 2, 23), date(2026, 2, 23), limit=100, offset=0,
        )
        # Terminal session (2s) dropped; the two Firefox segments merge
        app_names = [s.app_name for s in sessions]
        assert "Terminal" not in app_names
        assert sessions[0].app_name == "Firefox"

    async def test_noise_sessions_dropped_when_finalized(
        self, db_session: AsyncSession, test_user: UserModel,
    ):
        """Short sessions (< 2 min) that are past the merge window get removed."""
        activity_repo = ActivityEventRepository(db_session)
        session_repo = ActivitySessionRepository(db_session)
        generator = ActivitySessionGenerator(activity_repo, session_repo)

        # Use a past date so all sessions are finalized
        base = datetime(2026, 2, 22, 14, 0, tzinfo=timezone.utc)
        events = [
            # Long Chrome session (10 min) — kept
            _event("active_window", base, app_name="Chrome", window_title="YouTube"),
            _event("active_window", base + timedelta(minutes=10), app_name="Chrome", window_title="GitHub"),
            # 30-second Telegram check — should be dropped (short + finalized)
            _event("active_window", base + timedelta(minutes=20), app_name="Telegram", window_title="Chat"),
            # 5-second terminal glance — should be dropped
            _event("active_window", base + timedelta(minutes=20, seconds=30), app_name="Terminal", window_title="bash"),
            _event("active_window", base + timedelta(minutes=20, seconds=35), app_name="Terminal", window_title="bash"),
            # Back to Chrome for 15 min — kept
            _event("active_window", base + timedelta(minutes=20, seconds=40), app_name="Chrome", window_title="Docs"),
            _event("active_window", base + timedelta(minutes=35), app_name="Firefox", window_title="End"),
        ]
        await _seed_events(activity_repo, test_user.id, events)

        await generator.generate_for_date(test_user.id, date(2026, 2, 22))

        sessions = await session_repo.get_by_date_range(
            test_user.id, date(2026, 2, 22), date(2026, 2, 22), limit=100, offset=0,
        )
        app_names = [s.app_name for s in sessions]
        # Chrome merges into one big session; Telegram and Terminal are noise
        assert "Telegram" not in app_names, f"Telegram should be dropped: {app_names}"
        assert "Terminal" not in app_names, f"Terminal should be dropped: {app_names}"
        assert "Chrome" in app_names

    async def test_regeneration_replaces_old_sessions(
        self, db_session: AsyncSession, test_user: UserModel,
    ):
        activity_repo = ActivityEventRepository(db_session)
        session_repo = ActivitySessionRepository(db_session)
        generator = ActivitySessionGenerator(activity_repo, session_repo)

        base = datetime(2026, 2, 23, 14, 0, tzinfo=timezone.utc)
        events = [
            _event("active_window", base, app_name="Firefox", window_title="Home"),
            _event("active_window", base + timedelta(minutes=10), app_name="Chrome", window_title="Search"),
        ]
        await _seed_events(activity_repo, test_user.id, events)

        count1 = await generator.generate_for_date(test_user.id, date(2026, 2, 23))
        assert count1 == 2

        # Re-generate should replace, not duplicate
        count2 = await generator.generate_for_date(test_user.id, date(2026, 2, 23))
        assert count2 == 2

        total = await session_repo.count_by_date_range(
            test_user.id, date(2026, 2, 23), date(2026, 2, 23),
        )
        assert total == 2

    async def test_empty_day_returns_zero(
        self, db_session: AsyncSession, test_user: UserModel,
    ):
        activity_repo = ActivityEventRepository(db_session)
        session_repo = ActivitySessionRepository(db_session)
        generator = ActivitySessionGenerator(activity_repo, session_repo)

        count = await generator.generate_for_date(test_user.id, date(2026, 2, 23))
        assert count == 0

    async def test_single_event_capped_at_end_of_day(
        self, db_session: AsyncSession, test_user: UserModel,
    ):
        activity_repo = ActivityEventRepository(db_session)
        session_repo = ActivitySessionRepository(db_session)
        generator = ActivitySessionGenerator(activity_repo, session_repo)

        # Use a recent past date to ensure day_end < now(), so cap = day_end
        target = date(2026, 2, 22)
        base = datetime(2026, 2, 22, 22, 0, tzinfo=timezone.utc)
        events = [
            _event("active_window", base, app_name="Firefox", window_title="Home"),
        ]
        await _seed_events(activity_repo, test_user.id, events)

        count = await generator.generate_for_date(test_user.id, target)
        assert count == 1

        sessions = await session_repo.get_by_date_range(
            test_user.id, target, target, limit=100, offset=0,
        )
        assert len(sessions) == 1
        # end_time should be capped at end of day (not equal to start_time)
        assert sessions[0].end_time > sessions[0].start_time
        day_end = datetime(2026, 2, 22, 23, 59, 59, 999999, tzinfo=timezone.utc)
        assert sessions[0].end_time <= day_end

    async def test_window_titles_collected(
        self, db_session: AsyncSession, test_user: UserModel,
    ):
        activity_repo = ActivityEventRepository(db_session)
        session_repo = ActivitySessionRepository(db_session)
        generator = ActivitySessionGenerator(activity_repo, session_repo)

        base = datetime(2026, 2, 23, 14, 0, tzinfo=timezone.utc)
        events = [
            _event("active_window", base, app_name="Firefox", window_title="Tab 1", url="https://example.com"),
            _event("active_window", base + timedelta(minutes=5), app_name="Firefox", window_title="Tab 2"),
            _event("active_window", base + timedelta(minutes=10), app_name="Firefox", window_title="Tab 1"),
            _event("active_window", base + timedelta(minutes=15), app_name="Chrome", window_title="Docs"),
        ]
        await _seed_events(activity_repo, test_user.id, events)

        await generator.generate_for_date(test_user.id, date(2026, 2, 23))

        sessions = await session_repo.get_by_date_range(
            test_user.id, date(2026, 2, 23), date(2026, 2, 23), limit=100, offset=0,
        )
        firefox = sessions[0]
        assert firefox.window_title == "Tab 1"
        assert set(firefox.window_titles) == {"Tab 1", "Tab 2"}
        assert firefox.url == "https://example.com"


    async def test_merge_gap_exact_boundary(
        self, db_session: AsyncSession, test_user: UserModel,
    ):
        """Gap of exactly 300s merges (<=), gap of 301s does not."""
        activity_repo = ActivityEventRepository(db_session)
        session_repo = ActivitySessionRepository(db_session)
        generator = ActivitySessionGenerator(activity_repo, session_repo)

        base = datetime(2026, 2, 22, 14, 0, tzinfo=timezone.utc)
        events = [
            # Chrome block A: 14:00 - 14:05
            _event("active_window", base, app_name="Chrome", window_title="Tab 1"),
            _event("active_window", base + timedelta(minutes=5), app_name="Other", window_title="x"),
            # Chrome block B at 14:10 (gap from Chrome A end at 14:05 = 300s exactly — merges)
            _event("active_window", base + timedelta(minutes=10), app_name="Chrome", window_title="Tab 2"),
            _event("active_window", base + timedelta(minutes=15), app_name="Other", window_title="y"),
            # Chrome block C at 14:20:01 (gap from merged Chrome end at 14:15 = 301s — separate)
            _event("active_window", base + timedelta(minutes=20, seconds=1), app_name="Chrome", window_title="Tab 3"),
            _event("active_window", base + timedelta(minutes=25), app_name="Firefox", window_title="End"),
        ]
        await _seed_events(activity_repo, test_user.id, events)

        await generator.generate_for_date(test_user.id, date(2026, 2, 22))

        sessions = await session_repo.get_by_date_range(
            test_user.id, date(2026, 2, 22), date(2026, 2, 22), limit=100, offset=0,
        )
        chrome_sessions = [s for s in sessions if s.app_name == "Chrome"]
        assert len(chrome_sessions) == 2
        assert chrome_sessions[0].start_time == base
        assert chrome_sessions[0].end_time == base + timedelta(minutes=15)
        assert chrome_sessions[1].start_time == base + timedelta(minutes=20, seconds=1)

    async def test_noise_threshold_exact_boundary(
        self, db_session: AsyncSession, test_user: UserModel,
    ):
        """Session of exactly 120s is kept (not < 120); 119s is dropped."""
        activity_repo = ActivityEventRepository(db_session)
        session_repo = ActivitySessionRepository(db_session)
        generator = ActivitySessionGenerator(activity_repo, session_repo)

        base = datetime(2026, 2, 22, 14, 0, tzinfo=timezone.utc)
        events = [
            # Anchor session
            _event("active_window", base, app_name="VSCode", window_title="main.py"),
            # 119s session — should be dropped (finalized + short)
            _event("active_window", base + timedelta(minutes=30), app_name="Short119", window_title="x"),
            _event("active_window", base + timedelta(minutes=30, seconds=119), app_name="Filler", window_title="y"),
            # 120s session — should be kept (120 < 120 is false)
            _event("active_window", base + timedelta(minutes=40), app_name="Exact120", window_title="z"),
            _event("active_window", base + timedelta(minutes=42), app_name="Firefox", window_title="End"),
        ]
        await _seed_events(activity_repo, test_user.id, events)

        await generator.generate_for_date(test_user.id, date(2026, 2, 22))

        sessions = await session_repo.get_by_date_range(
            test_user.id, date(2026, 2, 22), date(2026, 2, 22), limit=100, offset=0,
        )
        app_names = [s.app_name for s in sessions]
        assert "Short119" not in app_names
        assert "Exact120" in app_names

    async def test_cross_midnight_session_split(
        self, db_session: AsyncSession, test_user: UserModel,
    ):
        """A session spanning midnight is split into two halves with correct dates."""
        activity_repo = ActivityEventRepository(db_session)
        session_repo = ActivitySessionRepository(db_session)
        generator = ActivitySessionGenerator(activity_repo, session_repo)

        events = [
            _event("active_window", datetime(2026, 2, 22, 23, 50, tzinfo=timezone.utc),
                   app_name="VSCode", window_title="main.py"),
            _event("active_window", datetime(2026, 2, 23, 0, 10, tzinfo=timezone.utc),
                   app_name="Chrome", window_title="Docs"),
            _event("active_window", datetime(2026, 2, 23, 0, 20, tzinfo=timezone.utc),
                   app_name="Firefox", window_title="End"),
        ]
        await _seed_events(activity_repo, test_user.id, events)

        timestamps = [e.timestamp for e in events]
        await generator.generate_incremental(test_user.id, timestamps)

        sessions_22 = await session_repo.get_by_date_range(
            test_user.id, date(2026, 2, 22), date(2026, 2, 22), limit=100, offset=0,
        )
        sessions_23 = await session_repo.get_by_date_range(
            test_user.id, date(2026, 2, 23), date(2026, 2, 23), limit=100, offset=0,
        )

        # VSCode 23:50→00:10 split at midnight
        vscode_22 = [s for s in sessions_22 if s.app_name == "VSCode"]
        assert len(vscode_22) == 1
        assert vscode_22[0].start_time == datetime(2026, 2, 22, 23, 50, tzinfo=timezone.utc)
        assert vscode_22[0].end_time == datetime(2026, 2, 23, 0, 0, tzinfo=timezone.utc)
        assert vscode_22[0].date == date(2026, 2, 22)

        vscode_23 = [s for s in sessions_23 if s.app_name == "VSCode"]
        assert len(vscode_23) == 1
        assert vscode_23[0].start_time == datetime(2026, 2, 23, 0, 0, tzinfo=timezone.utc)
        assert vscode_23[0].end_time == datetime(2026, 2, 23, 0, 10, tzinfo=timezone.utc)
        assert vscode_23[0].date == date(2026, 2, 23)

    async def test_url_merge_keeps_first_non_null(
        self, db_session: AsyncSession, test_user: UserModel,
    ):
        """When merging same-app sessions, the first non-null URL wins."""
        activity_repo = ActivityEventRepository(db_session)
        session_repo = ActivitySessionRepository(db_session)
        generator = ActivitySessionGenerator(activity_repo, session_repo)

        base = datetime(2026, 2, 22, 14, 0, tzinfo=timezone.utc)
        events = [
            _event("active_window", base, app_name="Chrome", window_title="Tab 1", url="https://first.com"),
            _event("active_window", base + timedelta(minutes=2), app_name="Terminal", window_title="bash"),
            _event("active_window", base + timedelta(minutes=4), app_name="Chrome", window_title="Tab 2", url="https://second.com"),
            _event("active_window", base + timedelta(minutes=10), app_name="Firefox", window_title="End"),
        ]
        await _seed_events(activity_repo, test_user.id, events)

        await generator.generate_for_date(test_user.id, date(2026, 2, 22))

        sessions = await session_repo.get_by_date_range(
            test_user.id, date(2026, 2, 22), date(2026, 2, 22), limit=100, offset=0,
        )
        chrome = [s for s in sessions if s.app_name == "Chrome"][0]
        assert chrome.url == "https://first.com"

    async def test_url_merge_adopts_from_later_segment(
        self, db_session: AsyncSession, test_user: UserModel,
    ):
        """When first segment has no URL, later segment's URL is adopted."""
        activity_repo = ActivityEventRepository(db_session)
        session_repo = ActivitySessionRepository(db_session)
        generator = ActivitySessionGenerator(activity_repo, session_repo)

        base = datetime(2026, 2, 22, 14, 0, tzinfo=timezone.utc)
        events = [
            _event("active_window", base, app_name="Chrome", window_title="Tab 1"),
            _event("active_window", base + timedelta(minutes=2), app_name="Terminal", window_title="bash"),
            _event("active_window", base + timedelta(minutes=4), app_name="Chrome", window_title="Tab 2", url="https://adopted.com"),
            _event("active_window", base + timedelta(minutes=10), app_name="Firefox", window_title="End"),
        ]
        await _seed_events(activity_repo, test_user.id, events)

        await generator.generate_for_date(test_user.id, date(2026, 2, 22))

        sessions = await session_repo.get_by_date_range(
            test_user.id, date(2026, 2, 22), date(2026, 2, 22), limit=100, offset=0,
        )
        chrome = [s for s in sessions if s.app_name == "Chrome"][0]
        assert chrome.url == "https://adopted.com"

    async def test_consecutive_idle_starts(
        self, db_session: AsyncSession, test_user: UserModel,
    ):
        """Double idle_start: session closes at first, second is harmless."""
        activity_repo = ActivityEventRepository(db_session)
        session_repo = ActivitySessionRepository(db_session)
        generator = ActivitySessionGenerator(activity_repo, session_repo)

        base = datetime(2026, 2, 22, 14, 0, tzinfo=timezone.utc)
        events = [
            _event("active_window", base, app_name="VSCode", window_title="main.py"),
            _event("idle_start", base + timedelta(minutes=10)),
            _event("idle_start", base + timedelta(minutes=12)),
            _event("active_window", base + timedelta(minutes=20), app_name="Chrome", window_title="Docs"),
            _event("active_window", base + timedelta(minutes=30), app_name="Firefox", window_title="End"),
        ]
        await _seed_events(activity_repo, test_user.id, events)

        await generator.generate_for_date(test_user.id, date(2026, 2, 22))

        sessions = await session_repo.get_by_date_range(
            test_user.id, date(2026, 2, 22), date(2026, 2, 22), limit=100, offset=0,
        )
        vscode = [s for s in sessions if s.app_name == "VSCode"][0]
        assert vscode.end_time == base + timedelta(minutes=10)

        chrome = [s for s in sessions if s.app_name == "Chrome"][0]
        assert chrome.start_time == base + timedelta(minutes=20)

    async def test_rapid_app_switching_merges_by_app(
        self, db_session: AsyncSession, test_user: UserModel,
    ):
        """Rapid Chrome↔Cursor switching should produce 2 merged sessions, not 8."""
        activity_repo = ActivityEventRepository(db_session)
        session_repo = ActivitySessionRepository(db_session)
        generator = ActivitySessionGenerator(activity_repo, session_repo)

        base = datetime(2026, 2, 23, 14, 0, tzinfo=timezone.utc)
        events = [
            _event("active_window", base, app_name="Chrome", window_title="YouTube"),
            _event("active_window", base + timedelta(seconds=5), app_name="Cursor", window_title="main.py"),
            _event("active_window", base + timedelta(seconds=10), app_name="Chrome", window_title="GitHub"),
            _event("active_window", base + timedelta(seconds=40), app_name="Cursor", window_title="utils.py"),
            _event("active_window", base + timedelta(seconds=90), app_name="Chrome", window_title="Docs"),
            _event("active_window", base + timedelta(seconds=120), app_name="Cursor", window_title="test.py"),
            _event("active_window", base + timedelta(minutes=3), app_name="Chrome", window_title="PR"),
            _event("active_window", base + timedelta(minutes=10), app_name="Firefox", window_title="End"),
        ]
        await _seed_events(activity_repo, test_user.id, events)

        count = await generator.generate_for_date(test_user.id, date(2026, 2, 23))

        sessions = await session_repo.get_by_date_range(
            test_user.id, date(2026, 2, 23), date(2026, 2, 23), limit=100, offset=0,
        )
        app_names = [s.app_name for s in sessions]
        # Chrome and Cursor each merge into one session, plus Firefox at the end
        assert app_names == ["Chrome", "Cursor", "Firefox"]
        # Chrome: from base to base+10min (all Chrome within 2min gaps merge)
        chrome = sessions[0]
        assert chrome.start_time == base
        assert chrome.end_time == base + timedelta(minutes=10)
        assert set(chrome.window_titles) == {"YouTube", "GitHub", "Docs", "PR"}


class TestIncrementalGeneration:
    async def test_first_batch_creates_sessions(
        self, db_session: AsyncSession, test_user: UserModel,
    ):
        activity_repo = ActivityEventRepository(db_session)
        session_repo = ActivitySessionRepository(db_session)
        generator = ActivitySessionGenerator(activity_repo, session_repo)

        base = datetime(2026, 2, 23, 14, 0, tzinfo=timezone.utc)
        events = [
            _event("active_window", base, app_name="Firefox", window_title="GitHub"),
            _event("active_window", base + timedelta(minutes=15), app_name="VSCode", window_title="main.py"),
            _event("active_window", base + timedelta(minutes=45), app_name="Chrome", window_title="Docs"),
        ]
        await _seed_events(activity_repo, test_user.id, events)

        timestamps = [e.timestamp for e in events]
        count = await generator.generate_incremental(test_user.id, timestamps)
        assert count == 3

        sessions = await session_repo.get_by_date_range(
            test_user.id, date(2026, 2, 23), date(2026, 2, 23), limit=100, offset=0,
        )
        assert len(sessions) == 3
        assert sessions[0].app_name == "Firefox"
        assert sessions[1].app_name == "VSCode"
        assert sessions[2].app_name == "Chrome"

    async def test_second_batch_extends_sessions(
        self, db_session: AsyncSession, test_user: UserModel,
    ):
        activity_repo = ActivityEventRepository(db_session)
        session_repo = ActivitySessionRepository(db_session)
        generator = ActivitySessionGenerator(activity_repo, session_repo)

        base = datetime(2026, 2, 23, 14, 0, tzinfo=timezone.utc)

        # First batch
        batch1 = [
            _event("active_window", base, app_name="Firefox", window_title="GitHub"),
            _event("active_window", base + timedelta(minutes=15), app_name="VSCode", window_title="main.py"),
        ]
        await _seed_events(activity_repo, test_user.id, batch1)
        await generator.generate_incremental(test_user.id, [e.timestamp for e in batch1])

        # Second batch — continues from where we left off
        batch2 = [
            _event("active_window", base + timedelta(minutes=30), app_name="VSCode", window_title="utils.py"),
            _event("active_window", base + timedelta(minutes=45), app_name="Chrome", window_title="Docs"),
        ]
        await _seed_events(activity_repo, test_user.id, batch2)
        await generator.generate_incremental(test_user.id, [e.timestamp for e in batch2])

        sessions = await session_repo.get_by_date_range(
            test_user.id, date(2026, 2, 23), date(2026, 2, 23), limit=100, offset=0,
        )
        assert len(sessions) == 3
        assert sessions[0].app_name == "Firefox"
        assert sessions[1].app_name == "VSCode"
        assert sessions[1].end_time == base + timedelta(minutes=45)
        assert sessions[2].app_name == "Chrome"

    async def test_late_arriving_old_events_trigger_rebuild(
        self, db_session: AsyncSession, test_user: UserModel,
    ):
        activity_repo = ActivityEventRepository(db_session)
        session_repo = ActivitySessionRepository(db_session)
        generator = ActivitySessionGenerator(activity_repo, session_repo)

        base = datetime(2026, 2, 23, 14, 0, tzinfo=timezone.utc)

        # First batch: events from 14:30 onward
        batch1 = [
            _event("active_window", base + timedelta(minutes=30), app_name="VSCode", window_title="main.py"),
            _event("active_window", base + timedelta(minutes=45), app_name="Chrome", window_title="Docs"),
        ]
        await _seed_events(activity_repo, test_user.id, batch1)
        await generator.generate_incremental(test_user.id, [e.timestamp for e in batch1])

        sessions_before = await session_repo.get_by_date_range(
            test_user.id, date(2026, 2, 23), date(2026, 2, 23), limit=100, offset=0,
        )
        assert len(sessions_before) == 2

        # Late-arriving batch: events from 14:00 (earlier than existing sessions)
        batch2 = [
            _event("active_window", base, app_name="Firefox", window_title="GitHub"),
            _event("active_window", base + timedelta(minutes=15), app_name="Firefox", window_title="PR Review"),
        ]
        await _seed_events(activity_repo, test_user.id, batch2)
        await generator.generate_incremental(test_user.id, [e.timestamp for e in batch2])

        sessions_after = await session_repo.get_by_date_range(
            test_user.id, date(2026, 2, 23), date(2026, 2, 23), limit=100, offset=0,
        )
        # Should rebuild from 14:00 onward: Firefox(14:00-14:30), VSCode(14:30-14:45), Chrome(14:45+)
        assert len(sessions_after) == 3
        assert sessions_after[0].app_name == "Firefox"
        assert sessions_after[0].start_time == base
        assert sessions_after[1].app_name == "VSCode"
        assert sessions_after[2].app_name == "Chrome"

    async def test_idempotent_same_batch_twice(
        self, db_session: AsyncSession, test_user: UserModel,
    ):
        activity_repo = ActivityEventRepository(db_session)
        session_repo = ActivitySessionRepository(db_session)
        generator = ActivitySessionGenerator(activity_repo, session_repo)

        base = datetime(2026, 2, 23, 14, 0, tzinfo=timezone.utc)
        events = [
            _event("active_window", base, app_name="Firefox", window_title="GitHub"),
            _event("active_window", base + timedelta(minutes=15), app_name="VSCode", window_title="main.py"),
        ]
        await _seed_events(activity_repo, test_user.id, events)
        timestamps = [e.timestamp for e in events]

        count1 = await generator.generate_incremental(test_user.id, timestamps)
        count2 = await generator.generate_incremental(test_user.id, timestamps)

        # Both calls should produce same result
        assert count1 == count2

        total = await session_repo.count_by_date_range(
            test_user.id, date(2026, 2, 23), date(2026, 2, 23),
        )
        assert total == count1

    async def test_empty_timestamps_returns_zero(
        self, db_session: AsyncSession, test_user: UserModel,
    ):
        activity_repo = ActivityEventRepository(db_session)
        session_repo = ActivitySessionRepository(db_session)
        generator = ActivitySessionGenerator(activity_repo, session_repo)

        count = await generator.generate_incremental(test_user.id, [])
        assert count == 0

    async def test_multi_batch_rapid_switching_merges_correctly(
        self, db_session: AsyncSession, test_user: UserModel,
    ):
        """Simulate real-world scenario: rapid Chrome↔Cursor switching across
        multiple daemon flush batches.  All Chrome segments should merge into
        one session, not fragment into 4."""
        activity_repo = ActivityEventRepository(db_session)
        session_repo = ActivitySessionRepository(db_session)
        generator = ActivitySessionGenerator(activity_repo, session_repo)

        base = datetime(2026, 2, 22, 19, 14, tzinfo=timezone.utc)

        # Batch 1: rapid Chrome↔Cursor switching (19:14 - 19:20)
        batch1 = [
            _event("active_window", base, app_name="Chrome", window_title="GitHub"),
            _event("active_window", base + timedelta(seconds=5), app_name="Cursor", window_title="main.py"),
            _event("active_window", base + timedelta(seconds=10), app_name="Chrome", window_title="YouTube"),
            _event("active_window", base + timedelta(seconds=15), app_name="Cursor", window_title="utils.py"),
            _event("active_window", base + timedelta(seconds=45), app_name="Chrome", window_title="PR"),
            _event("active_window", base + timedelta(minutes=2), app_name="Cursor", window_title="test.py"),
            _event("active_window", base + timedelta(minutes=5), app_name="Chrome", window_title="Docs"),
        ]
        await _seed_events(activity_repo, test_user.id, batch1)
        await generator.generate_incremental(test_user.id, [e.timestamp for e in batch1])

        # Batch 2: Telegram break, then back to Chrome (19:24 - 19:30)
        batch2 = [
            _event("active_window", base + timedelta(minutes=10), app_name="Telegram", window_title="Chat"),
            _event("active_window", base + timedelta(minutes=11), app_name="Chrome", window_title="Calendar"),
            _event("active_window", base + timedelta(minutes=13), app_name="Cursor", window_title="index.ts"),
            _event("active_window", base + timedelta(minutes=15), app_name="Chrome", window_title="Search"),
        ]
        await _seed_events(activity_repo, test_user.id, batch2)
        await generator.generate_incremental(test_user.id, [e.timestamp for e in batch2])

        # Batch 3: more Telegram, then Chrome again (19:32 - 19:38)
        batch3 = [
            _event("active_window", base + timedelta(minutes=18), app_name="Telegram", window_title="Group"),
            _event("active_window", base + timedelta(minutes=19), app_name="Chrome", window_title="New Tab"),
            _event("active_window", base + timedelta(minutes=22), app_name="Cursor", window_title="api.py"),
            _event("active_window", base + timedelta(minutes=24), app_name="Chrome", window_title="MDN"),
        ]
        await _seed_events(activity_repo, test_user.id, batch3)
        await generator.generate_incremental(test_user.id, [e.timestamp for e in batch3])

        sessions = await session_repo.get_by_date_range(
            test_user.id, date(2026, 2, 22), date(2026, 2, 22), limit=100, offset=0,
        )
        app_names = [s.app_name for s in sessions]

        # Chrome should be ONE merged session (all gaps < 5 min)
        assert app_names.count("Chrome") == 1, (
            f"Expected 1 Chrome session, got {app_names.count('Chrome')}: {app_names}"
        )
        # Cursor has 3 sessions because gaps between usage are 8 and 7 min (> MERGE_GAP)
        assert app_names.count("Cursor") == 3
        # Telegram sessions are short (1 min) and finalized → dropped as noise
        assert app_names.count("Telegram") == 0
