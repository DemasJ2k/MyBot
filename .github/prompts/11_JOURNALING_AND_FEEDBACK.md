# Prompt 11: Journaling and Feedback Loop

## Purpose

Build the trade journaling system and AI feedback loop that serves as the single source of truth for learning and performance analysis. This system records every trade (backtest and live) with complete context, provides immutable audit trails, and powers a deterministic feedback loop that analyzes performance patterns to trigger optimizations and strategy adjustments.

## Scope

- Unified trade journal (backtest + live trades)
- Immutable journal entries with complete trade context
- Performance analyzer comparing live vs backtest results
- Pattern detection (underperformance, regime changes)
- AI feedback loop with deterministic triggers
- Automatic optimization initiation
- Strategy disablement recommendations
- Learning memory integration
- Feedback decision audit trail
- Complete test suite

## Journaling Architecture

```
Trade Sources:
├─ Backtest Engine → Backtest Trades
└─ Execution Engine → Live Trades
    ↓
Journal Writer (immutable entries)
    ↓
Trade Journal Database
    ↓
Performance Analyzer
    ├─ Compare live vs backtest
    ├─ Detect patterns
    └─ Calculate metrics
    ↓
AI Feedback Loop
    ├─ Read journal
    ├─ Analyze performance
    ├─ Detect underperformance
    └─ Trigger actions
    ↓
Actions:
├─ Trigger optimization
├─ Disable strategy
├─ Adjust parameters
└─ Update agent memory
    ↓
Feedback Decision Log (audit trail)
```

## Implementation

### Step 1: Database Models

Create `backend/app/models/journal.py`:

```python
from sqlalchemy import String, Float, Integer, JSON, Enum as SQLEnum, Boolean, Index, Text
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from typing import Optional, Dict, Any
import enum
from app.models.base import Base, TimestampMixin


class TradeSource(str, enum.Enum):
    BACKTEST = "backtest"
    LIVE = "live"
    PAPER = "paper"


class JournalEntry(Base, TimestampMixin):
    """
    Immutable trade journal entry.

    Records complete trade context for learning and analysis.
    """
    __tablename__ = "journal_entries"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    entry_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)

    # Trade source
    source: Mapped[TradeSource] = mapped_column(SQLEnum(TradeSource), nullable=False, index=True)

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
    # {
    #   "trend": "bullish/bearish/neutral",
    #   "volatility": float,
    #   "volume_profile": {...},
    #   "indicators": {...}
    # }

    # Timing
    entry_time: Mapped[datetime] = mapped_column(nullable=False, index=True)
    exit_time: Mapped[datetime] = mapped_column(nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)

    # References
    backtest_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    execution_order_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    signal_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Metadata
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
    # "trigger_optimization", "disable_strategy", "adjust_parameters", "update_memory"

    # Target
    strategy_name: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)

    # Analysis
    analysis: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    # {
    #   "pattern_detected": str,
    #   "live_performance": {...},
    #   "backtest_performance": {...},
    #   "deviation_metrics": {...}
    # }

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
    source: Mapped[TradeSource] = mapped_column(SQLEnum(TradeSource), nullable=False)

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
```

Update `backend/app/models/__init__.py`:

```python
from app.models.base import Base, TimestampMixin
from app.models.user import User
from app.models.market_data import Candle, Symbol, EconomicEvent
from app.models.signal import Signal, SignalType, SignalStatus
from app.models.position import Position, PositionStatus, PositionSide
from app.models.backtest import BacktestResult
from app.models.optimization import (
    OptimizationJob,
    OptimizationResult,
    OptimizationMethod,
    OptimizationStatus,
    Playbook,
)
from app.models.ai_agent import (
    AIDecision,
    AgentMemory,
    SystemConfig,
    SystemMode,
    AgentRole,
    DecisionType,
)
from app.models.coordination import (
    AgentMessage,
    CoordinationState,
    AgentHealth,
    AgentAuthorityLevel,
    CoordinationPhase,
    MessageType,
    MessagePriority,
)
from app.models.risk import (
    RiskDecision,
    RiskDecisionType,
    AccountRiskState,
    StrategyRiskBudget,
)
from app.models.execution import (
    ExecutionOrder,
    ExecutionLog,
    BrokerConnection,
    BrokerType,
    OrderType,
    OrderSide,
    OrderStatus,
)
from app.models.journal import (
    JournalEntry,
    FeedbackDecision,
    PerformanceSnapshot,
    TradeSource,
)

__all__ = [
    "Base",
    "TimestampMixin",
    "User",
    "Candle",
    "Symbol",
    "EconomicEvent",
    "Signal",
    "SignalType",
    "SignalStatus",
    "Position",
    "PositionStatus",
    "PositionSide",
    "BacktestResult",
    "OptimizationJob",
    "OptimizationResult",
    "OptimizationMethod",
    "OptimizationStatus",
    "Playbook",
    "AIDecision",
    "AgentMemory",
    "SystemConfig",
    "SystemMode",
    "AgentRole",
    "DecisionType",
    "AgentMessage",
    "CoordinationState",
    "AgentHealth",
    "AgentAuthorityLevel",
    "CoordinationPhase",
    "MessageType",
    "MessagePriority",
    "RiskDecision",
    "RiskDecisionType",
    "AccountRiskState",
    "StrategyRiskBudget",
    "ExecutionOrder",
    "ExecutionLog",
    "BrokerConnection",
    "BrokerType",
    "OrderType",
    "OrderSide",
    "OrderStatus",
    "JournalEntry",
    "FeedbackDecision",
    "PerformanceSnapshot",
    "TradeSource",
]
```

### Step 2: Journal Writer

Create `backend/app/journal/writer.py`:

```python
from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.journal import JournalEntry, TradeSource
from app.models.position import Position
from app.backtest.portfolio import Trade
import uuid
import logging

logger = logging.getLogger(__name__)


class JournalWriter:
    """
    Writes immutable journal entries for all trades.

    Journal is the SINGLE SOURCE OF TRUTH for performance analysis.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def record_backtest_trade(
        self,
        trade: Trade,
        strategy_name: str,
        strategy_config: Dict[str, Any],
        backtest_id: int,
        market_context: Optional[Dict[str, Any]] = None
    ) -> JournalEntry:
        """
        Record a backtest trade to journal.

        Args:
            trade: Trade from backtest
            strategy_name: Strategy name
            strategy_config: Strategy configuration used
            backtest_id: Backtest result ID
            market_context: Market conditions at trade time

        Returns:
            Created journal entry
        """
        duration_minutes = int((trade.exit_time - trade.entry_time).total_seconds() / 60)

        # Determine exit reason
        exit_reason = trade.reason if trade.reason else "unknown"

        # Calculate metrics
        is_winner = trade.net_pnl > 0
        risk = abs(trade.entry_price - (trade.entry_price * 0.98))  # Simplified
        pnl_percent = (trade.net_pnl / (trade.entry_price * trade.position_size) * 100.0) if trade.entry_price > 0 else 0.0

        entry_id = f"BT_{backtest_id}_{uuid.uuid4().hex[:8]}"

        entry = JournalEntry(
            entry_id=entry_id,
            source=TradeSource.BACKTEST,
            strategy_name=strategy_name,
            strategy_config=strategy_config,
            symbol=trade.symbol,
            timeframe="unknown",  # Backtest doesn't track this
            side=trade.side,
            entry_price=trade.entry_price,
            exit_price=trade.exit_price,
            position_size=trade.position_size,
            stop_loss=0.0,  # Not tracked in simple backtest
            take_profit=0.0,
            risk_percent=2.0,  # Default assumption
            risk_reward_ratio=2.0,  # Default assumption
            pnl=trade.net_pnl,
            pnl_percent=pnl_percent,
            is_winner=is_winner,
            exit_reason=exit_reason,
            entry_slippage=0.0,
            exit_slippage=0.0,
            commission=trade.commission,
            market_context=market_context or {},
            entry_time=trade.entry_time,
            exit_time=trade.exit_time,
            duration_minutes=duration_minutes,
            backtest_id=backtest_id
        )

        self.db.add(entry)
        await self.db.commit()
        await self.db.refresh(entry)

        logger.info(f"Recorded backtest trade: {entry_id} P&L={trade.net_pnl:.2f}")

        return entry

    async def record_live_trade(
        self,
        position: Position,
        strategy_config: Dict[str, Any],
        execution_order_id: int,
        signal_id: Optional[int] = None,
        market_context: Optional[Dict[str, Any]] = None
    ) -> JournalEntry:
        """
        Record a live trade to journal.

        Args:
            position: Closed position
            strategy_config: Strategy configuration used
            execution_order_id: Execution order ID
            signal_id: Signal ID that generated trade
            market_context: Market conditions at trade time

        Returns:
            Created journal entry
        """
        if position.exit_time is None or position.realized_pnl is None:
            raise ValueError("Cannot journal open position")

        duration_minutes = int((position.exit_time - position.entry_time).total_seconds() / 60)

        # Calculate metrics
        is_winner = position.realized_pnl > 0
        risk_amount = abs(position.entry_price - position.stop_loss) * position.position_size
        reward_amount = abs(position.take_profit - position.entry_price) * position.position_size
        rr_ratio = reward_amount / risk_amount if risk_amount > 0 else 0.0

        pnl_percent = (position.realized_pnl / (position.entry_price * position.position_size) * 100.0) if position.entry_price > 0 else 0.0

        # Determine exit reason (simplified)
        exit_reason = "manual"  # Default
        if position.exit_price == position.stop_loss:
            exit_reason = "sl"
        elif position.exit_price == position.take_profit:
            exit_reason = "tp"

        entry_id = f"LIVE_{execution_order_id}_{uuid.uuid4().hex[:8]}"

        entry = JournalEntry(
            entry_id=entry_id,
            source=TradeSource.LIVE,
            strategy_name=position.strategy_name,
            strategy_config=strategy_config,
            symbol=position.symbol,
            timeframe="unknown",
            side=position.side.value,
            entry_price=position.entry_price,
            exit_price=position.exit_price,
            position_size=position.position_size,
            stop_loss=position.stop_loss,
            take_profit=position.take_profit,
            risk_percent=2.0,  # Would need to calculate from account balance
            risk_reward_ratio=rr_ratio,
            pnl=position.realized_pnl,
            pnl_percent=pnl_percent,
            is_winner=is_winner,
            exit_reason=exit_reason,
            entry_slippage=0.0,  # Would need actual execution data
            exit_slippage=0.0,
            commission=position.commission_paid,
            market_context=market_context or {},
            entry_time=position.entry_time,
            exit_time=position.exit_time,
            duration_minutes=duration_minutes,
            execution_order_id=execution_order_id,
            signal_id=signal_id
        )

        self.db.add(entry)
        await self.db.commit()
        await self.db.refresh(entry)

        logger.info(f"Recorded live trade: {entry_id} P&L={position.realized_pnl:.2f}")

        return entry
```

### Step 3: Performance Analyzer

Create `backend/app/journal/analyzer.py`:

```python
from typing import Dict, Any, List
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from app.models.journal import JournalEntry, PerformanceSnapshot, TradeSource
import logging

logger = logging.getLogger(__name__)


class PerformanceAnalyzer:
    """Analyzes journal entries to detect patterns and performance deviations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def analyze_strategy(
        self,
        strategy_name: str,
        symbol: str,
        lookback_days: int = 30
    ) -> Dict[str, Any]:
        """
        Analyze strategy performance from journal.

        Compares live vs backtest performance.

        Args:
            strategy_name: Strategy name
            symbol: Symbol
            lookback_days: Days to look back

        Returns:
            Analysis dict with performance metrics and deviation
        """
        cutoff_date = datetime.utcnow() - timedelta(days=lookback_days)

        # Get live trades
        live_metrics = await self._calculate_metrics(
            strategy_name, symbol, TradeSource.LIVE, cutoff_date
        )

        # Get backtest trades
        backtest_metrics = await self._calculate_metrics(
            strategy_name, symbol, TradeSource.BACKTEST, cutoff_date
        )

        # Calculate deviations
        deviation = self._calculate_deviation(live_metrics, backtest_metrics)

        analysis = {
            "strategy_name": strategy_name,
            "symbol": symbol,
            "lookback_days": lookback_days,
            "live_performance": live_metrics,
            "backtest_performance": backtest_metrics,
            "deviation": deviation,
            "analysis_time": datetime.utcnow().isoformat()
        }

        logger.info(f"Analyzed {strategy_name} on {symbol}: Live WR={live_metrics.get('win_rate', 0):.1f}% vs BT WR={backtest_metrics.get('win_rate', 0):.1f}%")

        return analysis

    async def _calculate_metrics(
        self,
        strategy_name: str,
        symbol: str,
        source: TradeSource,
        cutoff_date: datetime
    ) -> Dict[str, Any]:
        """Calculate performance metrics from journal entries."""
        stmt = select(JournalEntry).where(
            and_(
                JournalEntry.strategy_name == strategy_name,
                JournalEntry.symbol == symbol,
                JournalEntry.source == source,
                JournalEntry.entry_time >= cutoff_date
            )
        )

        result = await self.db.execute(stmt)
        entries = result.scalars().all()

        if not entries:
            return {
                "total_trades": 0,
                "win_rate": 0.0,
                "avg_pnl": 0.0,
                "profit_factor": 0.0
            }

        total_trades = len(entries)
        winning_trades = sum(1 for e in entries if e.is_winner)
        losing_trades = total_trades - winning_trades

        win_rate = (winning_trades / total_trades * 100.0) if total_trades > 0 else 0.0

        total_pnl = sum(e.pnl for e in entries)
        avg_pnl = total_pnl / total_trades if total_trades > 0 else 0.0

        gross_profit = sum(e.pnl for e in entries if e.is_winner)
        gross_loss = abs(sum(e.pnl for e in entries if not e.is_winner))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0.0

        avg_win = gross_profit / winning_trades if winning_trades > 0 else 0.0
        avg_loss = gross_loss / losing_trades if losing_trades > 0 else 0.0

        return {
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "win_rate": win_rate,
            "total_pnl": total_pnl,
            "avg_pnl": avg_pnl,
            "gross_profit": gross_profit,
            "gross_loss": gross_loss,
            "profit_factor": profit_factor,
            "avg_win": avg_win,
            "avg_loss": avg_loss
        }

    def _calculate_deviation(
        self,
        live_metrics: Dict[str, Any],
        backtest_metrics: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate deviation between live and backtest performance."""
        if backtest_metrics["total_trades"] == 0:
            return {"status": "no_backtest_data"}

        if live_metrics["total_trades"] == 0:
            return {"status": "no_live_data"}

        win_rate_deviation = live_metrics["win_rate"] - backtest_metrics["win_rate"]
        profit_factor_deviation = live_metrics["profit_factor"] - backtest_metrics["profit_factor"]

        # Determine severity
        severity = "normal"
        if abs(win_rate_deviation) > 20.0:  # >20% deviation in win rate
            severity = "critical"
        elif abs(win_rate_deviation) > 10.0:
            severity = "warning"

        return {
            "status": "analyzed",
            "win_rate_deviation_percent": win_rate_deviation,
            "profit_factor_deviation": profit_factor_deviation,
            "severity": severity
        }

    async def detect_underperformance(
        self,
        strategy_name: str,
        symbol: str
    ) -> Dict[str, Any]:
        """
        Detect if strategy is underperforming.

        Criteria:
        - Win rate < 40%
        - Profit factor < 1.0
        - 5+ consecutive losses
        - Live performance significantly worse than backtest

        Returns:
            Detection result with recommendations
        """
        analysis = await self.analyze_strategy(strategy_name, symbol, lookback_days=30)

        live_metrics = analysis["live_performance"]
        deviation = analysis["deviation"]

        issues = []

        # Check win rate
        if live_metrics["win_rate"] < 40.0:
            issues.append("low_win_rate")

        # Check profit factor
        if live_metrics["profit_factor"] < 1.0:
            issues.append("unprofitable")

        # Check deviation severity
        if deviation.get("severity") == "critical":
            issues.append("critical_deviation_from_backtest")

        # Check consecutive losses
        consecutive_losses = await self._count_consecutive_losses(strategy_name, symbol)
        if consecutive_losses >= 5:
            issues.append("excessive_consecutive_losses")

        if issues:
            recommendation = self._generate_recommendation(issues)

            return {
                "underperforming": True,
                "issues": issues,
                "recommendation": recommendation,
                "live_metrics": live_metrics,
                "deviation": deviation
            }

        return {
            "underperforming": False,
            "issues": [],
            "recommendation": "continue",
            "live_metrics": live_metrics
        }

    async def _count_consecutive_losses(self, strategy_name: str, symbol: str) -> int:
        """Count current consecutive losses."""
        stmt = select(JournalEntry).where(
            and_(
                JournalEntry.strategy_name == strategy_name,
                JournalEntry.symbol == symbol,
                JournalEntry.source == TradeSource.LIVE
            )
        ).order_by(JournalEntry.exit_time.desc()).limit(20)

        result = await self.db.execute(stmt)
        entries = result.scalars().all()

        consecutive = 0
        for entry in entries:
            if not entry.is_winner:
                consecutive += 1
            else:
                break

        return consecutive

    def _generate_recommendation(self, issues: List[str]) -> str:
        """Generate recommendation based on issues."""
        if "critical_deviation_from_backtest" in issues:
            return "trigger_optimization"

        if "excessive_consecutive_losses" in issues:
            return "disable_strategy"

        if "unprofitable" in issues and "low_win_rate" in issues:
            return "disable_strategy"

        return "monitor_closely"
```

### Step 4: Feedback Loop

Create `backend/app/journal/feedback_loop.py`:

```python
from typing import Dict, Any
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.journal.analyzer import PerformanceAnalyzer
from app.models.journal import FeedbackDecision
from app.models.optimization import OptimizationJob, OptimizationMethod, OptimizationStatus
from app.models.risk import StrategyRiskBudget
import logging

logger = logging.getLogger(__name__)


class FeedbackLoop:
    """
    AI feedback loop that learns from journal and triggers actions.

    Deterministic and auditable.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.analyzer = PerformanceAnalyzer(db)

    async def run_feedback_cycle(
        self,
        strategy_name: str,
        symbol: str
    ) -> Dict[str, Any]:
        """
        Run one feedback cycle for a strategy.

        Steps:
        1. Analyze performance from journal
        2. Detect underperformance patterns
        3. Determine action
        4. Log decision
        5. Execute action (if appropriate)

        Args:
            strategy_name: Strategy name
            symbol: Symbol

        Returns:
            Feedback cycle result
        """
        logger.info(f"Running feedback cycle for {strategy_name} on {symbol}")

        # Step 1: Analyze performance
        underperformance = await self.analyzer.detect_underperformance(strategy_name, symbol)

        # Step 2: Determine action
        if not underperformance["underperforming"]:
            logger.info(f"{strategy_name} on {symbol} is performing normally")
            return {
                "action": "none",
                "reason": "Performance within acceptable range"
            }

        recommendation = underperformance["recommendation"]

        # Step 3: Log decision
        decision = await self._log_decision(
            strategy_name=strategy_name,
            symbol=symbol,
            analysis=underperformance,
            recommendation=recommendation
        )

        # Step 4: Execute action
        result = await self._execute_action(
            decision_id=decision.id,
            strategy_name=strategy_name,
            symbol=symbol,
            recommendation=recommendation
        )

        return {
            "action": recommendation,
            "decision_id": decision.id,
            "execution_result": result,
            "underperformance": underperformance
        }

    async def _log_decision(
        self,
        strategy_name: str,
        symbol: str,
        analysis: Dict[str, Any],
        recommendation: str
    ) -> FeedbackDecision:
        """Log feedback decision to audit trail."""
        decision = FeedbackDecision(
            decision_type=recommendation,
            strategy_name=strategy_name,
            symbol=symbol,
            analysis=analysis,
            action_taken=f"Recommendation: {recommendation}",
            executed=False,
            decision_time=datetime.utcnow()
        )

        self.db.add(decision)
        await self.db.commit()
        await self.db.refresh(decision)

        logger.info(f"Feedback decision logged: {decision.id} - {recommendation}")

        return decision

    async def _execute_action(
        self,
        decision_id: int,
        strategy_name: str,
        symbol: str,
        recommendation: str
    ) -> str:
        """Execute feedback action."""
        stmt = select(FeedbackDecision).where(FeedbackDecision.id == decision_id)
        result = await self.db.execute(stmt)
        decision = result.scalar_one_or_none()

        if not decision:
            return "Decision not found"

        if recommendation == "trigger_optimization":
            # Check if optimization already running
            stmt = select(OptimizationJob).where(
                OptimizationJob.strategy_name == strategy_name,
                OptimizationJob.symbol == symbol,
                OptimizationJob.status.in_([OptimizationStatus.PENDING, OptimizationStatus.RUNNING])
            )
            result = await self.db.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                execution_result = f"Optimization already in progress (job {existing.id})"
            else:
                # Create optimization job
                # Note: Would need actual implementation to create job
                execution_result = "Optimization job creation requested (not implemented in this step)"

            decision.executed = True
            decision.executed_at = datetime.utcnow()
            decision.execution_result = execution_result
            await self.db.commit()

            logger.info(f"Triggered optimization for {strategy_name} on {symbol}")
            return execution_result

        elif recommendation == "disable_strategy":
            # Disable strategy in risk budget
            stmt = select(StrategyRiskBudget).where(
                StrategyRiskBudget.strategy_name == strategy_name,
                StrategyRiskBudget.symbol == symbol
            )
            result = await self.db.execute(stmt)
            budget = result.scalar_one_or_none()

            if budget:
                budget.is_enabled = False
                budget.disabled_reason = "AI feedback loop: Underperformance detected"
                await self.db.commit()

                execution_result = f"Strategy disabled in risk budget"
            else:
                execution_result = "Risk budget not found"

            decision.executed = True
            decision.executed_at = datetime.utcnow()
            decision.execution_result = execution_result
            await self.db.commit()

            logger.warning(f"Disabled {strategy_name} on {symbol} due to underperformance")
            return execution_result

        elif recommendation == "monitor_closely":
            execution_result = "Monitoring enabled (no action taken)"

            decision.executed = True
            decision.executed_at = datetime.utcnow()
            decision.execution_result = execution_result
            await self.db.commit()

            return execution_result

        return "Unknown recommendation"
```

### Step 5: Database Migration

```bash
cd backend
DATABASE_URL="sqlite+aiosqlite:///./flowrex_dev.db" python -m alembic revision --autogenerate -m "add_journal_tables"
```

Run migration:
```bash
DATABASE_URL="sqlite+aiosqlite:///./flowrex_dev.db" python -m alembic upgrade head
```

### Step 6: API Routes

Create `backend/app/api/v1/journal_routes.py`:

```python
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from pydantic import BaseModel
from app.database import get_db
from app.journal.analyzer import PerformanceAnalyzer
from app.journal.feedback_loop import FeedbackLoop
from app.models.journal import JournalEntry, FeedbackDecision, TradeSource
from sqlalchemy import select, desc, and_
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/journal", tags=["journal"])


class JournalEntryResponse(BaseModel):
    id: int
    entry_id: str
    source: str
    strategy_name: str
    symbol: str
    side: str
    entry_price: float
    exit_price: float
    pnl: float
    pnl_percent: float
    is_winner: bool
    exit_reason: str
    entry_time: datetime
    exit_time: datetime

    class Config:
        from_attributes = True


@router.get("/entries", response_model=List[JournalEntryResponse])
async def get_journal_entries(
    strategy_name: str | None = None,
    symbol: str | None = None,
    source: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db)
):
    """Get journal entries with optional filters."""
    stmt = select(JournalEntry)

    filters = []
    if strategy_name:
        filters.append(JournalEntry.strategy_name == strategy_name)
    if symbol:
        filters.append(JournalEntry.symbol == symbol)
    if source:
        filters.append(JournalEntry.source == source)

    if filters:
        stmt = stmt.where(and_(*filters))

    stmt = stmt.order_by(desc(JournalEntry.exit_time)).limit(limit)

    result = await db.execute(stmt)
    entries = result.scalars().all()

    return entries


@router.get("/entries/{entry_id}")
async def get_journal_entry(entry_id: str, db: AsyncSession = Depends(get_db)):
    """Get detailed journal entry."""
    stmt = select(JournalEntry).where(JournalEntry.entry_id == entry_id)
    result = await db.execute(stmt)
    entry = result.scalar_one_or_none()

    if not entry:
        raise HTTPException(status_code=404, detail="Journal entry not found")

    return {
        "entry": JournalEntryResponse.model_validate(entry),
        "strategy_config": entry.strategy_config,
        "market_context": entry.market_context
    }


@router.get("/analyze/{strategy_name}/{symbol}")
async def analyze_strategy(
    strategy_name: str,
    symbol: str,
    lookback_days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db)
):
    """Analyze strategy performance from journal."""
    analyzer = PerformanceAnalyzer(db=db)

    analysis = await analyzer.analyze_strategy(
        strategy_name=strategy_name,
        symbol=symbol,
        lookback_days=lookback_days
    )

    return analysis


@router.get("/underperformance/{strategy_name}/{symbol}")
async def detect_underperformance(
    strategy_name: str,
    symbol: str,
    db: AsyncSession = Depends(get_db)
):
    """Detect if strategy is underperforming."""
    analyzer = PerformanceAnalyzer(db=db)

    result = await analyzer.detect_underperformance(
        strategy_name=strategy_name,
        symbol=symbol
    )

    return result


@router.post("/feedback/{strategy_name}/{symbol}")
async def run_feedback_cycle(
    strategy_name: str,
    symbol: str,
    db: AsyncSession = Depends(get_db)
):
    """Run AI feedback cycle for strategy."""
    feedback_loop = FeedbackLoop(db=db)

    result = await feedback_loop.run_feedback_cycle(
        strategy_name=strategy_name,
        symbol=symbol
    )

    return result


@router.get("/feedback/decisions")
async def get_feedback_decisions(
    strategy_name: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db)
):
    """Get feedback decision log."""
    stmt = select(FeedbackDecision)

    if strategy_name:
        stmt = stmt.where(FeedbackDecision.strategy_name == strategy_name)

    stmt = stmt.order_by(desc(FeedbackDecision.decision_time)).limit(limit)

    result = await db.execute(stmt)
    decisions = result.scalars().all()

    return [
        {
            "id": d.id,
            "decision_type": d.decision_type,
            "strategy_name": d.strategy_name,
            "symbol": d.symbol,
            "analysis": d.analysis,
            "action_taken": d.action_taken,
            "executed": d.executed,
            "execution_result": d.execution_result,
            "decision_time": d.decision_time
        }
        for d in decisions
    ]
```

Register routes in `backend/app/main.py`:

```python
from app.api.v1 import (
    auth_routes,
    data_routes,
    strategy_routes,
    backtest_routes,
    optimization_routes,
    ai_routes,
    coordination_routes,
    risk_routes,
    execution_routes,
    journal_routes
)

app.include_router(journal_routes.router, prefix="/api/v1")
```

### Step 7: Tests

Create `backend/tests/unit/test_journal.py`:

```python
import pytest
from datetime import datetime, timedelta
from app.journal.writer import JournalWriter
from app.journal.analyzer import PerformanceAnalyzer
from app.models.journal import JournalEntry, TradeSource
from app.backtest.portfolio import Trade


@pytest.mark.asyncio
class TestJournalWriter:
    async def test_record_backtest_trade(self, async_db_session):
        writer = JournalWriter(db=async_db_session)

        # Create mock trade
        trade = Trade(
            entry_time=datetime.utcnow() - timedelta(hours=2),
            exit_time=datetime.utcnow(),
            symbol="EURUSD",
            side="long",
            entry_price=1.1000,
            exit_price=1.1050,
            position_size=1.0,
            pnl=50.0,
            commission=0.1,
            net_pnl=49.9,
            reason="Take Profit"
        )

        entry = await writer.record_backtest_trade(
            trade=trade,
            strategy_name="NBB",
            strategy_config={"zone_lookback": 20},
            backtest_id=1
        )

        assert entry.id is not None
        assert entry.source == TradeSource.BACKTEST
        assert entry.is_winner is True
        assert entry.pnl == 49.9


@pytest.mark.asyncio
class TestPerformanceAnalyzer:
    async def test_analyze_strategy_no_data(self, async_db_session):
        analyzer = PerformanceAnalyzer(db=async_db_session)

        analysis = await analyzer.analyze_strategy(
            strategy_name="NBB",
            symbol="EURUSD",
            lookback_days=30
        )

        assert analysis["live_performance"]["total_trades"] == 0
        assert analysis["backtest_performance"]["total_trades"] == 0

    async def test_detect_underperformance(self, async_db_session):
        """Test underperformance detection with mock data."""
        # Create journal entries with poor performance
        writer = JournalWriter(db=async_db_session)

        # Add 10 losing trades
        for i in range(10):
            trade = Trade(
                entry_time=datetime.utcnow() - timedelta(hours=i+2),
                exit_time=datetime.utcnow() - timedelta(hours=i+1),
                symbol="EURUSD",
                side="long",
                entry_price=1.1000,
                exit_price=1.0950,
                position_size=1.0,
                pnl=-50.0,
                commission=0.1,
                net_pnl=-50.1,
                reason="Stop Loss"
            )

            await writer.record_backtest_trade(
                trade=trade,
                strategy_name="NBB",
                strategy_config={"zone_lookback": 20},
                backtest_id=1
            )

        # Analyze
        analyzer = PerformanceAnalyzer(db=async_db_session)

        result = await analyzer.detect_underperformance(
            strategy_name="NBB",
            symbol="EURUSD"
        )

        # Should detect underperformance (0% win rate, profit factor < 1)
        assert result["underperforming"] is True
        assert "unprofitable" in result["issues"]
```

Run tests:
```bash
cd backend
DATABASE_URL="sqlite+aiosqlite:///./flowrex_dev.db" python -m pytest tests/unit/test_journal.py -v
```

## Validation Checklist

Before proceeding to Prompt 12, verify:

- [ ] JournalEntry, FeedbackDecision, PerformanceSnapshot models created
- [ ] Database migration applied successfully
- [ ] JournalWriter can record backtest trades
- [ ] JournalWriter can record live trades
- [ ] Journal entries are immutable (no update methods)
- [ ] PerformanceAnalyzer calculates metrics from journal
- [ ] PerformanceAnalyzer compares live vs backtest performance
- [ ] PerformanceAnalyzer detects underperformance patterns
- [ ] FeedbackLoop runs deterministic analysis cycle
- [ ] FeedbackLoop logs all decisions to audit trail
- [ ] FeedbackLoop can trigger optimization
- [ ] FeedbackLoop can disable underperforming strategies
- [ ] API route `/journal/entries` returns journal entries
- [ ] API route `/journal/analyze` analyzes strategy performance
- [ ] API route `/journal/underperformance` detects issues
- [ ] API route `/journal/feedback` runs feedback cycle
- [ ] API route `/journal/feedback/decisions` returns decision log
- [ ] All unit tests pass
- [ ] Journal records complete trade context
- [ ] Feedback loop is deterministic and auditable
- [ ] Underperformance detection uses multiple criteria
- [ ] All AI decisions from journal are logged
- [ ] CROSSCHECK.md validation for Prompt 11 completed

## Hard Stop Criteria

**DO NOT PROCEED to Prompt 12 unless:**

1. ✅ Database migration runs without errors
2. ✅ All pytest tests pass (0 failures, 0 errors)
3. ✅ Journal entries are immutable (cannot be modified)
4. ✅ Backtest and live trades are both recorded
5. ✅ Performance analyzer compares live vs backtest correctly
6. ✅ Underperformance detection uses multiple criteria
7. ✅ Feedback loop decisions are logged to audit trail
8. ✅ Feedback loop can trigger optimization automatically
9. ✅ Feedback loop can disable strategies automatically
10. ✅ CROSSCHECK.md section for Prompt 11 fully validated

If any criterion fails, **HALT** and fix before continuing.

---

**Completion Criteria:**
- Trade journaling system fully operational
- Unified journal for backtest and live trades
- Performance analyzer working correctly
- AI feedback loop implemented with deterministic triggers
- All decisions auditable through feedback decision log
- System ready for Frontend Core (Prompt 12)
