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


def _event(
    event_type: str,
    timestamp: datetime,
    app_name: str = "Firefox",
    window_title: str = "Home",
    url: str | None = None,
) -> FakeEvent:
    return FakeEvent(
        event_type=event_type,
        timestamp=timestamp,
        app_name=app_name,
        window_title=window_title,
        url=url,
    )


def _day_end(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, 23, 59, 59, 999999, tzinfo=timezone.utc)


class TestComputeSessions:
    def test_consecutive_windows_create_sessions(self):
        base = datetime(2026, 2, 23, 14, 0, tzinfo=timezone.utc)
        events = [
            _event("active_window", base, app_name="Firefox", window_title="GitHub"),
            _event("active_window", base + timedelta(minutes=15), app_name="VSCode", window_title="main.py"),
            _event("active_window", base + timedelta(minutes=45), app_name="Chrome", window_title="Docs"),
        ]

        sessions = compute_sessions(events, _day_end(date(2026, 2, 23)))
        assert len(sessions) == 3

        assert sessions[0]["app_name"] == "Firefox"
        assert sessions[0]["start_time"] == base
        assert sessions[0]["end_time"] == base + timedelta(minutes=15)

        assert sessions[1]["app_name"] == "VSCode"
        assert sessions[1]["start_time"] == base + timedelta(minutes=15)
        assert sessions[1]["end_time"] == base + timedelta(minutes=45)

        assert sessions[2]["app_name"] == "Chrome"

    def test_idle_gap_ends_session(self):
        base = datetime(2026, 2, 23, 14, 0, tzinfo=timezone.utc)
        events = [
            _event("active_window", base, app_name="VSCode", window_title="main.py"),
            _event("idle_start", base + timedelta(minutes=30)),
            _event("idle_end", base + timedelta(minutes=45)),
            _event("active_window", base + timedelta(minutes=45), app_name="Chrome", window_title="Search"),
        ]

        sessions = compute_sessions(events, _day_end(date(2026, 2, 23)))
        assert len(sessions) == 2

        assert sessions[0]["app_name"] == "VSCode"
        assert sessions[0]["end_time"] == base + timedelta(minutes=30)

        assert sessions[1]["app_name"] == "Chrome"
        assert sessions[1]["start_time"] == base + timedelta(minutes=45)

    def test_same_app_heartbeats_merge(self):
        base = datetime(2026, 2, 23, 14, 0, tzinfo=timezone.utc)
        events = [
            _event("active_window", base, app_name="VSCode", window_title="main.py"),
            _event("active_window", base + timedelta(minutes=5), app_name="VSCode", window_title="utils.py"),
            _event("active_window", base + timedelta(minutes=10), app_name="VSCode", window_title="test.py"),
            _event("active_window", base + timedelta(minutes=15), app_name="Firefox", window_title="Docs"),
        ]

        sessions = compute_sessions(events, _day_end(date(2026, 2, 23)))
        assert len(sessions) == 2

        assert sessions[0]["app_name"] == "VSCode"
        assert sessions[0]["start_time"] == base
        assert sessions[0]["end_time"] == base + timedelta(minutes=15)
        assert set(sessions[0]["window_titles"]) == {"main.py", "utils.py", "test.py"}

    def test_short_sessions_dropped(self):
        base = datetime(2026, 2, 23, 14, 0, tzinfo=timezone.utc)
        events = [
            _event("active_window", base, app_name="Firefox", window_title="Home"),
            _event("active_window", base + timedelta(seconds=2), app_name="Terminal", window_title="bash"),
            _event("active_window", base + timedelta(seconds=4), app_name="Firefox", window_title="Home"),
            _event("active_window", base + timedelta(minutes=10), app_name="Chrome", window_title="Search"),
        ]

        sessions = compute_sessions(events, _day_end(date(2026, 2, 23)))
        app_names = [s["app_name"] for s in sessions]
        assert "Terminal" not in app_names
        assert sessions[0]["app_name"] == "Firefox"

    def test_noise_sessions_dropped_when_finalized(self):
        base = datetime(2026, 2, 22, 14, 0, tzinfo=timezone.utc)
        events = [
            _event("active_window", base, app_name="Chrome", window_title="YouTube"),
            _event("active_window", base + timedelta(minutes=10), app_name="Chrome", window_title="GitHub"),
            _event("active_window", base + timedelta(minutes=20), app_name="Telegram", window_title="Chat"),
            _event("active_window", base + timedelta(minutes=20, seconds=30), app_name="Terminal", window_title="bash"),
            _event("active_window", base + timedelta(minutes=20, seconds=35), app_name="Terminal", window_title="bash"),
            _event("active_window", base + timedelta(minutes=20, seconds=40), app_name="Chrome", window_title="Docs"),
            _event("active_window", base + timedelta(minutes=35), app_name="Firefox", window_title="End"),
        ]

        sessions = compute_sessions(events, _day_end(date(2026, 2, 22)))
        app_names = [s["app_name"] for s in sessions]
        assert "Telegram" not in app_names, f"Telegram should be dropped: {app_names}"
        assert "Terminal" not in app_names, f"Terminal should be dropped: {app_names}"
        assert "Chrome" in app_names

    def test_empty_events_returns_empty(self):
        sessions = compute_sessions([], _day_end(date(2026, 2, 23)))
        assert sessions == []

    def test_single_event_capped_at_end_of_day(self):
        base = datetime(2026, 2, 22, 22, 0, tzinfo=timezone.utc)
        events = [
            _event("active_window", base, app_name="Firefox", window_title="Home"),
        ]
        day_end = _day_end(date(2026, 2, 22))

        sessions = compute_sessions(events, day_end)
        assert len(sessions) == 1
        assert sessions[0]["end_time"] > sessions[0]["start_time"]
        assert sessions[0]["end_time"] <= day_end

    def test_window_titles_collected(self):
        base = datetime(2026, 2, 23, 14, 0, tzinfo=timezone.utc)
        events = [
            _event("active_window", base, app_name="Firefox", window_title="Tab 1", url="https://example.com"),
            _event("active_window", base + timedelta(minutes=5), app_name="Firefox", window_title="Tab 2"),
            _event("active_window", base + timedelta(minutes=10), app_name="Firefox", window_title="Tab 1"),
            _event("active_window", base + timedelta(minutes=15), app_name="Chrome", window_title="Docs"),
        ]

        sessions = compute_sessions(events, _day_end(date(2026, 2, 23)))
        firefox = sessions[0]
        assert firefox["window_title"] == "Tab 1"
        assert set(firefox["window_titles"]) == {"Tab 1", "Tab 2"}
        assert firefox["url"] == "https://example.com"

    def test_merge_gap_exact_boundary(self):
        base = datetime(2026, 2, 22, 14, 0, tzinfo=timezone.utc)
        events = [
            _event("active_window", base, app_name="Chrome", window_title="Tab 1"),
            _event("active_window", base + timedelta(minutes=5), app_name="Other", window_title="x"),
            _event("active_window", base + timedelta(minutes=10), app_name="Chrome", window_title="Tab 2"),
            _event("active_window", base + timedelta(minutes=15), app_name="Other", window_title="y"),
            _event("active_window", base + timedelta(minutes=20, seconds=1), app_name="Chrome", window_title="Tab 3"),
            _event("active_window", base + timedelta(minutes=25), app_name="Firefox", window_title="End"),
        ]

        sessions = compute_sessions(events, _day_end(date(2026, 2, 22)))
        chrome_sessions = [s for s in sessions if s["app_name"] == "Chrome"]
        assert len(chrome_sessions) == 2
        assert chrome_sessions[0]["start_time"] == base
        assert chrome_sessions[0]["end_time"] == base + timedelta(minutes=15)
        assert chrome_sessions[1]["start_time"] == base + timedelta(minutes=20, seconds=1)

    def test_noise_threshold_exact_boundary(self):
        base = datetime(2026, 2, 22, 14, 0, tzinfo=timezone.utc)
        events = [
            _event("active_window", base, app_name="VSCode", window_title="main.py"),
            _event("active_window", base + timedelta(minutes=30), app_name="Short119", window_title="x"),
            _event("active_window", base + timedelta(minutes=30, seconds=119), app_name="Filler", window_title="y"),
            _event("active_window", base + timedelta(minutes=40), app_name="Exact120", window_title="z"),
            _event("active_window", base + timedelta(minutes=42), app_name="Firefox", window_title="End"),
        ]

        sessions = compute_sessions(events, _day_end(date(2026, 2, 22)))
        app_names = [s["app_name"] for s in sessions]
        assert "Short119" not in app_names
        assert "Exact120" in app_names

    def test_cross_midnight_session_split(self):
        events = [
            _event("active_window", datetime(2026, 2, 22, 23, 50, tzinfo=timezone.utc),
                   app_name="VSCode", window_title="main.py"),
            _event("active_window", datetime(2026, 2, 23, 0, 10, tzinfo=timezone.utc),
                   app_name="Chrome", window_title="Docs"),
            _event("active_window", datetime(2026, 2, 23, 0, 20, tzinfo=timezone.utc),
                   app_name="Firefox", window_title="End"),
        ]

        sessions = compute_sessions(events, _day_end(date(2026, 2, 23)))

        sessions_22 = [s for s in sessions if s["date"] == date(2026, 2, 22)]
        sessions_23 = [s for s in sessions if s["date"] == date(2026, 2, 23)]

        vscode_22 = [s for s in sessions_22 if s["app_name"] == "VSCode"]
        assert len(vscode_22) == 1
        assert vscode_22[0]["start_time"] == datetime(2026, 2, 22, 23, 50, tzinfo=timezone.utc)
        assert vscode_22[0]["end_time"] == datetime(2026, 2, 23, 0, 0, tzinfo=timezone.utc)
        assert vscode_22[0]["date"] == date(2026, 2, 22)

        vscode_23 = [s for s in sessions_23 if s["app_name"] == "VSCode"]
        assert len(vscode_23) == 1
        assert vscode_23[0]["start_time"] == datetime(2026, 2, 23, 0, 0, tzinfo=timezone.utc)
        assert vscode_23[0]["end_time"] == datetime(2026, 2, 23, 0, 10, tzinfo=timezone.utc)
        assert vscode_23[0]["date"] == date(2026, 2, 23)

    def test_url_merge_keeps_first_non_null(self):
        base = datetime(2026, 2, 22, 14, 0, tzinfo=timezone.utc)
        events = [
            _event("active_window", base, app_name="Chrome", window_title="Tab 1", url="https://first.com"),
            _event("active_window", base + timedelta(minutes=2), app_name="Terminal", window_title="bash"),
            _event("active_window", base + timedelta(minutes=4), app_name="Chrome", window_title="Tab 2", url="https://second.com"),
            _event("active_window", base + timedelta(minutes=10), app_name="Firefox", window_title="End"),
        ]

        sessions = compute_sessions(events, _day_end(date(2026, 2, 22)))
        chrome = [s for s in sessions if s["app_name"] == "Chrome"][0]
        assert chrome["url"] == "https://first.com"

    def test_url_merge_adopts_from_later_segment(self):
        base = datetime(2026, 2, 22, 14, 0, tzinfo=timezone.utc)
        events = [
            _event("active_window", base, app_name="Chrome", window_title="Tab 1"),
            _event("active_window", base + timedelta(minutes=2), app_name="Terminal", window_title="bash"),
            _event("active_window", base + timedelta(minutes=4), app_name="Chrome", window_title="Tab 2", url="https://adopted.com"),
            _event("active_window", base + timedelta(minutes=10), app_name="Firefox", window_title="End"),
        ]

        sessions = compute_sessions(events, _day_end(date(2026, 2, 22)))
        chrome = [s for s in sessions if s["app_name"] == "Chrome"][0]
        assert chrome["url"] == "https://adopted.com"

    def test_consecutive_idle_starts(self):
        base = datetime(2026, 2, 22, 14, 0, tzinfo=timezone.utc)
        events = [
            _event("active_window", base, app_name="VSCode", window_title="main.py"),
            _event("idle_start", base + timedelta(minutes=10)),
            _event("idle_start", base + timedelta(minutes=12)),
            _event("active_window", base + timedelta(minutes=20), app_name="Chrome", window_title="Docs"),
            _event("active_window", base + timedelta(minutes=30), app_name="Firefox", window_title="End"),
        ]

        sessions = compute_sessions(events, _day_end(date(2026, 2, 22)))
        vscode = [s for s in sessions if s["app_name"] == "VSCode"][0]
        assert vscode["end_time"] == base + timedelta(minutes=10)

        chrome = [s for s in sessions if s["app_name"] == "Chrome"][0]
        assert chrome["start_time"] == base + timedelta(minutes=20)

    def test_custom_merge_gap_larger(self):
        base = datetime(2026, 2, 22, 14, 0, tzinfo=timezone.utc)
        events = [
            _event("active_window", base, app_name="Chrome", window_title="Tab 1"),
            _event("active_window", base + timedelta(minutes=5), app_name="Other", window_title="x"),
            _event("active_window", base + timedelta(minutes=20, seconds=1), app_name="Chrome", window_title="Tab 2"),
            _event("active_window", base + timedelta(minutes=25), app_name="Firefox", window_title="End"),
        ]

        sessions_default = compute_sessions(events, _day_end(date(2026, 2, 22)))
        chrome_default = [s for s in sessions_default if s["app_name"] == "Chrome"]
        assert len(chrome_default) == 2

        sessions_large = compute_sessions(
            events, _day_end(date(2026, 2, 22)), merge_gap_seconds=1200,
        )
        chrome_large = [s for s in sessions_large if s["app_name"] == "Chrome"]
        assert len(chrome_large) == 1

    def test_custom_min_session_seconds(self):
        base = datetime(2026, 2, 22, 14, 0, tzinfo=timezone.utc)
        events = [
            _event("active_window", base, app_name="Firefox", window_title="Home"),
            _event("active_window", base + timedelta(minutes=2, seconds=30), app_name="Chrome", window_title="Docs"),
            _event("active_window", base + timedelta(minutes=10), app_name="Terminal", window_title="End"),
        ]

        sessions_default = compute_sessions(events, _day_end(date(2026, 2, 22)))
        apps_default = [s["app_name"] for s in sessions_default]
        assert "Firefox" in apps_default

        sessions_strict = compute_sessions(
            events, _day_end(date(2026, 2, 22)), min_session_seconds=180,
        )
        apps_strict = [s["app_name"] for s in sessions_strict]
        assert "Firefox" not in apps_strict

    def test_custom_noise_threshold(self):
        base = datetime(2026, 2, 22, 14, 0, tzinfo=timezone.utc)
        events = [
            _event("active_window", base, app_name="VSCode", window_title="main.py"),
            _event("active_window", base + timedelta(minutes=30), app_name="Slack", window_title="Chat"),
            _event("active_window", base + timedelta(minutes=33), app_name="Firefox", window_title="End"),
        ]

        sessions_default = compute_sessions(events, _day_end(date(2026, 2, 22)))
        apps_default = [s["app_name"] for s in sessions_default]
        assert "Slack" in apps_default

        sessions_strict = compute_sessions(
            events, _day_end(date(2026, 2, 22)), noise_threshold_seconds=300,
        )
        apps_strict = [s["app_name"] for s in sessions_strict]
        assert "Slack" not in apps_strict

    def test_rapid_app_switching_merges_by_app(self):
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

        sessions = compute_sessions(events, _day_end(date(2026, 2, 23)))
        app_names = [s["app_name"] for s in sessions]
        assert app_names == ["Chrome", "Cursor", "Firefox"]

        chrome = sessions[0]
        assert chrome["start_time"] == base
        assert chrome["end_time"] == base + timedelta(minutes=10)
        assert set(chrome["window_titles"]) == {"YouTube", "GitHub", "Docs", "PR"}
