import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db, get_redis
from redis.asyncio import Redis

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# CRYPTOGRAPHIC & AUTH SCHEMES
# --------------------------------------------------------------------------
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")

# --------------------------------------------------------------------------
# PASSWORD HASHING UTILITIES
# --------------------------------------------------------------------------
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

# --------------------------------------------------------------------------
# JWT TOKEN MANAGEMENT
# --------------------------------------------------------------------------
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")

async def get_current_user_id(token: str = Depends(oauth2_scheme)) -> str:
    """
    Extracts and validates the user ID from the JWT. 
    Does not hit the database, ensuring high performance for protected routes.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        return user_id
    except JWTError:
        raise credentials_exception

# --------------------------------------------------------------------------
# BUSINESS RULE ENFORCEMENT DEPENDENCIES
# --------------------------------------------------------------------------
async def verify_social_posting_gate(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis)
) -> str:
    """
    Cybersecurity & Business Rule: Enforces the Verification Gate.
    Users are structurally blocked from posting/commenting in the social forums 
    until they complete KYC and execute a minimum of 3 virtual trades.
    """
    # 1. Check KYC Status (Assuming User model has is_kyc_verified flag)
    # Note: The actual User model import will be resolved in the db/models/user.py step.
    from app.db.models.user import User 
    
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user or not user.is_kyc_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Identity verification (KYC) is required to access community forums."
        )

    # 2. Check Virtual Trade Count
    # We check the persistent simulation portfolio for the trade count.
    # (If in Demo mode, we check the Redis demo state; otherwise, the DB).
    if settings.DEMO_MODE_ENABLED:
        demo_portfolio_raw = await redis.get(f"demo:portfolio:{user_id}")
        if demo_portfolio_raw:
            import json
            portfolio = json.loads(demo_portfolio_raw)
            if portfolio.get("trade_count", 0) < settings.MIN_TRADES_TO_POST:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"You must execute at least {settings.MIN_TRADES_TO_POST} virtual trades to unlock community posting."
                )
    else:
        # Production check against the persistent simulation portfolio
        from app.db.models.portfolio import SimulationPortfolio
        result = await db.execute(
            select(SimulationPortfolio.trade_count).where(SimulationPortfolio.user_id == user_id)
        )
        trade_count = result.scalar_one_or_none() or 0
        if trade_count < settings.MIN_TRADES_TO_POST:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"You must execute at least {settings.MIN_TRADES_TO_POST} virtual trades to unlock community posting."
            )

    return user_id