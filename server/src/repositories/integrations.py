import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from src.models.postgres.user_integrations import UserIntegrationModel
from src.models.postgres.integration_connect_tokens import IntegrationConnectTokenModel

logger = logging.getLogger(__name__)


class IntegrationRepositoryInterface(ABC):
    @abstractmethod
    async def get_by_user_and_provider(
        self, user_id: UUID, provider: str
    ) -> Optional[UserIntegrationModel]:
        pass

    @abstractmethod
    async def get_all_for_user(self, user_id: UUID) -> list[UserIntegrationModel]:
        pass

    @abstractmethod
    async def upsert(
        self,
        user_id: UUID,
        provider: str,
        external_user_id: str,
        credentials: dict,
    ) -> UserIntegrationModel:
        pass

    @abstractmethod
    async def delete_integration(self, user_id: UUID, provider: str) -> bool:
        pass

    @abstractmethod
    async def get_by_provider_and_external_id(
        self, provider: str, external_user_id: str
    ) -> Optional[UserIntegrationModel]:
        pass

    @abstractmethod
    async def create_connect_token(
        self, user_id: UUID, provider: str, token: str, expires_at: datetime
    ) -> IntegrationConnectTokenModel:
        pass

    @abstractmethod
    async def get_connect_token(self, token: str) -> Optional[IntegrationConnectTokenModel]:
        pass

    @abstractmethod
    async def delete_connect_token(self, token: str) -> None:
        pass

    @abstractmethod
    async def delete_user_tokens(self, user_id: UUID, provider: str) -> None:
        pass


class IntegrationRepository(IntegrationRepositoryInterface):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_user_and_provider(
        self, user_id: UUID, provider: str
    ) -> Optional[UserIntegrationModel]:
        result = await self.session.execute(
            select(UserIntegrationModel).where(
                UserIntegrationModel.user_id == user_id,
                UserIntegrationModel.provider == provider,
            )
        )
        return result.scalar_one_or_none()

    async def get_all_for_user(self, user_id: UUID) -> list[UserIntegrationModel]:
        result = await self.session.execute(
            select(UserIntegrationModel).where(
                UserIntegrationModel.user_id == user_id
            )
        )
        return list(result.scalars().all())

    async def upsert(
        self,
        user_id: UUID,
        provider: str,
        external_user_id: str,
        credentials: dict,
    ) -> UserIntegrationModel:
        try:
            stmt = pg_insert(UserIntegrationModel).values(
                user_id=user_id,
                provider=provider,
                external_user_id=external_user_id,
                credentials=credentials,
                is_enabled=True,
            )
            stmt = stmt.on_conflict_do_update(
                constraint="uq_user_integrations_user_provider",
                set_={
                    "external_user_id": external_user_id,
                    "credentials": credentials,
                    "is_enabled": True,
                    "connected_at": datetime.utcnow(),
                },
            )
            await self.session.execute(stmt)
            await self.session.commit()

            return await self.get_by_user_and_provider(user_id, provider)
        except Exception as e:
            await self.session.rollback()
            raise e

    async def delete_integration(self, user_id: UUID, provider: str) -> bool:
        try:
            result = await self.session.execute(
                delete(UserIntegrationModel).where(
                    UserIntegrationModel.user_id == user_id,
                    UserIntegrationModel.provider == provider,
                )
            )
            await self.session.commit()
            return result.rowcount > 0
        except Exception as e:
            await self.session.rollback()
            raise e

    async def get_by_provider_and_external_id(
        self, provider: str, external_user_id: str
    ) -> Optional[UserIntegrationModel]:
        result = await self.session.execute(
            select(UserIntegrationModel).where(
                UserIntegrationModel.provider == provider,
                UserIntegrationModel.external_user_id == external_user_id,
            )
        )
        return result.scalar_one_or_none()

    async def create_connect_token(
        self, user_id: UUID, provider: str, token: str, expires_at: datetime
    ) -> IntegrationConnectTokenModel:
        try:
            db_token = IntegrationConnectTokenModel(
                user_id=user_id,
                provider=provider,
                token=token,
                expires_at=expires_at,
            )
            self.session.add(db_token)
            await self.session.commit()
            await self.session.refresh(db_token)
            return db_token
        except Exception as e:
            await self.session.rollback()
            raise e

    async def get_connect_token(self, token: str) -> Optional[IntegrationConnectTokenModel]:
        result = await self.session.execute(
            select(IntegrationConnectTokenModel).where(
                IntegrationConnectTokenModel.token == token
            )
        )
        return result.scalar_one_or_none()

    async def delete_connect_token(self, token: str) -> None:
        try:
            await self.session.execute(
                delete(IntegrationConnectTokenModel).where(
                    IntegrationConnectTokenModel.token == token
                )
            )
            await self.session.commit()
        except Exception as e:
            await self.session.rollback()
            raise e

    async def delete_user_tokens(self, user_id: UUID, provider: str) -> None:
        try:
            await self.session.execute(
                delete(IntegrationConnectTokenModel).where(
                    IntegrationConnectTokenModel.user_id == user_id,
                    IntegrationConnectTokenModel.provider == provider,
                )
            )
            await self.session.commit()
        except Exception as e:
            await self.session.rollback()
            raise e
