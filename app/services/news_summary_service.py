from datetime import datetime, timedelta, timezone
from sqlalchemy import select, func
from app.database import redis_client
from app.models import NewsItem
from app.services.cache_service import cached_json
from app.services.sentiment_service import signed_sentiment_expression


async def generation():
    return await redis_client.get("news:generation") or "0"


async def portfolio_sentiments(db):
    key = "news:summary:7d:v2:" + await generation()
    async def load():
        result = await db.execute(select(
            NewsItem.asset_type, func.avg(signed_sentiment_expression()).label("score"),
        ).where(NewsItem.published_at >= datetime.now(timezone.utc)-timedelta(days=7))
          .group_by(NewsItem.asset_type))
        return {row.asset_type: float(row.score) for row in result.all() if row.score is not None}
    return await cached_json(key, load, ttl=30)


async def daily_sentiments(db, asset_type):
    key = "news:summary:30d:v2:" + asset_type + ":" + await generation()
    async def load():
        day = func.date_trunc("day", NewsItem.published_at)
        result = await db.execute(select(day.label("day"),
            func.avg(signed_sentiment_expression()).label("score"))
            .where(NewsItem.asset_type == asset_type,
                   NewsItem.published_at >= datetime.now(timezone.utc)-timedelta(days=30))
            .group_by(day).order_by(day))
        return {row.day.strftime("%Y-%m-%d"): float(row.score) if row.score is not None else None
                for row in result.all()}
    return await cached_json(key, load, ttl=30)
