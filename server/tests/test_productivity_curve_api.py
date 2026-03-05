import uuid
from datetime import date, datetime, timezone

import httpx
import pytest

from src.models.postgres.productivity_points import ProductivityPointModel
from src.models.postgres.users import UserModel
from sqlalchemy.ext.asyncio import AsyncSession


async def _seed_points(db_session: AsyncSession, user_id, target_date=None):
    d = target_date or date(2026, 3, 1)
    points = [
        ProductivityPointModel(
            user_id=user_id,
            date=d,
            interval_start=datetime(d.year, d.month, d.day, 9, 0, tzinfo=timezone.utc),
            focus_score=0.9,
            depth="deep",
            productivity_score=90.0,
            category="Work",
            color="#3B82F6",
            is_work=True,
        ),
        ProductivityPointModel(
            user_id=user_id,
            date=d,
            interval_start=datetime(d.year, d.month, d.day, 9, 10, tzinfo=timezone.utc),
            focus_score=0.6,
            depth="shallow",
            productivity_score=36.0,
            category="Entertainment",
            color="#EF4444",
            is_work=False,
        ),
    ]
    for p in points:
        db_session.add(p)
    await db_session.commit()


class TestGetProductivityCurve:
    async def test_empty_returns_no_points(self, authed_client: httpx.AsyncClient):
        resp = await authed_client.get("/api/productivity-curve/2026-03-01")
        assert resp.status_code == 200
        body = resp.json()
        assert body["date"] == "2026-03-01"
        assert body["points"] == []
        assert body["day_score"] is None
        assert body["work_minutes"] == 0

    async def test_returns_points(
        self, authed_client: httpx.AsyncClient, db_session: AsyncSession, test_user: UserModel,
    ):
        await _seed_points(db_session, test_user.id)
        resp = await authed_client.get("/api/productivity-curve/2026-03-01")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["points"]) == 2
        assert body["day_score"] == 90.0
        assert body["work_minutes"] == 10.0

    async def test_auth_required(self, client: httpx.AsyncClient):
        resp = await client.get("/api/productivity-curve/2026-03-01")
        assert resp.status_code == 401


class TestGetProductivityCurveRange:
    async def test_range_query(
        self, authed_client: httpx.AsyncClient, db_session: AsyncSession, test_user: UserModel,
    ):
        await _seed_points(db_session, test_user.id, date(2026, 3, 1))
        resp = await authed_client.get(
            "/api/productivity-curve",
            params={"start": "2026-02-28", "end": "2026-03-02"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["date"] == "2026-03-01"

    async def test_90_day_limit(self, authed_client: httpx.AsyncClient):
        resp = await authed_client.get(
            "/api/productivity-curve",
            params={"start": "2025-01-01", "end": "2026-03-01"},
        )
        assert resp.status_code == 400

    async def test_end_before_start(self, authed_client: httpx.AsyncClient):
        resp = await authed_client.get(
            "/api/productivity-curve",
            params={"start": "2026-03-02", "end": "2026-03-01"},
        )
        assert resp.status_code == 400
