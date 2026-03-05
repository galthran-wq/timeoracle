#!/usr/bin/env python3
import asyncio
import sys
import os
from datetime import date, datetime, time, timezone, timedelta

script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
sys.path.insert(0, project_root)
if os.path.exists('/app/src'):
    sys.path.insert(0, '/app')

from sqlalchemy import select
from src.core.database import AsyncSessionLocal
from src.models.postgres import UserModel, ActivityEventModel, TimelineEntryModel
from src.services.activity_session_generator import compute_sessions
from src.services.day_boundary import day_range_utc


async def main():
    if len(sys.argv) < 3:
        print("Usage: python scripts/inspect_timeline.py <email> <date_from> [date_to]")
        print("  e.g. python scripts/inspect_timeline.py leo@gmail.com 2026-03-03")
        print("  e.g. python scripts/inspect_timeline.py leo@gmail.com 2026-03-01 2026-03-03")
        sys.exit(1)

    email = sys.argv[1]
    date_from = date.fromisoformat(sys.argv[2])
    date_to = date.fromisoformat(sys.argv[3]) if len(sys.argv) > 3 else date_from

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(UserModel).where(UserModel.email == email)
        )
        user = result.scalar_one_or_none()
        if not user:
            print(f"User not found: {email}")
            sys.exit(1)

        cfg = user.session_config or {}
        day_start_hour = cfg.get("day_start_hour", 0)
        day_tz = cfg.get("timezone", "UTC")

        print(f"User: {user.email} ({user.id})")
        print(f"Config: day_start_hour={day_start_hour}, timezone={day_tz}")
        print(f"Date range: {date_from} to {date_to}")
        print()

        current = date_from
        while current <= date_to:
            range_start, range_end = day_range_utc(current, day_start_hour, day_tz)
            range_start_aware = range_start.replace(tzinfo=timezone.utc)
            range_end_aware = range_end.replace(tzinfo=timezone.utc)

            print("=" * 100)
            print(f"DATE: {current}  (UTC range: {range_start_aware} -> {range_end_aware})")
            print("=" * 100)

            events_result = await session.execute(
                select(ActivityEventModel)
                .where(
                    ActivityEventModel.user_id == user.id,
                    ActivityEventModel.timestamp >= range_start_aware,
                    ActivityEventModel.timestamp < range_end_aware,
                )
                .order_by(ActivityEventModel.timestamp.asc())
            )
            events = list(events_result.scalars().all())

            print(f"\nACTIVITY EVENTS: {len(events)} raw events")

            if events:
                cap_time = min(datetime.now(timezone.utc), range_end_aware)
                sessions = compute_sessions(
                    events,
                    cap_time,
                    merge_gap_seconds=cfg.get("merge_gap_seconds", 300),
                    min_session_seconds=cfg.get("min_session_seconds", 5),
                    noise_threshold_seconds=cfg.get("noise_threshold_seconds", 120),
                    day_start_hour=day_start_hour,
                    day_timezone=day_tz,
                )
                print(f"COMPUTED SESSIONS: {len(sessions)}")
                for i, s in enumerate(sessions):
                    dur = (s["end_time"] - s["start_time"]).total_seconds()
                    titles = s.get("window_titles", [])
                    title_str = ", ".join(titles[:3])
                    if len(titles) > 3:
                        title_str += f" (+{len(titles)-3} more)"
                    print(f"  [{i+1}] {s['start_time'].strftime('%H:%M:%S')} - {s['end_time'].strftime('%H:%M:%S')} ({dur/60:.1f}m) "
                          f"| {s['app_name']} | {title_str}")

            entries_result = await session.execute(
                select(TimelineEntryModel)
                .where(
                    TimelineEntryModel.user_id == user.id,
                    TimelineEntryModel.start_time >= range_start_aware,
                    TimelineEntryModel.start_time < range_end_aware,
                )
                .order_by(TimelineEntryModel.start_time.asc())
            )
            entries = list(entries_result.scalars().all())

            print(f"\nTIMELINE ENTRIES: {len(entries)}")
            for i, e in enumerate(entries):
                dur = (e.end_time - e.start_time).total_seconds()
                print(f"  [{i+1}] {e.start_time.strftime('%H:%M:%S')} - {e.end_time.strftime('%H:%M:%S')} ({dur/60:.1f}m) "
                      f"| {e.label:<40} | cat={e.category or '-':<15} | src={e.source:<12} "
                      f"| edited={e.edited_by_user} | conf={e.confidence or 0:.2f}")
                print(f"        id={e.id}  chat_id={e.chat_id}  created={e.created_at}")

            overlaps = []
            for i in range(len(entries)):
                for j in range(i + 1, len(entries)):
                    a, b = entries[i], entries[j]
                    if a.start_time < b.end_time and b.start_time < a.end_time:
                        overlap_start = max(a.start_time, b.start_time)
                        overlap_end = min(a.end_time, b.end_time)
                        overlap_dur = (overlap_end - overlap_start).total_seconds()
                        overlaps.append((i+1, j+1, overlap_dur))

            if overlaps:
                print(f"\n  *** OVERLAPPING ENTRIES: {len(overlaps)} ***")
                for a_idx, b_idx, dur in overlaps:
                    print(f"    Entry [{a_idx}] overlaps with [{b_idx}] by {dur/60:.1f} min")

            chat_ids = set(e.chat_id for e in entries if e.chat_id)
            if chat_ids:
                print(f"\n  UNIQUE CHAT IDs (generation runs): {len(chat_ids)}")
                for cid in sorted(chat_ids, key=str):
                    count = sum(1 for e in entries if e.chat_id == cid)
                    created = min(e.created_at for e in entries if e.chat_id == cid)
                    print(f"    {cid} -> {count} entries (created ~{created})")

            print()
            current += timedelta(days=1)


if __name__ == "__main__":
    asyncio.run(main())
