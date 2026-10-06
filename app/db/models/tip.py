import uuid
from typing import Optional
from sqlalchemy import String, Numeric, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from app.db.base import Base, TimestampMixin


class ShowLoveTip(Base, TimestampMixin):
    __tablename__ = "show_love_tips"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # STRICTLY NO FOREIGN KEY HERE
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True, index=True
    )
    
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    amount_ngn: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    tier: Mapped[str] = mapped_column(String(50), nullable=False)
    payment_reference: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    payment_status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    is_public_leaderboard: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)