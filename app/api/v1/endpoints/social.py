from fastapi import APIRouter, Depends, HTTPException
import uuid
import httpx
from app.core.config import settings
from app.schemas.social import TipInitializeRequest, TipInitializeResponse

router = APIRouter()

@router.post("/tips/initialize", response_model=TipInitializeResponse)
async def initialize_tip_payment(payload: TipInitializeRequest):
    """Generates a transaction reference and hands off metadata to frontend for Paystack."""
    
    # 1. Generate unique reference
    reference = f"STOCKDADDY_{uuid.uuid4().hex[:10].upper()}"
    
    # 2. Call Paystack API (Mocked structure for production readiness)
    # In production, replace with actual httpx call to https://api.paystack.co/transaction/initialize
    paystack_payload = {
        "email": "user@example.com", # Fetch from current user profile
        "amount": int(payload.amount_ngn * 100), # Paystack expects amount in kobo
        "reference": reference,
        "metadata": {
            "tier": payload.tier,
            "is_public": payload.is_public_leaderboard
        }
    }
    
    # Mocked Paystack Response
    mock_paystack_response = {
        "status": True,
        "message": "Authorization URL created",
        "data": {
            "authorization_url": f"https://checkout.paystack.com/{reference}",
            "access_code": f"access_{reference}",
            "reference": reference
        }
    }

    if not mock_paystack_response["status"]:
        raise HTTPException(status_code=502, detail="Payment gateway initialization failed.")

    data = mock_paystack_response["data"]
    
    return TipInitializeResponse(
        success=True,
        payment_reference=data["reference"],
        authorization_url=data["authorization_url"],
        access_code=data["access_code"]
    )