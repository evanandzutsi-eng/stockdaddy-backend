import hashlib
import re
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.db.session import get_db

router = APIRouter()

CONSENT_VERSION = "1.0"

# IMPORTANT: Change this before public launch.
# Ideally move to .env as CONSENT_HASH_SALT.
CONSENT_HASH_SALT = "stockdaddy-beta-salt-change-me"

# Stable namespace for generating deterministic UUIDs from phone hashes.
USER_NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")


class ConsentRequest(BaseModel):
    phone: str = Field(..., min_length=7, max_length=20)
    email: Optional[str] = Field(None, max_length=120)
    consent_version: str = Field(default=CONSENT_VERSION, max_length=20)


class ConsentResponse(BaseModel):
    success: bool
    consent_recorded: bool
    user_id: str
    auth_token: str
    phone_masked: str
    consent_version: str
    consent_given_at: str


def normalize_nigerian_phone(raw_phone: str) -> str:
    """
    Normalizes Nigerian phone numbers to local format: 08012345678

    Accepts:
    - 08012345678
    - 8012345678
    - +2348012345678
    - 2348012345678
    """
    digits = re.sub(r"\D", "", raw_phone or "")

    if digits.startswith("234"):
        digits = digits[3:]

    if len(digits) == 10 and digits.startswith(("70", "80", "81", "90", "91")):
        digits = "0" + digits

    if len(digits) != 11 or not digits.startswith("0"):
        raise HTTPException(
            status_code=400,
            detail="Enter a valid Nigerian phone number, e.g. 08012345678",
        )

    return digits


def mask_phone(phone: str) -> str:
    # 08012345678 -> 080***5678
    if len(phone) < 7:
        return "***"
    return phone[:3] + "***" + phone[-4:]


def hash_phone(phone: str) -> str:
    return hashlib.sha256(f"{CONSENT_HASH_SALT}:{phone}".encode("utf-8")).hexdigest()


def validate_email(email: Optional[str]) -> None:
    if not email:
        return
    if "@" not in email or "." not in email.split("@")[-1]:
        raise HTTPException(status_code=400, detail="Enter a valid email address or leave it empty.")


@router.post("/consent", response_model=ConsentResponse)
async def record_consent(
    payload: ConsentRequest,
    db: AsyncSession = Depends(get_db),
):
    phone = normalize_nigerian_phone(payload.phone)
    validate_email(payload.email)

    phone_hash = hash_phone(phone)

    # Deterministic user ID for beta auth.
    # Same phone number always maps to same user_id.
    user_uuid = uuid.uuid5(USER_NAMESPACE, phone_hash)
    user_id_str = str(user_uuid)

    consent_stmt = text("""
        INSERT INTO public.user_consents (
            phone_hash,
            email,
            consent_version,
            consent_given_at,
            created_at,
            updated_at
        )
        VALUES (
            :phone_hash,
            :email,
            :consent_version,
            NOW(),
            NOW(),
            NOW()
        )
        ON CONFLICT (phone_hash)
        DO UPDATE SET
            email = EXCLUDED.email,
            consent_version = EXCLUDED.consent_version,
            consent_given_at = NOW(),
            updated_at = NOW()
        RETURNING consent_given_at
    """)

    try:
        result = await db.execute(
            consent_stmt,
            {
                "phone_hash": phone_hash,
                "email": payload.email.lower().strip() if payload.email else None,
                "consent_version": payload.consent_version or CONSENT_VERSION,
            },
        )
        row = result.first()

        # Ensure this user has their own portfolio.
        await db.execute(
            text("""
                INSERT INTO public.portfolios (user_id, cash_balance)
                VALUES (:uid, 10000000.00)
                ON CONFLICT (user_id) DO NOTHING
            """),
            {"uid": user_uuid},
        )

        # Ensure this user has their own profile.
        await db.execute(
            text("""
                INSERT INTO public.profiles (user_id)
                VALUES (:uid)
                ON CONFLICT (user_id) DO NOTHING
            """),
            {"uid": user_uuid},
        )

        await db.commit()
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Consent DB Error: {str(e)}")

    consent_given_at = row.consent_given_at.isoformat() if row and row.consent_given_at else ""

    return ConsentResponse(
        success=True,
        consent_recorded=True,
        user_id=user_id_str,
        auth_token=user_id_str,  # Beta token = user UUID. Replace with proper JWT later.
        phone_masked=mask_phone(phone),
        consent_version=payload.consent_version or CONSENT_VERSION,
        consent_given_at=consent_given_at,
    )