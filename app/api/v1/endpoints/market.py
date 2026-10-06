from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.models.stock import StockTick
from app.schemas.stock import StockTick as StockTickSchema, StockQuote
from app.services.chart_renderer import generate_line_chart_svg

router = APIRouter()

@router.get("/ticks/{symbol}", response_model=list[StockTickSchema])
async def get_stock_ticks(
    symbol: str,
    limit: int = Query(default=100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db)
):
    """Fetches raw time-series telemetry for a specific stock."""
    symbol = symbol.upper()
    result = await db.execute(
        select(StockTick)
        .where(StockTick.symbol == symbol)
        .order_by(desc(StockTick.timestamp))
        .limit(limit)
    )
    ticks = result.scalars().all()
    return [
        StockTickSchema(
            symbol=t.symbol,
            timestamp=t.timestamp,
            open_price=t.open_price,
            high_price=t.high_price,
            low_price=t.low_price,
            close_price=t.close_price,
            volume=t.volume
        ) for t in ticks
    ]

@router.get("/quote/{symbol}", response_model=StockQuote)
async def get_stock_quote(
    symbol: str,
    db: AsyncSession = Depends(get_db)
):
    """Fetches the latest aggregated market quote."""
    symbol = symbol.upper()
    result = await db.execute(
        select(StockTick)
        .where(StockTick.symbol == symbol)
        .order_by(desc(StockTick.timestamp))
        .limit(2)
    )
    ticks = result.scalars().all()
    if not ticks:
        raise HTTPException(status_code=404, detail=f"No market data for {symbol}")
    
    latest = ticks[0]
    prev = ticks[1] if len(ticks) > 1 else latest
    
    change = latest.close_price - prev.close_price
    change_pct = (change / prev.close_price) * 100 if prev.close_price else 0.0
    
    return StockQuote(
        symbol=latest.symbol,
        last_price=latest.close_price,
        change=change,
        change_percent=change_pct,
        volume=latest.volume,
        timestamp=latest.timestamp
    )

@router.get("/chart/{symbol}.svg")
async def get_static_chart(
    symbol: str,
    timeframe: str = Query(default="1D", pattern="^(1D|1W|1M|3M|1Y|ALL)$"),
    db: AsyncSession = Depends(get_db)
):
    """
    Server-side rendered static vector chart.
    Offloads all JavaScript charting execution from low-RAM mobile clients.
    Returns an SVG image directly, heavily cached by Cloudflare/CDN.
    """
    symbol = symbol.upper()
    
    # Map timeframe to data point limits
    limits = {"1D": 100, "1W": 200, "1M": 500, "3M": 1000, "1Y": 2000, "ALL": 5000}
    limit = limits.get(timeframe, 100)
    
    result = await db.execute(
        select(StockTick)
        .where(StockTick.symbol == symbol)
        .order_by(StockTick.timestamp.asc())
        .limit(limit)
    )
    ticks = result.scalars().all()
    
    if not ticks:
        raise HTTPException(status_code=404, detail=f"No data to chart for {symbol}")
        
    timestamps = [t.timestamp for t in ticks]
    prices = [t.close_price for t in ticks]
    
    svg_bytes = generate_line_chart_svg(symbol, timestamps, prices)
    
    return Response(
        content=svg_bytes,
        media_type="image/svg+xml",
        headers={
            "Cache-Control": "public, max-age=300", # Cache for 5 mins
            "X-Content-Type-Options": "nosniff"
        }
    )