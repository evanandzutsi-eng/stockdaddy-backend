import httpx
import yfinance as yf
import logging
from fastapi import APIRouter
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

NGN_MARKET_BASE_URL = "https://api.ngnmarket.com/v1"

# Tier 4: Ultimate Hardcoded Fallback (Guaranteed to load)
FALLBACK_STOCKS = [
    {"symbol": "GTCO", "name": "Guaranty Trust Holding Co.", "last_price": 37.50, "percent_change": 1.2, "volume": 1500000, "market_cap_billions": 1100.5, "sector": "Banking"},
    {"symbol": "DANGCEM", "name": "Dangote Cement Plc", "last_price": 1000.00, "percent_change": -0.5, "volume": 850000, "market_cap_billions": 7600.0, "sector": "Industrial Goods"},
    {"symbol": "MTNN", "name": "MTN Nigeria Communications", "last_price": 210.00, "percent_change": 0.8, "volume": 2100000, "market_cap_billions": 4200.0, "sector": "Telecommunications"},
    {"symbol": "BUAFOODS", "name": "BUA Foods Plc", "last_price": 75.00, "percent_change": 2.1, "volume": 500000, "market_cap_billions": 2500.0, "sector": "Consumer Goods"},
    {"symbol": "SEPLAT", "name": "Seplat Energy Plc", "last_price": 16000.00, "percent_change": -1.0, "volume": 120000, "market_cap_billions": 900.0, "sector": "Oil & Gas"},
    {"symbol": "ZENITHBANK", "name": "Zenith Bank Plc", "last_price": 32.00, "percent_change": 0.5, "volume": 3000000, "market_cap_billions": 1000.0, "sector": "Banking"},
]

YAHOO_NGX_MAP = {
    "GTCO": "GTCO.LG", "DANGCEM": "DANGCEM.LG", "MTNN": "MTNN.LG",
    "BUAFOODS": "BUAFOODS.LG", "SEPLAT": "SEPLAT.LG", "ZENITHBANK": "ZENITHBANK.LG",
    "AIRTELAFRI": "AIRTELAFRI.LG", "FBNH": "FBNH.LG", "NESTLE": "NESTLE.LG", "ACCESSCORP": "ACCESSCORP.LG"
}

async def fetch_tier_1_ngn_market() -> list | None:
    """Tier 1: Primary NGN Market API"""
    headers = {}
    if settings.NGN_MARKET_API_KEY:
        headers["Authorization"] = f"Bearer {settings.NGN_MARKET_API_KEY}"

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{NGN_MARKET_BASE_URL}/companies", headers=headers)
            response.raise_for_status()
            data = response.json()
            
            stocks_list = []
            if isinstance(data, dict) and "data" in data and isinstance(data["data"], dict) and "data" in data["data"]:
                stocks_list = data["data"]["data"]
            elif isinstance(data, dict) and "data" in data and isinstance(data["data"], list):
                stocks_list = data["data"]
            elif isinstance(data, list):
                stocks_list = data

            if stocks_list and len(stocks_list) > 0:
                standardized_stocks = []
                for s in stocks_list:
                    standardized_stocks.append({
                        "symbol": s.get("symbol", "UNKNOWN"),
                        "name": s.get("name", "Unknown Stock"),
                        "last_price": float(s.get("price", 0.0)),
                        "percent_change": float(s.get("price_change_percent", 0.0)),
                        "volume": int(s.get("volume", 0) or 0),
                        "market_cap_billions": float(s.get("market_cap", 0) / 1_000_000_000) if s.get("market_cap") else 0.0,
                        "sector": s.get("sector", "Unknown")
                    })
                logger.info(f"✅ Tier 1 (NGN Market) succeeded with {len(standardized_stocks)} stocks.")
                return standardized_stocks
                
            logger.warning("⚠️ Tier 1 returned empty data.")
            return None
    except Exception as e:
        logger.error(f"❌ Tier 1 (NGN Market) failed: {type(e).__name__} - {str(e)}")
        return None

async def fetch_tier_2_mansa_markets() -> list | None:
    """Tier 2: Mansa Markets API Fallback"""
    MANSA_API_URL = "https://mansaapi.com/api/v1/markets/exchanges/NGX/stocks"
    
    headers = {}
    if getattr(settings, "MANSA_API_KEY", None):
        headers["Authorization"] = f"Bearer {settings.MANSA_API_KEY}"

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(MANSA_API_URL, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            # Mansa returns {"stocks": [...], "count": 148}
            stocks_list = []
            if isinstance(data, dict) and "stocks" in data and isinstance(data["stocks"], list):
                stocks_list = data["stocks"]
            elif isinstance(data, list):
                stocks_list = data

            if stocks_list and len(stocks_list) > 0:
                standardized_stocks = []
                for s in stocks_list:
                    # Mansa uses 'ticker' or 'symbol', 'price', 'change_pct'
                    symbol = s.get("symbol") or s.get("ticker", "UNKNOWN")
                    
                    standardized_stocks.append({
                        "symbol": symbol,
                        "name": s.get("name") or s.get("company_name", "Unknown Stock"),
                        "last_price": float(s.get("price") or s.get("last_price", 0.0)),
                        "percent_change": float(s.get("change_pct") or s.get("percent_change", 0.0)),
                        "volume": int(s.get("volume", 0) or 0),
                        "market_cap_billions": float(s.get("market_cap", 0) / 1_000_000_000) if s.get("market_cap") else 0.0,
                        "sector": s.get("sector", "Unknown")
                    })
                logger.info(f"✅ Tier 2 (Mansa Markets) succeeded with {len(standardized_stocks)} stocks.")
                return standardized_stocks
                
            logger.warning("⚠️ Tier 2 (Mansa Markets) returned empty data.")
            return None
    except Exception as e:
        logger.error(f"❌ Tier 2 (Mansa Markets) failed: {type(e).__name__} - {str(e)}")
        return None

def fetch_tier_3_yahoo_finance() -> list | None:
    """Tier 3: Yahoo Finance Fallback (Synchronous, but fast for ~10 stocks)"""
    try:
        logger.info("🔄 Attempting Tier 3 (Yahoo Finance)...")
        stocks = []
        for symbol, yahoo_symbol in YAHOO_NGX_MAP.items():
            try:
                ticker = yf.Ticker(yahoo_symbol)
                info = ticker.info
                if info and 'currentPrice' in info:
                    stocks.append({
                        "symbol": symbol,
                        "name": info.get('shortName', symbol),
                        "last_price": float(info.get('currentPrice', 0.0)),
                        "percent_change": float(info.get('regularMarketChangePercent', 0.0) * 100),
                        "volume": int(info.get('volume', 0)),
                        "market_cap_billions": float(info.get('marketCap', 0) / 1_000_000_000) if info.get('marketCap') else 0.0,
                        "sector": info.get('sector', 'Unknown')
                    })
            except Exception as e:
                logger.warning(f"Yahoo Finance failed for {symbol}: {e}")
                continue 
        
        if stocks and len(stocks) > 0:
            logger.info(f"✅ Tier 3 (Yahoo Finance) succeeded with {len(stocks)} stocks.")
            return stocks
        return None
    except Exception as e:
        logger.error(f"❌ Tier 3 (Yahoo Finance) failed completely: {str(e)}")
        return None

@router.get("/stocks")
async def get_stocks_grid():
    """
    Cascading Fallback Chain for Market Data.
    """
    # 1. Try Primary API
    stocks = await fetch_tier_1_ngn_market()
    
    # 2. If Primary fails, try Tier 2 (Mansa Markets)
    if not stocks:
        stocks = await fetch_tier_2_mansa_markets()
        
    # 3. If Tier 2 fails, try Tier 3 (Yahoo Finance)
    if not stocks:
        stocks = fetch_tier_3_yahoo_finance()
        
    # 4. If ALL APIs fail, use Tier 4 (Hardcoded Fallback)
    if not stocks:
        logger.warning("⚠️ All external APIs failed. Serving Tier 4 Hardcoded Fallback.")
        stocks = FALLBACK_STOCKS

    return {"data": stocks, "total": len(stocks)}