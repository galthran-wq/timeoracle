import os
import logging
from pydantic_settings import BaseSettings
from typing import Optional

logger = logging.getLogger(__name__)


def get_env_file():
    env = os.getenv("ENV", "development")
    
    if env == "test":
        return ".env.test"
    elif env == "production":
        return ".env.prod"
    else:
        return ".env"


class Settings(BaseSettings):
    app_name: str = "WebApp"
    debug: bool = False
    
    postgres_user: str = "postgres"
    postgres_password: str = "password"
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "webexcel"
    
    secret_key: str = "your-secret-key-change-this-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 24 * 60

    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    moonshotai_api_key: Optional[str] = None
    default_llm_model: str = "moonshotai:kimi-k2.5"
    chat_llm_model: str = "moonshotai:kimi-k2.5"
    enable_cron_generation: bool = False
    enable_logfire: bool = False
    logfire_token: Optional[str] = None

    telegram_bot_token: Optional[str] = None
    telegram_bot_username: Optional[str] = None
    telegram_webhook_secret: Optional[str] = None
    public_base_url: Optional[str] = None
    
    @property
    def postgres_url(self) -> str:
        return f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
    
    class Config:
        env_file = get_env_file()
        case_sensitive = False


settings = Settings()

for _key in ("openai_api_key", "anthropic_api_key", "moonshotai_api_key"):
    _val = getattr(settings, _key, None)
    _env = _key.upper()
    if _val and not os.environ.get(_env):
        os.environ[_env] = _val 