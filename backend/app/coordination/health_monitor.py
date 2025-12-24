"""
Monitor agent health and performance.

Detects:
- Unresponsive agents
- High error rates
- Performance degradation
"""

from typing import Dict, Optional, List
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.coordination import AgentHealth
import logging

logger = logging.getLogger(__name__)


class HealthMonitor:
    """
    Monitor agent health and performance.

    Detects:
    - Unresponsive agents
    - High error rates
    - Performance degradation
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.heartbeat_timeout_seconds = 60

    async def heartbeat(
        self,
        agent_name: str,
        response_time_ms: float = 0.0
    ):
        """
        Record agent heartbeat.

        Args:
            agent_name: Agent name
            response_time_ms: Response time in milliseconds
        """
        stmt = select(AgentHealth).where(AgentHealth.agent_name == agent_name)
        result = await self.db.execute(stmt)
        health = result.scalar_one_or_none()

        if health:
            # Update existing
            health.last_heartbeat = datetime.utcnow()
            health.is_healthy = True

            # Update rolling average response time
            total_ops = health.success_count + health.error_count
            if total_ops > 0:
                health.avg_response_time_ms = (
                    (health.avg_response_time_ms * total_ops + response_time_ms) / (total_ops + 1)
                )
        else:
            # Create new
            health = AgentHealth(
                agent_name=agent_name,
                is_healthy=True,
                last_heartbeat=datetime.utcnow(),
                avg_response_time_ms=response_time_ms,
                error_count=0,
                success_count=0
            )
            self.db.add(health)

        await self.db.commit()

    async def record_success(self, agent_name: str):
        """Record successful agent operation."""
        stmt = select(AgentHealth).where(AgentHealth.agent_name == agent_name)
        result = await self.db.execute(stmt)
        health = result.scalar_one_or_none()

        if health:
            health.success_count += 1
            await self.db.commit()

    async def record_error(self, agent_name: str, error_message: str):
        """Record agent error."""
        stmt = select(AgentHealth).where(AgentHealth.agent_name == agent_name)
        result = await self.db.execute(stmt)
        health = result.scalar_one_or_none()

        if health:
            health.error_count += 1
            health.status_message = error_message

            # Mark unhealthy if error rate > 50%
            total_ops = health.success_count + health.error_count
            error_rate = health.error_count / total_ops if total_ops > 0 else 0

            if error_rate > 0.5:
                health.is_healthy = False
                logger.error(f"Agent {agent_name} marked unhealthy (error rate: {error_rate:.2%})")

            await self.db.commit()

    async def check_all_agents(self) -> Dict[str, bool]:
        """
        Check health of all agents.

        Returns:
            Dict of {agent_name: is_healthy}
        """
        stmt = select(AgentHealth)
        result = await self.db.execute(stmt)
        health_records = result.scalars().all()

        health_status = {}
        cutoff_time = datetime.utcnow() - timedelta(seconds=self.heartbeat_timeout_seconds)

        for health in health_records:
            # Check if heartbeat is recent
            is_responsive = health.last_heartbeat > cutoff_time

            # Overall health = responsive AND healthy flag
            health_status[health.agent_name] = health.is_healthy and is_responsive

            if not health_status[health.agent_name]:
                logger.warning(f"Agent {health.agent_name} is unhealthy or unresponsive")

        return health_status

    async def get_agent_health(self, agent_name: str) -> Optional[AgentHealth]:
        """Get health record for a specific agent."""
        stmt = select(AgentHealth).where(AgentHealth.agent_name == agent_name)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all_agent_health(self) -> List[AgentHealth]:
        """Get health records for all agents."""
        stmt = select(AgentHealth)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def initialize_agent(self, agent_name: str):
        """Initialize health record for an agent."""
        existing = await self.get_agent_health(agent_name)
        
        if not existing:
            health = AgentHealth(
                agent_name=agent_name,
                is_healthy=True,
                last_heartbeat=datetime.utcnow(),
                avg_response_time_ms=0.0,
                error_count=0,
                success_count=0
            )
            self.db.add(health)
            await self.db.commit()
            logger.info(f"Initialized health record for agent: {agent_name}")

    async def reset_agent_health(self, agent_name: str):
        """Reset health statistics for an agent."""
        health = await self.get_agent_health(agent_name)
        
        if health:
            health.is_healthy = True
            health.error_count = 0
            health.success_count = 0
            health.avg_response_time_ms = 0.0
            health.status_message = None
            health.last_heartbeat = datetime.utcnow()
            await self.db.commit()
            logger.info(f"Reset health for agent: {agent_name}")
