"""Execution Engine database models."""

from sqlalchemy import String, Float, Integer, Enum as SQLEnum, Boolean, Index, Text, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from typing import Optional, Dict, Any
import enum
from app.models.base import Base, TimestampMixin


class BrokerType(str, enum.Enum):
    """Supported broker types."""
    MT5 = "mt5"
    OANDA = "oanda"
    BINANCE_SPOT = "binance_spot"
    BINANCE_FUTURES = "binance_futures"
    PAPER = "paper"  # Paper trading / simulation


class OrderType(str, enum.Enum):
    """Order types."""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class OrderSide(str, enum.Enum):
    """Order side (buy/sell)."""
    BUY = "buy"
    SELL = "sell"


class OrderStatus(str, enum.Enum):
    """Order lifecycle status."""
    PENDING = "pending"          # Created but not submitted
    SUBMITTED = "submitted"      # Submitted to broker
    ACCEPTED = "accepted"        # Broker accepted
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"            # Completely filled
    CANCELLED = "cancelled"      # User cancelled
    REJECTED = "rejected"        # Broker rejected
    EXPIRED = "expired"          # Order expired
    FAILED = "failed"            # Execution failed


class ExecutionOrder(Base, TimestampMixin):
    """Execution order with full lifecycle tracking."""
    __tablename__ = "execution_orders"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Order identification
    client_order_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    broker_order_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)

    # Broker
    broker_type: Mapped[BrokerType] = mapped_column(
        SQLEnum(BrokerType, native_enum=False),
        nullable=False
    )

    # Order details
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    order_type: Mapped[OrderType] = mapped_column(
        SQLEnum(OrderType, native_enum=False),
        nullable=False
    )
    side: Mapped[OrderSide] = mapped_column(
        SQLEnum(OrderSide, native_enum=False),
        nullable=False
    )
    quantity: Mapped[float] = mapped_column(Float, nullable=False)

    # Prices
    price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # For limit orders
    stop_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # For stop orders

    # Stop loss / Take profit
    stop_loss: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    take_profit: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Status
    status: Mapped[OrderStatus] = mapped_column(
        SQLEnum(OrderStatus, native_enum=False),
        nullable=False,
        default=OrderStatus.PENDING,
        index=True
    )

    # Execution details
    filled_quantity: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    average_fill_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Timestamps
    submitted_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    filled_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Links
    signal_id: Mapped[Optional[int]] = mapped_column(ForeignKey("signals.id"), nullable=True)
    position_id: Mapped[Optional[int]] = mapped_column(ForeignKey("positions.id"), nullable=True)

    # Strategy context
    strategy_name: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    # Error tracking
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Extra data (renamed from metadata to avoid SQLAlchemy conflict)
    extra_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        Index("ix_execution_order_broker_symbol", "broker_type", "symbol"),
    )

    def __repr__(self) -> str:
        return f"<ExecutionOrder {self.client_order_id} {self.side.value} {self.symbol} {self.status.value}>"


class ExecutionLog(Base, TimestampMixin):
    """Audit log for all execution events."""
    __tablename__ = "execution_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("execution_orders.id"), nullable=False, index=True)

    # Event details
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    event_data: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)

    # Status changes
    old_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    new_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Timestamps
    event_time: Mapped[datetime] = mapped_column(nullable=False, index=True)

    # Relationship
    order: Mapped["ExecutionOrder"] = relationship("ExecutionOrder")

    def __repr__(self) -> str:
        return f"<ExecutionLog {self.id} order={self.order_id} {self.event_type}>"


class BrokerConnection(Base, TimestampMixin):
    """Broker connection configuration."""
    __tablename__ = "broker_connections"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    broker_type: Mapped[BrokerType] = mapped_column(
        SQLEnum(BrokerType, native_enum=False),
        unique=True,
        nullable=False,
        index=True
    )

    # Connection details (encrypted in production)
    credentials: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_connected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Health
    last_health_check: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    last_connection_time: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<BrokerConnection {self.broker_type.value} connected={self.is_connected}>"
