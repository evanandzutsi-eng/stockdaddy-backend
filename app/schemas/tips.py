from pydantic import BaseModel, Field
from enum import Enum
from typing import List, Optional


class TipTier(str, Enum):
    URGENT_2K = "Urgent 2K"
    MALT_AND_SUYA = "Malt & Suya"
    BIG_BOY_FLEX = "Big Boy Flex"
    CUSTOM = "Custom"


class TipInitializeRequest(BaseModel):
    amount_ngn: float = Field(..., ge=100)
    tier: TipTier
    is_public_leaderboard: bool = True
    display_name: Optional[str] = None


class TipInitializeResponse(BaseModel):
    success: bool
    payment_reference: str
    authorization_url: str
    access_code: str


class TipVerifyRequest(BaseModel):
    payment_reference: str


class TipVerifyResponse(BaseModel):
    success: bool
    payment_status: str
    message: str


class LeaderboardEntry(BaseModel):
    rank: int
    display_name: str
    total_tipped: float
    tip_count: int


class LeaderboardResponse(BaseModel):
    podium: List[LeaderboardEntry]
    supporters: List[LeaderboardEntry]