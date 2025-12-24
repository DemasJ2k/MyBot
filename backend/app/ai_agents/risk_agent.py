from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy import select
from app.ai_agents.base_agent import BaseAgent
from app.models.ai_agent import AgentRole, DecisionType
from app.models.signal import Signal, SignalType
from app.models.position import Position, PositionStatus
import logging

logger = logging.getLogger(__name__)


# Hard caps (immutable)
HARD_CAPS = {
    "max_risk_per_trade": 2.0,           # % of account
    "max_daily_loss": 5.0,               # % of account
    "max_trades_per_day": 20,
    "max_open_positions": 10,
    "max_order_size": 1.0,               # lots
    "emergency_drawdown_stop": 15.0,     # % triggers full stop
}


class RiskAgent(BaseAgent):
    """
    Risk management and enforcement agent.

    Responsibilities:
    - Enforce hard caps (CANNOT be overridden)
    - Calculate position sizes
    - Monitor drawdown
    - Validate signals before execution
    - Emergency shutdown on critical breach
    """

    def get_role(self) -> AgentRole:
        return AgentRole.RISK

    async def validate_signal(
        self,
        signal: Signal,
        account_balance: float
    ) -> Dict[str, Any]:
        """
        Validate signal against risk rules.

        Args:
            signal: Trading signal to validate
            account_balance: Current account balance

        Returns:
            Validation result with approved flag and position size
        """
        validation = {
            "approved": False,
            "position_size": 0.0,
            "reason": "",
            "checks": {}
        }

        # Check 1: Max open positions
        stmt = select(Position).where(Position.status == PositionStatus.OPEN)
        result = await self.db.execute(stmt)
        open_positions = len(result.scalars().all())

        validation["checks"]["open_positions"] = {
            "current": open_positions,
            "limit": HARD_CAPS["max_open_positions"],
            "passed": open_positions < HARD_CAPS["max_open_positions"]
        }

        if open_positions >= HARD_CAPS["max_open_positions"]:
            validation["reason"] = f"Max open positions reached ({open_positions}/{HARD_CAPS['max_open_positions']})"
            await self._log_rejection(signal, validation["reason"])
            return validation

        # Check 2: Daily trade limit
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        stmt = select(Position).where(Position.entry_time >= today_start)
        result = await self.db.execute(stmt)
        today_trades = len(result.scalars().all())

        validation["checks"]["daily_trades"] = {
            "current": today_trades,
            "limit": HARD_CAPS["max_trades_per_day"],
            "passed": today_trades < HARD_CAPS["max_trades_per_day"]
        }

        if today_trades >= HARD_CAPS["max_trades_per_day"]:
            validation["reason"] = f"Daily trade limit reached ({today_trades}/{HARD_CAPS['max_trades_per_day']})"
            await self._log_rejection(signal, validation["reason"])
            return validation

        # Check 3: Calculate position size
        position_size = self._calculate_position_size(
            account_balance=account_balance,
            risk_percent=min(signal.risk_percent, HARD_CAPS["max_risk_per_trade"]),
            entry_price=signal.entry_price,
            stop_loss=signal.stop_loss
        )

        validation["checks"]["position_size"] = {
            "calculated": position_size,
            "limit": HARD_CAPS["max_order_size"],
            "passed": position_size <= HARD_CAPS["max_order_size"]
        }

        if position_size > HARD_CAPS["max_order_size"]:
            position_size = HARD_CAPS["max_order_size"]
            logger.warning(f"Position size capped at {HARD_CAPS['max_order_size']} lots")

        if position_size <= 0:
            validation["reason"] = "Invalid position size (≤0)"
            await self._log_rejection(signal, validation["reason"])
            return validation

        # Check 4: Risk/Reward ratio
        rr_ratio = signal.risk_reward_ratio

        validation["checks"]["risk_reward"] = {
            "ratio": rr_ratio,
            "minimum": 1.5,
            "passed": rr_ratio >= 1.5
        }

        if rr_ratio < 1.5:
            validation["reason"] = f"R:R ratio too low ({rr_ratio:.2f} < 1.5)"
            await self._log_rejection(signal, validation["reason"])
            return validation

        # All checks passed
        validation["approved"] = True
        validation["position_size"] = position_size
        validation["reason"] = "All risk checks passed"

        await self.log_decision(
            decision_type=DecisionType.POSITION_SIZE,
            decision=f"Approved signal with position size {position_size:.2f}",
            reasoning="Signal passed all risk validation checks",
            context={
                "signal_id": signal.id,
                "strategy": signal.strategy_name,
                "symbol": signal.symbol,
                "position_size": position_size,
                "checks": validation["checks"]
            },
            executed=True
        )

        return validation

    def _calculate_position_size(
        self,
        account_balance: float,
        risk_percent: float,
        entry_price: float,
        stop_loss: float
    ) -> float:
        """
        Calculate position size based on risk parameters.

        Formula: position_size = (account_balance * risk%) / (entry_price - stop_loss)
        """
        risk_amount = account_balance * (risk_percent / 100.0)
        risk_per_unit = abs(entry_price - stop_loss)

        if risk_per_unit == 0:
            return 0.0

        position_size = risk_amount / risk_per_unit
        return round(position_size, 2)

    async def _log_rejection(self, signal: Signal, reason: str):
        """Log signal rejection."""
        await self.log_decision(
            decision_type=DecisionType.POSITION_SIZE,
            decision=f"Rejected signal for {signal.symbol}",
            reasoning=reason,
            context={
                "signal_id": signal.id,
                "strategy": signal.strategy_name,
                "symbol": signal.symbol,
                "entry_price": signal.entry_price
            },
            executed=False
        )

    async def check_emergency_conditions(self, account_balance: float, peak_balance: float) -> bool:
        """
        Check for emergency shutdown conditions.

        Returns:
            True if emergency shutdown required
        """
        if peak_balance == 0:
            return False

        current_drawdown = ((peak_balance - account_balance) / peak_balance) * 100.0

        if current_drawdown >= HARD_CAPS["emergency_drawdown_stop"]:
            await self.log_decision(
                decision_type=DecisionType.RISK_OVERRIDE,
                decision="EMERGENCY SHUTDOWN - Critical drawdown reached",
                reasoning=f"Account drawdown {current_drawdown:.2f}% exceeds emergency threshold {HARD_CAPS['emergency_drawdown_stop']}%",
                context={
                    "account_balance": account_balance,
                    "peak_balance": peak_balance,
                    "drawdown_percent": current_drawdown,
                    "threshold": HARD_CAPS["emergency_drawdown_stop"]
                },
                executed=True
            )

            logger.critical(f"EMERGENCY SHUTDOWN: Drawdown {current_drawdown:.2f}% >= {HARD_CAPS['emergency_drawdown_stop']}%")
            return True

        return False
