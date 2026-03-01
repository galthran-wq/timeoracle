import json
import uuid
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.postgres.users import UserModel
from src.repositories.chats import ChatRepository


async def _create_user(db_session: AsyncSession) -> UserModel:
    user = UserModel(
        id=uuid.uuid4(),
        email=f"test-{uuid.uuid4().hex[:8]}@example.com",
        password_hash="fake",
        is_verified=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


class TestChatRepository:
    async def test_create(self, db_session: AsyncSession, engine):
        user = await _create_user(db_session)
        repo = ChatRepository(db_session)

        chat = await repo.create(
            user_id=user.id,
            target_date=date(2026, 3, 1),
            trigger="generate",
            llm_model="openai:gpt-4o-mini",
        )

        assert chat.id is not None
        assert chat.user_id == user.id
        assert chat.date == date(2026, 3, 1)
        assert chat.trigger == "generate"
        assert chat.llm_model == "openai:gpt-4o-mini"
        assert chat.total_input_tokens == 0
        assert chat.total_output_tokens == 0

    async def test_get_by_id(self, db_session: AsyncSession, engine):
        user = await _create_user(db_session)
        repo = ChatRepository(db_session)

        chat = await repo.create(
            user_id=user.id,
            target_date=date(2026, 3, 1),
            trigger="chat",
            llm_model="openai:gpt-4o-mini",
        )

        found = await repo.get_by_id(chat.id)
        assert found is not None
        assert found.id == chat.id

    async def test_get_by_id_not_found(self, db_session: AsyncSession, engine):
        repo = ChatRepository(db_session)
        found = await repo.get_by_id(uuid.uuid4())
        assert found is None

    async def test_get_active_chat(self, db_session: AsyncSession, engine):
        user = await _create_user(db_session)
        repo = ChatRepository(db_session)

        # Create a generate chat (should not be returned)
        await repo.create(
            user_id=user.id,
            target_date=date(2026, 3, 1),
            trigger="generate",
            llm_model="openai:gpt-4o-mini",
        )

        # Create an interactive chat (should be returned)
        chat = await repo.create(
            user_id=user.id,
            target_date=date(2026, 3, 1),
            trigger="chat",
            llm_model="openai:gpt-4o-mini",
        )

        found = await repo.get_active_chat(user.id, date(2026, 3, 1))
        assert found is not None
        assert found.id == chat.id

    async def test_get_active_chat_different_date(self, db_session: AsyncSession, engine):
        user = await _create_user(db_session)
        repo = ChatRepository(db_session)

        await repo.create(
            user_id=user.id,
            target_date=date(2026, 3, 1),
            trigger="chat",
            llm_model="openai:gpt-4o-mini",
        )

        # Different date should return None
        found = await repo.get_active_chat(user.id, date(2026, 3, 2))
        assert found is None

    async def test_update_messages(self, db_session: AsyncSession, engine):
        user = await _create_user(db_session)
        repo = ChatRepository(db_session)

        chat = await repo.create(
            user_id=user.id,
            target_date=date(2026, 3, 1),
            trigger="chat",
            llm_model="openai:gpt-4o-mini",
        )

        messages = [{"role": "user", "content": "hello"}, {"role": "assistant", "content": "hi"}]
        await repo.update_messages(
            chat.id,
            json.dumps(messages),
            input_tokens=100,
            output_tokens=50,
        )

        updated = await repo.get_by_id(chat.id)
        assert updated.messages == messages
        assert updated.total_input_tokens == 100
        assert updated.total_output_tokens == 50

    async def test_update_messages_accumulates_tokens(self, db_session: AsyncSession, engine):
        user = await _create_user(db_session)
        repo = ChatRepository(db_session)

        chat = await repo.create(
            user_id=user.id,
            target_date=date(2026, 3, 1),
            trigger="chat",
            llm_model="openai:gpt-4o-mini",
        )

        await repo.update_messages(chat.id, "[]", input_tokens=100, output_tokens=50)
        await repo.update_messages(chat.id, "[]", input_tokens=200, output_tokens=100)

        updated = await repo.get_by_id(chat.id)
        assert updated.total_input_tokens == 300
        assert updated.total_output_tokens == 150
