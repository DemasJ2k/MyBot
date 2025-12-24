"""
API routes for multi-agent coordination.

Provides endpoints for:
- Executing coordination cycles
- Viewing agent messages
- Viewing cycle history
- Monitoring agent health
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from typing import List, Dict, Any, Optional
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
    """Request to execute a coordination cycle."""
    symbol: str
    strategies: List[str]
    account_balance: float
    peak_balance: float


class HaltRequest(BaseModel):
    """Request to halt a coordination cycle."""
    cycle_id: str
    reason: str


@router.post("/cycle")
async def execute_coordination_cycle(
    request: CycleRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Execute a complete coordination cycle.
    
    The cycle will:
    1. Check agent health
    2. Execute strategy analysis
    3. Execute risk validation
    4. Execute trade execution
    
    Returns cycle results including success status, completed phases, and any errors.
    """
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


@router.post("/halt")
async def halt_coordination_cycle(
    request: HaltRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Halt a running coordination cycle.
    
    Broadcasts HALT message to all agents and updates cycle state.
    """
    # Get system mode for pipeline
    stmt = select(SystemConfig).where(SystemConfig.key == "system_mode")
    result = await db.execute(stmt)
    config = result.scalar_one_or_none()

    mode_str = config.value.get("mode", "guide") if config else "guide"
    system_mode = SystemMode.GUIDE if mode_str == "guide" else SystemMode.AUTONOMOUS

    pipeline = CoordinationPipeline(db=db, system_mode=system_mode)
    
    await pipeline.halt_cycle(request.cycle_id, request.reason)
    
    return {"status": "halted", "cycle_id": request.cycle_id, "reason": request.reason}


@router.get("/cycle/{cycle_id}")
async def get_cycle_status(
    cycle_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get status of a specific coordination cycle."""
    # Get system mode for pipeline
    stmt = select(SystemConfig).where(SystemConfig.key == "system_mode")
    result = await db.execute(stmt)
    config = result.scalar_one_or_none()

    mode_str = config.value.get("mode", "guide") if config else "guide"
    system_mode = SystemMode.GUIDE if mode_str == "guide" else SystemMode.AUTONOMOUS

    pipeline = CoordinationPipeline(db=db, system_mode=system_mode)
    
    status = await pipeline.get_cycle_status(cycle_id)
    
    if not status:
        raise HTTPException(status_code=404, detail=f"Cycle {cycle_id} not found")
    
    return status


@router.get("/messages")
async def get_messages(
    agent_name: Optional[str] = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
):
    """
    Get agent messages.
    
    Optionally filter by agent name.
    """
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
            "sent_at": m.sent_at.isoformat() if m.sent_at else None
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
            "cycle_started_at": c.cycle_started_at.isoformat() if c.cycle_started_at else None,
            "cycle_completed_at": c.cycle_completed_at.isoformat() if c.cycle_completed_at else None,
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
            "last_heartbeat": h.last_heartbeat.isoformat() if h.last_heartbeat else None,
            "avg_response_time_ms": h.avg_response_time_ms,
            "error_count": h.error_count,
            "success_count": h.success_count,
            "status_message": h.status_message
        }
        for h in health_records
    ]


@router.post("/health/{agent_name}/heartbeat")
async def record_agent_heartbeat(
    agent_name: str,
    response_time_ms: float = 0.0,
    db: AsyncSession = Depends(get_db)
):
    """Record a heartbeat for an agent."""
    health_monitor = HealthMonitor(db=db)
    await health_monitor.heartbeat(agent_name, response_time_ms)
    return {"status": "ok", "agent": agent_name}


@router.post("/health/{agent_name}/initialize")
async def initialize_agent_health(
    agent_name: str,
    db: AsyncSession = Depends(get_db)
):
    """Initialize health record for an agent."""
    health_monitor = HealthMonitor(db=db)
    await health_monitor.initialize_agent(agent_name)
    return {"status": "initialized", "agent": agent_name}


@router.post("/health/{agent_name}/reset")
async def reset_agent_health(
    agent_name: str,
    db: AsyncSession = Depends(get_db)
):
    """Reset health statistics for an agent."""
    health_monitor = HealthMonitor(db=db)
    await health_monitor.reset_agent_health(agent_name)
    return {"status": "reset", "agent": agent_name}
