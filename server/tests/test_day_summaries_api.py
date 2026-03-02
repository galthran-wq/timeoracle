import uuid
from datetime import date, datetime, timedelta, timezone

import httpx
import pytest

from src.core.auth import create_token_for_user
from src.models.postgres.timeline_entries import TimelineEntryModel
from src.models.postgres.users import UserModel
from sqlalchemy.ext.asyncio import AsyncSession


async def _seed_timeline(db_session: AsyncSession, user_id, target_date=None):
    d = target_date or date(2026, 3, 1)
    entries = [
        TimelineEntryModel(
            user_id=user_id,
            date=d,
            start_time=datetime(d.year, d.month, d.day, 9, 0, tzinfo=timezone.utc),
            end_time=datetime(d.year, d.month, d.day, 11, 0, tzinfo=timezone.utc),
            label="Coding",
            category="Work",
            source="ai_generated",
        ),
        TimelineEntryModel(
            user_id=user_id,
            date=d,
            start_time=datetime(d.year, d.month, d.day, 11, 0, tzinfo=timezone.utc),
            end_time=datetime(d.year, d.month, d.day, 11, 30, tzinfo=timezone.utc),
            label="YouTube",
            category="Entertainment",
            source="ai_generated",
        ),
    ]
    for e in entries:
        db_session.add(e)
    await db_session.commit()


class TestGetDaySummary:
    async def test_404_when_no_summary(self, authed_client: httpx.AsyncClient):
        resp = await authed_client.get("/api/day-summaries/2026-03-01")
        assert resp.status_code == 404

    async def test_returns_summary_after_generate(
        self, authed_client: httpx.AsyncClient, db_session: AsyncSession, test_user: UserModel,
    ):
        await _seed_timeline(db_session, test_user.id)
        gen = await authed_client.post("/api/day-summaries/2026-03-01/generate")
        assert gen.status_code == 200

        resp = await authed_client.get("/api/day-summaries/2026-03-01")
        assert resp.status_code == 200
        body = resp.json()
        assert body["date"] == "2026-03-01"
        assert body["total_active_minutes"] > 0
        assert body["productive_minutes"] > 0
        assert body["distraction_minutes"] > 0
        assert body["session_count"] == 0
        assert body["category_breakdown"] is not None
        assert len(body["category_breakdown"]) == 2

    async def test_auth_required(self, client: httpx.AsyncClient):
        resp = await client.get("/api/day-summaries/2026-03-01")
        assert resp.status_code == 401


class TestForceGenerate:
    async def test_404_when_no_timeline_data(self, authed_client: httpx.AsyncClient):
        resp = await authed_client.post("/api/day-summaries/2026-01-01/generate")
        assert resp.status_code == 404

    async def test_generates_with_metrics(
        self, authed_client: httpx.AsyncClient, db_session: AsyncSession, test_user: UserModel,
    ):
        await _seed_timeline(db_session, test_user.id)
        resp = await authed_client.post("/api/day-summaries/2026-03-01/generate")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_active_minutes"] == 150.0
        assert body["productive_minutes"] == 120.0
        assert body["distraction_minutes"] == 30.0
        assert body["is_partial"] is False


class TestTrends:
    async def test_trends_date_range(
        self, authed_client: httpx.AsyncClient, db_session: AsyncSession, test_user: UserModel,
    ):
        await _seed_timeline(db_session, test_user.id, date(2026, 3, 1))
        await authed_client.post("/api/day-summaries/2026-03-01/generate")

        resp = await authed_client.get(
            "/api/day-summaries", params={"start": "2026-02-28", "end": "2026-03-02"}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["start"] == "2026-02-28"
        assert body["end"] == "2026-03-02"
        assert len(body["summaries"]) == 1
        assert body["summaries"][0]["date"] == "2026-03-01"

    async def test_90_day_limit(self, authed_client: httpx.AsyncClient):
        resp = await authed_client.get(
            "/api/day-summaries", params={"start": "2025-01-01", "end": "2026-03-01"}
        )
        assert resp.status_code == 400

    async def test_end_before_start(self, authed_client: httpx.AsyncClient):
        resp = await authed_client.get(
            "/api/day-summaries", params={"start": "2026-03-02", "end": "2026-03-01"}
        )
        assert resp.status_code == 400


class TestUserIsolation:
    async def test_cannot_see_other_users_summary(
        self, authed_client: httpx.AsyncClient, db_session: AsyncSession, test_user: UserModel,
    ):
        other_user = UserModel(
            id=uuid.uuid4(),
            email="other@example.com",
            password_hash="fake",
            is_verified=True,
        )
        db_session.add(other_user)
        await db_session.commit()

        await _seed_timeline(db_session, other_user.id)

        other_token = create_token_for_user(other_user)
        other_headers = {"Authorization": f"Bearer {other_token}"}

        other_client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=authed_client._transport.app),
            base_url="http://test",
            headers=other_headers,
        )
        async with other_client:
            resp = await other_client.post("/api/day-summaries/2026-03-01/generate")
            assert resp.status_code == 200

        resp = await authed_client.get("/api/day-summaries/2026-03-01")
        assert resp.status_code == 404
