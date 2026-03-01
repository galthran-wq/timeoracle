from pydantic import BaseModel, EmailStr, Field
from uuid import UUID
from datetime import datetime
from typing import Optional, Union


class SessionConfig(BaseModel):
    merge_gap_seconds: int = Field(default=300, ge=1, le=3600)
    min_session_seconds: int = Field(default=5, ge=0, le=600)
    noise_threshold_seconds: int = Field(default=120, ge=0, le=3600)
    llm_model: Optional[str] = None
    enable_cron_generation: Optional[bool] = None


class SessionConfigUpdate(BaseModel):
    merge_gap_seconds: Optional[int] = Field(default=None, ge=1, le=3600)
    min_session_seconds: Optional[int] = Field(default=None, ge=0, le=600)
    noise_threshold_seconds: Optional[int] = Field(default=None, ge=0, le=3600)
    llm_model: Optional[str] = None
    enable_cron_generation: Optional[bool] = None


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