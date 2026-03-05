import asyncio
from dataclasses import dataclass, field
from datetime import date
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.repositories.activity_events import ActivityEventRepository
from src.repositories.agent_memories import AgentMemoryRepository
from src.repositories.productivity_points import ProductivityPointRepository
from src.repositories.timeline_entries import TimelineEntryRepository
from src.repositories.chats import ChatRepository


@dataclass
class AgentDeps:
    user_id: UUID
    session: AsyncSession
    activity_repo: ActivityEventRepository
    timeline_repo: TimelineEntryRepository
    chat_repo: ChatRepository
    target_date: Optional[date] = None
    chat_id: Optional[UUID] = None
    user_session_config: Optional[dict] = None
    event_queue: Optional[asyncio.Queue] = None
    memories: list[str] = field(default_factory=list)
    memory_repo: Optional[AgentMemoryRepository] = None
    productivity_repo: Optional[ProductivityPointRepository] = None
