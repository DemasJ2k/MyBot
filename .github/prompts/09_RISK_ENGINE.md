# Prompt 09: Risk Engine

## Purpose

Build the authoritative risk management system that enforces hard, immutable risk limits across all trading operations. The Risk Engine has absolute veto power over all trade decisions, operates independently of AI agents, and cannot be overridden by any component including the Supervisor. This is the final checkpoint before any capital is risked.

## Scope

- Hard risk limits (immutable constants)
- Pre-execution risk validation pipeline
- Real-time position risk monitoring
- Account-level risk tracking
- Drawdown-based throttling and emergency shutdown
- Per-strategy risk budgets and auto-disablement
- Correlation risk across positions
- Risk decision audit log
- Kill switch mechanism
- Complete test suite

## Risk Engine Architecture

```
Trade Request (from Execution Agent)
    ↓
Risk Engine Validator (HARD LIMITS ENFORCED)
    ↓
┌─────────────┬──────────────┬──────────────┬──────────────┐
│ Position    │ Account      │ Strategy     │ Correlation  │
│ Limit Check │ Drawdown     │ Budget Check │ Risk Check   │
└─────────────┴──────────────┴──────────────┴──────────────┘
    ↓
APPROVE (proceeds to execution) OR REJECT (logged and blocked)

Risk Precedence (highest to lowest):
1. Emergency Shutdown (15% drawdown)
2. Hard Position Limits (2% per trade, 10 positions max)
3. Daily Loss Limit (5% max)
4. Strategy Budget Limits
5. Correlation Limits
```

## Implementation

### Step 1: Hard Risk Constants

Create `backend/app/risk/constants.py`:

```python
"""
HARD RISK LIMITS

These limits are IMMUTABLE and CANNOT be overridden by any agent,
user, or system component. They represent the absolute maximum risk
tolerance for the system.

ANY ATTEMPT TO MODIFY THESE VALUES MUST BE AUDITED AND APPROVED
BY SYSTEM ADMINISTRATORS.
"""

# Position Limits
MAX_RISK_PER_TRADE_PERCENT = 2.0          # Maximum 2% of account per trade
MAX_POSITION_SIZE_LOTS = 1.0              # Maximum 1.0 lots per position
MAX_OPEN_POSITIONS = 10                    # Maximum 10 simultaneous positions

# Account Limits
MAX_DAILY_LOSS_PERCENT = 5.0              # Maximum 5% daily loss
EMERGENCY_DRAWDOWN_PERCENT = 15.0         # Emergency shutdown at 15% drawdown
MAX_ACCOUNT_LEVERAGE = 10.0               # Maximum 10:1 leverage

# Daily Limits
MAX_TRADES_PER_DAY = 20                   # Maximum 20 trades per day
MAX_TRADES_PER_HOUR = 5                   # Maximum 5 trades per hour

# Strategy Limits
MAX_STRATEGIES_ACTIVE = 4                 # Maximum 4 active strategies
MAX_RISK_PER_STRATEGY_PERCENT = 5.0       # Maximum 5% total exposure per strategy

# Correlation Limits
MAX_CORRELATED_POSITIONS = 3              # Maximum 3 highly correlated positions
CORRELATION_THRESHOLD = 0.7               # Positions with >0.7 correlation considered correlated

# Minimum Requirements
MIN_RISK_REWARD_RATIO = 1.5               # Minimum 1.5:1 risk/reward
MIN_ACCOUNT_BALANCE = 1000.0              # Minimum $1000 account balance


# Risk severity levels (for logging and alerts)
class RiskSeverity:
    """Risk event severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"
```

### Step 2: Database Models

Create `backend/app/models/risk.py`:

```python
from sqlalchemy import String, Float, Integer, JSON, Enum as SQLEnum, Boolean, Index, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from typing import Optional, Dict, Any
import enum
from app.models.base import Base, TimestampMixin


class RiskDecisionType(str, enum.Enum):
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
    decision_type: Mapped[RiskDecisionType] = mapped_column(SQLEnum(RiskDecisionType), nullable=False, index=True)

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
]
```

### Step 3: Risk Validator

Create `backend/app/risk/validator.py`:

```python
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from app.models.signal import Signal
from app.models.position import Position, PositionStatus
from app.models.risk import RiskDecision, RiskDecisionType, AccountRiskState, StrategyRiskBudget
from app.risk.constants import *
import logging

logger = logging.getLogger(__name__)


class RiskValidator:
    """
    Authoritative risk validation engine.

    THIS ENGINE HAS ABSOLUTE VETO POWER.
    All checks are executed in order of severity.
    If ANY check fails, the trade is REJECTED.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def validate_trade(
        self,
        signal: Signal,
        account_balance: float,
        peak_balance: float
    ) -> Tuple[bool, Optional[str], Dict[str, Any]]:
        """
        Validate a trade signal against ALL risk limits.

        Returns:
            (approved, rejection_reason, risk_metrics)
        """
        risk_metrics = {
            "account_balance": account_balance,
            "peak_balance": peak_balance,
            "signal_id": signal.id,
            "strategy_name": signal.strategy_name,
            "symbol": signal.symbol,
            "checks_performed": []
        }

        limits_checked = {}

        # CHECK 1: Emergency Shutdown Status
        check_result = await self._check_emergency_shutdown()
        risk_metrics["checks_performed"].append("emergency_shutdown")
        limits_checked["emergency_shutdown"] = check_result

        if not check_result["passed"]:
            await self._log_decision(
                decision_type=RiskDecisionType.TRADE_REJECTION,
                subject=f"Trade for {signal.symbol}",
                subject_id=signal.id,
                approved=False,
                rejection_reason=check_result["reason"],
                risk_metrics=risk_metrics,
                limits_checked=limits_checked,
                severity=RiskSeverity.EMERGENCY
            )
            return False, check_result["reason"], risk_metrics

        # CHECK 2: Account Drawdown
        current_drawdown = ((peak_balance - account_balance) / peak_balance * 100.0) if peak_balance > 0 else 0.0
        check_result = self._check_drawdown(current_drawdown)
        risk_metrics["checks_performed"].append("drawdown")
        risk_metrics["current_drawdown_percent"] = current_drawdown
        limits_checked["drawdown"] = check_result

        if not check_result["passed"]:
            # Trigger emergency shutdown
            await self._trigger_emergency_shutdown(current_drawdown)

            await self._log_decision(
                decision_type=RiskDecisionType.EMERGENCY_SHUTDOWN,
                subject="Emergency Shutdown Triggered",
                subject_id=None,
                approved=False,
                rejection_reason=check_result["reason"],
                risk_metrics=risk_metrics,
                limits_checked=limits_checked,
                severity=RiskSeverity.EMERGENCY
            )
            return False, check_result["reason"], risk_metrics

        # CHECK 3: Maximum Open Positions
        check_result = await self._check_max_positions()
        risk_metrics["checks_performed"].append("max_positions")
        limits_checked["max_positions"] = check_result

        if not check_result["passed"]:
            await self._log_decision(
                decision_type=RiskDecisionType.TRADE_REJECTION,
                subject=f"Trade for {signal.symbol}",
                subject_id=signal.id,
                approved=False,
                rejection_reason=check_result["reason"],
                risk_metrics=risk_metrics,
                limits_checked=limits_checked,
                severity=RiskSeverity.CRITICAL
            )
            return False, check_result["reason"], risk_metrics

        # CHECK 4: Daily Trade Limit
        check_result = await self._check_daily_trade_limit()
        risk_metrics["checks_performed"].append("daily_trade_limit")
        limits_checked["daily_trade_limit"] = check_result

        if not check_result["passed"]:
            await self._log_decision(
                decision_type=RiskDecisionType.TRADE_REJECTION,
                subject=f"Trade for {signal.symbol}",
                subject_id=signal.id,
                approved=False,
                rejection_reason=check_result["reason"],
                risk_metrics=risk_metrics,
                limits_checked=limits_checked,
                severity=RiskSeverity.WARNING
            )
            return False, check_result["reason"], risk_metrics

        # CHECK 5: Hourly Trade Limit
        check_result = await self._check_hourly_trade_limit()
        risk_metrics["checks_performed"].append("hourly_trade_limit")
        limits_checked["hourly_trade_limit"] = check_result

        if not check_result["passed"]:
            await self._log_decision(
                decision_type=RiskDecisionType.TRADE_REJECTION,
                subject=f"Trade for {signal.symbol}",
                subject_id=signal.id,
                approved=False,
                rejection_reason=check_result["reason"],
                risk_metrics=risk_metrics,
                limits_checked=limits_checked,
                severity=RiskSeverity.WARNING
            )
            return False, check_result["reason"], risk_metrics

        # CHECK 6: Risk per Trade
        position_size = self._calculate_position_size(
            account_balance=account_balance,
            risk_percent=min(signal.risk_percent, MAX_RISK_PER_TRADE_PERCENT),
            entry_price=signal.entry_price,
            stop_loss=signal.stop_loss
        )

        check_result = self._check_position_size(position_size)
        risk_metrics["checks_performed"].append("position_size")
        risk_metrics["calculated_position_size"] = position_size
        limits_checked["position_size"] = check_result

        if not check_result["passed"]:
            await self._log_decision(
                decision_type=RiskDecisionType.TRADE_REJECTION,
                subject=f"Trade for {signal.symbol}",
                subject_id=signal.id,
                approved=False,
                rejection_reason=check_result["reason"],
                risk_metrics=risk_metrics,
                limits_checked=limits_checked,
                severity=RiskSeverity.CRITICAL
            )
            return False, check_result["reason"], risk_metrics

        # CHECK 7: Risk/Reward Ratio
        rr_ratio = signal.risk_reward_ratio
        check_result = self._check_risk_reward(rr_ratio)
        risk_metrics["checks_performed"].append("risk_reward")
        risk_metrics["risk_reward_ratio"] = rr_ratio
        limits_checked["risk_reward"] = check_result

        if not check_result["passed"]:
            await self._log_decision(
                decision_type=RiskDecisionType.TRADE_REJECTION,
                subject=f"Trade for {signal.symbol}",
                subject_id=signal.id,
                approved=False,
                rejection_reason=check_result["reason"],
                risk_metrics=risk_metrics,
                limits_checked=limits_checked,
                severity=RiskSeverity.WARNING
            )
            return False, check_result["reason"], risk_metrics

        # CHECK 8: Strategy Budget
        check_result = await self._check_strategy_budget(signal.strategy_name, signal.symbol)
        risk_metrics["checks_performed"].append("strategy_budget")
        limits_checked["strategy_budget"] = check_result

        if not check_result["passed"]:
            await self._log_decision(
                decision_type=RiskDecisionType.TRADE_REJECTION,
                subject=f"Trade for {signal.symbol}",
                subject_id=signal.id,
                approved=False,
                rejection_reason=check_result["reason"],
                risk_metrics=risk_metrics,
                limits_checked=limits_checked,
                severity=RiskSeverity.WARNING
            )
            return False, check_result["reason"], risk_metrics

        # CHECK 9: Daily Loss Limit
        check_result = await self._check_daily_loss_limit(account_balance)
        risk_metrics["checks_performed"].append("daily_loss_limit")
        limits_checked["daily_loss_limit"] = check_result

        if not check_result["passed"]:
            await self._log_decision(
                decision_type=RiskDecisionType.TRADE_REJECTION,
                subject=f"Trade for {signal.symbol}",
                subject_id=signal.id,
                approved=False,
                rejection_reason=check_result["reason"],
                risk_metrics=risk_metrics,
                limits_checked=limits_checked,
                severity=RiskSeverity.CRITICAL
            )
            return False, check_result["reason"], risk_metrics

        # ALL CHECKS PASSED
        await self._log_decision(
            decision_type=RiskDecisionType.TRADE_APPROVAL,
            subject=f"Trade for {signal.symbol}",
            subject_id=signal.id,
            approved=True,
            rejection_reason=None,
            risk_metrics=risk_metrics,
            limits_checked=limits_checked,
            severity=RiskSeverity.INFO
        )

        logger.info(f"Risk validation APPROVED: {signal.strategy_name} {signal.symbol}")

        return True, None, risk_metrics

    async def _check_emergency_shutdown(self) -> Dict[str, Any]:
        """Check if emergency shutdown is active."""
        stmt = select(AccountRiskState).order_by(AccountRiskState.last_updated.desc()).limit(1)
        result = await self.db.execute(stmt)
        state = result.scalar_one_or_none()

        if state and state.emergency_shutdown_active:
            return {
                "passed": False,
                "reason": "Emergency shutdown is active - all trading halted",
                "current": True,
                "limit": False
            }

        return {"passed": True, "reason": None, "current": False, "limit": False}

    def _check_drawdown(self, current_drawdown: float) -> Dict[str, Any]:
        """Check account drawdown against emergency limit."""
        if current_drawdown >= EMERGENCY_DRAWDOWN_PERCENT:
            return {
                "passed": False,
                "reason": f"Emergency drawdown limit breached: {current_drawdown:.2f}% >= {EMERGENCY_DRAWDOWN_PERCENT}%",
                "current": current_drawdown,
                "limit": EMERGENCY_DRAWDOWN_PERCENT
            }

        return {"passed": True, "reason": None, "current": current_drawdown, "limit": EMERGENCY_DRAWDOWN_PERCENT}

    async def _check_max_positions(self) -> Dict[str, Any]:
        """Check maximum open positions limit."""
        stmt = select(Position).where(Position.status == PositionStatus.OPEN)
        result = await self.db.execute(stmt)
        open_positions = len(result.scalars().all())

        if open_positions >= MAX_OPEN_POSITIONS:
            return {
                "passed": False,
                "reason": f"Maximum open positions reached: {open_positions}/{MAX_OPEN_POSITIONS}",
                "current": open_positions,
                "limit": MAX_OPEN_POSITIONS
            }

        return {"passed": True, "reason": None, "current": open_positions, "limit": MAX_OPEN_POSITIONS}

    async def _check_daily_trade_limit(self) -> Dict[str, Any]:
        """Check daily trade limit."""
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        stmt = select(Position).where(Position.entry_time >= today_start)
        result = await self.db.execute(stmt)
        trades_today = len(result.scalars().all())

        if trades_today >= MAX_TRADES_PER_DAY:
            return {
                "passed": False,
                "reason": f"Daily trade limit reached: {trades_today}/{MAX_TRADES_PER_DAY}",
                "current": trades_today,
                "limit": MAX_TRADES_PER_DAY
            }

        return {"passed": True, "reason": None, "current": trades_today, "limit": MAX_TRADES_PER_DAY}

    async def _check_hourly_trade_limit(self) -> Dict[str, Any]:
        """Check hourly trade limit."""
        hour_ago = datetime.utcnow() - timedelta(hours=1)
        stmt = select(Position).where(Position.entry_time >= hour_ago)
        result = await self.db.execute(stmt)
        trades_this_hour = len(result.scalars().all())

        if trades_this_hour >= MAX_TRADES_PER_HOUR:
            return {
                "passed": False,
                "reason": f"Hourly trade limit reached: {trades_this_hour}/{MAX_TRADES_PER_HOUR}",
                "current": trades_this_hour,
                "limit": MAX_TRADES_PER_HOUR
            }

        return {"passed": True, "reason": None, "current": trades_this_hour, "limit": MAX_TRADES_PER_HOUR}

    def _calculate_position_size(
        self,
        account_balance: float,
        risk_percent: float,
        entry_price: float,
        stop_loss: float
    ) -> float:
        """Calculate position size based on risk parameters."""
        risk_amount = account_balance * (risk_percent / 100.0)
        risk_per_unit = abs(entry_price - stop_loss)

        if risk_per_unit == 0:
            return 0.0

        position_size = risk_amount / risk_per_unit
        return round(min(position_size, MAX_POSITION_SIZE_LOTS), 2)

    def _check_position_size(self, position_size: float) -> Dict[str, Any]:
        """Check position size against maximum."""
        if position_size > MAX_POSITION_SIZE_LOTS:
            return {
                "passed": False,
                "reason": f"Position size exceeds maximum: {position_size} > {MAX_POSITION_SIZE_LOTS} lots",
                "current": position_size,
                "limit": MAX_POSITION_SIZE_LOTS
            }

        if position_size <= 0:
            return {
                "passed": False,
                "reason": f"Invalid position size: {position_size}",
                "current": position_size,
                "limit": MAX_POSITION_SIZE_LOTS
            }

        return {"passed": True, "reason": None, "current": position_size, "limit": MAX_POSITION_SIZE_LOTS}

    def _check_risk_reward(self, rr_ratio: float) -> Dict[str, Any]:
        """Check risk/reward ratio."""
        if rr_ratio < MIN_RISK_REWARD_RATIO:
            return {
                "passed": False,
                "reason": f"Risk/reward ratio too low: {rr_ratio:.2f} < {MIN_RISK_REWARD_RATIO}",
                "current": rr_ratio,
                "limit": MIN_RISK_REWARD_RATIO
            }

        return {"passed": True, "reason": None, "current": rr_ratio, "limit": MIN_RISK_REWARD_RATIO}

    async def _check_strategy_budget(self, strategy_name: str, symbol: str) -> Dict[str, Any]:
        """Check strategy risk budget."""
        stmt = select(StrategyRiskBudget).where(
            and_(
                StrategyRiskBudget.strategy_name == strategy_name,
                StrategyRiskBudget.symbol == symbol
            )
        )
        result = await self.db.execute(stmt)
        budget = result.scalar_one_or_none()

        if not budget:
            # Create default budget
            budget = StrategyRiskBudget(
                strategy_name=strategy_name,
                symbol=symbol,
                max_exposure_percent=MAX_RISK_PER_STRATEGY_PERCENT,
                max_daily_loss_percent=2.0,
                current_exposure=0.0,
                current_exposure_percent=0.0,
                daily_pnl=0.0,
                is_enabled=True,
                last_updated=datetime.utcnow()
            )
            self.db.add(budget)
            await self.db.commit()
            await self.db.refresh(budget)

        # Check if strategy is enabled
        if not budget.is_enabled:
            return {
                "passed": False,
                "reason": f"Strategy {strategy_name} is disabled: {budget.disabled_reason}",
                "current": "disabled",
                "limit": "enabled"
            }

        # Check consecutive losses
        if budget.consecutive_losses >= budget.max_consecutive_losses:
            return {
                "passed": False,
                "reason": f"Strategy {strategy_name} has {budget.consecutive_losses} consecutive losses (max {budget.max_consecutive_losses})",
                "current": budget.consecutive_losses,
                "limit": budget.max_consecutive_losses
            }

        return {"passed": True, "reason": None, "current": budget.consecutive_losses, "limit": budget.max_consecutive_losses}

    async def _check_daily_loss_limit(self, account_balance: float) -> Dict[str, Any]:
        """Check daily loss limit."""
        stmt = select(AccountRiskState).order_by(AccountRiskState.last_updated.desc()).limit(1)
        result = await self.db.execute(stmt)
        state = result.scalar_one_or_none()

        if state:
            if state.daily_loss_percent >= MAX_DAILY_LOSS_PERCENT:
                return {
                    "passed": False,
                    "reason": f"Daily loss limit reached: {state.daily_loss_percent:.2f}% >= {MAX_DAILY_LOSS_PERCENT}%",
                    "current": state.daily_loss_percent,
                    "limit": MAX_DAILY_LOSS_PERCENT
                }

        return {"passed": True, "reason": None, "current": state.daily_loss_percent if state else 0.0, "limit": MAX_DAILY_LOSS_PERCENT}

    async def _trigger_emergency_shutdown(self, current_drawdown: float):
        """Trigger emergency shutdown."""
        stmt = select(AccountRiskState).order_by(AccountRiskState.last_updated.desc()).limit(1)
        result = await self.db.execute(stmt)
        state = result.scalar_one_or_none()

        if state:
            state.emergency_shutdown_active = True
            await self.db.commit()

        logger.critical(f"EMERGENCY SHUTDOWN TRIGGERED: Drawdown {current_drawdown:.2f}% >= {EMERGENCY_DRAWDOWN_PERCENT}%")

    async def _log_decision(
        self,
        decision_type: RiskDecisionType,
        subject: str,
        subject_id: Optional[int],
        approved: bool,
        rejection_reason: Optional[str],
        risk_metrics: Dict[str, Any],
        limits_checked: Dict[str, Any],
        severity: str
    ):
        """Log risk decision to audit trail."""
        decision = RiskDecision(
            decision_type=decision_type,
            subject=subject,
            subject_id=subject_id,
            approved=approved,
            rejection_reason=rejection_reason,
            risk_metrics=risk_metrics,
            limits_checked=limits_checked,
            severity=severity,
            decision_time=datetime.utcnow()
        )

        self.db.add(decision)
        await self.db.commit()
```

### Step 4: Risk Monitor

Create `backend/app/risk/monitor.py`:

```python
from typing import Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from app.models.position import Position, PositionStatus
from app.models.risk import AccountRiskState, StrategyRiskBudget
import logging

logger = logging.getLogger(__name__)


class RiskMonitor:
    """
    Continuous risk monitoring and state tracking.

    Updates:
    - Account risk state
    - Strategy risk budgets
    - Daily P&L and limits
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def update_account_state(
        self,
        account_balance: float,
        peak_balance: float
    ) -> AccountRiskState:
        """
        Update account risk state.

        Args:
            account_balance: Current account balance
            peak_balance: Peak account balance

        Returns:
            Updated account risk state
        """
        # Get or create state
        stmt = select(AccountRiskState).order_by(AccountRiskState.last_updated.desc()).limit(1)
        result = await self.db.execute(stmt)
        state = result.scalar_one_or_none()

        # Calculate metrics
        current_drawdown = ((peak_balance - account_balance) / peak_balance * 100.0) if peak_balance > 0 else 0.0

        # Get daily P&L
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        stmt = select(Position).where(
            and_(
                Position.exit_time >= today_start,
                Position.status == PositionStatus.CLOSED
            )
        )
        result = await self.db.execute(stmt)
        closed_positions = result.scalars().all()

        daily_pnl = sum(p.realized_pnl for p in closed_positions if p.realized_pnl)
        daily_loss_percent = (abs(daily_pnl) / account_balance * 100.0) if daily_pnl < 0 and account_balance > 0 else 0.0

        # Count trades
        stmt = select(Position).where(Position.entry_time >= today_start)
        result = await self.db.execute(stmt)
        trades_today = len(result.scalars().all())

        hour_ago = datetime.utcnow() - timedelta(hours=1)
        stmt = select(Position).where(Position.entry_time >= hour_ago)
        result = await self.db.execute(stmt)
        trades_this_hour = len(result.scalars().all())

        # Count open positions
        stmt = select(Position).where(Position.status == PositionStatus.OPEN)
        result = await self.db.execute(stmt)
        open_positions = result.scalars().all()
        open_positions_count = len(open_positions)

        # Calculate exposure
        total_exposure = sum(p.entry_price * p.position_size for p in open_positions)
        total_exposure_percent = (total_exposure / account_balance * 100.0) if account_balance > 0 else 0.0

        if state:
            # Update existing state
            state.account_balance = account_balance
            state.peak_balance = peak_balance
            state.current_drawdown_percent = current_drawdown
            state.daily_pnl = daily_pnl
            state.daily_loss_percent = daily_loss_percent
            state.trades_today = trades_today
            state.trades_this_hour = trades_this_hour
            state.open_positions_count = open_positions_count
            state.total_exposure = total_exposure
            state.total_exposure_percent = total_exposure_percent
            state.last_updated = datetime.utcnow()
        else:
            # Create new state
            state = AccountRiskState(
                account_balance=account_balance,
                peak_balance=peak_balance,
                current_drawdown_percent=current_drawdown,
                daily_pnl=daily_pnl,
                daily_loss_percent=daily_loss_percent,
                trades_today=trades_today,
                trades_this_hour=trades_this_hour,
                open_positions_count=open_positions_count,
                total_exposure=total_exposure,
                total_exposure_percent=total_exposure_percent,
                emergency_shutdown_active=False,
                throttling_active=False,
                last_updated=datetime.utcnow()
            )
            self.db.add(state)

        await self.db.commit()
        await self.db.refresh(state)

        return state

    async def update_strategy_budget(
        self,
        strategy_name: str,
        symbol: str,
        position: Position,
        trade_closed: bool = False
    ):
        """
        Update strategy risk budget after trade.

        Args:
            strategy_name: Strategy name
            symbol: Trading symbol
            position: Position object
            trade_closed: True if position was closed
        """
        stmt = select(StrategyRiskBudget).where(
            and_(
                StrategyRiskBudget.strategy_name == strategy_name,
                StrategyRiskBudget.symbol == symbol
            )
        )
        result = await self.db.execute(stmt)
        budget = result.scalar_one_or_none()

        if not budget:
            # Create new budget
            from app.risk.constants import MAX_RISK_PER_STRATEGY_PERCENT
            budget = StrategyRiskBudget(
                strategy_name=strategy_name,
                symbol=symbol,
                max_exposure_percent=MAX_RISK_PER_STRATEGY_PERCENT,
                max_daily_loss_percent=2.0,
                current_exposure=0.0,
                current_exposure_percent=0.0,
                daily_pnl=0.0,
                is_enabled=True,
                last_updated=datetime.utcnow()
            )
            self.db.add(budget)

        # Update metrics
        budget.total_trades += 1
        budget.last_trade_time = datetime.utcnow()
        budget.last_updated = datetime.utcnow()

        if trade_closed and position.realized_pnl is not None:
            # Update P&L
            budget.total_pnl += position.realized_pnl
            budget.daily_pnl += position.realized_pnl

            # Update win/loss count
            if position.realized_pnl > 0:
                budget.winning_trades += 1
                budget.consecutive_losses = 0  # Reset
            else:
                budget.losing_trades += 1
                budget.consecutive_losses += 1

            # Check auto-disable criteria
            if budget.consecutive_losses >= budget.max_consecutive_losses:
                budget.is_enabled = False
                budget.disabled_reason = f"{budget.consecutive_losses} consecutive losses"
                logger.warning(f"Strategy {strategy_name} auto-disabled: {budget.disabled_reason}")

        await self.db.commit()
```

### Step 5: Database Migration

```bash
cd backend
DATABASE_URL="sqlite+aiosqlite:///./flowrex_dev.db" python -m alembic revision --autogenerate -m "add_risk_engine_tables"
```

Run migration:
```bash
DATABASE_URL="sqlite+aiosqlite:///./flowrex_dev.db" python -m alembic upgrade head
```

### Step 6: API Routes

Create `backend/app/api/v1/risk_routes.py`:

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from typing import List
from pydantic import BaseModel
from app.database import get_db
from app.risk.validator import RiskValidator
from app.risk.monitor import RiskMonitor
from app.models.risk import RiskDecision, AccountRiskState, StrategyRiskBudget
from app.models.signal import Signal
from sqlalchemy import select, desc
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/risk", tags=["risk"])


class TradeValidationRequest(BaseModel):
    signal_id: int
    account_balance: float
    peak_balance: float


@router.post("/validate")
async def validate_trade(
    request: TradeValidationRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Validate a trade signal against risk limits.

    This is the AUTHORITATIVE risk check.
    """
    # Get signal
    stmt = select(Signal).where(Signal.id == request.signal_id)
    result = await db.execute(stmt)
    signal = result.scalar_one_or_none()

    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")

    # Validate
    validator = RiskValidator(db=db)

    approved, rejection_reason, risk_metrics = await validator.validate_trade(
        signal=signal,
        account_balance=request.account_balance,
        peak_balance=request.peak_balance
    )

    return {
        "approved": approved,
        "rejection_reason": rejection_reason,
        "risk_metrics": risk_metrics
    }


@router.get("/state")
async def get_risk_state(db: AsyncSession = Depends(get_db)):
    """Get current account risk state."""
    stmt = select(AccountRiskState).order_by(desc(AccountRiskState.last_updated)).limit(1)
    result = await db.execute(stmt)
    state = result.scalar_one_or_none()

    if not state:
        return {"message": "No risk state available"}

    return {
        "account_balance": state.account_balance,
        "peak_balance": state.peak_balance,
        "current_drawdown_percent": state.current_drawdown_percent,
        "daily_pnl": state.daily_pnl,
        "daily_loss_percent": state.daily_loss_percent,
        "trades_today": state.trades_today,
        "trades_this_hour": state.trades_this_hour,
        "open_positions_count": state.open_positions_count,
        "total_exposure": state.total_exposure,
        "total_exposure_percent": state.total_exposure_percent,
        "emergency_shutdown_active": state.emergency_shutdown_active,
        "throttling_active": state.throttling_active,
        "last_updated": state.last_updated
    }


@router.get("/decisions")
async def get_risk_decisions(
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
):
    """Get risk decision audit log."""
    stmt = select(RiskDecision).order_by(desc(RiskDecision.decision_time)).limit(limit)
    result = await db.execute(stmt)
    decisions = result.scalars().all()

    return [
        {
            "id": d.id,
            "decision_type": d.decision_type.value,
            "subject": d.subject,
            "approved": d.approved,
            "rejection_reason": d.rejection_reason,
            "risk_metrics": d.risk_metrics,
            "limits_checked": d.limits_checked,
            "severity": d.severity,
            "decision_time": d.decision_time
        }
        for d in decisions
    ]


@router.get("/budgets")
async def get_strategy_budgets(db: AsyncSession = Depends(get_db)):
    """Get all strategy risk budgets."""
    stmt = select(StrategyRiskBudget)
    result = await db.execute(stmt)
    budgets = result.scalars().all()

    return [
        {
            "id": b.id,
            "strategy_name": b.strategy_name,
            "symbol": b.symbol,
            "max_exposure_percent": b.max_exposure_percent,
            "current_exposure_percent": b.current_exposure_percent,
            "daily_pnl": b.daily_pnl,
            "total_trades": b.total_trades,
            "winning_trades": b.winning_trades,
            "losing_trades": b.losing_trades,
            "consecutive_losses": b.consecutive_losses,
            "is_enabled": b.is_enabled,
            "disabled_reason": b.disabled_reason
        }
        for b in budgets
    ]


@router.get("/limits")
async def get_risk_limits():
    """Get all hard risk limits."""
    from app.risk.constants import *

    return {
        "position_limits": {
            "max_risk_per_trade_percent": MAX_RISK_PER_TRADE_PERCENT,
            "max_position_size_lots": MAX_POSITION_SIZE_LOTS,
            "max_open_positions": MAX_OPEN_POSITIONS
        },
        "account_limits": {
            "max_daily_loss_percent": MAX_DAILY_LOSS_PERCENT,
            "emergency_drawdown_percent": EMERGENCY_DRAWDOWN_PERCENT,
            "max_account_leverage": MAX_ACCOUNT_LEVERAGE
        },
        "daily_limits": {
            "max_trades_per_day": MAX_TRADES_PER_DAY,
            "max_trades_per_hour": MAX_TRADES_PER_HOUR
        },
        "strategy_limits": {
            "max_strategies_active": MAX_STRATEGIES_ACTIVE,
            "max_risk_per_strategy_percent": MAX_RISK_PER_STRATEGY_PERCENT
        },
        "minimum_requirements": {
            "min_risk_reward_ratio": MIN_RISK_REWARD_RATIO,
            "min_account_balance": MIN_ACCOUNT_BALANCE
        }
    }
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
    risk_routes
)

app.include_router(risk_routes.router, prefix="/api/v1")
```

### Step 7: Tests

Create `backend/tests/unit/test_risk.py`:

```python
import pytest
from datetime import datetime
from app.risk.validator import RiskValidator
from app.risk.constants import *
from app.models.signal import Signal, SignalType, SignalStatus


@pytest.mark.asyncio
class TestRiskValidator:
    async def test_hard_limits_immutable(self):
        """Verify hard limits are defined correctly."""
        assert MAX_RISK_PER_TRADE_PERCENT == 2.0
        assert MAX_DAILY_LOSS_PERCENT == 5.0
        assert EMERGENCY_DRAWDOWN_PERCENT == 15.0
        assert MAX_OPEN_POSITIONS == 10
        assert MAX_TRADES_PER_DAY == 20
        assert MIN_RISK_REWARD_RATIO == 1.5

    async def test_validate_trade_approved(self, async_db_session):
        validator = RiskValidator(db=async_db_session)

        signal = Signal(
            strategy_name="NBB",
            symbol="EURUSD",
            signal_type=SignalType.LONG,
            status=SignalStatus.PENDING,
            entry_price=1.1000,
            stop_loss=1.0950,
            take_profit=1.1150,
            risk_percent=2.0,
            timeframe="1h",
            confidence=75.0,
            signal_time=datetime.utcnow()
        )

        async_db_session.add(signal)
        await async_db_session.commit()
        await async_db_session.refresh(signal)

        approved, reason, metrics = await validator.validate_trade(
            signal=signal,
            account_balance=10000.0,
            peak_balance=10000.0
        )

        assert approved is True
        assert reason is None

    async def test_validate_trade_emergency_drawdown(self, async_db_session):
        validator = RiskValidator(db=async_db_session)

        signal = Signal(
            strategy_name="NBB",
            symbol="EURUSD",
            signal_type=SignalType.LONG,
            status=SignalStatus.PENDING,
            entry_price=1.1000,
            stop_loss=1.0950,
            take_profit=1.1150,
            risk_percent=2.0,
            timeframe="1h",
            confidence=75.0,
            signal_time=datetime.utcnow()
        )

        async_db_session.add(signal)
        await async_db_session.commit()
        await async_db_session.refresh(signal)

        # Account balance is 8500, peak is 10000 = 15% drawdown
        approved, reason, metrics = await validator.validate_trade(
            signal=signal,
            account_balance=8500.0,
            peak_balance=10000.0
        )

        assert approved is False
        assert "Emergency drawdown" in reason

    async def test_risk_reward_ratio_check(self, async_db_session):
        validator = RiskValidator(db=async_db_session)

        # Low R:R ratio
        signal = Signal(
            strategy_name="NBB",
            symbol="EURUSD",
            signal_type=SignalType.LONG,
            status=SignalStatus.PENDING,
            entry_price=1.1000,
            stop_loss=1.0950,
            take_profit=1.1020,  # Very small TP
            risk_percent=2.0,
            timeframe="1h",
            confidence=75.0,
            signal_time=datetime.utcnow()
        )

        async_db_session.add(signal)
        await async_db_session.commit()
        await async_db_session.refresh(signal)

        approved, reason, metrics = await validator.validate_trade(
            signal=signal,
            account_balance=10000.0,
            peak_balance=10000.0
        )

        assert approved is False
        assert "Risk/reward ratio" in reason
```

Run tests:
```bash
cd backend
DATABASE_URL="sqlite+aiosqlite:///./flowrex_dev.db" python -m pytest tests/unit/test_risk.py -v
```

## Validation Checklist

Before proceeding to Prompt 10, verify:

- [ ] Hard risk constants defined in `risk/constants.py`
- [ ] All hard limits are immutable (cannot be changed at runtime)
- [ ] RiskDecision, AccountRiskState, StrategyRiskBudget models created
- [ ] Database migration applied successfully
- [ ] RiskValidator implements all 9 checks in order of severity
- [ ] Emergency shutdown check is first (highest priority)
- [ ] Drawdown check triggers emergency shutdown at 15%
- [ ] Position limit check enforces max 10 open positions
- [ ] Daily trade limit check enforces max 20 trades/day
- [ ] Hourly trade limit check enforces max 5 trades/hour
- [ ] Position size check enforces max 1.0 lots
- [ ] Risk/reward check enforces min 1.5:1 ratio
- [ ] Strategy budget check validates enabled status
- [ ] Daily loss limit check enforces max 5% loss
- [ ] All risk decisions are logged to audit trail
- [ ] RiskMonitor updates account state correctly
- [ ] RiskMonitor tracks strategy budgets
- [ ] Strategy auto-disablement after 5 consecutive losses
- [ ] API route `/risk/validate` performs trade validation
- [ ] API route `/risk/state` returns account risk state
- [ ] API route `/risk/decisions` returns audit log
- [ ] API route `/risk/limits` returns all hard limits
- [ ] All unit tests pass
- [ ] Emergency drawdown triggers shutdown correctly
- [ ] Low R:R ratio is rejected
- [ ] Risk engine has veto power (cannot be bypassed)
- [ ] CROSSCHECK.md validation for Prompt 09 completed

## Hard Stop Criteria

**DO NOT PROCEED to Prompt 10 unless:**

1. ✅ Database migration runs without errors
2. ✅ All pytest tests pass (0 failures, 0 errors)
3. ✅ Hard limits are defined as constants (not configurable)
4. ✅ Emergency drawdown at 15% triggers shutdown
5. ✅ All 9 risk checks execute in correct order
6. ✅ Risk validator rejects trades exceeding ANY limit
7. ✅ Risk decisions are logged with full audit trail
8. ✅ Strategy auto-disablement works after consecutive losses
9. ✅ Risk engine operates independently of AI agents
10. ✅ CROSSCHECK.md section for Prompt 09 fully validated

If any criterion fails, **HALT** and fix before continuing.

---

**Completion Criteria:**
- Risk engine fully operational with immutable hard limits
- All risk checks enforced before execution
- Emergency shutdown mechanism working
- Strategy auto-disablement implemented
- Complete audit trail for all risk decisions
- Risk engine has absolute veto power
- System ready for Execution Engine (Prompt 10)
