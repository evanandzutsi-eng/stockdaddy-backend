import uuid
import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.db.session import get_db
from app.db.models.tip import ShowLoveTip
from app.schemas.tips import (
    TipInitializeRequest, TipInitializeResponse,
    TipVerifyRequest, TipVerifyResponse,
    LeaderboardEntry, LeaderboardResponse,
)
from app.core.config import settings
from app.core.deps import get_current_user_id, DEV_USER_ID
from app.core.redis_cache import get_cached_data, set_cached_data

router = APIRouter()

PAYSTACK_INIT_URL = "https://api.paystack.co/transaction/initialize"
PAYSTACK_VERIFY_URL = "https://api.paystack.co/transaction/verify/"

TIER_FIXED_AMOUNTS = {"Urgent 2K": 2000.0, "Malt & Suya": 5000.0}
MIN_FLEX_AMOUNT = 10000.0


def _resolve_amount(tier: str, amount: float) -> float:
    if tier in TIER_FIXED_AMOUNTS:
        return TIER_FIXED_AMOUNTS[tier]
    if amount < MIN_FLEX_AMOUNT:
        raise HTTPException(status_code=422, detail="Big Boy Flex and Custom tiers require at least 10,000 Naira.")
    return amount


async def _paystack_initialize(amount_ngn: float, reference: str, metadata: dict):
    headers = {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json",
    }
    payload = {"amount": int(amount_ngn * 100), "reference": reference, "metadata": metadata}
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(PAYSTACK_INIT_URL, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()["data"]
        return data["authorization_url"], data["access_code"]


async def _paystack_verify(reference: str) -> str:
    headers = {"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"}
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(f"{PAYSTACK_VERIFY_URL}{reference}", headers=headers)
        response.raise_for_status()
        return response.json()["data"]["status"]


@router.post("/initialize", response_model=TipInitializeResponse)
async def initialize_tip(
    payload: TipInitializeRequest,
    db: AsyncSession = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
):
    amount = _resolve_amount(payload.tier.value, payload.amount_ngn)
    reference = f"SD_{uuid.uuid4().hex.upper()}"
    display_name = (payload.display_name or "Anonymous Chairman").strip()[:100]

    user_uuid = None
    if current_user_id != DEV_USER_ID:
        try:
            user_uuid = uuid.UUID(current_user_id)
        except ValueError:
            user_uuid = None

    # 1. Create the tip object
    tip = ShowLoveTip(
        user_id=user_uuid,
        display_name=display_name,
        amount_ngn=amount,
        tier=payload.tier.value,
        payment_reference=reference,
        payment_status="pending",
        is_public_leaderboard=payload.is_public_leaderboard,
    )

    # 2. Save to database with strict error catching
    try:
        db.add(tip)
        await db.commit()
    except Exception as e:
        await db.rollback()
        # This will force Swagger UI to show the EXACT database error
        raise HTTPException(status_code=500, detail=f"Database Save Failed: {str(e)}")

    # 3. Handle Paystack Gateway (or Dev Mode fallback)
    auth_url = ""
    access_code = ""
    
    if settings.PAYSTACK_SECRET_KEY:
        try:
            auth_url, access_code = await _paystack_initialize(
                amount, reference, {"tier": payload.tier.value, "display_name": display_name}
            )
        except Exception as gateway_error:
            tip.payment_status = "failed"
            db.add(tip)
            await db.commit()
            raise HTTPException(status_code=502, detail=f"Payment gateway failed: {str(gateway_error)}")
    else:
        # Development mode: no Paystack secret configured, use sandbox checkout URL.
        auth_url = f"https://checkout.paystack.com/{reference}"
        access_code = f"DEV_{reference}"

    return TipInitializeResponse(
        success=True, payment_reference=reference, authorization_url=auth_url, access_code=access_code
    )


@router.post("/verify", response_model=TipVerifyResponse)
async def verify_tip(payload: TipVerifyRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ShowLoveTip).where(ShowLoveTip.payment_reference == payload.payment_reference)
    )
    tip = result.scalars().first()
    if not tip:
        raise HTTPException(status_code=404, detail="Transaction reference not found.")

    if tip.payment_status == "success":
        return TipVerifyResponse(success=True, payment_status="success", message="Tip already confirmed. Thank you!")

    if settings.PAYSTACK_SECRET_KEY:
        try:
            gateway_status = await _paystack_verify(payload.payment_reference)
        except Exception:
            raise HTTPException(status_code=502, detail="Payment gateway verification failed.")
    else:
        # Development mode: simulate gateway confirmation so the loop is testable.
        gateway_status = "success"

    tip.payment_status = gateway_status if gateway_status in ("success", "failed") else "pending"
    await db.commit()

    return TipVerifyResponse(
        success=tip.payment_status == "success",
        payment_status=tip.payment_status,
        message="Tip confirmed. You are on the leaderboard!" if tip.payment_status == "success" else "Payment not successful.",
    )


@router.get("/leaderboard", response_model=LeaderboardResponse)
async def get_leaderboard(db: AsyncSession = Depends(get_db)):
    cache_key = "tips_leaderboard_v1"
    cached = await get_cached_data(cache_key)
    if cached:
        return cached

    stmt = (
        select(
            ShowLoveTip.display_name,
            func.sum(ShowLoveTip.amount_ngn).label("total"),
            func.count(ShowLoveTip.id).label("tips"),
        )
        .where(ShowLoveTip.payment_status == "success", ShowLoveTip.is_public_leaderboard.is_(True))
        .group_by(ShowLoveTip.display_name)
        .order_by(func.sum(ShowLoveTip.amount_ngn).desc())
        .limit(50)
    )
    rows = (await db.execute(stmt)).all()

    entries = [
        LeaderboardEntry(rank=i + 1, display_name=row.display_name, total_tipped=float(row.total), tip_count=row.tips)
        for i, row in enumerate(rows)
    ]
    response = LeaderboardResponse(podium=entries[:3], supporters=entries[3:])
    await set_cached_data(cache_key, response.model_dump(mode="json"))
    return response