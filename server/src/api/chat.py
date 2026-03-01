import asyncio
import json
import logging
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.agent import agent, _build_deps, generate_timeline
from src.core.auth import get_current_user
from src.core.config import settings
from src.core.database import get_postgres_session
from src.models.postgres.users import UserModel
from src.repositories.chats import ChatRepository
from src.schemas.chat import ChatRequest, GenerateRequest, GenerateResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agent", tags=["agent"])


def _sse_event(event_type: str, data: dict) -> str:
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


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
    target_date = body.date or date.today()
    chat_repo = ChatRepository(session)

    # Find or create chat session for this user+date
    user_cfg = current_user.session_config or {}
    effective_model = user_cfg.get("llm_model") or settings.chat_llm_model

    chat = await chat_repo.get_active_chat(current_user.id, target_date)
    if not chat:
        chat = await chat_repo.create(
            user_id=current_user.id,
            target_date=target_date,
            trigger="chat",
            llm_model=effective_model,
        )

    # Load message history
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

    event_queue: asyncio.Queue = asyncio.Queue()

    deps = _build_deps(
        user_id=current_user.id,
        session=session,
        target_date=target_date,
        chat_id=chat.id,
        user_session_config=current_user.session_config,
        event_queue=event_queue,
    )

    async def run_agent():
        """Run agent in background task, pushing events to the queue."""
        try:
            async with agent.run_stream(
                body.message,
                deps=deps,
                model=effective_model,
                message_history=message_history,
            ) as result:
                async for text in result.stream_text(delta=True):
                    await event_queue.put(("text", {"text": text}))

                # Save message history and tokens
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

            await event_queue.put(("done", {}))
        except Exception as e:
            logger.exception("Agent error in chat %s", chat.id)
            await event_queue.put(("error", {"error": str(e)}))

    async def event_generator():
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
