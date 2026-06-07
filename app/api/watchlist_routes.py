from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from pydantic import BaseModel

from app.database import get_db
from app.models import User, Watchlist
from app.auth import get_current_user

router = APIRouter()

class WatchlistCreate(BaseModel):
    asset_type: str

class WatchlistResponse(BaseModel):
    id: int
    asset_type: str

@router.get("/", response_model=List[WatchlistResponse])
async def get_watchlist(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Watchlist).where(Watchlist.user_id == current_user.id))
    watchlists = result.scalars().all()
    return watchlists

@router.post("/", response_model=WatchlistResponse)
async def add_to_watchlist(item: WatchlistCreate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    # Check if already exists
    result = await db.execute(
        select(Watchlist).where(Watchlist.user_id == current_user.id, Watchlist.asset_type == item.asset_type)
    )
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Bu varlık zaten takip listenizde.")
        
    new_item = Watchlist(user_id=current_user.id, asset_type=item.asset_type)
    db.add(new_item)
    await db.commit()
    await db.refresh(new_item)
    return new_item

@router.delete("/{item_id}")
async def remove_from_watchlist(item_id: int, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Watchlist).where(Watchlist.id == item_id, Watchlist.user_id == current_user.id)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Öğe bulunamadı veya size ait değil.")
        
    await db.delete(item)
    await db.commit()
    return {"message": "Başarıyla silindi"}
