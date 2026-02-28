import uuid
from datetime import date, datetime, timezone

import httpx
import pytest

from src.core.auth import create_token_for_user
from src.models.postgres.users import UserModel


def make_entry(hour_start=14, hour_end=15, **overrides):
    now = datetime.now(timezone.utc).replace(microsecond=0)
    start = now.replace(hour=hour_start, minute=0, second=0)
    end = now.replace(hour=hour_end, minute=0, second=0)
    defaults = {
        "date": start.date().isoformat(),
        "start_time": start.isoformat(),
        "end_time": end.isoformat(),
        "label": "Deep work",
    }
    defaults.update(overrides)
    return defaults


class TestBulkCreate:
    async def test_create_multiple(self, authed_client: httpx.AsyncClient):
        entries = [
            make_entry(hour_start=10, hour_end=11, label="Morning coding"),
            make_entry(hour_start=11, hour_end=12, label="Code review"),
            make_entry(hour_start=13, hour_end=14, label="Research"),
        ]
        resp = await authed_client.post("/api/timeline/bulk", json={"entries": entries})
        assert resp.status_code == 200
        body = resp.json()
        assert body["created"] == 3
        assert body["updated"] == 0
        assert body["skipped"] == 0
        assert body["errors"] == []

    async def test_source_is_ai_generated(self, authed_client: httpx.AsyncClient):
        resp = await authed_client.post(
            "/api/timeline/bulk", json={"entries": [make_entry()]}
        )
        assert resp.status_code == 200

        today = date.today().isoformat()
        list_resp = await authed_client.get("/api/timeline", params={"date": today})
        entries = list_resp.json()["entries"]
        assert len(entries) == 1
        assert entries[0]["source"] == "ai_generated"

    async def test_source_summary_and_confidence(self, authed_client: httpx.AsyncClient):
        entry = make_entry(
            source_summary="User was coding in VS Code on timeoracle project",
            confidence=0.85,
        )
        resp = await authed_client.post(
            "/api/timeline/bulk", json={"entries": [entry]}
        )
        assert resp.status_code == 200

        today = date.today().isoformat()
        list_resp = await authed_client.get("/api/timeline", params={"date": today})
        created = list_resp.json()["entries"][0]
        assert created["source_summary"] == "User was coding in VS Code on timeoracle project"
        assert created["confidence"] == pytest.approx(0.85)

    async def test_max_100_items(self, authed_client: httpx.AsyncClient):
        entries = [make_entry(label=f"Entry {i}") for i in range(101)]
        resp = await authed_client.post("/api/timeline/bulk", json={"entries": entries})
        assert resp.status_code == 422

    async def test_empty_array(self, authed_client: httpx.AsyncClient):
        resp = await authed_client.post("/api/timeline/bulk", json={"entries": []})
        assert resp.status_code == 422

    async def test_validation_bad_color(self, authed_client: httpx.AsyncClient):
        resp = await authed_client.post(
            "/api/timeline/bulk", json={"entries": [make_entry(color="red")]}
        )
        assert resp.status_code == 422

    async def test_validation_end_before_start(self, authed_client: httpx.AsyncClient):
        resp = await authed_client.post(
            "/api/timeline/bulk",
            json={"entries": [make_entry(hour_start=15, hour_end=14)]},
        )
        assert resp.status_code == 422

    async def test_unauthenticated(self, client: httpx.AsyncClient):
        resp = await client.post(
            "/api/timeline/bulk", json={"entries": [make_entry()]}
        )
        assert resp.status_code == 401


class TestBulkUpdate:
    async def _create_entry(self, client: httpx.AsyncClient, **overrides) -> dict:
        entry = make_entry(**overrides)
        resp = await client.post("/api/timeline", json=entry)
        assert resp.status_code == 201
        return resp.json()

    async def test_update_existing(self, authed_client: httpx.AsyncClient):
        existing = await self._create_entry(authed_client)
        bulk_item = make_entry(
            id=existing["id"],
            label="Updated by AI",
            category="Work",
            source_summary="Reclassified based on new data",
            confidence=0.92,
        )
        resp = await authed_client.post(
            "/api/timeline/bulk", json={"entries": [bulk_item]}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["updated"] == 1
        assert body["created"] == 0

        today = date.today().isoformat()
        list_resp = await authed_client.get("/api/timeline", params={"date": today})
        entry = list_resp.json()["entries"][0]
        assert entry["label"] == "Updated by AI"
        assert entry["source"] == "ai_generated"
        assert entry["source_summary"] == "Reclassified based on new data"
        assert entry["confidence"] == pytest.approx(0.92)

    async def test_skip_edited_by_user(self, authed_client: httpx.AsyncClient):
        existing = await self._create_entry(authed_client)
        await authed_client.patch(
            f"/api/timeline/{existing['id']}", json={"label": "User edited"}
        )

        bulk_item = make_entry(id=existing["id"], label="AI override attempt")
        resp = await authed_client.post(
            "/api/timeline/bulk", json={"entries": [bulk_item]}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["skipped"] == 1
        assert body["updated"] == 0

        today = date.today().isoformat()
        list_resp = await authed_client.get("/api/timeline", params={"date": today})
        entry = list_resp.json()["entries"][0]
        assert entry["label"] == "User edited"

    async def test_not_found_id(self, authed_client: httpx.AsyncClient):
        fake_id = str(uuid.uuid4())
        bulk_item = make_entry(id=fake_id, label="Ghost entry")
        resp = await authed_client.post(
            "/api/timeline/bulk", json={"entries": [bulk_item]}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["errors"] == [{"index": 0, "message": "Entry not found"}]

    async def test_other_users_entry(
        self, authed_client: httpx.AsyncClient, client: httpx.AsyncClient, db_session,
    ):
        existing = await self._create_entry(authed_client)

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

        bulk_item = make_entry(id=existing["id"], label="Steal this entry")
        resp = await client.post(
            "/api/timeline/bulk",
            json={"entries": [bulk_item]},
            headers={"Authorization": f"Bearer {token2}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["errors"] == [{"index": 0, "message": "Entry not found"}]


class TestBulkMixed:
    async def test_create_and_update_together(self, authed_client: httpx.AsyncClient):
        existing_resp = await authed_client.post("/api/timeline", json=make_entry())
        assert existing_resp.status_code == 201
        existing_id = existing_resp.json()["id"]

        entries = [
            make_entry(hour_start=10, hour_end=11, label="New entry"),
            make_entry(id=existing_id, label="Updated entry"),
        ]
        resp = await authed_client.post("/api/timeline/bulk", json={"entries": entries})
        assert resp.status_code == 200
        body = resp.json()
        assert body["created"] == 1
        assert body["updated"] == 1

    async def test_partial_success(self, authed_client: httpx.AsyncClient):
        existing_resp = await authed_client.post("/api/timeline", json=make_entry())
        assert existing_resp.status_code == 201
        existing_id = existing_resp.json()["id"]

        await authed_client.patch(
            f"/api/timeline/{existing_id}", json={"label": "User touched"}
        )

        entries = [
            make_entry(hour_start=10, hour_end=11, label="Brand new"),
            make_entry(id=existing_id, label="Try to update edited"),
            make_entry(id=str(uuid.uuid4()), label="Nonexistent"),
        ]
        resp = await authed_client.post("/api/timeline/bulk", json={"entries": entries})
        assert resp.status_code == 200
        body = resp.json()
        assert body["created"] == 1
        assert body["skipped"] == 1
        assert body["errors"] == [{"index": 2, "message": "Entry not found"}]

    async def test_confidence_validation(self, authed_client: httpx.AsyncClient):
        resp = await authed_client.post(
            "/api/timeline/bulk",
            json={"entries": [make_entry(confidence=1.5)]},
        )
        assert resp.status_code == 422

        resp = await authed_client.post(
            "/api/timeline/bulk",
            json={"entries": [make_entry(confidence=-0.1)]},
        )
        assert resp.status_code == 422
