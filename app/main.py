from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import your main router
from app.api.v1.router import api_router

app = FastAPI(
    title="StockDaddy API",
    description="NGX Intelligence Terminal Backend",
    version="1.0.0"
)

# 1. CORS MIDDLEWARE (Must be added before including routers)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allows all local network IPs (like your phone)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. INCLUDE ROUTERS
app.include_router(api_router, prefix="/api/v1")

# 3. Root Health Check
@app.get("/")
async def root():
    return {"message": "StockDaddy API is live. Visit /docs for Swagger UI."}