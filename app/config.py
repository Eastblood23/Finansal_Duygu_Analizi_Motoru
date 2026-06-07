from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    # App
    debug: bool = True
    update_interval_minutes: int = 15

    # PostgreSQL
    postgres_user: str = "finans_user"
    postgres_password: str = "finans_pass"
    postgres_db: str = "finans_db"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # API Keys
    news_api_key: Optional[str] = None
    finnhub_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None

    @property
    def database_url(self) -> str:
        return f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"

    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()
