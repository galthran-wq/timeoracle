from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo


def day_boundary_utc(logical_date: date, day_start_hour: int, tz: str) -> datetime:
    zone = ZoneInfo(tz)
    local_dt = datetime(logical_date.year, logical_date.month, logical_date.day, day_start_hour, tzinfo=zone)
    return local_dt.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)


def day_range_utc(logical_date: date, day_start_hour: int, tz: str) -> tuple[datetime, datetime]:
    start = day_boundary_utc(logical_date, day_start_hour, tz)
    next_date = logical_date + timedelta(days=1)
    end = day_boundary_utc(next_date, day_start_hour, tz)
    return start, end


def week_range_utc(start_date: date, day_start_hour: int, tz: str) -> tuple[datetime, datetime]:
    start = day_boundary_utc(start_date, day_start_hour, tz)
    end_date = start_date + timedelta(days=7)
    end = day_boundary_utc(end_date, day_start_hour, tz)
    return start, end


def logical_date_for_timestamp(ts: datetime, day_start_hour: int, tz: str) -> date:
    zone = ZoneInfo(tz)
    if ts.tzinfo is not None:
        local = ts.astimezone(zone)
    else:
        local = ts.replace(tzinfo=ZoneInfo("UTC")).astimezone(zone)
    if local.hour < day_start_hour:
        return (local - timedelta(days=1)).date()
    return local.date()
