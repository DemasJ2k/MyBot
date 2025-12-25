"""
System Settings and User Preferences Models.

These models manage centralized settings, mode configuration,
and audit trails for all settings changes.
"""

from sqlalchemy import String, Float, Integer, Boolean, JSON, Enum as SQLEnum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
import enum

from app.models.base import Base


class SystemMode(str, enum.Enum):
    """System operating mode."""
    GUIDE = "guide"
    AUTONOMOUS = "autonomous"


class BrokerType(str, enum.Enum):
    """Supported broker types."""
    MT5 = "mt5"
    OANDA = "oanda"
    BINANCE = "binance"
    PAPER = "paper"


class SystemSettings(Base):
    """
    Centralized system settings.
    
    This is THE SINGLE SOURCE OF TRUTH for system configuration.
    All configurable behavior is controlled through this model.
    """
    __tablename__ = "system_settings"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Mode Configuration
    mode: Mapped[SystemMode] = mapped_column(
        SQLEnum(SystemMode), 
        default=SystemMode.GUIDE, 
        nullable=False
    )

    # Execution Mode (SIMULATION/PAPER/LIVE)
    execution_mode: Mapped[str] = mapped_column(
        String(20),
        default="simulation",
        nullable=False
    )

    # Broker Configuration
    broker_type: Mapped[BrokerType] = mapped_column(
        SQLEnum(BrokerType), 
        default=BrokerType.PAPER, 
        nullable=False
    )
    broker_connected: Mapped[bool] = mapped_column(
        Boolean, 
        default=False, 
        nullable=False
    )

    # Data Provider Configuration
    data_provider: Mapped[str] = mapped_column(
        String(50), 
        default="twelvedata", 
        nullable=False
    )

    # Risk Configuration (Soft Limits - must be <= hard limits)
    # These can be configured but cannot exceed hard-coded constants
    max_risk_per_trade_percent: Mapped[float] = mapped_column(
        Float, 
        default=2.0, 
        nullable=False
    )
    max_daily_loss_percent: Mapped[float] = mapped_column(
        Float, 
        default=5.0, 
        nullable=False
    )
    emergency_drawdown_percent: Mapped[float] = mapped_column(
        Float, 
        default=15.0, 
        nullable=False
    )
    max_open_positions: Mapped[int] = mapped_column(
        Integer, 
        default=10, 
        nullable=False
    )
    max_trades_per_day: Mapped[int] = mapped_column(
        Integer, 
        default=20, 
        nullable=False
    )

    # Strategy Management
    auto_disable_strategies: Mapped[bool] = mapped_column(
        Boolean, 
        default=True, 
        nullable=False
    )
    strategy_disable_threshold: Mapped[int] = mapped_column(
        Integer, 
        default=5, 
        nullable=False
    )

    # Mode Transition Behavior
    cancel_orders_on_mode_switch: Mapped[bool] = mapped_column(
        Boolean, 
        default=True, 
        nullable=False
    )
    require_confirmation_for_autonomous: Mapped[bool] = mapped_column(
        Boolean, 
        default=True, 
        nullable=False
    )

    # System Health Monitoring
    health_check_interval_seconds: Mapped[int] = mapped_column(
        Integer, 
        default=30, 
        nullable=False
    )
    agent_timeout_seconds: Mapped[int] = mapped_column(
        Integer, 
        default=60, 
        nullable=False
    )

    # Notification Settings
    email_notifications_enabled: Mapped[bool] = mapped_column(
        Boolean, 
        default=False, 
        nullable=False
    )
    notification_email: Mapped[str | None] = mapped_column(
        String(255), 
        nullable=True
    )

    # Advanced Settings (flexible JSON for future extensions)
    advanced_settings: Mapped[dict] = mapped_column(
        JSON, 
        default=dict, 
        nullable=False
    )

    # Audit Fields
    version: Mapped[int] = mapped_column(
        Integer, 
        default=1, 
        nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, 
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, 
        onupdate=datetime.utcnow, 
        nullable=False
    )
    updated_by: Mapped[int | None] = mapped_column(
        Integer, 
        nullable=True
    )  # user_id

    def validate(self) -> tuple[bool, str]:
        """
        Validates settings against hard-coded constraints.
        Returns (is_valid, error_message).
        """
        from app.risk.constants import (
            MAX_RISK_PER_TRADE_PERCENT,
            MAX_DAILY_LOSS_PERCENT,
            EMERGENCY_DRAWDOWN_PERCENT,
            MAX_OPEN_POSITIONS,
            MAX_TRADES_PER_DAY,
            STRATEGY_AUTO_DISABLE_THRESHOLD,
        )

        # Validate risk limits do not exceed hard caps
        if self.max_risk_per_trade_percent > MAX_RISK_PER_TRADE_PERCENT:
            return False, f"max_risk_per_trade_percent cannot exceed {MAX_RISK_PER_TRADE_PERCENT}%"

        if self.max_daily_loss_percent > MAX_DAILY_LOSS_PERCENT:
            return False, f"max_daily_loss_percent cannot exceed {MAX_DAILY_LOSS_PERCENT}%"

        if self.emergency_drawdown_percent > EMERGENCY_DRAWDOWN_PERCENT:
            return False, f"emergency_drawdown_percent cannot exceed {EMERGENCY_DRAWDOWN_PERCENT}%"

        if self.max_open_positions > MAX_OPEN_POSITIONS:
            return False, f"max_open_positions cannot exceed {MAX_OPEN_POSITIONS}"

        if self.max_trades_per_day > MAX_TRADES_PER_DAY:
            return False, f"max_trades_per_day cannot exceed {MAX_TRADES_PER_DAY}"

        if self.strategy_disable_threshold > STRATEGY_AUTO_DISABLE_THRESHOLD:
            return False, f"strategy_disable_threshold cannot exceed {STRATEGY_AUTO_DISABLE_THRESHOLD}"

        # Validate logical consistency
        if self.max_risk_per_trade_percent <= 0:
            return False, "max_risk_per_trade_percent must be positive"

        if self.max_daily_loss_percent <= 0:
            return False, "max_daily_loss_percent must be positive"

        if self.max_daily_loss_percent < self.max_risk_per_trade_percent:
            return False, "max_daily_loss_percent should be >= max_risk_per_trade_percent"

        if self.max_open_positions < 1:
            return False, "max_open_positions must be at least 1"

        if self.max_trades_per_day < 1:
            return False, "max_trades_per_day must be at least 1"

        if self.strategy_disable_threshold < 1:
            return False, "strategy_disable_threshold must be at least 1"

        if self.health_check_interval_seconds < 10:
            return False, "health_check_interval_seconds must be at least 10"

        if self.agent_timeout_seconds < 10:
            return False, "agent_timeout_seconds must be at least 10"

        return True, ""

    def to_dict(self) -> dict:
        """Convert settings to dictionary for audit purposes."""
        return {
            "mode": self.mode.value,
            "broker_type": self.broker_type.value,
            "broker_connected": self.broker_connected,
            "data_provider": self.data_provider,
            "max_risk_per_trade_percent": self.max_risk_per_trade_percent,
            "max_daily_loss_percent": self.max_daily_loss_percent,
            "emergency_drawdown_percent": self.emergency_drawdown_percent,
            "max_open_positions": self.max_open_positions,
            "max_trades_per_day": self.max_trades_per_day,
            "auto_disable_strategies": self.auto_disable_strategies,
            "strategy_disable_threshold": self.strategy_disable_threshold,
            "cancel_orders_on_mode_switch": self.cancel_orders_on_mode_switch,
            "require_confirmation_for_autonomous": self.require_confirmation_for_autonomous,
            "health_check_interval_seconds": self.health_check_interval_seconds,
            "agent_timeout_seconds": self.agent_timeout_seconds,
            "email_notifications_enabled": self.email_notifications_enabled,
            "notification_email": self.notification_email,
            "version": self.version,
        }


class SettingsAudit(Base):
    """
    Audit trail for all settings changes.
    
    Every change to SystemSettings creates a new audit entry,
    preserving the full history of system configuration changes.
    """
    __tablename__ = "settings_audit"

    id: Mapped[int] = mapped_column(primary_key=True)
    settings_version: Mapped[int] = mapped_column(Integer, nullable=False)
    changed_by: Mapped[int | None] = mapped_column(Integer, nullable=True)  # user_id, None = system
    changed_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, nullable=False)
    change_type: Mapped[str] = mapped_column(String(50), nullable=False)  # mode_change, risk_update, etc.
    old_value: Mapped[dict] = mapped_column(JSON, nullable=False)
    new_value: Mapped[dict] = mapped_column(JSON, nullable=False)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)


class UserPreferences(Base):
    """
    Per-user preferences and UI customization.
    
    These settings are personal to each user and cannot
    override system-level settings.
    """
    __tablename__ = "user_preferences"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, 
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False
    )

    # UI Preferences
    theme: Mapped[str] = mapped_column(String(20), default="system", nullable=False)  # light, dark, system
    sidebar_collapsed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    default_chart_timeframe: Mapped[str] = mapped_column(String(10), default="1h", nullable=False)
    
    # Notification Preferences
    email_on_trade_execution: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    email_on_signal_generated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    email_on_risk_alert: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    email_on_emergency_shutdown: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Dashboard Preferences
    dashboard_widgets: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    favorite_symbols: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    favorite_strategies: Mapped[list] = mapped_column(JSON, default=list, nullable=False)

    # Display Settings
    decimal_places: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    date_format: Mapped[str] = mapped_column(String(20), default="YYYY-MM-DD", nullable=False)
    timezone: Mapped[str] = mapped_column(String(50), default="UTC", nullable=False)

    # Audit Fields
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, 
        onupdate=datetime.utcnow, 
        nullable=False
    )

    def to_dict(self) -> dict:
        """Convert preferences to dictionary."""
        return {
            "theme": self.theme,
            "sidebar_collapsed": self.sidebar_collapsed,
            "default_chart_timeframe": self.default_chart_timeframe,
            "email_on_trade_execution": self.email_on_trade_execution,
            "email_on_signal_generated": self.email_on_signal_generated,
            "email_on_risk_alert": self.email_on_risk_alert,
            "email_on_emergency_shutdown": self.email_on_emergency_shutdown,
            "dashboard_widgets": self.dashboard_widgets,
            "favorite_symbols": self.favorite_symbols,
            "favorite_strategies": self.favorite_strategies,
            "decimal_places": self.decimal_places,
            "date_format": self.date_format,
            "timezone": self.timezone,
        }
