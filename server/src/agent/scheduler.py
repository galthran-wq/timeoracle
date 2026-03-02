import asyncio
import logging
from datetime import date, datetime, timezone

from src.agent.agent import generate_timeline
from src.core.config import settings
from src.core.database import AsyncSessionLocal
from src.repositories.users import UserRepository
from src.services.day_boundary import logical_date_for_timestamp

logger = logging.getLogger(__name__)


async def cron_generation_loop():
    logger.info("Cron generation loop started")

    while True:
        await asyncio.sleep(3600)

        logger.info("Starting hourly timeline generation")
        try:
            async with AsyncSessionLocal() as session:
                user_repo = UserRepository(session)
                users = await user_repo.get_all()

            for user in users:
                user_cfg = user.session_config or {}
                user_cron = user_cfg.get("enable_cron_generation")
                if user_cron is False:
                    continue
                if user_cron is None and not settings.enable_cron_generation:
                    continue

                try:
                    day_start_hour = user_cfg.get("day_start_hour", 0)
                    day_tz = user_cfg.get("timezone", "UTC")
                    target = logical_date_for_timestamp(
                        datetime.now(timezone.utc), day_start_hour, day_tz,
                    )
                    async with AsyncSessionLocal() as session:
                        await generate_timeline(
                            user_id=user.id,
                            target_date=target,
                            session=session,
                            user_session_config=user.session_config,
                        )
                    logger.info("Generated timeline for user %s", user.id)
                except Exception:
                    logger.exception("Failed to generate timeline for user %s", user.id)

        except Exception:
            logger.exception("Cron generation loop error")
