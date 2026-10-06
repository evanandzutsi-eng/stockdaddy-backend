import httpx
from typing import Optional
from app.core.config import settings

POLLINATIONS_TEXT_URL = "https://text.pollinations.ai/openai"

async def generate_stock_insight(symbol: str, transcript: str) -> Optional[str]:
    """
    Generates a 3-bullet retail insight summary from a corporate transcript 
    using Pollinations AI. Runs asynchronously to prevent thread blocking.
    """
    if not transcript or len(transcript) < 50:
        return None

    system_prompt = """
    You are an elite financial analyst for the Nigerian Exchange (NGX). 
    Your task is to analyze corporate transcripts and generate exactly 3 concise, 
    high-impact bullet points for retail investors. 
    Format: 
    - [Insight 1]
    - [Insight 2]
    - [Insight 3]
    Keep it strictly under 150 words. Focus on earnings, guidance, and market sentiment.
    """

    user_prompt = f"Analyze the following transcript for {symbol}:\n\n{transcript}"

    payload = {
        "model": "openai", # Pollinations routes to best available model
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.4, # Lower temperature for factual financial analysis
        "max_tokens": 200
    }

    headers = {
        "Content-Type": "application/json"
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                POLLINATIONS_TEXT_URL, 
                json=payload, 
                headers=headers
            )
            response.raise_for_status()
            data = response.json()
            
            # Extract the text from the OpenAI-compatible response structure
            if "choices" in data and len(data["choices"]) > 0:
                return data["choices"][0]["message"]["content"]
                
    except httpx.HTTPStatusError as e:
        print(f"Pollinations AI HTTP error: {e.response.status_code}")
    except httpx.RequestError as e:
        print(f"Pollinations AI connection error: {e}")
    except Exception as e:
        print(f"Pollinations AI unexpected error: {e}")

    return None