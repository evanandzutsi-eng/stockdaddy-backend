from pydantic import BaseModel, Field
from typing import List

class StockData(BaseModel):
    """
    Represents a single NGX equity, mapped directly from the NGN Market API.
    """
    symbol: str = Field(..., description="NGX Ticker Symbol (e.g., DANGCEM)")
    name: str = Field(..., description="Full company name")
    sector: str = Field("Other", description="NGX Sector classification")
    last_price: float = Field(0.0, description="Current trading price in NGN")
    percent_change: float = Field(0.0, description="Daily percentage change (+/-)")
    volume: int = Field(0, description="Total shares traded today")
    market_cap_billions: float = Field(0.0, description="Market capitalization in billions of NGN")
    
    # Sparkline is optional for now, but keeps the schema ready for future charting
    sparkline: List[float] = Field(default_factory=list, description="Historical price points for mini-charts")

class StockGridResponse(BaseModel):
    """
    The wrapper response sent to the mobile app's Market tab.
    """
    total: int = Field(..., description="Total number of stocks returned")
    data: List[StockData] = Field(..., description="The list of stock objects")