from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
import redis.asyncio as redis
from app.config import settings

# SQLAlchemy setup
engine = create_async_engine(settings.database_url, echo=settings.debug)
AsyncSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

Base = declarative_base()

# Redis setup
redis_client = redis.from_url(settings.redis_url, encoding="utf-8", decode_responses=True)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
