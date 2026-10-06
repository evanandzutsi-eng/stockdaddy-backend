import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from pydantic import BaseModel

from app.db.session import get_db
from app.core.deps import get_current_user_id, get_optional_user_id, DEV_USER_ID

router = APIRouter()

# =========================================================================
# PYDANTIC MODELS
# =========================================================================
class PostCreate(BaseModel):
    content: str
    image_url: Optional[str] = None
    parent_post_id: Optional[str] = None

class PostResponse(BaseModel):
    id: str
    user_id: str
    username: str
    avatar: str
    content: str
    image_url: Optional[str] = None
    parent_post_id: Optional[str] = None
    likes_count: int = 0
    comments_count: int = 0
    reposts_count: int = 0
    is_liked_by_me: bool = False
    created_at: str

class CommentCreate(BaseModel):
    content: str
    parent_comment_id: Optional[str] = None

class CommentResponse(BaseModel):
    id: str
    post_id: str
    user_id: str
    content: str
    parent_comment_id: Optional[str] = None
    created_at: str

def _resolve_user_uuid(current_user_id: str) -> uuid.UUID:
    return uuid.UUID(current_user_id) if current_user_id != DEV_USER_ID else uuid.UUID(DEV_USER_ID)

# =========================================================================
# POSTS ENDPOINTS
# =========================================================================
@router.get("/posts", response_model=List[PostResponse])
async def get_posts(
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user_id: str | None = Depends(get_optional_user_id),
):
    try:
        stmt = text("""
            SELECT 
                p.id, p.user_id, p.content, p.image_url, p.parent_post_id, p.created_at,
                COALESCE(pr.username, 'Anonymous Chairman') as username,
                COALESCE(pr.avatar, '👤') as avatar
            FROM posts p
            LEFT JOIN profiles pr ON p.user_id = pr.user_id
            ORDER BY p.created_at DESC
            LIMIT :limit OFFSET :offset
        """)
        
        result = await db.execute(stmt, {"limit": limit, "offset": offset})
        rows = result.mappings().all()
        
        posts = []
        for row in rows:
            post_id = row["id"]
            
            likes_count = await db.scalar(text("SELECT COUNT(*) FROM post_likes WHERE post_id = :pid"), {"pid": post_id}) or 0
            comments_count = await db.scalar(text("SELECT COUNT(*) FROM comments WHERE post_id = :pid"), {"pid": post_id}) or 0
            reposts_count = await db.scalar(text("SELECT COUNT(*) FROM posts WHERE parent_post_id = :pid"), {"pid": post_id}) or 0
            
            is_liked_by_me = False
            if current_user_id:
                user_uuid = _resolve_user_uuid(current_user_id)
                liked = await db.scalar(
                    text("SELECT id FROM post_likes WHERE post_id = :pid AND user_id = :uid LIMIT 1"),
                    {"pid": post_id, "uid": user_uuid}
                )
                is_liked_by_me = liked is not None

            posts.append(PostResponse(
                id=str(row["id"]),
                user_id=str(row["user_id"]),
                username=row["username"],
                avatar=row["avatar"],
                content=row["content"],
                image_url=row["image_url"],
                parent_post_id=str(row["parent_post_id"]) if row["parent_post_id"] else None,
                likes_count=likes_count,
                comments_count=comments_count,
                reposts_count=reposts_count,
                is_liked_by_me=is_liked_by_me,
                created_at=row["created_at"].isoformat() if row["created_at"] else ""
            ))
            
        return posts
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch posts: {str(e)}")


@router.post("/posts", response_model=PostResponse)
async def create_post(
    payload: PostCreate,
    db: AsyncSession = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
):
    try:
        user_uuid = _resolve_user_uuid(current_user_id)
        post_id = uuid.uuid4()
        parent_uuid = uuid.UUID(payload.parent_post_id) if payload.parent_post_id else None

        stmt = text("""
            INSERT INTO posts (id, user_id, content, image_url, parent_post_id) 
            VALUES (:id, :uid, :content, :image_url, :parent_id) 
            RETURNING created_at
        """)
        result = await db.execute(stmt, {
            "id": post_id, "uid": user_uuid, "content": payload.content, 
            "image_url": payload.image_url, "parent_id": parent_uuid
        })
        await db.commit()
        created_at = result.first()[0]

        profile_stmt = text("SELECT username, avatar FROM profiles WHERE user_id = :uid")
        profile_res = await db.execute(profile_stmt, {"uid": user_uuid})
        profile_row = profile_res.first()
        
        username = profile_row.username if profile_row else "Anonymous Chairman"
        avatar = profile_row.avatar if profile_row else "👤"

        return PostResponse(
            id=str(post_id),
            user_id=str(user_uuid),
            username=username,
            avatar=avatar,
            content=payload.content,
            image_url=payload.image_url,
            parent_post_id=payload.parent_post_id,
            likes_count=0,
            comments_count=0,
            reposts_count=0,
            is_liked_by_me=False,
            created_at=created_at.isoformat() if created_at else ""
        )
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create post: {str(e)}")


# =========================================================================
# LIKES ENDPOINTS (Updated paths to include /posts/)
# =========================================================================
@router.post("/posts/{post_id}/like")
async def like_post(
    post_id: str,
    db: AsyncSession = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
):
    try:
        user_uuid = _resolve_user_uuid(current_user_id)
        post_uuid = uuid.UUID(post_id)
        like_id = uuid.uuid4()

        stmt = text("INSERT INTO post_likes (id, post_id, user_id) VALUES (:id, :pid, :uid)")
        await db.execute(stmt, {"id": like_id, "pid": post_uuid, "uid": user_uuid})
        await db.commit()
        return {"status": "liked"}
    except Exception as e:
        await db.rollback()
        if "duplicate key" in str(e).lower() or "unique constraint" in str(e).lower():
            return {"status": "already_liked"}
        raise HTTPException(status_code=500, detail=f"Failed to like post: {str(e)}")

@router.delete("/posts/{post_id}/like")
async def unlike_post(
    post_id: str,
    db: AsyncSession = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
):
    try:
        user_uuid = _resolve_user_uuid(current_user_id)
        post_uuid = uuid.UUID(post_id)

        stmt = text("DELETE FROM post_likes WHERE post_id = :pid AND user_id = :uid")
        await db.execute(stmt, {"pid": post_uuid, "uid": user_uuid})
        await db.commit()
        return {"status": "unliked"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to unlike post: {str(e)}")


# =========================================================================
# COMMENTS ENDPOINTS (Updated paths to include /posts/)
# =========================================================================
@router.get("/posts/{post_id}/comments", response_model=List[CommentResponse])
async def get_comments(
    post_id: str,
    db: AsyncSession = Depends(get_db),
):
    try:
        post_uuid = uuid.UUID(post_id)
        stmt = text("""
            SELECT id, post_id, user_id, content, parent_comment_id, created_at 
            FROM comments WHERE post_id = :pid ORDER BY created_at ASC
        """)
        result = await db.execute(stmt, {"pid": post_uuid})
        rows = result.mappings().all()
        
        return [
            CommentResponse(
                id=str(row["id"]),
                post_id=str(row["post_id"]),
                user_id=str(row["user_id"]),
                content=row["content"],
                parent_comment_id=str(row["parent_comment_id"]) if row["parent_comment_id"] else None,
                created_at=row["created_at"].isoformat() if row["created_at"] else ""
            ) for row in rows
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch comments: {str(e)}")

@router.post("/posts/{post_id}/comments", response_model=CommentResponse)
async def add_comment(
    post_id: str,
    payload: CommentCreate,
    db: AsyncSession = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
):
    try:
        user_uuid = _resolve_user_uuid(current_user_id)
        post_uuid = uuid.UUID(post_id)
        parent_uuid = uuid.UUID(payload.parent_comment_id) if payload.parent_comment_id else None
        comment_id = uuid.uuid4()

        stmt = text("""
            INSERT INTO comments (id, post_id, user_id, content, parent_comment_id) 
            VALUES (:id, :pid, :uid, :content, :parent_id) RETURNING created_at
        """)
        result = await db.execute(stmt, {
            "id": comment_id, "pid": post_uuid, "uid": user_uuid, 
            "content": payload.content, "parent_id": parent_uuid
        })
        await db.commit()
        created_at = result.first()[0]

        return CommentResponse(
            id=str(comment_id),
            post_id=str(post_uuid),
            user_id=str(user_uuid),
            content=payload.content,
            parent_comment_id=payload.parent_comment_id,
            created_at=created_at.isoformat() if created_at else ""
        )
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to add comment: {str(e)}")