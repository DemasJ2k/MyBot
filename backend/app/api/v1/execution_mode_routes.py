"""
Execution Mode API Routes.

Provides endpoints for:
- Getting/setting execution mode (SIMULATION/PAPER/LIVE)
- Simulation account management
- Mode change audit trail

Safety First: Live mode requires explicit confirmation and password verification.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.models.user import User
from app.models.execution_mode import ExecutionMode
from app.services.execution_mode_service import (
    ExecutionModeService,
    ExecutionModeError,
    LiveModeConfirmationRequired,
    PasswordVerificationRequired,
)


router = APIRouter(prefix="/execution-mode", tags=["Execution Mode"])


# ============= Request/Response Models =============

class ExecutionModeResponse(BaseModel):
    """Current execution mode response."""
    mode: str
    is_live: bool
    is_simulation: bool
    description: str


class ExecutionModeChangeRequest(BaseModel):
    """Request to change execution mode."""
    mode: str = Field(..., description="New mode: 'simulation', 'paper', or 'live'")
    reason: Optional[str] = Field(None, max_length=500, description="Reason for change (required for live)")
    password: Optional[str] = Field(None, description="Password verification (required for live)")
    confirmed: bool = Field(False, description="Explicit confirmation (required for live)")


class SimulationAccountResponse(BaseModel):
    """Simulation account information."""
    has_account: bool
    balance: float
    equity: float
    margin_used: float
    margin_available: float
    initial_balance: float
    total_pnl: float
    total_trades: int
    winning_trades: int
    win_rate: float
    open_positions: int
    unrealized_pnl: float
    slippage_pips: float
    commission_per_lot: float
    latency_ms: int
    fill_probability: float
    last_reset: Optional[str]


class SimulationSettingsUpdateRequest(BaseModel):
    """Request to update simulation settings."""
    initial_balance: Optional[float] = Field(None, ge=100, le=10000000, description="Initial balance (resets account)")
    slippage_pips: Optional[float] = Field(None, ge=0, le=10, description="Simulated slippage in pips")
    commission_per_lot: Optional[float] = Field(None, ge=0, le=50, description="Commission per lot ($)")
    latency_ms: Optional[int] = Field(None, ge=0, le=5000, description="Simulated latency in ms")
    fill_probability: Optional[float] = Field(None, ge=0, le=1, description="Fill probability (0-1)")


class SimulationPositionResponse(BaseModel):
    """Simulation position information."""
    id: int
    symbol: str
    side: str
    quantity: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    stop_loss: Optional[float]
    take_profit: Optional[float]
    margin_required: float
    opened_at: str


class ModeAuditResponse(BaseModel):
    """Execution mode audit entry."""
    id: int
    user_id: int
    old_mode: Optional[str]
    new_mode: str
    reason: Optional[str]
    ip_address: Optional[str]
    confirmation_required: bool
    password_verified: bool
    had_open_positions: bool
    positions_cancelled: int
    created_at: str


# ============= Endpoints =============

@router.get("", response_model=ExecutionModeResponse)
async def get_current_mode(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get the current execution mode.
    
    Returns current mode along with helper flags.
    """
    service = ExecutionModeService(db)
    mode = await service.get_current_mode()
    
    descriptions = {
        ExecutionMode.SIMULATION: "Virtual trading with simulated account. No real money at risk.",
        ExecutionMode.PAPER: "Paper trading through broker's demo account.",
        ExecutionMode.LIVE: "LIVE TRADING - Real money is at risk!",
    }
    
    return ExecutionModeResponse(
        mode=mode.value,
        is_live=mode == ExecutionMode.LIVE,
        is_simulation=mode == ExecutionMode.SIMULATION,
        description=descriptions.get(mode, "Unknown mode"),
    )


@router.post("", response_model=ExecutionModeResponse)
async def change_mode(
    request: ExecutionModeChangeRequest,
    http_request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Change the execution mode.
    
    IMPORTANT SAFETY REQUIREMENTS for LIVE mode:
    - password: Must provide password for verification
    - confirmed: Must be explicitly set to true
    - reason: Must provide a reason for enabling live trading
    
    SIMULATION and PAPER modes can be changed without additional verification.
    """
    # Validate mode string
    try:
        new_mode = ExecutionMode(request.mode)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid mode: {request.mode}. Must be 'simulation', 'paper', or 'live'",
        )
    
    service = ExecutionModeService(db)
    
    # Password verification for live mode
    password_verified = False
    if new_mode == ExecutionMode.LIVE and request.password:
        # In a real implementation, verify password against user's stored hash
        # For now, we'll just check that a password was provided
        password_verified = True  # TODO: Implement actual password verification
    
    try:
        new_mode = await service.change_mode(
            user_id=current_user.id,
            new_mode=new_mode,
            reason=request.reason,
            ip_address=http_request.client.host if http_request.client else None,
            user_agent=http_request.headers.get("user-agent"),
            password_verified=password_verified,
            confirmed=request.confirmed,
        )
        
        await db.commit()
        
        descriptions = {
            ExecutionMode.SIMULATION: "Virtual trading with simulated account. No real money at risk.",
            ExecutionMode.PAPER: "Paper trading through broker's demo account.",
            ExecutionMode.LIVE: "LIVE TRADING - Real money is at risk!",
        }
        
        return ExecutionModeResponse(
            mode=new_mode.value,
            is_live=new_mode == ExecutionMode.LIVE,
            is_simulation=new_mode == ExecutionMode.SIMULATION,
            description=descriptions.get(new_mode, "Unknown mode"),
        )
        
    except PasswordVerificationRequired:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Password verification required to enable live trading",
        )
    except LiveModeConfirmationRequired:
        raise HTTPException(
            status_code=status.HTTP_428_PRECONDITION_REQUIRED,
            detail="Explicit confirmation required to enable live trading. Set 'confirmed: true' and acknowledge that real money will be at risk.",
        )
    except ExecutionModeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/simulation/account", response_model=SimulationAccountResponse)
async def get_simulation_account(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get simulation account information and statistics.
    
    Includes balance, equity, P&L, win rate, and simulation parameters.
    """
    service = ExecutionModeService(db)
    stats = await service.get_simulation_stats(current_user.id)
    
    return SimulationAccountResponse(**stats)


@router.post("/simulation/reset", response_model=SimulationAccountResponse)
async def reset_simulation_account(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Reset simulation account to initial state.
    
    This will:
    - Close all open positions
    - Reset balance to initial balance
    - Clear trading statistics
    """
    service = ExecutionModeService(db)
    await service.reset_simulation_account(current_user.id)
    await db.commit()
    
    stats = await service.get_simulation_stats(current_user.id)
    return SimulationAccountResponse(**stats)


@router.patch("/simulation/settings", response_model=SimulationAccountResponse)
async def update_simulation_settings(
    request: SimulationSettingsUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update simulation account settings.
    
    Available settings:
    - initial_balance: Starting balance (changing this resets the account)
    - slippage_pips: Simulated slippage (0-10 pips)
    - commission_per_lot: Commission per lot ($0-50)
    - latency_ms: Simulated execution latency (0-5000ms)
    - fill_probability: Probability of fill (0-1)
    """
    service = ExecutionModeService(db)
    
    try:
        await service.update_simulation_settings(
            user_id=current_user.id,
            initial_balance=request.initial_balance,
            slippage_pips=request.slippage_pips,
            commission_per_lot=request.commission_per_lot,
            latency_ms=request.latency_ms,
            fill_probability=request.fill_probability,
        )
        await db.commit()
        
        stats = await service.get_simulation_stats(current_user.id)
        return SimulationAccountResponse(**stats)
        
    except ExecutionModeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/simulation/positions", response_model=List[SimulationPositionResponse])
async def get_simulation_positions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get all open simulation positions.
    """
    service = ExecutionModeService(db)
    positions = await service.get_simulation_positions(current_user.id)
    
    return [
        SimulationPositionResponse(
            id=p.id,
            symbol=p.symbol,
            side=p.side,
            quantity=p.quantity,
            entry_price=p.entry_price,
            current_price=p.current_price,
            unrealized_pnl=p.unrealized_pnl,
            stop_loss=p.stop_loss,
            take_profit=p.take_profit,
            margin_required=p.margin_required,
            opened_at=p.opened_at.isoformat(),
        )
        for p in positions
    ]


@router.get("/audit", response_model=List[ModeAuditResponse])
async def get_mode_audit_history(
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get execution mode change audit history.
    
    Returns the most recent mode changes with full audit details.
    """
    service = ExecutionModeService(db)
    audits = await service.get_mode_audit_history(limit=limit)
    
    return [
        ModeAuditResponse(
            id=a.id,
            user_id=a.user_id,
            old_mode=a.old_mode,
            new_mode=a.new_mode,
            reason=a.reason,
            ip_address=a.ip_address,
            confirmation_required=a.confirmation_required,
            password_verified=a.password_verified,
            had_open_positions=a.had_open_positions,
            positions_cancelled=a.positions_cancelled,
            created_at=a.created_at.isoformat(),
        )
        for a in audits
    ]


@router.get("/safety-check")
async def check_mode_safety(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Check current mode safety status.
    
    Returns warnings and recommendations based on current mode.
    """
    service = ExecutionModeService(db)
    mode = await service.get_current_mode()
    
    warnings = []
    recommendations = []
    
    if mode == ExecutionMode.LIVE:
        warnings.append("⚠️ LIVE TRADING ENABLED - Real money is at risk!")
        recommendations.append("Ensure risk parameters are properly configured")
        recommendations.append("Monitor trades closely")
        recommendations.append("Consider using simulation mode for testing new strategies")
    elif mode == ExecutionMode.PAPER:
        recommendations.append("Paper trading connects to broker's demo account")
        recommendations.append("Some features may behave differently than live trading")
    else:  # SIMULATION
        recommendations.append("Simulation mode is the safest for testing")
        recommendations.append("Configure slippage and latency for realistic results")
    
    return {
        "mode": mode.value,
        "is_safe": mode != ExecutionMode.LIVE,
        "warnings": warnings,
        "recommendations": recommendations,
    }
