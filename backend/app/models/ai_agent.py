from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, JSON, Enum as SQLEnum
from sqlalchemy.sql import func
from app.models.base import Base
from datetime import datetime
import enum


class SystemMode(str, enum.Enum):
    """System operating mode."""
    GUIDE = "guide"             # Simulate only, no live execution
    AUTONOMOUS = "autonomous"   # Live trading with hard caps


class AgentRole(str, enum.Enum):
    """AI agent roles."""
    SUPERVISOR = "supervisor"
    STRATEGY = "strategy"
    RISK = "risk"
    EXECUTION = "execution"


class DecisionType(str, enum.Enum):
    """Types of AI decisions."""
    MODE_ENFORCEMENT = "mode_enforcement"
    STRATEGY_SELECTION = "strategy_selection"
    STRATEGY_DISABLE = "strategy_disable"
    OPTIMIZATION_TRIGGER = "optimization_trigger"
    POSITION_SIZE = "position_size"
    RISK_OVERRIDE = "risk_override"
    TRADE_EXECUTION = "trade_execution"


class AIDecision(Base):
    """
    Log of all AI agent decisions with reasoning.
    
    Tracks:
    - Which agent made the decision
    - What decision was made
    - Why (reasoning/logic)
    - Was it executed or just recommended
    - Full context snapshot
    """
    __tablename__ = "ai_decisions"

    id = Column(Integer, primary_key=True, index=True)
    agent_role = Column(SQLEnum(AgentRole), nullable=False, index=True)
    decision_type = Column(SQLEnum(DecisionType), nullable=False, index=True)
    decision = Column(String, nullable=False)  # Short decision summary
    reasoning = Column(String, nullable=False)  # Detailed explanation
    context = Column(JSON, nullable=False)      # Full context (params, state, etc.)
    executed = Column(Boolean, default=False)   # Was decision executed or just logged
    decision_time = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AgentMemory(Base):
    """
    Long-term learning and memory for AI agents.
    
    Stores:
    - Strategy performance patterns
    - Risk tolerance learnings
    - Market regime observations
    - Confidence levels
    """
    __tablename__ = "agent_memory"

    id = Column(Integer, primary_key=True, index=True)
    agent_role = Column(SQLEnum(AgentRole), nullable=False, index=True)
    memory_type = Column(String, nullable=False, index=True)  # e.g., "strategy_performance", "risk_threshold"
    memory_key = Column(String, nullable=False, index=True)   # Unique identifier within type
    data = Column(JSON, nullable=False)                       # Arbitrary data storage
    confidence = Column(Float, nullable=False)                # Confidence in this memory (0.0-1.0)
    sample_count = Column(Integer, default=1)                 # Number of observations
    last_updated = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class SystemConfig(Base):
    """
    System-wide configuration.
    
    Stores:
    - Current system mode (GUIDE/AUTONOMOUS)
    - Global parameters
    - Feature flags
    """
    __tablename__ = "system_config"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, nullable=False, index=True)
    value = Column(JSON, nullable=False)
    description = Column(String, nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
