from collections import defaultdict
from datetime import datetime, time, timedelta, timezone

from src.services.day_boundary import day_boundary_utc, logical_date_for_timestamp

MIN_SESSION_DURATION_SECONDS = 5
MERGE_GAP_SECONDS = 300
SHORT_SESSION_THRESHOLD_SECONDS = 120


def compute_sessions(
    events,
    cap_time: datetime,
    *,
    merge_gap_seconds: int = MERGE_GAP_SECONDS,
    min_session_seconds: int = MIN_SESSION_DURATION_SECONDS,
    noise_threshold_seconds: int = SHORT_SESSION_THRESHOLD_SECONDS,
    day_start_hour: int = 0,
    day_timezone: str = "UTC",
) -> list[dict]:
    raw = _build_sessions(events, cap_time)
    merged = _merge_by_app(raw, merge_gap_seconds=merge_gap_seconds)
    filtered = [s for s in merged if _duration_seconds(s) >= min_session_seconds]
    filtered = _drop_noise_sessions(filtered, merge_gap_seconds=merge_gap_seconds, noise_threshold_seconds=noise_threshold_seconds)
    return _split_cross_day_boundary(filtered, day_start_hour=day_start_hour, day_timezone=day_timezone)


def _build_sessions(events, cap_time: datetime) -> list[dict]:
    sessions = []
    current = None

    for event in events:
        event_type = event.event_type
        ts = event.timestamp

        if event_type == "idle_start":
            if current is not None:
                current["end_time"] = ts
                sessions.append(current)
                current = None

        elif event_type == "idle_end":
            pass

        elif event_type == "active_window":
            app = event.app_name
            title = event.window_title
            url = event.url

            if current is not None:
                if current["app_name"] == app:
                    current["end_time"] = ts
                    if title and title not in current["_titles_set"]:
                        current["_titles_set"].add(title)
                        current["window_titles"].append(title)
                    if url and not current["url"]:
                        current["url"] = url
                    continue
                else:
                    current["end_time"] = ts
                    sessions.append(current)
                    current = None

            current = {
                "app_name": app,
                "window_title": title,
                "window_titles": [title] if title else [],
                "_titles_set": {title} if title else set(),
                "url": url,
                "start_time": ts,
                "end_time": ts,
            }

    if current is not None:
        now = datetime.now(timezone.utc)
        cap = min(now, cap_time)
        if cap > current["start_time"]:
            current["end_time"] = cap
        else:
            current["end_time"] = cap_time
        sessions.append(current)

    for s in sessions:
        s.pop("_titles_set", None)

    return sessions


def _merge_by_app(sessions: list[dict], *, merge_gap_seconds: int = MERGE_GAP_SECONDS) -> list[dict]:
    if not sessions:
        return []

    groups: dict[str, list[dict]] = defaultdict(list)
    for s in sessions:
        groups[s["app_name"]].append(s)

    merged: list[dict] = []
    for app_sessions in groups.values():
        current = app_sessions[0]
        for s in app_sessions[1:]:
            gap = (s["start_time"] - current["end_time"]).total_seconds()
            if gap <= merge_gap_seconds:
                current["end_time"] = max(current["end_time"], s["end_time"])
                existing = set(current["window_titles"])
                for t in s["window_titles"]:
                    if t not in existing:
                        current["window_titles"].append(t)
                        existing.add(t)
                if s["url"] and not current["url"]:
                    current["url"] = s["url"]
            else:
                merged.append(current)
                current = s
        merged.append(current)

    merged.sort(key=lambda s: s["start_time"])
    return merged


def _split_cross_day_boundary(
    sessions: list[dict],
    *,
    day_start_hour: int = 0,
    day_timezone: str = "UTC",
) -> list[dict]:
    result = []
    for s in sessions:
        start = s["start_time"]
        end = s["end_time"]
        start_logical = logical_date_for_timestamp(start, day_start_hour, day_timezone)
        end_logical = logical_date_for_timestamp(end, day_start_hour, day_timezone)

        if start_logical == end_logical:
            s["date"] = start_logical
            result.append(s)
        else:
            cursor = start
            current_logical = start_logical
            while current_logical < end_logical:
                next_logical = current_logical + timedelta(days=1)
                boundary = day_boundary_utc(next_logical, day_start_hour, day_timezone)
                if boundary.tzinfo is None:
                    boundary = boundary.replace(tzinfo=timezone.utc)
                split_point = min(boundary, end)
                result.append({**s, "start_time": cursor, "end_time": split_point, "date": current_logical})
                cursor = split_point
                current_logical = next_logical
            if cursor < end:
                result.append({**s, "start_time": cursor, "end_time": end, "date": end_logical})

    return result


def _drop_noise_sessions(
    sessions: list[dict],
    *,
    merge_gap_seconds: int = MERGE_GAP_SECONDS,
    noise_threshold_seconds: int = SHORT_SESSION_THRESHOLD_SECONDS,
) -> list[dict]:
    now = datetime.now(timezone.utc)
    merge_cutoff = now - timedelta(seconds=merge_gap_seconds)
    result = []
    for s in sessions:
        duration = (s["end_time"] - s["start_time"]).total_seconds()
        is_short = duration < noise_threshold_seconds
        is_finalized = s["end_time"] < merge_cutoff
        if is_short and is_finalized:
            continue
        result.append(s)
    return result


def _duration_seconds(session: dict) -> float:
    return (session["end_time"] - session["start_time"]).total_seconds()
