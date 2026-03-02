import logging
from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.postgres.agent_memories import AgentMemoryModel

logger = logging.getLogger(__name__)


class AgentMemoryRepositoryInterface(ABC):
    @abstractmethod
    async def create(
        self, user_id: UUID, content: str, source: str,
        source_entry_id: Optional[UUID] = None,
    ) -> AgentMemoryModel:
        pass

    @abstractmethod
    async def get_active_for_user(
        self, user_id: UUID, limit: int = 50,
    ) -> list[AgentMemoryModel]:
        pass

    @abstractmethod
    async def count_for_user(self, user_id: UUID) -> int:
        pass

    @abstractmethod
    async def delete(self, memory_id: UUID, user_id: UUID) -> bool:
        pass


class AgentMemoryRepository(AgentMemoryRepositoryInterface):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self, user_id: UUID, content: str, source: str,
        source_entry_id: Optional[UUID] = None,
    ) -> AgentMemoryModel:
        memory = AgentMemoryModel(
            user_id=user_id,
            content=content,
            source=source,
            source_entry_id=source_entry_id,
        )
        self.session.add(memory)
        try:
            await self.session.commit()
            await self.session.refresh(memory)
        except Exception:
            await self.session.rollback()
            raise
        return memory

    async def get_active_for_user(
        self, user_id: UUID, limit: int = 50,
    ) -> list[AgentMemoryModel]:
        query = (
            select(AgentMemoryModel)
            .where(
                AgentMemoryModel.user_id == user_id,
                AgentMemoryModel.is_active == True,
            )
            .order_by(AgentMemoryModel.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def count_for_user(self, user_id: UUID) -> int:
        query = (
            select(func.count())
            .select_from(AgentMemoryModel)
            .where(
                AgentMemoryModel.user_id == user_id,
                AgentMemoryModel.is_active == True,
            )
        )
        result = await self.session.execute(query)
        return result.scalar() or 0

    async def delete(self, memory_id: UUID, user_id: UUID) -> bool:
        query = select(AgentMemoryModel).where(
            AgentMemoryModel.id == memory_id,
            AgentMemoryModel.user_id == user_id,
        )
        result = await self.session.execute(query)
        memory = result.scalar_one_or_none()
        if not memory:
            return False
        try:
            await self.session.delete(memory)
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        return True
