"""
Optimization models for parameter optimization jobs and playbooks.

Prompt 06 - Optimization Engine: Database persistence layer.
"""

from sqlalchemy import String, Float, Integer, Enum as SQLEnum, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from typing import Optional, Dict, Any, List
import enum

from app.models.base import Base, TimestampMixin


class OptimizationMethod(str, enum.Enum):
    """Supported optimization methods."""
    GRID_SEARCH = "grid_search"
    RANDOM_SEARCH = "random_search"
    AI_DRIVEN = "ai_driven"
    GENETIC = "genetic"


class OptimizationStatus(str, enum.Enum):
    """Optimization job status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class OptimizationJob(Base, TimestampMixin):
    """
    Optimization job configuration and status.
    
    Tracks parameter optimization runs including configuration,
    progress, and best results found.
    """
    __tablename__ = "optimization_jobs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    strategy_name: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    interval: Mapped[str] = mapped_column(String(10), nullable=False)

    # Optimization parameters
    method: Mapped[OptimizationMethod] = mapped_column(
        SQLEnum(OptimizationMethod, native_enum=False, length=20),
        nullable=False
    )
    status: Mapped[OptimizationStatus] = mapped_column(
        SQLEnum(OptimizationStatus, native_enum=False, length=20),
        default=OptimizationStatus.PENDING,
        nullable=False,
        index=True
    )

    # Parameter space (JSON)
    parameter_ranges: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)

    # Backtest configuration
    start_date: Mapped[datetime] = mapped_column(nullable=False)
    end_date: Mapped[datetime] = mapped_column(nullable=False)
    initial_balance: Mapped[float] = mapped_column(Float, nullable=False, default=10000.0)
    commission_percent: Mapped[float] = mapped_column(Float, nullable=False, default=0.1)
    slippage_percent: Mapped[float] = mapped_column(Float, nullable=False, default=0.05)

    # Optimization settings
    max_iterations: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    objective_metric: Mapped[str] = mapped_column(String(50), nullable=False, default="sharpe_ratio")
    minimize: Mapped[bool] = mapped_column(default=False, nullable=False)  # False = maximize

    # Progress tracking
    total_combinations: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    completed_iterations: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    progress_percent: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # Results
    best_config: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    best_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    best_backtest_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    # Execution metadata
    started_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    results: Mapped[List["OptimizationResult"]] = relationship(
        "OptimizationResult",
        back_populates="job",
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_optimization_strategy_status", "strategy_name", "status"),
    )

    def __repr__(self) -> str:
        return f"<OptimizationJob {self.id} {self.strategy_name} {self.method.value} {self.status.value}>"


class OptimizationResult(Base, TimestampMixin):
    """
    Individual optimization iteration result.
    
    Stores the configuration tested and resulting metrics
    for each iteration of an optimization job.
    """
    __tablename__ = "optimization_results"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    job_id: Mapped[int] = mapped_column(
        ForeignKey("optimization_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    iteration: Mapped[int] = mapped_column(Integer, nullable=False)

    # Configuration tested
    config: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)

    # Performance metrics
    score: Mapped[float] = mapped_column(Float, nullable=False)  # Objective metric value
    total_return_percent: Mapped[float] = mapped_column(Float, nullable=False)
    sharpe_ratio: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_drawdown_percent: Mapped[float] = mapped_column(Float, nullable=False)
    win_rate_percent: Mapped[float] = mapped_column(Float, nullable=False)
    profit_factor: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    total_trades: Mapped[int] = mapped_column(Integer, nullable=False)

    # Reference to backtest (String(36) for UUID compatibility)
    backtest_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    # Relationships
    job: Mapped["OptimizationJob"] = relationship("OptimizationJob", back_populates="results")

    __table_args__ = (
        Index("ix_optimization_result_job_score", "job_id", "score"),
    )

    def __repr__(self) -> str:
        return f"<OptimizationResult {self.id} job={self.job_id} iter={self.iteration} score={self.score:.4f}>"


class Playbook(Base, TimestampMixin):
    """
    Saved strategy configuration for deployment.
    
    Playbooks store optimized strategy configurations that can be
    deployed to live or paper trading.
    """
    __tablename__ = "playbooks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    strategy_name: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)

    # Strategy configuration (JSON)
    config: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)

    # Performance metrics from optimization
    expected_return_percent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    expected_sharpe_ratio: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    expected_max_drawdown_percent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Metadata
    optimization_job_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_playbook_strategy_active", "strategy_name", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<Playbook {self.id} '{self.name}' {self.strategy_name} {self.symbol}>"
