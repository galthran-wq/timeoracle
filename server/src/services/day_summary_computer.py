from collections import defaultdict

from src.agent.prompts import DEFAULT_CATEGORIES

FOCUS_GAP_TOLERANCE_MINUTES = 5
CONTEXT_SWITCH_GAP_LIMIT_MINUTES = 30


def _resolve_category_type(category: str | None, user_categories: dict | None) -> str:
    if not category:
        return "uncategorized"
    cats = user_categories or DEFAULT_CATEGORIES
    cfg = cats.get(category)
    if isinstance(cfg, dict):
        return cfg.get("type", "neutral")
    return "neutral"


def compute_day_summary(
    timeline_entries: list,
    sessions: list,
    user_categories: dict | None = None,
) -> dict:
    productive = 0.0
    neutral = 0.0
    distraction = 0.0
    uncategorized = 0.0

    for entry in timeline_entries:
        start = entry.start_time
        end = entry.end_time
        minutes = (end - start).total_seconds() / 60.0
        cat_type = _resolve_category_type(entry.category, user_categories)
        if cat_type == "productive":
            productive += minutes
        elif cat_type == "distraction":
            distraction += minutes
        elif cat_type == "uncategorized":
            uncategorized += minutes
        else:
            neutral += minutes

    total_active = productive + neutral + distraction + uncategorized

    focus_score = None
    distraction_score = None
    if total_active > 0:
        focus_score = productive / total_active
        distraction_score = distraction / total_active

    longest_focus = _compute_longest_focus(timeline_entries, user_categories)
    switches = _compute_context_switches(timeline_entries, user_categories)

    cat_breakdown = _compute_category_breakdown(timeline_entries, user_categories)
    app_breakdown = _compute_app_breakdown(sessions)

    top_category = cat_breakdown[0]["category"] if cat_breakdown else None
    top_app = app_breakdown[0]["app"] if app_breakdown else None

    return {
        "total_active_minutes": round(total_active, 2),
        "productive_minutes": round(productive, 2),
        "neutral_minutes": round(neutral, 2),
        "distraction_minutes": round(distraction, 2),
        "uncategorized_minutes": round(uncategorized, 2),
        "focus_score": round(focus_score, 4) if focus_score is not None else None,
        "distraction_score": round(distraction_score, 4) if distraction_score is not None else None,
        "longest_focus_minutes": round(longest_focus, 2),
        "context_switches": switches,
        "session_count": len(sessions),
        "top_app": top_app,
        "top_category": top_category,
        "category_breakdown": cat_breakdown,
        "app_breakdown": app_breakdown[:10],
    }


def _compute_longest_focus(entries: list, user_categories: dict | None) -> float:
    sorted_entries = sorted(entries, key=lambda e: e.start_time)

    max_streak = 0.0
    streak_start = None
    streak_end = None

    for entry in sorted_entries:
        cat_type = _resolve_category_type(entry.category, user_categories)
        if cat_type != "productive":
            if streak_start is not None:
                duration = (streak_end - streak_start).total_seconds() / 60.0
                max_streak = max(max_streak, duration)
                streak_start = None
                streak_end = None
            continue

        if streak_start is None:
            streak_start = entry.start_time
            streak_end = entry.end_time
        else:
            gap = (entry.start_time - streak_end).total_seconds() / 60.0
            if gap <= FOCUS_GAP_TOLERANCE_MINUTES:
                streak_end = max(streak_end, entry.end_time)
            else:
                duration = (streak_end - streak_start).total_seconds() / 60.0
                max_streak = max(max_streak, duration)
                streak_start = entry.start_time
                streak_end = entry.end_time

    if streak_start is not None:
        duration = (streak_end - streak_start).total_seconds() / 60.0
        max_streak = max(max_streak, duration)

    return max_streak


def _compute_context_switches(entries: list, user_categories: dict | None) -> int:
    sorted_entries = sorted(entries, key=lambda e: e.start_time)
    switches = 0
    prev_type = None
    prev_end = None

    for entry in sorted_entries:
        cat_type = _resolve_category_type(entry.category, user_categories)
        if prev_end is not None:
            gap = (entry.start_time - prev_end).total_seconds() / 60.0
            if gap <= CONTEXT_SWITCH_GAP_LIMIT_MINUTES and cat_type != prev_type:
                switches += 1
        prev_type = cat_type
        prev_end = entry.end_time

    return switches


def _compute_category_breakdown(entries: list, user_categories: dict | None) -> list[dict]:
    by_cat: dict[str, float] = defaultdict(float)
    for entry in entries:
        minutes = (entry.end_time - entry.start_time).total_seconds() / 60.0
        cat = entry.category or "Uncategorized"
        by_cat[cat] += minutes

    result = []
    for cat, minutes in sorted(by_cat.items(), key=lambda x: -x[1]):
        cat_type = _resolve_category_type(cat if cat != "Uncategorized" else None, user_categories)
        result.append({"category": cat, "type": cat_type, "minutes": round(minutes, 2)})
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
