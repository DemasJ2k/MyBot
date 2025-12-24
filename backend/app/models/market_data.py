from sqlalchemy import String, Float, Integer, DateTime, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from typing import Optional
from app.models.base import Base, TimestampMixin


class Candle(Base, TimestampMixin):
    """OHLCV candle data normalized from TwelveData."""
    __tablename__ = "candles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    interval: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    open: Mapped[float] = mapped_column(Float, nullable=False)
    high: Mapped[float] = mapped_column(Float, nullable=False)
    low: Mapped[float] = mapped_column(Float, nullable=False)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    source: Mapped[str] = mapped_column(String(50), nullable=False, default="twelvedata")

    __table_args__ = (
        UniqueConstraint("symbol", "interval", "timestamp", name="uq_candle_symbol_interval_time"),
        Index("ix_candle_symbol_interval_timestamp", "symbol", "interval", "timestamp"),
    )

    def __repr__(self) -> str:
        return f"<Candle {self.symbol} {self.interval} {self.timestamp} OHLC={self.open}/{self.high}/{self.low}/{self.close}>"


class Symbol(Base, TimestampMixin):
    """Tradable symbols with metadata."""
    __tablename__ = "symbols"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False)
    exchange: Mapped[str] = mapped_column(String(50), nullable=False)
    mic_code: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    country: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    def __repr__(self) -> str:
        return f"<Symbol {self.symbol} {self.name}>"


class EconomicEvent(Base, TimestampMixin):
    """Economic calendar events from TwelveData."""
    __tablename__ = "economic_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    event_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    country: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    event: Mapped[str] = mapped_column(String(255), nullable=False)
    impact: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    actual: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    forecast: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    previous: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    __table_args__ = (
        Index("ix_economic_event_date", "event_date"),
    )

    def __repr__(self) -> str:
        return f"<EconomicEvent {self.country} {self.event} {self.event_date}>"
