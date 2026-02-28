import asyncio
import logging
from datetime import date, datetime, time, timedelta, timezone
from uuid import UUID

from src.repositories.activity_events import ActivityEventRepositoryInterface
from src.repositories.activity_sessions import ActivitySessionRepositoryInterface

logger = logging.getLogger(__name__)

_user_locks: dict[UUID, asyncio.Lock] = {}


def _get_user_lock(user_id: UUID) -> asyncio.Lock:
    if user_id not in _user_locks:
        _user_locks[user_id] = asyncio.Lock()
    return _user_locks[user_id]

MIN_SESSION_DURATION_SECONDS = 5
MERGE_GAP_SECONDS = 300  # merge same-app sessions separated by ≤5 min
SHORT_SESSION_THRESHOLD_SECONDS = 120  # drop finalized sessions shorter than 2 min


class ActivitySessionGenerator:
    def __init__(
        self,
        activity_repo: ActivityEventRepositoryInterface,
        session_repo: ActivitySessionRepositoryInterface,
    ):
        self.activity_repo = activity_repo
        self.session_repo = session_repo

    async def generate_incremental(self, user_id: UUID, event_timestamps: list[datetime]) -> int:
        async with _get_user_lock(user_id):
            return await self._generate_incremental(user_id, event_timestamps)

    async def _generate_incremental(self, user_id: UUID, event_timestamps: list[datetime]) -> int:
        if not event_timestamps:
            return 0

        earliest_new = min(event_timestamps)
        rebuild_from = earliest_new - timedelta(seconds=MERGE_GAP_SECONDS)

        # Iteratively expand the rebuild window to capture all sessions
        # that could be merged with new data.  Each iteration looks back
        # an extra MERGE_GAP to find sessions ending just before the
        # current boundary (they aren't "overlapping" but ARE within
        # merge distance).  Stops when no earlier sessions are found.
        for _ in range(10):
            lookback = rebuild_from - timedelta(seconds=MERGE_GAP_SECONDS)
            earliest_affected = await self.session_repo.get_earliest_affected_start(
                user_id, lookback
            )
            if earliest_affected is not None and earliest_affected < rebuild_from:
                rebuild_from = earliest_affected
            else:
                break

        await self.session_repo.delete_from_timestamp(user_id, rebuild_from)

        events = await self.activity_repo.get_by_time_range(
            user_id, rebuild_from, datetime.max.replace(tzinfo=timezone.utc),
            limit=100_000, offset=0,
        )

        if not events:
            return 0

        latest_event_time = max(e.timestamp for e in events)
        end_of_event_day = datetime.combine(latest_event_time.date(), time.max, tzinfo=timezone.utc)
        cap_time = min(datetime.now(timezone.utc), end_of_event_day)
        raw_sessions = self._build_sessions(events, cap_time)
        merged = self._merge_by_app(raw_sessions)
        filtered = [s for s in merged if self._duration_seconds(s) >= MIN_SESSION_DURATION_SECONDS]
        filtered = self._drop_noise_sessions(filtered)
        final = self._split_cross_midnight(filtered)

        if not final:
            return 0

        return await self.session_repo.bulk_create(user_id, final)

    async def generate_for_date(self, user_id: UUID, target_date: date) -> int:
        day_start = datetime.combine(target_date, time.min, tzinfo=timezone.utc)
        day_end = datetime.combine(target_date, time.max, tzinfo=timezone.utc)

        events = await self.activity_repo.get_by_time_range(
            user_id, day_start, day_end, limit=100_000, offset=0,
        )

        if not events:
            await self.session_repo.delete_for_date(user_id, target_date)
            return 0

        raw_sessions = self._build_sessions(events, day_end)
        merged = self._merge_by_app(raw_sessions)
        filtered = [s for s in merged if self._duration_seconds(s) >= MIN_SESSION_DURATION_SECONDS]
        filtered = self._drop_noise_sessions(filtered)
        final = self._split_cross_midnight(filtered)

        await self.session_repo.delete_for_date(user_id, target_date)

        if not final:
            return 0

        return await self.session_repo.bulk_create(user_id, final)

    def _build_sessions(self, events, cap_time: datetime) -> list[dict]:
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
                # No-op: next active_window will open a new session
                pass

            elif event_type == "active_window":
                app = event.app_name
                title = event.window_title
                url = event.url

                if current is not None:
                    if current["app_name"] == app:
                        # Same app — extend: update end_time, collect titles
                        current["end_time"] = ts
                        if title and title not in current["_titles_set"]:
                            current["_titles_set"].add(title)
                            current["window_titles"].append(title)
                        if url and not current["url"]:
                            current["url"] = url
                        continue
                    else:
                        # Different app — close current, open new
                        current["end_time"] = ts
                        sessions.append(current)
                        current = None

                # Open new session
                current = {
                    "app_name": app,
                    "window_title": title,
                    "window_titles": [title] if title else [],
                    "_titles_set": {title} if title else set(),
                    "url": url,
                    "start_time": ts,
                    "end_time": ts,
                }

        # Cap last open session
        if current is not None:
            now = datetime.now(timezone.utc)
            cap = min(now, cap_time)
            if cap > current["start_time"]:
                current["end_time"] = cap
            else:
                current["end_time"] = cap_time
            sessions.append(current)

        # Clean up internal tracking field
        for s in sessions:
            s.pop("_titles_set", None)

        return sessions

    def _merge_by_app(self, sessions: list[dict]) -> list[dict]:
        """Merge same-app sessions that are within MERGE_GAP_SECONDS of each other,
        even when separated by other-app sessions. This collapses rapid
        app-switching (e.g. Chrome↔Cursor every 5s) into larger blocks."""
        if not sessions:
            return []

        from collections import defaultdict

        groups: dict[str, list[dict]] = defaultdict(list)
        for s in sessions:
            groups[s["app_name"]].append(s)

        merged: list[dict] = []
        for app_sessions in groups.values():
            # Sessions are already in chronological order from _build_sessions
            current = app_sessions[0]
            for s in app_sessions[1:]:
                gap = (s["start_time"] - current["end_time"]).total_seconds()
                if gap <= MERGE_GAP_SECONDS:
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

    def _split_cross_midnight(self, sessions: list[dict]) -> list[dict]:
        result = []
        for s in sessions:
            start = s["start_time"]
            end = s["end_time"]
            start_date = start.date()
            end_date = end.date()

            if start_date == end_date:
                s["date"] = start_date
                result.append(s)
            else:
                # Split at midnight
                midnight = datetime.combine(
                    start_date + timedelta(days=1), time.min, tzinfo=start.tzinfo
                )
                first_half = {**s, "end_time": midnight, "date": start_date}
                second_half = {**s, "start_time": midnight, "date": end_date}
                result.append(first_half)
                result.append(second_half)

        return result

    @staticmethod
    def _drop_noise_sessions(sessions: list[dict]) -> list[dict]:
        """Remove short sessions that are finalized (past the merge window).

        A session is kept if it's either long enough or still recent enough
        that future events could merge into it and make it longer.
        """
        now = datetime.now(timezone.utc)
        merge_cutoff = now - timedelta(seconds=MERGE_GAP_SECONDS)
        result = []
        for s in sessions:
            duration = (s["end_time"] - s["start_time"]).total_seconds()
            is_short = duration < SHORT_SESSION_THRESHOLD_SECONDS
            is_finalized = s["end_time"] < merge_cutoff
            if is_short and is_finalized:
                continue
            result.append(s)
        return result

    @staticmethod
    def _duration_seconds(session: dict) -> float:
        return (session["end_time"] - session["start_time"]).total_seconds()
