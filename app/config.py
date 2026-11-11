from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
from pydantic import Field, SecretStr, field_validator
from sqlalchemy.engine import URL

class Settings(BaseSettings):
    # App
    debug: bool = False
    update_interval_minutes: int = Field(default=15, ge=1)
    jwt_secret_key: SecretStr

    @field_validator("jwt_secret_key")
    @classmethod
    def validate_jwt_secret(cls, value: SecretStr) -> SecretStr:
        secret = value.get_secret_value()
        if len(secret) < 32 or secret != secret.strip() or secret.lower().startswith(("change", "your_", "replace")):
            raise ValueError("JWT_SECRET_KEY must be an independent random secret of at least 32 characters")
        return value

    # PostgreSQL
    postgres_user: str = "finans_user"
    postgres_password: SecretStr = Field(min_length=1)
    postgres_db: str = "finans_db"
    postgres_host: str = "localhost"
    postgres_port: int = Field(default=5432, ge=1, le=65535)

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # API Keys
    news_api_key: Optional[str] = None
    finnhub_api_key: Optional[str] = None
    gemini_api_key: Optional[SecretStr] = None
    gemini_model: str = Field(default="gemini-3.6-flash", min_length=1, max_length=200)
    gemini_timeout_seconds: int = Field(default=30, ge=1, le=120)
    gemini_max_output_tokens: int = Field(default=2048, ge=128, le=4096)

    @property
    def database_url(self) -> str:
        return URL.create(
            "postgresql+asyncpg",
            username=self.postgres_user,
            password=self.postgres_password.get_secret_value(),
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        ).render_as_string(hide_password=False)

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", hide_input_in_errors=True)

settings = Settings()
