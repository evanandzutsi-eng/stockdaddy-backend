import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from pydantic import BaseModel

from app.db.session import get_db
from app.core.deps import get_current_user_id, DEV_USER_ID

router = APIRouter()

class ProfileResponse(BaseModel):
    username: str
    avatar: str
    bio: str

class ProfileUpdate(BaseModel):
    username: str
    avatar: str
    bio: str

def _resolve_user_uuid(current_user_id: str) -> uuid.UUID:
    return uuid.UUID(current_user_id) if current_user_id != DEV_USER_ID else uuid.UUID(DEV_USER_ID)

@router.get("/", response_model=ProfileResponse)
async def get_profile(
    db: AsyncSession = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
):
    try:
        user_uuid = _resolve_user_uuid(current_user_id)
        stmt = text("SELECT username, avatar, bio FROM profiles WHERE user_id = :uid")
        result = await db.execute(stmt, {"uid": user_uuid})
        row = result.first()
        
        if not row:
            # Insert defaults if profile doesn't exist
            insert_stmt = text("""
                INSERT INTO profiles (user_id, username, avatar, bio) 
                VALUES (:uid, 'Anonymous Chairman', '👤', 'NGX Intelligence Trader')
            """)
            await db.execute(insert_stmt, {"uid": user_uuid})
            await db.commit()
            return ProfileResponse(username="Anonymous Chairman", avatar="👤", bio="NGX Intelligence Trader")
            
        return ProfileResponse(username=row.username, avatar=row.avatar, bio=row.bio)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Profile DB Error: {str(e)}")

@router.put("/", response_model=ProfileResponse)
async def update_profile(
    payload: ProfileUpdate, 
    db: AsyncSession = Depends(get_db), 
    current_user_id: str = Depends(get_current_user_id)
):
    try:
        user_uuid = _resolve_user_uuid(current_user_id)
        
        stmt = text("""
            INSERT INTO profiles (user_id, username, avatar, bio, updated_at) 
            VALUES (:uid, :username, :avatar, :bio, NOW())
            ON CONFLICT (user_id) 
            DO UPDATE SET username = :username, avatar = :avatar, bio = :bio, updated_at = NOW()
        """)
        await db.execute(stmt, {
            "uid": user_uuid, 
            "username": payload.username, 
            "avatar": payload.avatar, 
            "bio": payload.bio
        })
        await db.commit()
        
        return ProfileResponse(username=payload.username, avatar=payload.avatar, bio=payload.bio)
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Profile Update Error: {str(e)}")