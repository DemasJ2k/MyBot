"""
Execution Mode Models.

These models manage the three execution modes:
- SIMULATION: Virtual account, no real broker connection
- PAPER: Broker's paper trading account
- LIVE: Real money trading

Safety is the priority - defaults to SIMULATION mode.
"""

from sqlalchemy import String, Float, Integer, Boolean, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
import enum

from app.models.base import Base


class ExecutionMode(str, enum.Enum):
    """
    Execution mode for trading operations.
    
    SIMULATION: Default, safest mode. Uses virtual account.
    PAPER: Uses broker's paper trading account.
    LIVE: Real money trading - requires explicit opt-in.
    """
    SIMULATION = "simulation"
    PAPER = "paper"
    LIVE = "live"


class SimulationAccount(Base):
    """
    Virtual account for simulation mode.
    
    Each user has their own simulation account that tracks:
    - Virtual balance and equity
    - Margin usage
    - Simulation parameters (slippage, latency, etc.)
    """
    __tablename__ = "simulation_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, 
        ForeignKey("users.id"), 
        nullable=False,
        unique=True  # One simulation account per user
    )

    # Account State
    balance: Mapped[float] = mapped_column(Float, nullable=False, default=10000.0)
    equity: Mapped[float] = mapped_column(Float, nullable=False, default=10000.0)
    margin_used: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    margin_available: Mapped[float] = mapped_column(Float, nullable=False, default=10000.0)

    # Configuration
    initial_balance: Mapped[float] = mapped_column(Float, nullable=False, default=10000.0)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")

    # Simulation Parameters
    slippage_pips: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    commission_per_lot: Mapped[float] = mapped_column(Float, nullable=False, default=7.0)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    fill_probability: Mapped[float] = mapped_column(Float, nullable=False, default=0.98)

    # Trading Statistics
    total_trades: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    winning_trades: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_pnl: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # Metadata
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, 
        onupdate=datetime.utcnow, 
        nullable=False
    )
    last_reset_at: Mapped[datetime | None] = mapped_column(nullable=True)

    def reset(self) -> None:
        """Reset account to initial state."""
        self.balance = self.initial_balance
        self.equity = self.initial_balance
        self.margin_used = 0.0
        self.margin_available = self.initial_balance
        self.total_trades = 0
        self.winning_trades = 0
        self.total_pnl = 0.0
        self.last_reset_at = datetime.utcnow()

    def update_equity(self, unrealized_pnl: float) -> None:
        """Update equity based on unrealized P&L."""
        self.equity = self.balance + unrealized_pnl
        self.margin_available = self.equity - self.margin_used

    def record_trade(self, pnl: float, is_winner: bool) -> None:
        """Record completed trade."""
        self.balance += pnl
        self.total_pnl += pnl
        self.total_trades += 1
        if is_winner:
            self.winning_trades += 1
        self.equity = self.balance
        self.margin_available = self.equity - self.margin_used

    @property
    def win_rate(self) -> float:
        """Calculate win rate percentage."""
        if self.total_trades == 0:
            return 0.0
        return (self.winning_trades / self.total_trades) * 100


class ExecutionModeAudit(Base):
    """
    Audit trail for execution mode changes.
    
    Every mode change is logged with full context for:
    - Security compliance
    - User activity tracking
    - Dispute resolution
    """
    __tablename__ = "execution_mode_audit"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)

    # Mode Change
    old_mode: Mapped[str | None] = mapped_column(String(20), nullable=True)
    new_mode: Mapped[str] = mapped_column(String(20), nullable=False)

    # Context
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Safety Checks
    confirmation_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    password_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    had_open_positions: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    positions_cancelled: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, nullable=False)


class SimulationPosition(Base):
    """
    Open position in simulation mode.
    
    Tracks virtual positions separately from live positions.
    """
    __tablename__ = "simulation_positions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    simulation_account_id: Mapped[int] = mapped_column(
        Integer, 
        ForeignKey("simulation_accounts.id"), 
        nullable=False
    )

    # Position Details
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    side: Mapped[str] = mapped_column(String(10), nullable=False)  # "long" or "short"
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    entry_price: Mapped[float] = mapped_column(Float, nullable=False)
    current_price: Mapped[float] = mapped_column(Float, nullable=False)
    
    # Risk Management
    stop_loss: Mapped[float | None] = mapped_column(Float, nullable=True)
    take_profit: Mapped[float | None] = mapped_column(Float, nullable=True)
    
    # P&L
    unrealized_pnl: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    
    # Margin
    margin_required: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # Metadata
    order_id: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    opened_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, 
        onupdate=datetime.utcnow, 
        nullable=False
    )

    def update_price(self, new_price: float) -> None:
        """Update current price and calculate unrealized P&L."""
        self.current_price = new_price
        if self.side == "long":
            self.unrealized_pnl = (new_price - self.entry_price) * self.quantity * 100000
        else:
            self.unrealized_pnl = (self.entry_price - new_price) * self.quantity * 100000

    def check_stop_loss(self) -> bool:
        """Check if stop loss is triggered."""
        if self.stop_loss is None:
            return False
        if self.side == "long":
            return self.current_price <= self.stop_loss
        else:
            return self.current_price >= self.stop_loss

    def check_take_profit(self) -> bool:
        """Check if take profit is triggered."""
        if self.take_profit is None:
            return False
        if self.side == "long":
            return self.current_price >= self.take_profit
        else:
            return self.current_price <= self.take_profit
