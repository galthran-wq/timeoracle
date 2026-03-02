import re
from zoneinfo import ZoneInfo

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
from uuid import UUID
from datetime import datetime
from typing import Optional, Union


CATEGORY_TYPES = {"productive", "neutral", "distraction"}
HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


def _validate_timezone(v: str) -> str:
    ZoneInfo(v)
    return v


def _validate_categories(
    v: Optional[dict[str, "CategoryConfig"]],
) -> Optional[dict[str, "CategoryConfig"]]:
    if v is not None:
        if len(v) > 20:
            raise ValueError("Maximum 20 categories allowed")
        for name in v:
            if len(name) > 50 or len(name) == 0:
                raise ValueError(f"Category name must be 1-50 characters: {name!r}")
    return v


def _validate_classification_rules(v: Optional[list[str]]) -> Optional[list[str]]:
    if v is not None:
        if len(v) > 30:
            raise ValueError("Maximum 30 classification rules allowed")
        for rule in v:
            if len(rule) > 500 or len(rule) == 0:
                raise ValueError("Each rule must be 1-500 characters")
    return v


class CategoryConfig(BaseModel):
    color: str
    type: str = "neutral"

    @field_validator("color")
    @classmethod
    def validate_color(cls, v: str) -> str:
        if not HEX_COLOR_RE.match(v):
            raise ValueError(f"Invalid hex color: {v}")
        return v

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        if v not in CATEGORY_TYPES:
            raise ValueError(f"type must be one of {CATEGORY_TYPES}")
        return v


class SessionConfig(BaseModel):
    merge_gap_seconds: int = Field(default=300, ge=1, le=3600)
    min_session_seconds: int = Field(default=5, ge=0, le=600)
    noise_threshold_seconds: int = Field(default=120, ge=0, le=3600)
    llm_model: Optional[str] = None
    enable_cron_generation: Optional[bool] = None
    day_start_hour: int = Field(default=0, ge=0, le=23)
    timezone: str = Field(default="UTC")
    categories: Optional[dict[str, CategoryConfig]] = None
    classification_rules: Optional[list[str]] = None

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, v: str) -> str:
        return _validate_timezone(v)

    @field_validator("categories")
    @classmethod
    def validate_categories(cls, v: Optional[dict[str, CategoryConfig]]) -> Optional[dict[str, CategoryConfig]]:
        return _validate_categories(v)

    @field_validator("classification_rules")
    @classmethod
    def validate_classification_rules(cls, v: Optional[list[str]]) -> Optional[list[str]]:
        return _validate_classification_rules(v)


class SessionConfigUpdate(BaseModel):
    merge_gap_seconds: Optional[int] = Field(default=None, ge=1, le=3600)
    min_session_seconds: Optional[int] = Field(default=None, ge=0, le=600)
    noise_threshold_seconds: Optional[int] = Field(default=None, ge=0, le=3600)
    llm_model: Optional[str] = None
    enable_cron_generation: Optional[bool] = None
    day_start_hour: Optional[int] = Field(default=None, ge=0, le=23)
    timezone: Optional[str] = None
    categories: Optional[dict[str, CategoryConfig]] = None
    classification_rules: Optional[list[str]] = None

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return _validate_timezone(v)
        return v

    @field_validator("categories")
    @classmethod
    def validate_categories(cls, v: Optional[dict[str, CategoryConfig]]) -> Optional[dict[str, CategoryConfig]]:
        return _validate_categories(v)

    @field_validator("classification_rules")
    @classmethod
    def validate_classification_rules(cls, v: Optional[list[str]]) -> Optional[list[str]]:
        return _validate_classification_rules(v)


class UserResponse(BaseModel):
    id: UUID
    email: Optional[str] = None
    is_verified: bool
    is_superuser: bool
    created_at: datetime
    session_config: Optional[SessionConfig] = None

    class Config:
        from_attributes = True


class UserRegisterRequest(BaseModel):
    email: EmailStr
    password: str


class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class CreateUserRequest(BaseModel):
    email: EmailStr
    password: str


class CreateUserResponse(BaseModel):
    success: bool
    message: str
    user: Optional[UserResponse] = None


class DeleteUserRequest(BaseModel):
    user_identifier: Union[UUID, EmailStr]


class DeleteUserResponse(BaseModel):
    success: bool
    message: str 