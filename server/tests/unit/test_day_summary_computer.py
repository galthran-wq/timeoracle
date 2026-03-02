from datetime import datetime, timezone
from types import SimpleNamespace

from src.services.day_summary_computer import compute_day_summary


def _entry(start_hour, start_min, end_hour, end_min, category=None):
    return SimpleNamespace(
        start_time=datetime(2026, 3, 1, start_hour, start_min, tzinfo=timezone.utc),
        end_time=datetime(2026, 3, 1, end_hour, end_min, tzinfo=timezone.utc),
        category=category,
    )


def _session(start_hour, start_min, end_hour, end_min, app_name="VS Code"):
    return {
        "start_time": datetime(2026, 3, 1, start_hour, start_min, tzinfo=timezone.utc),
        "end_time": datetime(2026, 3, 1, end_hour, end_min, tzinfo=timezone.utc),
        "app_name": app_name,
    }


class TestEmptyInput:
    def test_empty_entries_and_sessions(self):
        result = compute_day_summary([], [])
        assert result["total_active_minutes"] == 0
        assert result["productive_minutes"] == 0
        assert result["focus_score"] is None
        assert result["distraction_score"] is None
        assert result["longest_focus_minutes"] == 0
        assert result["context_switches"] == 0
        assert result["session_count"] == 0
        assert result["top_app"] is None
        assert result["top_category"] is None
        assert result["category_breakdown"] == []
        assert result["app_breakdown"] == []


class TestTimeBucketing:
    def test_all_productive(self):
        entries = [_entry(9, 0, 11, 0, "Work")]
        result = compute_day_summary(entries, [])
        assert result["productive_minutes"] == 120.0
        assert result["neutral_minutes"] == 0
        assert result["distraction_minutes"] == 0
        assert result["total_active_minutes"] == 120.0
        assert result["focus_score"] == 1.0
        assert result["distraction_score"] == 0.0

    def test_all_distraction(self):
        entries = [_entry(9, 0, 10, 0, "Entertainment")]
        result = compute_day_summary(entries, [])
        assert result["distraction_minutes"] == 60.0
        assert result["productive_minutes"] == 0
        assert result["distraction_score"] == 1.0
        assert result["focus_score"] == 0.0

    def test_mixed_categories(self):
        entries = [
            _entry(9, 0, 10, 0, "Work"),
            _entry(10, 0, 10, 30, "Entertainment"),
            _entry(10, 30, 11, 0, "Communication"),
        ]
        result = compute_day_summary(entries, [])
        assert result["productive_minutes"] == 60.0
        assert result["distraction_minutes"] == 30.0
        assert result["neutral_minutes"] == 30.0
        assert result["total_active_minutes"] == 120.0
        assert abs(result["focus_score"] - 0.5) < 0.01
        assert abs(result["distraction_score"] - 0.25) < 0.01

    def test_uncategorized_entries(self):
        entries = [_entry(9, 0, 10, 0, None)]
        result = compute_day_summary(entries, [])
        assert result["uncategorized_minutes"] == 60.0
        assert result["focus_score"] == 0.0


class TestFocusStreak:
    def test_contiguous_productive(self):
        entries = [
            _entry(9, 0, 10, 0, "Work"),
            _entry(10, 0, 11, 0, "Work"),
        ]
        result = compute_day_summary(entries, [])
        assert result["longest_focus_minutes"] == 120.0

    def test_broken_by_distraction(self):
        entries = [
            _entry(9, 0, 10, 0, "Work"),
            _entry(10, 0, 10, 15, "Entertainment"),
            _entry(10, 15, 11, 0, "Work"),
        ]
        result = compute_day_summary(entries, [])
        assert result["longest_focus_minutes"] == 60.0

    def test_gap_tolerance(self):
        entries = [
            _entry(9, 0, 10, 0, "Work"),
            _entry(10, 4, 11, 0, "Work"),
        ]
        result = compute_day_summary(entries, [])
        assert result["longest_focus_minutes"] == 120.0

    def test_gap_exceeds_tolerance(self):
        entries = [
            _entry(9, 0, 10, 0, "Work"),
            _entry(10, 6, 11, 0, "Work"),
        ]
        result = compute_day_summary(entries, [])
        assert result["longest_focus_minutes"] == 60.0


class TestContextSwitches:
    def test_no_switches_same_type(self):
        entries = [
            _entry(9, 0, 10, 0, "Work"),
            _entry(10, 0, 11, 0, "Research"),
        ]
        result = compute_day_summary(entries, [])
        assert result["context_switches"] == 0

    def test_switch_between_types(self):
        entries = [
            _entry(9, 0, 10, 0, "Work"),
            _entry(10, 0, 10, 30, "Entertainment"),
            _entry(10, 30, 11, 0, "Work"),
        ]
        result = compute_day_summary(entries, [])
        assert result["context_switches"] == 2

    def test_ignores_large_gaps(self):
        entries = [
            _entry(9, 0, 10, 0, "Work"),
            _entry(11, 0, 12, 0, "Entertainment"),
        ]
        result = compute_day_summary(entries, [])
        assert result["context_switches"] == 0


class TestCustomCategories:
    def test_user_categories_override_defaults(self):
        custom = {"Coding": {"color": "#000", "type": "productive"}}
        entries = [_entry(9, 0, 10, 0, "Coding")]
        result = compute_day_summary(entries, [], user_categories=custom)
        assert result["productive_minutes"] == 60.0
        assert result["focus_score"] == 1.0

    def test_unknown_category_defaults_to_neutral(self):
        entries = [_entry(9, 0, 10, 0, "RandomThing")]
        result = compute_day_summary(entries, [])
        assert result["neutral_minutes"] == 60.0


class TestBreakdowns:
    def test_category_breakdown_shape(self):
        entries = [
            _entry(9, 0, 10, 0, "Work"),
            _entry(10, 0, 10, 30, "Entertainment"),
        ]
        result = compute_day_summary(entries, [])
        bd = result["category_breakdown"]
        assert len(bd) == 2
        assert bd[0]["category"] == "Work"
        assert bd[0]["type"] == "productive"
        assert bd[0]["minutes"] == 60.0
        assert bd[1]["category"] == "Entertainment"

    def test_app_breakdown_top_10(self):
        sessions = [_session(9, 0, 10, 0, f"App{i}") for i in range(15)]
        result = compute_day_summary([], sessions)
        assert len(result["app_breakdown"]) == 10

    def test_app_breakdown_sorted_by_minutes(self):
        sessions = [
            _session(9, 0, 9, 30, "Short"),
            _session(9, 0, 11, 0, "Long"),
        ]
        result = compute_day_summary([], sessions)
        assert result["app_breakdown"][0]["app"] == "Long"
        assert result["app_breakdown"][1]["app"] == "Short"

    def test_session_count(self):
        sessions = [_session(9, 0, 10, 0), _session(10, 0, 11, 0)]
        result = compute_day_summary([], sessions)
        assert result["session_count"] == 2
