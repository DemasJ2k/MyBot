from typing import Dict, Any
from sqlalchemy import select
from app.ai_agents.base_agent import BaseAgent
from app.models.ai_agent import AgentRole, DecisionType, SystemMode, SystemConfig
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


class SupervisorAgent(BaseAgent):
    """
    Supervisor agent - top-level orchestration and rule enforcement.

    Responsibilities:
    - Enforce system mode (GUIDE vs AUTONOMOUS)
    - Monitor hard caps compliance
    - Coordinate other agents
    - Emergency shutdown authority
    """

    def get_role(self) -> AgentRole:
        return AgentRole.SUPERVISOR

    async def enforce_mode(self) -> bool:
        """
        Enforce system mode and hard caps.

        Returns:
            True if mode enforcement passed, False otherwise
        """
        # Load current mode from database
        stmt = select(SystemConfig).where(SystemConfig.key == "system_mode")
        result = await self.db.execute(stmt)
        config = result.scalar_one_or_none()

        if config:
            mode_str = config.value.get("mode", "guide")
            self.system_mode = SystemMode.GUIDE if mode_str == "guide" else SystemMode.AUTONOMOUS
        else:
            # Default to GUIDE mode
            self.system_mode = SystemMode.GUIDE

        # Log mode enforcement
        await self.log_decision(
            decision_type=DecisionType.MODE_ENFORCEMENT,
            decision=f"System operating in {self.system_mode.value} mode",
            reasoning=f"Mode loaded from config: {self.system_mode.value}",
            context={
                "mode": self.system_mode.value,
                "hard_caps": HARD_CAPS
            },
            executed=True
        )

        logger.info(f"System mode enforced: {self.system_mode.value}")

        return True

    async def verify_hard_caps(self) -> Dict[str, Any]:
        """
        Verify that hard caps are correctly configured and immutable.

        Returns:
            Verification result with all hard caps
        """
        verification = {
            "verified": True,
            "hard_caps": HARD_CAPS,
            "immutable": True,
            "violations": []
        }

        # Hard caps should never be modified at runtime
        # This is a safety check
        expected_caps = {
            "max_risk_per_trade": 2.0,
            "max_daily_loss": 5.0,
            "max_trades_per_day": 20,
            "max_open_positions": 10,
            "max_order_size": 1.0,
            "emergency_drawdown_stop": 15.0,
        }

        for key, expected_value in expected_caps.items():
            if HARD_CAPS.get(key) != expected_value:
                verification["verified"] = False
                verification["violations"].append(f"{key} modified: {HARD_CAPS.get(key)} != {expected_value}")

        await self.log_decision(
            decision_type=DecisionType.MODE_ENFORCEMENT,
            decision="Hard caps verification",
            reasoning="Verified immutability of hard caps",
            context=verification,
            executed=True
        )

        return verification

    async def can_proceed_with_trading(
        self,
        account_balance: float,
        peak_balance: float,
        open_positions: int,
        trades_today: int
    ) -> Dict[str, Any]:
        """
        Check if trading can proceed based on hard caps.

        Args:
            account_balance: Current account balance
            peak_balance: Peak account balance
            open_positions: Number of open positions
            trades_today: Number of trades executed today

        Returns:
            Permission dict with can_proceed flag and reasons
        """
        permission = {
            "can_proceed": True,
            "reasons": [],
            "checks": {}
        }

        # Check 1: Max open positions
        permission["checks"]["open_positions"] = {
            "current": open_positions,
            "limit": HARD_CAPS["max_open_positions"],
            "passed": open_positions < HARD_CAPS["max_open_positions"]
        }

        if open_positions >= HARD_CAPS["max_open_positions"]:
            permission["can_proceed"] = False
            permission["reasons"].append(f"Max open positions reached ({open_positions}/{HARD_CAPS['max_open_positions']})")

        # Check 2: Daily trade limit
        permission["checks"]["daily_trades"] = {
            "current": trades_today,
            "limit": HARD_CAPS["max_trades_per_day"],
            "passed": trades_today < HARD_CAPS["max_trades_per_day"]
        }

        if trades_today >= HARD_CAPS["max_trades_per_day"]:
            permission["can_proceed"] = False
            permission["reasons"].append(f"Daily trade limit reached ({trades_today}/{HARD_CAPS['max_trades_per_day']})")

        # Check 3: Drawdown limit
        if peak_balance > 0:
            current_drawdown = ((peak_balance - account_balance) / peak_balance) * 100.0

            permission["checks"]["drawdown"] = {
                "current": current_drawdown,
                "limit": HARD_CAPS["emergency_drawdown_stop"],
                "passed": current_drawdown < HARD_CAPS["emergency_drawdown_stop"]
            }

            if current_drawdown >= HARD_CAPS["emergency_drawdown_stop"]:
                permission["can_proceed"] = False
                permission["reasons"].append(f"Emergency drawdown exceeded ({current_drawdown:.2f}% >= {HARD_CAPS['emergency_drawdown_stop']}%)")

        await self.log_decision(
            decision_type=DecisionType.MODE_ENFORCEMENT,
            decision=f"Trading permission: {permission['can_proceed']}",
            reasoning=f"Checks: {len([c for c in permission['checks'].values() if c['passed']])}/{len(permission['checks'])} passed",
            context=permission,
            executed=True
        )

        return permission
