import uuid
from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin

class User(TimestampMixin, Base):
    """
    PostgreSQL User Model.
    Enforces the non-custodial, data-only architecture by strictly 
    separating identity from financial assets.
    """
    __tablename__ = "users"

    # Primary Key: UUID4 for security and distributed system compatibility
    id: Mapped[str] = mapped_column(
        String(36), 
        primary_key=True, 
        default=lambda: str(uuid.uuid4()),
        index=True
    )
    
    # Identity & Authentication
    email: Mapped[str] = mapped_column(
        String(255), 
        unique=True, 
        index=True, 
        nullable=False
    )
    hashed_password: Mapped[str] = mapped_column(
        String(255), 
        nullable=False
    )
    
    # Status & Business Rule Gates
    is_active: Mapped[bool] = mapped_column(
        Boolean, 
        default=True, 
        nullable=False
    )
    
    # CRITICAL: Verification Gate for Social Forums
    # Defaults to False. Must be explicitly set to True via KYC integration.
    is_kyc_verified: Mapped[bool] = mapped_column(
        Boolean, 
        default=False, 
        nullable=False
    )