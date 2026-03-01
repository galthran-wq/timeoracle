from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    date: Optional[date] = None


class GenerateRequest(BaseModel):
    date: date


class GenerateResponse(BaseModel):
    message: str
    chat_id: str
