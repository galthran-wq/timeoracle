from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class IntegrationStatus(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    provider: str
    is_connected: bool
    is_enabled: bool = False
    external_user_id: Optional[str] = None
    display_name: Optional[str] = None
    connected_at: Optional[datetime] = None


class IntegrationListResponse(BaseModel):
    integrations: list[IntegrationStatus]


class TelegramConnectResponse(BaseModel):
    deep_link: str
    token: str
    expires_in_seconds: int


class TelegramDisconnectResponse(BaseModel):
    success: bool
    message: str
