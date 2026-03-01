import uuid
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from src.models.postgres.users import UserModel


def make_event(**overrides):
    defaults = {
        "client_event_id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": "active_window",
        "app_name": "VS Code",
        "window_title": "main.py - digitalgulag",
    }
    defaults.update(overrides)
    return defaults


# ── POST /api/activity/events ──────────────────────────────────────


class TestIngestEvents:
    async def test_ingest_single_event(self, authed_client: httpx.AsyncClient):
        resp = await authed_client.post(
            "/api/activity/events",
            json={"events": [make_event()]},
        )
        assert resp.status_code == 201
        assert resp.json()["inserted_count"] == 1

    async def test_ingest_batch(self, authed_client: httpx.AsyncClient):
        events = [make_event() for _ in range(10)]
        resp = await authed_client.post(
            "/api/activity/events",
            json={"events": events},
        )
        assert resp.status_code == 201
        assert resp.json()["inserted_count"] == 10

    async def test_idempotent_insert(self, authed_client: httpx.AsyncClient):
        event_id = str(uuid.uuid4())
        batch = {"events": [make_event(client_event_id=event_id)]}

        resp1 = await authed_client.post("/api/activity/events", json=batch)
        assert resp1.status_code == 201
        assert resp1.json()["inserted_count"] == 1

        resp2 = await authed_client.post("/api/activity/events", json=batch)
        assert resp2.status_code == 201
        assert resp2.json()["inserted_count"] == 0

    async def test_mixed_duplicates(self, authed_client: httpx.AsyncClient):
        dup_id = str(uuid.uuid4())
        batch1 = {"events": [make_event(client_event_id=dup_id)]}
        await authed_client.post("/api/activity/events", json=batch1)

        batch2 = {"events": [
            make_event(client_event_id=dup_id),
            make_event(),
        ]}
        resp = await authed_client.post("/api/activity/events", json=batch2)
        assert resp.status_code == 201
        assert resp.json()["inserted_count"] == 1

    async def test_all_event_types(self, authed_client: httpx.AsyncClient):
        events = [
            make_event(event_type="active_window"),
            make_event(event_type="idle_start"),
            make_event(event_type="idle_end"),
        ]
        resp = await authed_client.post(
            "/api/activity/events",
            json={"events": events},
        )
        assert resp.status_code == 201
        assert resp.json()["inserted_count"] == 3

    async def test_event_with_url_and_metadata(self, authed_client: httpx.AsyncClient):
        event = make_event(
            url="https://github.com/digitalgulag",
            metadata={"tab_count": 5, "incognito": False},
        )
        resp = await authed_client.post(
            "/api/activity/events",
            json={"events": [event]},
        )
        assert resp.status_code == 201
        assert resp.json()["inserted_count"] == 1

    async def test_reject_future_timestamp(self, authed_client: httpx.AsyncClient):
        future = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
        resp = await authed_client.post(
            "/api/activity/events",
            json={"events": [make_event(timestamp=future)]},
        )
        assert resp.status_code == 400
        body = resp.json()["detail"]
        assert body["errors"][0]["field"] == "timestamp"

    async def test_reject_old_timestamp(self, authed_client: httpx.AsyncClient):
        old = (datetime.now(timezone.utc) - timedelta(days=31)).isoformat()
        resp = await authed_client.post(
            "/api/activity/events",
            json={"events": [make_event(timestamp=old)]},
        )
        assert resp.status_code == 400

    async def test_reject_naive_timestamp(self, authed_client: httpx.AsyncClient):
        naive = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
        resp = await authed_client.post(
            "/api/activity/events",
            json={"events": [make_event(timestamp=naive)]},
        )
        assert resp.status_code == 422

    async def test_reject_unknown_event_type(self, authed_client: httpx.AsyncClient):
        resp = await authed_client.post(
            "/api/activity/events",
            json={"events": [make_event(event_type="unknown_type")]},
        )
        assert resp.status_code == 422

    async def test_reject_empty_batch(self, authed_client: httpx.AsyncClient):
        resp = await authed_client.post(
            "/api/activity/events",
            json={"events": []},
        )
        assert resp.status_code == 422

    async def test_reject_oversized_metadata(self, authed_client: httpx.AsyncClient):
        big_meta = {"data": "x" * 5000}
        resp = await authed_client.post(
            "/api/activity/events",
            json={"events": [make_event(metadata=big_meta)]},
        )
        assert resp.status_code == 422

    async def test_reject_too_long_app_name(self, authed_client: httpx.AsyncClient):
        resp = await authed_client.post(
            "/api/activity/events",
            json={"events": [make_event(app_name="x" * 256)]},
        )
        assert resp.status_code == 422

    async def test_reject_empty_app_name(self, authed_client: httpx.AsyncClient):
        resp = await authed_client.post(
            "/api/activity/events",
            json={"events": [make_event(app_name="")]},
        )
        assert resp.status_code == 422

    async def test_unauthenticated(self, client: httpx.AsyncClient):
        resp = await client.post(
            "/api/activity/events",
            json={"events": [make_event()]},
        )
        assert resp.status_code == 401


# ── GET /api/activity/events ───────────────────────────────────────


class TestListEvents:
    async def _seed_events(self, client: httpx.AsyncClient, count: int = 5, **overrides):
        events = [make_event(**overrides) for _ in range(count)]
        await client.post("/api/activity/events", json={"events": events})

    async def test_list_events(self, authed_client: httpx.AsyncClient):
        await self._seed_events(authed_client, count=3)
        now = datetime.now(timezone.utc)
        resp = await authed_client.get(
            "/api/activity/events",
            params={
                "start": (now - timedelta(hours=1)).isoformat(),
                "end": (now + timedelta(hours=1)).isoformat(),
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_count"] == 3
        assert len(body["events"]) == 3
        assert body["limit"] == 100
        assert body["offset"] == 0

    async def test_list_with_pagination(self, authed_client: httpx.AsyncClient):
        await self._seed_events(authed_client, count=5)
        now = datetime.now(timezone.utc)
        params = {
            "start": (now - timedelta(hours=1)).isoformat(),
            "end": (now + timedelta(hours=1)).isoformat(),
            "limit": 2,
            "offset": 0,
        }
        resp = await authed_client.get("/api/activity/events", params=params)
        body = resp.json()
        assert len(body["events"]) == 2
        assert body["total_count"] == 5

    async def test_filter_by_event_type(self, authed_client: httpx.AsyncClient):
        await self._seed_events(authed_client, count=3, event_type="active_window")
        await self._seed_events(authed_client, count=2, event_type="idle_start")
        now = datetime.now(timezone.utc)
        resp = await authed_client.get(
            "/api/activity/events",
            params={
                "start": (now - timedelta(hours=1)).isoformat(),
                "end": (now + timedelta(hours=1)).isoformat(),
                "event_type": "idle_start",
            },
        )
        assert resp.json()["total_count"] == 2

    async def test_filter_by_app_name(self, authed_client: httpx.AsyncClient):
        await self._seed_events(authed_client, count=2, app_name="Firefox")
        await self._seed_events(authed_client, count=3, app_name="VS Code")
        now = datetime.now(timezone.utc)
        resp = await authed_client.get(
            "/api/activity/events",
            params={
                "start": (now - timedelta(hours=1)).isoformat(),
                "end": (now + timedelta(hours=1)).isoformat(),
                "app_name": "Firefox",
            },
        )
        assert resp.json()["total_count"] == 2

    async def test_empty_range(self, authed_client: httpx.AsyncClient):
        now = datetime.now(timezone.utc)
        resp = await authed_client.get(
            "/api/activity/events",
            params={
                "start": (now - timedelta(hours=2)).isoformat(),
                "end": (now - timedelta(hours=1)).isoformat(),
            },
        )
        assert resp.status_code == 200
        assert resp.json()["total_count"] == 0
        assert resp.json()["events"] == []

    async def test_reject_end_before_start(self, authed_client: httpx.AsyncClient):
        now = datetime.now(timezone.utc)
        resp = await authed_client.get(
            "/api/activity/events",
            params={
                "start": now.isoformat(),
                "end": (now - timedelta(hours=1)).isoformat(),
            },
        )
        assert resp.status_code == 400

    async def test_reject_range_over_31_days(self, authed_client: httpx.AsyncClient):
        now = datetime.now(timezone.utc)
        resp = await authed_client.get(
            "/api/activity/events",
            params={
                "start": (now - timedelta(days=32)).isoformat(),
                "end": now.isoformat(),
            },
        )
        assert resp.status_code == 400

    async def test_events_ordered_by_timestamp(self, authed_client: httpx.AsyncClient):
        now = datetime.now(timezone.utc)
        events = [
            make_event(timestamp=(now - timedelta(minutes=i)).isoformat())
            for i in range(5)
        ]
        await authed_client.post("/api/activity/events", json={"events": events})

        resp = await authed_client.get(
            "/api/activity/events",
            params={
                "start": (now - timedelta(hours=1)).isoformat(),
                "end": (now + timedelta(hours=1)).isoformat(),
            },
        )
        timestamps = [e["timestamp"] for e in resp.json()["events"]]
        assert timestamps == sorted(timestamps)

    async def test_unauthenticated(self, client: httpx.AsyncClient):
        now = datetime.now(timezone.utc)
        resp = await client.get(
            "/api/activity/events",
            params={
                "start": (now - timedelta(hours=1)).isoformat(),
                "end": now.isoformat(),
            },
        )
        assert resp.status_code == 401


# ── GET /api/activity/status ───────────────────────────────────────


class TestDaemonStatus:
    async def test_status_no_events(self, authed_client: httpx.AsyncClient):
        resp = await authed_client.get("/api/activity/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["last_event_at"] is None
        assert body["events_today"] == 0

    async def test_status_with_events(self, authed_client: httpx.AsyncClient):
        events = [make_event() for _ in range(3)]
        await authed_client.post("/api/activity/events", json={"events": events})

        resp = await authed_client.get("/api/activity/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["last_event_at"] is not None
        assert body["events_today"] == 3

    async def test_unauthenticated(self, client: httpx.AsyncClient):
        resp = await client.get("/api/activity/status")
        assert resp.status_code == 401


# ── Cross-user isolation ──────────────────────────────────────────


class TestUserIsolation:
    async def test_users_cannot_see_each_others_events(
        self,
        authed_client: httpx.AsyncClient,
        client: httpx.AsyncClient,
        db_session,
    ):
        # User 1 inserts events
        await authed_client.post(
            "/api/activity/events",
            json={"events": [make_event() for _ in range(3)]},
        )

        # Create user 2
        from src.models.postgres.users import UserModel
        from src.core.auth import create_token_for_user

        user2 = UserModel(
            id=uuid.uuid4(),
            email="other@example.com",
            password_hash="fake",
            is_verified=True,
        )
        db_session.add(user2)
        await db_session.commit()
        await db_session.refresh(user2)
        token2 = create_token_for_user(user2)

        now = datetime.now(timezone.utc)
        resp = await client.get(
            "/api/activity/events",
            params={
                "start": (now - timedelta(hours=1)).isoformat(),
                "end": (now + timedelta(hours=1)).isoformat(),
            },
            headers={"Authorization": f"Bearer {token2}"},
        )
        assert resp.status_code == 200
        assert resp.json()["total_count"] == 0
