from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from src.services.day_summary_computer import compute_day_summary


def _entry(start_hour, start_min, end_hour, end_min, category=None):
    return SimpleNamespace(
        start_time=datetime(2026, 3, 1, start_hour, start_min, tzinfo=timezone.utc),
        end_time=datetime(2026, 3, 1, end_hour, end_min, tzinfo=timezone.utc),
        category=category,
    )


def _point(hour, minute, focus_score=None, depth=None, is_work=False, productivity_score=None):
    return SimpleNamespace(
        interval_start=datetime(2026, 3, 1, hour, minute, tzinfo=timezone.utc),
        focus_score=focus_score,
        depth=depth,
        is_work=is_work,
        productivity_score=productivity_score,
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
        assert result["longest_focus_minutes"] == 0
        assert result["context_switches"] == 0
        assert result["session_count"] == 0
        assert result["top_app"] is None
        assert result["top_category"] is None
        assert result["category_breakdown"] == []
        assert result["app_breakdown"] == []
        assert result["deep_work_minutes"] == 0
        assert result["shallow_work_minutes"] == 0
        assert result["reactive_minutes"] == 0
        assert result["avg_focus_score"] is None
        assert result["fragmentation_index"] is None
        assert result["switches_per_hour"] is None
        assert result["focus_sessions_25min"] == 0
        assert result["focus_sessions_90min"] == 0
        assert result["productivity_score"] is None
        assert result["work_minutes"] == 0


class TestTotalActiveMinutes:
    def test_single_entry(self):
        entries = [_entry(9, 0, 11, 0, "Work")]
        result = compute_day_summary(entries, [])
        assert result["total_active_minutes"] == 120.0

    def test_multiple_entries(self):
        entries = [
            _entry(9, 0, 10, 0, "Work"),
            _entry(10, 0, 10, 30, "Entertainment"),
            _entry(10, 30, 11, 0, "Communication"),
        ]
        result = compute_day_summary(entries, [])
        assert result["total_active_minutes"] == 120.0


class TestFocusStreak:
    def test_contiguous_focused_points(self):
        points = [
            _point(9, 0, focus_score=0.9, depth="deep"),
            _point(9, 10, focus_score=0.85, depth="deep"),
            _point(9, 20, focus_score=0.8, depth="deep"),
            _point(9, 30, focus_score=0.9, depth="deep"),
            _point(9, 40, focus_score=0.8, depth="deep"),
            _point(9, 50, focus_score=0.85, depth="deep"),
        ]
        result = compute_day_summary([], [], points)
        assert result["longest_focus_minutes"] == 60.0

    def test_broken_by_low_focus(self):
        points = [
            _point(9, 0, focus_score=0.9, depth="deep"),
            _point(9, 10, focus_score=0.9, depth="deep"),
            _point(9, 20, focus_score=0.3, depth="shallow"),
            _point(9, 30, focus_score=0.8, depth="deep"),
            _point(9, 40, focus_score=0.8, depth="deep"),
        ]
        result = compute_day_summary([], [], points)
        assert result["longest_focus_minutes"] == 20.0

    def test_no_focus_score_means_not_focused(self):
        points = [_point(9, 0), _point(9, 10)]
        result = compute_day_summary([], [], points)
        assert result["longest_focus_minutes"] == 0.0


class TestContextSwitches:
    def test_no_switches_same_depth(self):
        points = [
            _point(9, 0, focus_score=0.9, depth="deep"),
            _point(9, 10, focus_score=0.8, depth="deep"),
            _point(9, 20, focus_score=0.7, depth="deep"),
        ]
        result = compute_day_summary([], [], points)
        assert result["context_switches"] == 0

    def test_switch_between_depths(self):
        points = [
            _point(9, 0, focus_score=0.9, depth="deep"),
            _point(9, 10, focus_score=0.5, depth="reactive"),
            _point(9, 20, focus_score=0.8, depth="deep"),
        ]
        result = compute_day_summary([], [], points)
        assert result["context_switches"] == 2

    def test_ignores_large_gaps(self):
        points = [
            _point(9, 0, focus_score=0.9, depth="deep"),
            _point(11, 0, focus_score=0.5, depth="reactive"),
        ]
        result = compute_day_summary([], [], points)
        assert result["context_switches"] == 0


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


class TestDepthBreakdown:
    def test_all_deep(self):
        points = [
            _point(9, 0, focus_score=0.9, depth="deep"),
            _point(9, 10, focus_score=0.9, depth="deep"),
        ]
        result = compute_day_summary([], [], points)
        assert result["deep_work_minutes"] == 20.0
        assert result["shallow_work_minutes"] == 0.0
        assert result["reactive_minutes"] == 0.0

    def test_mixed_depth(self):
        points = [
            _point(9, 0, focus_score=0.9, depth="deep"),
            _point(9, 10, focus_score=0.5, depth="reactive"),
            _point(9, 20, focus_score=0.6, depth="shallow"),
        ]
        result = compute_day_summary([], [], points)
        assert result["deep_work_minutes"] == 10.0
        assert result["reactive_minutes"] == 10.0
        assert result["shallow_work_minutes"] == 10.0

    def test_no_depth_set(self):
        points = [_point(9, 0)]
        result = compute_day_summary([], [], points)
        assert result["deep_work_minutes"] == 0.0


class TestAvgFocusScore:
    def test_single_point(self):
        points = [_point(9, 0, focus_score=0.8, depth="deep")]
        result = compute_day_summary([], [], points)
        assert result["avg_focus_score"] == 0.8

    def test_average_across_points(self):
        points = [
            _point(9, 0, focus_score=0.9, depth="deep"),
            _point(9, 10, focus_score=0.3, depth="shallow"),
        ]
        result = compute_day_summary([], [], points)
        assert abs(result["avg_focus_score"] - 0.6) < 0.01

    def test_none_when_no_scores(self):
        points = [_point(9, 0)]
        result = compute_day_summary([], [], points)
        assert result["avg_focus_score"] is None

    def test_empty(self):
        result = compute_day_summary([], [])
        assert result["avg_focus_score"] is None


class TestFragmentationIndex:
    def test_empty_returns_none(self):
        result = compute_day_summary([], [])
        assert result["fragmentation_index"] is None


class TestSwitchesPerHour:
    def test_empty_returns_none(self):
        result = compute_day_summary([], [])
        assert result["switches_per_hour"] is None


class TestFocusSessions:
    def test_no_sessions_without_focus_score(self):
        points = [_point(9, 0)]
        result = compute_day_summary([], [], points)
        assert result["focus_sessions_25min"] == 0
        assert result["focus_sessions_90min"] == 0

    def test_one_25min_session(self):
        points = [
            _point(9, 0, focus_score=0.8, depth="deep"),
            _point(9, 10, focus_score=0.8, depth="deep"),
            _point(9, 20, focus_score=0.8, depth="deep"),
        ]
        result = compute_day_summary([], [], points)
        assert result["focus_sessions_25min"] == 1
        assert result["focus_sessions_90min"] == 0

    def test_one_90min_session(self):
        points = []
        for i in range(10):
            h = 9 + (i * 10) // 60
            m = (i * 10) % 60
            points.append(_point(h, m, focus_score=0.8, depth="deep"))
        result = compute_day_summary([], [], points)
        assert result["focus_sessions_25min"] == 1
        assert result["focus_sessions_90min"] == 1

    def test_broken_by_low_focus(self):
        points = [
            _point(9, 0, focus_score=0.9, depth="deep"),
            _point(9, 10, focus_score=0.9, depth="deep"),
            _point(9, 20, focus_score=0.9, depth="deep"),
            _point(9, 30, focus_score=0.2, depth="shallow"),
            _point(9, 40, focus_score=0.8, depth="deep"),
            _point(9, 50, focus_score=0.8, depth="deep"),
            _point(10, 0, focus_score=0.8, depth="deep"),
        ]
        result = compute_day_summary([], [], points)
        assert result["focus_sessions_25min"] == 2
        assert result["focus_sessions_90min"] == 0


class TestProductivityScore:
    def test_avg_over_work_points(self):
        points = [
            _point(9, 0, focus_score=0.9, depth="deep", is_work=True, productivity_score=90.0),
            _point(9, 10, focus_score=0.6, depth="deep", is_work=True, productivity_score=60.0),
            _point(9, 20, focus_score=0.8, depth="shallow", is_work=False, productivity_score=48.0),
        ]
        result = compute_day_summary([], [], points)
        assert result["productivity_score"] == 75.0

    def test_none_when_no_work_points(self):
        points = [
            _point(9, 0, focus_score=0.8, depth="shallow", is_work=False, productivity_score=48.0),
        ]
        result = compute_day_summary([], [], points)
        assert result["productivity_score"] is None


class TestWorkMinutes:
    def test_counts_work_points(self):
        points = [
            _point(9, 0, is_work=True),
            _point(9, 10, is_work=True),
            _point(9, 20, is_work=False),
        ]
        result = compute_day_summary([], [], points)
        assert result["work_minutes"] == 20.0

    def test_zero_when_no_work(self):
        result = compute_day_summary([], [])
        assert result["work_minutes"] == 0
