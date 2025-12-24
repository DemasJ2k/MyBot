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
        db.add(config)

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
