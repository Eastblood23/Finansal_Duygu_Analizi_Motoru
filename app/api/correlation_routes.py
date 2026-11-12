from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone

from app.database import get_db
from app.services.market_service import get_all_market_data, SYMBOLS
from app.services.news_summary_service import daily_sentiments

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
        
    asset_type = ASSET_TYPE_MAP.get(symbol, "GENERAL")
    market_data = (await get_all_market_data())[symbol]
    sentiment_dict = await daily_sentiments(db, asset_type)

    # 3. Merge data
    # market_data["history"] is [{"timestamp": ..., "price": ...}, ...]
    merged_data = []
    for item in market_data.get("history", []):
        dt = datetime.fromtimestamp(item["timestamp"], tz=timezone.utc)
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
