"""
Execution package - The ONLY authorized path to execute trades.

This package provides:
- BaseBrokerAdapter: Abstract interface for all broker integrations
- PaperBrokerAdapter: Simulated trading for testing and GUIDE mode
- ExecutionEngine: Central orchestrator with pre-validation pipeline

CRITICAL: All trade execution MUST go through ExecutionEngine.
Direct broker access is prohibited in production.
"""

from .base_broker import (
    BaseBrokerAdapter,
    BrokerOrderResult,
    BrokerPositionInfo,
    BrokerAccountInfo,
    OrderRequest,
)
from .paper_broker import PaperBrokerAdapter
from .engine import (
    ExecutionEngine,
    ExecutionMode,
    ExecutionResult,
)


__all__ = [
    # Base broker interface
    "BaseBrokerAdapter",
    "BrokerOrderResult",
    "BrokerPositionInfo",
    "BrokerAccountInfo",
    "OrderRequest",
    # Paper trading
    "PaperBrokerAdapter",
    # Execution engine
    "ExecutionEngine",
    "ExecutionMode",
    "ExecutionResult",
]
