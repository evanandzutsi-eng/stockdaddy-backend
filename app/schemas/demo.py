from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum

class OrderAction(str, Enum):
    BUY = "BUY"
    SELL = "SELL"

class DemoOrderRequest(BaseModel):
    stock_symbol: str = Field(..., min_length=1, max_length=10)
    action: OrderAction
    quantity: int = Field(..., gt=0)

class DemoOrderResponse(BaseModel):
    success: bool
    message: str
    transaction_id: Optional[str] = None
    new_cash_balance: float
    executed_price: float