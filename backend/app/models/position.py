from sqlalchemy import String, Float, Integer, Enum as SQLEnum, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from typing import Optional, List, TYPE_CHECKING
import enum
from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.signal import Signal


class PositionStatus(str, enum.Enum):
    OPEN = "open"
    CLOSED = "closed"
    PARTIAL = "partial"


class PositionSide(str, enum.Enum):
    LONG = "long"
    SHORT = "short"


class Position(Base, TimestampMixin):
    """Active or historical trading position."""
    __tablename__ = "positions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    strategy_name: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    side: Mapped[PositionSide] = mapped_column(SQLEnum(PositionSide), nullable=False)
    status: Mapped[PositionStatus] = mapped_column(
        SQLEnum(PositionStatus),
        default=PositionStatus.OPEN,
        nullable=False,
        index=True
    )

    # Entry
    entry_price: Mapped[float] = mapped_column(Float, nullable=False)
    position_size: Mapped[float] = mapped_column(Float, nullable=False)  # lots/shares
    entry_time: Mapped[datetime] = mapped_column(nullable=False, index=True)

    # Exit
    exit_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    exit_time: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Risk management
    stop_loss: Mapped[float] = mapped_column(Float, nullable=False)
    take_profit: Mapped[float] = mapped_column(Float, nullable=False)
    trailing_stop: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # P&L
    unrealized_pnl: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    realized_pnl: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Commission and fees
    commission_paid: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # Relationships
    signal: Mapped[Optional["Signal"]] = relationship("Signal", back_populates="position")

    __table_args__ = (
        Index("ix_position_strategy_status", "strategy_name", "status"),
        Index("ix_position_symbol_status", "symbol", "status"),
    )

    def __repr__(self) -> str:
        return f"<Position {self.id} {self.strategy_name} {self.side.value} {self.symbol} {self.position_size} @ {self.entry_price}>"

    def calculate_pnl(self, current_price: float) -> float:
        """Calculate unrealized P&L."""
        if self.side == PositionSide.LONG:
            pnl = (current_price - self.entry_price) * self.position_size
        else:
            pnl = (self.entry_price - current_price) * self.position_size

        return pnl - self.commission_paid
