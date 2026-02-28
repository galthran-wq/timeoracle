#!/usr/bin/env python3
"""
Rebuild activity sessions for a user.
Usage:
  python scripts/rebuild_sessions.py <email> [--date 2026-02-23]
  python scripts/rebuild_sessions.py <email>  # rebuilds today
"""

import asyncio
import sys
import os
from datetime import date, datetime, timezone

script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
sys.path.insert(0, project_root)
if os.path.exists('/app/src'):
    sys.path.insert(0, '/app')

from sqlalchemy import select
from src.core.database import AsyncSessionLocal
from src.models.postgres.users import UserModel
from src.repositories.activity_events import ActivityEventRepository
from src.repositories.activity_sessions import ActivitySessionRepository
from src.services.activity_session_generator import ActivitySessionGenerator


async def rebuild(email: str, target_date: date):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(UserModel).where(UserModel.email == email)
        )
        user = result.scalar_one_or_none()
        if not user:
            print(f"User '{email}' not found")
            sys.exit(1)

        activity_repo = ActivityEventRepository(session)
        session_repo = ActivitySessionRepository(session)
        generator = ActivitySessionGenerator(activity_repo, session_repo)

        count = await generator.generate_for_date(user.id, target_date)
        print(f"Rebuilt {count} sessions for {email} on {target_date}")


async def main():
    if len(sys.argv) < 2 or sys.argv[1] in ('--help', '-h'):
        print(__doc__.strip())
        sys.exit(0)

    email = sys.argv[1]
    target = date.today()

    if '--date' in sys.argv:
        idx = sys.argv.index('--date')
        target = date.fromisoformat(sys.argv[idx + 1])

    await rebuild(email, target)


if __name__ == "__main__":
    asyncio.run(main())
