from fastapi import APIRouter
from app.api.v1.endpoints import auth, simulation, social, market_data, tips, ai_insights, alerts, community, portfolio, profile, legal, news, watchlist

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(simulation.router, prefix="/simulation", tags=["Simulation"])
api_router.include_router(social.router, prefix="/social", tags=["Social"])
api_router.include_router(market_data.router, prefix="/market", tags=["Market Data"])
api_router.include_router(tips.router, prefix="/tips", tags=["Tips"])
api_router.include_router(ai_insights.router, prefix="/ai", tags=["AI Insights"])
api_router.include_router(alerts.router, prefix="/alerts", tags=["Price Alerts"])
api_router.include_router(profile.router, prefix="/profile", tags=["Profile"])
api_router.include_router(community.router, prefix="/community", tags=["Community"])
api_router.include_router(portfolio.router, prefix="/portfolio", tags=["Portfolio"])
api_router.include_router(legal.router, prefix="/legal", tags=["Legal"])
api_router.include_router(news.router, prefix="/news", tags=["News"])
api_router.include_router(watchlist.router, prefix="/watchlist", tags=["watchlist"])

@api_router.get("/health")
async def health_check():
    return {"status": "healthy", "service": "StockDaddy API"}