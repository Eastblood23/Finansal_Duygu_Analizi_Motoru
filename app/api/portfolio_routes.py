from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from pydantic import BaseModel, Field
from typing import List

from app.database import get_db
from app.models import PortfolioItem
from app.auth import get_current_user
from app.services.market_service import get_all_market_data, SYMBOLS
from app.services.portfolio_service import build_portfolio_report
from app.services.news_summary_service import portfolio_sentiments

router = APIRouter()

class PortfolioInput(BaseModel):
    symbol: str
    amount: float = Field(ge=0, le=1e15, allow_inf_nan=False)

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
    if payload.symbol == "BIST100" and payload.amount > 0:
        raise HTTPException(status_code=400, detail="BIST100 bir endekstir; portföye doğrudan eklenemez. Mevcut kayıt silinebilir.")
    
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
    result = await db.execute(select(PortfolioItem).where(PortfolioItem.user_id == current_user.id))
    items = result.scalars().all()
    if not items:
        return build_portfolio_report([], {}, {})

    market_data = await get_all_market_data()
    sentiments = await portfolio_sentiments(db)
    return build_portfolio_report(items, market_data, sentiments)
