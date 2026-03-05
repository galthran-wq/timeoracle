from collections import defaultdict

FOCUS_GAP_TOLERANCE_MINUTES = 5
CONTEXT_SWITCH_GAP_LIMIT_MINUTES = 30
FOCUS_SCORE_THRESHOLD = 0.7
POINT_INTERVAL_MINUTES = 10


def compute_day_summary(
    timeline_entries: list,
    sessions: list,
    productivity_points: list | None = None,
) -> dict:
    total_active = 0.0
    for entry in timeline_entries:
        minutes = (entry.end_time - entry.start_time).total_seconds() / 60.0
        total_active += minutes

    points = productivity_points or []

    longest_focus = _compute_longest_focus(points)
    switches = _compute_context_switches(points)

    cat_breakdown = _compute_category_breakdown(timeline_entries)
    app_breakdown = _compute_app_breakdown(sessions)

    top_category = cat_breakdown[0]["category"] if cat_breakdown else None
    top_app = app_breakdown[0]["app"] if app_breakdown else None

    depth_breakdown = _compute_depth_breakdown(points)
    avg_focus = _compute_avg_focus_score(points)
    total_hours = total_active / 60.0
    frag_index = _compute_fragmentation_index(points, switches, total_hours)
    sph = _compute_switches_per_hour(switches, total_hours)
    sessions_25 = _compute_focus_sessions(points, 25)
    sessions_90 = _compute_focus_sessions(points, 90)

    productivity_score = _compute_productivity_score_avg(points)
    overall_productivity_score = _compute_overall_productivity_score_avg(points)
    work_minutes = _compute_work_minutes(points)

    return {
        "total_active_minutes": round(total_active, 2),
        "longest_focus_minutes": round(longest_focus, 2),
        "context_switches": switches,
        "session_count": len(sessions),
        "top_app": top_app,
        "top_category": top_category,
        "category_breakdown": cat_breakdown,
        "app_breakdown": app_breakdown[:10],
        "deep_work_minutes": round(depth_breakdown["deep"], 2),
        "shallow_work_minutes": round(depth_breakdown["shallow"], 2),
        "reactive_minutes": round(depth_breakdown["reactive"], 2),
        "avg_focus_score": round(avg_focus, 4) if avg_focus is not None else None,
        "fragmentation_index": round(frag_index, 2) if frag_index is not None else None,
        "switches_per_hour": round(sph, 2) if sph is not None else None,
        "focus_sessions_25min": sessions_25,
        "focus_sessions_90min": sessions_90,
        "productivity_score": round(productivity_score, 1) if productivity_score is not None else None,
        "overall_productivity_score": round(overall_productivity_score, 1) if overall_productivity_score is not None else None,
        "work_minutes": round(work_minutes, 2),
    }


def _compute_longest_focus(points: list) -> float:
    sorted_points = sorted(points, key=lambda p: p.interval_start)

    max_streak = 0.0
    streak_start = None
    streak_end = None

    for point in sorted_points:
        fs = getattr(point, "focus_score", None)
        is_focused = fs is not None and fs >= FOCUS_SCORE_THRESHOLD
        if not is_focused:
            if streak_start is not None:
                duration = (streak_end - streak_start).total_seconds() / 60.0
                max_streak = max(max_streak, duration)
                streak_start = None
                streak_end = None
            continue

        from datetime import timedelta
        point_end = point.interval_start + timedelta(minutes=POINT_INTERVAL_MINUTES)

        if streak_start is None:
            streak_start = point.interval_start
            streak_end = point_end
        else:
            gap = (point.interval_start - streak_end).total_seconds() / 60.0
            if gap <= FOCUS_GAP_TOLERANCE_MINUTES:
                streak_end = max(streak_end, point_end)
            else:
                duration = (streak_end - streak_start).total_seconds() / 60.0
                max_streak = max(max_streak, duration)
                streak_start = point.interval_start
                streak_end = point_end

    if streak_start is not None:
        duration = (streak_end - streak_start).total_seconds() / 60.0
        max_streak = max(max_streak, duration)

    return max_streak


def _compute_context_switches(points: list) -> int:
    sorted_points = sorted(points, key=lambda p: p.interval_start)
    switches = 0
    prev_depth = None
    prev_end = None

    for point in sorted_points:
        from datetime import timedelta
        point_end = point.interval_start + timedelta(minutes=POINT_INTERVAL_MINUTES)
        depth = getattr(point, "depth", None) or "unknown"

        if prev_end is not None:
            gap = (point.interval_start - prev_end).total_seconds() / 60.0
            if gap <= CONTEXT_SWITCH_GAP_LIMIT_MINUTES and depth != prev_depth:
                switches += 1

        prev_depth = depth
        prev_end = point_end

    return switches


def _compute_category_breakdown(entries: list) -> list[dict]:
    by_cat: dict[str, float] = defaultdict(float)
    for entry in entries:
        minutes = (entry.end_time - entry.start_time).total_seconds() / 60.0
        cat = entry.category or "Uncategorized"
        by_cat[cat] += minutes

    result = []
    for cat, minutes in sorted(by_cat.items(), key=lambda x: -x[1]):
        result.append({"category": cat, "minutes": round(minutes, 2)})
    return result


def _compute_app_breakdown(sessions: list) -> list[dict]:
    by_app: dict[str, float] = defaultdict(float)
    for s in sessions:
        start = s["start_time"]
        end = s["end_time"]
        minutes = (end - start).total_seconds() / 60.0
        by_app[s["app_name"]] += minutes

    result = []
    for app, minutes in sorted(by_app.items(), key=lambda x: -x[1]):
        result.append({"app": app, "minutes": round(minutes, 2)})
    return result


def _compute_depth_breakdown(points: list) -> dict[str, float]:
    breakdown = {"deep": 0.0, "shallow": 0.0, "reactive": 0.0}
    for point in points:
        depth = getattr(point, "depth", None)
        if depth in breakdown:
            breakdown[depth] += POINT_INTERVAL_MINUTES
    return breakdown


def _compute_avg_focus_score(points: list) -> float | None:
    total = 0.0
    count = 0
    for point in points:
        fs = getattr(point, "focus_score", None)
        if fs is not None:
            total += fs
            count += 1
    if count == 0:
        return None
    return total / count


def _compute_fragmentation_index(
    points: list,
    context_switches: int,
    total_hours: float,
) -> float | None:
    if total_hours <= 0 or not points:
        return None

    sph = context_switches / total_hours

    distinct_depths = len({
        getattr(point, "depth", None) or "unknown" for point in points
    })

    total_minutes = total_hours * 60
    avg_point_duration = total_minutes / len(points) if points else 60

    sph_score = min(sph / 6.0, 1.0)
    depth_score = min((distinct_depths - 1) / 2.0, 1.0)
    duration_score = max(0.0, 1.0 - (avg_point_duration / 60.0))

    raw = (sph_score * 0.5) + (duration_score * 0.3) + (depth_score * 0.2)
    return raw * 10.0


def _compute_switches_per_hour(switches: int, total_hours: float) -> float | None:
    if total_hours <= 0:
        return None
    return switches / total_hours


def _compute_focus_sessions(points: list, min_minutes: int) -> int:
    sorted_points = sorted(points, key=lambda p: p.interval_start)
    count = 0
    streak_start = None
    streak_end = None

    def _check_streak():
        nonlocal count
        if streak_start is not None:
            duration = (streak_end - streak_start).total_seconds() / 60.0
            if duration >= min_minutes:
                count += 1

    for point in sorted_points:
        fs = getattr(point, "focus_score", None)
        is_focused = fs is not None and fs >= FOCUS_SCORE_THRESHOLD

        from datetime import timedelta
        point_end = point.interval_start + timedelta(minutes=POINT_INTERVAL_MINUTES)

        if not is_focused:
            _check_streak()
            streak_start = None
            streak_end = None
            continue

        if streak_start is None:
            streak_start = point.interval_start
            streak_end = point_end
        else:
            gap = (point.interval_start - streak_end).total_seconds() / 60.0
            if gap <= FOCUS_GAP_TOLERANCE_MINUTES:
                streak_end = max(streak_end, point_end)
            else:
                _check_streak()
                streak_start = point.interval_start
                streak_end = point_end

    _check_streak()
    return count


def _compute_productivity_score_avg(points: list) -> float | None:
    work_scores = []
    for point in points:
        is_work = getattr(point, "is_work", False)
        score = getattr(point, "productivity_score", None)
        if is_work and score is not None:
            work_scores.append(score)
    if not work_scores:
        return None
    return sum(work_scores) / len(work_scores)


def _compute_overall_productivity_score_avg(points: list) -> float | None:
    scores = []
    for point in points:
        score = getattr(point, "productivity_score", None)
        if score is not None:
            scores.append(score)
    if not scores:
        return None
    return sum(scores) / len(scores)


def _compute_work_minutes(points: list) -> float:
    count = 0
    for point in points:
        if getattr(point, "is_work", False):
            count += 1
    return count * POINT_INTERVAL_MINUTES
