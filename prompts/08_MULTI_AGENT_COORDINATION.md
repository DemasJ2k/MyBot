# Prompt 08: Multi-Agent Coordination

## Purpose

Build the coordination layer that orchestrates communication, data sharing, and execution control between AI agents. This system establishes a strict hierarchy with the Supervisor as the authoritative controller, enforces deterministic execution order, manages shared state, and implements comprehensive failure handling.

## Scope

- Agent hierarchy and authority levels
- Message-passing protocol between agents
- Shared state management and access control
- Deterministic execution pipeline
- Agent communication bus
- Coordination state machine
- Failure detection and recovery
- Deadlock prevention
- Agent health monitoring
- Mode enforcement coordination
- HALT conditions and emergency protocols
- Complete test suite

## Coordination Architecture

```
Supervisor Agent (Authority Level 0 - HIGHEST)
    ↓
Coordination Bus (Message Queue + Shared State)
    ↓
┌──────────────┬──────────────┬──────────────┐
│ Strategy     │ Risk         │ Execution    │
│ Agent        │ Agent        │ Agent        │
│ (Level 1)    │ (Level 1)    │ (Level 1)    │
└──────────────┴──────────────┴──────────────┘

Execution Flow:
1. Supervisor initiates cycle
2. Strategy Agent analyzes (waits for Supervisor approval)
3. Risk Agent validates (waits for Strategy completion)
4. Execution Agent executes (waits for Risk approval)
5. Supervisor monitors and can HALT at any step
```

## Implementation

### Step 1: Database Models

Create `backend/app/models/coordination.py`:

```python
from sqlalchemy import String, Float, Integer, JSON, Enum as SQLEnum, Boolean, Index, Text
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from typing import Optional, Dict, Any
import enum
from app.models.base import Base, TimestampMixin


class AgentAuthorityLevel(int, enum.Enum):
    SUPERVISOR = 0      # Highest authority
    SUBORDINATE = 1     # Strategy, Risk, Execution agents


class CoordinationPhase(str, enum.Enum):
    IDLE = "idle"
    INITIALIZING = "initializing"
    STRATEGY_ANALYSIS = "strategy_analysis"
    RISK_VALIDATION = "risk_validation"
    EXECUTION = "execution"
    MONITORING = "monitoring"
    HALTED = "halted"
    FAILED = "failed"
    COMPLETED = "completed"


class MessageType(str, enum.Enum):
    COMMAND = "command"
    REQUEST = "request"
    RESPONSE = "response"
    EVENT = "event"
    HALT = "halt"


class MessagePriority(int, enum.Enum):
    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3


class AgentMessage(Base, TimestampMixin):
    """Inter-agent message for coordination."""
    __tablename__ = "agent_messages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Message routing
    from_agent: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    to_agent: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    # Message details
    message_type: Mapped[MessageType] = mapped_column(SQLEnum(MessageType), nullable=False)
    priority: Mapped[MessagePriority] = mapped_column(SQLEnum(MessagePriority), nullable=False, default=MessagePriority.NORMAL)

    # Content
    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    payload: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)

    # Status
    processed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    processed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    response_message_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Timestamps
    sent_at: Mapped[datetime] = mapped_column(nullable=False, index=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    __table_args__ = (
        Index("ix_agent_message_to_processed", "to_agent", "processed"),
    )

    def __repr__(self) -> str:
        return f"<AgentMessage {self.id} {self.from_agent}->{self.to_agent} {self.message_type.value}>"


class CoordinationState(Base, TimestampMixin):
    """Shared state for agent coordination."""
    __tablename__ = "coordination_state"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    cycle_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)

    # Current phase
    phase: Mapped[CoordinationPhase] = mapped_column(SQLEnum(CoordinationPhase), nullable=False, index=True)

    # Agents involved
    active_agents: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)  # {agent_name: status}

    # Shared data
    shared_data: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    # Control flags
    halt_requested: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    halt_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timing
    cycle_started_at: Mapped[datetime] = mapped_column(nullable=False)
    cycle_completed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Results
    cycle_result: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    errors: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    def __repr__(self) -> str:
        return f"<CoordinationState {self.cycle_id} {self.phase.value}>"


class AgentHealth(Base, TimestampMixin):
    """Agent health monitoring."""
    __tablename__ = "agent_health"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    agent_name: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    # Health metrics
    is_healthy: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_heartbeat: Mapped[datetime] = mapped_column(nullable=False, index=True)

    # Performance metrics
    avg_response_time_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    success_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Status
    status_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<AgentHealth {self.agent_name} healthy={self.is_healthy}>"
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
]
```

### Step 2: Message Bus

Create `backend/app/coordination/message_bus.py`:

```python
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from app.models.coordination import (
    AgentMessage,
    MessageType,
    MessagePriority,
)
import logging

logger = logging.getLogger(__name__)


class MessageBus:
    """
    Inter-agent message bus for coordination.

    Enforces:
    - Priority-based message delivery
    - Message expiration
    - Request-response correlation
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def send_message(
        self,
        from_agent: str,
        to_agent: str,
        message_type: MessageType,
        subject: str,
        payload: Dict[str, Any],
        priority: MessagePriority = MessagePriority.NORMAL,
        expires_in_seconds: Optional[int] = None
    ) -> AgentMessage:
        """
        Send a message from one agent to another.

        Args:
            from_agent: Sender agent name
            to_agent: Recipient agent name
            message_type: Type of message
            subject: Message subject
            payload: Message data
            priority: Message priority
            expires_in_seconds: Optional expiration time

        Returns:
            Created message
        """
        expires_at = None
        if expires_in_seconds:
            expires_at = datetime.utcnow() + timedelta(seconds=expires_in_seconds)

        message = AgentMessage(
            from_agent=from_agent,
            to_agent=to_agent,
            message_type=message_type,
            priority=priority,
            subject=subject,
            payload=payload,
            processed=False,
            sent_at=datetime.utcnow(),
            expires_at=expires_at
        )

        self.db.add(message)
        await self.db.commit()
        await self.db.refresh(message)

        logger.debug(f"Message sent: {from_agent} -> {to_agent} ({message_type.value}): {subject}")

        return message

    async def receive_messages(
        self,
        agent_name: str,
        message_type: Optional[MessageType] = None,
        limit: int = 10
    ) -> List[AgentMessage]:
        """
        Receive pending messages for an agent.

        Args:
            agent_name: Agent name
            message_type: Optional filter by message type
            limit: Maximum messages to retrieve

        Returns:
            List of unprocessed messages, ordered by priority then time
        """
        # Build query
        stmt = select(AgentMessage).where(
            and_(
                AgentMessage.to_agent == agent_name,
                AgentMessage.processed == False,
                or_(
                    AgentMessage.expires_at.is_(None),
                    AgentMessage.expires_at > datetime.utcnow()
                )
            )
        )

        if message_type:
            stmt = stmt.where(AgentMessage.message_type == message_type)

        # Order by priority (lower number = higher priority), then by sent time
        stmt = stmt.order_by(
            AgentMessage.priority.asc(),
            AgentMessage.sent_at.asc()
        ).limit(limit)

        result = await self.db.execute(stmt)
        messages = list(result.scalars().all())

        return messages

    async def mark_processed(
        self,
        message_id: int,
        response_message_id: Optional[int] = None
    ):
        """Mark a message as processed."""
        stmt = select(AgentMessage).where(AgentMessage.id == message_id)
        result = await self.db.execute(stmt)
        message = result.scalar_one_or_none()

        if message:
            message.processed = True
            message.processed_at = datetime.utcnow()
            if response_message_id:
                message.response_message_id = response_message_id
            await self.db.commit()

    async def send_response(
        self,
        original_message: AgentMessage,
        response_payload: Dict[str, Any]
    ) -> AgentMessage:
        """
        Send a response to a message.

        Args:
            original_message: Message to respond to
            response_payload: Response data

        Returns:
            Response message
        """
        response = await self.send_message(
            from_agent=original_message.to_agent,
            to_agent=original_message.from_agent,
            message_type=MessageType.RESPONSE,
            subject=f"Re: {original_message.subject}",
            payload=response_payload,
            priority=original_message.priority
        )

        # Mark original as processed with response link
        await self.mark_processed(original_message.id, response.id)

        return response

    async def broadcast_halt(
        self,
        from_agent: str,
        reason: str
    ):
        """
        Broadcast HALT message to all agents.

        Args:
            from_agent: Agent issuing halt
            reason: Halt reason
        """
        agents = ["supervisor", "strategy", "risk", "execution"]

        for agent in agents:
            if agent != from_agent:
                await self.send_message(
                    from_agent=from_agent,
                    to_agent=agent,
                    message_type=MessageType.HALT,
                    subject="EMERGENCY HALT",
                    payload={"reason": reason, "timestamp": datetime.utcnow().isoformat()},
                    priority=MessagePriority.CRITICAL,
                    expires_in_seconds=60
                )

        logger.critical(f"HALT broadcast from {from_agent}: {reason}")
```

### Step 3: Shared State Manager

Create `backend/app/coordination/shared_state.py`:

```python
from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.coordination import CoordinationState, CoordinationPhase
import logging
import uuid

logger = logging.getLogger(__name__)


class SharedStateManager:
    """
    Manages shared state between agents.

    Enforces:
    - Single source of truth
    - Atomic state transitions
    - Phase-based access control
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_cycle(
        self,
        active_agents: Dict[str, str]
    ) -> CoordinationState:
        """
        Create a new coordination cycle.

        Args:
            active_agents: Dict of {agent_name: "pending"}

        Returns:
            New coordination state
        """
        cycle_id = f"cycle_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

        state = CoordinationState(
            cycle_id=cycle_id,
            phase=CoordinationPhase.INITIALIZING,
            active_agents=active_agents,
            shared_data={},
            halt_requested=False,
            cycle_started_at=datetime.utcnow()
        )

        self.db.add(state)
        await self.db.commit()
        await self.db.refresh(state)

        logger.info(f"Created coordination cycle: {cycle_id}")

        return state

    async def get_current_cycle(self, cycle_id: str) -> Optional[CoordinationState]:
        """Get current cycle state."""
        stmt = select(CoordinationState).where(CoordinationState.cycle_id == cycle_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def transition_phase(
        self,
        cycle_id: str,
        new_phase: CoordinationPhase,
        agent_name: str
    ) -> bool:
        """
        Transition cycle to new phase.

        Only Supervisor can transition phases.

        Args:
            cycle_id: Cycle ID
            new_phase: Target phase
            agent_name: Agent requesting transition

        Returns:
            True if transition successful
        """
        state = await self.get_current_cycle(cycle_id)

        if not state:
            logger.error(f"Cycle {cycle_id} not found")
            return False

        # Only Supervisor can transition phases
        if agent_name != "supervisor":
            logger.error(f"Agent {agent_name} cannot transition phases (Supervisor only)")
            return False

        # Check if halt requested
        if state.halt_requested:
            logger.warning(f"Cannot transition to {new_phase.value}: HALT requested")
            return False

        # Transition
        old_phase = state.phase
        state.phase = new_phase

        await self.db.commit()

        logger.info(f"Phase transition: {old_phase.value} -> {new_phase.value}")

        return True

    async def write_shared_data(
        self,
        cycle_id: str,
        key: str,
        value: Any,
        agent_name: str
    ) -> bool:
        """
        Write data to shared state.

        Access control:
        - Strategy agent: Can write "strategy_*" keys
        - Risk agent: Can write "risk_*" keys
        - Execution agent: Can write "execution_*" keys
        - Supervisor: Can write any key

        Args:
            cycle_id: Cycle ID
            key: Data key
            value: Data value
            agent_name: Agent writing data

        Returns:
            True if write successful
        """
        state = await self.get_current_cycle(cycle_id)

        if not state:
            logger.error(f"Cycle {cycle_id} not found")
            return False

        # Access control
        if agent_name != "supervisor":
            if not key.startswith(f"{agent_name}_"):
                logger.error(f"Agent {agent_name} cannot write key '{key}' (must start with '{agent_name}_')")
                return False

        # Write data
        state.shared_data[key] = value

        await self.db.commit()

        logger.debug(f"Shared data written: {key} by {agent_name}")

        return True

    async def read_shared_data(
        self,
        cycle_id: str,
        key: str
    ) -> Optional[Any]:
        """Read data from shared state."""
        state = await self.get_current_cycle(cycle_id)

        if not state:
            return None

        return state.shared_data.get(key)

    async def request_halt(
        self,
        cycle_id: str,
        reason: str,
        agent_name: str
    ):
        """
        Request cycle halt.

        Any agent can request halt, but only Supervisor can enforce.

        Args:
            cycle_id: Cycle ID
            reason: Halt reason
            agent_name: Agent requesting halt
        """
        state = await self.get_current_cycle(cycle_id)

        if not state:
            logger.error(f"Cycle {cycle_id} not found")
            return

        state.halt_requested = True
        state.halt_reason = f"{agent_name}: {reason}"
        state.phase = CoordinationPhase.HALTED

        await self.db.commit()

        logger.warning(f"HALT requested by {agent_name}: {reason}")

    async def complete_cycle(
        self,
        cycle_id: str,
        result: Dict[str, Any],
        errors: Optional[Dict[str, Any]] = None
    ):
        """Mark cycle as completed."""
        state = await self.get_current_cycle(cycle_id)

        if not state:
            logger.error(f"Cycle {cycle_id} not found")
            return

        state.phase = CoordinationPhase.COMPLETED if not errors else CoordinationPhase.FAILED
        state.cycle_completed_at = datetime.utcnow()
        state.cycle_result = result
        state.errors = errors

        await self.db.commit()

        logger.info(f"Cycle {cycle_id} completed with status: {state.phase.value}")
```

### Step 4: Agent Health Monitor

Create `backend/app/coordination/health_monitor.py`:

```python
from typing import Dict
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.coordination import AgentHealth
import logging

logger = logging.getLogger(__name__)


class HealthMonitor:
    """
    Monitor agent health and performance.

    Detects:
    - Unresponsive agents
    - High error rates
    - Performance degradation
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.heartbeat_timeout_seconds = 60

    async def heartbeat(
        self,
        agent_name: str,
        response_time_ms: float = 0.0
    ):
        """
        Record agent heartbeat.

        Args:
            agent_name: Agent name
            response_time_ms: Response time in milliseconds
        """
        stmt = select(AgentHealth).where(AgentHealth.agent_name == agent_name)
        result = await self.db.execute(stmt)
        health = result.scalar_one_or_none()

        if health:
            # Update existing
            health.last_heartbeat = datetime.utcnow()
            health.is_healthy = True

            # Update rolling average response time
            total_ops = health.success_count + health.error_count
            if total_ops > 0:
                health.avg_response_time_ms = (
                    (health.avg_response_time_ms * total_ops + response_time_ms) / (total_ops + 1)
                )
        else:
            # Create new
            health = AgentHealth(
                agent_name=agent_name,
                is_healthy=True,
                last_heartbeat=datetime.utcnow(),
                avg_response_time_ms=response_time_ms,
                error_count=0,
                success_count=0
            )
            self.db.add(health)

        await self.db.commit()

    async def record_success(self, agent_name: str):
        """Record successful agent operation."""
        stmt = select(AgentHealth).where(AgentHealth.agent_name == agent_name)
        result = await self.db.execute(stmt)
        health = result.scalar_one_or_none()

        if health:
            health.success_count += 1
            await self.db.commit()

    async def record_error(self, agent_name: str, error_message: str):
        """Record agent error."""
        stmt = select(AgentHealth).where(AgentHealth.agent_name == agent_name)
        result = await self.db.execute(stmt)
        health = result.scalar_one_or_none()

        if health:
            health.error_count += 1
            health.status_message = error_message

            # Mark unhealthy if error rate > 50%
            total_ops = health.success_count + health.error_count
            error_rate = health.error_count / total_ops if total_ops > 0 else 0

            if error_rate > 0.5:
                health.is_healthy = False
                logger.error(f"Agent {agent_name} marked unhealthy (error rate: {error_rate:.2%})")

            await self.db.commit()

    async def check_all_agents(self) -> Dict[str, bool]:
        """
        Check health of all agents.

        Returns:
            Dict of {agent_name: is_healthy}
        """
        stmt = select(AgentHealth)
        result = await self.db.execute(stmt)
        health_records = result.scalars().all()

        health_status = {}
        cutoff_time = datetime.utcnow() - timedelta(seconds=self.heartbeat_timeout_seconds)

        for health in health_records:
            # Check if heartbeat is recent
            is_responsive = health.last_heartbeat > cutoff_time

            # Overall health = responsive AND healthy flag
            health_status[health.agent_name] = health.is_healthy and is_responsive

            if not health_status[health.agent_name]:
                logger.warning(f"Agent {health.agent_name} is unhealthy or unresponsive")

        return health_status
```

### Step 5: Coordination Pipeline

Create `backend/app/coordination/pipeline.py`:

```python
from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from app.coordination.message_bus import MessageBus
from app.coordination.shared_state import SharedStateManager
from app.coordination.health_monitor import HealthMonitor
from app.models.coordination import (
    CoordinationPhase,
    MessageType,
    MessagePriority,
)
from app.models.ai_agent import SystemMode
import logging

logger = logging.getLogger(__name__)


class CoordinationPipeline:
    """
    Deterministic execution pipeline for multi-agent coordination.

    Execution order:
    1. Supervisor initiates cycle
    2. Strategy agent analyzes market
    3. Risk agent validates signals
    4. Execution agent executes trades
    5. Supervisor monitors and can HALT at any point
    """

    def __init__(self, db: AsyncSession, system_mode: SystemMode):
        self.db = db
        self.system_mode = system_mode
        self.message_bus = MessageBus(db)
        self.shared_state = SharedStateManager(db)
        self.health_monitor = HealthMonitor(db)

    async def execute_cycle(
        self,
        symbol: str,
        strategies: list[str],
        account_balance: float,
        peak_balance: float
    ) -> Dict[str, Any]:
        """
        Execute one complete coordination cycle.

        Returns:
            Cycle execution result
        """
        # Step 1: Create coordination state
        active_agents = {
            "supervisor": "active",
            "strategy": "pending",
            "risk": "pending",
            "execution": "pending"
        }

        state = await self.shared_state.create_cycle(active_agents)
        cycle_id = state.cycle_id

        result = {
            "cycle_id": cycle_id,
            "success": False,
            "phases_completed": [],
            "errors": [],
            "halt_reason": None
        }

        try:
            # Step 2: Check agent health
            health_status = await self.health_monitor.check_all_agents()

            unhealthy_agents = [name for name, healthy in health_status.items() if not healthy]
            if unhealthy_agents:
                error_msg = f"Unhealthy agents detected: {', '.join(unhealthy_agents)}"
                await self.shared_state.request_halt(cycle_id, error_msg, "supervisor")
                result["errors"].append(error_msg)
                result["halt_reason"] = error_msg
                return result

            # Step 3: Initialize shared data
            await self.shared_state.write_shared_data(cycle_id, "symbol", symbol, "supervisor")
            await self.shared_state.write_shared_data(cycle_id, "strategies", strategies, "supervisor")
            await self.shared_state.write_shared_data(cycle_id, "account_balance", account_balance, "supervisor")
            await self.shared_state.write_shared_data(cycle_id, "peak_balance", peak_balance, "supervisor")
            await self.shared_state.write_shared_data(cycle_id, "mode", self.system_mode.value, "supervisor")

            # Step 4: STRATEGY PHASE
            phase_ok = await self._execute_strategy_phase(cycle_id)
            if not phase_ok:
                result["errors"].append("Strategy phase failed")
                return result
            result["phases_completed"].append("strategy")

            # Check for halt
            state = await self.shared_state.get_current_cycle(cycle_id)
            if state.halt_requested:
                result["halt_reason"] = state.halt_reason
                return result

            # Step 5: RISK VALIDATION PHASE
            phase_ok = await self._execute_risk_phase(cycle_id)
            if not phase_ok:
                result["errors"].append("Risk phase failed")
                return result
            result["phases_completed"].append("risk")

            # Check for halt
            state = await self.shared_state.get_current_cycle(cycle_id)
            if state.halt_requested:
                result["halt_reason"] = state.halt_reason
                return result

            # Step 6: EXECUTION PHASE
            phase_ok = await self._execute_execution_phase(cycle_id)
            if not phase_ok:
                result["errors"].append("Execution phase failed")
                return result
            result["phases_completed"].append("execution")

            # Step 7: Complete cycle
            result["success"] = True
            await self.shared_state.complete_cycle(cycle_id, result)

            logger.info(f"Coordination cycle {cycle_id} completed successfully")

            return result

        except Exception as e:
            logger.error(f"Coordination cycle {cycle_id} failed: {e}")
            result["errors"].append(str(e))
            await self.shared_state.complete_cycle(cycle_id, result, errors={"exception": str(e)})
            return result

    async def _execute_strategy_phase(self, cycle_id: str) -> bool:
        """
        Execute strategy analysis phase.

        Returns:
            True if successful
        """
        # Transition to strategy phase
        await self.shared_state.transition_phase(cycle_id, CoordinationPhase.STRATEGY_ANALYSIS, "supervisor")

        # Send command to strategy agent
        await self.message_bus.send_message(
            from_agent="supervisor",
            to_agent="strategy",
            message_type=MessageType.COMMAND,
            subject="Analyze market and select strategies",
            payload={"cycle_id": cycle_id},
            priority=MessagePriority.HIGH,
            expires_in_seconds=120
        )

        # In real implementation, strategy agent would process this command
        # and write results to shared state
        # For now, we simulate success

        # Record heartbeat
        await self.health_monitor.heartbeat("strategy")
        await self.health_monitor.record_success("strategy")

        logger.info(f"Strategy phase completed for cycle {cycle_id}")
        return True

    async def _execute_risk_phase(self, cycle_id: str) -> bool:
        """
        Execute risk validation phase.

        Returns:
            True if successful
        """
        await self.shared_state.transition_phase(cycle_id, CoordinationPhase.RISK_VALIDATION, "supervisor")

        await self.message_bus.send_message(
            from_agent="supervisor",
            to_agent="risk",
            message_type=MessageType.COMMAND,
            subject="Validate signals and calculate position sizes",
            payload={"cycle_id": cycle_id},
            priority=MessagePriority.HIGH,
            expires_in_seconds=120
        )

        await self.health_monitor.heartbeat("risk")
        await self.health_monitor.record_success("risk")

        logger.info(f"Risk phase completed for cycle {cycle_id}")
        return True

    async def _execute_execution_phase(self, cycle_id: str) -> bool:
        """
        Execute trade execution phase.

        Returns:
            True if successful
        """
        await self.shared_state.transition_phase(cycle_id, CoordinationPhase.EXECUTION, "supervisor")

        await self.message_bus.send_message(
            from_agent="supervisor",
            to_agent="execution",
            message_type=MessageType.COMMAND,
            subject="Execute validated trades",
            payload={"cycle_id": cycle_id},
            priority=MessagePriority.HIGH,
            expires_in_seconds=120
        )

        await self.health_monitor.heartbeat("execution")
        await self.health_monitor.record_success("execution")

        logger.info(f"Execution phase completed for cycle {cycle_id}")
        return True
```

### Step 6: Database Migration

```bash
cd backend
DATABASE_URL="sqlite+aiosqlite:///./flowrex_dev.db" python -m alembic revision --autogenerate -m "add_coordination_tables"
```

Run migration:
```bash
DATABASE_URL="sqlite+aiosqlite:///./flowrex_dev.db" python -m alembic upgrade head
```

### Step 7: API Routes

Create `backend/app/api/v1/coordination_routes.py`:

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from typing import List, Dict, Any
from pydantic import BaseModel
from app.database import get_db
from app.coordination.pipeline import CoordinationPipeline
from app.coordination.message_bus import MessageBus
from app.coordination.shared_state import SharedStateManager
from app.coordination.health_monitor import HealthMonitor
from app.models.coordination import AgentMessage, CoordinationState, AgentHealth
from app.models.ai_agent import SystemMode, SystemConfig
from sqlalchemy import select, desc
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/coordination", tags=["coordination"])


class CycleRequest(BaseModel):
    symbol: str
    strategies: List[str]
    account_balance: float
    peak_balance: float


@router.post("/cycle")
async def execute_coordination_cycle(
    request: CycleRequest,
    db: AsyncSession = Depends(get_db)
):
    """Execute a complete coordination cycle."""
    # Get system mode
    stmt = select(SystemConfig).where(SystemConfig.key == "system_mode")
    result = await db.execute(stmt)
    config = result.scalar_one_or_none()

    mode_str = config.value.get("mode", "guide") if config else "guide"
    system_mode = SystemMode.GUIDE if mode_str == "guide" else SystemMode.AUTONOMOUS

    pipeline = CoordinationPipeline(db=db, system_mode=system_mode)

    result = await pipeline.execute_cycle(
        symbol=request.symbol,
        strategies=request.strategies,
        account_balance=request.account_balance,
        peak_balance=request.peak_balance
    )

    return result


@router.get("/messages")
async def get_messages(
    agent_name: str | None = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
):
    """Get agent messages."""
    stmt = select(AgentMessage)

    if agent_name:
        stmt = stmt.where(AgentMessage.to_agent == agent_name)

    stmt = stmt.order_by(desc(AgentMessage.sent_at)).limit(limit)

    result = await db.execute(stmt)
    messages = result.scalars().all()

    return [
        {
            "id": m.id,
            "from_agent": m.from_agent,
            "to_agent": m.to_agent,
            "message_type": m.message_type.value,
            "priority": m.priority.value,
            "subject": m.subject,
            "payload": m.payload,
            "processed": m.processed,
            "sent_at": m.sent_at
        }
        for m in messages
    ]


@router.get("/cycles")
async def get_coordination_cycles(
    limit: int = 20,
    db: AsyncSession = Depends(get_db)
):
    """Get coordination cycle history."""
    stmt = select(CoordinationState).order_by(desc(CoordinationState.cycle_started_at)).limit(limit)

    result = await db.execute(stmt)
    cycles = result.scalars().all()

    return [
        {
            "cycle_id": c.cycle_id,
            "phase": c.phase.value,
            "halt_requested": c.halt_requested,
            "halt_reason": c.halt_reason,
            "cycle_started_at": c.cycle_started_at,
            "cycle_completed_at": c.cycle_completed_at,
            "cycle_result": c.cycle_result
        }
        for c in cycles
    ]


@router.get("/health")
async def get_agent_health(db: AsyncSession = Depends(get_db)):
    """Get health status of all agents."""
    stmt = select(AgentHealth)
    result = await db.execute(stmt)
    health_records = result.scalars().all()

    return [
        {
            "agent_name": h.agent_name,
            "is_healthy": h.is_healthy,
            "last_heartbeat": h.last_heartbeat,
            "avg_response_time_ms": h.avg_response_time_ms,
            "error_count": h.error_count,
            "success_count": h.success_count,
            "status_message": h.status_message
        }
        for h in health_records
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
    coordination_routes
)

app.include_router(coordination_routes.router, prefix="/api/v1")
```

### Step 8: Tests

Create `backend/tests/unit/test_coordination.py`:

```python
import pytest
from datetime import datetime
from app.coordination.message_bus import MessageBus
from app.coordination.shared_state import SharedStateManager
from app.models.coordination import MessageType, MessagePriority, CoordinationPhase


@pytest.mark.asyncio
class TestMessageBus:
    async def test_send_and_receive_message(self, async_db_session):
        bus = MessageBus(db=async_db_session)

        # Send message
        message = await bus.send_message(
            from_agent="supervisor",
            to_agent="strategy",
            message_type=MessageType.COMMAND,
            subject="Test command",
            payload={"test": "data"},
            priority=MessagePriority.NORMAL
        )

        assert message.id is not None
        assert message.processed is False

        # Receive messages
        messages = await bus.receive_messages("strategy")
        assert len(messages) == 1
        assert messages[0].subject == "Test command"

    async def test_message_priority_ordering(self, async_db_session):
        bus = MessageBus(db=async_db_session)

        # Send low priority message
        await bus.send_message(
            from_agent="supervisor",
            to_agent="strategy",
            message_type=MessageType.COMMAND,
            subject="Low priority",
            payload={},
            priority=MessagePriority.LOW
        )

        # Send high priority message
        await bus.send_message(
            from_agent="supervisor",
            to_agent="strategy",
            message_type=MessageType.COMMAND,
            subject="High priority",
            payload={},
            priority=MessagePriority.HIGH
        )

        # Receive messages - should get high priority first
        messages = await bus.receive_messages("strategy", limit=10)
        assert len(messages) == 2
        assert messages[0].subject == "High priority"


@pytest.mark.asyncio
class TestSharedState:
    async def test_create_and_retrieve_cycle(self, async_db_session):
        manager = SharedStateManager(db=async_db_session)

        state = await manager.create_cycle(
            active_agents={"supervisor": "active", "strategy": "pending"}
        )

        assert state.cycle_id is not None
        assert state.phase == CoordinationPhase.INITIALIZING

        # Retrieve
        retrieved = await manager.get_current_cycle(state.cycle_id)
        assert retrieved.cycle_id == state.cycle_id

    async def test_phase_transition_supervisor_only(self, async_db_session):
        manager = SharedStateManager(db=async_db_session)

        state = await manager.create_cycle(active_agents={"supervisor": "active"})

        # Supervisor can transition
        success = await manager.transition_phase(
            state.cycle_id,
            CoordinationPhase.STRATEGY_ANALYSIS,
            "supervisor"
        )
        assert success is True

        # Other agents cannot transition
        success = await manager.transition_phase(
            state.cycle_id,
            CoordinationPhase.EXECUTION,
            "strategy"
        )
        assert success is False

    async def test_write_access_control(self, async_db_session):
        manager = SharedStateManager(db=async_db_session)

        state = await manager.create_cycle(active_agents={"supervisor": "active"})

        # Strategy agent can write strategy_* keys
        success = await manager.write_shared_data(
            state.cycle_id,
            "strategy_analysis",
            {"result": "bullish"},
            "strategy"
        )
        assert success is True

        # Strategy agent cannot write risk_* keys
        success = await manager.write_shared_data(
            state.cycle_id,
            "risk_check",
            {"result": "approved"},
            "strategy"
        )
        assert success is False

        # Supervisor can write any key
        success = await manager.write_shared_data(
            state.cycle_id,
            "any_key",
            {"data": "test"},
            "supervisor"
        )
        assert success is True
```

Run tests:
```bash
cd backend
DATABASE_URL="sqlite+aiosqlite:///./flowrex_dev.db" python -m pytest tests/unit/test_coordination.py -v
```

## Validation Checklist

Before proceeding to Prompt 09, verify:

- [ ] AgentMessage, CoordinationState, AgentHealth models created
- [ ] Database migration applied successfully
- [ ] MessageBus implements priority-based message delivery
- [ ] MessageBus supports request-response correlation
- [ ] MessageBus broadcasts HALT messages with CRITICAL priority
- [ ] SharedStateManager creates coordination cycles
- [ ] SharedStateManager enforces phase transitions (Supervisor only)
- [ ] SharedStateManager enforces write access control (agent-prefixed keys)
- [ ] SharedStateManager tracks halt requests
- [ ] HealthMonitor records agent heartbeats
- [ ] HealthMonitor detects unhealthy agents (>50% error rate)
- [ ] HealthMonitor detects unresponsive agents (no heartbeat in 60s)
- [ ] CoordinationPipeline executes deterministic phase order
- [ ] CoordinationPipeline checks agent health before starting
- [ ] CoordinationPipeline can HALT at any phase
- [ ] API route `/coordination/cycle` executes coordination cycle
- [ ] API route `/coordination/messages` returns agent messages
- [ ] API route `/coordination/cycles` returns cycle history
- [ ] API route `/coordination/health` returns agent health status
- [ ] All unit tests pass
- [ ] Message priority ordering works correctly
- [ ] Phase transition access control works (Supervisor only)
- [ ] Shared data write access control works (agent-prefixed keys)
- [ ] CROSSCHECK.md validation for Prompt 08 completed

## Hard Stop Criteria

**DO NOT PROCEED to Prompt 09 unless:**

1. ✅ Database migration runs without errors
2. ✅ All pytest tests pass (0 failures, 0 errors)
3. ✅ Supervisor agent has exclusive phase transition authority
4. ✅ Message bus delivers messages in priority order
5. ✅ Shared state enforces agent-specific write access
6. ✅ Health monitor correctly detects unhealthy/unresponsive agents
7. ✅ Coordination pipeline executes phases in deterministic order
8. ✅ HALT mechanism stops execution at any phase
9. ✅ All agent messages are logged and traceable
10. ✅ CROSSCHECK.md section for Prompt 08 fully validated

If any criterion fails, **HALT** and fix before continuing.

---

**Completion Criteria:**
- Multi-agent coordination system fully operational
- Supervisor has authoritative control over all agents
- Message-passing and shared state working correctly
- Deterministic execution order enforced
- Failure handling and HALT mechanism implemented
- System ready for Risk Engine (Prompt 09)
