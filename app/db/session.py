import logging
from typing import AsyncGenerator

from redis.asyncio import ConnectionPool, Redis
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.config import settings

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# POSTGRESQL / SUPABASE ASYNC ENGINE
# --------------------------------------------------------------------------
# This configuration is optimized for Supabase beta usage.
#
# Why these settings matter:
#
# 1. NullPool
#    Prevents SQLAlchemy from keeping stale database connections alive.
#    This avoids many Supabase/PgBouncer prepared-statement issues.
#
# 2. statement_cache_size=0
#    Disables asyncpg prepared statement caching.
#    Required when using Supabase transaction pooler or unstable pooled connections.
#
# 3. ssl=True
#    Supabase direct database connections require SSL.
#    asyncpg handles SSL through connect_args, not through sslmode in the URL.
#
# Recommended Supabase connection for beta:
# Use the direct database connection:
#
# db.<project_ref>.supabase.co
# port 5432
#
# Avoid using:
#
# aws-x-region.pooler.supabase.com
# port 6543
#
# unless you specifically need transaction pooling and have configured it properly.
# --------------------------------------------------------------------------

db_url = str(settings.SQLALCHEMY_DATABASE_URI)

engine = create_async_engine(
    db_url,
    echo=settings.DEBUG,
    poolclass=NullPool,
    connect_args={
        "statement_cache_size": 0,
        "ssl": "require",
    },
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# --------------------------------------------------------------------------
# REDIS ASYNC CONNECTION POOL
# --------------------------------------------------------------------------
# Used for caching, rate limiting, and future notification queues.
#
# If Redis/Upstash is unavailable, your app should still continue working
# because most Redis usage should be wrapped in try/except blocks.
# --------------------------------------------------------------------------
redis_pool = ConnectionPool.from_url(
    str(settings.REDIS_URL),
    decode_responses=True,
    max_connections=50,
)

# --------------------------------------------------------------------------
# DEPENDENCY INJECTION FUNCTIONS
# --------------------------------------------------------------------------


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Yields an async database session.

    Ensures the session is properly closed and rolled back in case of
    unhandled exceptions.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            logger.exception(
                "Database session rollback triggered due to unhandled exception."
            )
            raise
        finally:
            await session.close()


async def get_redis() -> Redis:
    """
    Returns an async Redis client connected to the global connection pool.
    """
    return Redis(connection_pool=redis_pool)