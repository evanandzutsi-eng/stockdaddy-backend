import uuid
from datetime import datetime, timezone
from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    """
    SQLAlchemy 2.0 Declarative Base. 
    All models must inherit from this class to be recognized by the ORM.
    """
    pass

class TimestampMixin:
    """
    Mixin to automatically add created_at and updated_at columns 
    to all database models, ensuring strict audit trails.
    """
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now(),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )