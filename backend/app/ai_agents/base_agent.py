from typing import Dict, Any, Optional
from abc import ABC, abstractmethod
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.ai_agent import AIDecision, AgentMemory, AgentRole, DecisionType, SystemMode
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Abstract base class for all AI agents.
    
    Provides:
    - Decision logging with reasoning
    - Memory storage and recall
    - Mode awareness (GUIDE vs AUTONOMOUS)
    """

    def __init__(self, db: AsyncSession, system_mode: SystemMode):
        self.db = db
        self.system_mode = system_mode
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    @abstractmethod
    def get_role(self) -> AgentRole:
        """Return this agent's role."""
        pass

    async def log_decision(
        self,
        decision_type: DecisionType,
        decision: str,
        reasoning: str,
        context: Dict[str, Any],
        executed: bool = False
    ):
        """
        Log an AI decision with full reasoning and context.

        Args:
            decision_type: Type of decision made
            decision: Short summary of the decision
            reasoning: Detailed explanation of why this decision was made
            context: Full context dict (parameters, state, etc.)
            executed: Whether the decision was actually executed or just recommended
        """
        decision_record = AIDecision(
            agent_role=self.get_role(),
            decision_type=decision_type,
            decision=decision,
            reasoning=reasoning,
            context=context,
            executed=executed,
            decision_time=datetime.utcnow()
        )

        self.db.add(decision_record)
        await self.db.commit()

        log_level = "INFO" if executed else "DEBUG"
        getattr(self.logger, log_level.lower())(
            f"[{self.get_role().value}] {decision_type.value}: {decision}"
        )

    async def store_memory(
        self,
        memory_type: str,
        memory_key: str,
        data: Dict[str, Any],
        confidence: float = 0.5
    ):
        """
        Store or update agent learning memory.

        Args:
            memory_type: Category of memory (e.g., "strategy_performance")
            memory_key: Unique key within type
            data: Memory data to store
            confidence: Confidence level (0.0-1.0)
        """
        # Check if memory already exists
        stmt = select(AgentMemory).where(
            AgentMemory.agent_role == self.get_role(),
            AgentMemory.memory_type == memory_type,
            AgentMemory.memory_key == memory_key
        )

        result = await self.db.execute(stmt)
        memory = result.scalar_one_or_none()

        if memory:
            # Update existing memory
            memory.data = data
            memory.confidence = confidence
            memory.sample_count += 1
            memory.last_updated = datetime.utcnow()
        else:
            # Create new memory
            memory = AgentMemory(
                agent_role=self.get_role(),
                memory_type=memory_type,
                memory_key=memory_key,
                data=data,
                confidence=confidence,
                sample_count=1,
                last_updated=datetime.utcnow()
            )
            self.db.add(memory)

        await self.db.commit()

        self.logger.debug(
            f"Stored memory: {memory_type}/{memory_key} (confidence: {confidence:.2f})"
        )

    async def recall_memory(
        self,
        memory_type: str,
        memory_key: str
    ) -> Optional[Dict[str, Any]]:
        """
        Recall stored memory.

        Args:
            memory_type: Category of memory
            memory_key: Unique key within type

        Returns:
            Memory data dict if found, None otherwise
        """
        stmt = select(AgentMemory).where(
            AgentMemory.agent_role == self.get_role(),
            AgentMemory.memory_type == memory_type,
            AgentMemory.memory_key == memory_key
        )

        result = await self.db.execute(stmt)
        memory = result.scalar_one_or_none()

        if memory:
            self.logger.debug(f"Recalled memory: {memory_type}/{memory_key}")
            return memory.data

        return None

    async def recall_all_memories(
        self,
        memory_type: str
    ) -> list[AgentMemory]:
        """
        Recall all memories of a specific type.

        Args:
            memory_type: Category of memory

        Returns:
            List of memory records
        """
        stmt = select(AgentMemory).where(
            AgentMemory.agent_role == self.get_role(),
            AgentMemory.memory_type == memory_type
        )

        result = await self.db.execute(stmt)
        memories = result.scalars().all()

        self.logger.debug(f"Recalled {len(memories)} memories of type: {memory_type}")
        return list(memories)
