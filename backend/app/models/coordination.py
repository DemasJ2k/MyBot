"""
Coordination models for multi-agent coordination system.
Supports message passing, shared state, and agent health monitoring.
"""

from sqlalchemy import String, Float, Integer, JSON, Enum as SQLEnum, Boolean, Index, Text
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from typing import Optional, Dict, Any
import enum
from app.models.base import Base, TimestampMixin


class AgentAuthorityLevel(int, enum.Enum):
    """Agent authority levels - lower number = higher authority."""
    SUPERVISOR = 0      # Highest authority
    SUBORDINATE = 1     # Strategy, Risk, Execution agents


class CoordinationPhase(str, enum.Enum):
    """Phases in a coordination cycle."""
    IDLE = "idle"
    INITIALIZING = "initializing"
    STRATEGY_ANALYSIS = "strategy_analysis"
    RISK_VALIDATION = "risk_validation"
    EXECUTION = "execution"
    MONITORING = "monitoring"
    HALTED = "halted"
    FAILED = "failed"
    COMPLETED = "completed"


class MessageType(str, enum.Enum):
    """Types of inter-agent messages."""
    COMMAND = "command"
    REQUEST = "request"
    RESPONSE = "response"
    EVENT = "event"
    HALT = "halt"


class MessagePriority(int, enum.Enum):
    """Message priority levels - lower number = higher priority."""
    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3


class AgentMessage(Base, TimestampMixin):
    """Inter-agent message for coordination."""
    __tablename__ = "agent_messages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Message routing
    from_agent: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    to_agent: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    # Message details
    message_type: Mapped[MessageType] = mapped_column(SQLEnum(MessageType), nullable=False)
    priority: Mapped[MessagePriority] = mapped_column(SQLEnum(MessagePriority), nullable=False, default=MessagePriority.NORMAL)

    # Content
    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    payload: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)

    # Status
    processed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    processed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    response_message_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Timestamps
    sent_at: Mapped[datetime] = mapped_column(nullable=False, index=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    __table_args__ = (
        Index("ix_agent_message_to_processed", "to_agent", "processed"),
    )

    def __repr__(self) -> str:
        return f"<AgentMessage {self.id} {self.from_agent}->{self.to_agent} {self.message_type.value}>"


class CoordinationState(Base, TimestampMixin):
    """Shared state for agent coordination."""
    __tablename__ = "coordination_state"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    cycle_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)

    # Current phase
    phase: Mapped[CoordinationPhase] = mapped_column(SQLEnum(CoordinationPhase), nullable=False, index=True)

    # Agents involved
    active_agents: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)  # {agent_name: status}

    # Shared data
    shared_data: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    # Control flags
    halt_requested: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    halt_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timing
    cycle_started_at: Mapped[datetime] = mapped_column(nullable=False)
    cycle_completed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Results
    cycle_result: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    errors: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    def __repr__(self) -> str:
        return f"<CoordinationState {self.cycle_id} {self.phase.value}>"


class AgentHealth(Base, TimestampMixin):
    """Agent health monitoring."""
    __tablename__ = "agent_health"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    agent_name: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    # Health metrics
    is_healthy: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_heartbeat: Mapped[datetime] = mapped_column(nullable=False, index=True)

    # Performance metrics
    avg_response_time_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    success_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Status
    status_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<AgentHealth {self.agent_name} healthy={self.is_healthy}>"
