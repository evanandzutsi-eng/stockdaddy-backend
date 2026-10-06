from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from enum import Enum
from typing import List, Optional


class TradeAction(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class TradeExecutionRequest(BaseModel):
    """Client request to execute a virtual trade."""
    stock_symbol: str = Field(
        ..., 
        min_length=2, 
        max_length=10, 
        pattern=r"^[A-Z]+$",
        examples=["GTCO", "DANGCEM", "MTNN"],
        description="NGX stock ticker symbol (uppercase)"
    )
    action: TradeAction
    quantity: int = Field(
        ..., 
        gt=0, 
        le=100_000,
        description="Number of units to trade"
    )


class TradeExecutionResponse(BaseModel):
    """Confirmation payload returned after a successful virtual trade."""
    trade_id: str
    stock_symbol: str
    action: TradeAction
    quantity: int
    execution_price_ngn: float
    total_value_ngn: float
    remaining_cash_balance_ngn: float
    message: str


class HoldingSnapshot(BaseModel):
    """Server-computed snapshot of a single stock position."""
    stock_symbol: str
    quantity: int
    avg_cost_basis_ngn: float
    current_market_price_ngn: float
    unrealized_pnl_ngn: float = Field(description="Server-calculated: (market_price - cost_basis) * qty")
    unrealized_pnl_percentage: float = Field(description="Server-calculated percentage gain/loss")
    total_market_value_ngn: float

    model_config = ConfigDict(from_attributes=True)


class PortfolioValuationResponse(BaseModel):
    """
    Complete portfolio valuation. 
    ALL numbers are pre-computed server-side to minimize client processing.
    """
    user_id: str
    cash_balance_ngn: float
    total_holdings_value_ngn: float
    total_portfolio_value_ngn: float
    total_unrealized_pnl_ngn: float
    total_unrealized_pnl_percentage: float
    total_trade_count: int
    is_demo_graduated: bool
    holdings: List[HoldingSnapshot]


class TradeHistoryEntry(BaseModel):
    """Single entry in the immutable trade audit log."""
    trade_id: str
    stock_symbol: str
    action: TradeAction
    quantity: int
    execution_price_ngn: float
    total_value_ngn: float
    executed_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TradeHistoryResponse(BaseModel):
    """Paginated trade history for the frontend presentation layer."""
    total_records: int
    trades: List[TradeHistoryEntry]