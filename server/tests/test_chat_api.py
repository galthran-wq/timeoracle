import json
import uuid
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.core.auth import create_token_for_user
from src.models.postgres.users import UserModel


class TestGenerateEndpoint:
    async def test_unauthenticated(self, client: httpx.AsyncClient):
        resp = await client.post(
            "/api/agent/generate",
            json={"date": "2026-03-01"},
        )
        assert resp.status_code == 401

    async def test_missing_date(self, authed_client: httpx.AsyncClient):
        resp = await authed_client.post("/api/agent/generate", json={})
        assert resp.status_code == 422

    async def test_invalid_date(self, authed_client: httpx.AsyncClient):
        resp = await authed_client.post(
            "/api/agent/generate", json={"date": "not-a-date"}
        )
        assert resp.status_code == 422

    @patch("src.api.chat.generate_timeline")
    async def test_success(self, mock_gen, authed_client: httpx.AsyncClient):
        mock_gen.return_value = {
            "message": "Created 3 timeline entries for 2026-03-01",
            "chat_id": str(uuid.uuid4()),
        }

        resp = await authed_client.post(
            "/api/agent/generate", json={"date": "2026-03-01"}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "message" in body
        assert "chat_id" in body
        mock_gen.assert_called_once()

    @patch("src.api.chat.generate_timeline")
    async def test_passes_user_id_and_date(self, mock_gen, authed_client: httpx.AsyncClient, test_user):
        mock_gen.return_value = {
            "message": "Done",
            "chat_id": str(uuid.uuid4()),
        }

        await authed_client.post(
            "/api/agent/generate", json={"date": "2026-03-01"}
        )

        call_kwargs = mock_gen.call_args
        assert call_kwargs[1]["user_id"] == test_user.id
        assert call_kwargs[1]["target_date"] == date(2026, 3, 1)

    @patch("src.api.chat.generate_timeline")
    async def test_internal_error(self, mock_gen, authed_client: httpx.AsyncClient):
        mock_gen.side_effect = RuntimeError("LLM API down")

        resp = await authed_client.post(
            "/api/agent/generate", json={"date": "2026-03-01"}
        )
        assert resp.status_code == 500
        assert "Timeline generation failed" in resp.json()["detail"]


class TestChatEndpoint:
    async def test_unauthenticated(self, client: httpx.AsyncClient):
        resp = await client.post(
            "/api/agent/chat",
            json={"message": "what did I do today?"},
        )
        assert resp.status_code == 401

    async def test_missing_message(self, authed_client: httpx.AsyncClient):
        resp = await authed_client.post("/api/agent/chat", json={})
        assert resp.status_code == 422

    async def test_empty_message(self, authed_client: httpx.AsyncClient):
        resp = await authed_client.post(
            "/api/agent/chat", json={"message": ""}
        )
        assert resp.status_code == 422

    @patch("src.api.chat.agent")
    async def test_returns_sse_stream(self, mock_agent, authed_client: httpx.AsyncClient):
        """Verify the endpoint returns SSE-formatted events."""
        # Create a mock streaming result
        mock_result = AsyncMock()
        mock_result.stream_text = MagicMock()
        mock_result.all_messages_json = MagicMock(return_value=b"[]")

        mock_usage = MagicMock()
        mock_usage.request_tokens = 10
        mock_usage.response_tokens = 20
        mock_result.usage = MagicMock(return_value=mock_usage)

        # stream_text returns an async iterator of text chunks
        async def fake_stream(delta=True):
            yield "Hello "
            yield "world!"

        mock_result.stream_text = fake_stream

        # run_stream is an async context manager
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_result)
        mock_cm.__aexit__ = AsyncMock(return_value=False)
        mock_agent.run_stream = MagicMock(return_value=mock_cm)

        resp = await authed_client.post(
            "/api/agent/chat",
            json={"message": "what did I do today?"},
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")

        # Parse SSE events from the response body
        body = resp.text
        events = _parse_sse(body)

        # Should have text events and a done event
        text_events = [e for e in events if e["event"] == "text"]
        done_events = [e for e in events if e["event"] == "done"]

        assert len(text_events) >= 1
        assert len(done_events) == 1

        # Verify text content
        full_text = "".join(json.loads(e["data"])["text"] for e in text_events)
        assert "Hello" in full_text
        assert "world" in full_text

    @patch("src.api.chat.agent")
    async def test_error_event_on_failure(self, mock_agent, authed_client: httpx.AsyncClient):
        """Verify errors are sent as SSE error events."""
        mock_agent.run_stream = MagicMock(side_effect=RuntimeError("LLM exploded"))

        resp = await authed_client.post(
            "/api/agent/chat",
            json={"message": "hello"},
        )
        assert resp.status_code == 200  # SSE always returns 200, errors are in-stream

        events = _parse_sse(resp.text)
        error_events = [e for e in events if e["event"] == "error"]
        assert len(error_events) == 1


def _parse_sse(body: str) -> list[dict]:
    """Parse SSE text into a list of {event, data} dicts."""
    events = []
    current_event = None
    current_data = None

    for line in body.split("\n"):
        if line.startswith("event: "):
            current_event = line[7:]
        elif line.startswith("data: "):
            current_data = line[6:]
        elif line == "" and current_event is not None:
            events.append({"event": current_event, "data": current_data})
            current_event = None
            current_data = None

    return events
