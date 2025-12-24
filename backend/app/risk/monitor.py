"""Risk Monitor - Continuous risk monitoring and state tracking."""

from typing import Optional
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from app.models.position import Position, PositionStatus
from app.models.risk import AccountRiskState, StrategyRiskBudget
from app.risk.constants import MAX_RISK_PER_STRATEGY_PERCENT
import logging

logger = logging.getLogger(__name__)


class RiskMonitor:
    """
    Continuous risk monitoring and state tracking.

    Updates:
    - Account risk state
    - Strategy risk budgets
    - Daily P&L and limits
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def update_account_state(
        self,
        account_balance: float,
        peak_balance: float
    ) -> AccountRiskState:
        """
        Update account risk state.

        Args:
            account_balance: Current account balance
            peak_balance: Peak account balance

        Returns:
            Updated account risk state
        """
        # Get or create state
        stmt = select(AccountRiskState).order_by(AccountRiskState.last_updated.desc()).limit(1)
        result = await self.db.execute(stmt)
        state = result.scalar_one_or_none()

        # Calculate metrics
        current_drawdown = ((peak_balance - account_balance) / peak_balance * 100.0) if peak_balance > 0 else 0.0

        # Get daily P&L
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        stmt = select(Position).where(
            and_(
                Position.exit_time >= today_start,
                Position.status == PositionStatus.CLOSED
            )
        )
        result = await self.db.execute(stmt)
        closed_positions = result.scalars().all()

        daily_pnl = sum(p.realized_pnl for p in closed_positions if p.realized_pnl)
        daily_loss_percent = (abs(daily_pnl) / account_balance * 100.0) if daily_pnl < 0 and account_balance > 0 else 0.0

        # Count trades
        stmt = select(Position).where(Position.entry_time >= today_start)
        result = await self.db.execute(stmt)
        trades_today = len(result.scalars().all())

        hour_ago = datetime.utcnow() - timedelta(hours=1)
        stmt = select(Position).where(Position.entry_time >= hour_ago)
        result = await self.db.execute(stmt)
        trades_this_hour = len(result.scalars().all())

        # Count open positions
        stmt = select(Position).where(Position.status == PositionStatus.OPEN)
        result = await self.db.execute(stmt)
        open_positions = result.scalars().all()
        open_positions_count = len(open_positions)

        # Calculate exposure
        total_exposure = sum(p.entry_price * p.position_size for p in open_positions)
        total_exposure_percent = (total_exposure / account_balance * 100.0) if account_balance > 0 else 0.0

        if state:
            # Update existing state
            state.account_balance = account_balance
            state.peak_balance = peak_balance
            state.current_drawdown_percent = current_drawdown
            state.daily_pnl = daily_pnl
            state.daily_loss_percent = daily_loss_percent
            state.trades_today = trades_today
            state.trades_this_hour = trades_this_hour
            state.open_positions_count = open_positions_count
            state.total_exposure = total_exposure
            state.total_exposure_percent = total_exposure_percent
            state.last_updated = datetime.utcnow()
        else:
            # Create new state
            state = AccountRiskState(
                account_balance=account_balance,
                peak_balance=peak_balance,
                current_drawdown_percent=current_drawdown,
                daily_pnl=daily_pnl,
                daily_loss_percent=daily_loss_percent,
                trades_today=trades_today,
                trades_this_hour=trades_this_hour,
                open_positions_count=open_positions_count,
                total_exposure=total_exposure,
                total_exposure_percent=total_exposure_percent,
                emergency_shutdown_active=False,
                throttling_active=False,
                last_updated=datetime.utcnow()
            )
            self.db.add(state)

        await self.db.commit()
        await self.db.refresh(state)

        return state

    async def update_strategy_budget(
        self,
        strategy_name: str,
        symbol: str,
        position: Position,
        trade_closed: bool = False
    ):
        """
        Update strategy risk budget after trade.

        Args:
            strategy_name: Strategy name
            symbol: Trading symbol
            position: Position object
            trade_closed: True if position was closed
        """
        stmt = select(StrategyRiskBudget).where(
            and_(
                StrategyRiskBudget.strategy_name == strategy_name,
                StrategyRiskBudget.symbol == symbol
            )
        )
        result = await self.db.execute(stmt)
        budget = result.scalar_one_or_none()

        if not budget:
            # Create new budget
            budget = StrategyRiskBudget(
                strategy_name=strategy_name,
                symbol=symbol,
                max_exposure_percent=MAX_RISK_PER_STRATEGY_PERCENT,
                max_daily_loss_percent=2.0,
                current_exposure=0.0,
                current_exposure_percent=0.0,
                daily_pnl=0.0,
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                total_pnl=0.0,
                consecutive_losses=0,
                max_consecutive_losses=5,
                is_enabled=True,
                last_updated=datetime.utcnow()
            )
            self.db.add(budget)

        # Update metrics
        budget.total_trades += 1
        budget.last_trade_time = datetime.utcnow()
        budget.last_updated = datetime.utcnow()

        if trade_closed and position.realized_pnl is not None:
            # Update P&L
            budget.total_pnl += position.realized_pnl
            budget.daily_pnl += position.realized_pnl

            # Update win/loss count
            if position.realized_pnl > 0:
                budget.winning_trades += 1
                budget.consecutive_losses = 0  # Reset
            else:
                budget.losing_trades += 1
                budget.consecutive_losses += 1

            # Check auto-disable criteria
            if budget.consecutive_losses >= budget.max_consecutive_losses:
                budget.is_enabled = False
                budget.disabled_reason = f"{budget.consecutive_losses} consecutive losses"
                logger.warning(f"Strategy {strategy_name} auto-disabled: {budget.disabled_reason}")

        await self.db.commit()

    async def get_account_state(self) -> Optional[AccountRiskState]:
        """Get current account risk state."""
        stmt = select(AccountRiskState).order_by(AccountRiskState.last_updated.desc()).limit(1)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def reset_emergency_shutdown(self) -> bool:
        """
        Reset emergency shutdown (requires manual intervention).

        Returns:
            True if shutdown was reset, False if no shutdown was active
        """
        stmt = select(AccountRiskState).order_by(AccountRiskState.last_updated.desc()).limit(1)
        result = await self.db.execute(stmt)
        state = result.scalar_one_or_none()

        if state and state.emergency_shutdown_active:
            state.emergency_shutdown_active = False
            state.last_updated = datetime.utcnow()
            await self.db.commit()
            logger.warning("Emergency shutdown has been manually reset")
            return True

        return False

    async def reset_daily_metrics(self) -> None:
        """Reset daily metrics (should be called at start of trading day)."""
        stmt = select(AccountRiskState).order_by(AccountRiskState.last_updated.desc()).limit(1)
        result = await self.db.execute(stmt)
        state = result.scalar_one_or_none()

        if state:
            state.daily_pnl = 0.0
            state.daily_loss_percent = 0.0
            state.trades_today = 0
            state.last_updated = datetime.utcnow()
            await self.db.commit()

        # Reset strategy daily P&L
        stmt = select(StrategyRiskBudget)
        result = await self.db.execute(stmt)
        budgets = result.scalars().all()

        for budget in budgets:
            budget.daily_pnl = 0.0
            budget.last_updated = datetime.utcnow()

        await self.db.commit()
        logger.info("Daily risk metrics have been reset")

    async def enable_strategy(self, strategy_name: str, symbol: str) -> bool:
        """
        Re-enable a disabled strategy.

        Returns:
            True if strategy was enabled, False if not found
        """
        stmt = select(StrategyRiskBudget).where(
            and_(
                StrategyRiskBudget.strategy_name == strategy_name,
                StrategyRiskBudget.symbol == symbol
            )
        )
        result = await self.db.execute(stmt)
        budget = result.scalar_one_or_none()

        if budget:
            budget.is_enabled = True
            budget.disabled_reason = None
            budget.consecutive_losses = 0
            budget.last_updated = datetime.utcnow()
            await self.db.commit()
            logger.info(f"Strategy {strategy_name}/{symbol} has been re-enabled")
            return True

        return False
