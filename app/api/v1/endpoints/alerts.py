import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from pydantic import BaseModel

from app.db.session import get_db
from app.core.deps import get_current_user_id, DEV_USER_ID

router = APIRouter()

class PriceAlertCreate(BaseModel):
    symbol: str
    alert_below: Optional[float] = None
    alert_above: Optional[float] = None

class PriceAlertResponse(BaseModel):
    id: str
    symbol: str
    alert_below: Optional[float] = None
    alert_above: Optional[float] = None
    is_active: bool

def _resolve_user_uuid(current_user_id: str) -> uuid.UUID:
    return uuid.UUID(current_user_id) if current_user_id != DEV_USER_ID else uuid.UUID(DEV_USER_ID)

@router.get("/", response_model=List[PriceAlertResponse])
async def get_all_alerts(
    db: AsyncSession = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
):
    """Get all active alerts for the current user."""
    try:
        user_uuid = _resolve_user_uuid(current_user_id)
        stmt = text("""
            SELECT id, symbol, alert_below, alert_above, is_active 
            FROM price_alerts 
            WHERE user_id = :uid AND is_active = true
            ORDER BY created_at DESC
        """)
        result = await db.execute(stmt, {"uid": user_uuid})
        rows = result.fetchall()
        
        alerts = []
        for row in rows:
            alerts.append({
                "id": str(row[0]),
                "symbol": row[1],
                "alert_below": float(row[2]) if row[2] else None,
                "alert_above": float(row[3]) if row[3] else None,
                "is_active": row[4]
            })
        return alerts
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch alerts: {str(e)}")

@router.get("/{symbol}", response_model=List[PriceAlertResponse])
async def get_alerts_for_symbol(
    symbol: str,
    db: AsyncSession = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
):
    """Get all active alerts for a specific symbol."""
    try:
        user_uuid = _resolve_user_uuid(current_user_id)
        symbol_upper = symbol.upper().strip()
        stmt = text("""
            SELECT id, symbol, alert_below, alert_above, is_active 
            FROM price_alerts 
            WHERE user_id = :uid AND symbol = :symbol AND is_active = true
            ORDER BY created_at DESC
        """)
        result = await db.execute(stmt, {"uid": user_uuid, "symbol": symbol_upper})
        rows = result.fetchall()
        
        alerts = []
        for row in rows:
            alerts.append({
                "id": str(row[0]),
                "symbol": row[1],
                "alert_below": float(row[2]) if row[2] else None,
                "alert_above": float(row[3]) if row[3] else None,
                "is_active": row[4]
            })
        return alerts
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch alerts for {symbol}: {str(e)}")

@router.post("/", response_model=PriceAlertResponse)
async def create_alert(
    payload: PriceAlertCreate,
    db: AsyncSession = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
):
    """Create or update a price alert."""
    try:
        user_uuid = _resolve_user_uuid(current_user_id)
        symbol_upper = payload.symbol.upper().strip()
        new_id = uuid.uuid4()
        
        # UPSERT: If the user already has an alert for this symbol, update it instead of crashing
        stmt = text("""
            INSERT INTO price_alerts (id, user_id, symbol, alert_below, alert_above, is_active) 
            VALUES (:id, :uid, :symbol, :below, :above, true)
            ON CONFLICT (user_id, symbol) 
            DO UPDATE SET 
                alert_below = EXCLUDED.alert_below, 
                alert_above = EXCLUDED.alert_above, 
                is_active = true,
                updated_at = NOW()
            RETURNING id, symbol, alert_below, alert_above, is_active
        """)
        result = await db.execute(stmt, {
            "id": new_id,
            "uid": user_uuid, 
            "symbol": symbol_upper, 
            "below": payload.alert_below, 
            "above": payload.alert_above
        })
        await db.commit()
        row = result.fetchone()
        
        return {
            "id": str(row[0]),
            "symbol": row[1],
            "alert_below": float(row[2]) if row[2] else None,
            "alert_above": float(row[3]) if row[3] else None,
            "is_active": row[4]
        }
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create alert: {str(e)}")

@router.delete("/{alert_id}")
async def delete_alert(
    alert_id: str,
    db: AsyncSession = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
):
    """Delete a price alert."""
    try:
        user_uuid = _resolve_user_uuid(current_user_id)
        alert_uuid = uuid.UUID(alert_id)
        
        stmt = text("""
            DELETE FROM price_alerts 
            WHERE id = :id AND user_id = :uid
        """)
        await db.execute(stmt, {"id": alert_uuid, "uid": user_uuid})
        await db.commit()
        return {"status": "deleted", "id": alert_id}
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid alert ID format")
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete alert: {str(e)}")