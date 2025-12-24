"""Risk Engine database models."""

from sqlalchemy import String, Float, Integer, JSON, Enum as SQLEnum, Boolean, Index, Text
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from typing import Optional, Dict, Any
import enum
from app.models.base import Base, TimestampMixin


class RiskDecisionType(str, enum.Enum):
    """Types of risk decisions that can be made."""
    TRADE_APPROVAL = "trade_approval"
    TRADE_REJECTION = "trade_rejection"
    POSITION_CLOSE = "position_close"
    STRATEGY_DISABLE = "strategy_disable"
    EMERGENCY_SHUTDOWN = "emergency_shutdown"
    THROTTLE_ENABLE = "throttle_enable"
    THROTTLE_DISABLE = "throttle_disable"


class RiskDecision(Base, TimestampMixin):
    """Audit log for all risk decisions."""
    __tablename__ = "risk_decisions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    decision_type: Mapped[RiskDecisionType] = mapped_column(
        SQLEnum(RiskDecisionType, native_enum=False),
        nullable=False,
        index=True
    )

    # What was evaluated
    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    subject_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # Signal ID, Position ID, etc.

    # Decision outcome
    approved: Mapped[bool] = mapped_column(Boolean, nullable=False, index=True)
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Risk metrics at decision time
    risk_metrics: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)

    # Limits checked
    limits_checked: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)

    # Severity
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="info")

    # Timestamps
    decision_time: Mapped[datetime] = mapped_column(nullable=False, index=True)

    def __repr__(self) -> str:
        return f"<RiskDecision {self.id} {self.decision_type.value} approved={self.approved}>"


class AccountRiskState(Base, TimestampMixin):
    """Current account risk state tracking."""
    __tablename__ = "account_risk_state"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Account metrics
    account_balance: Mapped[float] = mapped_column(Float, nullable=False)
    peak_balance: Mapped[float] = mapped_column(Float, nullable=False)
    current_drawdown_percent: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # Daily tracking
    daily_pnl: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    daily_loss_percent: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    trades_today: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    trades_this_hour: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Position tracking
    open_positions_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_exposure: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_exposure_percent: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # Risk flags
    emergency_shutdown_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    throttling_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Timestamps
    last_updated: Mapped[datetime] = mapped_column(nullable=False, index=True)
    last_trade_time: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    def __repr__(self) -> str:
        return f"<AccountRiskState balance={self.account_balance} drawdown={self.current_drawdown_percent:.2f}%>"


class StrategyRiskBudget(Base, TimestampMixin):
    """Per-strategy risk budget and performance tracking."""
    __tablename__ = "strategy_risk_budgets"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    strategy_name: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)

    # Budget limits
    max_exposure_percent: Mapped[float] = mapped_column(Float, nullable=False, default=5.0)
    max_daily_loss_percent: Mapped[float] = mapped_column(Float, nullable=False, default=2.0)

    # Current usage
    current_exposure: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    current_exposure_percent: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    daily_pnl: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # Performance metrics
    total_trades: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    winning_trades: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    losing_trades: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_pnl: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # Auto-disable criteria
    consecutive_losses: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_consecutive_losses: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    disabled_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    last_trade_time: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    last_updated: Mapped[datetime] = mapped_column(nullable=False)

    __table_args__ = (
        Index("ix_strategy_risk_budget_strategy_symbol", "strategy_name", "symbol"),
    )

    def __repr__(self) -> str:
        return f"<StrategyRiskBudget {self.strategy_name} {self.symbol} enabled={self.is_enabled}>"
