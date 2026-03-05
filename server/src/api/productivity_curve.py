import logging
from collections import Counter, defaultdict
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth import get_current_user
from src.core.database import get_postgres_session
from src.models.postgres.users import UserModel
from src.repositories.productivity_points import ProductivityPointRepository
from src.schemas.productivity_points import (
    AggregatedBucket,
    AggregatedCurveResponse,
    ProductivityCurveResponse,
    ProductivityPointResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/productivity-curve", tags=["productivity-curve"])

MAX_RANGE_DAYS = 90


def get_productivity_point_repository(
    postgres_session: AsyncSession = Depends(get_postgres_session),
) -> ProductivityPointRepository:
    return ProductivityPointRepository(postgres_session)


@router.get("/aggregate", response_model=AggregatedCurveResponse)
async def get_aggregated_productivity_curve(
    start: date = Query(...),
    end: date = Query(...),
    bucket_minutes: int = Query(default=360, ge=10, le=1440),
    current_user: UserModel = Depends(get_current_user),
    repo: ProductivityPointRepository = Depends(get_productivity_point_repository),
):
    if (end - start).days > MAX_RANGE_DAYS:
        raise HTTPException(status_code=400, detail=f"Date range must not exceed {MAX_RANGE_DAYS} days")
    if end < start:
        raise HTTPException(status_code=400, detail="end must be after start")

    all_points = await repo.get_by_date_range(current_user.id, start, end)

    grouped: dict[datetime, list] = defaultdict(list)
    for p in all_points:
        ts = p.interval_start.replace(tzinfo=None) if p.interval_start.tzinfo else p.interval_start
        bucket_key = datetime(
            ts.year, ts.month, ts.day,
            (ts.hour * 60 + ts.minute) // bucket_minutes * bucket_minutes // 60,
            (ts.hour * 60 + ts.minute) // bucket_minutes * bucket_minutes % 60,
        )
        grouped[bucket_key].append(p)

    all_work_scores: list[float] = []
    all_scores: list[float] = []
    buckets = []
    for bucket_start in sorted(grouped.keys()):
        points = grouped[bucket_start]
        prod_scores = [p.productivity_score for p in points if p.productivity_score is not None]
        work_scores = [p.productivity_score for p in points if p.is_work and p.productivity_score is not None]
        work_count = sum(1 for p in points if p.is_work)

        all_scores.extend(prod_scores)
        all_work_scores.extend(work_scores)

        cats = Counter(p.category for p in points if p.category)
        dominant_cat = cats.most_common(1)[0][0] if cats else None
        colors = Counter(p.color for p in points if p.color)
        dominant_color = colors.most_common(1)[0][0] if colors else None

        buckets.append(AggregatedBucket(
            bucket_start=bucket_start.replace(tzinfo=timezone.utc),
            avg_productivity_score=round(sum(prod_scores) / len(prod_scores), 1) if prod_scores else None,
            avg_performance_score=round(sum(work_scores) / len(work_scores), 1) if work_scores else None,
            point_count=len(points),
            work_point_count=work_count,
            dominant_category=dominant_cat,
            dominant_color=dominant_color,
        ))

    return AggregatedCurveResponse(
        start=start,
        end=end,
        bucket_minutes=bucket_minutes,
        buckets=buckets,
        overall_score=round(sum(all_scores) / len(all_scores), 1) if all_scores else None,
        performance_score=round(sum(all_work_scores) / len(all_work_scores), 1) if all_work_scores else None,
    )


@router.get("/{target_date}", response_model=ProductivityCurveResponse)
async def get_productivity_curve(
    target_date: date,
    current_user: UserModel = Depends(get_current_user),
    repo: ProductivityPointRepository = Depends(get_productivity_point_repository),
):
    points = await repo.get_by_date(current_user.id, target_date)

    work_scores = []
    all_scores = []
    work_count = 0
    for p in points:
        if p.productivity_score is not None:
            all_scores.append(p.productivity_score)
        if p.is_work:
            work_count += 1
            if p.productivity_score is not None:
                work_scores.append(p.productivity_score)

    day_score = round(sum(work_scores) / len(work_scores), 1) if work_scores else None
    overall_score = round(sum(all_scores) / len(all_scores), 1) if all_scores else None
    work_minutes = work_count * 10.0

    return ProductivityCurveResponse(
        date=target_date,
        points=[ProductivityPointResponse.model_validate(p) for p in points],
        day_score=day_score,
        overall_score=overall_score,
        work_minutes=work_minutes,
    )


@router.get("", response_model=list[ProductivityCurveResponse])
async def get_productivity_curve_range(
    start: date = Query(...),
    end: date = Query(...),
    current_user: UserModel = Depends(get_current_user),
    repo: ProductivityPointRepository = Depends(get_productivity_point_repository),
):
    if (end - start).days > MAX_RANGE_DAYS:
        raise HTTPException(status_code=400, detail=f"Date range must not exceed {MAX_RANGE_DAYS} days")
    if end < start:
        raise HTTPException(status_code=400, detail="end must be after start")

    all_points = await repo.get_by_date_range(current_user.id, start, end)

    by_date: dict[date, list] = {}
    for p in all_points:
        by_date.setdefault(p.date, []).append(p)

    results = []
    for d in sorted(by_date.keys()):
        points = by_date[d]
        work_scores = []
        all_scores = []
        work_count = 0
        for p in points:
            if p.productivity_score is not None:
                all_scores.append(p.productivity_score)
            if p.is_work:
                work_count += 1
                if p.productivity_score is not None:
                    work_scores.append(p.productivity_score)

        day_score = round(sum(work_scores) / len(work_scores), 1) if work_scores else None
        overall_score = round(sum(all_scores) / len(all_scores), 1) if all_scores else None
        work_minutes = work_count * 10.0

        results.append(ProductivityCurveResponse(
            date=d,
            points=[ProductivityPointResponse.model_validate(p) for p in points],
            day_score=day_score,
            overall_score=overall_score,
            work_minutes=work_minutes,
        ))

    return results
