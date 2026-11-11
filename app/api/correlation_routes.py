from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, timedelta, timezone
from app.services.sentiment_service import signed_sentiment_expression
import asyncio

from app.database import get_db
from app.models import NewsItem
from app.services.market_service import fetch_ticker_data, SYMBOLS

router = APIRouter()

# Map ticker symbols to news asset_types
ASSET_TYPE_MAP = {
    "BTC": "CRYPTO",
    "GOLD": "GENERAL",
    "USD_TRY": "GENERAL",
    "BIST100": "GENERAL"
}

@router.get("/{symbol}")
async def get_correlation_data(symbol: str, db: AsyncSession = Depends(get_db)):
    if symbol not in SYMBOLS:
        raise HTTPException(status_code=404, detail="Symbol not supported")
        
    yahoo_symbol = SYMBOLS[symbol]
    asset_type = ASSET_TYPE_MAP.get(symbol, "GENERAL")
    
    # 1. Fetch 30d prices from Yahoo Finance
    market_data = await fetch_ticker_data(symbol, yahoo_symbol)
    
    # 2. Fetch 30d daily sentiment average from Database
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    
    from sqlalchemy import text
    stmt = select(
        func.date_trunc('day', NewsItem.published_at).label('day'),
        func.avg(signed_sentiment_expression()).label('avg_score')
    ).where(
        NewsItem.asset_type == asset_type,
        NewsItem.published_at >= thirty_days_ago
    ).group_by(
        text('day')
    ).order_by(
        text('day')
    )
    
    result = await db.execute(stmt)
    sentiment_rows = result.all()
    
    # Create a lookup dictionary for sentiment: { "YYYY-MM-DD": avg_score }
    sentiment_dict = {}
    for row in sentiment_rows:
        day_str = row.day.strftime("%Y-%m-%d")
        # Ensure it's a float
        sentiment_dict[day_str] = float(row.avg_score) if row.avg_score is not None else None
        
    # 3. Merge data
    # market_data["history"] is [{"timestamp": ..., "price": ...}, ...]
    merged_data = []
    for item in market_data.get("history", []):
        dt = datetime.fromtimestamp(item["timestamp"])
        day_str = dt.strftime("%Y-%m-%d")
        
        merged_data.append({
            "date": day_str,
            "timestamp": item["timestamp"],
            "price": item["price"],
            "sentiment_score": sentiment_dict.get(day_str) # Missing news is not neutral sentiment.
        })
        
    return {
        "symbol": symbol,
        "asset_type": asset_type,
        "data": merged_data
    }
