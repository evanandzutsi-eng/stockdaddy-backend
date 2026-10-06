import json
import secrets
from typing import Any, List, Optional
from urllib.parse import parse_qsl, quote_plus, urlencode, urlparse, urlunparse

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _sanitize_asyncpg_uri(uri: str) -> str:
    """
    Removes sslmode from the URL because asyncpg uses connect_args={"ssl": True}
    instead of PostgreSQL/libpq-style sslmode query parameters.
    """
    parsed = urlparse(uri)

    if not parsed.query:
        return uri

    query_params = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key.lower() != "sslmode"
    ]

    return urlunparse(parsed._replace(query=urlencode(query_params)))


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_ignore_empty=True,
        case_sensitive=True,
        extra="ignore",
    )

    # =========================================================================
    # CORE APPLICATION
    # =========================================================================
    PROJECT_NAME: str = "StockDaddy API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"

    DEBUG: bool = True
    SECRET_KEY: str = secrets.token_urlsafe(32)

    BACKEND_CORS_ORIGINS: List[str] = []

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Any) -> Any:
        if isinstance(v, str):
            v = v.strip()

            if not v:
                return []

            if v.startswith("["):
                return json.loads(v)

            return [item.strip() for item in v.split(",") if item.strip()]

        return v

    # =========================================================================
    # DATABASE: SUPABASE / POSTGRES
    # =========================================================================
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "postgres"

    SQLALCHEMY_DATABASE_URI: Optional[str] = None

    @field_validator("SQLALCHEMY_DATABASE_URI", mode="before")
    @classmethod
    def assemble_db_connection(cls, v: Optional[str], info: Any) -> str:
        """
        If SQLALCHEMY_DATABASE_URI is provided in .env, use it directly.

        Otherwise, build it from POSTGRES_* variables.

        Important:
        - asyncpg requires postgresql+asyncpg://
        - Do not use sslmode in the URL; SSL is handled in session.py.
        """
        if isinstance(v, str) and v.strip():
            return _sanitize_asyncpg_uri(v.strip())

        user = str(info.data.get("POSTGRES_USER") or "")
        password = quote_plus(str(info.data.get("POSTGRES_PASSWORD") or ""))
        server = str(info.data.get("POSTGRES_SERVER") or "")
        port = str(info.data.get("POSTGRES_PORT") or "5432")
        db = str(info.data.get("POSTGRES_DB") or "postgres")

        return f"postgresql+asyncpg://{user}:{password}@{server}:{port}/{db}"

    # =========================================================================
    # REDIS / UPSTASH
    # =========================================================================
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None

    REDIS_URL: Optional[str] = None

    @field_validator("REDIS_URL", mode="before")
    @classmethod
    def assemble_redis_url(cls, v: Optional[str], info: Any) -> str:
        """
        If REDIS_URL is provided in .env, use it directly.

        Otherwise, build it from REDIS_* variables.
        """
        if isinstance(v, str) and v.strip():
            return v.strip()

        host = str(info.data.get("REDIS_HOST") or "localhost")
        port = str(info.data.get("REDIS_PORT") or "6379")
        db = str(info.data.get("REDIS_DB") or "0")
        password = info.data.get("REDIS_PASSWORD")

        auth = f":{quote_plus(password)}@" if password else ""

        return f"redis://{auth}{host}:{port}/{db}"

    # =========================================================================
    # SUPABASE API KEYS
    # =========================================================================
    SUPABASE_URL: Optional[str] = None
    SUPABASE_PUBLISHABLE_KEY: Optional[str] = None
    SUPABASE_SECRET_KEY: Optional[str] = None
    SUPABASE_JWKS_URL: Optional[str] = None

    # =========================================================================
    # BUSINESS RULES
    # =========================================================================
    DEMO_MODE_ENABLED: bool = True
    DEMO_INITIAL_BALANCE_NGN: float = 10000000.00
    MIN_TRADES_TO_POST: int = 3

    # =========================================================================
    # INTEGRATIONS / SECURITY
    # =========================================================================
    AI_MODERATION_WEBHOOK_URL: Optional[str] = None
    PAYSTACK_SECRET_KEY: str = ""
    TURNSTILE_SECRET_KEY: Optional[str] = None
    SUPABASE_JWT_SECRET: str = ""
    NGN_MARKET_API_KEY: str = ""


settings = Settings()