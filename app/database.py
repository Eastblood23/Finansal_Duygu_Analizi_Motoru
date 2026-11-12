from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
import redis.asyncio as redis
from app.config import settings

# SQLAlchemy setup
engine = create_async_engine(
    settings.database_url, echo=settings.debug, pool_timeout=2, pool_recycle=1800,
    connect_args={"timeout": settings.db_timeout_seconds,
                  "command_timeout": settings.db_timeout_seconds,
                  "server_settings": {"statement_timeout": str(int(settings.db_timeout_seconds * 1000)),
                                      "lock_timeout": "1000"}},
)
AsyncSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

Base = declarative_base()

# Redis setup
redis_client = redis.from_url(
    settings.redis_url, encoding="utf-8", decode_responses=True,
    socket_connect_timeout=settings.redis_timeout_seconds,
    socket_timeout=settings.redis_timeout_seconds, retry_on_timeout=False,
)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
