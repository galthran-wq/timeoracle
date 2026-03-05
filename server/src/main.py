import asyncio
import logging

from fastapi import FastAPI
from contextlib import asynccontextmanager

from src.core.config import settings
from src.core.database import postgres_engine, Base
from src.core.metrics import MetricsMiddleware, metrics_endpoint
from src.api.users import router as users_router
from src.api.activity import router as activity_router
from src.api.activity_sessions import router as activity_sessions_router
from src.api.timeline import router as timeline_router
from src.api.chat import router as chat_router
from src.api.integrations import router as integrations_router
from src.api.agent_memories import router as agent_memories_router
from src.api.day_summaries import router as day_summaries_router
from src.api.productivity_curve import router as productivity_curve_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.enable_logfire:
        import logfire
        logfire.configure(token=settings.logfire_token)
        logfire.instrument_pydantic_ai()
        logger.info("Logfire instrumentation enabled")

    cron_task = None
    if settings.enable_cron_generation:
        from src.agent.scheduler import cron_generation_loop
        cron_task = asyncio.create_task(cron_generation_loop())
        logger.info("Cron generation loop scheduled")

    if settings.telegram_bot_token and settings.telegram_webhook_secret and settings.public_base_url:
        try:
            from src.services.telegram import TelegramClient
            tg = TelegramClient()
            webhook_url = f"{settings.public_base_url}/api/integrations/telegram/webhook"
            await tg.set_webhook(webhook_url, settings.telegram_webhook_secret)
            logger.info("Telegram webhook configured: %s", webhook_url)
        except Exception:
            logger.exception("Failed to configure Telegram webhook")

    yield
    if cron_task:
        cron_task.cancel()


app = FastAPI(
    title="Web API",
    description="",
    version="1.0.0",
    openapi_version="3.1.0",
    lifespan=lifespan,
)

app.add_middleware(MetricsMiddleware)
app.include_router(users_router)
app.include_router(activity_router)
app.include_router(activity_sessions_router)
app.include_router(timeline_router)
app.include_router(chat_router)
app.include_router(integrations_router)
app.include_router(agent_memories_router)
app.include_router(day_summaries_router)
app.include_router(productivity_curve_router)

@app.get("/")
async def root():
    return {"message": "API is running"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.get("/metrics")
async def get_metrics():
    return await metrics_endpoint()


if __name__ == "__main__":
    import uvicorn
    import logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    uvicorn.run(app, host="0.0.0.0", port=8000) 
