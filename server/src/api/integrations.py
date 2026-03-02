import logging
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth import get_current_user
from src.core.config import settings
from src.core.database import get_postgres_session
from src.models.postgres.users import UserModel
from src.repositories.integrations import IntegrationRepository
from src.schemas.integrations import (
    IntegrationListResponse,
    IntegrationStatus,
    TelegramConnectResponse,
    TelegramDisconnectResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/integrations", tags=["integrations"])

AVAILABLE_PROVIDERS = ["telegram"]
TOKEN_EXPIRY_SECONDS = 600


def get_integration_repository(
    postgres_session: AsyncSession = Depends(get_postgres_session),
) -> IntegrationRepository:
    return IntegrationRepository(postgres_session)


@router.get("/", response_model=IntegrationListResponse)
async def list_integrations(
    current_user: UserModel = Depends(get_current_user),
    repo: IntegrationRepository = Depends(get_integration_repository),
):
    connected = await repo.get_all_for_user(current_user.id)
    connected_map = {i.provider: i for i in connected}

    statuses = []
    for provider in AVAILABLE_PROVIDERS:
        integration = connected_map.get(provider)
        if integration:
            display_name = None
            if integration.credentials:
                username = integration.credentials.get("username")
                first_name = integration.credentials.get("first_name")
                display_name = f"@{username}" if username else first_name
            statuses.append(
                IntegrationStatus(
                    provider=provider,
                    is_connected=True,
                    is_enabled=integration.is_enabled,
                    external_user_id=integration.external_user_id,
                    display_name=display_name,
                    connected_at=integration.connected_at,
                )
            )
        else:
            statuses.append(
                IntegrationStatus(provider=provider, is_connected=False)
            )

    return IntegrationListResponse(integrations=statuses)


@router.post("/telegram/connect", response_model=TelegramConnectResponse)
async def telegram_connect(
    current_user: UserModel = Depends(get_current_user),
    repo: IntegrationRepository = Depends(get_integration_repository),
):
    if not settings.telegram_bot_token or not settings.telegram_bot_username:
        raise HTTPException(status_code=503, detail="Telegram integration not configured")

    existing = await repo.get_by_user_and_provider(current_user.id, "telegram")
    if existing:
        raise HTTPException(status_code=409, detail="Telegram already connected")

    await repo.delete_user_tokens(current_user.id, "telegram")

    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=TOKEN_EXPIRY_SECONDS)
    await repo.create_connect_token(current_user.id, "telegram", token, expires_at)

    deep_link = f"https://t.me/{settings.telegram_bot_username}?start={token}"

    return TelegramConnectResponse(
        deep_link=deep_link,
        token=token,
        expires_in_seconds=TOKEN_EXPIRY_SECONDS,
    )


@router.delete("/telegram/disconnect", response_model=TelegramDisconnectResponse)
async def telegram_disconnect(
    current_user: UserModel = Depends(get_current_user),
    repo: IntegrationRepository = Depends(get_integration_repository),
):
    existing = await repo.get_by_user_and_provider(current_user.id, "telegram")

    deleted = await repo.delete_integration(current_user.id, "telegram")
    await repo.delete_user_tokens(current_user.id, "telegram")

    if deleted and existing and existing.credentials:
        chat_id = existing.credentials.get("chat_id")
        if chat_id and settings.telegram_bot_token:
            try:
                from src.services.telegram import TelegramClient
                tg = TelegramClient()
                await tg.send_message(chat_id, "Your account has been disconnected from digitalgulag.")
            except Exception:
                logger.exception("Failed to send disconnect message to Telegram")

    return TelegramDisconnectResponse(
        success=deleted,
        message="Telegram disconnected" if deleted else "Telegram was not connected",
    )


@router.post("/telegram/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str = Header(None),
    session: AsyncSession = Depends(get_postgres_session),
):
    if not settings.telegram_webhook_secret:
        raise HTTPException(status_code=503, detail="Telegram webhook not configured")
    if x_telegram_bot_api_secret_token != settings.telegram_webhook_secret:
        raise HTTPException(status_code=403, detail="Invalid secret token")

    repo = IntegrationRepository(session)
    update = await request.json()

    message = update.get("message")
    if not message:
        return {"ok": True}

    text = message.get("text", "")
    from_user = message.get("from", {})
    chat = message.get("chat", {})
    telegram_user_id = str(from_user.get("id", ""))
    chat_id = chat.get("id")
    username = from_user.get("username")
    first_name = from_user.get("first_name")

    if not chat_id or not telegram_user_id:
        return {"ok": True}

    from src.services.telegram import TelegramClient
    tg = TelegramClient()

    if text.startswith("/start "):
        token_value = text[7:].strip()
        if not token_value:
            await tg.send_message(chat_id, "Welcome! To connect, use the link from your digitalgulag settings.")
            return {"ok": True}

        token_record = await repo.get_connect_token(token_value)
        if not token_record or token_record.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
            if token_record:
                await repo.delete_connect_token(token_value)
            await tg.send_message(chat_id, "This link has expired. Please generate a new one from your settings.")
            return {"ok": True}

        existing = await repo.get_by_provider_and_external_id("telegram", telegram_user_id)
        if existing and existing.user_id != token_record.user_id:
            await tg.send_message(chat_id, "This Telegram account is already connected to a different user.")
            await repo.delete_connect_token(token_value)
            return {"ok": True}

        await repo.upsert(
            user_id=token_record.user_id,
            provider="telegram",
            external_user_id=telegram_user_id,
            credentials={
                "chat_id": chat_id,
                "username": username,
                "first_name": first_name,
            },
        )
        await repo.delete_connect_token(token_value)

        try:
            await tg.send_message(chat_id, "Connected! Your digitalgulag account is now linked.")
        except Exception:
            logger.exception("Failed to send Telegram connection confirmation")
        return {"ok": True}

    if text == "/start":
        await tg.send_message(chat_id, "Welcome! To connect, use the link from your digitalgulag settings.")
        return {"ok": True}

    await tg.send_message(chat_id, "Bot features coming soon.")
    return {"ok": True}
