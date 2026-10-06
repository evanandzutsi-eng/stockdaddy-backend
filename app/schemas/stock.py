from pydantic import BaseModel, Field
from datetime import datetime
from typing import List

class StockTick(BaseModel):
    """Raw time-series telemetry data point."""
    symbol: str
    timestamp: datetime
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    volume: int

class StockQuote(BaseModel):
    """Aggregated current market quote for presentation."""
    symbol: str
    last_price: float
    change: float
    change_percent: float
    volume: int
    timestamp: datetime