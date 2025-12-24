"""Risk Validator - Authoritative risk validation engine."""

from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from app.models.signal import Signal
from app.models.position import Position, PositionStatus
from app.models.risk import RiskDecision, RiskDecisionType, AccountRiskState, StrategyRiskBudget
from app.risk.constants import (
    MAX_RISK_PER_TRADE_PERCENT,
    MAX_POSITION_SIZE_LOTS,
    MAX_OPEN_POSITIONS,
    MAX_DAILY_LOSS_PERCENT,
    EMERGENCY_DRAWDOWN_PERCENT,
    MAX_TRADES_PER_DAY,
    MAX_TRADES_PER_HOUR,
    MAX_RISK_PER_STRATEGY_PERCENT,
    MIN_RISK_REWARD_RATIO,
    RiskSeverity,
)
import logging

logger = logging.getLogger(__name__)


class RiskValidator:
    """
    Authoritative risk validation engine.

    THIS ENGINE HAS ABSOLUTE VETO POWER.
    All checks are executed in order of severity.
    If ANY check fails, the trade is REJECTED.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def validate_trade(
        self,
        signal: Signal,
        account_balance: float,
        peak_balance: float
    ) -> Tuple[bool, Optional[str], Dict[str, Any]]:
        """
        Validate a trade signal against ALL risk limits.

        Returns:
            (approved, rejection_reason, risk_metrics)
        """
        risk_metrics = {
            "account_balance": account_balance,
            "peak_balance": peak_balance,
            "signal_id": signal.id,
            "strategy_name": signal.strategy_name,
            "symbol": signal.symbol,
            "checks_performed": []
        }

        limits_checked = {}

        # CHECK 1: Emergency Shutdown Status
        check_result = await self._check_emergency_shutdown()
        risk_metrics["checks_performed"].append("emergency_shutdown")
        limits_checked["emergency_shutdown"] = check_result

        if not check_result["passed"]:
            await self._log_decision(
                decision_type=RiskDecisionType.TRADE_REJECTION,
                subject=f"Trade for {signal.symbol}",
                subject_id=signal.id,
                approved=False,
                rejection_reason=check_result["reason"],
                risk_metrics=risk_metrics,
                limits_checked=limits_checked,
                severity=RiskSeverity.EMERGENCY
            )
            return False, check_result["reason"], risk_metrics

        # CHECK 2: Account Drawdown
        current_drawdown = ((peak_balance - account_balance) / peak_balance * 100.0) if peak_balance > 0 else 0.0
        check_result = self._check_drawdown(current_drawdown)
        risk_metrics["checks_performed"].append("drawdown")
        risk_metrics["current_drawdown_percent"] = current_drawdown
        limits_checked["drawdown"] = check_result

        if not check_result["passed"]:
            # Trigger emergency shutdown
            await self._trigger_emergency_shutdown(current_drawdown)

            await self._log_decision(
                decision_type=RiskDecisionType.EMERGENCY_SHUTDOWN,
                subject="Emergency Shutdown Triggered",
                subject_id=None,
                approved=False,
                rejection_reason=check_result["reason"],
                risk_metrics=risk_metrics,
                limits_checked=limits_checked,
                severity=RiskSeverity.EMERGENCY
            )
            return False, check_result["reason"], risk_metrics

        # CHECK 3: Maximum Open Positions
        check_result = await self._check_max_positions()
        risk_metrics["checks_performed"].append("max_positions")
        limits_checked["max_positions"] = check_result

        if not check_result["passed"]:
            await self._log_decision(
                decision_type=RiskDecisionType.TRADE_REJECTION,
                subject=f"Trade for {signal.symbol}",
                subject_id=signal.id,
                approved=False,
                rejection_reason=check_result["reason"],
                risk_metrics=risk_metrics,
                limits_checked=limits_checked,
                severity=RiskSeverity.CRITICAL
            )
            return False, check_result["reason"], risk_metrics

        # CHECK 4: Daily Trade Limit
        check_result = await self._check_daily_trade_limit()
        risk_metrics["checks_performed"].append("daily_trade_limit")
        limits_checked["daily_trade_limit"] = check_result

        if not check_result["passed"]:
            await self._log_decision(
                decision_type=RiskDecisionType.TRADE_REJECTION,
                subject=f"Trade for {signal.symbol}",
                subject_id=signal.id,
                approved=False,
                rejection_reason=check_result["reason"],
                risk_metrics=risk_metrics,
                limits_checked=limits_checked,
                severity=RiskSeverity.WARNING
            )
            return False, check_result["reason"], risk_metrics

        # CHECK 5: Hourly Trade Limit
        check_result = await self._check_hourly_trade_limit()
        risk_metrics["checks_performed"].append("hourly_trade_limit")
        limits_checked["hourly_trade_limit"] = check_result

        if not check_result["passed"]:
            await self._log_decision(
                decision_type=RiskDecisionType.TRADE_REJECTION,
                subject=f"Trade for {signal.symbol}",
                subject_id=signal.id,
                approved=False,
                rejection_reason=check_result["reason"],
                risk_metrics=risk_metrics,
                limits_checked=limits_checked,
                severity=RiskSeverity.WARNING
            )
            return False, check_result["reason"], risk_metrics

        # CHECK 6: Risk per Trade
        position_size = self._calculate_position_size(
            account_balance=account_balance,
            risk_percent=min(signal.risk_percent, MAX_RISK_PER_TRADE_PERCENT),
            entry_price=signal.entry_price,
            stop_loss=signal.stop_loss
        )

        check_result = self._check_position_size(position_size)
        risk_metrics["checks_performed"].append("position_size")
        risk_metrics["calculated_position_size"] = position_size
        limits_checked["position_size"] = check_result

        if not check_result["passed"]:
            await self._log_decision(
                decision_type=RiskDecisionType.TRADE_REJECTION,
                subject=f"Trade for {signal.symbol}",
                subject_id=signal.id,
                approved=False,
                rejection_reason=check_result["reason"],
                risk_metrics=risk_metrics,
                limits_checked=limits_checked,
                severity=RiskSeverity.CRITICAL
            )
            return False, check_result["reason"], risk_metrics

        # CHECK 7: Risk/Reward Ratio
        rr_ratio = signal.risk_reward_ratio
        check_result = self._check_risk_reward(rr_ratio)
        risk_metrics["checks_performed"].append("risk_reward")
        risk_metrics["risk_reward_ratio"] = rr_ratio
        limits_checked["risk_reward"] = check_result

        if not check_result["passed"]:
            await self._log_decision(
                decision_type=RiskDecisionType.TRADE_REJECTION,
                subject=f"Trade for {signal.symbol}",
                subject_id=signal.id,
                approved=False,
                rejection_reason=check_result["reason"],
                risk_metrics=risk_metrics,
                limits_checked=limits_checked,
                severity=RiskSeverity.WARNING
            )
            return False, check_result["reason"], risk_metrics

        # CHECK 8: Strategy Budget
        check_result = await self._check_strategy_budget(signal.strategy_name, signal.symbol)
        risk_metrics["checks_performed"].append("strategy_budget")
        limits_checked["strategy_budget"] = check_result

        if not check_result["passed"]:
            await self._log_decision(
                decision_type=RiskDecisionType.TRADE_REJECTION,
                subject=f"Trade for {signal.symbol}",
                subject_id=signal.id,
                approved=False,
                rejection_reason=check_result["reason"],
                risk_metrics=risk_metrics,
                limits_checked=limits_checked,
                severity=RiskSeverity.WARNING
            )
            return False, check_result["reason"], risk_metrics

        # CHECK 9: Daily Loss Limit
        check_result = await self._check_daily_loss_limit(account_balance)
        risk_metrics["checks_performed"].append("daily_loss_limit")
        limits_checked["daily_loss_limit"] = check_result

        if not check_result["passed"]:
            await self._log_decision(
                decision_type=RiskDecisionType.TRADE_REJECTION,
                subject=f"Trade for {signal.symbol}",
                subject_id=signal.id,
                approved=False,
                rejection_reason=check_result["reason"],
                risk_metrics=risk_metrics,
                limits_checked=limits_checked,
                severity=RiskSeverity.CRITICAL
            )
            return False, check_result["reason"], risk_metrics

        # ALL CHECKS PASSED
        await self._log_decision(
            decision_type=RiskDecisionType.TRADE_APPROVAL,
            subject=f"Trade for {signal.symbol}",
            subject_id=signal.id,
            approved=True,
            rejection_reason=None,
            risk_metrics=risk_metrics,
            limits_checked=limits_checked,
            severity=RiskSeverity.INFO
        )

        logger.info(f"Risk validation APPROVED: {signal.strategy_name} {signal.symbol}")

        return True, None, risk_metrics

    async def _check_emergency_shutdown(self) -> Dict[str, Any]:
        """Check if emergency shutdown is active."""
        stmt = select(AccountRiskState).order_by(AccountRiskState.last_updated.desc()).limit(1)
        result = await self.db.execute(stmt)
        state = result.scalar_one_or_none()

        if state and state.emergency_shutdown_active:
            return {
                "passed": False,
                "reason": "Emergency shutdown is active - all trading halted",
                "current": True,
                "limit": False
            }

        return {"passed": True, "reason": None, "current": False, "limit": False}

    def _check_drawdown(self, current_drawdown: float) -> Dict[str, Any]:
        """Check account drawdown against emergency limit."""
        if current_drawdown >= EMERGENCY_DRAWDOWN_PERCENT:
            return {
                "passed": False,
                "reason": f"Emergency drawdown limit breached: {current_drawdown:.2f}% >= {EMERGENCY_DRAWDOWN_PERCENT}%",
                "current": current_drawdown,
                "limit": EMERGENCY_DRAWDOWN_PERCENT
            }

        return {"passed": True, "reason": None, "current": current_drawdown, "limit": EMERGENCY_DRAWDOWN_PERCENT}

    async def _check_max_positions(self) -> Dict[str, Any]:
        """Check maximum open positions limit."""
        stmt = select(Position).where(Position.status == PositionStatus.OPEN)
        result = await self.db.execute(stmt)
        open_positions = len(result.scalars().all())

        if open_positions >= MAX_OPEN_POSITIONS:
            return {
                "passed": False,
                "reason": f"Maximum open positions reached: {open_positions}/{MAX_OPEN_POSITIONS}",
                "current": open_positions,
                "limit": MAX_OPEN_POSITIONS
            }

        return {"passed": True, "reason": None, "current": open_positions, "limit": MAX_OPEN_POSITIONS}

    async def _check_daily_trade_limit(self) -> Dict[str, Any]:
        """Check daily trade limit."""
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        stmt = select(Position).where(Position.entry_time >= today_start)
        result = await self.db.execute(stmt)
        trades_today = len(result.scalars().all())

        if trades_today >= MAX_TRADES_PER_DAY:
            return {
                "passed": False,
                "reason": f"Daily trade limit reached: {trades_today}/{MAX_TRADES_PER_DAY}",
                "current": trades_today,
                "limit": MAX_TRADES_PER_DAY
            }

        return {"passed": True, "reason": None, "current": trades_today, "limit": MAX_TRADES_PER_DAY}

    async def _check_hourly_trade_limit(self) -> Dict[str, Any]:
        """Check hourly trade limit."""
        hour_ago = datetime.utcnow() - timedelta(hours=1)
        stmt = select(Position).where(Position.entry_time >= hour_ago)
        result = await self.db.execute(stmt)
        trades_this_hour = len(result.scalars().all())

        if trades_this_hour >= MAX_TRADES_PER_HOUR:
            return {
                "passed": False,
                "reason": f"Hourly trade limit reached: {trades_this_hour}/{MAX_TRADES_PER_HOUR}",
                "current": trades_this_hour,
                "limit": MAX_TRADES_PER_HOUR
            }

        return {"passed": True, "reason": None, "current": trades_this_hour, "limit": MAX_TRADES_PER_HOUR}

    def _calculate_position_size(
        self,
        account_balance: float,
        risk_percent: float,
        entry_price: float,
        stop_loss: float
    ) -> float:
        """Calculate position size based on risk parameters."""
        risk_amount = account_balance * (risk_percent / 100.0)
        risk_per_unit = abs(entry_price - stop_loss)

        if risk_per_unit == 0:
            return 0.0

        position_size = risk_amount / risk_per_unit
        return round(min(position_size, MAX_POSITION_SIZE_LOTS), 2)

    def _check_position_size(self, position_size: float) -> Dict[str, Any]:
        """Check position size against maximum."""
        if position_size > MAX_POSITION_SIZE_LOTS:
            return {
                "passed": False,
                "reason": f"Position size exceeds maximum: {position_size} > {MAX_POSITION_SIZE_LOTS} lots",
                "current": position_size,
                "limit": MAX_POSITION_SIZE_LOTS
            }

        if position_size <= 0:
            return {
                "passed": False,
                "reason": f"Invalid position size: {position_size}",
                "current": position_size,
                "limit": MAX_POSITION_SIZE_LOTS
            }

        return {"passed": True, "reason": None, "current": position_size, "limit": MAX_POSITION_SIZE_LOTS}

    def _check_risk_reward(self, rr_ratio: float) -> Dict[str, Any]:
        """Check risk/reward ratio."""
        if rr_ratio < MIN_RISK_REWARD_RATIO:
            return {
                "passed": False,
                "reason": f"Risk/reward ratio too low: {rr_ratio:.2f} < {MIN_RISK_REWARD_RATIO}",
                "current": rr_ratio,
                "limit": MIN_RISK_REWARD_RATIO
            }

        return {"passed": True, "reason": None, "current": rr_ratio, "limit": MIN_RISK_REWARD_RATIO}

    async def _check_strategy_budget(self, strategy_name: str, symbol: str) -> Dict[str, Any]:
        """Check strategy risk budget."""
        stmt = select(StrategyRiskBudget).where(
            and_(
                StrategyRiskBudget.strategy_name == strategy_name,
                StrategyRiskBudget.symbol == symbol
            )
        )
        result = await self.db.execute(stmt)
        budget = result.scalar_one_or_none()

        if not budget:
            # Create default budget
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
            await self.db.commit()
            await self.db.refresh(budget)

        # Check if strategy is enabled
        if not budget.is_enabled:
            return {
                "passed": False,
                "reason": f"Strategy {strategy_name} is disabled: {budget.disabled_reason}",
                "current": "disabled",
                "limit": "enabled"
            }

        # Check consecutive losses
        if budget.consecutive_losses >= budget.max_consecutive_losses:
            return {
                "passed": False,
                "reason": f"Strategy {strategy_name} has {budget.consecutive_losses} consecutive losses (max {budget.max_consecutive_losses})",
                "current": budget.consecutive_losses,
                "limit": budget.max_consecutive_losses
            }

        return {"passed": True, "reason": None, "current": budget.consecutive_losses, "limit": budget.max_consecutive_losses}

    async def _check_daily_loss_limit(self, account_balance: float) -> Dict[str, Any]:
        """Check daily loss limit."""
        stmt = select(AccountRiskState).order_by(AccountRiskState.last_updated.desc()).limit(1)
        result = await self.db.execute(stmt)
        state = result.scalar_one_or_none()

        if state:
            if state.daily_loss_percent >= MAX_DAILY_LOSS_PERCENT:
                return {
                    "passed": False,
                    "reason": f"Daily loss limit reached: {state.daily_loss_percent:.2f}% >= {MAX_DAILY_LOSS_PERCENT}%",
                    "current": state.daily_loss_percent,
                    "limit": MAX_DAILY_LOSS_PERCENT
                }

        return {"passed": True, "reason": None, "current": state.daily_loss_percent if state else 0.0, "limit": MAX_DAILY_LOSS_PERCENT}

    async def _trigger_emergency_shutdown(self, current_drawdown: float):
        """Trigger emergency shutdown."""
        stmt = select(AccountRiskState).order_by(AccountRiskState.last_updated.desc()).limit(1)
        result = await self.db.execute(stmt)
        state = result.scalar_one_or_none()

        if state:
            state.emergency_shutdown_active = True
            await self.db.commit()

        logger.critical(f"EMERGENCY SHUTDOWN TRIGGERED: Drawdown {current_drawdown:.2f}% >= {EMERGENCY_DRAWDOWN_PERCENT}%")

    async def _log_decision(
        self,
        decision_type: RiskDecisionType,
        subject: str,
        subject_id: Optional[int],
        approved: bool,
        rejection_reason: Optional[str],
        risk_metrics: Dict[str, Any],
        limits_checked: Dict[str, Any],
        severity: str
    ):
        """Log risk decision to audit trail."""
        decision = RiskDecision(
            decision_type=decision_type,
            subject=subject,
            subject_id=subject_id,
            approved=approved,
            rejection_reason=rejection_reason,
            risk_metrics=risk_metrics,
            limits_checked=limits_checked,
            severity=severity,
            decision_time=datetime.utcnow()
        )

        self.db.add(decision)
        await self.db.commit()
