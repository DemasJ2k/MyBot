"""
Execution Mode Service.

This service manages execution mode transitions with full safety enforcement:
- SIMULATION (default): Virtual account, no real money
- PAPER: Broker's paper trading account
- LIVE: Real money trading - requires explicit confirmation

CRITICAL: Live mode requires password verification and explicit confirmation.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.execution_mode import (
    ExecutionMode,
    SimulationAccount,
    ExecutionModeAudit,
    SimulationPosition,
)
from app.models.system_settings import SystemSettings
from app.models.user import User


class ExecutionModeError(Exception):
    """Error during execution mode operations."""
    pass


class LiveModeConfirmationRequired(ExecutionModeError):
    """Live mode requires explicit confirmation."""
    pass


class PasswordVerificationRequired(ExecutionModeError):
    """Password verification required for live mode."""
    pass


class ExecutionModeService:
    """
    Service for managing execution modes.
    
    Safety Features:
    - Defaults to SIMULATION mode
    - Live mode requires password verification
    - All mode changes are audited
    - Open positions are tracked during transitions
    
    Usage:
        service = ExecutionModeService(db_session)
        current_mode = await service.get_current_mode()
        await service.change_mode(
            user_id=1,
            new_mode=ExecutionMode.PAPER,
            reason="Testing strategy"
        )
    """
    
    def __init__(self, db: AsyncSession):
        """
        Initialize execution mode service.
        
        Args:
            db: Async database session
        """
        self.db = db
    
    async def get_current_mode(self) -> ExecutionMode:
        """
        Get the current execution mode from system settings.
        
        Returns:
            Current ExecutionMode (defaults to SIMULATION)
        """
        result = await self.db.execute(select(SystemSettings).limit(1))
        settings = result.scalar_one_or_none()
        
        if not settings:
            return ExecutionMode.SIMULATION
        
        try:
            return ExecutionMode(settings.execution_mode)
        except ValueError:
            # Invalid mode stored, default to safe mode
            return ExecutionMode.SIMULATION
    
    async def change_mode(
        self,
        user_id: int,
        new_mode: ExecutionMode,
        reason: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        password_verified: bool = False,
        confirmed: bool = False,
    ) -> ExecutionMode:
        """
        Change the execution mode with full safety checks.
        
        Args:
            user_id: User requesting the change
            new_mode: Target execution mode
            reason: Reason for the change (required for LIVE)
            ip_address: Client IP for audit trail
            user_agent: Client user agent for audit
            password_verified: Whether password was verified (required for LIVE)
            confirmed: Whether user explicitly confirmed (required for LIVE)
        
        Returns:
            New execution mode after change
            
        Raises:
            LiveModeConfirmationRequired: If changing to LIVE without confirmation
            PasswordVerificationRequired: If changing to LIVE without password
            ExecutionModeError: For other validation errors
        """
        current_mode = await self.get_current_mode()
        
        # Same mode - no change needed
        if current_mode == new_mode:
            return current_mode
        
        # Safety checks for LIVE mode
        if new_mode == ExecutionMode.LIVE:
            if not password_verified:
                raise PasswordVerificationRequired(
                    "Password verification required to enable live trading"
                )
            if not confirmed:
                raise LiveModeConfirmationRequired(
                    "Explicit confirmation required to enable live trading. "
                    "This will use REAL MONEY. Are you sure?"
                )
            if not reason:
                raise ExecutionModeError(
                    "A reason is required when enabling live trading"
                )
        
        # Check for open positions
        open_position_count = 0
        positions_cancelled = 0
        
        if current_mode == ExecutionMode.SIMULATION:
            # Count simulation positions
            sim_account = await self.get_simulation_account(user_id)
            if sim_account:
                result = await self.db.execute(
                    select(SimulationPosition).where(
                        SimulationPosition.simulation_account_id == sim_account.id
                    )
                )
                positions = result.scalars().all()
                open_position_count = len(positions)
        
        # Get or create settings
        result = await self.db.execute(select(SystemSettings).limit(1))
        settings = result.scalar_one_or_none()
        
        if not settings:
            settings = SystemSettings()
            self.db.add(settings)
        
        # Update mode
        settings.execution_mode = new_mode.value
        
        # Create audit record
        audit = ExecutionModeAudit(
            user_id=user_id,
            old_mode=current_mode.value,
            new_mode=new_mode.value,
            reason=reason,
            ip_address=ip_address,
            user_agent=user_agent,
            confirmation_required=new_mode == ExecutionMode.LIVE,
            password_verified=password_verified,
            had_open_positions=open_position_count > 0,
            positions_cancelled=positions_cancelled,
        )
        self.db.add(audit)
        
        await self.db.flush()
        
        return new_mode
    
    async def get_simulation_account(
        self,
        user_id: int,
        create_if_missing: bool = False,
    ) -> Optional[SimulationAccount]:
        """
        Get simulation account for user.
        
        Args:
            user_id: User ID
            create_if_missing: Whether to create if doesn't exist
            
        Returns:
            SimulationAccount or None
        """
        result = await self.db.execute(
            select(SimulationAccount).where(SimulationAccount.user_id == user_id)
        )
        account = result.scalar_one_or_none()
        
        if not account and create_if_missing:
            account = SimulationAccount(user_id=user_id)
            self.db.add(account)
            await self.db.flush()
        
        return account
    
    async def reset_simulation_account(self, user_id: int) -> SimulationAccount:
        """
        Reset simulation account to initial state.
        
        Closes all positions and resets balance.
        
        Args:
            user_id: User ID
            
        Returns:
            Reset SimulationAccount
        """
        account = await self.get_simulation_account(user_id, create_if_missing=True)
        
        # Close all positions
        result = await self.db.execute(
            select(SimulationPosition).where(
                SimulationPosition.simulation_account_id == account.id
            )
        )
        positions = result.scalars().all()
        
        for position in positions:
            await self.db.delete(position)
        
        # Reset account
        account.reset()
        
        await self.db.flush()
        
        return account
    
    async def update_simulation_settings(
        self,
        user_id: int,
        initial_balance: Optional[float] = None,
        slippage_pips: Optional[float] = None,
        commission_per_lot: Optional[float] = None,
        latency_ms: Optional[int] = None,
        fill_probability: Optional[float] = None,
    ) -> SimulationAccount:
        """
        Update simulation account settings.
        
        Args:
            user_id: User ID
            initial_balance: New initial balance (resets account)
            slippage_pips: Simulated slippage in pips
            commission_per_lot: Commission per lot traded
            latency_ms: Simulated execution latency
            fill_probability: Probability of fill (0-1)
            
        Returns:
            Updated SimulationAccount
        """
        account = await self.get_simulation_account(user_id, create_if_missing=True)
        
        if initial_balance is not None:
            if initial_balance < 100:
                raise ExecutionModeError("Initial balance must be at least $100")
            account.initial_balance = initial_balance
            # Reset account when balance changes
            account.reset()
        
        if slippage_pips is not None:
            if slippage_pips < 0 or slippage_pips > 10:
                raise ExecutionModeError("Slippage must be between 0 and 10 pips")
            account.slippage_pips = slippage_pips
        
        if commission_per_lot is not None:
            if commission_per_lot < 0 or commission_per_lot > 50:
                raise ExecutionModeError("Commission must be between $0 and $50 per lot")
            account.commission_per_lot = commission_per_lot
        
        if latency_ms is not None:
            if latency_ms < 0 or latency_ms > 5000:
                raise ExecutionModeError("Latency must be between 0 and 5000ms")
            account.latency_ms = latency_ms
        
        if fill_probability is not None:
            if fill_probability < 0 or fill_probability > 1:
                raise ExecutionModeError("Fill probability must be between 0 and 1")
            account.fill_probability = fill_probability
        
        await self.db.flush()
        
        return account
    
    async def get_mode_audit_history(
        self,
        user_id: Optional[int] = None,
        limit: int = 50,
    ) -> list[ExecutionModeAudit]:
        """
        Get audit history for mode changes.
        
        Args:
            user_id: Filter by user (None for all)
            limit: Maximum records to return
            
        Returns:
            List of audit records
        """
        query = select(ExecutionModeAudit).order_by(
            ExecutionModeAudit.created_at.desc()
        ).limit(limit)
        
        if user_id:
            query = query.where(ExecutionModeAudit.user_id == user_id)
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def get_simulation_positions(
        self,
        user_id: int,
    ) -> list[SimulationPosition]:
        """
        Get all simulation positions for user.
        
        Args:
            user_id: User ID
            
        Returns:
            List of simulation positions
        """
        account = await self.get_simulation_account(user_id)
        if not account:
            return []
        
        result = await self.db.execute(
            select(SimulationPosition).where(
                SimulationPosition.simulation_account_id == account.id
            )
        )
        return list(result.scalars().all())
    
    async def get_simulation_stats(self, user_id: int) -> dict:
        """
        Get statistics for simulation account.
        
        Args:
            user_id: User ID
            
        Returns:
            Dict with account statistics
        """
        account = await self.get_simulation_account(user_id)
        
        if not account:
            return {
                "has_account": False,
                "balance": 0,
                "equity": 0,
                "total_pnl": 0,
                "total_trades": 0,
                "win_rate": 0,
                "open_positions": 0,
            }
        
        positions = await self.get_simulation_positions(user_id)
        
        return {
            "has_account": True,
            "balance": account.balance,
            "equity": account.equity,
            "margin_used": account.margin_used,
            "margin_available": account.margin_available,
            "initial_balance": account.initial_balance,
            "total_pnl": account.total_pnl,
            "total_trades": account.total_trades,
            "winning_trades": account.winning_trades,
            "win_rate": account.win_rate,
            "open_positions": len(positions),
            "unrealized_pnl": sum(p.unrealized_pnl for p in positions),
            "slippage_pips": account.slippage_pips,
            "commission_per_lot": account.commission_per_lot,
            "latency_ms": account.latency_ms,
            "fill_probability": account.fill_probability,
            "last_reset": account.last_reset_at.isoformat() if account.last_reset_at else None,
        }
    
    async def validate_mode_for_action(
        self,
        required_modes: list[ExecutionMode],
        action_description: str,
    ) -> None:
        """
        Validate current mode allows an action.
        
        Args:
            required_modes: List of modes that allow this action
            action_description: Human-readable action name
            
        Raises:
            ExecutionModeError: If current mode doesn't allow action
        """
        current_mode = await self.get_current_mode()
        
        if current_mode not in required_modes:
            allowed = ", ".join(m.value for m in required_modes)
            raise ExecutionModeError(
                f"Action '{action_description}' requires mode: {allowed}. "
                f"Current mode: {current_mode.value}"
            )
    
    async def is_live_trading_enabled(self) -> bool:
        """Check if live trading is currently enabled."""
        mode = await self.get_current_mode()
        return mode == ExecutionMode.LIVE
    
    async def is_simulation_mode(self) -> bool:
        """Check if simulation mode is active."""
        mode = await self.get_current_mode()
        return mode == ExecutionMode.SIMULATION
