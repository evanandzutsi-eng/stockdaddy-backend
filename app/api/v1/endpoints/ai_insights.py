import httpx
import urllib.parse
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.redis_cache import get_cached_data, set_cached_data

router = APIRouter()

POLLINATIONS_URL = "https://text.pollinations.ai/"


class AIInsightResponse(BaseModel):
    symbol: str
    insights: list[str]
    source: str


async def _generate_insight(symbol: str) -> list[str]:
    prompt = (
        f"Generate exactly 3 short, professional bullet points (under 15 words each) "
        f"about the Nigerian Exchange Group (NGX) stock '{symbol}'. "
        f"Focus on market sentiment, recent performance, or key metrics. "
        f"Return ONLY the 3 bullet points separated by newlines. No intro or outro text."
    )
    
    # CRITICAL FIX: URL encode the prompt to prevent 502 Bad Gateway from their proxy
    encoded_prompt = urllib.parse.quote(prompt)
    
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(f"{POLLINATIONS_URL}{encoded_prompt}")
        response.raise_for_status()
        raw_text = response.text.strip()
        
    # Parse the response into a list of bullets
    bullets = [line.strip().lstrip('-•* ') for line in raw_text.split('\n') if line.strip()]
    
    # Ensure we return exactly 3 bullets
    return bullets[:3] if len(bullets) >= 3 else [raw_text]


@router.get("/insights/{symbol}", response_model=AIInsightResponse)
async def get_stock_insights(symbol: str):
    symbol = symbol.upper()
    cache_key = f"ai_insight_{symbol}"
    
    # 1. Try to serve from cache
    cached = await get_cached_data(cache_key)
    if cached:
        return cached
    
    # 2. Generate fresh insights via Pollinations
    try:
        insights = await _generate_insight(symbol)
    except Exception as e:
        # GRACEFUL FALLBACK: If Pollinations is down/overloaded, don't crash the app.
        # Return a generic message so the UI still looks good.
        print(f"Pollinations AI failed for {symbol}: {str(e)}")
        insights = [
            "AI service temporarily overloaded.",
            "Market sentiment is currently mixed.",
            "Check back in a few minutes for fresh analysis."
        ]
    
    response = AIInsightResponse(symbol=symbol, insights=insights, source="Pollinations.ai")
    
    # 3. Cache for 1 hour
    await set_cached_data(cache_key, response.model_dump(mode="json"), is_static=False)
    
    return response