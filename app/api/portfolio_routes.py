from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete
from pydantic import BaseModel
from typing import List, Dict, Any
from datetime import datetime, timedelta

from app.database import get_db
from app.models import PortfolioItem, NewsItem
from app.auth import get_current_user
from app.services.market_service import get_all_market_data, SYMBOLS

router = APIRouter()

class PortfolioInput(BaseModel):
    symbol: str
    amount: float

class PortfolioResponse(BaseModel):
    symbol: str
    amount: float

ASSET_TYPE_MAP = {
    "BTC": "CRYPTO",
    "GOLD": "GENERAL",
    "USD_TRY": "GENERAL",
    "BIST100": "GENERAL"
}

@router.get("/", response_model=List[PortfolioResponse])
async def get_portfolio(current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    stmt = select(PortfolioItem).where(PortfolioItem.user_id == current_user.id)
    result = await db.execute(stmt)
    items = result.scalars().all()
    return [{"symbol": item.symbol, "amount": item.amount} for item in items]

@router.post("/", response_model=PortfolioResponse)
async def set_portfolio_item(payload: PortfolioInput, current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if payload.symbol not in SYMBOLS:
        raise HTTPException(status_code=400, detail="Desteklenmeyen varlık (symbol).")
    
    if payload.amount < 0:
        raise HTTPException(status_code=400, detail="Miktar 0'dan küçük olamaz.")

    # Check if exists
    stmt = select(PortfolioItem).where(
        PortfolioItem.user_id == current_user.id,
        PortfolioItem.symbol == payload.symbol
    )
    result = await db.execute(stmt)
    item = result.scalars().first()

    if item:
        if payload.amount == 0:
            await db.delete(item)
            await db.commit()
            return {"symbol": payload.symbol, "amount": 0.0}
        else:
            item.amount = payload.amount
    else:
        if payload.amount > 0:
            item = PortfolioItem(user_id=current_user.id, symbol=payload.symbol, amount=payload.amount)
            db.add(item)
        else:
            return {"symbol": payload.symbol, "amount": 0.0}

    await db.commit()
    return {"symbol": payload.symbol, "amount": payload.amount}

@router.delete("/{symbol}")
async def remove_portfolio_item(symbol: str, current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    stmt = delete(PortfolioItem).where(
        PortfolioItem.user_id == current_user.id,
        PortfolioItem.symbol == symbol
    )
    await db.execute(stmt)
    await db.commit()
    return {"status": "ok"}

@router.get("/report")
async def get_portfolio_report(current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    # 1. Fetch user's portfolio
    stmt = select(PortfolioItem).where(PortfolioItem.user_id == current_user.id)
    result = await db.execute(stmt)
    items = result.scalars().all()

    if not items:
        return {
            "total_value_usd": 0.0,
            "risk_score": 0.0,
            "report_text": "Portföyünüz boş. Yapay zeka risk raporu oluşturabilmek için bir varlık ekleyin.",
            "items": []
        }

    # 2. Fetch market data
    market_data = await get_all_market_data()

    total_value_usd = 0.0
    portfolio_details = []

    # Calculate Total Value
    for item in items:
        price = market_data.get(item.symbol, {}).get("price", 0.0)
        
        if item.symbol in ["USD_TRY", "USD/TRY"]:
            value = item.amount # USD_TRY amount is already in USD
        else:
            value = item.amount * price
            
        total_value_usd += value
        portfolio_details.append({
            "symbol": item.symbol,
            "amount": item.amount,
            "price": price,
            "value": value,
            "asset_type": ASSET_TYPE_MAP.get(item.symbol, "GENERAL")
        })

    if total_value_usd == 0:
        return {
            "total_value_usd": 0.0,
            "risk_score": 0.0,
            "report_text": "Portföy değeriniz 0.",
            "items": portfolio_details
        }

    # 3. Fetch sentiment scores for the last 7 days grouped by asset_type
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    sentiment_stmt = select(
        NewsItem.asset_type,
        func.avg(NewsItem.sentiment_score).label('avg_score')
    ).where(
        NewsItem.published_at >= seven_days_ago
    ).group_by(NewsItem.asset_type)

    sent_result = await db.execute(sentiment_stmt)
    sentiment_map = {row.asset_type: float(row.avg_score) for row in sent_result.all()}

    # 4. Calculate Weighted Risk
    weighted_sentiment = 0.0
    dominant_asset = None
    dominant_weight = 0.0

    for detail in portfolio_details:
        weight = detail["value"] / total_value_usd
        sent_score = sentiment_map.get(detail["asset_type"], 0.0)
        weighted_sentiment += (weight * sent_score)
        
        if weight > dominant_weight:
            dominant_weight = weight
            dominant_asset = detail["symbol"]

    # 5. Generate AI Text
    report_text = ""
    trend = "Nötr (Yatay)"
    action = "pozisyonunuzu koruyabilirsiniz."

    if weighted_sentiment < -0.2:
        trend = "Ayı (Düşüş)"
        action = "riskinizi azaltmanızı tavsiye ederiz."
    elif weighted_sentiment > 0.2:
        trend = "Boğa (Yükseliş)"
        action = "kazancınızı maksimize etme fırsatını değerlendirebilirsiniz."

    report_text = f"Portföyünüz ağırlıklı olarak {dominant_asset}'da (Ağırlık: %{int(dominant_weight*100)}). "
    report_text += f"{dominant_asset} ve portföyünüzün genelindeki güncel haber duygu skoru {weighted_sentiment:.2f}. "
    report_text += f"Piyasa riski {trend} eğiliminde, {action}"

    return {
        "total_value_usd": total_value_usd,
        "risk_score": weighted_sentiment,
        "report_text": report_text,
        "items": portfolio_details
    }
