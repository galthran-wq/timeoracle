import httpx


class TestSessionConfigEndpoints:
    async def test_get_default_config(self, authed_client: httpx.AsyncClient):
        resp = await authed_client.get("/api/users/me/session-config")
        assert resp.status_code == 200
        body = resp.json()
        assert body["merge_gap_seconds"] == 300
        assert body["min_session_seconds"] == 5
        assert body["noise_threshold_seconds"] == 120

    async def test_patch_partial_config(self, authed_client: httpx.AsyncClient):
        resp = await authed_client.patch(
            "/api/users/me/session-config",
            json={"merge_gap_seconds": 600},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["merge_gap_seconds"] == 600
        assert body["min_session_seconds"] == 5
        assert body["noise_threshold_seconds"] == 120

    async def test_patch_persists(self, authed_client: httpx.AsyncClient):
        await authed_client.patch(
            "/api/users/me/session-config",
            json={"noise_threshold_seconds": 60},
        )
        resp = await authed_client.get("/api/users/me/session-config")
        assert resp.status_code == 200
        assert resp.json()["noise_threshold_seconds"] == 60

    async def test_patch_multiple_fields(self, authed_client: httpx.AsyncClient):
        resp = await authed_client.patch(
            "/api/users/me/session-config",
            json={"merge_gap_seconds": 900, "min_session_seconds": 10},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["merge_gap_seconds"] == 900
        assert body["min_session_seconds"] == 10
        assert body["noise_threshold_seconds"] == 120

    async def test_patch_empty_body_returns_defaults(self, authed_client: httpx.AsyncClient):
        resp = await authed_client.patch(
            "/api/users/me/session-config",
            json={},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["merge_gap_seconds"] == 300

    async def test_patch_validation_rejects_invalid(self, authed_client: httpx.AsyncClient):
        resp = await authed_client.patch(
            "/api/users/me/session-config",
            json={"merge_gap_seconds": 0},
        )
        assert resp.status_code == 422

    async def test_unauthenticated_get(self, client: httpx.AsyncClient):
        resp = await client.get("/api/users/me/session-config")
        assert resp.status_code == 401

    async def test_unauthenticated_patch(self, client: httpx.AsyncClient):
        resp = await client.patch(
            "/api/users/me/session-config",
            json={"merge_gap_seconds": 600},
        )
        assert resp.status_code == 401
