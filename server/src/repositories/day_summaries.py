import logging
from abc import ABC, abstractmethod
from datetime import date
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.postgres.day_summaries import DaySummaryModel

logger = logging.getLogger(__name__)


class DaySummaryRepositoryInterface(ABC):
    @abstractmethod
    async def get_by_user_and_date(self, user_id: UUID, target_date: date) -> Optional[DaySummaryModel]:
        pass

    @abstractmethod
    async def get_by_date_range(
        self, user_id: UUID, start_date: date, end_date: date,
    ) -> list[DaySummaryModel]:
        pass

    @abstractmethod
    async def upsert(self, user_id: UUID, target_date: date, **metrics) -> DaySummaryModel:
        pass

    @abstractmethod
    async def delete(self, summary: DaySummaryModel) -> None:
        pass


class DaySummaryRepository(DaySummaryRepositoryInterface):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_user_and_date(self, user_id: UUID, target_date: date) -> Optional[DaySummaryModel]:
        result = await self.session.execute(
            select(DaySummaryModel).where(
                DaySummaryModel.user_id == user_id,
                DaySummaryModel.date == target_date,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_date_range(
        self, user_id: UUID, start_date: date, end_date: date,
    ) -> list[DaySummaryModel]:
        result = await self.session.execute(
            select(DaySummaryModel)
            .where(
                DaySummaryModel.user_id == user_id,
                DaySummaryModel.date >= start_date,
                DaySummaryModel.date <= end_date,
            )
            .order_by(DaySummaryModel.date.asc())
        )
        return list(result.scalars().all())

    async def upsert(self, user_id: UUID, target_date: date, **metrics) -> DaySummaryModel:
        try:
            existing = await self.get_by_user_and_date(user_id, target_date)
            if existing:
                for field, value in metrics.items():
                    setattr(existing, field, value)
                await self.session.commit()
                await self.session.refresh(existing)
                return existing

            summary = DaySummaryModel(user_id=user_id, date=target_date, **metrics)
            self.session.add(summary)
            await self.session.commit()
            await self.session.refresh(summary)
            return summary
        except Exception:
            await self.session.rollback()
            raise

    async def delete(self, summary: DaySummaryModel) -> None:
        try:
            await self.session.delete(summary)
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
