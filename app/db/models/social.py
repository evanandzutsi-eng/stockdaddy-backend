import uuid
from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

class SocialPost(TimestampMixin, Base):
    """
    Stock-specific community post (e.g., $GTCO stream).
    Implements the shadow-ban visibility flag.
    """
    __tablename__ = "social_posts"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    stock_symbol: Mapped[str] = mapped_column(
        String(10), nullable=False, index=True, comment="e.g., GTCO, DANGCEM"
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Shadow-Ban Flag: False means hidden from public, but visible to author
    is_visible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    comments: Mapped[list["SocialComment"]] = relationship(
        back_populates="post", cascade="all, delete-orphan", lazy="selectin"
    )


class SocialComment(TimestampMixin, Base):
    """Comments on stock-specific posts."""
    __tablename__ = "social_comments"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    post_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("social_posts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_visible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    post: Mapped["SocialPost"] = relationship(back_populates="comments")


class UserModerationState(TimestampMixin, Base):
    """
    Tracks the AI moderation state for a user.
    Used to escalate repeat offenders from shadow-bans to hard bans.
    """
    __tablename__ = "user_moderation_states"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    is_shadow_banned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    shadow_ban_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_moderation_check: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )