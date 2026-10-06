from datetime import datetime  # <-- Added this import
from sqlalchemy import BigInteger, DateTime, Float, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

class StockTick(Base):
    """
    TimescaleDB Hypertable Model.
    Stores high-frequency NGX tick telemetry.
    
    NOTE: To activate TimescaleDB optimizations, the following SQL must 
    be executed post-migration:
    SELECT create_hypertable('stock_ticks', 'timestamp');
    """
    __tablename__ = "stock_ticks"

    # Composite primary key required for TimescaleDB hypertables
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True, nullable=False
    )
    symbol: Mapped[str] = mapped_column(
        String(10), primary_key=True, nullable=False, index=True
    )

    open_price: Mapped[float] = mapped_column(Float, nullable=False)
    high_price: Mapped[float] = mapped_column(Float, nullable=False)
    low_price: Mapped[float] = mapped_column(Float, nullable=False)
    close_price: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[int] = mapped_column(BigInteger, nullable=False)

    __table_args__ = (
        # TimescaleDB best practice: Index by symbol and time descending
        Index("ix_stock_ticks_symbol_time_desc", "symbol", "timestamp"),
    )