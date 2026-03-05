import asyncio
import logging
from datetime import date
from uuid import UUID

from pydantic_ai import Agent, RunContext
from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.deps import AgentDeps
from src.agent.prompts import build_system_prompt
from src.agent.tools import (
    get_activity_sessions,
    get_existing_timeline,
    save_timeline_entries,
    save_productivity_curve,
    save_memory,
)
from src.core.config import settings
from src.repositories.activity_events import ActivityEventRepository
from src.repositories.agent_memories import AgentMemoryRepository
from src.repositories.chats import ChatRepository
from src.repositories.productivity_points import ProductivityPointRepository
from src.repositories.timeline_entries import TimelineEntryRepository

logger = logging.getLogger(__name__)

agent = Agent(deps_type=AgentDeps)


@agent.system_prompt
async def dynamic_system_prompt(ctx: RunContext[AgentDeps]) -> str:
    cfg = ctx.deps.user_session_config or {}
    return build_system_prompt(
        ctx.deps.target_date,
        day_start_hour=cfg.get("day_start_hour", 0),
        day_timezone=cfg.get("timezone", "UTC"),
        categories=cfg.get("categories"),
        classification_rules=cfg.get("classification_rules"),
        memories=ctx.deps.memories or None,
    )


agent.tool(get_activity_sessions)
agent.tool(get_existing_timeline)
agent.tool(save_timeline_entries)
agent.tool(save_productivity_curve)
agent.tool(save_memory)


async def _load_memories(session: AsyncSession, user_id: UUID) -> list[str]:
    repo = AgentMemoryRepository(session)
    rows = await repo.get_active_for_user(user_id, limit=50)
    return [m.content for m in rows]


def _build_deps(
    user_id: UUID,
    session: AsyncSession,
    target_date: date | None = None,
    chat_id: UUID | None = None,
    user_session_config: dict | None = None,
    event_queue: asyncio.Queue | None = None,
    memories: list[str] | None = None,
) -> AgentDeps:
    return AgentDeps(
        user_id=user_id,
        session=session,
        activity_repo=ActivityEventRepository(session),
        timeline_repo=TimelineEntryRepository(session),
        chat_repo=ChatRepository(session),
        target_date=target_date,
        chat_id=chat_id,
        user_session_config=user_session_config,
        event_queue=event_queue,
        memories=memories or [],
        memory_repo=AgentMemoryRepository(session),
        productivity_repo=ProductivityPointRepository(session),
    )


async def generate_timeline(
    user_id: UUID,
    target_date: date,
    session: AsyncSession,
    model: str | None = None,
    user_session_config: dict | None = None,
) -> dict:
    chat_repo = ChatRepository(session)
    chat = await chat_repo.create(
        user_id=user_id,
        trigger="generate",
        llm_model=model or (user_session_config or {}).get("llm_model") or settings.default_llm_model,
    )

    memories = await _load_memories(session, user_id)

    deps = _build_deps(
        user_id=user_id,
        session=session,
        target_date=target_date,
        chat_id=chat.id,
        user_session_config=user_session_config,
        memories=memories,
    )

    prompt = f"Generate timeline entries for {target_date.isoformat()}"
    user_model = (user_session_config or {}).get("llm_model")
    effective_model = model or user_model or settings.default_llm_model

    result = await agent.run(
        prompt,
        deps=deps,
        model=effective_model,
    )

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

    return {
        "message": result.output,
        "chat_id": str(chat.id),
    }
