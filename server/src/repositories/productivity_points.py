import logging
from abc import ABC, abstractmethod
from datetime import date, datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert

from src.models.postgres.productivity_points import ProductivityPointModel

logger = logging.getLogger(__name__)


class ProductivityPointRepositoryInterface(ABC):
    @abstractmethod
    async def get_by_date(self, user_id: UUID, target_date: date) -> list[ProductivityPointModel]:
        pass

    @abstractmethod
    async def get_by_date_range(
        self, user_id: UUID, start_date: date, end_date: date,
    ) -> list[ProductivityPointModel]:
        pass

    @abstractmethod
    async def bulk_upsert(
        self, user_id: UUID, points: list[dict],
    ) -> int:
        pass

    @abstractmethod
    async def delete_by_date(self, user_id: UUID, target_date: date) -> int:
        pass


class ProductivityPointRepository(ProductivityPointRepositoryInterface):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_date(self, user_id: UUID, target_date: date) -> list[ProductivityPointModel]:
        result = await self.session.execute(
            select(ProductivityPointModel)
            .where(
                ProductivityPointModel.user_id == user_id,
                ProductivityPointModel.date == target_date,
            )
            .order_by(ProductivityPointModel.interval_start.asc())
        )
        return list(result.scalars().all())

    async def get_by_date_range(
        self, user_id: UUID, start_date: date, end_date: date,
    ) -> list[ProductivityPointModel]:
        result = await self.session.execute(
            select(ProductivityPointModel)
            .where(
                ProductivityPointModel.user_id == user_id,
                ProductivityPointModel.date >= start_date,
                ProductivityPointModel.date <= end_date,
            )
            .order_by(ProductivityPointModel.interval_start.asc())
        )
        return list(result.scalars().all())

    async def bulk_upsert(self, user_id: UUID, points: list[dict]) -> int:
        if not points:
            return 0
        try:
            stmt = insert(ProductivityPointModel).values(points)
            stmt = stmt.on_conflict_do_update(
                constraint="uq_productivity_points_user_interval",
                set_={
                    "date": stmt.excluded.date,
                    "focus_score": stmt.excluded.focus_score,
                    "depth": stmt.excluded.depth,
                    "productivity_score": stmt.excluded.productivity_score,
                    "category": stmt.excluded.category,
                    "color": stmt.excluded.color,
                    "is_work": stmt.excluded.is_work,
                    "timeline_entry_id": stmt.excluded.timeline_entry_id,
                },
            )
            result = await self.session.execute(stmt)
            await self.session.commit()
            return result.rowcount
        except Exception:
            await self.session.rollback()
            raise

    async def delete_by_date(self, user_id: UUID, target_date: date) -> int:
        try:
            result = await self.session.execute(
                delete(ProductivityPointModel).where(
                    ProductivityPointModel.user_id == user_id,
                    ProductivityPointModel.date == target_date,
                )
            )
            await self.session.commit()
            return result.rowcount
        except Exception:
            await self.session.rollback()
            raise
