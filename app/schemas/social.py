from pydantic import BaseModel, Field
from enum import Enum

class TipTier(str, Enum):
    URGENT_2K = "Urgent 2K"
    MALT_AND_SUYA = "Malt & Suya"
    BIG_BOY_FLEX = "Big Boy Flex"
    CUSTOM = "Custom"

class TipInitializeRequest(BaseModel):
    amount_ngn: float = Field(..., ge=100)
    tier: TipTier
    is_public_leaderboard: bool = True

class TipInitializeResponse(BaseModel):
    success: bool
    payment_reference: str
    authorization_url: str
    access_code: str