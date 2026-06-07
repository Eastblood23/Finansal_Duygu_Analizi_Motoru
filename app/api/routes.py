from fastapi import APIRouter, Depends, HTTPException, Request, Query
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Dict, Any
import json

from app.database import get_db, redis_client
from app.models import NewsItem
from app.limiter import limiter

router = APIRouter()

@router.get("/sentiment/latest", response_model=List[Dict[str, Any]])
@limiter.limit("60/minute")
async def get_latest_sentiment(
    request: Request,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    asset_type: Optional[str] = None,
    sentiment_label: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Önce Redis önbelleğine bakar, yoksa veritabanından filtrelenmiş haberleri getirir.
    """
    cache_key = f"latest_sentiment_{limit}_{offset}_{asset_type}_{sentiment_label}"
    
    # 1. Önbelleği kontrol et
    cached_data = await redis_client.get(cache_key)
    if cached_data:
        return json.loads(cached_data)
        
    # 2. Veritabanından çek
    query = select(NewsItem)
    if asset_type:
        query = query.where(NewsItem.asset_type == asset_type)
    if sentiment_label:
        query = query.where(NewsItem.sentiment_label == sentiment_label)
        
    query = query.order_by(NewsItem.published_at.desc()).offset(offset).limit(limit)
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
        
    # 3. Önbelleğe yaz (60 saniye boyunca geçerli olsun)
    if response_data:
        await redis_client.setex(cache_key, 60, json.dumps(response_data))
        
    return response_data

from app.services.market_service import get_all_market_data

@router.get("/market/ticker", summary="Anlık Piyasa Verileri")
@limiter.limit("30/minute")
async def get_market_ticker(request: Request):
    """Yahoo Finance üzerinden canlı piyasa verilerini döndürür (60 sn önbellekli)"""
    cache_key = "market_ticker_data"
    
    # 1. Önbelleği kontrol et
    cached_data = await redis_client.get(cache_key)
    if cached_data:
        return json.loads(cached_data)
        
    # 2. Önbellek boşsa canlı veri çek
    data = await get_all_market_data()
    
    # 3. 60 saniye boyunca önbellekte tut
    if data:
        await redis_client.setex(cache_key, 60, json.dumps(data))
        
    return data
