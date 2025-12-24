"""
Backtest result model for storing backtesting runs.

Prompt 05 - Backtest Engine: Data persistence layer.
"""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class BacktestResult(Base):
    """
    Stores the results of a backtest run.
    
    Captures all metrics, trade history, and equity curve for
    later analysis and comparison.
    """
    
    __tablename__ = "backtest_results"
    
    # Primary key - use String for cross-database compatibility
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4())
    )
    
    # Foreign key to user (int, referencing users.id)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Backtest configuration
    strategy_name: Mapped[str] = mapped_column(String(100), nullable=False)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False)
    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    
    # Initial conditions
    initial_capital: Mapped[float] = mapped_column(Float, nullable=False)
    
    # Performance metrics
    total_return: Mapped[float] = mapped_column(Float, nullable=False)
    sharpe_ratio: Mapped[float] = mapped_column(Float, nullable=True)
    sortino_ratio: Mapped[float] = mapped_column(Float, nullable=True)
    max_drawdown: Mapped[float] = mapped_column(Float, nullable=False)
    win_rate: Mapped[float] = mapped_column(Float, nullable=False)
    profit_factor: Mapped[float] = mapped_column(Float, nullable=True)
    
    # Trade statistics
    total_trades: Mapped[int] = mapped_column(Integer, nullable=False)
    winning_trades: Mapped[int] = mapped_column(Integer, nullable=False)
    losing_trades: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # JSON columns for detailed data
    equity_curve: Mapped[dict] = mapped_column(JSON, nullable=False, default=list)
    trade_log: Mapped[dict] = mapped_column(JSON, nullable=False, default=list)
    
    # Strategy parameters used
    strategy_params: Mapped[dict] = mapped_column(JSON, nullable=True)
    
    # Optional notes
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    
    # Relationship
    user: Mapped["User"] = relationship(
        "User",
        back_populates="backtest_results",
        lazy="selectin"
    )
    
    def __repr__(self) -> str:
        return (
            f"<BacktestResult(id={self.id}, strategy={self.strategy_name}, "
            f"symbol={self.symbol}, return={self.total_return:.2%})>"
        )
