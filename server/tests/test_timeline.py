import uuid
from datetime import date, datetime, timedelta, timezone

import httpx
import pytest

from src.core.auth import create_token_for_user
from src.models.postgres.users import UserModel


def make_entry(**overrides):
    now = datetime.now(timezone.utc).replace(microsecond=0)
    start = now.replace(hour=14, minute=0, second=0)
    end = now.replace(hour=15, minute=0, second=0)
    defaults = {
        "date": start.date().isoformat(),
        "start_time": start.isoformat(),
        "end_time": end.isoformat(),
        "label": "Deep work",
    }
    defaults.update(overrides)
    return defaults



class TestCreateEntry:
    async def test_create_success(self, authed_client: httpx.AsyncClient):
        resp = await authed_client.post("/api/timeline", json=make_entry())
        assert resp.status_code == 201
        body = resp.json()
        assert body["label"] == "Deep work"
        assert body["source"] == "manual"
        assert body["edited_by_user"] is False
        assert body["id"] is not None

    async def test_create_with_all_fields(self, authed_client: httpx.AsyncClient):
        resp = await authed_client.post(
            "/api/timeline",
            json=make_entry(
                description="Focused coding session",
                category="Work",
                color="#3B82F6",
            ),
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["description"] == "Focused coding session"
        assert body["category"] == "Work"
        assert body["color"] == "#3B82F6"

    async def test_reject_end_before_start(self, authed_client: httpx.AsyncClient):
        now = datetime.now(timezone.utc).replace(microsecond=0)
        start = now.replace(hour=15, minute=0, second=0)
        end = now.replace(hour=14, minute=0, second=0)
        resp = await authed_client.post(
            "/api/timeline",
            json=make_entry(start_time=start.isoformat(), end_time=end.isoformat()),
        )
        assert resp.status_code == 422

    async def test_reject_empty_label(self, authed_client: httpx.AsyncClient):
        resp = await authed_client.post("/api/timeline", json=make_entry(label=""))
        assert resp.status_code == 422

    async def test_reject_naive_timestamps(self, authed_client: httpx.AsyncClient):
        now = datetime.utcnow().replace(microsecond=0)
        start = now.replace(hour=14, minute=0, second=0)
        end = now.replace(hour=15, minute=0, second=0)
        resp = await authed_client.post(
            "/api/timeline",
            json=make_entry(
                date=start.date().isoformat(),
                start_time=start.strftime("%Y-%m-%dT%H:%M:%S"),
                end_time=end.strftime("%Y-%m-%dT%H:%M:%S"),
            ),
        )
        assert resp.status_code == 422

    async def test_date_mismatch_auto_corrected(self, authed_client: httpx.AsyncClient):
        now = datetime.now(timezone.utc).replace(microsecond=0)
        start = now.replace(hour=14, minute=0, second=0)
        end = now.replace(hour=15, minute=0, second=0)
        wrong_date = (start.date() + timedelta(days=1)).isoformat()
        resp = await authed_client.post(
            "/api/timeline",
            json=make_entry(
                date=wrong_date,
                start_time=start.isoformat(),
                end_time=end.isoformat(),
            ),
        )
        assert resp.status_code == 201
        assert resp.json()["date"] == start.date().isoformat()

    async def test_reject_bad_color(self, authed_client: httpx.AsyncClient):
        resp = await authed_client.post(
            "/api/timeline", json=make_entry(color="red")
        )
        assert resp.status_code == 422

    async def test_unauthenticated(self, client: httpx.AsyncClient):
        resp = await client.post("/api/timeline", json=make_entry())
        assert resp.status_code == 401



class TestListEntries:
    async def _seed(self, client: httpx.AsyncClient, count: int = 1, **overrides):
        entries = []
        for i in range(count):
            now = datetime.now(timezone.utc).replace(microsecond=0)
            start = now.replace(hour=10 + i, minute=0, second=0)
            end = now.replace(hour=11 + i, minute=0, second=0)
            entry = make_entry(
                start_time=start.isoformat(),
                end_time=end.isoformat(),
                date=start.date().isoformat(),
                **overrides,
            )
            resp = await client.post("/api/timeline", json=entry)
            assert resp.status_code == 201
            entries.append(resp.json())
        return entries

    async def test_day_query(self, authed_client: httpx.AsyncClient):
        await self._seed(authed_client, count=3)
        today = date.today().isoformat()
        resp = await authed_client.get("/api/timeline", params={"date": today})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_count"] == 3
        assert len(body["entries"]) == 3

    async def test_week_query(self, authed_client: httpx.AsyncClient):
        await self._seed(authed_client, count=2)
        today = date.today().isoformat()
        resp = await authed_client.get(
            "/api/timeline", params={"date": today, "range": "week"}
        )
        assert resp.status_code == 200
        assert resp.json()["total_count"] == 2

    async def test_empty_result(self, authed_client: httpx.AsyncClient):
        far_date = (date.today() - timedelta(days=365)).isoformat()
        resp = await authed_client.get("/api/timeline", params={"date": far_date})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_count"] == 0
        assert body["entries"] == []

    async def test_pagination(self, authed_client: httpx.AsyncClient):
        await self._seed(authed_client, count=5)
        today = date.today().isoformat()
        resp = await authed_client.get(
            "/api/timeline", params={"date": today, "limit": 2, "offset": 0}
        )
        body = resp.json()
        assert len(body["entries"]) == 2
        assert body["total_count"] == 5

    async def test_category_filter(self, authed_client: httpx.AsyncClient):
        await self._seed(authed_client, count=3, category="Work")
        await self._seed(authed_client, count=2, category="Exercise")
        today = date.today().isoformat()
        resp = await authed_client.get(
            "/api/timeline", params={"date": today, "category": "Exercise"}
        )
        assert resp.json()["total_count"] == 2

    async def test_missing_date_param(self, authed_client: httpx.AsyncClient):
        resp = await authed_client.get("/api/timeline")
        assert resp.status_code == 422

    async def test_unauthenticated(self, client: httpx.AsyncClient):
        resp = await client.get(
            "/api/timeline", params={"date": date.today().isoformat()}
        )
        assert resp.status_code == 401



class TestUpdateEntry:
    async def _create_entry(self, client: httpx.AsyncClient, **overrides) -> dict:
        resp = await client.post("/api/timeline", json=make_entry(**overrides))
        assert resp.status_code == 201
        return resp.json()

    async def test_update_label(self, authed_client: httpx.AsyncClient):
        entry = await self._create_entry(authed_client)
        resp = await authed_client.patch(
            f"/api/timeline/{entry['id']}", json={"label": "Updated label"}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["label"] == "Updated label"
        assert body["edited_by_user"] is True

    async def test_update_category(self, authed_client: httpx.AsyncClient):
        entry = await self._create_entry(authed_client)
        resp = await authed_client.patch(
            f"/api/timeline/{entry['id']}", json={"category": "Exercise"}
        )
        assert resp.status_code == 200
        assert resp.json()["category"] == "Exercise"

    async def test_update_times(self, authed_client: httpx.AsyncClient):
        entry = await self._create_entry(authed_client)
        now = datetime.now(timezone.utc).replace(microsecond=0)
        new_start = now.replace(hour=16, minute=0, second=0)
        new_end = now.replace(hour=17, minute=30, second=0)
        resp = await authed_client.patch(
            f"/api/timeline/{entry['id']}",
            json={
                "start_time": new_start.isoformat(),
                "end_time": new_end.isoformat(),
            },
        )
        assert resp.status_code == 200

    async def test_partial_update_preserves_other_fields(self, authed_client: httpx.AsyncClient):
        entry = await self._create_entry(authed_client, category="Work")
        resp = await authed_client.patch(
            f"/api/timeline/{entry['id']}", json={"label": "New label"}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["label"] == "New label"
        assert body["category"] == "Work"

    async def test_reject_end_before_start(self, authed_client: httpx.AsyncClient):
        entry = await self._create_entry(authed_client)
        now = datetime.now(timezone.utc).replace(microsecond=0)
        early = now.replace(hour=10, minute=0, second=0)
        resp = await authed_client.patch(
            f"/api/timeline/{entry['id']}",
            json={"end_time": early.isoformat()},
        )
        assert resp.status_code == 400

    async def test_not_found(self, authed_client: httpx.AsyncClient):
        fake_id = str(uuid.uuid4())
        resp = await authed_client.patch(
            f"/api/timeline/{fake_id}", json={"label": "x"}
        )
        assert resp.status_code == 404

    async def test_unauthenticated(self, client: httpx.AsyncClient):
        fake_id = str(uuid.uuid4())
        resp = await client.patch(
            f"/api/timeline/{fake_id}", json={"label": "x"}
        )
        assert resp.status_code == 401



class TestDeleteEntry:
    async def test_delete_success(self, authed_client: httpx.AsyncClient):
        resp = await authed_client.post("/api/timeline", json=make_entry())
        entry_id = resp.json()["id"]

        resp = await authed_client.delete(f"/api/timeline/{entry_id}")
        assert resp.status_code == 204

        resp = await authed_client.patch(
            f"/api/timeline/{entry_id}", json={"label": "x"}
        )
        assert resp.status_code == 404

    async def test_not_found(self, authed_client: httpx.AsyncClient):
        fake_id = str(uuid.uuid4())
        resp = await authed_client.delete(f"/api/timeline/{fake_id}")
        assert resp.status_code == 404

    async def test_unauthenticated(self, client: httpx.AsyncClient):
        fake_id = str(uuid.uuid4())
        resp = await client.delete(f"/api/timeline/{fake_id}")
        assert resp.status_code == 401



class TestUserIsolation:
    async def test_cannot_see_other_users_entries(
        self, authed_client: httpx.AsyncClient, client: httpx.AsyncClient, db_session,
    ):
        resp = await authed_client.post("/api/timeline", json=make_entry())
        assert resp.status_code == 201

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
        headers2 = {"Authorization": f"Bearer {token2}"}

        today = date.today().isoformat()
        resp = await client.get(
            "/api/timeline", params={"date": today}, headers=headers2
        )
        assert resp.status_code == 200
        assert resp.json()["total_count"] == 0

    async def test_cannot_update_other_users_entry(
        self, authed_client: httpx.AsyncClient, client: httpx.AsyncClient, db_session,
    ):
        resp = await authed_client.post("/api/timeline", json=make_entry())
        entry_id = resp.json()["id"]

        user2 = UserModel(
            id=uuid.uuid4(),
            email="other2@example.com",
            password_hash="fake",
            is_verified=True,
        )
        db_session.add(user2)
        await db_session.commit()
        await db_session.refresh(user2)
        token2 = create_token_for_user(user2)
        headers2 = {"Authorization": f"Bearer {token2}"}

        resp = await client.patch(
            f"/api/timeline/{entry_id}",
            json={"label": "hacked"},
            headers=headers2,
        )
        assert resp.status_code == 404

    async def test_cannot_delete_other_users_entry(
        self, authed_client: httpx.AsyncClient, client: httpx.AsyncClient, db_session,
    ):
        resp = await authed_client.post("/api/timeline", json=make_entry())
        entry_id = resp.json()["id"]

        user2 = UserModel(
            id=uuid.uuid4(),
            email="other3@example.com",
            password_hash="fake",
            is_verified=True,
        )
        db_session.add(user2)
        await db_session.commit()
        await db_session.refresh(user2)
        token2 = create_token_for_user(user2)
        headers2 = {"Authorization": f"Bearer {token2}"}

        resp = await client.delete(
            f"/api/timeline/{entry_id}", headers=headers2
        )
        assert resp.status_code == 404
