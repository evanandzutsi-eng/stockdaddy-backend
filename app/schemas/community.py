from pydantic import BaseModel, Field
from typing import List, Optional
from uuid import UUID
from datetime import datetime

class PostCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=1000)
    image_url: Optional[str] = None
    parent_post_id: Optional[UUID] = None # For reposts

class PostResponse(BaseModel):
    id: UUID
    user_id: UUID
    content: str
    image_url: Optional[str]
    parent_post_id: Optional[UUID]
    likes_count: int = 0
    comments_count: int = 0
    reposts_count: int = 0
    is_liked_by_me: bool = False
    created_at: datetime

class CommentCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=500)
    parent_comment_id: Optional[UUID] = None # For nested replies

class CommentResponse(BaseModel):
    id: UUID
    post_id: UUID
    user_id: UUID
    content: str
    parent_comment_id: Optional[UUID]
    created_at: datetime