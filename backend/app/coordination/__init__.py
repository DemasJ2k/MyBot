"""
Coordination package for multi-agent coordination system.

Provides:
- MessageBus: Inter-agent message passing
- SharedStateManager: Shared state and access control
- HealthMonitor: Agent health monitoring
- CoordinationPipeline: Deterministic execution pipeline
"""

from app.coordination.message_bus import MessageBus
from app.coordination.shared_state import SharedStateManager
from app.coordination.health_monitor import HealthMonitor
from app.coordination.pipeline import CoordinationPipeline

__all__ = [
    "MessageBus",
    "SharedStateManager",
    "HealthMonitor",
    "CoordinationPipeline",
]
