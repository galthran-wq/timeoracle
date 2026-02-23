import logging
from abc import ABC, abstractmethod
from datetime import date
from typing import Optional
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.postgres.timeline_entries import TimelineEntryModel
from src.schemas.timeline_entries import TimelineEntryCreate, TimelineEntryUpdate

logger = logging.getLogger(__name__)


class TimelineEntryRepositoryInterface(ABC):
    @abstractmethod
    async def create(self, user_id: UUID, entry: TimelineEntryCreate) -> TimelineEntryModel:
        pass

    @abstractmethod
    async def get_by_id(self, entry_id: UUID) -> Optional[TimelineEntryModel]:
        pass

    @abstractmethod
    async def get_by_date_range(
        self, user_id: UUID, start_date: date, end_date: date,
        limit: int, offset: int, category: Optional[str] = None,
    ) -> list[TimelineEntryModel]:
        pass

    @abstractmethod
    async def count_by_date_range(
        self, user_id: UUID, start_date: date, end_date: date,
        category: Optional[str] = None,
    ) -> int:
        pass

    @abstractmethod
    async def update(self, entry: TimelineEntryModel, updates: TimelineEntryUpdate) -> TimelineEntryModel:
        pass

    @abstractmethod
    async def delete(self, entry: TimelineEntryModel) -> None:
        pass


class TimelineEntryRepository(TimelineEntryRepositoryInterface):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, user_id: UUID, entry: TimelineEntryCreate) -> TimelineEntryModel:
        try:
            db_entry = TimelineEntryModel(
                user_id=user_id,
                date=entry.date,
                start_time=entry.start_time,
                end_time=entry.end_time,
                label=entry.label,
                description=entry.description,
                category=entry.category,
                color=entry.color,
                source="manual",
            )
            self.session.add(db_entry)
            await self.session.commit()
            await self.session.refresh(db_entry)
            return db_entry
        except Exception:
            await self.session.rollback()
            raise

    async def get_by_id(self, entry_id: UUID) -> Optional[TimelineEntryModel]:
        result = await self.session.execute(
            select(TimelineEntryModel).where(TimelineEntryModel.id == entry_id)
        )
        return result.scalar_one_or_none()

    async def get_by_date_range(
        self, user_id: UUID, start_date: date, end_date: date,
        limit: int, offset: int, category: Optional[str] = None,
    ) -> list[TimelineEntryModel]:
        query = (
            select(TimelineEntryModel)
            .where(
                TimelineEntryModel.user_id == user_id,
                TimelineEntryModel.date >= start_date,
                TimelineEntryModel.date <= end_date,
            )
            .order_by(TimelineEntryModel.start_time.asc())
            .limit(limit)
            .offset(offset)
        )
        if category is not None:
            query = query.where(TimelineEntryModel.category == category)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def count_by_date_range(
        self, user_id: UUID, start_date: date, end_date: date,
        category: Optional[str] = None,
    ) -> int:
        query = (
            select(func.count())
            .select_from(TimelineEntryModel)
            .where(
                TimelineEntryModel.user_id == user_id,
                TimelineEntryModel.date >= start_date,
                TimelineEntryModel.date <= end_date,
            )
        )
        if category is not None:
            query = query.where(TimelineEntryModel.category == category)

        result = await self.session.execute(query)
        return result.scalar_one()

    async def update(self, entry: TimelineEntryModel, updates: TimelineEntryUpdate) -> TimelineEntryModel:
        try:
            update_data = updates.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                setattr(entry, field, value)

            if "start_time" in update_data and "date" not in update_data:
                entry.date = update_data["start_time"].date()

            entry.edited_by_user = True

            await self.session.commit()
            await self.session.refresh(entry)
            return entry
        except Exception:
            await self.session.rollback()
            raise

    async def delete(self, entry: TimelineEntryModel) -> None:
        try:
            await self.session.delete(entry)
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
