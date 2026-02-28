import uuid
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from src.models.postgres.users import UserModel


def make_event(timestamp: datetime, **overrides):
    defaults = {
        "client_event_id": str(uuid.uuid4()),
        "timestamp": timestamp.isoformat(),
        "event_type": "active_window",
        "app_name": "VS Code",
        "window_title": "main.py - timeoracle",
    }
    defaults.update(overrides)
    return defaults


class TestListEndpoint:
    async def _seed_events(self, client: httpx.AsyncClient, events: list[dict]):
        """POST events — sessions are created inline during ingestion."""
        resp = await client.post("/api/activity/events", json={"events": events})
        assert resp.status_code == 201

    async def test_list_sessions(self, authed_client: httpx.AsyncClient):
        base = datetime(2026, 2, 23, 14, 0, tzinfo=timezone.utc)
        events = [
            make_event(base, app_name="Firefox", window_title="GitHub"),
            make_event(base + timedelta(minutes=15), app_name="VSCode", window_title="main.py"),
            make_event(base + timedelta(minutes=45), app_name="Chrome", window_title="Docs"),
        ]
        await self._seed_events(authed_client, events)

        resp = await authed_client.get(
            "/api/activity/sessions",
            params={"date": "2026-02-23"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_count"] == 3
        assert len(body["sessions"]) == 3
        assert body["sessions"][0]["app_name"] == "Firefox"
        assert body["sessions"][1]["app_name"] == "VSCode"

    async def test_list_sessions_empty(self, authed_client: httpx.AsyncClient):
        resp = await authed_client.get(
            "/api/activity/sessions",
            params={"date": "2026-02-23"},
        )
        assert resp.status_code == 200
        assert resp.json()["total_count"] == 0
        assert resp.json()["sessions"] == []

    async def test_list_sessions_week_range(self, authed_client: httpx.AsyncClient):
        base = datetime(2026, 2, 23, 14, 0, tzinfo=timezone.utc)
        events = [
            make_event(base, app_name="Firefox", window_title="GitHub"),
            make_event(base + timedelta(minutes=15), app_name="VSCode", window_title="main.py"),
            make_event(base + timedelta(minutes=45), app_name="Chrome", window_title="Docs"),
        ]
        await self._seed_events(authed_client, events)

        resp = await authed_client.get(
            "/api/activity/sessions",
            params={"date": "2026-02-23", "range": "week"},
        )
        assert resp.status_code == 200
        assert resp.json()["total_count"] == 3

    async def test_list_unauthenticated(self, client: httpx.AsyncClient):
        resp = await client.get(
            "/api/activity/sessions",
            params={"date": "2026-02-23"},
        )
        assert resp.status_code == 401

    async def test_list_sessions_with_pagination(self, authed_client: httpx.AsyncClient):
        base = datetime(2026, 2, 23, 14, 0, tzinfo=timezone.utc)
        events = [
            make_event(base, app_name="Firefox", window_title="GitHub"),
            make_event(base + timedelta(minutes=15), app_name="VSCode", window_title="main.py"),
            make_event(base + timedelta(minutes=45), app_name="Chrome", window_title="Docs"),
        ]
        await self._seed_events(authed_client, events)

        resp = await authed_client.get(
            "/api/activity/sessions",
            params={"date": "2026-02-23", "limit": 2, "offset": 0},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["sessions"]) == 2
        assert body["total_count"] == 3

    async def test_session_fields(self, authed_client: httpx.AsyncClient):
        """Verify all expected fields are present in session response."""
        base = datetime(2026, 2, 23, 14, 0, tzinfo=timezone.utc)
        events = [
            make_event(base, app_name="Firefox", window_title="Home", url="https://example.com"),
            make_event(base + timedelta(minutes=10), app_name="Chrome", window_title="Search"),
        ]
        await self._seed_events(authed_client, events)

        resp = await authed_client.get(
            "/api/activity/sessions",
            params={"date": "2026-02-23"},
        )
        session = resp.json()["sessions"][0]
        assert "id" in session
        assert "user_id" in session
        assert "app_name" in session
        assert "window_title" in session
        assert "start_time" in session
        assert "end_time" in session
        assert "date" in session
        assert session["url"] == "https://example.com"

    async def test_ingest_creates_sessions_inline(self, authed_client: httpx.AsyncClient):
        """Sessions are created automatically during event ingestion."""
        base = datetime(2026, 2, 23, 14, 0, tzinfo=timezone.utc)
        events = [
            make_event(base, app_name="Firefox", window_title="Home"),
            make_event(base + timedelta(minutes=10), app_name="VSCode", window_title="code.py"),
        ]
        resp = await authed_client.post("/api/activity/events", json={"events": events})
        assert resp.status_code == 201
        assert resp.json()["inserted_count"] == 2

        # Sessions should already exist — no separate generate call needed
        resp = await authed_client.get(
            "/api/activity/sessions",
            params={"date": "2026-02-23"},
        )
        assert resp.status_code == 200
        assert resp.json()["total_count"] == 2

    async def test_ingest_twice_sessions_accumulate(self, authed_client: httpx.AsyncClient):
        """Two sequential ingestions produce correct accumulated sessions."""
        base = datetime(2026, 2, 23, 14, 0, tzinfo=timezone.utc)

        # First ingestion
        batch1 = [
            make_event(base, app_name="Firefox", window_title="Home"),
            make_event(base + timedelta(minutes=15), app_name="VSCode", window_title="main.py"),
        ]
        await authed_client.post("/api/activity/events", json={"events": batch1})

        # Second ingestion
        batch2 = [
            make_event(base + timedelta(minutes=30), app_name="VSCode", window_title="utils.py"),
            make_event(base + timedelta(minutes=45), app_name="Chrome", window_title="Docs"),
        ]
        await authed_client.post("/api/activity/events", json={"events": batch2})

        resp = await authed_client.get(
            "/api/activity/sessions",
            params={"date": "2026-02-23"},
        )
        body = resp.json()
        assert body["total_count"] == 3
        apps = [s["app_name"] for s in body["sessions"]]
        assert apps == ["Firefox", "VSCode", "Chrome"]

    async def test_session_icon_field_null(self, authed_client: httpx.AsyncClient):
        """icon field is present and null (no icon logic yet)."""
        base = datetime(2026, 2, 23, 14, 0, tzinfo=timezone.utc)
        events = [
            make_event(base, app_name="Firefox", window_title="Home"),
            make_event(base + timedelta(minutes=10), app_name="Chrome", window_title="Search"),
        ]
        await self._seed_events(authed_client, events)

        resp = await authed_client.get(
            "/api/activity/sessions",
            params={"date": "2026-02-23"},
        )
        for session in resp.json()["sessions"]:
            assert "icon" in session
            assert session["icon"] is None

    async def test_session_window_titles_in_response(self, authed_client: httpx.AsyncClient):
        """window_titles contains all unique titles; window_title is first seen."""
        base = datetime(2026, 2, 23, 14, 0, tzinfo=timezone.utc)
        events = [
            make_event(base, app_name="Firefox", window_title="Tab A"),
            make_event(base + timedelta(minutes=5), app_name="Firefox", window_title="Tab B"),
            make_event(base + timedelta(minutes=10), app_name="Firefox", window_title="Tab A"),
            make_event(base + timedelta(minutes=15), app_name="Chrome", window_title="End"),
        ]
        await self._seed_events(authed_client, events)

        resp = await authed_client.get(
            "/api/activity/sessions",
            params={"date": "2026-02-23"},
        )
        firefox = resp.json()["sessions"][0]
        assert firefox["app_name"] == "Firefox"
        assert firefox["window_title"] == "Tab A"
        assert set(firefox["window_titles"]) == {"Tab A", "Tab B"}

    async def test_generate_endpoint_removed(self, authed_client: httpx.AsyncClient):
        """POST /generate endpoint no longer exists."""
        resp = await authed_client.post(
            "/api/activity/sessions/generate",
            json={"date": "2026-02-23"},
        )
        assert resp.status_code in (404, 405)
