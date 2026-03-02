from datetime import date, datetime, timezone

from src.services.day_boundary import (
    day_boundary_utc,
    day_range_utc,
    week_range_utc,
    logical_date_for_timestamp,
)


class TestDayBoundaryUtc:
    def test_midnight_utc(self):
        result = day_boundary_utc(date(2026, 3, 1), 0, "UTC")
        assert result == datetime(2026, 3, 1, 0, 0)

    def test_4am_utc(self):
        result = day_boundary_utc(date(2026, 3, 1), 4, "UTC")
        assert result == datetime(2026, 3, 1, 4, 0)

    def test_4am_us_eastern(self):
        result = day_boundary_utc(date(2026, 3, 1), 4, "America/New_York")
        assert result == datetime(2026, 3, 1, 9, 0)

    def test_3am_europe_berlin(self):
        result = day_boundary_utc(date(2026, 7, 15), 3, "Europe/Berlin")
        assert result == datetime(2026, 7, 15, 1, 0)


class TestDayRangeUtc:
    def test_default_midnight_utc(self):
        start, end = day_range_utc(date(2026, 3, 1), 0, "UTC")
        assert start == datetime(2026, 3, 1, 0, 0)
        assert end == datetime(2026, 3, 2, 0, 0)

    def test_4am_utc_spans_correctly(self):
        start, end = day_range_utc(date(2026, 3, 1), 4, "UTC")
        assert start == datetime(2026, 3, 1, 4, 0)
        assert end == datetime(2026, 3, 2, 4, 0)

    def test_range_is_24_hours(self):
        start, end = day_range_utc(date(2026, 6, 15), 3, "America/New_York")
        diff = (end - start).total_seconds()
        assert diff == 86400


class TestWeekRangeUtc:
    def test_week_covers_7_days(self):
        start, end = week_range_utc(date(2026, 3, 1), 0, "UTC")
        diff = (end - start).total_seconds()
        assert diff == 7 * 86400

    def test_week_with_custom_boundary(self):
        start, end = week_range_utc(date(2026, 3, 1), 4, "UTC")
        assert start == datetime(2026, 3, 1, 4, 0)
        assert end == datetime(2026, 3, 8, 4, 0)


class TestLogicalDateForTimestamp:
    def test_default_midnight_utc(self):
        ts = datetime(2026, 3, 1, 15, 30, tzinfo=timezone.utc)
        assert logical_date_for_timestamp(ts, 0, "UTC") == date(2026, 3, 1)

    def test_before_boundary_goes_to_previous_day(self):
        ts = datetime(2026, 3, 2, 2, 0, tzinfo=timezone.utc)
        assert logical_date_for_timestamp(ts, 4, "UTC") == date(2026, 3, 1)

    def test_at_boundary_stays_current_day(self):
        ts = datetime(2026, 3, 2, 4, 0, tzinfo=timezone.utc)
        assert logical_date_for_timestamp(ts, 4, "UTC") == date(2026, 3, 2)

    def test_after_boundary_stays_current_day(self):
        ts = datetime(2026, 3, 2, 5, 0, tzinfo=timezone.utc)
        assert logical_date_for_timestamp(ts, 4, "UTC") == date(2026, 3, 2)

    def test_1am_with_4am_boundary(self):
        ts = datetime(2026, 3, 2, 1, 0, tzinfo=timezone.utc)
        assert logical_date_for_timestamp(ts, 4, "UTC") == date(2026, 3, 1)

    def test_timezone_conversion(self):
        ts = datetime(2026, 3, 2, 10, 0, tzinfo=timezone.utc)
        assert logical_date_for_timestamp(ts, 4, "America/New_York") == date(2026, 3, 2)

    def test_timezone_conversion_before_boundary(self):
        ts = datetime(2026, 3, 2, 8, 0, tzinfo=timezone.utc)
        assert logical_date_for_timestamp(ts, 4, "America/New_York") == date(2026, 3, 1)

    def test_naive_utc_timestamp(self):
        ts = datetime(2026, 3, 2, 2, 0)
        assert logical_date_for_timestamp(ts, 4, "UTC") == date(2026, 3, 1)

    def test_zero_boundary_behaves_like_calendar(self):
        ts = datetime(2026, 3, 2, 23, 59, tzinfo=timezone.utc)
        assert logical_date_for_timestamp(ts, 0, "UTC") == date(2026, 3, 2)

        ts2 = datetime(2026, 3, 3, 0, 1, tzinfo=timezone.utc)
        assert logical_date_for_timestamp(ts2, 0, "UTC") == date(2026, 3, 3)
