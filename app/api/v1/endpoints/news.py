import re
import hashlib
from typing import List, Optional
from urllib.parse import quote

import httpx
import xml.etree.ElementTree as ET

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import settings
from app.core.redis_cache import get_cached_data, set_cached_data

router = APIRouter()

NGN_MARKET_BASE_URL = "https://api.ngnmarket.com/v1"
NEWS_CACHE_KEY = "stockdaddy_news_feed_v1"
NEWS_CACHE_TTL = 900  # 15 minutes


class NewsItem(BaseModel):
    id: str
    title: str
    summary: str
    url: str
    source: str
    published_at: str


def strip_html(html: Optional[str]) -> str:
    if not html:
        return ""
    clean = re.sub(r"<[^<]+?>", " ", html)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean


def make_id(value: str) -> str:
    return hashlib.md5(value.encode("utf-8")).hexdigest()


def first_value(obj: dict, keys: List[str], default: str = "") -> str:
    for key in keys:
        val = obj.get(key)
        if val:
            return str(val)
    return default


async def fetch_ngn_market_news(limit: int = 20) -> Optional[List[NewsItem]]:
    """
    Attempts to use NGN Market blog/news endpoint.
    If your plan/docs use a different shape, send me a sample JSON and I will map it perfectly.
    """
    if not settings.NGN_MARKET_API_KEY:
        return None

    headers = {"Authorization": f"Bearer {settings.NGN_MARKET_API_KEY}"}

    # Common possible endpoints. We try /blog first.
    candidate_urls = [
        f"{NGN_MARKET_BASE_URL}/blog",
        f"{NGN_MARKET_BASE_URL}/news",
    ]

    for url in candidate_urls:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(url, headers=headers, params={"limit": limit})
                if res.status_code != 200:
                    continue

                payload = res.json()
                data = payload.get("data", {})

                # Support multiple possible response shapes
                items = []
                if isinstance(data, list):
                    items = data
                elif isinstance(data, dict):
                    items = data.get("data") or data.get("items") or data.get("articles") or []

                if not items:
                    continue

                news: List[NewsItem] = []
                for item in items[:limit]:
                    if not isinstance(item, dict):
                        continue

                    title = first_value(item, ["title", "headline", "name"], "Untitled market update")
                    url_link = first_value(item, ["url", "link", "share_url", "permalink"], "")
                    summary = strip_html(first_value(item, ["excerpt", "summary", "description", "content", "body"], ""))
                    source = first_value(item, ["source", "publisher", "author", "site"], "NGN Market")
                    published = first_value(item, ["published_at", "created_at", "date", "timestamp"], "")

                    if not url_link:
                        continue

                    news.append(
                        NewsItem(
                            id=make_id(url_link or title),
                            title=title,
                            summary=summary[:280] if summary else "Tap to read full update.",
                            url=url_link,
                            source=source,
                            published_at=published,
                        )
                    )

                if news:
                    return news

        except Exception:
            continue

    return None


async def fetch_google_news_fallback(limit: int = 20) -> List[NewsItem]:
    """
    Public RSS fallback for Nigerian economy/stock market news.
    """
    query = "NGX OR Nigerian Stock Exchange OR Nigerian economy stock market"
    rss_url = (
        "https://news.google.com/rss/search/"
        f"?q={quote(query)}&hl=en-NG&gl=NG&ceid=NG:en"
    )

    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            res = await client.get(rss_url)
            res.raise_for_status()

        root = ET.fromstring(res.text)
        channel = root.find("channel")
        raw_items = channel.findall("item") if channel is not None else []

        news: List[NewsItem] = []

        for item in raw_items[:limit]:
            title = item.findtext("title") or "Market update"
            link = item.findtext("link") or ""
            description = strip_html(item.findtext("description"))
            pub_date = item.findtext("pubDate") or ""
            source_node = item.find("source")
            source = source_node.text if source_node is not None and source_node.text else "Google News"

            if not link:
                continue

            news.append(
                NewsItem(
                    id=make_id(link),
                    title=title.strip(),
                    summary=description[:280] if description else "Tap to read full update.",
                    url=link,
                    source=source,
                    published_at=pub_date,
                )
            )

        return news

    except Exception:
        return []


@router.get("/feed", response_model=List[NewsItem])
async def get_news_feed(limit: int = 20):
    limit = max(5, min(limit, 50))

    cached = await get_cached_data(NEWS_CACHE_KEY)
    if cached:
        return cached

    news = await fetch_ngn_market_news(limit=limit)

    if not news:
        news = await fetch_google_news_fallback(limit=limit)

    await set_cached_data(NEWS_CACHE_KEY, [n.model_dump(mode="json") for n in news], is_static=False)

    return news