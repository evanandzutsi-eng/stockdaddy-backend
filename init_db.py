import asyncio
from app.db.session import engine
from app.db.base import Base
import app.db.models  # This imports all models so Base.metadata knows about them

async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ All database tables created successfully in Supabase!")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(create_tables())