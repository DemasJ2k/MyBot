# Prompt 10: Execution Engine

## Purpose

Build the execution layer that interfaces with broker APIs to place, monitor, modify, and close real trades. This is the **ONLY** component authorized to execute live trades. The execution engine enforces strict pre-execution validation (Strategy approval → Risk approval → Mode check), provides broker abstraction, handles order lifecycle management, and ensures idempotent retry-safe operations.

## Scope

- Broker adapter architecture (MT5, OANDA, Binance)
- Order lifecycle management (create → submit → monitor → modify → close)
- Pre-execution validation pipeline
- Order state machine with deterministic transitions
- Idempotent order operations (safe retries)
- Execution failure handling and recovery
- Real-time order monitoring and updates
- Position synchronization with broker
- Execution audit trail
- Complete test suite

## Execution Architecture

```
Execution Request (from Execution Agent)
    ↓
Pre-Execution Validator
    ├─ Strategy Approval Check
    ├─ Risk Approval Check
    └─ Mode Check (AUTONOMOUS only)
    ↓
Order Builder → Order Validator
    ↓
Broker Adapter [MT5 | OANDA | Binance]
    ↓
Order Submission → Broker API
    ↓
Order Monitor (real-time updates)
    ↓
Position Synchronizer → Database
    ↓
Execution Log (audit trail)
```

## Implementation

### Step 1: Database Models

Create `backend/app/models/execution.py`:

```python
from sqlalchemy import String, Float, Integer, Enum as SQLEnum, Boolean, Index, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from typing import Optional, Dict, Any
import enum
from app.models.base import Base, TimestampMixin


class BrokerType(str, enum.Enum):
    MT5 = "mt5"
    OANDA = "oanda"
    BINANCE_SPOT = "binance_spot"
    BINANCE_FUTURES = "binance_futures"
    PAPER = "paper"  # Paper trading / simulation


class OrderType(str, enum.Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class OrderSide(str, enum.Enum):
    BUY = "buy"
    SELL = "sell"


class OrderStatus(str, enum.Enum):
    PENDING = "pending"          # Created but not submitted
    SUBMITTED = "submitted"      # Submitted to broker
    ACCEPTED = "accepted"        # Broker accepted
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"            # Completely filled
    CANCELLED = "cancelled"      # User cancelled
    REJECTED = "rejected"        # Broker rejected
    EXPIRED = "expired"          # Order expired
    FAILED = "failed"            # Execution failed


class ExecutionOrder(Base, TimestampMixin):
    """Execution order with full lifecycle tracking."""
    __tablename__ = "execution_orders"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Order identification
    client_order_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    broker_order_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)

    # Broker
    broker_type: Mapped[BrokerType] = mapped_column(SQLEnum(BrokerType), nullable=False)

    # Order details
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    order_type: Mapped[OrderType] = mapped_column(SQLEnum(OrderType), nullable=False)
    side: Mapped[OrderSide] = mapped_column(SQLEnum(OrderSide), nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)

    # Prices
    price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # For limit orders
    stop_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # For stop orders

    # Stop loss / Take profit
    stop_loss: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    take_profit: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Status
    status: Mapped[OrderStatus] = mapped_column(SQLEnum(OrderStatus), nullable=False, default=OrderStatus.PENDING, index=True)

    # Execution details
    filled_quantity: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    average_fill_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Timestamps
    submitted_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    filled_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Links
    signal_id: Mapped[Optional[int]] = mapped_column(ForeignKey("signals.id"), nullable=True)
    position_id: Mapped[Optional[int]] = mapped_column(ForeignKey("positions.id"), nullable=True)

    # Strategy context
    strategy_name: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    # Error tracking
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Metadata
    metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        Index("ix_execution_order_status", "status"),
        Index("ix_execution_order_broker_symbol", "broker_type", "symbol"),
    )

    def __repr__(self) -> str:
        return f"<ExecutionOrder {self.client_order_id} {self.side.value} {self.symbol} {self.status.value}>"


class ExecutionLog(Base, TimestampMixin):
    """Audit log for all execution events."""
    __tablename__ = "execution_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("execution_orders.id"), nullable=False, index=True)

    # Event details
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    event_data: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)

    # Status changes
    old_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    new_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Timestamps
    event_time: Mapped[datetime] = mapped_column(nullable=False, index=True)

    # Relationship
    order: Mapped["ExecutionOrder"] = relationship("ExecutionOrder")

    def __repr__(self) -> str:
        return f"<ExecutionLog {self.id} order={self.order_id} {self.event_type}>"


class BrokerConnection(Base, TimestampMixin):
    """Broker connection configuration."""
    __tablename__ = "broker_connections"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    broker_type: Mapped[BrokerType] = mapped_column(SQLEnum(BrokerType), unique=True, nullable=False, index=True)

    # Connection details (encrypted in production)
    credentials: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_connected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Health
    last_health_check: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    last_connection_time: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<BrokerConnection {self.broker_type.value} connected={self.is_connected}>"
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
]
```

### Step 2: Base Broker Adapter

Create `backend/app/execution/base_broker.py`:

```python
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from app.models.execution import ExecutionOrder, OrderStatus
import logging

logger = logging.getLogger(__name__)


class BaseBrokerAdapter(ABC):
    """
    Abstract base class for broker adapters.

    All brokers must implement:
    - connect()
    - disconnect()
    - submit_order()
    - cancel_order()
    - modify_order()
    - get_order_status()
    - get_positions()
    """

    def __init__(self, credentials: Dict[str, Any]):
        self.credentials = credentials
        self.is_connected = False

    @abstractmethod
    async def connect(self) -> bool:
        """
        Connect to broker.

        Returns:
            True if connection successful
        """
        pass

    @abstractmethod
    async def disconnect(self):
        """Disconnect from broker."""
        pass

    @abstractmethod
    async def submit_order(self, order: ExecutionOrder) -> Dict[str, Any]:
        """
        Submit order to broker.

        Args:
            order: Execution order

        Returns:
            Dict with broker response including broker_order_id
        """
        pass

    @abstractmethod
    async def cancel_order(self, broker_order_id: str) -> bool:
        """
        Cancel an order.

        Args:
            broker_order_id: Broker's order ID

        Returns:
            True if cancellation successful
        """
        pass

    @abstractmethod
    async def modify_order(
        self,
        broker_order_id: str,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None
    ) -> bool:
        """
        Modify order stop loss or take profit.

        Args:
            broker_order_id: Broker's order ID
            stop_loss: New stop loss price
            take_profit: New take profit price

        Returns:
            True if modification successful
        """
        pass

    @abstractmethod
    async def get_order_status(self, broker_order_id: str) -> Dict[str, Any]:
        """
        Get current order status from broker.

        Returns:
            Dict with order status details
        """
        pass

    @abstractmethod
    async def get_positions(self) -> List[Dict[str, Any]]:
        """
        Get all open positions.

        Returns:
            List of position dicts
        """
        pass

    @abstractmethod
    async def get_account_balance(self) -> float:
        """
        Get current account balance.

        Returns:
            Account balance
        """
        pass
```

### Step 3: Paper Broker (Simulation)

Create `backend/app/execution/paper_broker.py`:

```python
from typing import Dict, Any, Optional, List
from app.execution.base_broker import BaseBrokerAdapter
from app.models.execution import ExecutionOrder, OrderStatus
import uuid
import logging

logger = logging.getLogger(__name__)


class PaperBroker(BaseBrokerAdapter):
    """
    Paper trading broker for simulation.

    Simulates order execution without real money.
    """

    def __init__(self, credentials: Dict[str, Any]):
        super().__init__(credentials)
        self.simulated_balance = credentials.get("initial_balance", 10000.0)
        self.simulated_positions = {}
        self.simulated_orders = {}

    async def connect(self) -> bool:
        """Connect to paper broker (always succeeds)."""
        self.is_connected = True
        logger.info("Paper broker connected")
        return True

    async def disconnect(self):
        """Disconnect from paper broker."""
        self.is_connected = False
        logger.info("Paper broker disconnected")

    async def submit_order(self, order: ExecutionOrder) -> Dict[str, Any]:
        """
        Simulate order submission.

        Immediately "fills" market orders.
        """
        if not self.is_connected:
            raise RuntimeError("Paper broker not connected")

        # Generate broker order ID
        broker_order_id = f"PAPER_{uuid.uuid4().hex[:12].upper()}"

        # Simulate instant fill for market orders
        if order.order_type.value == "market":
            # Use entry price as fill price (from signal)
            fill_price = order.price if order.price else 1.0

            self.simulated_orders[broker_order_id] = {
                "status": OrderStatus.FILLED.value,
                "filled_quantity": order.quantity,
                "average_fill_price": fill_price
            }

            logger.info(f"Paper order filled: {broker_order_id} {order.side.value} {order.quantity} @ {fill_price}")

            return {
                "broker_order_id": broker_order_id,
                "status": OrderStatus.FILLED.value,
                "filled_quantity": order.quantity,
                "average_fill_price": fill_price
            }

        # For limit/stop orders, mark as submitted
        self.simulated_orders[broker_order_id] = {
            "status": OrderStatus.SUBMITTED.value,
            "filled_quantity": 0.0,
            "average_fill_price": None
        }

        return {
            "broker_order_id": broker_order_id,
            "status": OrderStatus.SUBMITTED.value
        }

    async def cancel_order(self, broker_order_id: str) -> bool:
        """Cancel simulated order."""
        if broker_order_id in self.simulated_orders:
            self.simulated_orders[broker_order_id]["status"] = OrderStatus.CANCELLED.value
            logger.info(f"Paper order cancelled: {broker_order_id}")
            return True
        return False

    async def modify_order(
        self,
        broker_order_id: str,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None
    ) -> bool:
        """Modify simulated order."""
        if broker_order_id in self.simulated_orders:
            logger.info(f"Paper order modified: {broker_order_id} SL={stop_loss} TP={take_profit}")
            return True
        return False

    async def get_order_status(self, broker_order_id: str) -> Dict[str, Any]:
        """Get simulated order status."""
        if broker_order_id in self.simulated_orders:
            return self.simulated_orders[broker_order_id]

        return {"status": OrderStatus.FAILED.value}

    async def get_positions(self) -> List[Dict[str, Any]]:
        """Get simulated positions."""
        return list(self.simulated_positions.values())

    async def get_account_balance(self) -> float:
        """Get simulated account balance."""
        return self.simulated_balance
```

### Step 4: Execution Engine

Create `backend/app/execution/engine.py`:

```python
from typing import Dict, Any, Optional, Tuple
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.execution import (
    ExecutionOrder,
    ExecutionLog,
    BrokerConnection,
    BrokerType,
    OrderStatus,
    OrderType,
    OrderSide,
)
from app.models.signal import Signal, SignalStatus, SignalType
from app.models.ai_agent import SystemMode, SystemConfig
from app.execution.base_broker import BaseBrokerAdapter
from app.execution.paper_broker import PaperBroker
import uuid
import logging

logger = logging.getLogger(__name__)


class ExecutionEngine:
    """
    Execution engine - ONLY component authorized to place live trades.

    Enforces:
    1. Strategy approval (signal exists)
    2. Risk approval (risk validation passed)
    3. Mode check (AUTONOMOUS only for live trading)
    4. Broker connectivity
    5. Idempotent operations
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.broker_adapters: Dict[BrokerType, BaseBrokerAdapter] = {}

    async def initialize_broker(self, broker_type: BrokerType) -> bool:
        """
        Initialize broker connection.

        Args:
            broker_type: Broker to initialize

        Returns:
            True if initialization successful
        """
        # Load broker credentials
        stmt = select(BrokerConnection).where(BrokerConnection.broker_type == broker_type)
        result = await self.db.execute(stmt)
        connection = result.scalar_one_or_none()

        if not connection or not connection.is_active:
            logger.error(f"Broker {broker_type.value} not configured or inactive")
            return False

        # Create adapter
        adapter = self._create_adapter(broker_type, connection.credentials)

        # Connect
        connected = await adapter.connect()

        if connected:
            self.broker_adapters[broker_type] = adapter
            connection.is_connected = True
            connection.last_connection_time = datetime.utcnow()
            await self.db.commit()
            logger.info(f"Broker {broker_type.value} initialized")
            return True

        connection.is_connected = False
        connection.last_error = "Connection failed"
        await self.db.commit()
        logger.error(f"Broker {broker_type.value} connection failed")
        return False

    def _create_adapter(self, broker_type: BrokerType, credentials: Dict[str, Any]) -> BaseBrokerAdapter:
        """Create broker adapter instance."""
        if broker_type == BrokerType.PAPER:
            return PaperBroker(credentials)
        # Add real broker adapters here:
        # elif broker_type == BrokerType.MT5:
        #     return MT5Broker(credentials)
        # elif broker_type == BrokerType.OANDA:
        #     return OandaBroker(credentials)
        # elif broker_type == BrokerType.BINANCE_SPOT:
        #     return BinanceSpotBroker(credentials)
        else:
            raise ValueError(f"Unsupported broker: {broker_type.value}")

    async def execute_signal(
        self,
        signal: Signal,
        position_size: float,
        broker_type: BrokerType = BrokerType.PAPER
    ) -> Tuple[bool, Optional[ExecutionOrder], Optional[str]]:
        """
        Execute a trading signal.

        PRE-EXECUTION VALIDATION:
        1. Signal exists and is PENDING
        2. System is in AUTONOMOUS mode (not GUIDE)
        3. Broker is connected
        4. Order is idempotent (no duplicate client_order_id)

        Args:
            signal: Trading signal
            position_size: Position size (from risk engine)
            broker_type: Broker to use

        Returns:
            (success, order, error_message)
        """
        # VALIDATION 1: Check signal status
        if signal.status != SignalStatus.PENDING:
            error = f"Signal {signal.id} is not pending (status={signal.status.value})"
            logger.error(error)
            return False, None, error

        # VALIDATION 2: Check system mode
        stmt = select(SystemConfig).where(SystemConfig.key == "system_mode")
        result = await self.db.execute(stmt)
        config = result.scalar_one_or_none()

        mode_str = config.value.get("mode", "guide") if config else "guide"
        system_mode = SystemMode.GUIDE if mode_str == "guide" else SystemMode.AUTONOMOUS

        if system_mode == SystemMode.GUIDE:
            error = "Cannot execute live trades in GUIDE mode"
            logger.warning(error)
            return False, None, error

        # VALIDATION 3: Check broker connectivity
        if broker_type not in self.broker_adapters:
            # Try to initialize
            initialized = await self.initialize_broker(broker_type)
            if not initialized:
                error = f"Broker {broker_type.value} not available"
                logger.error(error)
                return False, None, error

        broker = self.broker_adapters[broker_type]

        if not broker.is_connected:
            error = f"Broker {broker_type.value} not connected"
            logger.error(error)
            return False, None, error

        # VALIDATION 4: Idempotency check
        client_order_id = f"{signal.strategy_name}_{signal.symbol}_{signal.id}_{uuid.uuid4().hex[:8]}"

        stmt = select(ExecutionOrder).where(ExecutionOrder.client_order_id == client_order_id)
        result = await self.db.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            error = f"Order with client_order_id {client_order_id} already exists"
            logger.warning(error)
            return False, existing, error

        # Create execution order
        order = ExecutionOrder(
            client_order_id=client_order_id,
            broker_type=broker_type,
            symbol=signal.symbol,
            order_type=OrderType.MARKET,
            side=OrderSide.BUY if signal.signal_type == SignalType.LONG else OrderSide.SELL,
            quantity=position_size,
            price=signal.entry_price,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            status=OrderStatus.PENDING,
            signal_id=signal.id,
            strategy_name=signal.strategy_name
        )

        self.db.add(order)
        await self.db.commit()
        await self.db.refresh(order)

        # Log creation
        await self._log_event(order.id, "order_created", {"client_order_id": client_order_id})

        # Submit to broker
        try:
            broker_response = await broker.submit_order(order)

            # Update order with broker response
            order.broker_order_id = broker_response.get("broker_order_id")
            order.status = OrderStatus[broker_response.get("status", "SUBMITTED").upper()]
            order.submitted_at = datetime.utcnow()

            if order.status == OrderStatus.FILLED:
                order.filled_quantity = broker_response.get("filled_quantity", 0.0)
                order.average_fill_price = broker_response.get("average_fill_price")
                order.filled_at = datetime.utcnow()

            await self.db.commit()

            # Log submission
            await self._log_event(order.id, "order_submitted", broker_response, OrderStatus.PENDING.value, order.status.value)

            # Update signal status
            if order.status == OrderStatus.FILLED:
                signal.status = SignalStatus.EXECUTED
                signal.executed_at = datetime.utcnow()
                await self.db.commit()

            logger.info(f"Order executed: {order.client_order_id} status={order.status.value}")

            return True, order, None

        except Exception as e:
            logger.error(f"Order execution failed: {e}")

            order.status = OrderStatus.FAILED
            order.error_message = str(e)
            await self.db.commit()

            await self._log_event(order.id, "execution_failed", {"error": str(e)}, OrderStatus.PENDING.value, OrderStatus.FAILED.value)

            return False, order, str(e)

    async def monitor_order(self, order_id: int) -> ExecutionOrder:
        """
        Monitor order status and update from broker.

        Args:
            order_id: Order ID

        Returns:
            Updated order
        """
        stmt = select(ExecutionOrder).where(ExecutionOrder.id == order_id)
        result = await self.db.execute(stmt)
        order = result.scalar_one_or_none()

        if not order:
            raise ValueError(f"Order {order_id} not found")

        if not order.broker_order_id:
            logger.warning(f"Order {order_id} has no broker_order_id")
            return order

        # Get broker
        broker = self.broker_adapters.get(order.broker_type)
        if not broker:
            logger.warning(f"Broker {order.broker_type.value} not available")
            return order

        # Query broker for status
        try:
            broker_status = await broker.get_order_status(order.broker_order_id)

            old_status = order.status.value
            new_status = broker_status.get("status", order.status.value)

            if new_status != old_status:
                order.status = OrderStatus[new_status.upper()]

                if order.status == OrderStatus.FILLED:
                    order.filled_quantity = broker_status.get("filled_quantity", order.quantity)
                    order.average_fill_price = broker_status.get("average_fill_price")
                    order.filled_at = datetime.utcnow()

                await self.db.commit()

                await self._log_event(order.id, "status_updated", broker_status, old_status, new_status)

                logger.info(f"Order {order.client_order_id} status updated: {old_status} → {new_status}")

        except Exception as e:
            logger.error(f"Failed to monitor order {order_id}: {e}")

        return order

    async def cancel_order(self, order_id: int) -> bool:
        """
        Cancel an order.

        Args:
            order_id: Order ID

        Returns:
            True if cancellation successful
        """
        stmt = select(ExecutionOrder).where(ExecutionOrder.id == order_id)
        result = await self.db.execute(stmt)
        order = result.scalar_one_or_none()

        if not order:
            logger.error(f"Order {order_id} not found")
            return False

        if order.status in [OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED]:
            logger.warning(f"Cannot cancel order {order_id} with status {order.status.value}")
            return False

        # Get broker
        broker = self.broker_adapters.get(order.broker_type)
        if not broker or not order.broker_order_id:
            logger.error(f"Cannot cancel order {order_id}: broker not available")
            return False

        # Cancel with broker
        try:
            success = await broker.cancel_order(order.broker_order_id)

            if success:
                old_status = order.status.value
                order.status = OrderStatus.CANCELLED
                await self.db.commit()

                await self._log_event(order.id, "order_cancelled", {}, old_status, OrderStatus.CANCELLED.value)

                logger.info(f"Order {order.client_order_id} cancelled")
                return True

        except Exception as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")

        return False

    async def _log_event(
        self,
        order_id: int,
        event_type: str,
        event_data: Dict[str, Any],
        old_status: Optional[str] = None,
        new_status: Optional[str] = None
    ):
        """Log execution event."""
        log = ExecutionLog(
            order_id=order_id,
            event_type=event_type,
            event_data=event_data,
            old_status=old_status,
            new_status=new_status,
            event_time=datetime.utcnow()
        )

        self.db.add(log)
        await self.db.commit()
```

### Step 5: Database Migration

```bash
cd backend
DATABASE_URL="sqlite+aiosqlite:///./flowrex_dev.db" python -m alembic revision --autogenerate -m "add_execution_tables"
```

Run migration:
```bash
DATABASE_URL="sqlite+aiosqlite:///./flowrex_dev.db" python -m alembic upgrade head
```

### Step 6: API Routes

Create `backend/app/api/v1/execution_routes.py`:

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from pydantic import BaseModel
from app.database import get_db
from app.execution.engine import ExecutionEngine
from app.models.execution import ExecutionOrder, ExecutionLog, BrokerType
from app.models.signal import Signal
from sqlalchemy import select, desc
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/execution", tags=["execution"])


class ExecuteSignalRequest(BaseModel):
    signal_id: int
    position_size: float
    broker_type: str = "paper"


class OrderResponse(BaseModel):
    id: int
    client_order_id: str
    broker_order_id: str | None
    symbol: str
    side: str
    quantity: float
    status: str
    filled_quantity: float
    average_fill_price: float | None

    class Config:
        from_attributes = True


@router.post("/execute")
async def execute_signal(
    request: ExecuteSignalRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Execute a trading signal.

    CRITICAL: This is the ONLY endpoint that places live trades.
    """
    # Get signal
    stmt = select(Signal).where(Signal.id == request.signal_id)
    result = await db.execute(stmt)
    signal = result.scalar_one_or_none()

    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")

    # Validate broker type
    try:
        broker_type = BrokerType[request.broker_type.upper()]
    except KeyError:
        raise HTTPException(status_code=400, detail=f"Invalid broker type: {request.broker_type}")

    # Execute
    engine = ExecutionEngine(db=db)

    success, order, error = await engine.execute_signal(
        signal=signal,
        position_size=request.position_size,
        broker_type=broker_type
    )

    if not success:
        raise HTTPException(status_code=400, detail=error)

    return {
        "success": True,
        "order": OrderResponse.model_validate(order)
    }


@router.get("/orders", response_model=List[OrderResponse])
async def get_orders(
    status: str | None = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
):
    """Get execution orders."""
    stmt = select(ExecutionOrder)

    if status:
        stmt = stmt.where(ExecutionOrder.status == status)

    stmt = stmt.order_by(desc(ExecutionOrder.created_at)).limit(limit)

    result = await db.execute(stmt)
    orders = result.scalars().all()

    return orders


@router.get("/orders/{order_id}")
async def get_order(order_id: int, db: AsyncSession = Depends(get_db)):
    """Get order details with execution log."""
    stmt = select(ExecutionOrder).where(ExecutionOrder.id == order_id)
    result = await db.execute(stmt)
    order = result.scalar_one_or_none()

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # Get execution log
    stmt = select(ExecutionLog).where(ExecutionLog.order_id == order_id).order_by(ExecutionLog.event_time.asc())
    result = await db.execute(stmt)
    logs = result.scalars().all()

    return {
        "order": OrderResponse.model_validate(order),
        "execution_log": [
            {
                "event_type": log.event_type,
                "event_data": log.event_data,
                "old_status": log.old_status,
                "new_status": log.new_status,
                "event_time": log.event_time
            }
            for log in logs
        ]
    }


@router.post("/orders/{order_id}/cancel")
async def cancel_order(order_id: int, db: AsyncSession = Depends(get_db)):
    """Cancel an order."""
    engine = ExecutionEngine(db=db)

    success = await engine.cancel_order(order_id)

    if not success:
        raise HTTPException(status_code=400, detail="Failed to cancel order")

    return {"success": True, "message": f"Order {order_id} cancelled"}


@router.post("/orders/{order_id}/monitor")
async def monitor_order(order_id: int, db: AsyncSession = Depends(get_db)):
    """Monitor and update order status from broker."""
    engine = ExecutionEngine(db=db)

    order = await engine.monitor_order(order_id)

    return OrderResponse.model_validate(order)
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
    execution_routes
)

app.include_router(execution_routes.router, prefix="/api/v1")
```

### Step 7: Tests

Create `backend/tests/unit/test_execution.py`:

```python
import pytest
from datetime import datetime
from app.execution.engine import ExecutionEngine
from app.execution.paper_broker import PaperBroker
from app.models.execution import BrokerType, OrderStatus
from app.models.signal import Signal, SignalType, SignalStatus
from app.models.ai_agent import SystemConfig


@pytest.mark.asyncio
class TestPaperBroker:
    async def test_connect(self):
        broker = PaperBroker({"initial_balance": 10000.0})
        connected = await broker.connect()
        assert connected is True
        assert broker.is_connected is True

    async def test_submit_market_order(self, async_db_session):
        broker = PaperBroker({"initial_balance": 10000.0})
        await broker.connect()

        # Create order
        from app.models.execution import ExecutionOrder, OrderType, OrderSide

        order = ExecutionOrder(
            client_order_id="TEST_001",
            broker_type=BrokerType.PAPER,
            symbol="EURUSD",
            order_type=OrderType.MARKET,
            side=OrderSide.BUY,
            quantity=1.0,
            price=1.1000,
            status=OrderStatus.PENDING,
            strategy_name="TEST"
        )

        response = await broker.submit_order(order)

        assert "broker_order_id" in response
        assert response["status"] == OrderStatus.FILLED.value
        assert response["filled_quantity"] == 1.0


@pytest.mark.asyncio
class TestExecutionEngine:
    async def test_execute_signal_guide_mode_blocked(self, async_db_session):
        """Test that execution is blocked in GUIDE mode."""
        # Set GUIDE mode
        config = SystemConfig(
            key="system_mode",
            value={"mode": "guide"}
        )
        async_db_session.add(config)

        # Create signal
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

        # Try to execute
        engine = ExecutionEngine(db=async_db_session)

        success, order, error = await engine.execute_signal(
            signal=signal,
            position_size=1.0,
            broker_type=BrokerType.PAPER
        )

        assert success is False
        assert "GUIDE mode" in error

    async def test_execute_signal_autonomous_mode(self, async_db_session):
        """Test successful execution in AUTONOMOUS mode."""
        # Set AUTONOMOUS mode
        config = SystemConfig(
            key="system_mode",
            value={"mode": "autonomous"}
        )
        async_db_session.add(config)

        # Create broker connection
        from app.models.execution import BrokerConnection

        broker_conn = BrokerConnection(
            broker_type=BrokerType.PAPER,
            credentials={"initial_balance": 10000.0},
            is_active=True
        )
        async_db_session.add(broker_conn)

        # Create signal
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

        # Execute
        engine = ExecutionEngine(db=async_db_session)

        success, order, error = await engine.execute_signal(
            signal=signal,
            position_size=1.0,
            broker_type=BrokerType.PAPER
        )

        assert success is True
        assert order is not None
        assert order.status == OrderStatus.FILLED
```

Run tests:
```bash
cd backend
DATABASE_URL="sqlite+aiosqlite:///./flowrex_dev.db" python -m pytest tests/unit/test_execution.py -v
```

## Validation Checklist

Before proceeding to Prompt 11, verify:

- [ ] ExecutionOrder, ExecutionLog, BrokerConnection models created
- [ ] Database migration applied successfully
- [ ] BaseBrokerAdapter abstract class defines broker interface
- [ ] PaperBroker implements simulation trading
- [ ] ExecutionEngine enforces pre-execution validation (4 checks)
- [ ] Execution blocked in GUIDE mode
- [ ] Execution allowed in AUTONOMOUS mode only
- [ ] Client order IDs are unique (idempotency)
- [ ] Orders have deterministic status transitions
- [ ] Broker submission is retry-safe
- [ ] Order monitoring updates status from broker
- [ ] Order cancellation works correctly
- [ ] All execution events logged to ExecutionLog
- [ ] API route `/execution/execute` executes signals
- [ ] API route `/execution/orders` lists orders
- [ ] API route `/execution/orders/{id}` returns order with log
- [ ] API route `/execution/orders/{id}/cancel` cancels orders
- [ ] API route `/execution/orders/{id}/monitor` updates status
- [ ] All unit tests pass
- [ ] GUIDE mode blocks execution
- [ ] AUTONOMOUS mode allows execution
- [ ] Paper broker fills market orders instantly
- [ ] Execution failures are logged with error messages
- [ ] CROSSCHECK.md validation for Prompt 10 completed

## Hard Stop Criteria

**DO NOT PROCEED to Prompt 11 unless:**

1. ✅ Database migration runs without errors
2. ✅ All pytest tests pass (0 failures, 0 errors)
3. ✅ Execution is BLOCKED in GUIDE mode
4. ✅ Execution is ALLOWED in AUTONOMOUS mode only
5. ✅ Pre-execution validation enforces all 4 checks
6. ✅ Orders are idempotent (duplicate client_order_id rejected)
7. ✅ All execution events logged to audit trail
8. ✅ Broker adapter interface is clearly defined
9. ✅ Paper broker simulation works correctly
10. ✅ CROSSCHECK.md section for Prompt 10 fully validated

If any criterion fails, **HALT** and fix before continuing.

---

**Completion Criteria:**
- Execution engine fully operational
- Broker abstraction layer complete
- Pre-execution validation enforced
- Order lifecycle management working
- Execution audit trail complete
- System ready for Journaling and Feedback (Prompt 11)
