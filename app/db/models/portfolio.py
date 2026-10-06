import uuid
from datetime import datetime
from sqlalchemy import String, Numeric, Integer, ForeignKey, CheckConstraint, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from app.db.base import Base, TimestampMixin

class DemoPortfolio(Base, TimestampMixin):
    __tablename__ = "demo_portfolios"
    
    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    cash_balance: Mapped[float] = mapped_column(Numeric(16, 2), nullable=False, default=10000000.00)
    total_pnl: Mapped[float] = mapped_column(Numeric(16, 2), default=0.00)
    
    # Relationship
    transactions: Mapped[list["DemoTransaction"]] = relationship("DemoTransaction", back_populates="portfolio", cascade="all, delete-orphan")
    
    __table_args__ = (
        CheckConstraint("cash_balance >= 0", name="check_positive_balance"),
    )


class DemoTransaction(Base):
    __tablename__ = "demo_transactions"
    
    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    portfolio_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("demo_portfolios.id", ondelete="CASCADE"), nullable=False, index=True)
    stock_symbol: Mapped[str] = mapped_column(String(10), nullable=False)
    action: Mapped[str] = mapped_column(String(4), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    execution_price: Mapped[float] = mapped_column(Numeric(16, 4), nullable=False)
    total_value: Mapped[float] = mapped_column(Numeric(16, 2), nullable=False)
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationship
    portfolio: Mapped["DemoPortfolio"] = relationship("DemoPortfolio", back_populates="transactions")
    
    __table_args__ = (
        CheckConstraint("quantity > 0", name="check_positive_quantity"),
        CheckConstraint("action IN ('BUY', 'SELL')", name="check_valid_action"),
    )