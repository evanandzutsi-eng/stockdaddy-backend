from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID


class PriceAlertCreate(BaseModel):
    symbol: str = Field(..., max_length=20)
    alert_below: Optional[float] = Field(None, ge=0)
    alert_above: Optional[float] = Field(None, ge=0)
    is_active: bool = True


class PriceAlertResponse(BaseModel):
    id: UUID
    symbol: str
    alert_below: Optional[float]
    alert_above: Optional[float]
    is_active: bool


class PriceAlertUpdate(BaseModel):
    alert_below: Optional[float] = Field(None, ge=0)
    alert_above: Optional[float] = Field(None, ge=0)
    is_active: Optional[bool] = None