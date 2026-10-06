"""
Background Task Definitions.
These tasks are dispatched asynchronously to prevent blocking 
the main FastAPI request/response cycle.
"""
import logging
import httpx
from app.workers.celery_app import celery_app
from app.core.config import settings

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def dispatch_ai_moderation_webhook(self, post_id: str, content: str, user_id: str):
    """
    Dispatches post content to an external AI moderation service 
    for deep contextual analysis beyond the regex tier.
    """
    if not settings.AI_MODERATION_WEBHOOK_URL:
        logger.info(f"AI moderation webhook not configured. Skipping post {post_id}.")
        return {"status": "skipped", "reason": "webhook_not_configured"}

    payload = {
        "post_id": post_id,
        "user_id": user_id,
        "content": content,
        "callback_url": f"{settings.API_V1_STR}/social/moderation-callback",
    }

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                str(settings.AI_MODERATION_WEBHOOK_URL),
                json=payload,
            )
            response.raise_for_status()
            logger.info(f"AI moderation webhook dispatched for post {post_id}")
            return {"status": "dispatched", "post_id": post_id}

    except httpx.HTTPError as exc:
        logger.error(f"AI moderation webhook failed for post {post_id}: {exc}")
        raise self.retry(exc=exc)


@celery_app.task
def invalidate_chart_cache(symbol: str):
    """
    Dispatches a cache purge request to Cloudflare for a specific 
    stock's SVG chart when new tick data arrives.
    """
    logger.info(f"Chart cache invalidation queued for {symbol}")
    # In production, this would call the Cloudflare API to purge 
    # the specific URL: /api/market/chart/{symbol}.svg
    return {"status": "queued", "symbol": symbol}