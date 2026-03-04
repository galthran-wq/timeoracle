import logging
from abc import ABC, abstractmethod
from datetime import date, datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.postgres.timeline_entries import TimelineEntryModel
from src.schemas.timeline_entries import TimelineEntryCreate, TimelineEntryUpdate, TimelineEntryBulkItem

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

    @abstractmethod
    async def get_by_time_range(
        self, user_id: UUID, start_dt: datetime, end_dt: datetime,
        limit: int, offset: int, category: Optional[str] = None, include_overlap: bool = False,
    ) -> list[TimelineEntryModel]:
        pass

    @abstractmethod
    async def count_by_time_range(
        self, user_id: UUID, start_dt: datetime, end_dt: datetime,
        category: Optional[str] = None,
    ) -> int:
        pass

    @abstractmethod
    async def get_max_updated_at_in_range(
        self, user_id: UUID, start_dt: datetime, end_dt: datetime,
    ) -> datetime | None:
        pass

    @abstractmethod
    async def bulk_upsert(
        self, user_id: UUID, items: list[TimelineEntryBulkItem],
        chat_id: UUID | None = None,
    ) -> tuple[int, int, int, list[dict]]:
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

    async def get_by_time_range(
        self, user_id: UUID, start_dt: datetime, end_dt: datetime,
        limit: int, offset: int, category: Optional[str] = None, include_overlap: bool = False,
    ) -> list[TimelineEntryModel]:
        query = select(TimelineEntryModel).where(TimelineEntryModel.user_id == user_id)
        if include_overlap:
            query = query.where(
                TimelineEntryModel.start_time < end_dt,
                TimelineEntryModel.end_time > start_dt,
            )
        else:
            query = query.where(
                TimelineEntryModel.start_time >= start_dt,
                TimelineEntryModel.start_time < end_dt,
            )
        query = (
            query
            .order_by(TimelineEntryModel.start_time.asc())
            .limit(limit)
            .offset(offset)
        )
        if category is not None:
            query = query.where(TimelineEntryModel.category == category)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def count_by_time_range(
        self, user_id: UUID, start_dt: datetime, end_dt: datetime,
        category: Optional[str] = None,
    ) -> int:
        query = (
            select(func.count())
            .select_from(TimelineEntryModel)
            .where(
                TimelineEntryModel.user_id == user_id,
                TimelineEntryModel.start_time >= start_dt,
                TimelineEntryModel.start_time < end_dt,
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

    async def get_max_updated_at_in_range(
        self, user_id: UUID, start_dt: datetime, end_dt: datetime,
    ) -> datetime | None:
        result = await self.session.execute(
            select(func.max(TimelineEntryModel.updated_at)).where(
                TimelineEntryModel.user_id == user_id,
                TimelineEntryModel.start_time >= start_dt,
                TimelineEntryModel.start_time < end_dt,
            )
        )
        return result.scalar_one_or_none()

    async def bulk_upsert(
        self, user_id: UUID, items: list[TimelineEntryBulkItem],
        chat_id: UUID | None = None,
    ) -> tuple[int, int, int, list[dict]]:
        created = updated = skipped = 0
        errors = []
        try:
            update_ids = [item.id for item in items if item.id is not None]
            existing = {}
            if update_ids:
                result = await self.session.execute(
                    select(TimelineEntryModel).where(
                        TimelineEntryModel.id.in_(update_ids),
                        TimelineEntryModel.user_id == user_id,
                    )
                )
                existing = {e.id: e for e in result.scalars().all()}

            for i, item in enumerate(items):
                if item.id is None:
                    db_entry = TimelineEntryModel(
                        user_id=user_id,
                        date=item.date,
                        start_time=item.start_time,
                        end_time=item.end_time,
                        label=item.label,
                        description=item.description,
                        category=item.category,
                        color=item.color,
                        source="ai_generated",
                        source_summary=item.source_summary,
                        confidence=item.confidence,
                        chat_id=chat_id,
                    )
                    self.session.add(db_entry)
                    created += 1
                else:
                    entry = existing.get(item.id)
                    if entry is None:
                        errors.append({"index": i, "message": "Entry not found"})
                        continue
                    if entry.edited_by_user:
                        skipped += 1
                        continue
                    entry.date = item.date
                    entry.start_time = item.start_time
                    entry.end_time = item.end_time
                    entry.label = item.label
                    entry.description = item.description
                    entry.category = item.category
                    entry.color = item.color
                    entry.source = "ai_generated"
                    entry.source_summary = item.source_summary
                    entry.confidence = item.confidence
                    entry.chat_id = chat_id
                    updated += 1

            await self.session.commit()
            return created, updated, skipped, errors
        except Exception:
            await self.session.rollback()
            raise
