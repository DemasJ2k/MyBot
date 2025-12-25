"""
HARD RISK LIMITS

These limits are IMMUTABLE and CANNOT be overridden by any agent,
user, or system component. They represent the absolute maximum risk
tolerance for the system.

ANY ATTEMPT TO MODIFY THESE VALUES MUST BE AUDITED AND APPROVED
BY SYSTEM ADMINISTRATORS.
"""

# Position Limits
MAX_RISK_PER_TRADE_PERCENT = 2.0          # Maximum 2% of account per trade
MAX_POSITION_SIZE_LOTS = 1.0              # Maximum 1.0 lots per position
MAX_OPEN_POSITIONS = 10                    # Maximum 10 simultaneous positions

# Account Limits
MAX_DAILY_LOSS_PERCENT = 5.0              # Maximum 5% daily loss
EMERGENCY_DRAWDOWN_PERCENT = 15.0         # Emergency shutdown at 15% drawdown
MAX_ACCOUNT_LEVERAGE = 10.0               # Maximum 10:1 leverage

# Daily Limits
MAX_TRADES_PER_DAY = 20                   # Maximum 20 trades per day
MAX_TRADES_PER_HOUR = 5                   # Maximum 5 trades per hour

# Strategy Limits
MAX_STRATEGIES_ACTIVE = 4                 # Maximum 4 active strategies
MAX_RISK_PER_STRATEGY_PERCENT = 5.0       # Maximum 5% total exposure per strategy

# Correlation Limits
MAX_CORRELATED_POSITIONS = 3              # Maximum 3 highly correlated positions
CORRELATION_THRESHOLD = 0.7               # Positions with >0.7 correlation considered correlated

# Minimum Requirements
MIN_RISK_REWARD_RATIO = 1.5               # Minimum 1.5:1 risk/reward
MIN_ACCOUNT_BALANCE = 1000.0              # Minimum $1000 account balance


class RiskSeverity:
    """Risk event severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


# Maximum position size as percentage of account balance
MAX_POSITION_SIZE_PERCENT = 10.0

# Strategy auto-disable threshold (consecutive losses)
STRATEGY_AUTO_DISABLE_THRESHOLD = 5


def validate_immutable_constants() -> None:
    """
    Validates that hard-coded constants are within acceptable ranges.
    Called on system startup.
    Raises AssertionError if any constant is out of range.
    """
    assert 0 < MAX_RISK_PER_TRADE_PERCENT <= 5.0, "MAX_RISK_PER_TRADE_PERCENT out of acceptable range"
    assert 0 < MAX_DAILY_LOSS_PERCENT <= 10.0, "MAX_DAILY_LOSS_PERCENT out of acceptable range"
    assert 0 < EMERGENCY_DRAWDOWN_PERCENT <= 25.0, "EMERGENCY_DRAWDOWN_PERCENT out of acceptable range"
    assert 1 <= MAX_OPEN_POSITIONS <= 50, "MAX_OPEN_POSITIONS out of acceptable range"
    assert 1 <= MAX_TRADES_PER_DAY <= 100, "MAX_TRADES_PER_DAY out of acceptable range"
    assert 1.0 <= MIN_RISK_REWARD_RATIO <= 5.0, "MIN_RISK_REWARD_RATIO out of acceptable range"
    assert 0 < MAX_POSITION_SIZE_PERCENT <= 20.0, "MAX_POSITION_SIZE_PERCENT out of acceptable range"
    assert 1 <= STRATEGY_AUTO_DISABLE_THRESHOLD <= 10, "STRATEGY_AUTO_DISABLE_THRESHOLD out of acceptable range"
