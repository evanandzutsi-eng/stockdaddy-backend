import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from pydantic import BaseModel

from app.db.session import get_db
from app.core.deps import get_current_user_id, DEV_USER_ID

router = APIRouter()

class WatchlistResponse(BaseModel):
    symbols: List[str]

class WatchlistItem(BaseModel):
    symbol: str
    added_at: str

def _resolve_user_uuid(current_user_id: str) -> uuid.UUID:
    return uuid.UUID(current_user_id) if current_user_id != DEV_USER_ID else uuid.UUID(DEV_USER_ID)

@router.get("/", response_model=WatchlistResponse)
async def get_watchlist(
    db: AsyncSession = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
):
    """Get all symbols in the current user's watchlist."""
    try:
        user_uuid = _resolve_user_uuid(current_user_id)
        stmt = text("""
            SELECT symbol FROM watchlists 
            WHERE user_id = :uid 
            ORDER BY created_at DESC
        """)
        result = await db.execute(stmt, {"uid": user_uuid})
        rows = result.fetchall()
        return WatchlistResponse(symbols=[row[0] for row in rows])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Watchlist DB Error: {str(e)}")

@router.post("/{symbol}")
async def add_to_watchlist(
    symbol: str,
    db: AsyncSession = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
):
    """Add a symbol to the user's watchlist."""
    try:
        user_uuid = _resolve_user_uuid(current_user_id)
        symbol_upper = symbol.upper().strip()
        
        stmt = text("""
            INSERT INTO watchlists (user_id, symbol) 
            VALUES (:uid, :symbol)
            ON CONFLICT (user_id, symbol) DO NOTHING
        """)
        await db.execute(stmt, {"uid": user_uuid, "symbol": symbol_upper})
        await db.commit()
        return {"status": "added", "symbol": symbol_upper}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to add to watchlist: {str(e)}")

@router.delete("/{symbol}")
async def remove_from_watchlist(
    symbol: str,
    db: AsyncSession = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
):
    """Remove a symbol from the user's watchlist."""
    try:
        user_uuid = _resolve_user_uuid(current_user_id)
        symbol_upper = symbol.upper().strip()
        
        stmt = text("""
            DELETE FROM watchlists 
            WHERE user_id = :uid AND symbol = :symbol
        """)
        await db.execute(stmt, {"uid": user_uuid, "symbol": symbol_upper})
        await db.commit()
        return {"status": "removed", "symbol": symbol_upper}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to remove from watchlist: {str(e)}")