# 16_SIMULATION_AND_DEMO_MODE.md

## Purpose and Scope

This prompt instructs Opus 4.5 to implement a comprehensive simulation and demo trading mode system that allows users to:
- Test strategies risk-free with simulated market data and execution
- Practice using the platform before risking real capital
- Run AI agents in full autonomous mode without live trading risk
- Validate strategy logic and parameters in realistic conditions

**Core Principles:**
1. **Safety First**: Impossible to accidentally execute live trades while in simulation mode
2. **Realistic Simulation**: Accurately model fills, slippage, latency, and market impact
3. **Data Isolation**: Complete separation between simulation and live data/state
4. **Clear Indicators**: Unmistakable UI signals showing current mode
5. **Default to Safe**: New users start in simulation mode by default
6. **Explicit Confirmation**: Switching to live requires explicit user acknowledgment

**Integration Points:**
- Extends EXECUTION_ENGINE.md (prompt 10) with simulated adapters
- Extends SETTINGS_AND_MODES.md (prompt 14) with execution mode
- Integrates with JOURNALING_AND_FEEDBACK.md (prompt 11) for simulation tagging
- Works with AI_AGENT_SYSTEM.md (prompt 07) for unrestricted AI in simulation

---

## Mode Definitions

### Three Execution Modes

**1. SIMULATION Mode (Default)**
- Uses simulated broker adapter
- No real broker connection required
- Virtual account balance (default: $10,000)
- Simulated fills with realistic slippage/latency
- All AI agents can run fully autonomous
- Journal entries tagged as "SIMULATED"
- WebSocket events use simulation data stream

**2. PAPER Mode (Optional)**
- Connects to real broker in paper trading mode
- Uses broker's paper trading account
- Real market data, simulated execution
- Broker handles fill simulation
- Useful for validating broker integration
- Requires broker credentials

**3. LIVE Mode (Production)**
- Real broker connection
- Real money at risk
- Real execution with real fills
- Restricted AI autonomy (respects hard caps)
- Maximum safeguards enabled
- Requires explicit opt-in

### Mode Transition Rules

```
SIMULATION → PAPER: Allowed with user confirmation
SIMULATION → LIVE: Allowed with explicit warning + confirmation
PAPER → SIMULATION: Allowed (cancels open orders by default)
PAPER → LIVE: Allowed with explicit warning + confirmation
LIVE → SIMULATION: Allowed (cancels ALL live orders, requires confirmation)
LIVE → PAPER: Allowed (cancels ALL live orders, requires confirmation)
```

**Safeguards:**
- Mode stored in database, not just memory
- Mode changes logged to audit trail
- Switching to LIVE requires password re-entry
- Open positions in LIVE prevent mode switching (user must close first)
- Background sync prevents multiple instances from conflicting modes

---

## System Architecture

### Execution Mode Hierarchy

```
┌─────────────────────────────────────┐
│   System Settings (execution_mode)  │
│   - simulation (default)            │
│   - paper                           │
│   - live                            │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│   Execution Engine Adapter Factory  │
│   - Routes to correct adapter       │
│   - Enforces mode isolation         │
└──────────────┬──────────────────────┘
               │
       ┌───────┴──────────┐
       ▼                  ▼
┌──────────────┐   ┌──────────────┐
│ Simulated    │   │ Live Broker  │
│ Adapter      │   │ Adapter      │
│ - Fill sim   │   │ - OANDA      │
│ - Slippage   │   │ - MT5        │
│ - Latency    │   │ - Real fills │
└──────────────┘   └──────────────┘
```

### Data Isolation

**Simulation Data:**
- Separate `simulation_accounts` table
- Virtual balance, equity, margin
- Independent from live accounts

**Live Data:**
- Real `broker_accounts` table
- Actual balance from broker API
- Never mixed with simulation data

**Shared Data (Tagged):**
- `signals` table has `execution_mode` column
- `trades` table has `execution_mode` column
- `journal_entries` table has `execution_mode` column
- Queries filter by mode to prevent cross-contamination

---

## Backend Implementation

### Database Models

**File: `backend/app/models/execution_mode.py`**

```python
from enum import Enum
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func
from app.models.base import Base


class ExecutionMode(str, Enum):
    """Execution mode for trading operations."""
    SIMULATION = "simulation"
    PAPER = "paper"
    LIVE = "live"


class SimulationAccount(Base):
    """Virtual account for simulation mode."""
    __tablename__ = "simulation_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)

    # Account state
    balance: Mapped[float] = mapped_column(Float, nullable=False, default=10000.0)
    equity: Mapped[float] = mapped_column(Float, nullable=False, default=10000.0)
    margin_used: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    margin_available: Mapped[float] = mapped_column(Float, nullable=False, default=10000.0)

    # Configuration
    initial_balance: Mapped[float] = mapped_column(Float, nullable=False, default=10000.0)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")

    # Simulation parameters
    slippage_pips: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    commission_per_lot: Mapped[float] = mapped_column(Float, nullable=False, default=7.0)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    fill_probability: Mapped[float] = mapped_column(Float, nullable=False, default=0.98)

    # Metadata
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="simulation_account")

    def reset(self) -> None:
        """Reset account to initial state."""
        self.balance = self.initial_balance
        self.equity = self.initial_balance
        self.margin_used = 0.0
        self.margin_available = self.initial_balance


class ExecutionModeAudit(Base):
    """Audit trail for execution mode changes."""
    __tablename__ = "execution_mode_audit"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)

    old_mode: Mapped[ExecutionMode] = mapped_column(SQLEnum(ExecutionMode), nullable=True)
    new_mode: Mapped[ExecutionMode] = mapped_column(SQLEnum(ExecutionMode), nullable=False)

    reason: Mapped[str] = mapped_column(String(500), nullable=True)
    ip_address: Mapped[str] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str] = mapped_column(String(500), nullable=True)

    # Safeguards
    confirmation_required: Mapped[bool] = mapped_column(Boolean, default=False)
    password_verified: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    user: Mapped["User"] = relationship("User")
```

**File: `backend/app/models/__init__.py`** (update)

```python
from app.models.execution_mode import ExecutionMode, SimulationAccount, ExecutionModeAudit

__all__ = [
    # ... existing exports
    "ExecutionMode",
    "SimulationAccount",
    "ExecutionModeAudit",
]
```

### Simulated Execution Adapter

**File: `backend/app/execution/adapters/simulated_adapter.py`**

```python
import asyncio
import random
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from app.execution.adapters.base import BaseBrokerAdapter, OrderResult, PositionInfo, AccountInfo
from app.models.execution_mode import SimulationAccount
from sqlalchemy.ext.asyncio import AsyncSession


class SimulatedBrokerAdapter(BaseBrokerAdapter):
    """Simulated broker adapter for demo/simulation mode."""

    def __init__(self, db: AsyncSession, simulation_account: SimulationAccount):
        super().__init__()
        self.db = db
        self.account = simulation_account
        self._open_positions: Dict[str, PositionInfo] = {}
        self._pending_orders: Dict[str, Dict[str, Any]] = {}
        self._order_counter = 0

    async def connect(self) -> bool:
        """Simulate connection (always succeeds)."""
        await asyncio.sleep(0.1)  # Simulate network latency
        self._connected = True
        return True

    async def disconnect(self) -> None:
        """Simulate disconnection."""
        self._connected = False

    async def get_account_info(self) -> AccountInfo:
        """Return simulated account information."""
        return AccountInfo(
            balance=self.account.balance,
            equity=self.account.equity,
            margin_used=self.account.margin_used,
            margin_available=self.account.margin_available,
            currency=self.account.currency,
        )

    async def place_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        order_type: str = "market",
        price: Optional[float] = None,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
    ) -> OrderResult:
        """Simulate order placement with realistic fills."""
        if not self._connected:
            return OrderResult(
                success=False,
                error="Not connected to broker",
            )

        # Simulate network latency
        await asyncio.sleep(self.account.latency_ms / 1000.0)

        # Generate order ID
        self._order_counter += 1
        order_id = f"SIM_{self._order_counter:08d}"

        # Simulate fill probability
        if random.random() > self.account.fill_probability:
            return OrderResult(
                success=False,
                order_id=order_id,
                error="Order rejected (simulated)",
            )

        # For market orders, simulate immediate fill
        if order_type == "market":
            # Simulate slippage
            slippage = random.gauss(self.account.slippage_pips, self.account.slippage_pips / 2)

            # Get current market price (would come from data engine in real implementation)
            fill_price = await self._get_market_price(symbol)

            # Apply slippage
            if side == "buy":
                fill_price += slippage * 0.0001  # Assuming 4-decimal pairs
            else:
                fill_price -= slippage * 0.0001

            # Create position
            position = PositionInfo(
                symbol=symbol,
                side=side,
                quantity=quantity,
                entry_price=fill_price,
                current_price=fill_price,
                unrealized_pnl=0.0,
                stop_loss=stop_loss,
                take_profit=take_profit,
            )

            self._open_positions[order_id] = position

            # Update account margin
            await self._update_margin()

            return OrderResult(
                success=True,
                order_id=order_id,
                fill_price=fill_price,
                filled_quantity=quantity,
                status="filled",
            )

        # For limit/stop orders, store as pending
        else:
            self._pending_orders[order_id] = {
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "order_type": order_type,
                "price": price,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "placed_at": datetime.utcnow(),
            }

            return OrderResult(
                success=True,
                order_id=order_id,
                status="pending",
            )

    async def close_position(self, order_id: str) -> OrderResult:
        """Simulate position closing."""
        if order_id not in self._open_positions:
            return OrderResult(
                success=False,
                error=f"Position {order_id} not found",
            )

        # Simulate latency
        await asyncio.sleep(self.account.latency_ms / 1000.0)

        position = self._open_positions[order_id]

        # Get current market price
        current_price = await self._get_market_price(position.symbol)

        # Apply slippage
        slippage = random.gauss(self.account.slippage_pips, self.account.slippage_pips / 2)
        if position.side == "buy":
            exit_price = current_price - slippage * 0.0001
        else:
            exit_price = current_price + slippage * 0.0001

        # Calculate PnL
        if position.side == "buy":
            pnl = (exit_price - position.entry_price) * position.quantity * 100000  # Assuming standard lot
        else:
            pnl = (position.entry_price - exit_price) * position.quantity * 100000

        # Deduct commission
        commission = self.account.commission_per_lot * position.quantity
        pnl -= commission

        # Update account balance
        self.account.balance += pnl
        self.account.equity += pnl

        # Remove position
        del self._open_positions[order_id]

        # Update margin
        await self._update_margin()

        # Persist account state
        await self.db.commit()

        return OrderResult(
            success=True,
            order_id=order_id,
            fill_price=exit_price,
            filled_quantity=position.quantity,
            status="closed",
            pnl=pnl,
        )

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel pending order."""
        if order_id in self._pending_orders:
            del self._pending_orders[order_id]
            return True
        return False

    async def get_positions(self) -> List[PositionInfo]:
        """Return all open positions."""
        # Update current prices and unrealized PnL
        for order_id, position in self._open_positions.items():
            current_price = await self._get_market_price(position.symbol)
            position.current_price = current_price

            if position.side == "buy":
                position.unrealized_pnl = (current_price - position.entry_price) * position.quantity * 100000
            else:
                position.unrealized_pnl = (position.entry_price - current_price) * position.quantity * 100000

        return list(self._open_positions.values())

    async def get_order_status(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Get status of an order."""
        if order_id in self._open_positions:
            return {"status": "filled", "position": self._open_positions[order_id]}
        elif order_id in self._pending_orders:
            return {"status": "pending", "order": self._pending_orders[order_id]}
        else:
            return {"status": "not_found"}

    async def _get_market_price(self, symbol: str) -> float:
        """Get current market price for symbol (placeholder - would integrate with data engine)."""
        # In real implementation, this would call the data engine
        # For now, return a placeholder price
        base_prices = {
            "EURUSD": 1.1000,
            "GBPUSD": 1.3000,
            "USDJPY": 110.00,
            "AUDUSD": 0.7500,
        }

        base_price = base_prices.get(symbol, 1.0000)

        # Add some random movement
        movement = random.gauss(0, 0.0001)
        return base_price + movement

    async def _update_margin(self) -> None:
        """Update margin calculations."""
        total_margin = 0.0

        for position in self._open_positions.values():
            # Simplified margin calculation (1:100 leverage)
            position_value = position.quantity * 100000 * position.current_price
            margin_required = position_value / 100
            total_margin += margin_required

        self.account.margin_used = total_margin
        self.account.margin_available = self.account.equity - total_margin

        # Update equity with unrealized PnL
        total_unrealized = sum(p.unrealized_pnl for p in self._open_positions.values())
        self.account.equity = self.account.balance + total_unrealized

        await self.db.commit()
```

### Execution Engine Service (Updated)

**File: `backend/app/services/execution_service.py`** (update)

```python
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.user import User
from app.models.execution_mode import ExecutionMode, SimulationAccount
from app.models.settings import SystemSettings
from app.execution.adapters.base import BaseBrokerAdapter
from app.execution.adapters.simulated_adapter import SimulatedBrokerAdapter
from app.execution.adapters.oanda_adapter import OandaAdapter
from app.execution.adapters.mt5_adapter import MT5Adapter


class ExecutionService:
    """Service for managing trade execution across different modes."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self._adapter_cache: Dict[int, BaseBrokerAdapter] = {}

    async def get_adapter(self, user_id: int) -> BaseBrokerAdapter:
        """Get appropriate broker adapter based on execution mode."""
        # Check cache first
        if user_id in self._adapter_cache:
            adapter = self._adapter_cache[user_id]
            if adapter.is_connected():
                return adapter

        # Get system settings to determine execution mode
        result = await self.db.execute(select(SystemSettings).where(SystemSettings.id == 1))
        settings = result.scalar_one_or_none()

        if not settings:
            raise ValueError("System settings not found")

        execution_mode = settings.execution_mode

        # Route to appropriate adapter
        if execution_mode == ExecutionMode.SIMULATION:
            adapter = await self._get_simulation_adapter(user_id)
        elif execution_mode == ExecutionMode.PAPER:
            adapter = await self._get_paper_adapter(user_id)
        elif execution_mode == ExecutionMode.LIVE:
            adapter = await self._get_live_adapter(user_id)
        else:
            raise ValueError(f"Unknown execution mode: {execution_mode}")

        # Connect adapter
        connected = await adapter.connect()
        if not connected:
            raise ConnectionError(f"Failed to connect to broker in {execution_mode} mode")

        # Cache adapter
        self._adapter_cache[user_id] = adapter

        return adapter

    async def _get_simulation_adapter(self, user_id: int) -> SimulatedBrokerAdapter:
        """Get or create simulation adapter."""
        # Get or create simulation account
        result = await self.db.execute(
            select(SimulationAccount).where(SimulationAccount.user_id == user_id)
        )
        sim_account = result.scalar_one_or_none()

        if not sim_account:
            # Create new simulation account with defaults
            sim_account = SimulationAccount(
                user_id=user_id,
                balance=10000.0,
                equity=10000.0,
                initial_balance=10000.0,
                currency="USD",
            )
            self.db.add(sim_account)
            await self.db.commit()
            await self.db.refresh(sim_account)

        return SimulatedBrokerAdapter(self.db, sim_account)

    async def _get_paper_adapter(self, user_id: int) -> BaseBrokerAdapter:
        """Get paper trading adapter (uses broker's paper account)."""
        # Get user's broker configuration
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if not user:
            raise ValueError(f"User {user_id} not found")

        # Get system settings for broker type
        result = await self.db.execute(select(SystemSettings).where(SystemSettings.id == 1))
        settings = result.scalar_one_or_none()

        broker_type = settings.broker_type if settings else "oanda"

        # Create appropriate adapter in paper mode
        if broker_type == "oanda":
            return OandaAdapter(
                account_id=user.broker_account_id,
                api_key=user.broker_api_key,
                paper_mode=True,
            )
        elif broker_type == "mt5":
            return MT5Adapter(
                account_id=user.broker_account_id,
                password=user.broker_password,
                server=user.broker_server,
                paper_mode=True,
            )
        else:
            raise ValueError(f"Unsupported broker type: {broker_type}")

    async def _get_live_adapter(self, user_id: int) -> BaseBrokerAdapter:
        """Get live trading adapter (REAL MONEY)."""
        # Get user's broker configuration
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if not user:
            raise ValueError(f"User {user_id} not found")

        # Verify user has completed live trading setup
        if not user.live_trading_enabled:
            raise PermissionError("Live trading not enabled for this user")

        # Get system settings for broker type
        result = await self.db.execute(select(SystemSettings).where(SystemSettings.id == 1))
        settings = result.scalar_one_or_none()

        broker_type = settings.broker_type if settings else "oanda"

        # Create appropriate adapter in live mode
        if broker_type == "oanda":
            return OandaAdapter(
                account_id=user.broker_account_id,
                api_key=user.broker_api_key,
                paper_mode=False,  # LIVE MODE
            )
        elif broker_type == "mt5":
            return MT5Adapter(
                account_id=user.broker_account_id,
                password=user.broker_password,
                server=user.broker_server,
                paper_mode=False,  # LIVE MODE
            )
        else:
            raise ValueError(f"Unsupported broker type: {broker_type}")

    async def clear_adapter_cache(self, user_id: Optional[int] = None) -> None:
        """Clear adapter cache (useful when switching modes)."""
        if user_id:
            if user_id in self._adapter_cache:
                await self._adapter_cache[user_id].disconnect()
                del self._adapter_cache[user_id]
        else:
            # Clear all cached adapters
            for adapter in self._adapter_cache.values():
                await adapter.disconnect()
            self._adapter_cache.clear()
```

### Mode Switching Service

**File: `backend/app/services/execution_mode_service.py`**

```python
from typing import Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.execution_mode import ExecutionMode, ExecutionModeAudit, SimulationAccount
from app.models.settings import SystemSettings
from app.models.user import User
from app.services.execution_service import ExecutionService
from datetime import datetime


class ExecutionModeService:
    """Service for managing execution mode transitions."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.execution_service = ExecutionService(db)

    async def get_current_mode(self) -> ExecutionMode:
        """Get current execution mode."""
        result = await self.db.execute(select(SystemSettings).where(SystemSettings.id == 1))
        settings = result.scalar_one_or_none()

        if not settings:
            # Default to simulation if settings don't exist
            return ExecutionMode.SIMULATION

        return settings.execution_mode

    async def set_execution_mode(
        self,
        new_mode: ExecutionMode,
        user_id: int,
        reason: Optional[str] = None,
        password: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """Change execution mode with validation and safeguards."""
        # Get current mode
        current_mode = await self.get_current_mode()

        if current_mode == new_mode:
            return False, f"Already in {new_mode.value} mode"

        # Validate transition
        valid, message = await self._validate_transition(current_mode, new_mode, user_id, password)
        if not valid:
            return False, message

        # Check for open positions in LIVE mode
        if current_mode == ExecutionMode.LIVE:
            has_positions = await self._check_open_positions(user_id)
            if has_positions:
                return False, "Cannot switch mode with open LIVE positions. Please close all positions first."

        # Update system settings
        result = await self.db.execute(select(SystemSettings).where(SystemSettings.id == 1))
        settings = result.scalar_one_or_none()

        if not settings:
            return False, "System settings not found"

        old_mode = settings.execution_mode
        settings.execution_mode = new_mode
        settings.updated_at = datetime.utcnow()

        # Create audit record
        audit = ExecutionModeAudit(
            user_id=user_id,
            old_mode=old_mode,
            new_mode=new_mode,
            reason=reason or f"Mode change to {new_mode.value}",
            ip_address=ip_address,
            user_agent=user_agent,
            confirmation_required=self._requires_confirmation(old_mode, new_mode),
            password_verified=password is not None,
        )

        self.db.add(audit)
        await self.db.commit()

        # Clear execution adapter cache to force reconnection
        await self.execution_service.clear_adapter_cache()

        return True, f"Successfully switched to {new_mode.value} mode"

    async def _validate_transition(
        self,
        old_mode: ExecutionMode,
        new_mode: ExecutionMode,
        user_id: int,
        password: Optional[str],
    ) -> Tuple[bool, str]:
        """Validate that mode transition is allowed."""
        # Switching to LIVE requires password verification
        if new_mode == ExecutionMode.LIVE:
            if not password:
                return False, "Password verification required to switch to LIVE mode"

            # Verify password
            result = await self.db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()

            if not user:
                return False, "User not found"

            from app.auth.utils import verify_password
            if not verify_password(password, user.hashed_password):
                return False, "Invalid password"

            # Check if user has live trading enabled
            if not user.live_trading_enabled:
                return False, "Live trading not enabled for this account"

        # Switching from LIVE requires explicit confirmation (handled in UI)
        if old_mode == ExecutionMode.LIVE:
            # Additional safety check - ensure no pending operations
            # This would integrate with execution engine to check for in-flight orders
            pass

        return True, ""

    def _requires_confirmation(self, old_mode: ExecutionMode, new_mode: ExecutionMode) -> bool:
        """Check if mode transition requires explicit confirmation."""
        # Switching to LIVE always requires confirmation
        if new_mode == ExecutionMode.LIVE:
            return True

        # Switching from LIVE always requires confirmation
        if old_mode == ExecutionMode.LIVE:
            return True

        return False

    async def _check_open_positions(self, user_id: int) -> bool:
        """Check if user has open positions."""
        try:
            adapter = await self.execution_service.get_adapter(user_id)
            positions = await adapter.get_positions()
            return len(positions) > 0
        except Exception:
            # If we can't check, assume there might be positions (safe default)
            return True

    async def reset_simulation_account(self, user_id: int) -> Tuple[bool, str]:
        """Reset simulation account to initial state."""
        # Get simulation account
        result = await self.db.execute(
            select(SimulationAccount).where(SimulationAccount.user_id == user_id)
        )
        sim_account = result.scalar_one_or_none()

        if not sim_account:
            return False, "Simulation account not found"

        # Verify we're in simulation mode
        current_mode = await self.get_current_mode()
        if current_mode != ExecutionMode.SIMULATION:
            return False, "Can only reset account in SIMULATION mode"

        # Reset account
        sim_account.reset()
        await self.db.commit()

        # Clear adapter cache to reset open positions
        await self.execution_service.clear_adapter_cache(user_id)

        return True, "Simulation account reset successfully"
```

### API Routes

**File: `backend/app/api/v1/execution_mode_routes.py`**

```python
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from typing import Optional
from app.database import get_db
from app.auth.dependencies import get_current_user
from app.models.user import User
from app.models.execution_mode import ExecutionMode, SimulationAccount
from app.services.execution_mode_service import ExecutionModeService
from sqlalchemy import select

router = APIRouter(prefix="/execution-mode", tags=["execution-mode"])


# Schemas
class ExecutionModeResponse(BaseModel):
    mode: str

    class Config:
        from_attributes = True


class SetExecutionModeRequest(BaseModel):
    mode: str = Field(..., pattern="^(simulation|paper|live)$")
    reason: Optional[str] = None
    password: Optional[str] = None  # Required when switching to LIVE


class SimulationAccountResponse(BaseModel):
    balance: float
    equity: float
    margin_used: float
    margin_available: float
    initial_balance: float
    currency: str
    slippage_pips: float
    commission_per_lot: float
    latency_ms: int
    fill_probability: float

    class Config:
        from_attributes = True


class UpdateSimulationAccountRequest(BaseModel):
    initial_balance: Optional[float] = Field(None, ge=100, le=1000000)
    slippage_pips: Optional[float] = Field(None, ge=0, le=10)
    commission_per_lot: Optional[float] = Field(None, ge=0, le=100)
    latency_ms: Optional[int] = Field(None, ge=0, le=5000)
    fill_probability: Optional[float] = Field(None, ge=0.5, le=1.0)


# Routes
@router.get("", response_model=ExecutionModeResponse)
async def get_execution_mode(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get current execution mode."""
    service = ExecutionModeService(db)
    mode = await service.get_current_mode()
    return ExecutionModeResponse(mode=mode.value)


@router.post("", response_model=ExecutionModeResponse)
async def set_execution_mode(
    request_data: SetExecutionModeRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Change execution mode."""
    service = ExecutionModeService(db)

    try:
        mode = ExecutionMode(request_data.mode)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid execution mode: {request_data.mode}. Must be simulation, paper, or live.",
        )

    # Get client info
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    success, message = await service.set_execution_mode(
        new_mode=mode,
        user_id=current_user.id,
        reason=request_data.reason,
        password=request_data.password,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    if not success:
        raise HTTPException(status_code=400, detail=message)

    return ExecutionModeResponse(mode=mode.value)


@router.get("/simulation-account", response_model=SimulationAccountResponse)
async def get_simulation_account(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get simulation account details."""
    result = await db.execute(
        select(SimulationAccount).where(SimulationAccount.user_id == current_user.id)
    )
    sim_account = result.scalar_one_or_none()

    if not sim_account:
        # Create default simulation account
        sim_account = SimulationAccount(user_id=current_user.id)
        db.add(sim_account)
        await db.commit()
        await db.refresh(sim_account)

    return SimulationAccountResponse.model_validate(sim_account)


@router.patch("/simulation-account", response_model=SimulationAccountResponse)
async def update_simulation_account(
    request_data: UpdateSimulationAccountRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update simulation account parameters."""
    result = await db.execute(
        select(SimulationAccount).where(SimulationAccount.user_id == current_user.id)
    )
    sim_account = result.scalar_one_or_none()

    if not sim_account:
        raise HTTPException(status_code=404, detail="Simulation account not found")

    # Update fields
    if request_data.initial_balance is not None:
        sim_account.initial_balance = request_data.initial_balance
    if request_data.slippage_pips is not None:
        sim_account.slippage_pips = request_data.slippage_pips
    if request_data.commission_per_lot is not None:
        sim_account.commission_per_lot = request_data.commission_per_lot
    if request_data.latency_ms is not None:
        sim_account.latency_ms = request_data.latency_ms
    if request_data.fill_probability is not None:
        sim_account.fill_probability = request_data.fill_probability

    await db.commit()
    await db.refresh(sim_account)

    return SimulationAccountResponse.model_validate(sim_account)


@router.post("/simulation-account/reset", response_model=SimulationAccountResponse)
async def reset_simulation_account(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Reset simulation account to initial state."""
    service = ExecutionModeService(db)
    success, message = await service.reset_simulation_account(current_user.id)

    if not success:
        raise HTTPException(status_code=400, detail=message)

    # Return updated account
    result = await db.execute(
        select(SimulationAccount).where(SimulationAccount.user_id == current_user.id)
    )
    sim_account = result.scalar_one()

    return SimulationAccountResponse.model_validate(sim_account)
```

**File: `backend/app/main.py`** (update)

```python
from app.api.v1 import execution_mode_routes

# Register router
app.include_router(execution_mode_routes.router, prefix="/api/v1")
```

---

## Frontend Implementation

### Execution Mode Context

**File: `frontend/contexts/ExecutionModeContext.tsx`**

```typescript
'use client'

import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '@/services/api'

export type ExecutionMode = 'simulation' | 'paper' | 'live'

interface ExecutionModeContextType {
  mode: ExecutionMode
  isLoading: boolean
  setMode: (mode: ExecutionMode, password?: string, reason?: string) => Promise<void>
  simulationAccount: SimulationAccount | null
  resetSimulationAccount: () => Promise<void>
}

interface SimulationAccount {
  balance: number
  equity: number
  margin_used: number
  margin_available: number
  initial_balance: number
  currency: string
  slippage_pips: number
  commission_per_lot: number
  latency_ms: number
  fill_probability: number
}

const ExecutionModeContext = createContext<ExecutionModeContextType | undefined>(undefined)

export function ExecutionModeProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()

  const { data: modeData, isLoading } = useQuery({
    queryKey: ['executionMode'],
    queryFn: () => apiClient.getExecutionMode(),
    refetchInterval: 10000, // Poll every 10 seconds
  })

  const { data: simulationAccount } = useQuery({
    queryKey: ['simulationAccount'],
    queryFn: () => apiClient.getSimulationAccount(),
    enabled: modeData?.mode === 'simulation',
    refetchInterval: 5000,
  })

  const setModeMutation = useMutation({
    mutationFn: ({ mode, password, reason }: { mode: ExecutionMode; password?: string; reason?: string }) =>
      apiClient.setExecutionMode(mode, password, reason),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['executionMode'] })
      queryClient.invalidateQueries({ queryKey: ['simulationAccount'] })
      queryClient.invalidateQueries({ queryKey: ['accountInfo'] })
      queryClient.invalidateQueries({ queryKey: ['positions'] })
    },
  })

  const resetAccountMutation = useMutation({
    mutationFn: () => apiClient.resetSimulationAccount(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['simulationAccount'] })
      queryClient.invalidateQueries({ queryKey: ['accountInfo'] })
      queryClient.invalidateQueries({ queryKey: ['positions'] })
    },
  })

  const setMode = async (mode: ExecutionMode, password?: string, reason?: string) => {
    await setModeMutation.mutateAsync({ mode, password, reason })
  }

  const resetSimulationAccount = async () => {
    await resetAccountMutation.mutateAsync()
  }

  return (
    <ExecutionModeContext.Provider
      value={{
        mode: modeData?.mode || 'simulation',
        isLoading,
        setMode,
        simulationAccount: simulationAccount || null,
        resetSimulationAccount,
      }}
    >
      {children}
    </ExecutionModeContext.Provider>
  )
}

export function useExecutionMode() {
  const context = useContext(ExecutionModeContext)
  if (context === undefined) {
    throw new Error('useExecutionMode must be used within ExecutionModeProvider')
  }
  return context
}
```

### Mode Indicator Component

**File: `frontend/components/ExecutionModeIndicator.tsx`**

```typescript
'use client'

import React from 'react'
import { useExecutionMode } from '@/contexts/ExecutionModeContext'
import { Shield, AlertTriangle, Zap } from 'lucide-react'

export default function ExecutionModeIndicator() {
  const { mode, isLoading } = useExecutionMode()

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 px-3 py-1 bg-gray-100 rounded-full text-sm">
        <div className="w-2 h-2 bg-gray-400 rounded-full animate-pulse"></div>
        <span className="text-gray-600">Loading...</span>
      </div>
    )
  }

  const configs = {
    simulation: {
      icon: Shield,
      label: 'SIMULATION',
      bgColor: 'bg-blue-100',
      textColor: 'text-blue-800',
      iconColor: 'text-blue-600',
      dotColor: 'bg-blue-500',
    },
    paper: {
      icon: Zap,
      label: 'PAPER',
      bgColor: 'bg-yellow-100',
      textColor: 'text-yellow-800',
      iconColor: 'text-yellow-600',
      dotColor: 'bg-yellow-500',
    },
    live: {
      icon: AlertTriangle,
      label: 'LIVE',
      bgColor: 'bg-red-100',
      textColor: 'text-red-800',
      iconColor: 'text-red-600',
      dotColor: 'bg-red-500',
    },
  }

  const config = configs[mode]
  const Icon = config.icon

  return (
    <div className={`flex items-center gap-2 px-3 py-1 ${config.bgColor} rounded-full text-sm font-medium`}>
      <Icon className={`w-4 h-4 ${config.iconColor}`} />
      <span className={config.textColor}>{config.label}</span>
      <div className={`w-2 h-2 ${config.dotColor} rounded-full animate-pulse`}></div>
    </div>
  )
}
```

### Mode Switcher Component

**File: `frontend/components/ExecutionModeSwitcher.tsx`**

```typescript
'use client'

import React, { useState } from 'react'
import { useExecutionMode } from '@/contexts/ExecutionModeContext'
import type { ExecutionMode } from '@/contexts/ExecutionModeContext'
import { Shield, Zap, AlertTriangle, Lock } from 'lucide-react'

export default function ExecutionModeSwitcher() {
  const { mode, setMode } = useExecutionMode()
  const [showConfirmation, setShowConfirmation] = useState(false)
  const [pendingMode, setPendingMode] = useState<ExecutionMode | null>(null)
  const [password, setPassword] = useState('')
  const [reason, setReason] = useState('')
  const [error, setError] = useState('')
  const [isLoading, setIsLoading] = useState(false)

  const handleModeSelect = (newMode: ExecutionMode) => {
    if (newMode === mode) return

    setPendingMode(newMode)
    setShowConfirmation(true)
    setPassword('')
    setReason('')
    setError('')
  }

  const handleConfirm = async () => {
    if (!pendingMode) return

    setIsLoading(true)
    setError('')

    try {
      await setMode(pendingMode, password || undefined, reason || undefined)
      setShowConfirmation(false)
      setPendingMode(null)
      setPassword('')
      setReason('')
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to change mode')
    } finally {
      setIsLoading(false)
    }
  }

  const handleCancel = () => {
    setShowConfirmation(false)
    setPendingMode(null)
    setPassword('')
    setReason('')
    setError('')
  }

  const modes = [
    {
      value: 'simulation' as ExecutionMode,
      label: 'Simulation',
      icon: Shield,
      description: 'Virtual account, no broker required',
      color: 'blue',
    },
    {
      value: 'paper' as ExecutionMode,
      label: 'Paper Trading',
      icon: Zap,
      description: 'Broker paper account, real data',
      color: 'yellow',
    },
    {
      value: 'live' as ExecutionMode,
      label: 'Live Trading',
      icon: AlertTriangle,
      description: 'Real money at risk',
      color: 'red',
    },
  ]

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-4">
        {modes.map((modeConfig) => {
          const Icon = modeConfig.icon
          const isActive = mode === modeConfig.value

          return (
            <button
              key={modeConfig.value}
              onClick={() => handleModeSelect(modeConfig.value)}
              disabled={isActive}
              className={`p-4 rounded-lg border-2 transition-all ${
                isActive
                  ? `border-${modeConfig.color}-500 bg-${modeConfig.color}-50`
                  : 'border-gray-200 bg-white hover:border-gray-300'
              } ${isActive ? 'cursor-default' : 'cursor-pointer'}`}
            >
              <div className="flex flex-col items-center gap-2">
                <Icon
                  className={`w-8 h-8 ${
                    isActive ? `text-${modeConfig.color}-600` : 'text-gray-400'
                  }`}
                />
                <div className="text-center">
                  <p className={`font-semibold ${isActive ? `text-${modeConfig.color}-900` : 'text-gray-700'}`}>
                    {modeConfig.label}
                  </p>
                  <p className="text-xs text-gray-500 mt-1">{modeConfig.description}</p>
                </div>
                {isActive && (
                  <span className={`text-xs font-medium text-${modeConfig.color}-700`}>
                    ACTIVE
                  </span>
                )}
              </div>
            </button>
          )
        })}
      </div>

      {/* Confirmation Dialog */}
      {showConfirmation && pendingMode && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4">
            <h3 className="text-lg font-bold mb-4">
              Confirm Mode Change
            </h3>

            <div className="mb-4">
              <p className="text-gray-700">
                You are about to switch from <span className="font-semibold">{mode.toUpperCase()}</span> to{' '}
                <span className="font-semibold">{pendingMode.toUpperCase()}</span> mode.
              </p>

              {mode === 'live' && (
                <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded">
                  <p className="text-red-800 text-sm font-medium">
                    ⚠️ All open LIVE positions must be closed before switching modes.
                  </p>
                </div>
              )}

              {pendingMode === 'live' && (
                <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded">
                  <p className="text-red-800 text-sm font-medium">
                    ⚠️ WARNING: You are about to enable LIVE TRADING with real money.
                  </p>
                </div>
              )}
            </div>

            {pendingMode === 'live' && (
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  <Lock className="w-4 h-4 inline mr-1" />
                  Password Required
                </label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter your password"
                  className="w-full px-3 py-2 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            )}

            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Reason (optional)
              </label>
              <textarea
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="Why are you changing modes?"
                rows={3}
                className="w-full px-3 py-2 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            {error && (
              <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded">
                <p className="text-red-800 text-sm">{error}</p>
              </div>
            )}

            <div className="flex gap-3">
              <button
                onClick={handleCancel}
                disabled={isLoading}
                className="flex-1 px-4 py-2 border border-gray-300 rounded hover:bg-gray-50 disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirm}
                disabled={isLoading || (pendingMode === 'live' && !password)}
                className="flex-1 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
              >
                {isLoading ? 'Switching...' : 'Confirm'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
```

### Simulation Account Settings

**File: `frontend/components/SimulationAccountSettings.tsx`**

```typescript
'use client'

import React, { useState } from 'react'
import { useExecutionMode } from '@/contexts/ExecutionModeContext'
import { RefreshCw, DollarSign, TrendingUp, Clock, Target } from 'lucide-react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '@/services/api'

export default function SimulationAccountSettings() {
  const { simulationAccount, resetSimulationAccount } = useExecutionMode()
  const queryClient = useQueryClient()
  const [showResetConfirm, setShowResetConfirm] = useState(false)

  const updateMutation = useMutation({
    mutationFn: (updates: any) => apiClient.updateSimulationAccount(updates),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['simulationAccount'] })
    },
  })

  if (!simulationAccount) {
    return <div>Loading simulation account...</div>
  }

  const handleReset = async () => {
    await resetSimulationAccount()
    setShowResetConfirm(false)
  }

  const handleUpdate = (field: string, value: number) => {
    updateMutation.mutate({ [field]: value })
  }

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold">Simulation Account</h3>
          <button
            onClick={() => setShowResetConfirm(true)}
            className="flex items-center gap-2 px-3 py-1 text-sm bg-gray-100 hover:bg-gray-200 rounded"
          >
            <RefreshCw className="w-4 h-4" />
            Reset Account
          </button>
        </div>

        <div className="grid grid-cols-2 gap-4 mb-6">
          <div className="p-4 bg-blue-50 rounded">
            <div className="flex items-center gap-2 mb-2">
              <DollarSign className="w-5 h-5 text-blue-600" />
              <span className="text-sm text-gray-600">Balance</span>
            </div>
            <p className="text-2xl font-bold text-blue-900">
              ${simulationAccount.balance.toFixed(2)}
            </p>
          </div>

          <div className="p-4 bg-green-50 rounded">
            <div className="flex items-center gap-2 mb-2">
              <TrendingUp className="w-5 h-5 text-green-600" />
              <span className="text-sm text-gray-600">Equity</span>
            </div>
            <p className="text-2xl font-bold text-green-900">
              ${simulationAccount.equity.toFixed(2)}
            </p>
          </div>
        </div>

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              <DollarSign className="w-4 h-4 inline mr-1" />
              Initial Balance
            </label>
            <input
              type="number"
              value={simulationAccount.initial_balance}
              onChange={(e) => handleUpdate('initial_balance', parseFloat(e.target.value))}
              min={100}
              max={1000000}
              step={100}
              className="w-full px-3 py-2 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <p className="text-xs text-gray-500 mt-1">
              Starting balance when account is reset
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              <Target className="w-4 h-4 inline mr-1" />
              Slippage (pips)
            </label>
            <input
              type="number"
              value={simulationAccount.slippage_pips}
              onChange={(e) => handleUpdate('slippage_pips', parseFloat(e.target.value))}
              min={0}
              max={10}
              step={0.1}
              className="w-full px-3 py-2 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <p className="text-xs text-gray-500 mt-1">
              Simulated slippage on order fills
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              <Clock className="w-4 h-4 inline mr-1" />
              Latency (ms)
            </label>
            <input
              type="number"
              value={simulationAccount.latency_ms}
              onChange={(e) => handleUpdate('latency_ms', parseInt(e.target.value))}
              min={0}
              max={5000}
              step={10}
              className="w-full px-3 py-2 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <p className="text-xs text-gray-500 mt-1">
              Simulated network delay for order execution
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Fill Probability
            </label>
            <input
              type="number"
              value={simulationAccount.fill_probability}
              onChange={(e) => handleUpdate('fill_probability', parseFloat(e.target.value))}
              min={0.5}
              max={1.0}
              step={0.01}
              className="w-full px-3 py-2 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <p className="text-xs text-gray-500 mt-1">
              Probability that orders get filled (1.0 = always fill)
            </p>
          </div>
        </div>
      </div>

      {/* Reset Confirmation Dialog */}
      {showResetConfirm && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4">
            <h3 className="text-lg font-bold mb-4">Reset Simulation Account?</h3>
            <p className="text-gray-700 mb-4">
              This will reset your simulation account to the initial balance and close all open positions.
              This action cannot be undone.
            </p>
            <div className="flex gap-3">
              <button
                onClick={() => setShowResetConfirm(false)}
                className="flex-1 px-4 py-2 border border-gray-300 rounded hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={handleReset}
                className="flex-1 px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700"
              >
                Reset Account
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
```

### API Client Methods

**File: `frontend/services/api.ts`** (update)

```typescript
class ApiClient {
  // ... existing methods

  // Execution Mode
  async getExecutionMode() {
    const response = await this.get('/execution-mode')
    return response.data
  }

  async setExecutionMode(mode: string, password?: string, reason?: string) {
    const response = await this.post('/execution-mode', { mode, password, reason })
    return response.data
  }

  async getSimulationAccount() {
    const response = await this.get('/execution-mode/simulation-account')
    return response.data
  }

  async updateSimulationAccount(updates: any) {
    const response = await this.patch('/execution-mode/simulation-account', updates)
    return response.data
  }

  async resetSimulationAccount() {
    const response = await this.post('/execution-mode/simulation-account/reset')
    return response.data
  }
}
```

---

## Database Migration

**File: `backend/alembic/versions/YYYYMMDD_HHMMSS_add_execution_mode.py`**

```python
"""Add execution mode and simulation accounts

Revision ID: YYYYMMDD_HHMMSS
Revises: <previous_revision>
Create Date: YYYY-MM-DD HH:MM:SS
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = 'YYYYMMDD_HHMMSS'
down_revision = '<previous_revision>'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create execution mode enum
    execution_mode_enum = postgresql.ENUM('simulation', 'paper', 'live', name='executionmode')
    execution_mode_enum.create(op.get_bind(), checkfirst=True)

    # Add execution_mode column to system_settings
    op.add_column(
        'system_settings',
        sa.Column('execution_mode', sa.Enum('simulation', 'paper', 'live', name='executionmode'),
                 nullable=False, server_default='simulation')
    )

    # Create simulation_accounts table
    op.create_table(
        'simulation_accounts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('balance', sa.Float(), nullable=False, server_default='10000.0'),
        sa.Column('equity', sa.Float(), nullable=False, server_default='10000.0'),
        sa.Column('margin_used', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('margin_available', sa.Float(), nullable=False, server_default='10000.0'),
        sa.Column('initial_balance', sa.Float(), nullable=False, server_default='10000.0'),
        sa.Column('currency', sa.String(length=3), nullable=False, server_default='USD'),
        sa.Column('slippage_pips', sa.Float(), nullable=False, server_default='0.5'),
        sa.Column('commission_per_lot', sa.Float(), nullable=False, server_default='7.0'),
        sa.Column('latency_ms', sa.Integer(), nullable=False, server_default='100'),
        sa.Column('fill_probability', sa.Float(), nullable=False, server_default='0.98'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.text('now()')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_simulation_accounts_user_id', 'simulation_accounts', ['user_id'], unique=True)

    # Create execution_mode_audit table
    op.create_table(
        'execution_mode_audit',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('old_mode', sa.Enum('simulation', 'paper', 'live', name='executionmode'), nullable=True),
        sa.Column('new_mode', sa.Enum('simulation', 'paper', 'live', name='executionmode'), nullable=False),
        sa.Column('reason', sa.String(length=500), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.String(length=500), nullable=True),
        sa.Column('confirmation_required', sa.Boolean(), server_default='false'),
        sa.Column('password_verified', sa.Boolean(), server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_execution_mode_audit_user_id', 'execution_mode_audit', ['user_id'])

    # Add execution_mode column to signals table
    op.add_column(
        'signals',
        sa.Column('execution_mode', sa.Enum('simulation', 'paper', 'live', name='executionmode'),
                 nullable=False, server_default='simulation')
    )

    # Add execution_mode column to trades table
    op.add_column(
        'trades',
        sa.Column('execution_mode', sa.Enum('simulation', 'paper', 'live', name='executionmode'),
                 nullable=False, server_default='simulation')
    )

    # Add execution_mode column to journal_entries table
    op.add_column(
        'journal_entries',
        sa.Column('execution_mode', sa.Enum('simulation', 'paper', 'live', name='executionmode'),
                 nullable=False, server_default='simulation')
    )

    # Add live_trading_enabled column to users table
    op.add_column(
        'users',
        sa.Column('live_trading_enabled', sa.Boolean(), nullable=False, server_default='false')
    )


def downgrade() -> None:
    # Remove columns
    op.drop_column('users', 'live_trading_enabled')
    op.drop_column('journal_entries', 'execution_mode')
    op.drop_column('trades', 'execution_mode')
    op.drop_column('signals', 'execution_mode')

    # Drop tables
    op.drop_index('ix_execution_mode_audit_user_id', 'execution_mode_audit')
    op.drop_table('execution_mode_audit')
    op.drop_index('ix_simulation_accounts_user_id', 'simulation_accounts')
    op.drop_table('simulation_accounts')

    op.drop_column('system_settings', 'execution_mode')

    # Drop enum
    sa.Enum(name='executionmode').drop(op.get_bind(), checkfirst=True)
```

---

## Testing

### Unit Tests

**File: `backend/tests/unit/test_simulated_adapter.py`**

```python
import pytest
from app.execution.adapters.simulated_adapter import SimulatedBrokerAdapter
from app.models.execution_mode import SimulationAccount


class TestSimulatedAdapter:
    """Test simulated broker adapter."""

    @pytest.fixture
    def sim_account(self, db) -> SimulationAccount:
        """Create a test simulation account."""
        account = SimulationAccount(
            user_id=1,
            balance=10000.0,
            equity=10000.0,
            initial_balance=10000.0,
            slippage_pips=0.5,
            commission_per_lot=7.0,
            latency_ms=100,
            fill_probability=1.0,  # Always fill for testing
        )
        db.add(account)
        db.commit()
        return account

    @pytest.fixture
    async def adapter(self, db, sim_account) -> SimulatedBrokerAdapter:
        """Create and connect adapter."""
        adapter = SimulatedBrokerAdapter(db, sim_account)
        await adapter.connect()
        return adapter

    @pytest.mark.asyncio
    async def test_connect(self, adapter):
        """Test adapter connection."""
        assert adapter.is_connected()

    @pytest.mark.asyncio
    async def test_get_account_info(self, adapter, sim_account):
        """Test getting account information."""
        account_info = await adapter.get_account_info()

        assert account_info.balance == sim_account.balance
        assert account_info.equity == sim_account.equity
        assert account_info.currency == sim_account.currency

    @pytest.mark.asyncio
    async def test_place_market_order(self, adapter):
        """Test placing market order."""
        result = await adapter.place_order(
            symbol="EURUSD",
            side="buy",
            quantity=0.1,
            order_type="market",
            stop_loss=1.0950,
            take_profit=1.1100,
        )

        assert result.success
        assert result.order_id is not None
        assert result.status == "filled"
        assert result.fill_price is not None
        assert result.filled_quantity == 0.1

    @pytest.mark.asyncio
    async def test_close_position(self, adapter, sim_account):
        """Test closing position."""
        # Place order first
        place_result = await adapter.place_order(
            symbol="EURUSD",
            side="buy",
            quantity=0.1,
            order_type="market",
        )

        initial_balance = sim_account.balance

        # Close position
        close_result = await adapter.close_position(place_result.order_id)

        assert close_result.success
        assert close_result.status == "closed"
        assert close_result.pnl is not None

        # Balance should have changed
        assert sim_account.balance != initial_balance

    @pytest.mark.asyncio
    async def test_get_positions(self, adapter):
        """Test getting open positions."""
        # Place two orders
        await adapter.place_order("EURUSD", "buy", 0.1, "market")
        await adapter.place_order("GBPUSD", "sell", 0.2, "market")

        positions = await adapter.get_positions()

        assert len(positions) == 2
        assert all(p.unrealized_pnl is not None for p in positions)

    @pytest.mark.asyncio
    async def test_slippage_applied(self, adapter, sim_account):
        """Test that slippage is applied to fills."""
        # Set higher slippage for testing
        sim_account.slippage_pips = 2.0

        results = []
        for _ in range(10):
            result = await adapter.place_order("EURUSD", "buy", 0.1, "market")
            results.append(result.fill_price)

        # All fills should have different prices due to slippage
        assert len(set(results)) > 1
```

### Integration Tests

**File: `backend/tests/integration/test_execution_mode_switching.py`**

```python
import pytest
from httpx import AsyncClient
from app.models.execution_mode import ExecutionMode
from app.models.user import User


@pytest.mark.integration
class TestExecutionModeSwitching:
    """Test execution mode switching workflow."""

    @pytest.mark.asyncio
    async def test_get_current_mode(self, client: AsyncClient, auth_headers):
        """Test getting current execution mode."""
        response = await client.get("/api/v1/execution-mode", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["mode"] in ["simulation", "paper", "live"]

    @pytest.mark.asyncio
    async def test_switch_to_paper_mode(self, client: AsyncClient, auth_headers):
        """Test switching to paper mode."""
        response = await client.post(
            "/api/v1/execution-mode",
            json={"mode": "paper", "reason": "Testing paper mode"},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["mode"] == "paper"

    @pytest.mark.asyncio
    async def test_switch_to_live_requires_password(self, client: AsyncClient, auth_headers):
        """Test that switching to LIVE requires password."""
        response = await client.post(
            "/api/v1/execution-mode",
            json={"mode": "live"},
            headers=auth_headers,
        )

        assert response.status_code == 400
        assert "password" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_switch_to_live_with_password(self, client: AsyncClient, auth_headers, test_user):
        """Test switching to LIVE with password."""
        # Enable live trading for user
        test_user.live_trading_enabled = True

        response = await client.post(
            "/api/v1/execution-mode",
            json={
                "mode": "live",
                "password": "testpassword123",
                "reason": "Enabling live trading",
            },
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["mode"] == "live"

    @pytest.mark.asyncio
    async def test_get_simulation_account(self, client: AsyncClient, auth_headers):
        """Test getting simulation account details."""
        response = await client.get(
            "/api/v1/execution-mode/simulation-account",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "balance" in data
        assert "equity" in data
        assert "initial_balance" in data

    @pytest.mark.asyncio
    async def test_reset_simulation_account(self, client: AsyncClient, auth_headers, db):
        """Test resetting simulation account."""
        # First, set mode to simulation
        await client.post(
            "/api/v1/execution-mode",
            json={"mode": "simulation"},
            headers=auth_headers,
        )

        # Reset account
        response = await client.post(
            "/api/v1/execution-mode/simulation-account/reset",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["balance"] == data["initial_balance"]
        assert data["equity"] == data["initial_balance"]
        assert data["margin_used"] == 0.0
```

---

## Validation Checklist

Before proceeding, Opus MUST verify:

### Backend Implementation
- [ ] ExecutionMode enum defined (simulation, paper, live)
- [ ] SimulationAccount model created with all fields
- [ ] ExecutionModeAudit model created for audit trail
- [ ] SimulatedBrokerAdapter implemented with realistic fills
- [ ] Fill simulator includes slippage modeling
- [ ] Fill simulator includes latency modeling
- [ ] Fill simulator includes commission calculation
- [ ] ExecutionService routes to correct adapter based on mode
- [ ] ExecutionModeService handles mode switching with validation
- [ ] Password verification required for LIVE mode
- [ ] Open position check prevents mode switching
- [ ] Adapter cache cleared on mode change

### API Implementation
- [ ] GET /execution-mode returns current mode
- [ ] POST /execution-mode changes mode with validation
- [ ] GET /simulation-account returns account details
- [ ] PATCH /simulation-account updates parameters
- [ ] POST /simulation-account/reset resets to initial state
- [ ] All routes protected by authentication
- [ ] Mode changes logged to audit trail

### Frontend Implementation
- [ ] ExecutionModeContext provides mode state
- [ ] ExecutionModeIndicator shows current mode clearly
- [ ] Color-coded mode indicators (blue=sim, yellow=paper, red=live)
- [ ] ExecutionModeSwitcher allows mode selection
- [ ] Confirmation dialog shown for mode changes
- [ ] Password input required for LIVE mode
- [ ] SimulationAccountSettings displays account state
- [ ] Reset account button with confirmation
- [ ] Simulation parameters editable
- [ ] Real-time account balance updates

### Data Isolation
- [ ] execution_mode column added to signals table
- [ ] execution_mode column added to trades table
- [ ] execution_mode column added to journal_entries table
- [ ] All queries filter by execution_mode
- [ ] Simulation data never mixes with live data
- [ ] Separate simulation_accounts table

### Safety Mechanisms
- [ ] Default mode is SIMULATION for new users
- [ ] Switching to LIVE requires password
- [ ] Open LIVE positions block mode switching
- [ ] Mode changes require explicit confirmation
- [ ] Audit trail logs all mode changes
- [ ] Impossible to accidentally execute live trades in simulation
- [ ] Clear visual indicators prevent confusion

### Testing
- [ ] Unit tests for SimulatedBrokerAdapter
- [ ] Unit tests for fill simulation logic
- [ ] Integration tests for mode switching
- [ ] Integration tests for password verification
- [ ] Tests verify data isolation
- [ ] Tests verify adapter routing
- [ ] Tests verify safety mechanisms

### Database
- [ ] Migration adds execution_mode to system_settings
- [ ] Migration creates simulation_accounts table
- [ ] Migration creates execution_mode_audit table
- [ ] Migration adds execution_mode to signals/trades/journal
- [ ] Migration adds live_trading_enabled to users
- [ ] Migration runs without errors

---

## Hard Stop Criteria - DO NOT PROCEED if:

1. **Simulation mode can execute live trades** - The simulated adapter MUST be completely isolated from real broker APIs
2. **No execution mode enum** - ExecutionMode enum does not exist or is not used consistently
3. **Missing confirmation dialogs** - Switching to LIVE does not require explicit user confirmation
4. **No password verification** - Switching to LIVE does not verify user password
5. **Data not isolated** - Simulation and live data can mix in database queries
6. **No mode indicator** - Frontend does not clearly show current execution mode
7. **Default is not simulation** - New users do not start in simulation mode by default
8. **No audit trail** - Mode changes are not logged to execution_mode_audit table
9. **Open positions not checked** - Can switch modes with open LIVE positions
10. **Missing tests** - No tests verify simulation behavior or safety mechanisms

---

## Integration Notes

**Signal Generation** (from 04_STRATEGY_ENGINE.md):
- All signals must be tagged with current execution_mode
- Queries must filter by execution_mode to prevent cross-contamination

**Trade Execution** (from 10_EXECUTION_ENGINE.md):
- Execution engine uses ExecutionService.get_adapter() to route correctly
- Adapter choice determined by system-level execution_mode setting
- Simulated adapter used in simulation mode (never touches broker API)

**Journal Entries** (from 11_JOURNALING_AND_FEEDBACK.md):
- All journal entries tagged with execution_mode
- UI must clearly indicate "SIMULATED" vs "LIVE" trades
- Simulation journal entries use different visual styling

**AI Agents** (from 07_AI_AGENT_SYSTEM.md):
- AI can run fully autonomous in SIMULATION mode
- AI respects hard caps in LIVE mode
- Mode determines AI permission level

**Settings** (from 14_SETTINGS_AND_MODES.md):
- execution_mode stored in system_settings table
- Mode changes propagate to all components
- Broadcast mechanism notifies frontend of mode changes

---

END OF PROMPT 16
