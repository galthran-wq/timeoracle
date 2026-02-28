import logging
from abc import ABC, abstractmethod
from typing import Optional, Union
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from src.models.postgres.users import UserModel

logger = logging.getLogger(__name__)


class UserRepositoryInterface(ABC):
    @abstractmethod
    async def create_user(self) -> UserModel:
        pass

    @abstractmethod
    async def get_user(self, user_id: UUID) -> Optional[UserModel]:
        pass

    @abstractmethod
    async def get_user_by_email(self, email: str) -> Optional[UserModel]:
        pass

    @abstractmethod
    async def register_user(self, user_id: UUID, email: str, password_hash: str) -> UserModel:
        pass

    @abstractmethod
    async def create_registered_user(self, email: str, password_hash: str) -> UserModel:
        pass

    @abstractmethod
    async def delete_user(self, user_identifier: Union[UUID, str], deleting_user_id: UUID) -> UserModel:
        pass

    @abstractmethod
    async def update_session_config(self, user_id: UUID, config_dict: dict) -> UserModel:
        pass


class UserRepository(UserRepositoryInterface):
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create_user(self) -> UserModel:
        db_user = UserModel()
        self.session.add(db_user)
        await self.session.commit()
        await self.session.refresh(db_user)
        return db_user
    
    async def get_user(self, user_id: UUID) -> Optional[UserModel]:
        result = await self.session.execute(
            select(UserModel).where(UserModel.id == user_id)
        )
        return result.scalar_one_or_none()
    
    async def get_user_by_email(self, email: str) -> Optional[UserModel]:
        result = await self.session.execute(
            select(UserModel).where(UserModel.email == email)
        )
        return result.scalar_one_or_none()
    
    async def register_user(self, user_id: UUID, email: str, password_hash: str) -> UserModel:
        result = await self.session.execute(
            select(UserModel).where(UserModel.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            raise ValueError("User not found")
        
        existing_user = await self.get_user_by_email(email)
        if existing_user:
            raise ValueError("Email already registered")
        
        user.email = email
        user.password_hash = password_hash
        user.is_verified = True
        
        await self.session.commit()
        await self.session.refresh(user)
        
        return user
    
    async def create_registered_user(self, email: str, password_hash: str) -> UserModel:
        try:
            existing_user = await self.get_user_by_email(email)
            if existing_user:
                raise ValueError("Email already registered")

            db_user = UserModel(
                email=email,
                password_hash=password_hash,
                is_verified=True,
                is_superuser=False
            )
            
            self.session.add(db_user)
            await self.session.commit()
            await self.session.refresh(db_user)
            return db_user
            
        except Exception as e:
            await self.session.rollback()
            raise e

    async def delete_user(self, user_identifier: Union[UUID, str], deleting_user_id: UUID) -> UserModel:
        try:
            user = None
            if isinstance(user_identifier, UUID):
                user = await self.get_user(user_identifier)
            else:
                try:
                    uuid_identifier = UUID(str(user_identifier))
                    user = await self.get_user(uuid_identifier)
                except ValueError:
                    user = await self.get_user_by_email(str(user_identifier))

            if not user:
                raise ValueError("User not found")

            if user.id == deleting_user_id:
                raise ValueError("Cannot delete your own account")

            if user.is_superuser:
                raise ValueError("Cannot delete another superuser account")

            await self.session.delete(user)
            await self.session.commit()

            return user

        except Exception as e:
            await self.session.rollback()
            raise e

    async def update_session_config(self, user_id: UUID, config_dict: dict) -> UserModel:
        try:
            user = await self.get_user(user_id)
            if not user:
                raise ValueError("User not found")
            existing = dict(user.session_config or {})
            existing.update(config_dict)
            user.session_config = existing
            await self.session.commit()
            await self.session.refresh(user)
            return user
        except Exception as e:
            await self.session.rollback()
            raise e
