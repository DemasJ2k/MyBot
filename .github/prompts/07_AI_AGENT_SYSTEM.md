# Prompt 07: AI Agent System

## Purpose

Build the complete AI agent architecture that powers Flowrex's autonomous decision-making. This multi-agent system orchestrates strategy selection, risk management, trade execution, and continuous learning. The AI operates in two modes: GUIDE (simulation-only, recommendations) and AUTONOMOUS (live trading with hard risk enforcement).

## Scope

- Multi-agent architecture:
  - **Supervisor Agent**: Master orchestrator, mode enforcement, system health
  - **Strategy Agent**: Market analysis, strategy selection, optimization triggers
  - **Risk Agent**: Risk monitoring, hard cap enforcement, position sizing
  - **Execution Agent**: Order execution, position management
- GUIDE vs AUTONOMOUS mode hard enforcement
- AI decision logging and reasoning storage
- Learning system (from backtests and live trades)
- Automatic optimization triggering
- Strategy performance monitoring and auto-disable
- AI memory and context management
- Agent communication protocol
- Complete test suite

## AI Agent Architecture

```
User Input / Market Data
    ↓
Supervisor Agent (orchestrator)
    ↓
┌───────────────┬──────────────┬──────────────┐
│ Strategy      │ Risk         │ Execution    │
│ Agent         │ Agent        │ Agent        │
└───────────────┴──────────────┴──────────────┘
    ↓               ↓               ↓
Decisions      Risk Checks     Order Execution
    ↓               ↓               ↓
AI Decision Log → Learning System → Performance Feedback
```

## Implementation

### Step 1: Database Models

Create `backend/app/models/ai_agent.py`:

```python
from sqlalchemy import String, Float, Integer, JSON, Enum as SQLEnum, Boolean, Index, Text
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from typing import Optional, Dict, Any
import enum
from app.models.base import Base, TimestampMixin


class SystemMode(str, enum.Enum):
    GUIDE = "guide"
    AUTONOMOUS = "autonomous"


class AgentRole(str, enum.Enum):
    SUPERVISOR = "supervisor"
    STRATEGY = "strategy"
    RISK = "risk"
    EXECUTION = "execution"


class DecisionType(str, enum.Enum):
    STRATEGY_SELECTION = "strategy_selection"
    OPTIMIZATION_TRIGGER = "optimization_trigger"
    STRATEGY_DISABLE = "strategy_disable"
    POSITION_SIZE = "position_size"
    TRADE_EXECUTION = "trade_execution"
    RISK_OVERRIDE = "risk_override"
    MODE_ENFORCEMENT = "mode_enforcement"


class AIDecision(Base, TimestampMixin):
    """AI agent decision log with reasoning."""
    __tablename__ = "ai_decisions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    agent_role: Mapped[AgentRole] = mapped_column(SQLEnum(AgentRole), nullable=False, index=True)
    decision_type: Mapped[DecisionType] = mapped_column(SQLEnum(DecisionType), nullable=False, index=True)
    system_mode: Mapped[SystemMode] = mapped_column(SQLEnum(SystemMode), nullable=False)

    # Decision details
    decision: Mapped[str] = mapped_column(Text, nullable=False)  # What was decided
    reasoning: Mapped[str] = mapped_column(Text, nullable=False)  # Why
    context: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)  # Contextual data

    # Outcome tracking
    executed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    outcome: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    outcome_metrics: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # Timestamps
    decision_time: Mapped[datetime] = mapped_column(nullable=False, index=True)

    __table_args__ = (
        Index("ix_ai_decision_agent_type", "agent_role", "decision_type"),
    )

    def __repr__(self) -> str:
        return f"<AIDecision {self.id} {self.agent_role.value} {self.decision_type.value}>"


class AgentMemory(Base, TimestampMixin):
    """Agent learning memory from past experiences."""
    __tablename__ = "agent_memory"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    agent_role: Mapped[AgentRole] = mapped_column(SQLEnum(AgentRole), nullable=False, index=True)

    # Memory type and key
    memory_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    memory_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    # Memory content
    data: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)

    # Learning metrics
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)  # 0-1
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    last_updated: Mapped[datetime] = mapped_column(nullable=False, index=True)

    __table_args__ = (
        Index("ix_agent_memory_type_key", "memory_type", "memory_key"),
    )

    def __repr__(self) -> str:
        return f"<AgentMemory {self.id} {self.agent_role.value} {self.memory_type}:{self.memory_key}>"


class SystemConfig(Base, TimestampMixin):
    """System-wide AI configuration."""
    __tablename__ = "system_config"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    value: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<SystemConfig {self.key}>"
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
]
```

### Step 2: Base Agent Class

Create `backend/app/ai_agents/base_agent.py`:

```python
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.ai_agent import (
    AIDecision,
    AgentMemory,
    SystemMode,
    AgentRole,
    DecisionType,
)
import logging

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Base class for all AI agents."""

    def __init__(self, db: AsyncSession, system_mode: SystemMode):
        self.db = db
        self.system_mode = system_mode
        self.role = self.get_role()

    @abstractmethod
    def get_role(self) -> AgentRole:
        """Return agent role."""
        pass

    async def log_decision(
        self,
        decision_type: DecisionType,
        decision: str,
        reasoning: str,
        context: Dict[str, Any],
        executed: bool = False
    ) -> AIDecision:
        """
        Log an AI decision with reasoning.

        Args:
            decision_type: Type of decision
            decision: What was decided
            reasoning: Why this decision was made
            context: Contextual data
            executed: Whether decision was executed

        Returns:
            Created AIDecision record
        """
        ai_decision = AIDecision(
            agent_role=self.role,
            decision_type=decision_type,
            system_mode=self.system_mode,
            decision=decision,
            reasoning=reasoning,
            context=context,
            executed=executed,
            decision_time=datetime.utcnow()
        )

        self.db.add(ai_decision)
        await self.db.commit()
        await self.db.refresh(ai_decision)

        logger.info(f"{self.role.value} agent: {decision_type.value} - {decision}")

        return ai_decision

    async def store_memory(
        self,
        memory_type: str,
        memory_key: str,
        data: Dict[str, Any],
        confidence: float = 0.5
    ):
        """
        Store learning memory.

        Args:
            memory_type: Type of memory (e.g., "strategy_performance", "risk_pattern")
            memory_key: Unique key (e.g., "NBB_EURUSD", "drawdown_recovery")
            data: Memory data
            confidence: Confidence level (0-1)
        """
        # Check if memory exists
        stmt = select(AgentMemory).where(
            AgentMemory.agent_role == self.role,
            AgentMemory.memory_type == memory_type,
            AgentMemory.memory_key == memory_key
        )

        result = await self.db.execute(stmt)
        memory = result.scalar_one_or_none()

        if memory:
            # Update existing memory
            memory.data = data
            memory.confidence = confidence
            memory.sample_count += 1
            memory.last_updated = datetime.utcnow()
        else:
            # Create new memory
            memory = AgentMemory(
                agent_role=self.role,
                memory_type=memory_type,
                memory_key=memory_key,
                data=data,
                confidence=confidence,
                sample_count=1,
                last_updated=datetime.utcnow()
            )
            self.db.add(memory)

        await self.db.commit()

    async def recall_memory(
        self,
        memory_type: str,
        memory_key: str
    ) -> Optional[Dict[str, Any]]:
        """
        Recall learning memory.

        Returns:
            Memory data or None if not found
        """
        stmt = select(AgentMemory).where(
            AgentMemory.agent_role == self.role,
            AgentMemory.memory_type == memory_type,
            AgentMemory.memory_key == memory_key
        )

        result = await self.db.execute(stmt)
        memory = result.scalar_one_or_none()

        if memory:
            return memory.data

        return None
```

### Step 3: Supervisor Agent

Create `backend/app/ai_agents/supervisor_agent.py`:

```python
from typing import Dict, Any, List
from datetime import datetime, timedelta
from sqlalchemy import select
from app.ai_agents.base_agent import BaseAgent
from app.models.ai_agent import AgentRole, DecisionType, SystemMode
from app.models.position import Position, PositionStatus
from app.models.backtest import BacktestResult
import logging

logger = logging.getLogger(__name__)


class SupervisorAgent(BaseAgent):
    """
    Master orchestrator agent.

    Responsibilities:
    - Enforce GUIDE vs AUTONOMOUS mode
    - Monitor system health
    - Coordinate other agents
    - Emergency shutdown if hard caps breached
    """

    def get_role(self) -> AgentRole:
        return AgentRole.SUPERVISOR

    async def enforce_mode(self) -> bool:
        """
        Enforce current system mode.

        In GUIDE mode:
        - Block all live trade execution
        - Allow only simulated backtests
        - Log recommendations

        In AUTONOMOUS mode:
        - Allow live trading
        - Enforce hard caps strictly
        - Monitor for emergency conditions

        Returns:
            True if mode is properly enforced
        """
        if self.system_mode == SystemMode.GUIDE:
            # Check for any live positions (should be impossible)
            stmt = select(Position).where(Position.status == PositionStatus.OPEN)
            result = await self.db.execute(stmt)
            open_positions = result.scalars().all()

            if open_positions:
                await self.log_decision(
                    decision_type=DecisionType.MODE_ENFORCEMENT,
                    decision="EMERGENCY: Close all positions in GUIDE mode",
                    reasoning="Live positions detected in GUIDE mode - this violates mode constraints",
                    context={"open_positions": len(open_positions)},
                    executed=False
                )
                logger.error(f"GUIDE mode violation: {len(open_positions)} open positions detected")
                return False

            await self.log_decision(
                decision_type=DecisionType.MODE_ENFORCEMENT,
                decision="GUIDE mode active - all trading is simulated",
                reasoning="System is in GUIDE mode, blocking live execution",
                context={"mode": "guide"},
                executed=True
            )

            return True

        else:  # AUTONOMOUS mode
            # Check hard caps are being respected
            is_compliant = await self._check_hard_caps()

            if not is_compliant:
                await self.log_decision(
                    decision_type=DecisionType.RISK_OVERRIDE,
                    decision="EMERGENCY SHUTDOWN - Hard caps breached",
                    reasoning="Critical risk limits exceeded, halting all trading",
                    context={"mode": "autonomous", "compliant": False},
                    executed=True
                )
                logger.critical("AUTONOMOUS mode: Hard caps breached, emergency shutdown initiated")
                return False

            return True

    async def _check_hard_caps(self) -> bool:
        """
        Check if hard caps are being respected.

        Hard caps (from SKILLS.md):
        - Max 2% risk per trade
        - Max 5% daily loss
        - Max 20 trades per day
        - Max 10 open positions

        Returns:
            True if all caps respected, False otherwise
        """
        # Check open positions count
        stmt = select(Position).where(Position.status == PositionStatus.OPEN)
        result = await self.db.execute(stmt)
        open_positions = len(result.scalars().all())

        if open_positions > 10:
            logger.error(f"Hard cap breach: {open_positions} open positions (max 10)")
            return False

        # Check daily trades
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        stmt = select(Position).where(Position.entry_time >= today_start)
        result = await self.db.execute(stmt)
        today_trades = len(result.scalars().all())

        if today_trades > 20:
            logger.error(f"Hard cap breach: {today_trades} trades today (max 20)")
            return False

        # Daily loss check would require account balance tracking
        # Implementation depends on account model

        return True

    async def coordinate_agents(self) -> Dict[str, Any]:
        """
        Coordinate execution of Strategy, Risk, and Execution agents.

        Returns:
            Coordination result
        """
        # This is called by the main orchestration loop
        # Determines order of agent execution and data flow

        coordination_plan = {
            "sequence": [
                "strategy_agent",  # Analyze markets first
                "risk_agent",      # Validate risk second
                "execution_agent"  # Execute trades last
            ],
            "mode": self.system_mode.value,
            "timestamp": datetime.utcnow().isoformat()
        }

        await self.log_decision(
            decision_type=DecisionType.MODE_ENFORCEMENT,
            decision=f"Coordinating agents in {self.system_mode.value} mode",
            reasoning="Standard agent coordination sequence",
            context=coordination_plan,
            executed=True
        )

        return coordination_plan
```

### Step 4: Strategy Agent

Create `backend/app/ai_agents/strategy_agent.py`:

```python
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from sqlalchemy import select, desc, and_
from app.ai_agents.base_agent import BaseAgent
from app.models.ai_agent import AgentRole, DecisionType
from app.models.backtest import BacktestResult
from app.models.optimization import Playbook, OptimizationJob, OptimizationStatus
from app.models.signal import Signal, SignalStatus
import logging

logger = logging.getLogger(__name__)


class StrategyAgent(BaseAgent):
    """
    Strategy analysis and selection agent.

    Responsibilities:
    - Analyze market conditions
    - Select appropriate strategies
    - Trigger optimizations when performance degrades
    - Disable underperforming strategies
    - Learn from backtest results
    """

    def get_role(self) -> AgentRole:
        return AgentRole.STRATEGY

    async def analyze_and_select_strategies(
        self,
        symbol: str,
        available_strategies: List[str]
    ) -> List[str]:
        """
        Analyze which strategies should be active for a symbol.

        Args:
            symbol: Trading symbol
            available_strategies: List of strategy names

        Returns:
            List of selected strategy names
        """
        selected = []

        for strategy_name in available_strategies:
            # Check if strategy has active playbook
            stmt = select(Playbook).where(
                and_(
                    Playbook.strategy_name == strategy_name,
                    Playbook.symbol == symbol,
                    Playbook.is_active == True
                )
            )

            result = await self.db.execute(stmt)
            playbook = result.scalar_one_or_none()

            if playbook:
                # Check recent performance
                should_use = await self._evaluate_strategy_performance(strategy_name, symbol)

                if should_use:
                    selected.append(strategy_name)
                else:
                    # Disable underperforming strategy
                    await self._disable_strategy(strategy_name, symbol, playbook)

        await self.log_decision(
            decision_type=DecisionType.STRATEGY_SELECTION,
            decision=f"Selected {len(selected)} strategies for {symbol}",
            reasoning=f"Based on performance evaluation and active playbooks",
            context={
                "symbol": symbol,
                "selected_strategies": selected,
                "total_available": len(available_strategies)
            },
            executed=True
        )

        return selected

    async def _evaluate_strategy_performance(
        self,
        strategy_name: str,
        symbol: str
    ) -> bool:
        """
        Evaluate if strategy should continue running.

        Criteria:
        - Recent backtest Sharpe ratio > 0.5
        - Max drawdown < 20%
        - Win rate > 40%
        - At least 10 trades in backtest

        Returns:
            True if strategy should continue, False to disable
        """
        # Get most recent backtest for this strategy
        stmt = select(BacktestResult).where(
            and_(
                BacktestResult.strategy_name == strategy_name,
                BacktestResult.symbol == symbol
            )
        ).order_by(desc(BacktestResult.created_at)).limit(1)

        result = await self.db.execute(stmt)
        backtest = result.scalar_one_or_none()

        if not backtest:
            logger.warning(f"No backtest found for {strategy_name} on {symbol}")
            return False

        # Check performance criteria
        if backtest.total_trades < 10:
            logger.info(f"{strategy_name}: Too few trades ({backtest.total_trades})")
            return False

        if backtest.sharpe_ratio is None or backtest.sharpe_ratio < 0.5:
            logger.info(f"{strategy_name}: Low Sharpe ratio ({backtest.sharpe_ratio})")
            return False

        if backtest.max_drawdown_percent > 20.0:
            logger.info(f"{strategy_name}: High drawdown ({backtest.max_drawdown_percent}%)")
            return False

        if backtest.win_rate_percent < 40.0:
            logger.info(f"{strategy_name}: Low win rate ({backtest.win_rate_percent}%)")
            return False

        # Store performance in memory
        await self.store_memory(
            memory_type="strategy_performance",
            memory_key=f"{strategy_name}_{symbol}",
            data={
                "sharpe_ratio": backtest.sharpe_ratio,
                "max_drawdown_percent": backtest.max_drawdown_percent,
                "win_rate_percent": backtest.win_rate_percent,
                "total_trades": backtest.total_trades,
                "last_evaluated": datetime.utcnow().isoformat()
            },
            confidence=0.8
        )

        return True

    async def _disable_strategy(
        self,
        strategy_name: str,
        symbol: str,
        playbook: Playbook
    ):
        """Disable underperforming strategy."""
        playbook.is_active = False
        await self.db.commit()

        await self.log_decision(
            decision_type=DecisionType.STRATEGY_DISABLE,
            decision=f"Disabled {strategy_name} for {symbol}",
            reasoning="Strategy failed performance evaluation criteria",
            context={
                "strategy_name": strategy_name,
                "symbol": symbol,
                "playbook_id": playbook.id
            },
            executed=True
        )

        logger.warning(f"Disabled strategy {strategy_name} for {symbol} due to poor performance")

    async def should_trigger_optimization(
        self,
        strategy_name: str,
        symbol: str
    ) -> bool:
        """
        Determine if optimization should be triggered.

        Triggers:
        - No optimization in last 30 days
        - Recent performance degradation
        - New market regime detected

        Returns:
            True if optimization should run
        """
        # Check last optimization time
        stmt = select(OptimizationJob).where(
            and_(
                OptimizationJob.strategy_name == strategy_name,
                OptimizationJob.symbol == symbol,
                OptimizationJob.status == OptimizationStatus.COMPLETED
            )
        ).order_by(desc(OptimizationJob.completed_at)).limit(1)

        result = await self.db.execute(stmt)
        last_opt = result.scalar_one_or_none()

        if not last_opt:
            # Never optimized
            await self.log_decision(
                decision_type=DecisionType.OPTIMIZATION_TRIGGER,
                decision=f"Trigger optimization for {strategy_name} on {symbol}",
                reasoning="No previous optimization found",
                context={"strategy_name": strategy_name, "symbol": symbol},
                executed=False
            )
            return True

        # Check if optimization is recent (within 30 days)
        days_since_opt = (datetime.utcnow() - last_opt.completed_at).days

        if days_since_opt > 30:
            await self.log_decision(
                decision_type=DecisionType.OPTIMIZATION_TRIGGER,
                decision=f"Trigger optimization for {strategy_name} on {symbol}",
                reasoning=f"Last optimization was {days_since_opt} days ago (threshold: 30 days)",
                context={
                    "strategy_name": strategy_name,
                    "symbol": symbol,
                    "days_since_optimization": days_since_opt
                },
                executed=False
            )
            return True

        return False
```

### Step 5: Risk Agent

Create `backend/app/ai_agents/risk_agent.py`:

```python
from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy import select
from app.ai_agents.base_agent import BaseAgent
from app.models.ai_agent import AgentRole, DecisionType
from app.models.signal import Signal, SignalType
from app.models.position import Position, PositionStatus
import logging

logger = logging.getLogger(__name__)


# Hard caps (immutable)
HARD_CAPS = {
    "max_risk_per_trade": 2.0,           # % of account
    "max_daily_loss": 5.0,               # % of account
    "max_trades_per_day": 20,
    "max_open_positions": 10,
    "max_order_size": 1.0,               # lots
    "emergency_drawdown_stop": 15.0,     # % triggers full stop
}


class RiskAgent(BaseAgent):
    """
    Risk management and enforcement agent.

    Responsibilities:
    - Enforce hard caps (CANNOT be overridden)
    - Calculate position sizes
    - Monitor drawdown
    - Validate signals before execution
    - Emergency shutdown on critical breach
    """

    def get_role(self) -> AgentRole:
        return AgentRole.RISK

    async def validate_signal(
        self,
        signal: Signal,
        account_balance: float
    ) -> Dict[str, Any]:
        """
        Validate signal against risk rules.

        Args:
            signal: Trading signal to validate
            account_balance: Current account balance

        Returns:
            Validation result with approved flag and position size
        """
        validation = {
            "approved": False,
            "position_size": 0.0,
            "reason": "",
            "checks": {}
        }

        # Check 1: Max open positions
        stmt = select(Position).where(Position.status == PositionStatus.OPEN)
        result = await self.db.execute(stmt)
        open_positions = len(result.scalars().all())

        validation["checks"]["open_positions"] = {
            "current": open_positions,
            "limit": HARD_CAPS["max_open_positions"],
            "passed": open_positions < HARD_CAPS["max_open_positions"]
        }

        if open_positions >= HARD_CAPS["max_open_positions"]:
            validation["reason"] = f"Max open positions reached ({open_positions}/{HARD_CAPS['max_open_positions']})"
            await self._log_rejection(signal, validation["reason"])
            return validation

        # Check 2: Daily trade limit
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        stmt = select(Position).where(Position.entry_time >= today_start)
        result = await self.db.execute(stmt)
        today_trades = len(result.scalars().all())

        validation["checks"]["daily_trades"] = {
            "current": today_trades,
            "limit": HARD_CAPS["max_trades_per_day"],
            "passed": today_trades < HARD_CAPS["max_trades_per_day"]
        }

        if today_trades >= HARD_CAPS["max_trades_per_day"]:
            validation["reason"] = f"Daily trade limit reached ({today_trades}/{HARD_CAPS['max_trades_per_day']})"
            await self._log_rejection(signal, validation["reason"])
            return validation

        # Check 3: Calculate position size
        position_size = self._calculate_position_size(
            account_balance=account_balance,
            risk_percent=min(signal.risk_percent, HARD_CAPS["max_risk_per_trade"]),
            entry_price=signal.entry_price,
            stop_loss=signal.stop_loss
        )

        validation["checks"]["position_size"] = {
            "calculated": position_size,
            "limit": HARD_CAPS["max_order_size"],
            "passed": position_size <= HARD_CAPS["max_order_size"]
        }

        if position_size > HARD_CAPS["max_order_size"]:
            position_size = HARD_CAPS["max_order_size"]
            logger.warning(f"Position size capped at {HARD_CAPS['max_order_size']} lots")

        if position_size <= 0:
            validation["reason"] = "Invalid position size (≤0)"
            await self._log_rejection(signal, validation["reason"])
            return validation

        # Check 4: Risk/Reward ratio
        rr_ratio = signal.risk_reward_ratio

        validation["checks"]["risk_reward"] = {
            "ratio": rr_ratio,
            "minimum": 1.5,
            "passed": rr_ratio >= 1.5
        }

        if rr_ratio < 1.5:
            validation["reason"] = f"R:R ratio too low ({rr_ratio:.2f} < 1.5)"
            await self._log_rejection(signal, validation["reason"])
            return validation

        # All checks passed
        validation["approved"] = True
        validation["position_size"] = position_size
        validation["reason"] = "All risk checks passed"

        await self.log_decision(
            decision_type=DecisionType.POSITION_SIZE,
            decision=f"Approved signal with position size {position_size:.2f}",
            reasoning="Signal passed all risk validation checks",
            context={
                "signal_id": signal.id,
                "strategy": signal.strategy_name,
                "symbol": signal.symbol,
                "position_size": position_size,
                "checks": validation["checks"]
            },
            executed=True
        )

        return validation

    def _calculate_position_size(
        self,
        account_balance: float,
        risk_percent: float,
        entry_price: float,
        stop_loss: float
    ) -> float:
        """
        Calculate position size based on risk parameters.

        Formula: position_size = (account_balance * risk%) / (entry_price - stop_loss)
        """
        risk_amount = account_balance * (risk_percent / 100.0)
        risk_per_unit = abs(entry_price - stop_loss)

        if risk_per_unit == 0:
            return 0.0

        position_size = risk_amount / risk_per_unit
        return round(position_size, 2)

    async def _log_rejection(self, signal: Signal, reason: str):
        """Log signal rejection."""
        await self.log_decision(
            decision_type=DecisionType.POSITION_SIZE,
            decision=f"Rejected signal for {signal.symbol}",
            reasoning=reason,
            context={
                "signal_id": signal.id,
                "strategy": signal.strategy_name,
                "symbol": signal.symbol,
                "entry_price": signal.entry_price
            },
            executed=False
        )

    async def check_emergency_conditions(self, account_balance: float, peak_balance: float) -> bool:
        """
        Check for emergency shutdown conditions.

        Returns:
            True if emergency shutdown required
        """
        if peak_balance == 0:
            return False

        current_drawdown = ((peak_balance - account_balance) / peak_balance) * 100.0

        if current_drawdown >= HARD_CAPS["emergency_drawdown_stop"]:
            await self.log_decision(
                decision_type=DecisionType.RISK_OVERRIDE,
                decision="EMERGENCY SHUTDOWN - Critical drawdown reached",
                reasoning=f"Account drawdown {current_drawdown:.2f}% exceeds emergency threshold {HARD_CAPS['emergency_drawdown_stop']}%",
                context={
                    "account_balance": account_balance,
                    "peak_balance": peak_balance,
                    "drawdown_percent": current_drawdown,
                    "threshold": HARD_CAPS["emergency_drawdown_stop"]
                },
                executed=True
            )

            logger.critical(f"EMERGENCY SHUTDOWN: Drawdown {current_drawdown:.2f}% >= {HARD_CAPS['emergency_drawdown_stop']}%")
            return True

        return False
```

### Step 6: Execution Agent

Create `backend/app/ai_agents/execution_agent.py`:

```python
from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy import select
from app.ai_agents.base_agent import BaseAgent
from app.models.ai_agent import AgentRole, DecisionType, SystemMode
from app.models.signal import Signal, SignalStatus
from app.models.position import Position, PositionStatus, PositionSide
import logging

logger = logging.getLogger(__name__)


class ExecutionAgent(BaseAgent):
    """
    Trade execution agent.

    Responsibilities:
    - Execute approved signals
    - Manage open positions
    - Update stop loss / take profit
    - Close positions
    - GUIDE mode: Simulate only, no real execution
    - AUTONOMOUS mode: Execute live trades
    """

    def get_role(self) -> AgentRole:
        return AgentRole.EXECUTION

    async def execute_signal(
        self,
        signal: Signal,
        position_size: float,
        account_balance: float
    ) -> Optional[Position]:
        """
        Execute a validated trading signal.

        In GUIDE mode: Logs recommendation only
        In AUTONOMOUS mode: Creates real position

        Args:
            signal: Approved signal
            position_size: Validated position size
            account_balance: Current account balance

        Returns:
            Position object if executed, None otherwise
        """
        if self.system_mode == SystemMode.GUIDE:
            # GUIDE MODE: Simulate only, do not execute
            await self.log_decision(
                decision_type=DecisionType.TRADE_EXECUTION,
                decision=f"SIMULATED: Would execute {signal.signal_type.value} {signal.symbol}",
                reasoning="System is in GUIDE mode - execution is simulated",
                context={
                    "signal_id": signal.id,
                    "strategy": signal.strategy_name,
                    "symbol": signal.symbol,
                    "entry_price": signal.entry_price,
                    "position_size": position_size,
                    "mode": "guide"
                },
                executed=False
            )

            logger.info(f"GUIDE MODE: Simulated execution of {signal.strategy_name} {signal.signal_type.value} {signal.symbol}")
            return None

        else:
            # AUTONOMOUS MODE: Execute live trade
            position = Position(
                strategy_name=signal.strategy_name,
                symbol=signal.symbol,
                side=PositionSide.LONG if signal.signal_type.value == "long" else PositionSide.SHORT,
                status=PositionStatus.OPEN,
                entry_price=signal.entry_price,
                position_size=position_size,
                entry_time=datetime.utcnow(),
                stop_loss=signal.stop_loss,
                take_profit=signal.take_profit,
                unrealized_pnl=0.0
            )

            self.db.add(position)

            # Update signal status
            signal.status = SignalStatus.EXECUTED
            signal.executed_at = datetime.utcnow()
            signal.position_size = position_size

            await self.db.commit()
            await self.db.refresh(position)

            await self.log_decision(
                decision_type=DecisionType.TRADE_EXECUTION,
                decision=f"EXECUTED: {signal.signal_type.value} {signal.symbol} @ {signal.entry_price}",
                reasoning=f"Live execution in AUTONOMOUS mode for {signal.strategy_name}",
                context={
                    "signal_id": signal.id,
                    "position_id": position.id,
                    "strategy": signal.strategy_name,
                    "symbol": signal.symbol,
                    "side": position.side.value,
                    "entry_price": signal.entry_price,
                    "position_size": position_size,
                    "stop_loss": signal.stop_loss,
                    "take_profit": signal.take_profit,
                    "mode": "autonomous"
                },
                executed=True
            )

            logger.info(f"AUTONOMOUS MODE: Executed {signal.strategy_name} {signal.signal_type.value} {signal.symbol} @ {signal.entry_price}")

            return position

    async def close_position(
        self,
        position: Position,
        exit_price: float,
        reason: str
    ) -> Position:
        """
        Close an open position.

        Args:
            position: Position to close
            exit_price: Exit price
            reason: Reason for closing

        Returns:
            Updated position
        """
        position.status = PositionStatus.CLOSED
        position.exit_price = exit_price
        position.exit_time = datetime.utcnow()

        # Calculate realized P&L
        if position.side == PositionSide.LONG:
            pnl = (exit_price - position.entry_price) * position.position_size
        else:
            pnl = (position.entry_price - exit_price) * position.position_size

        position.realized_pnl = pnl

        await self.db.commit()

        await self.log_decision(
            decision_type=DecisionType.TRADE_EXECUTION,
            decision=f"CLOSED: {position.side.value} {position.symbol} @ {exit_price}",
            reasoning=reason,
            context={
                "position_id": position.id,
                "strategy": position.strategy_name,
                "symbol": position.symbol,
                "entry_price": position.entry_price,
                "exit_price": exit_price,
                "pnl": pnl,
                "reason": reason
            },
            executed=True
        )

        logger.info(f"Closed position {position.id}: {position.symbol} P&L={pnl:.2f}")

        return position
```

### Step 7: AI Orchestrator

Create `backend/app/ai_agents/orchestrator.py`:

```python
from typing import Dict, Any, List
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.ai_agents.supervisor_agent import SupervisorAgent
from app.ai_agents.strategy_agent import StrategyAgent
from app.ai_agents.risk_agent import RiskAgent
from app.ai_agents.execution_agent import ExecutionAgent
from app.models.ai_agent import SystemMode, SystemConfig
from app.models.signal import Signal, SignalStatus
import logging

logger = logging.getLogger(__name__)


class AIOrchestrator:
    """
    Master orchestrator for AI agent system.

    Coordinates all agents and enforces mode-specific behavior.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.system_mode = None
        self.supervisor = None
        self.strategy_agent = None
        self.risk_agent = None
        self.execution_agent = None

    async def initialize(self):
        """Initialize orchestrator and load system mode."""
        # Load system mode from config
        stmt = select(SystemConfig).where(SystemConfig.key == "system_mode")
        result = await self.db.execute(stmt)
        config = result.scalar_one_or_none()

        if config:
            mode_str = config.value.get("mode", "guide")
            self.system_mode = SystemMode.GUIDE if mode_str == "guide" else SystemMode.AUTONOMOUS
        else:
            # Default to GUIDE mode
            self.system_mode = SystemMode.GUIDE
            config = SystemConfig(
                key="system_mode",
                value={"mode": "guide"},
                description="Current system operating mode (guide or autonomous)"
            )
            self.db.add(config)
            await self.db.commit()

        # Initialize agents
        self.supervisor = SupervisorAgent(db=self.db, system_mode=self.system_mode)
        self.strategy_agent = StrategyAgent(db=self.db, system_mode=self.system_mode)
        self.risk_agent = RiskAgent(db=self.db, system_mode=self.system_mode)
        self.execution_agent = ExecutionAgent(db=self.db, system_mode=self.system_mode)

        logger.info(f"AI Orchestrator initialized in {self.system_mode.value} mode")

    async def run_trading_cycle(
        self,
        symbol: str,
        available_strategies: List[str],
        account_balance: float,
        peak_balance: float
    ) -> Dict[str, Any]:
        """
        Execute one complete trading cycle.

        Steps:
        1. Supervisor enforces mode
        2. Strategy agent selects strategies
        3. Risk agent validates signals
        4. Execution agent executes trades

        Args:
            symbol: Trading symbol
            available_strategies: List of strategy names
            account_balance: Current account balance
            peak_balance: Peak account balance

        Returns:
            Cycle execution summary
        """
        cycle_result = {
            "timestamp": datetime.utcnow().isoformat(),
            "mode": self.system_mode.value,
            "symbol": symbol,
            "strategies_selected": [],
            "signals_validated": 0,
            "trades_executed": 0,
            "errors": []
        }

        try:
            # Step 1: Mode enforcement
            mode_ok = await self.supervisor.enforce_mode()
            if not mode_ok:
                cycle_result["errors"].append("Mode enforcement failed")
                return cycle_result

            # Step 2: Emergency check
            emergency = await self.risk_agent.check_emergency_conditions(account_balance, peak_balance)
            if emergency:
                cycle_result["errors"].append("Emergency shutdown triggered")
                return cycle_result

            # Step 3: Select strategies
            selected_strategies = await self.strategy_agent.analyze_and_select_strategies(
                symbol=symbol,
                available_strategies=available_strategies
            )

            cycle_result["strategies_selected"] = selected_strategies

            if not selected_strategies:
                logger.info(f"No strategies selected for {symbol}")
                return cycle_result

            # Step 4: Get pending signals
            stmt = select(Signal).where(
                Signal.symbol == symbol,
                Signal.status == SignalStatus.PENDING
            )

            result = await self.db.execute(stmt)
            pending_signals = result.scalars().all()

            # Step 5: Validate and execute signals
            for signal in pending_signals:
                # Risk validation
                validation = await self.risk_agent.validate_signal(signal, account_balance)

                if validation["approved"]:
                    cycle_result["signals_validated"] += 1

                    # Execute (or simulate)
                    position = await self.execution_agent.execute_signal(
                        signal=signal,
                        position_size=validation["position_size"],
                        account_balance=account_balance
                    )

                    if position:
                        cycle_result["trades_executed"] += 1

            logger.info(f"Trading cycle complete: {cycle_result['signals_validated']} validated, {cycle_result['trades_executed']} executed")

            return cycle_result

        except Exception as e:
            logger.error(f"Trading cycle error: {e}")
            cycle_result["errors"].append(str(e))
            return cycle_result
```

### Step 8: Database Migration

```bash
cd backend
DATABASE_URL="sqlite+aiosqlite:///./flowrex_dev.db" python -m alembic revision --autogenerate -m "add_ai_agent_tables"
```

Run migration:
```bash
DATABASE_URL="sqlite+aiosqlite:///./flowrex_dev.db" python -m alembic upgrade head
```

### Step 9: API Routes

Create `backend/app/api/v1/ai_routes.py`:

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from typing import List, Dict, Any
from pydantic import BaseModel
from app.database import get_db
from app.ai_agents.orchestrator import AIOrchestrator
from app.models.ai_agent import AIDecision, AgentMemory, SystemConfig, SystemMode
from sqlalchemy import select, desc
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ai", tags=["ai"])


class TradingCycleRequest(BaseModel):
    symbol: str
    strategies: List[str]
    account_balance: float
    peak_balance: float


class SystemModeUpdate(BaseModel):
    mode: str  # "guide" or "autonomous"


@router.get("/mode")
async def get_system_mode(db: AsyncSession = Depends(get_db)):
    """Get current system mode."""
    stmt = select(SystemConfig).where(SystemConfig.key == "system_mode")
    result = await db.execute(stmt)
    config = result.scalar_one_or_none()

    if config:
        return {"mode": config.value.get("mode", "guide")}

    return {"mode": "guide"}


@router.put("/mode")
async def set_system_mode(
    request: SystemModeUpdate,
    db: AsyncSession = Depends(get_db)
):
    """
    Set system mode.

    CRITICAL: Switching to AUTONOMOUS mode enables live trading.
    """
    if request.mode not in ["guide", "autonomous"]:
        raise HTTPException(status_code=400, detail="Mode must be 'guide' or 'autonomous'")

    stmt = select(SystemConfig).where(SystemConfig.key == "system_mode")
    result = await db.execute(stmt)
    config = result.scalar_one_or_none()

    if config:
        config.value = {"mode": request.mode}
    else:
        config = SystemConfig(
            key="system_mode",
            value={"mode": request.mode},
            description="Current system operating mode"
        )
        self.db.add(config)

    await db.commit()

    logger.warning(f"System mode changed to: {request.mode.upper()}")

    return {"mode": request.mode, "message": f"System mode set to {request.mode}"}


@router.post("/trading-cycle")
async def run_trading_cycle(
    request: TradingCycleRequest,
    db: AsyncSession = Depends(get_db)
):
    """Execute one AI trading cycle."""
    orchestrator = AIOrchestrator(db=db)
    await orchestrator.initialize()

    result = await orchestrator.run_trading_cycle(
        symbol=request.symbol,
        available_strategies=request.strategies,
        account_balance=request.account_balance,
        peak_balance=request.peak_balance
    )

    return result


@router.get("/decisions")
async def get_ai_decisions(
    agent_role: str | None = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
):
    """Get AI decision log."""
    stmt = select(AIDecision)

    if agent_role:
        stmt = stmt.where(AIDecision.agent_role == agent_role)

    stmt = stmt.order_by(desc(AIDecision.decision_time)).limit(limit)

    result = await db.execute(stmt)
    decisions = result.scalars().all()

    return [
        {
            "id": d.id,
            "agent_role": d.agent_role.value,
            "decision_type": d.decision_type.value,
            "decision": d.decision,
            "reasoning": d.reasoning,
            "context": d.context,
            "executed": d.executed,
            "decision_time": d.decision_time
        }
        for d in decisions
    ]


@router.get("/memory")
async def get_agent_memory(
    agent_role: str | None = None,
    memory_type: str | None = None,
    db: AsyncSession = Depends(get_db)
):
    """Get agent learning memory."""
    stmt = select(AgentMemory)

    if agent_role:
        stmt = stmt.where(AgentMemory.agent_role == agent_role)
    if memory_type:
        stmt = stmt.where(AgentMemory.memory_type == memory_type)

    stmt = stmt.order_by(desc(AgentMemory.last_updated))

    result = await db.execute(stmt)
    memories = result.scalars().all()

    return [
        {
            "id": m.id,
            "agent_role": m.agent_role.value,
            "memory_type": m.memory_type,
            "memory_key": m.memory_key,
            "data": m.data,
            "confidence": m.confidence,
            "sample_count": m.sample_count,
            "last_updated": m.last_updated
        }
        for m in memories
    ]
```

Register routes in `backend/app/main.py`:

```python
from app.api.v1 import auth_routes, data_routes, strategy_routes, backtest_routes, optimization_routes, ai_routes

app.include_router(ai_routes.router, prefix="/api/v1")
```

### Step 10: Tests

Create `backend/tests/unit/test_ai_agents.py`:

```python
import pytest
from app.ai_agents.risk_agent import RiskAgent, HARD_CAPS
from app.models.ai_agent import SystemMode
from app.models.signal import Signal, SignalType, SignalStatus
from datetime import datetime


@pytest.mark.asyncio
class TestRiskAgent:
    async def test_hard_caps_defined(self):
        assert HARD_CAPS["max_risk_per_trade"] == 2.0
        assert HARD_CAPS["max_daily_loss"] == 5.0
        assert HARD_CAPS["max_trades_per_day"] == 20
        assert HARD_CAPS["max_open_positions"] == 10

    async def test_position_size_calculation(self, async_db_session):
        agent = RiskAgent(db=async_db_session, system_mode=SystemMode.GUIDE)

        position_size = agent._calculate_position_size(
            account_balance=10000.0,
            risk_percent=2.0,
            entry_price=1.1000,
            stop_loss=1.0950
        )

        # Risk amount = 10000 * 0.02 = 200
        # Risk per unit = 1.1000 - 1.0950 = 0.005
        # Position size = 200 / 0.005 = 40000 (but likely capped)

        assert position_size > 0

    async def test_validate_signal_approved(self, async_db_session):
        agent = RiskAgent(db=async_db_session, system_mode=SystemMode.AUTONOMOUS)

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

        validation = await agent.validate_signal(signal, account_balance=10000.0)

        assert validation["approved"] is True
        assert validation["position_size"] > 0
```

Run tests:
```bash
cd backend
DATABASE_URL="sqlite+aiosqlite:///./flowrex_dev.db" python -m pytest tests/unit/test_ai_agents.py -v
```

## Validation Checklist

Before proceeding to Prompt 08, verify:

- [ ] AIDecision, AgentMemory, SystemConfig models created
- [ ] Database migration applied successfully
- [ ] BaseAgent class implements decision logging and memory storage
- [ ] SupervisorAgent enforces GUIDE vs AUTONOMOUS mode
- [ ] SupervisorAgent checks hard caps
- [ ] StrategyAgent evaluates strategy performance
- [ ] StrategyAgent disables underperforming strategies
- [ ] StrategyAgent triggers optimizations when needed
- [ ] RiskAgent enforces hard caps (cannot be overridden)
- [ ] RiskAgent validates signals before execution
- [ ] RiskAgent calculates position sizes correctly
- [ ] ExecutionAgent simulates in GUIDE mode (no real execution)
- [ ] ExecutionAgent executes live trades in AUTONOMOUS mode
- [ ] AIOrchestrator coordinates all agents
- [ ] API route `/ai/mode` returns current mode
- [ ] API route `/ai/mode` updates system mode
- [ ] API route `/ai/trading-cycle` runs full cycle
- [ ] API route `/ai/decisions` returns decision log
- [ ] API route `/ai/memory` returns agent memories
- [ ] All unit tests pass
- [ ] Hard caps are immutable and enforced
- [ ] GUIDE mode prevents all live execution
- [ ] AUTONOMOUS mode allows live trading with risk checks
- [ ] CROSSCHECK.md validation for Prompt 07 completed

## Hard Stop Criteria

**DO NOT PROCEED to Prompt 08 unless:**

1. ✅ Database migration runs without errors
2. ✅ All pytest tests pass (0 failures, 0 errors)
3. ✅ GUIDE mode blocks all live trade execution
4. ✅ AUTONOMOUS mode enforces hard caps strictly
5. ✅ Risk agent rejects signals exceeding risk limits
6. ✅ Strategy agent can disable underperforming strategies
7. ✅ All agent decisions are logged with reasoning
8. ✅ Agent memory system stores and recalls learnings
9. ✅ AI orchestrator coordinates agents correctly
10. ✅ CROSSCHECK.md section for Prompt 07 fully validated

If any criterion fails, **HALT** and fix before continuing.

---

**Completion Criteria:**
- AI agent system fully operational with 4 agents
- GUIDE vs AUTONOMOUS mode hard-enforced
- Hard caps immutable and strictly enforced
- Decision logging and learning system active
- Strategy performance monitoring and auto-disable working
- System ready for Multi-Agent Coordination (Prompt 08)
