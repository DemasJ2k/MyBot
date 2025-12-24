"""Journaling and Feedback Loop database models."""

from sqlalchemy import String, Float, Integer, JSON, Enum as SQLEnum, Boolean, Index, Text
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from typing import Optional, Dict, Any
import enum
from app.models.base import Base, TimestampMixin


class TradeSource(str, enum.Enum):
    """Source of a trade entry."""
    BACKTEST = "backtest"
    LIVE = "live"
    PAPER = "paper"


class JournalEntry(Base, TimestampMixin):
    """
    Immutable trade journal entry.

    Records complete trade context for learning and analysis.
    This is the SINGLE SOURCE OF TRUTH for performance analysis.
    """
    __tablename__ = "journal_entries"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    entry_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)

    # Trade source
    source: Mapped[TradeSource] = mapped_column(
        SQLEnum(TradeSource, native_enum=False),
        nullable=False,
        index=True
    )

    # Strategy context
    strategy_name: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    strategy_config: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)

    # Symbol and timeframe
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False)

    # Trade details
    side: Mapped[str] = mapped_column(String(10), nullable=False)  # long/short
    entry_price: Mapped[float] = mapped_column(Float, nullable=False)
    exit_price: Mapped[float] = mapped_column(Float, nullable=False)
    position_size: Mapped[float] = mapped_column(Float, nullable=False)

    # Risk parameters
    stop_loss: Mapped[float] = mapped_column(Float, nullable=False)
    take_profit: Mapped[float] = mapped_column(Float, nullable=False)
    risk_percent: Mapped[float] = mapped_column(Float, nullable=False)
    risk_reward_ratio: Mapped[float] = mapped_column(Float, nullable=False)

    # Outcome
    pnl: Mapped[float] = mapped_column(Float, nullable=False)
    pnl_percent: Mapped[float] = mapped_column(Float, nullable=False)
    is_winner: Mapped[bool] = mapped_column(Boolean, nullable=False, index=True)
    exit_reason: Mapped[str] = mapped_column(String(50), nullable=False)  # tp/sl/manual/expired

    # Execution metrics
    entry_slippage: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    exit_slippage: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    commission: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # Market context
    market_context: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)

    # Timing
    entry_time: Mapped[datetime] = mapped_column(nullable=False, index=True)
    exit_time: Mapped[datetime] = mapped_column(nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)

    # References
    backtest_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    execution_order_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    signal_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Notes
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_journal_strategy_source", "strategy_name", "source"),
        Index("ix_journal_symbol_time", "symbol", "entry_time"),
    )

    def __repr__(self) -> str:
        return f"<JournalEntry {self.entry_id} {self.strategy_name} {self.source.value} P&L={self.pnl:.2f}>"


class FeedbackDecision(Base, TimestampMixin):
    """AI feedback loop decision log."""
    __tablename__ = "feedback_decisions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Decision type
    decision_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    # "trigger_optimization", "disable_strategy", "adjust_parameters", "update_memory", "monitor_closely"

    # Target
    strategy_name: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)

    # Analysis
    analysis: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)

    # Decision
    action_taken: Mapped[str] = mapped_column(Text, nullable=False)
    action_params: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # Outcome tracking
    executed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    execution_result: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    decision_time: Mapped[datetime] = mapped_column(nullable=False, index=True)
    executed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    __table_args__ = (
        Index("ix_feedback_strategy_type", "strategy_name", "decision_type"),
    )

    def __repr__(self) -> str:
        return f"<FeedbackDecision {self.id} {self.decision_type} {self.strategy_name}>"


class PerformanceSnapshot(Base, TimestampMixin):
    """Periodic performance snapshot for trend analysis."""
    __tablename__ = "performance_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Scope
    strategy_name: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    source: Mapped[TradeSource] = mapped_column(
        SQLEnum(TradeSource, native_enum=False),
        nullable=False
    )

    # Time period
    period_start: Mapped[datetime] = mapped_column(nullable=False)
    period_end: Mapped[datetime] = mapped_column(nullable=False)

    # Metrics
    total_trades: Mapped[int] = mapped_column(Integer, nullable=False)
    winning_trades: Mapped[int] = mapped_column(Integer, nullable=False)
    losing_trades: Mapped[int] = mapped_column(Integer, nullable=False)
    win_rate_percent: Mapped[float] = mapped_column(Float, nullable=False)

    total_pnl: Mapped[float] = mapped_column(Float, nullable=False)
    avg_win: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    avg_loss: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    profit_factor: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    max_consecutive_wins: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_consecutive_losses: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    avg_duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Snapshot time
    snapshot_time: Mapped[datetime] = mapped_column(nullable=False, index=True)

    __table_args__ = (
        Index("ix_performance_strategy_source_time", "strategy_name", "source", "snapshot_time"),
    )

    def __repr__(self) -> str:
        return f"<PerformanceSnapshot {self.strategy_name} {self.source.value} WR={self.win_rate_percent:.1f}%>"
