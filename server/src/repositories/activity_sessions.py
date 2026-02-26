import logging
from abc import ABC, abstractmethod
from datetime import date, datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import select, func, delete, or_
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.postgres.activity_sessions import ActivitySessionModel

logger = logging.getLogger(__name__)


class ActivitySessionRepositoryInterface(ABC):
    @abstractmethod
    async def bulk_create(self, user_id: UUID, sessions: list[dict]) -> int:
        pass

    @abstractmethod
    async def delete_for_date(self, user_id: UUID, target_date: date) -> int:
        pass

    @abstractmethod
    async def get_by_date_range(
        self, user_id: UUID, start_date: date, end_date: date,
        limit: int, offset: int,
    ) -> list[ActivitySessionModel]:
        pass

    @abstractmethod
    async def count_by_date_range(
        self, user_id: UUID, start_date: date, end_date: date,
    ) -> int:
        pass

    @abstractmethod
    async def get_latest_session(self, user_id: UUID) -> Optional[ActivitySessionModel]:
        pass

    @abstractmethod
    async def get_earliest_affected_start(
        self, user_id: UUID, from_time: datetime,
    ) -> Optional[datetime]:
        pass

    @abstractmethod
    async def delete_from_timestamp(self, user_id: UUID, from_time: datetime) -> int:
        pass


class ActivitySessionRepository(ActivitySessionRepositoryInterface):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def bulk_create(self, user_id: UUID, sessions: list[dict]) -> int:
        if not sessions:
            return 0

        rows = [
            {
                "id": uuid4(),
                "user_id": user_id,
                "app_name": s["app_name"],
                "window_title": s["window_title"],
                "window_titles": s.get("window_titles"),
                "url": s.get("url"),
                "icon": s.get("icon"),
                "start_time": s["start_time"],
                "end_time": s["end_time"],
                "date": s["date"],
            }
            for s in sessions
        ]

        stmt = pg_insert(ActivitySessionModel).values(rows)
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount

    async def delete_for_date(self, user_id: UUID, target_date: date) -> int:
        stmt = (
            delete(ActivitySessionModel)
            .where(
                ActivitySessionModel.user_id == user_id,
                ActivitySessionModel.date == target_date,
            )
        )
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount

    async def get_by_date_range(
        self, user_id: UUID, start_date: date, end_date: date,
        limit: int, offset: int,
    ) -> list[ActivitySessionModel]:
        query = (
            select(ActivitySessionModel)
            .where(
                ActivitySessionModel.user_id == user_id,
                ActivitySessionModel.date >= start_date,
                ActivitySessionModel.date <= end_date,
            )
            .order_by(ActivitySessionModel.start_time.asc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def count_by_date_range(
        self, user_id: UUID, start_date: date, end_date: date,
    ) -> int:
        query = (
            select(func.count())
            .select_from(ActivitySessionModel)
            .where(
                ActivitySessionModel.user_id == user_id,
                ActivitySessionModel.date >= start_date,
                ActivitySessionModel.date <= end_date,
            )
        )
        result = await self.session.execute(query)
        return result.scalar_one()

    async def get_latest_session(self, user_id: UUID) -> Optional[ActivitySessionModel]:
        query = (
            select(ActivitySessionModel)
            .where(ActivitySessionModel.user_id == user_id)
            .order_by(ActivitySessionModel.end_time.desc())
            .limit(1)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_earliest_affected_start(
        self, user_id: UUID, from_time: datetime,
    ) -> Optional[datetime]:
        """Get the earliest start_time of any session overlapping with [from_time, inf)."""
        query = (
            select(func.min(ActivitySessionModel.start_time))
            .where(
                ActivitySessionModel.user_id == user_id,
                or_(
                    ActivitySessionModel.start_time >= from_time,
                    ActivitySessionModel.end_time > from_time,
                ),
            )
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def delete_from_timestamp(self, user_id: UUID, from_time: datetime) -> int:
        stmt = (
            delete(ActivitySessionModel)
            .where(
                ActivitySessionModel.user_id == user_id,
                or_(
                    ActivitySessionModel.start_time >= from_time,
                    ActivitySessionModel.end_time > from_time,
                ),
            )
        )
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount
