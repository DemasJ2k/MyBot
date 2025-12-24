"""
Execution API routes.

Provides REST endpoints for:
- Executing signals through the execution pipeline
- Managing execution orders
- Querying execution status and history
- Controlling execution mode (GUIDE vs AUTONOMOUS)
"""

from typing import Optional
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ...database import get_db
from ...models.execution import (
    ExecutionOrder,
    ExecutionLog,
    BrokerConnection,
    BrokerType,
    OrderStatus,
)
from ...execution.engine import ExecutionEngine, ExecutionMode


router = APIRouter(prefix="/execution", tags=["execution"])


# ============================================================================
# Request/Response Models
# ============================================================================

class ExecuteSignalRequest(BaseModel):
    """Request to execute a signal."""
    signal_id: int
    broker_type: str = "PAPER"  # PAPER, SIGNUM, DIRECT


class SetModeRequest(BaseModel):
    """Request to set execution mode."""
    mode: str  # GUIDE or AUTONOMOUS
    confirm_autonomous: bool = False  # Must be True to enable AUTONOMOUS


class ExecutionOrderResponse(BaseModel):
    """Execution order details."""
    id: int
    client_order_id: str
    signal_id: Optional[int]
    position_id: Optional[int]
    broker_type: str
    order_type: str
    side: str
    symbol: str
    quantity: float
    price: Optional[float]
    stop_loss: Optional[float]
    take_profit: Optional[float]
    status: str
    broker_order_id: Optional[str]
    average_fill_price: Optional[float]
    filled_quantity: float
    error_message: Optional[str]
    strategy_name: str
    
    class Config:
        from_attributes = True


class ExecutionLogResponse(BaseModel):
    """Execution log entry."""
    id: int
    order_id: int
    event_type: str
    event_data: dict
    event_time: str
    
    class Config:
        from_attributes = True


class ModeStatusResponse(BaseModel):
    """Current execution mode status."""
    mode: str
    description: str
    allows_execution: bool


# ============================================================================
# Dependency: Get Execution Engine
# ============================================================================

async def get_execution_engine(db: AsyncSession = Depends(get_db)) -> ExecutionEngine:
    """Create execution engine instance."""
    return ExecutionEngine(db)


# ============================================================================
# Mode Management Endpoints
# ============================================================================

@router.get("/mode", response_model=ModeStatusResponse)
async def get_execution_mode(
    engine: ExecutionEngine = Depends(get_execution_engine),
):
    """
    Get current execution mode.
    
    Modes:
    - GUIDE: Signals recorded but NOT executed
    - AUTONOMOUS: Full automated execution enabled
    """
    mode = engine.mode
    
    return ModeStatusResponse(
        mode=mode.value,
        description=(
            "GUIDE mode - trades are recorded but not executed"
            if mode == ExecutionMode.GUIDE
            else "AUTONOMOUS mode - full automated execution enabled"
        ),
        allows_execution=mode == ExecutionMode.AUTONOMOUS,
    )


@router.post("/mode", response_model=ModeStatusResponse)
async def set_execution_mode(
    request: SetModeRequest,
    engine: ExecutionEngine = Depends(get_execution_engine),
):
    """
    Set execution mode.
    
    CRITICAL: Switching to AUTONOMOUS mode requires explicit confirmation.
    Set confirm_autonomous=true to enable AUTONOMOUS mode.
    """
    try:
        mode = ExecutionMode(request.mode.upper())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid mode: {request.mode}. Must be GUIDE or AUTONOMOUS",
        )
    
    # Safety check for AUTONOMOUS mode
    if mode == ExecutionMode.AUTONOMOUS and not request.confirm_autonomous:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="AUTONOMOUS mode requires confirm_autonomous=true. This enables live trading.",
        )
    
    engine.set_mode(mode)
    
    return ModeStatusResponse(
        mode=mode.value,
        description=(
            "GUIDE mode - trades are recorded but not executed"
            if mode == ExecutionMode.GUIDE
            else "AUTONOMOUS mode - full automated execution enabled"
        ),
        allows_execution=mode == ExecutionMode.AUTONOMOUS,
    )


# ============================================================================
# Signal Execution Endpoints
# ============================================================================

@router.post("/execute")
async def execute_signal(
    request: ExecuteSignalRequest,
    engine: ExecutionEngine = Depends(get_execution_engine),
):
    """
    Execute a trading signal.
    
    The signal goes through the full validation pipeline:
    1. Strategy approval - Is the strategy active?
    2. Risk approval - Does it pass all risk checks?
    3. Mode check - Is execution allowed?
    
    In GUIDE mode: Signal is recorded but not executed.
    In AUTONOMOUS mode: Signal is executed through the broker.
    """
    try:
        broker_type = BrokerType(request.broker_type.upper())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid broker type: {request.broker_type}",
        )
    
    result = await engine.execute_signal(
        signal_id=request.signal_id,
        broker_type=broker_type,
    )
    
    return result.to_dict()


# ============================================================================
# Order Management Endpoints
# ============================================================================

@router.get("/orders", response_model=list[ExecutionOrderResponse])
async def list_execution_orders(
    status_filter: Optional[str] = None,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    """
    List execution orders.
    
    Optional filters:
    - status: Filter by order status (PENDING, SUBMITTED, FILLED, etc.)
    """
    query = select(ExecutionOrder).order_by(ExecutionOrder.created_at.desc()).limit(limit)
    
    if status_filter:
        try:
            order_status = OrderStatus(status_filter.upper())
            query = query.where(ExecutionOrder.status == order_status)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status: {status_filter}",
            )
    
    result = await db.execute(query)
    orders = result.scalars().all()
    
    return [
        ExecutionOrderResponse(
            id=o.id,
            client_order_id=o.client_order_id,
            signal_id=o.signal_id,
            position_id=o.position_id,
            broker_type=o.broker_type.value,
            order_type=o.order_type.value,
            side=o.side.value,
            symbol=o.symbol,
            quantity=o.quantity,
            price=o.price,
            stop_loss=o.stop_loss,
            take_profit=o.take_profit,
            status=o.status.value,
            broker_order_id=o.broker_order_id,
            average_fill_price=o.average_fill_price,
            filled_quantity=o.filled_quantity,
            error_message=o.error_message,
            strategy_name=o.strategy_name,
        )
        for o in orders
    ]


@router.get("/orders/{order_id}", response_model=ExecutionOrderResponse)
async def get_execution_order(
    order_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get details of a specific execution order."""
    result = await db.execute(
        select(ExecutionOrder).where(ExecutionOrder.id == order_id)
    )
    order = result.scalar_one_or_none()
    
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Execution order {order_id} not found",
        )
    
    return ExecutionOrderResponse(
        id=order.id,
        client_order_id=order.client_order_id,
        signal_id=order.signal_id,
        position_id=order.position_id,
        broker_type=order.broker_type.value,
        order_type=order.order_type.value,
        side=order.side.value,
        symbol=order.symbol,
        quantity=order.quantity,
        price=order.price,
        stop_loss=order.stop_loss,
        take_profit=order.take_profit,
        status=order.status.value,
        broker_order_id=order.broker_order_id,
        average_fill_price=order.average_fill_price,
        filled_quantity=order.filled_quantity,
        error_message=order.error_message,
        strategy_name=order.strategy_name,
    )


@router.post("/orders/{order_id}/cancel")
async def cancel_execution_order(
    order_id: int,
    engine: ExecutionEngine = Depends(get_execution_engine),
):
    """Cancel a pending or submitted execution order."""
    result = await engine.cancel_order(order_id)
    
    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.blocked_reason,
        )
    
    return result.to_dict()


# ============================================================================
# Execution Log Endpoints
# ============================================================================

@router.get("/orders/{order_id}/logs", response_model=list[ExecutionLogResponse])
async def get_execution_logs(
    order_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get execution logs for an order."""
    result = await db.execute(
        select(ExecutionLog)
        .where(ExecutionLog.order_id == order_id)
        .order_by(ExecutionLog.event_time)
    )
    logs = result.scalars().all()
    
    return [
        ExecutionLogResponse(
            id=log.id,
            order_id=log.order_id,
            event_type=log.event_type,
            event_data=log.event_data,
            event_time=log.event_time.isoformat(),
        )
        for log in logs
    ]


# ============================================================================
# Broker Connection Endpoints
# ============================================================================

@router.get("/brokers")
async def list_broker_connections(
    db: AsyncSession = Depends(get_db),
):
    """List configured broker connections."""
    result = await db.execute(
        select(BrokerConnection).order_by(BrokerConnection.created_at.desc())
    )
    connections = result.scalars().all()
    
    return [
        {
            "id": conn.id,
            "broker_type": conn.broker_type.value,
            "is_active": conn.is_active,
            "is_connected": conn.is_connected,
            "last_health_check": conn.last_health_check.isoformat() if conn.last_health_check else None,
            "last_connection_time": conn.last_connection_time.isoformat() if conn.last_connection_time else None,
        }
        for conn in connections
    ]


@router.get("/health")
async def execution_health_check(
    engine: ExecutionEngine = Depends(get_execution_engine),
):
    """
    Check execution system health.
    
    Returns status of:
    - Current mode
    - Registered brokers
    - Broker connection status
    """
    broker_status = {}
    for broker_type, adapter in engine._brokers.items():
        broker_status[broker_type.value] = {
            "name": adapter.broker_name,
            "is_paper": adapter.is_paper,
            "is_connected": adapter.is_connected,
        }
    
    return {
        "status": "healthy",
        "mode": engine.mode.value,
        "brokers": broker_status,
    }
