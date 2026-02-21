import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.postgres.activity_events import ActivityEventModel
from src.schemas.activity_events import ActivityEventCreate

logger = logging.getLogger(__name__)

MAX_EVENT_AGE_DAYS = 30
MAX_FUTURE_TOLERANCE_SECONDS = 300
MAX_DAILY_EVENTS_PER_USER = 100_000


class ActivityEventRepositoryInterface(ABC):
    @abstractmethod
    def validate_batch(self, events: list[ActivityEventCreate]) -> Optional[list[dict]]:
        pass

    @abstractmethod
    async def check_daily_limit(self, user_id: UUID, batch_size: int) -> bool:
        pass

    @abstractmethod
    async def bulk_create(self, user_id: UUID, events: list[ActivityEventCreate]) -> int:
        pass

    @abstractmethod
    async def get_by_time_range(
        self, user_id: UUID, start: datetime, end: datetime,
        limit: int, offset: int,
        event_type: Optional[str] = None, app_name: Optional[str] = None,
    ) -> list[ActivityEventModel]:
        pass

    @abstractmethod
    async def count_by_time_range(
        self, user_id: UUID, start: datetime, end: datetime,
        event_type: Optional[str] = None, app_name: Optional[str] = None,
    ) -> int:
        pass

    @abstractmethod
    async def get_latest(self, user_id: UUID, limit: int) -> list[ActivityEventModel]:
        pass

    @abstractmethod
    async def count_events_today(self, user_id: UUID) -> int:
        pass


class ActivityEventRepository(ActivityEventRepositoryInterface):
    def __init__(self, session: AsyncSession):
        self.session = session

    def validate_batch(self, events: list[ActivityEventCreate]) -> Optional[list[dict]]:
        now = datetime.now(timezone.utc)
        max_future = now + timedelta(seconds=MAX_FUTURE_TOLERANCE_SECONDS)
        min_past = now - timedelta(days=MAX_EVENT_AGE_DAYS)
        errors = []

        for i, event in enumerate(events):
            if event.timestamp > max_future:
                errors.append({
                    "index": i,
                    "field": "timestamp",
                    "message": "Timestamp is in the future (>5 min tolerance)",
                })
            elif event.timestamp < min_past:
                errors.append({
                    "index": i,
                    "field": "timestamp",
                    "message": f"Timestamp is older than {MAX_EVENT_AGE_DAYS} days",
                })

        return errors if errors else None

    async def check_daily_limit(self, user_id: UUID, batch_size: int) -> bool:
        one_day_ago = datetime.now(timezone.utc) - timedelta(days=1)
        result = await self.session.execute(
            select(func.count()).select_from(ActivityEventModel).where(
                ActivityEventModel.user_id == user_id,
                ActivityEventModel.created_at > one_day_ago,
            )
        )
        count = result.scalar_one()
        return count + batch_size <= MAX_DAILY_EVENTS_PER_USER

    async def bulk_create(self, user_id: UUID, events: list[ActivityEventCreate]) -> int:
        rows = [
            {
                "id": uuid4(),
                "user_id": user_id,
                "client_event_id": event.client_event_id,
                "timestamp": event.timestamp,
                "event_type": event.event_type.value,
                "app_name": event.app_name,
                "window_title": event.window_title,
                "url": event.url,
                "metadata": event.metadata,
            }
            for event in events
        ]

        from sqlalchemy.dialects.postgresql import insert as pg_insert

        stmt = pg_insert(ActivityEventModel).values(rows)
        stmt = stmt.on_conflict_do_nothing(
            constraint="uq_activity_events_user_client_event"
        )
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount

    async def get_by_time_range(
        self, user_id: UUID, start: datetime, end: datetime,
        limit: int, offset: int,
        event_type: Optional[str] = None, app_name: Optional[str] = None,
    ) -> list[ActivityEventModel]:
        query = (
            select(ActivityEventModel)
            .where(
                ActivityEventModel.user_id == user_id,
                ActivityEventModel.timestamp >= start,
                ActivityEventModel.timestamp <= end,
            )
            .order_by(ActivityEventModel.timestamp.asc())
            .limit(limit)
            .offset(offset)
        )
        if event_type is not None:
            query = query.where(ActivityEventModel.event_type == event_type)
        if app_name is not None:
            query = query.where(ActivityEventModel.app_name == app_name)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def count_by_time_range(
        self, user_id: UUID, start: datetime, end: datetime,
        event_type: Optional[str] = None, app_name: Optional[str] = None,
    ) -> int:
        query = (
            select(func.count())
            .select_from(ActivityEventModel)
            .where(
                ActivityEventModel.user_id == user_id,
                ActivityEventModel.timestamp >= start,
                ActivityEventModel.timestamp <= end,
            )
        )
        if event_type is not None:
            query = query.where(ActivityEventModel.event_type == event_type)
        if app_name is not None:
            query = query.where(ActivityEventModel.app_name == app_name)

        result = await self.session.execute(query)
        return result.scalar_one()

    async def get_latest(self, user_id: UUID, limit: int) -> list[ActivityEventModel]:
        result = await self.session.execute(
            select(ActivityEventModel)
            .where(ActivityEventModel.user_id == user_id)
            .order_by(ActivityEventModel.timestamp.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def count_events_today(self, user_id: UUID) -> int:
        one_day_ago = datetime.now(timezone.utc) - timedelta(days=1)
        result = await self.session.execute(
            select(func.count()).select_from(ActivityEventModel).where(
                ActivityEventModel.user_id == user_id,
                ActivityEventModel.created_at > one_day_ago,
            )
        )
        return result.scalar_one()
