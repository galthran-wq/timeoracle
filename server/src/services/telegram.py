import logging

import httpx

from src.core.config import settings

logger = logging.getLogger(__name__)

TELEGRAM_API_BASE = "https://api.telegram.org/bot{token}"


class TelegramClient:
    def __init__(self):
        self.token = settings.telegram_bot_token
        self.base_url = TELEGRAM_API_BASE.format(token=self.token)

    async def send_message(self, chat_id: int, text: str, parse_mode: str = "HTML") -> dict:
        chunks = self._split_message(text)
        result = None
        async with httpx.AsyncClient() as client:
            for chunk in chunks:
                response = await client.post(
                    f"{self.base_url}/sendMessage",
                    json={"chat_id": chat_id, "text": chunk, "parse_mode": parse_mode},
                )
                response.raise_for_status()
                result = response.json()
        return result

    async def send_chat_action(self, chat_id: int, action: str = "typing") -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/sendChatAction",
                json={"chat_id": chat_id, "action": action},
            )
            response.raise_for_status()
            return response.json()

    @staticmethod
    def _split_message(text: str, max_length: int = 4096) -> list[str]:
        if len(text) <= max_length:
            return [text]
        chunks = []
        while text:
            if len(text) <= max_length:
                chunks.append(text)
                break
            split_at = text.rfind("\n", 0, max_length)
            if split_at == -1:
                split_at = max_length
            chunks.append(text[:split_at])
            text = text[split_at:].lstrip("\n")
        return chunks

    async def set_webhook(self, url: str, secret_token: str) -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/setWebhook",
                json={"url": url, "secret_token": secret_token},
            )
            response.raise_for_status()
            return response.json()

    async def delete_webhook(self) -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/deleteWebhook",
            )
            response.raise_for_status()
            return response.json()

    async def get_me(self) -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.base_url}/getMe")
            response.raise_for_status()
            return response.json()
