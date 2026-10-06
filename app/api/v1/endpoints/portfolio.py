import uuid
import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, bindparam
from sqlalchemy.dialects.postgresql import JSONB
from pydantic import BaseModel
from typing import Dict, List

from app.db.session import get_db
from app.core.deps import get_current_user_id, DEV_USER_ID

# NEW: Import market data functions for live price calculation
from app.api.v1.endpoints.market_data import fetch_tier_1_ngn_market, fetch_tier_2_mansa_markets, FALLBACK_STOCKS

router = APIRouter()

class PortfolioResponse(BaseModel):
    cash_balance: float
    holdings: Dict[str, int]

class TradeRequest(BaseModel):
    symbol: str
    action: str
    quantity: int
    price: float

# NEW: Leaderboard Response Model
class TraderEntry(BaseModel):
    rank: int
    user_id: str
    username: str
    avatar: str
    net_worth: float
    cash: float
    holdings_value: float

class TraderLeaderboardResponse(BaseModel):
    traders: List[TraderEntry]

def _resolve_user_uuid(current_user_id: str) -> uuid.UUID:
    return uuid.UUID(current_user_id) if current_user_id != DEV_USER_ID else uuid.UUID(DEV_USER_ID)

@router.get("/", response_model=PortfolioResponse)
async def get_portfolio(
    db: AsyncSession = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
):
    try:
        user_uuid = _resolve_user_uuid(current_user_id)
        stmt = text("SELECT cash_balance, holdings FROM portfolios WHERE user_id = :uid")
        result = await db.execute(stmt, {"uid": user_uuid})
        row = result.first()
        
        if not row:
            # Insert using bindparam for safety
            insert_stmt = text("INSERT INTO portfolios (user_id, cash_balance, holdings) VALUES (:uid, 10000000.00, :holdings)")
            insert_stmt = insert_stmt.bindparams(bindparam("holdings", type_=JSONB))
            await db.execute(insert_stmt, {"uid": user_uuid, "holdings": {}})
            await db.commit()
            return PortfolioResponse(cash_balance=10000000.00, holdings={})
            
        holdings = row.holdings
        # asyncpg sometimes returns JSONB as a string, so we safely parse it
        if isinstance(holdings, str):
            holdings = json.loads(holdings)
            
        return PortfolioResponse(cash_balance=float(row.cash_balance), holdings=dict(holdings))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Portfolio DB Error: {str(e)}")

@router.post("/trade", response_model=PortfolioResponse)
async def execute_trade(
    payload: TradeRequest,
    db: AsyncSession = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
):
    try:
        user_uuid = _resolve_user_uuid(current_user_id)
        symbol = payload.symbol.upper()
        price = payload.price
        cost = price * payload.quantity

        stmt = text("SELECT cash_balance, holdings FROM portfolios WHERE user_id = :uid")
        result = await db.execute(stmt, {"uid": user_uuid})
        row = result.first()
        
        if not row:
             raise HTTPException(status_code=404, detail="Portfolio not found")

        cash = float(row.cash_balance)
        holdings = row.holdings
        if isinstance(holdings, str):
            holdings = json.loads(holdings)
        holdings = dict(holdings)

        if payload.action == "BUY":
            if cash < cost:
                raise HTTPException(status_code=400, detail=f"Insufficient funds. Need ₦{cost:,.2f}, have ₦{cash:,.2f}")
            cash -= cost
            holdings[symbol] = holdings.get(symbol, 0) + payload.quantity
            
        elif payload.action == "SELL":
            current_qty = holdings.get(symbol, 0)
            if current_qty < payload.quantity:
                raise HTTPException(status_code=400, detail=f"Insufficient shares. Own {current_qty}, trying to sell {payload.quantity}")
            cash += cost
            holdings[symbol] = current_qty - payload.quantity
            if holdings[symbol] == 0:
                del holdings[symbol]

        # THE BULLETPROOF FIX: Use bindparam with JSONB type instead of raw SQL casting
        update_stmt = text("UPDATE portfolios SET cash_balance = :cash, holdings = :holdings, updated_at = NOW() WHERE user_id = :uid")
        update_stmt = update_stmt.bindparams(bindparam("holdings", type_=JSONB))
        
        await db.execute(update_stmt, {"cash": cash, "holdings": holdings, "uid": user_uuid})
        await db.commit()

        return PortfolioResponse(cash_balance=cash, holdings=holdings)
    except Exception as e:
        if isinstance(e, HTTPException): 
            raise e
        raise HTTPException(status_code=500, detail=f"Trade Error: {str(e)}")

# =========================================================================
# NEW: TOP TRADERS LEADERBOARD ENDPOINT
# =========================================================================
@router.get("/leaderboard", response_model=TraderLeaderboardResponse)
async def get_traders_leaderboard(
    db: AsyncSession = Depends(get_db),
):
    """Get the top 50 traders by real-time Net Worth."""
    try:
        # 1. Get live prices using the cascading fallback chain
        stocks = await fetch_tier_1_ngn_market()
        if not stocks:
            stocks = await fetch_tier_2_mansa_markets()
        if not stocks:
            stocks = FALLBACK_STOCKS
            
        # Build a price map for quick lookups
        price_map = {s['symbol']: s['last_price'] for s in stocks}
        
        # 2. Fetch all portfolios joined with profiles for username and avatar
        stmt = text("""
            SELECT 
                p.user_id, 
                p.cash_balance, 
                p.holdings,
                COALESCE(pr.username, 'Anonymous Chairman') as username,
                COALESCE(pr.avatar, '👤') as avatar
            FROM portfolios p
            LEFT JOIN profiles pr ON p.user_id = pr.user_id
        """)
        result = await db.execute(stmt)
        rows = result.fetchall()
        
        leaderboard = []
        for row in rows:
            user_id = row[0]
            cash = float(row[1])
            
            # Safely parse holdings (handles dict or string JSON)
            holdings = row[2] if isinstance(row[2], dict) else {}
            if isinstance(holdings, str):
                holdings = json.loads(holdings)
                
            username = row[3]
            avatar = row[4]
            
            # 3. Calculate real-time holdings value using live prices
            holdings_value = 0.0
            for symbol, qty in holdings.items():
                price = price_map.get(symbol, 0.0)
                holdings_value += float(qty) * price
                
            net_worth = cash + holdings_value
            
            # Only include users who have interacted with the app
            if net_worth > 0:
                leaderboard.append({
                    "user_id": str(user_id),
                    "username": username,
                    "avatar": avatar,
                    "net_worth": net_worth,
                    "cash": cash,
                    "holdings_value": holdings_value
                })
            
        # 4. Sort by net worth descending and limit to top 50
        leaderboard.sort(key=lambda x: x['net_worth'], reverse=True)
        top_traders = leaderboard[:50]
        
        # 5. Add rank to each trader
        for i, trader in enumerate(top_traders):
            trader['rank'] = i + 1
            
        return TraderLeaderboardResponse(traders=top_traders)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Leaderboard Error: {str(e)}")