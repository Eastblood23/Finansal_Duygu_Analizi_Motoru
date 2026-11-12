"""Idempotent, additive schema initialization; existing rows are never replaced."""
import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from app.config import settings
from app.database import Base
from app import models  # Register all tables.

INDEXES = {
    "ix_news_published_id": "published_at DESC, id DESC",
    "ix_news_asset_published_id": "asset_type, published_at DESC, id DESC",
    "ix_news_label_published_id": "sentiment_label, published_at DESC, id DESC",
    "ix_news_asset_label_published_id": "asset_type, sentiment_label, published_at DESC, id DESC",
}


async def initialize_schema():
    migration_engine = create_async_engine(settings.database_url, connect_args={
        "timeout": 3, "command_timeout": 120,
        "server_settings": {"statement_timeout": "120000", "lock_timeout": "5000"},
    })
    try:
        async with migration_engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with migration_engine.connect() as connection:
            connection = await connection.execution_options(isolation_level="AUTOCOMMIT")
            for name, columns in INDEXES.items():
                valid = (await connection.execute(text(
                    "SELECT indisvalid FROM pg_index WHERE indexrelid = to_regclass(:name)"
                ), {"name": name})).scalar_one_or_none()
                if valid is False:
                    await connection.execute(text(f"DROP INDEX CONCURRENTLY IF EXISTS {name}"))
                await connection.execute(text(
                    f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {name} ON news_items ({columns})"
                ))
    finally:
        await migration_engine.dispose()


if __name__ == "__main__":
    asyncio.run(initialize_schema())
