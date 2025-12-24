"""
Risk Engine Package.

Provides authoritative risk management with:
- Immutable hard limits
- Pre-execution validation
- Continuous monitoring
- Audit trail
"""

from app.risk.constants import (
    MAX_RISK_PER_TRADE_PERCENT,
    MAX_POSITION_SIZE_LOTS,
    MAX_OPEN_POSITIONS,
    MAX_DAILY_LOSS_PERCENT,
    EMERGENCY_DRAWDOWN_PERCENT,
    MAX_ACCOUNT_LEVERAGE,
    MAX_TRADES_PER_DAY,
    MAX_TRADES_PER_HOUR,
    MAX_STRATEGIES_ACTIVE,
    MAX_RISK_PER_STRATEGY_PERCENT,
    MAX_CORRELATED_POSITIONS,
    CORRELATION_THRESHOLD,
    MIN_RISK_REWARD_RATIO,
    MIN_ACCOUNT_BALANCE,
    RiskSeverity,
)
from app.risk.validator import RiskValidator
from app.risk.monitor import RiskMonitor

__all__ = [
    # Constants
    "MAX_RISK_PER_TRADE_PERCENT",
    "MAX_POSITION_SIZE_LOTS",
    "MAX_OPEN_POSITIONS",
    "MAX_DAILY_LOSS_PERCENT",
    "EMERGENCY_DRAWDOWN_PERCENT",
    "MAX_ACCOUNT_LEVERAGE",
    "MAX_TRADES_PER_DAY",
    "MAX_TRADES_PER_HOUR",
    "MAX_STRATEGIES_ACTIVE",
    "MAX_RISK_PER_STRATEGY_PERCENT",
    "MAX_CORRELATED_POSITIONS",
    "CORRELATION_THRESHOLD",
    "MIN_RISK_REWARD_RATIO",
    "MIN_ACCOUNT_BALANCE",
    "RiskSeverity",
    # Classes
    "RiskValidator",
    "RiskMonitor",
]
