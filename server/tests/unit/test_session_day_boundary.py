from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from src.services.activity_session_generator import compute_sessions


@dataclass
class FakeEvent:
    event_type: str
    timestamp: datetime
    app_name: str = "Firefox"
    window_title: str = "Home"
    url: str | None = None


def _event(event_type, timestamp, app_name="Firefox", window_title="Home", url=None):
    return FakeEvent(event_type=event_type, timestamp=timestamp, app_name=app_name, window_title=window_title, url=url)


def _cap(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, 23, 59, 59, 999999, tzinfo=timezone.utc)


class TestDayBoundarySplit:
    def test_split_at_custom_boundary_4am(self):
        events = [
            _event("active_window", datetime(2026, 3, 2, 3, 0, tzinfo=timezone.utc), app_name="VSCode", window_title="main.py"),
            _event("active_window", datetime(2026, 3, 2, 5, 0, tzinfo=timezone.utc), app_name="Chrome", window_title="End"),
        ]

        sessions = compute_sessions(events, _cap(date(2026, 3, 2)), day_start_hour=4, day_timezone="UTC")

        vscode_sessions = [s for s in sessions if s["app_name"] == "VSCode"]
        assert len(vscode_sessions) == 2

        before = [s for s in vscode_sessions if s["date"] == date(2026, 3, 1)]
        assert len(before) == 1
        assert before[0]["end_time"] == datetime(2026, 3, 2, 4, 0, tzinfo=timezone.utc)

        after = [s for s in vscode_sessions if s["date"] == date(2026, 3, 2)]
        assert len(after) == 1
        assert after[0]["start_time"] == datetime(2026, 3, 2, 4, 0, tzinfo=timezone.utc)

    def test_session_within_same_logical_day_no_split(self):
        events = [
            _event("active_window", datetime(2026, 3, 2, 1, 0, tzinfo=timezone.utc), app_name="VSCode", window_title="main.py"),
            _event("active_window", datetime(2026, 3, 2, 3, 0, tzinfo=timezone.utc), app_name="Chrome", window_title="End"),
        ]

        sessions = compute_sessions(events, _cap(date(2026, 3, 2)), day_start_hour=4, day_timezone="UTC")
        vscode = [s for s in sessions if s["app_name"] == "VSCode"]
        assert len(vscode) == 1
        assert vscode[0]["date"] == date(2026, 3, 1)

    def test_default_boundary_backward_compatible(self):
        events = [
            _event("active_window", datetime(2026, 3, 1, 23, 50, tzinfo=timezone.utc), app_name="VSCode", window_title="main.py"),
            _event("active_window", datetime(2026, 3, 2, 0, 10, tzinfo=timezone.utc), app_name="Chrome", window_title="End"),
        ]

        sessions = compute_sessions(events, _cap(date(2026, 3, 2)))
        vscode = [s for s in sessions if s["app_name"] == "VSCode"]
        assert len(vscode) == 2
        assert vscode[0]["date"] == date(2026, 3, 1)
        assert vscode[1]["date"] == date(2026, 3, 2)

    def test_1am_event_with_4am_boundary_belongs_to_previous_day(self):
        events = [
            _event("active_window", datetime(2026, 3, 2, 1, 0, tzinfo=timezone.utc), app_name="VSCode", window_title="main.py"),
            _event("active_window", datetime(2026, 3, 2, 2, 0, tzinfo=timezone.utc), app_name="Chrome", window_title="End"),
        ]

        sessions = compute_sessions(events, _cap(date(2026, 3, 2)), day_start_hour=4, day_timezone="UTC")
        vscode = [s for s in sessions if s["app_name"] == "VSCode"]
        assert len(vscode) == 1
        assert vscode[0]["date"] == date(2026, 3, 1)
