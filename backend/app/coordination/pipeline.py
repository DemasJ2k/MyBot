"""
Deterministic execution pipeline for multi-agent coordination.

Execution order:
1. Supervisor initiates cycle
2. Strategy agent analyzes market
3. Risk agent validates signals
4. Execution agent executes trades
5. Supervisor monitors and can HALT at any point
"""

from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from app.coordination.message_bus import MessageBus
from app.coordination.shared_state import SharedStateManager
from app.coordination.health_monitor import HealthMonitor
from app.models.coordination import (
    CoordinationPhase,
    MessageType,
    MessagePriority,
)
from app.models.ai_agent import SystemMode
import logging

logger = logging.getLogger(__name__)


class CoordinationPipeline:
    """
    Deterministic execution pipeline for multi-agent coordination.

    Execution order:
    1. Supervisor initiates cycle
    2. Strategy agent analyzes market
    3. Risk agent validates signals
    4. Execution agent executes trades
    5. Supervisor monitors and can HALT at any point
    """

    def __init__(self, db: AsyncSession, system_mode: SystemMode):
        self.db = db
        self.system_mode = system_mode
        self.message_bus = MessageBus(db)
        self.shared_state = SharedStateManager(db)
        self.health_monitor = HealthMonitor(db)

    async def execute_cycle(
        self,
        symbol: str,
        strategies: list[str],
        account_balance: float,
        peak_balance: float
    ) -> Dict[str, Any]:
        """
        Execute one complete coordination cycle.

        Returns:
            Cycle execution result
        """
        # Step 1: Create coordination state
        active_agents = {
            "supervisor": "active",
            "strategy": "pending",
            "risk": "pending",
            "execution": "pending"
        }

        state = await self.shared_state.create_cycle(active_agents)
        cycle_id = state.cycle_id

        result = {
            "cycle_id": cycle_id,
            "success": False,
            "phases_completed": [],
            "errors": [],
            "halt_reason": None,
            "mode": self.system_mode.value
        }

        try:
            # Step 2: Check agent health
            health_status = await self.health_monitor.check_all_agents()

            # Only check health if we have registered agents
            if health_status:
                unhealthy_agents = [name for name, healthy in health_status.items() if not healthy]
                if unhealthy_agents:
                    error_msg = f"Unhealthy agents detected: {', '.join(unhealthy_agents)}"
                    await self.shared_state.request_halt(cycle_id, error_msg, "supervisor")
                    result["errors"].append(error_msg)
                    result["halt_reason"] = error_msg
                    return result

            # Step 3: Initialize shared data
            await self.shared_state.write_shared_data(cycle_id, "symbol", symbol, "supervisor")
            await self.shared_state.write_shared_data(cycle_id, "strategies", strategies, "supervisor")
            await self.shared_state.write_shared_data(cycle_id, "account_balance", account_balance, "supervisor")
            await self.shared_state.write_shared_data(cycle_id, "peak_balance", peak_balance, "supervisor")
            await self.shared_state.write_shared_data(cycle_id, "mode", self.system_mode.value, "supervisor")

            # Step 4: STRATEGY PHASE
            phase_ok = await self._execute_strategy_phase(cycle_id)
            if not phase_ok:
                result["errors"].append("Strategy phase failed")
                return result
            result["phases_completed"].append("strategy")

            # Check for halt
            state = await self.shared_state.get_current_cycle(cycle_id)
            if state.halt_requested:
                result["halt_reason"] = state.halt_reason
                return result

            # Step 5: RISK VALIDATION PHASE
            phase_ok = await self._execute_risk_phase(cycle_id)
            if not phase_ok:
                result["errors"].append("Risk phase failed")
                return result
            result["phases_completed"].append("risk")

            # Check for halt
            state = await self.shared_state.get_current_cycle(cycle_id)
            if state.halt_requested:
                result["halt_reason"] = state.halt_reason
                return result

            # Step 6: EXECUTION PHASE
            phase_ok = await self._execute_execution_phase(cycle_id)
            if not phase_ok:
                result["errors"].append("Execution phase failed")
                return result
            result["phases_completed"].append("execution")

            # Step 7: Complete cycle
            result["success"] = True
            await self.shared_state.complete_cycle(cycle_id, result)

            logger.info(f"Coordination cycle {cycle_id} completed successfully")

            return result

        except Exception as e:
            logger.error(f"Coordination cycle {cycle_id} failed: {e}")
            result["errors"].append(str(e))
            await self.shared_state.complete_cycle(cycle_id, result, errors={"exception": str(e)})
            return result

    async def _execute_strategy_phase(self, cycle_id: str) -> bool:
        """
        Execute strategy analysis phase.

        Returns:
            True if successful
        """
        # Transition to strategy phase
        await self.shared_state.transition_phase(cycle_id, CoordinationPhase.STRATEGY_ANALYSIS, "supervisor")

        # Send command to strategy agent
        await self.message_bus.send_message(
            from_agent="supervisor",
            to_agent="strategy",
            message_type=MessageType.COMMAND,
            subject="Analyze market and select strategies",
            payload={"cycle_id": cycle_id},
            priority=MessagePriority.HIGH,
            expires_in_seconds=120
        )

        # In real implementation, strategy agent would process this command
        # and write results to shared state
        # For now, we simulate success

        # Record heartbeat
        await self.health_monitor.heartbeat("strategy")
        await self.health_monitor.record_success("strategy")

        logger.info(f"Strategy phase completed for cycle {cycle_id}")
        return True

    async def _execute_risk_phase(self, cycle_id: str) -> bool:
        """
        Execute risk validation phase.

        Returns:
            True if successful
        """
        await self.shared_state.transition_phase(cycle_id, CoordinationPhase.RISK_VALIDATION, "supervisor")

        await self.message_bus.send_message(
            from_agent="supervisor",
            to_agent="risk",
            message_type=MessageType.COMMAND,
            subject="Validate signals and calculate position sizes",
            payload={"cycle_id": cycle_id},
            priority=MessagePriority.HIGH,
            expires_in_seconds=120
        )

        await self.health_monitor.heartbeat("risk")
        await self.health_monitor.record_success("risk")

        logger.info(f"Risk phase completed for cycle {cycle_id}")
        return True

    async def _execute_execution_phase(self, cycle_id: str) -> bool:
        """
        Execute trade execution phase.

        Returns:
            True if successful
        """
        await self.shared_state.transition_phase(cycle_id, CoordinationPhase.EXECUTION, "supervisor")

        await self.message_bus.send_message(
            from_agent="supervisor",
            to_agent="execution",
            message_type=MessageType.COMMAND,
            subject="Execute validated trades",
            payload={"cycle_id": cycle_id},
            priority=MessagePriority.HIGH,
            expires_in_seconds=120
        )

        await self.health_monitor.heartbeat("execution")
        await self.health_monitor.record_success("execution")

        logger.info(f"Execution phase completed for cycle {cycle_id}")
        return True

    async def halt_cycle(self, cycle_id: str, reason: str, agent_name: str = "supervisor"):
        """
        Halt a running coordination cycle.

        Args:
            cycle_id: Cycle to halt
            reason: Reason for halt
            agent_name: Agent requesting halt
        """
        await self.shared_state.request_halt(cycle_id, reason, agent_name)
        await self.message_bus.broadcast_halt(agent_name, reason)
        logger.warning(f"Cycle {cycle_id} halted by {agent_name}: {reason}")

    async def get_cycle_status(self, cycle_id: str) -> Optional[Dict[str, Any]]:
        """Get current status of a coordination cycle."""
        state = await self.shared_state.get_current_cycle(cycle_id)
        
        if not state:
            return None
        
        return {
            "cycle_id": state.cycle_id,
            "phase": state.phase.value,
            "active_agents": state.active_agents,
            "halt_requested": state.halt_requested,
            "halt_reason": state.halt_reason,
            "started_at": state.cycle_started_at.isoformat() if state.cycle_started_at else None,
            "completed_at": state.cycle_completed_at.isoformat() if state.cycle_completed_at else None,
            "result": state.cycle_result,
            "errors": state.errors
        }
