from fastapi import APIRouter, Depends, HTTPException, Request, Query
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Dict, Any

from app.database import get_db
from app.models import NewsItem
from app.limiter import limiter
from datetime import datetime
from sqlalchemy import tuple_
from app.services.news_summary_service import generation
from app.services.cache_service import cached_json

router = APIRouter()

@router.get("/sentiment/latest", response_model=List[Dict[str, Any]])
@limiter.limit("60/minute")
async def get_latest_sentiment(
    request: Request,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    asset_type: Optional[str] = None,
    sentiment_label: Optional[str] = None,
    before_time: Optional[datetime] = None,
    before_id: Optional[int] = Query(None, ge=1),
    db: AsyncSession = Depends(get_db)
):
    """
    Önce Redis önbelleğine bakar, yoksa veritabanından filtrelenmiş haberleri getirir.
    """
    if (before_time is None) != (before_id is None) or (before_time is not None and offset):
        raise HTTPException(status_code=400, detail="Sayfalama için tarih ve kimlik birlikte, offset olmadan verilmelidir.")
    cache_key = f"latest_sentiment_v2_{await generation()}_{limit}_{offset}_{asset_type}_{sentiment_label}_{before_time}_{before_id}"

    async def load_news():
        # 2. Veritabanından çek
        query = select(NewsItem)
        if asset_type:
            query = query.where(NewsItem.asset_type == asset_type)
        if sentiment_label:
            query = query.where(NewsItem.sentiment_label == sentiment_label)
        if before_time is not None:
            query = query.where(tuple_(NewsItem.published_at, NewsItem.id) < tuple_(before_time, before_id))

        page = query.with_only_columns(NewsItem.id).order_by(
            NewsItem.published_at.desc(), NewsItem.id.desc()).offset(offset).limit(limit).subquery()
        query = select(NewsItem).join(page, NewsItem.id == page.c.id).order_by(
            NewsItem.published_at.desc(), NewsItem.id.desc())
        result = await db.execute(query)
        news_items = result.scalars().all()

        response_data = []
        for item in news_items:
            response_data.append({
                "id": item.id,
                "source": item.source,
                "asset_type": item.asset_type,
                "title": item.title,
                "url": item.url,
                "published_at": item.published_at.isoformat() if item.published_at else None,
                "sentiment_label": item.sentiment_label,
                "sentiment_score": item.sentiment_score
            })
        return response_data

    return await cached_json(cache_key, load_news, ttl=60)

from app.services.market_service import get_all_market_data

@router.get("/market/ticker", summary="Anlık Piyasa Verileri")
@limiter.limit("30/minute")
async def get_market_ticker(request: Request):
    """Yahoo Finance üzerinden canlı piyasa verilerini döndürür (60 sn önbellekli)"""
    return await get_all_market_data()
