"""
Manages shared state between agents.

Enforces:
- Single source of truth
- Atomic state transitions
- Phase-based access control
"""

from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.coordination import CoordinationState, CoordinationPhase
import logging
import uuid

logger = logging.getLogger(__name__)


class SharedStateManager:
    """
    Manages shared state between agents.

    Enforces:
    - Single source of truth
    - Atomic state transitions
    - Phase-based access control
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_cycle(
        self,
        active_agents: Dict[str, str]
    ) -> CoordinationState:
        """
        Create a new coordination cycle.

        Args:
            active_agents: Dict of {agent_name: "pending"}

        Returns:
            New coordination state
        """
        cycle_id = f"cycle_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

        state = CoordinationState(
            cycle_id=cycle_id,
            phase=CoordinationPhase.INITIALIZING,
            active_agents=active_agents,
            shared_data={},
            halt_requested=False,
            cycle_started_at=datetime.utcnow()
        )

        self.db.add(state)
        await self.db.commit()
        await self.db.refresh(state)

        logger.info(f"Created coordination cycle: {cycle_id}")

        return state

    async def get_current_cycle(self, cycle_id: str) -> Optional[CoordinationState]:
        """Get current cycle state."""
        stmt = select(CoordinationState).where(CoordinationState.cycle_id == cycle_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def transition_phase(
        self,
        cycle_id: str,
        new_phase: CoordinationPhase,
        agent_name: str
    ) -> bool:
        """
        Transition cycle to new phase.

        Only Supervisor can transition phases.

        Args:
            cycle_id: Cycle ID
            new_phase: Target phase
            agent_name: Agent requesting transition

        Returns:
            True if transition successful
        """
        state = await self.get_current_cycle(cycle_id)

        if not state:
            logger.error(f"Cycle {cycle_id} not found")
            return False

        # Only Supervisor can transition phases
        if agent_name != "supervisor":
            logger.error(f"Agent {agent_name} cannot transition phases (Supervisor only)")
            return False

        # Check if halt requested
        if state.halt_requested:
            logger.warning(f"Cannot transition to {new_phase.value}: HALT requested")
            return False

        # Transition
        old_phase = state.phase
        state.phase = new_phase

        await self.db.commit()

        logger.info(f"Phase transition: {old_phase.value} -> {new_phase.value}")

        return True

    async def write_shared_data(
        self,
        cycle_id: str,
        key: str,
        value: Any,
        agent_name: str
    ) -> bool:
        """
        Write data to shared state.

        Access control:
        - Strategy agent: Can write "strategy_*" keys
        - Risk agent: Can write "risk_*" keys
        - Execution agent: Can write "execution_*" keys
        - Supervisor: Can write any key

        Args:
            cycle_id: Cycle ID
            key: Data key
            value: Data value
            agent_name: Agent writing data

        Returns:
            True if write successful
        """
        state = await self.get_current_cycle(cycle_id)

        if not state:
            logger.error(f"Cycle {cycle_id} not found")
            return False

        # Access control
        if agent_name != "supervisor":
            if not key.startswith(f"{agent_name}_"):
                logger.error(f"Agent {agent_name} cannot write key '{key}' (must start with '{agent_name}_')")
                return False

        # Write data
        shared_data = dict(state.shared_data) if state.shared_data else {}
        shared_data[key] = value
        state.shared_data = shared_data

        await self.db.commit()

        logger.debug(f"Shared data written: {key} by {agent_name}")

        return True

    async def read_shared_data(
        self,
        cycle_id: str,
        key: str
    ) -> Optional[Any]:
        """Read data from shared state."""
        state = await self.get_current_cycle(cycle_id)

        if not state:
            return None

        return state.shared_data.get(key)

    async def read_all_shared_data(
        self,
        cycle_id: str
    ) -> Dict[str, Any]:
        """Read all shared data for a cycle."""
        state = await self.get_current_cycle(cycle_id)

        if not state:
            return {}

        return dict(state.shared_data) if state.shared_data else {}

    async def request_halt(
        self,
        cycle_id: str,
        reason: str,
        agent_name: str
    ):
        """
        Request cycle halt.

        Any agent can request halt, but only Supervisor can enforce.

        Args:
            cycle_id: Cycle ID
            reason: Halt reason
            agent_name: Agent requesting halt
        """
        state = await self.get_current_cycle(cycle_id)

        if not state:
            logger.error(f"Cycle {cycle_id} not found")
            return

        state.halt_requested = True
        state.halt_reason = f"{agent_name}: {reason}"
        state.phase = CoordinationPhase.HALTED

        await self.db.commit()

        logger.warning(f"HALT requested by {agent_name}: {reason}")

    async def complete_cycle(
        self,
        cycle_id: str,
        result: Dict[str, Any],
        errors: Optional[Dict[str, Any]] = None
    ):
        """Mark cycle as completed."""
        state = await self.get_current_cycle(cycle_id)

        if not state:
            logger.error(f"Cycle {cycle_id} not found")
            return

        state.phase = CoordinationPhase.COMPLETED if not errors else CoordinationPhase.FAILED
        state.cycle_completed_at = datetime.utcnow()
        state.cycle_result = result
        state.errors = errors

        await self.db.commit()

        logger.info(f"Cycle {cycle_id} completed with status: {state.phase.value}")

    async def get_recent_cycles(
        self,
        limit: int = 20
    ) -> list[CoordinationState]:
        """Get recent coordination cycles."""
        stmt = select(CoordinationState).order_by(
            CoordinationState.cycle_started_at.desc()
        ).limit(limit)
        
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
