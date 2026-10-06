import uuid

from fastapi import Header, HTTPException

from app.core.config import settings

DEV_USER_ID = "00000000-0000-4000-8000-000000000000"


def _get_bearer_token(authorization: str | None) -> str | None:
    """
    Extracts bearer token from Authorization header.

    Expected format:
    Authorization: Bearer <token>
    """
    if not authorization:
        return None

    parts = authorization.split()

    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None

    token = parts[1].strip()
    return token or None


def _is_valid_uuid(value: str | None) -> bool:
    if not value:
        return False

    try:
        uuid.UUID(value)
        return True
    except (ValueError, TypeError, AttributeError):
        return False


async def get_current_user_id(
    authorization: str | None = Header(None),
) -> str:
    """
    Required authentication for private/user-specific actions.

    Private actions include:
    - portfolio
    - profile save
    - community post
    - comment
    - like
    - repost
    - alerts
    - tips

    Beta behavior:
    - Valid UUID bearer token => use that user.
    - Invalid/missing token + DEBUG=true => fall back to DEV_USER_ID for local testing.
    - Invalid/missing token + DEBUG=false => 401 Unauthorized.
    """
    token = _get_bearer_token(authorization)

    if _is_valid_uuid(token):
        return token  # type: ignore[return-value]

    if settings.DEBUG:
        return DEV_USER_ID

    if token:
        raise HTTPException(status_code=401, detail="Invalid authentication token")

    raise HTTPException(status_code=401, detail="Authentication required")


async def get_optional_user_id(
    authorization: str | None = Header(None),
) -> str | None:
    """
    Optional authentication for public endpoints.

    Public endpoints include:
    - GET /community/posts
    - GET /tips/leaderboard
    - GET /news/feed
    - GET /market/stocks

    If the user has a valid token, return their user ID.
    If not, return None instead of failing.
    """
    token = _get_bearer_token(authorization)

    if _is_valid_uuid(token):
        return token  # type: ignore[return-value]

    return None