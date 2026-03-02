import asyncio
import json
import logging
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.agent import agent, _build_deps, generate_timeline
from src.core.auth import get_current_user
from src.core.config import settings
from src.core.database import get_postgres_session
from src.models.postgres.users import UserModel
from src.repositories.chats import ChatRepository
from src.schemas.chat import (
    ChatRequest, ChatDetail, ChatListResponse, ChatMessageItem,
    ChatSummary, GenerateRequest, GenerateResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agent", tags=["agent"])


def _sse_event(event_type: str, data: dict) -> str:
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


def _parse_messages(raw_messages: list | None) -> list[ChatMessageItem]:
    if not raw_messages:
        return []
    items = []
    for msg in raw_messages:
        kind = msg.get("kind")
        for part in msg.get("parts", []):
            pk = part.get("part_kind")
            content = part.get("content")
            if not content or not isinstance(content, str):
                continue
            if kind == "request" and pk == "user-prompt":
                items.append(ChatMessageItem(role="user", content=content))
            elif kind == "response" and pk == "text":
                items.append(ChatMessageItem(role="assistant", content=content))
    return items


def _preview_from_messages(raw_messages: list | None) -> str:
    if not raw_messages:
        return ""
    for msg in raw_messages:
        if msg.get("kind") != "request":
            continue
        for part in msg.get("parts", []):
            if part.get("part_kind") == "user-prompt":
                text = part.get("content", "")
                if isinstance(text, str) and text:
                    return text[:100]
    return ""


@router.get("/chats", response_model=ChatListResponse)
async def list_chats(
    limit: int = 20,
    offset: int = 0,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_postgres_session),
):
    chat_repo = ChatRepository(session)
    chats, total = await chat_repo.list_for_user(current_user.id, limit=limit, offset=offset)
    summaries = [
        ChatSummary(
            id=c.id,
            trigger=c.trigger,
            created_at=c.created_at,
            total_input_tokens=c.total_input_tokens,
            total_output_tokens=c.total_output_tokens,
            preview=_preview_from_messages(c.messages),
        )
        for c in chats
    ]
    return ChatListResponse(chats=summaries, total_count=total)


@router.get("/chats/{chat_id}", response_model=ChatDetail)
async def get_chat(
    chat_id: str,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_postgres_session),
):
    from uuid import UUID as PyUUID
    try:
        cid = PyUUID(chat_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid chat ID")

    chat_repo = ChatRepository(session)
    chat = await chat_repo.get_by_id(cid)
    if not chat or chat.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Chat not found")

    return ChatDetail(
        id=chat.id,
        trigger=chat.trigger,
        created_at=chat.created_at,
        total_input_tokens=chat.total_input_tokens,
        total_output_tokens=chat.total_output_tokens,
        preview=_preview_from_messages(chat.messages),
        messages=_parse_messages(chat.messages),
    )


@router.post("/generate", response_model=GenerateResponse)
async def generate_entries(
    body: GenerateRequest,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_postgres_session),
):
    try:
        result = await generate_timeline(
            user_id=current_user.id,
            target_date=body.date,
            session=session,
            user_session_config=current_user.session_config,
        )
        return GenerateResponse(**result)
    except Exception:
        logger.exception("Failed to generate timeline for user %s", current_user.id)
        raise HTTPException(status_code=500, detail="Timeline generation failed")


@router.post("/chat")
async def chat_stream(
    body: ChatRequest,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_postgres_session),
):
    chat_repo = ChatRepository(session)

    user_cfg = current_user.session_config or {}
    effective_model = user_cfg.get("llm_model") or settings.chat_llm_model

    chat = None
    if body.chat_id:
        from uuid import UUID as PyUUID
        try:
            chat = await chat_repo.get_by_id(PyUUID(body.chat_id))
            if chat and chat.user_id != current_user.id:
                chat = None
        except (ValueError, Exception):
            pass

    if not chat:
        chat = await chat_repo.create(
            user_id=current_user.id,
            trigger="chat",
            llm_model=effective_model,
        )

    message_history = None
    if chat.messages:
        try:
            from pydantic_ai.messages import ModelMessagesTypeAdapter
            raw = chat.messages
            if isinstance(raw, str):
                raw = json.loads(raw)
            if raw:
                message_history = ModelMessagesTypeAdapter.validate_python(raw)
        except Exception:
            logger.warning("Failed to parse chat history for chat %s, starting fresh", chat.id)
            message_history = None

    user_msg = {
        "kind": "request",
        "parts": [{
            "part_kind": "user-prompt",
            "content": body.message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }],
    }
    pre_save = (chat.messages or []) + [user_msg]
    await chat_repo.update_messages(
        chat.id, json.dumps(pre_save), input_tokens=0, output_tokens=0,
    )

    event_queue: asyncio.Queue = asyncio.Queue()

    deps = _build_deps(
        user_id=current_user.id,
        session=session,
        chat_id=chat.id,
        user_session_config=current_user.session_config,
        event_queue=event_queue,
    )

    async def run_agent():
        try:
            async with agent.run_stream(
                body.message,
                deps=deps,
                model=effective_model,
                message_history=message_history,
            ) as result:
                async for text in result.stream_text(delta=True):
                    await event_queue.put(("text", {"text": text}))

                try:
                    messages_json = result.all_messages_json().decode()
                except Exception:
                    messages_json = "[]"

                await chat_repo.update_messages(
                    chat.id,
                    messages_json,
                    input_tokens=result.usage().request_tokens or 0,
                    output_tokens=result.usage().response_tokens or 0,
                )

            await event_queue.put(("done", {"chat_id": str(chat.id)}))
        except Exception as e:
            logger.exception("Agent error in chat %s", chat.id)
            await event_queue.put(("error", {"error": str(e)}))

    async def event_generator():
        yield _sse_event("start", {"chat_id": str(chat.id)})
        task = asyncio.create_task(run_agent())
        try:
            while True:
                event_type, data = await event_queue.get()
                yield _sse_event(event_type, data)
                if event_type in ("done", "error"):
                    break
        finally:
            if not task.done():
                task.cancel()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
