import re
import logging
from fastapi import BackgroundTasks
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.social import SocialPost, SocialComment, UserModerationState

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# TIER 1: REGEX SCRUBBING (Instant Rejection)
# --------------------------------------------------------------------------
# Blocks obvious WhatsApp/Telegram drops and high-yield scam phrases.
SCAM_REGEX_PATTERN = re.compile(
    r"(wa\.me|t\.me|joinchat|whatsapp\.com|telegram\.me|"
    r"guaranteed returns|send btc|crypto pump|double your money|"
    r"click here to claim|free naira)",
    re.IGNORECASE
)

def check_regex_scrub(content: str) -> bool:
    """Returns True if the content is clean, False if it contains scam links."""
    return not SCAM_REGEX_PATTERN.search(content)

# --------------------------------------------------------------------------
# TIER 2: AI MODERATION AGENT (Async Shadow-Banning)
# --------------------------------------------------------------------------
async def run_ai_moderation_pipeline(
    post_id: str, 
    user_id: str, 
    content: str, 
    db: AsyncSession
):
    """
    Asynchronous AI Moderation Agent.
    In production, this calls an external LLM webhook (e.g., OpenAI, AWS Comprehend).
    Here, we implement a deterministic heuristic mock to simulate the AI shadow-ban 
    without blocking the API response or requiring external API keys.
    """
    logger.info(f"Running AI moderation on post {post_id} by user {user_id}")
    
    # Mock AI Heuristic: Flag posts containing specific financial advice/scam keywords
    ai_trigger_phrases = [
        "i have a secret strategy", 
        "message me privately", 
        "guaranteed profit", 
        "send me your capital"
    ]
    
    is_flagged_by_ai = any(phrase in content.lower() for phrase in ai_trigger_phrases)
    
    if is_flagged_by_ai:
        # Execute Shadow-Ban: Hide from public, but keep visible to the author
        await db.execute(
            update(SocialPost).where(SocialPost.id == post_id).values(is_visible=False)
        )
        
        # Update user moderation state
        mod_state = await db.execute(
            select(UserModerationState).where(UserModerationState.user_id == user_id)
        )
        state = mod_state.scalar_one_or_none()
        
        if not state:
            state = UserModerationState(
                user_id=user_id, 
                is_shadow_banned=True, 
                shadow_ban_reason="AI flagged for suspicious financial solicitation"
            )
            db.add(state)
        else:
            state.is_shadow_banned = True
            state.shadow_ban_reason = "AI flagged for suspicious financial solicitation"
            
        await db.commit()
        logger.warning(f"Post {post_id} shadow-banned by AI. User {user_id} flagged.")
    else:
        logger.info(f"Post {post_id} passed AI moderation.")