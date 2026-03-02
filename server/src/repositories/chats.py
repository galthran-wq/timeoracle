import json
import logging
from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.postgres.chats import ChatModel

logger = logging.getLogger(__name__)


class ChatRepositoryInterface(ABC):
    @abstractmethod
    async def create(
        self, user_id: UUID, trigger: str, llm_model: str,
    ) -> ChatModel:
        pass

    @abstractmethod
    async def get_by_id(self, chat_id: UUID) -> Optional[ChatModel]:
        pass

    @abstractmethod
    async def list_for_user(
        self, user_id: UUID, limit: int = 20, offset: int = 0,
    ) -> tuple[list[ChatModel], int]:
        pass

    @abstractmethod
    async def update_messages(
        self, chat_id: UUID, messages_json: str,
        input_tokens: int, output_tokens: int,
    ) -> None:
        pass


class ChatRepository(ChatRepositoryInterface):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self, user_id: UUID, trigger: str, llm_model: str,
    ) -> ChatModel:
        try:
            chat = ChatModel(
                user_id=user_id,
                trigger=trigger,
                llm_model=llm_model,
            )
            self.session.add(chat)
            await self.session.commit()
            await self.session.refresh(chat)
            return chat
        except Exception:
            await self.session.rollback()
            raise

    async def get_by_id(self, chat_id: UUID) -> Optional[ChatModel]:
        result = await self.session.execute(
            select(ChatModel).where(ChatModel.id == chat_id)
        )
        return result.scalar_one_or_none()

    async def list_for_user(
        self, user_id: UUID, limit: int = 20, offset: int = 0,
    ) -> tuple[list[ChatModel], int]:
        base = select(ChatModel).where(
            ChatModel.user_id == user_id,
            ChatModel.trigger.in_(["chat", "generate"]),
        )
        count_result = await self.session.execute(
            select(func.count()).select_from(base.subquery())
        )
        total = count_result.scalar() or 0

        result = await self.session.execute(
            base.order_by(ChatModel.created_at.desc())
            .limit(limit).offset(offset)
        )
        return list(result.scalars().all()), total

    async def update_messages(
        self, chat_id: UUID, messages_json: str,
        input_tokens: int, output_tokens: int,
    ) -> None:
        try:
            parsed = json.loads(messages_json)
        except (json.JSONDecodeError, TypeError):
            parsed = []

        try:
            await self.session.execute(
                update(ChatModel)
                .where(ChatModel.id == chat_id)
                .values(
                    messages=parsed,
                    total_input_tokens=ChatModel.total_input_tokens + input_tokens,
                    total_output_tokens=ChatModel.total_output_tokens + output_tokens,
                )
            )
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
