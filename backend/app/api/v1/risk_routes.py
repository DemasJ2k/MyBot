"""Risk Engine API routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
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
    """Request model for trade validation."""
    signal_id: int
    account_balance: float
    peak_balance: float


class AccountStateUpdateRequest(BaseModel):
    """Request model for account state update."""
    account_balance: float
    peak_balance: float


class StrategyEnableRequest(BaseModel):
    """Request model for enabling a strategy."""
    strategy_name: str
    symbol: str


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
        "id": state.id,
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


@router.post("/state/update")
async def update_risk_state(
    request: AccountStateUpdateRequest,
    db: AsyncSession = Depends(get_db)
):
    """Update account risk state."""
    monitor = RiskMonitor(db=db)
    state = await monitor.update_account_state(
        account_balance=request.account_balance,
        peak_balance=request.peak_balance
    )

    return {
        "id": state.id,
        "account_balance": state.account_balance,
        "peak_balance": state.peak_balance,
        "current_drawdown_percent": state.current_drawdown_percent,
        "daily_pnl": state.daily_pnl,
        "daily_loss_percent": state.daily_loss_percent,
        "trades_today": state.trades_today,
        "emergency_shutdown_active": state.emergency_shutdown_active,
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
            "total_pnl": b.total_pnl,
            "consecutive_losses": b.consecutive_losses,
            "is_enabled": b.is_enabled,
            "disabled_reason": b.disabled_reason
        }
        for b in budgets
    ]


@router.get("/limits")
async def get_risk_limits():
    """Get all hard risk limits."""
    from app.risk.constants import (
        MAX_RISK_PER_TRADE_PERCENT,
        MAX_POSITION_SIZE_LOTS,
        MAX_OPEN_POSITIONS,
        MAX_DAILY_LOSS_PERCENT,
        EMERGENCY_DRAWDOWN_PERCENT,
        MAX_ACCOUNT_LEVERAGE,
        MAX_TRADES_PER_DAY,
        MAX_TRADES_PER_HOUR,
        MAX_STRATEGIES_ACTIVE,
        MAX_RISK_PER_STRATEGY_PERCENT,
        MIN_RISK_REWARD_RATIO,
        MIN_ACCOUNT_BALANCE,
    )

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


@router.post("/emergency/reset")
async def reset_emergency_shutdown(db: AsyncSession = Depends(get_db)):
    """
    Reset emergency shutdown.

    WARNING: This requires manual intervention and careful consideration.
    """
    monitor = RiskMonitor(db=db)
    result = await monitor.reset_emergency_shutdown()

    if result:
        return {"message": "Emergency shutdown has been reset", "reset": True}
    else:
        return {"message": "No emergency shutdown was active", "reset": False}


@router.post("/daily/reset")
async def reset_daily_metrics(db: AsyncSession = Depends(get_db)):
    """Reset daily metrics (typically called at start of trading day)."""
    monitor = RiskMonitor(db=db)
    await monitor.reset_daily_metrics()

    return {"message": "Daily metrics have been reset"}


@router.post("/strategy/enable")
async def enable_strategy(
    request: StrategyEnableRequest,
    db: AsyncSession = Depends(get_db)
):
    """Re-enable a disabled strategy."""
    monitor = RiskMonitor(db=db)
    result = await monitor.enable_strategy(
        strategy_name=request.strategy_name,
        symbol=request.symbol
    )

    if result:
        return {"message": f"Strategy {request.strategy_name}/{request.symbol} has been enabled", "enabled": True}
    else:
        raise HTTPException(status_code=404, detail="Strategy budget not found")
