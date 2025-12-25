"""
Tests for Settings Module - Prompt 14.

Tests cover:
- System settings model validation
- Settings service operations
- Mode transitions (GUIDE <-> AUTONOMOUS)
- Settings API endpoints
- Audit trail functionality
- Hard-coded constraints enforcement
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch
from datetime import datetime

from app.models.system_settings import (
    SystemSettings,
    SettingsAudit,
    UserPreferences,
    SystemMode,
    BrokerType,
)
from app.services.settings_service import SettingsService, UserPreferencesService
from app.risk.constants import (
    MAX_RISK_PER_TRADE_PERCENT,
    MAX_DAILY_LOSS_PERCENT,
    EMERGENCY_DRAWDOWN_PERCENT,
    MAX_OPEN_POSITIONS,
    MAX_TRADES_PER_DAY,
    STRATEGY_AUTO_DISABLE_THRESHOLD,
    validate_immutable_constants,
)


# ============= Risk Constants Tests =============

class TestRiskConstants:
    """Tests for immutable risk constants."""

    def test_constants_within_safe_ranges(self):
        """Verify all constants are within acceptable safety ranges."""
        assert 0 < MAX_RISK_PER_TRADE_PERCENT <= 5.0
        assert 0 < MAX_DAILY_LOSS_PERCENT <= 10.0
        assert 0 < EMERGENCY_DRAWDOWN_PERCENT <= 25.0
        assert 1 <= MAX_OPEN_POSITIONS <= 50
        assert 1 <= MAX_TRADES_PER_DAY <= 100

    def test_validate_immutable_constants_passes(self):
        """validate_immutable_constants should not raise for valid constants."""
        # Should not raise any exception
        validate_immutable_constants()

    def test_constants_are_correct_values(self):
        """Verify expected constant values."""
        assert MAX_RISK_PER_TRADE_PERCENT == 2.0
        assert MAX_DAILY_LOSS_PERCENT == 5.0
        assert EMERGENCY_DRAWDOWN_PERCENT == 15.0
        assert MAX_OPEN_POSITIONS == 10
        assert MAX_TRADES_PER_DAY == 20


# ============= System Settings Model Tests =============

class TestSystemSettingsModel:
    """Tests for SystemSettings model validation."""

    def _create_settings(self, **kwargs) -> SystemSettings:
        """Helper to create settings with defaults."""
        defaults = {
            "mode": SystemMode.GUIDE,
            "broker_type": BrokerType.PAPER,
            "broker_connected": False,
            "data_provider": "twelvedata",
            "max_risk_per_trade_percent": 2.0,
            "max_daily_loss_percent": 5.0,
            "emergency_drawdown_percent": 15.0,
            "max_open_positions": 10,
            "max_trades_per_day": 20,
            "auto_disable_strategies": True,
            "strategy_disable_threshold": 5,
            "cancel_orders_on_mode_switch": True,
            "require_confirmation_for_autonomous": True,
            "health_check_interval_seconds": 30,
            "agent_timeout_seconds": 60,
            "email_notifications_enabled": False,
            "notification_email": None,
            "advanced_settings": {},
            "version": 1,
        }
        defaults.update(kwargs)
        return SystemSettings(**defaults)

    def test_default_settings_are_valid(self):
        """Default settings should pass validation."""
        settings = self._create_settings()
        is_valid, error = settings.validate()
        assert is_valid is True
        assert error == ""

    def test_mode_defaults_to_guide(self):
        """New settings should default to GUIDE mode."""
        settings = self._create_settings()
        assert settings.mode == SystemMode.GUIDE

    def test_broker_defaults_to_paper(self):
        """New settings should default to paper trading."""
        settings = self._create_settings()
        assert settings.broker_type == BrokerType.PAPER

    def test_validation_rejects_exceeding_max_risk(self):
        """Validation should reject risk exceeding hard limits."""
        settings = self._create_settings(
            max_risk_per_trade_percent=MAX_RISK_PER_TRADE_PERCENT + 0.1
        )
        is_valid, error = settings.validate()
        assert is_valid is False
        assert "max_risk_per_trade_percent" in error

    def test_validation_rejects_exceeding_max_daily_loss(self):
        """Validation should reject daily loss exceeding hard limits."""
        settings = self._create_settings(
            max_daily_loss_percent=MAX_DAILY_LOSS_PERCENT + 0.1
        )
        is_valid, error = settings.validate()
        assert is_valid is False
        assert "max_daily_loss_percent" in error

    def test_validation_rejects_exceeding_max_positions(self):
        """Validation should reject positions exceeding hard limits."""
        settings = self._create_settings(
            max_open_positions=MAX_OPEN_POSITIONS + 1
        )
        is_valid, error = settings.validate()
        assert is_valid is False
        assert "max_open_positions" in error

    def test_validation_rejects_zero_risk(self):
        """Validation should reject zero risk per trade."""
        settings = self._create_settings(
            max_risk_per_trade_percent=0
        )
        is_valid, error = settings.validate()
        assert is_valid is False
        assert "must be positive" in error

    def test_validation_rejects_negative_positions(self):
        """Validation should reject less than 1 position."""
        settings = self._create_settings(
            max_open_positions=0
        )
        is_valid, error = settings.validate()
        assert is_valid is False
        assert "must be at least 1" in error

    def test_validation_rejects_illogical_risk_config(self):
        """Daily loss should be >= risk per trade."""
        settings = self._create_settings(
            max_risk_per_trade_percent=2.0,
            max_daily_loss_percent=1.0  # Less than per-trade risk
        )
        is_valid, error = settings.validate()
        assert is_valid is False
        assert "should be >=" in error

    def test_to_dict_serialization(self):
        """to_dict should serialize settings correctly."""
        settings = self._create_settings(
            mode=SystemMode.AUTONOMOUS,
            broker_type=BrokerType.MT5
        )
        
        result = settings.to_dict()
        
        assert result["mode"] == "autonomous"
        assert result["broker_type"] == "mt5"
        assert "max_risk_per_trade_percent" in result
        assert "version" in result


# ============= Settings Service Tests =============

class TestSettingsService:
    """Tests for SettingsService."""

    @pytest_asyncio.fixture
    async def service(self, test_db):
        """Create settings service with test database."""
        return SettingsService(test_db)

    @pytest.mark.asyncio
    async def test_get_settings_creates_default(self, service):
        """get_settings should create default settings if none exist."""
        settings = await service.get_settings()
        
        assert settings is not None
        assert settings.mode == SystemMode.GUIDE
        assert settings.broker_type == BrokerType.PAPER
        assert settings.version == 1

    @pytest.mark.asyncio
    async def test_get_settings_returns_existing(self, service):
        """get_settings should return existing settings."""
        # First call creates
        settings1 = await service.get_settings()
        # Second call returns same
        settings2 = await service.get_settings()
        
        assert settings1.id == settings2.id

    @pytest.mark.asyncio
    async def test_update_settings_valid_change(self, service, test_user):
        """update_settings should accept valid changes."""
        success, message, settings = await service.update_settings(
            updates={"max_risk_per_trade_percent": 1.5},
            user_id=test_user.id,
            reason="Test update"
        )
        
        assert success is True
        assert settings.max_risk_per_trade_percent == 1.5
        assert settings.version == 2  # Incremented

    @pytest.mark.asyncio
    async def test_update_settings_rejects_invalid(self, service, test_user):
        """update_settings should reject invalid changes."""
        success, message, settings = await service.update_settings(
            updates={"max_risk_per_trade_percent": 10.0},  # Exceeds hard limit
            user_id=test_user.id,
        )
        
        assert success is False
        assert "cannot exceed" in message
        assert settings is None

    @pytest.mark.asyncio
    async def test_update_settings_rejects_unknown_field(self, service, test_user):
        """update_settings should reject unknown fields."""
        success, message, settings = await service.update_settings(
            updates={"unknown_field": "value"},
            user_id=test_user.id,
        )
        
        assert success is False
        assert "Unknown setting" in message

    @pytest.mark.asyncio
    async def test_update_creates_audit_entry(self, service, test_db, test_user):
        """update_settings should create audit entry."""
        await service.update_settings(
            updates={"max_open_positions": 5},
            user_id=test_user.id,
            reason="Reducing risk"
        )
        
        audits = await service.get_audit_trail(limit=10)
        
        assert len(audits) >= 1
        latest = audits[0]
        assert latest.changed_by == test_user.id
        assert latest.reason == "Reducing risk"
        assert "max_open_positions" in latest.new_value

    @pytest.mark.asyncio
    async def test_get_mode_returns_current(self, service):
        """get_mode should return current mode."""
        mode = await service.get_mode()
        assert mode == SystemMode.GUIDE

    @pytest.mark.asyncio
    async def test_set_mode_to_autonomous(self, service, test_user):
        """set_mode should change to autonomous when conditions met."""
        # First set broker as paper (always works)
        await service.update_settings(
            {"broker_type": "paper"},
            user_id=test_user.id
        )
        
        success, message = await service.set_mode(
            SystemMode.AUTONOMOUS,
            user_id=test_user.id,
            reason="Testing autonomous"
        )
        
        assert success is True
        mode = await service.get_mode()
        assert mode == SystemMode.AUTONOMOUS

    @pytest.mark.asyncio
    async def test_set_mode_back_to_guide(self, service, test_user):
        """set_mode should always allow switching to GUIDE."""
        # First go to autonomous
        await service.set_mode(SystemMode.AUTONOMOUS, user_id=test_user.id)
        
        # Then back to guide
        success, message = await service.set_mode(
            SystemMode.GUIDE,
            user_id=test_user.id,
            reason="Safety switch"
        )
        
        assert success is True
        mode = await service.get_mode()
        assert mode == SystemMode.GUIDE


# ============= Mode Transition Tests =============

class TestModeTransitions:
    """Tests for mode transition rules."""

    @pytest_asyncio.fixture
    async def service(self, test_db):
        return SettingsService(test_db)

    @pytest.mark.asyncio
    async def test_guide_to_autonomous_requires_health(self, service, test_user):
        """Guide -> Autonomous should check system health."""
        # Should pass with paper broker
        success, message = await service.set_mode(
            SystemMode.AUTONOMOUS,
            user_id=test_user.id
        )
        # With paper broker, should succeed
        assert success is True

    @pytest.mark.asyncio
    async def test_guide_to_autonomous_requires_broker_for_non_paper(self, service, test_user):
        """Guide -> Autonomous with non-paper broker requires connection."""
        # Set broker to MT5 but not connected
        await service.update_settings(
            {"broker_type": "mt5", "broker_connected": False},
            user_id=test_user.id
        )
        
        # Back to guide first
        await service.set_mode(SystemMode.GUIDE, user_id=test_user.id)
        
        # Now try autonomous with MT5
        success, message = await service.set_mode(
            SystemMode.AUTONOMOUS,
            user_id=test_user.id
        )
        
        assert success is False
        assert "Broker not connected" in message

    @pytest.mark.asyncio
    async def test_autonomous_to_guide_always_allowed(self, service, test_user):
        """Autonomous -> Guide should always be allowed (safety measure)."""
        # Go to autonomous first
        await service.set_mode(SystemMode.AUTONOMOUS, user_id=test_user.id)
        
        # Switch to guide should always work
        success, message = await service.set_mode(
            SystemMode.GUIDE,
            user_id=test_user.id
        )
        
        assert success is True


# ============= User Preferences Tests =============

class TestUserPreferencesService:
    """Tests for UserPreferencesService."""

    @pytest_asyncio.fixture
    async def service(self, test_db):
        return UserPreferencesService(test_db)

    @pytest.mark.asyncio
    async def test_get_preferences_creates_default(self, service, test_user):
        """get_preferences should create defaults for new user."""
        prefs = await service.get_preferences(test_user.id)
        
        assert prefs is not None
        assert prefs.user_id == test_user.id
        assert prefs.theme == "system"

    @pytest.mark.asyncio
    async def test_update_theme(self, service, test_user):
        """update_theme should change theme."""
        success, message = await service.update_theme(test_user.id, "dark")
        
        assert success is True
        prefs = await service.get_preferences(test_user.id)
        assert prefs.theme == "dark"

    @pytest.mark.asyncio
    async def test_update_theme_rejects_invalid(self, service, test_user):
        """update_theme should reject invalid theme."""
        success, message = await service.update_theme(test_user.id, "rainbow")
        
        assert success is False
        assert "Invalid theme" in message

    @pytest.mark.asyncio
    async def test_add_favorite_symbol(self, service, test_user):
        """add_favorite_symbol should add to list."""
        await service.add_favorite_symbol(test_user.id, "AAPL")
        await service.add_favorite_symbol(test_user.id, "MSFT")
        
        prefs = await service.get_preferences(test_user.id)
        assert "AAPL" in prefs.favorite_symbols
        assert "MSFT" in prefs.favorite_symbols

    @pytest.mark.asyncio
    async def test_remove_favorite_symbol(self, service, test_user):
        """remove_favorite_symbol should remove from list."""
        await service.add_favorite_symbol(test_user.id, "AAPL")
        await service.remove_favorite_symbol(test_user.id, "AAPL")
        
        prefs = await service.get_preferences(test_user.id)
        assert "AAPL" not in prefs.favorite_symbols


# ============= Settings Audit Tests =============

class TestSettingsAudit:
    """Tests for settings audit trail."""

    @pytest_asyncio.fixture
    async def service(self, test_db):
        return SettingsService(test_db)

    @pytest.mark.asyncio
    async def test_audit_trail_ordered_by_date(self, service, test_user):
        """Audit trail should be ordered newest first."""
        # Make several changes
        await service.update_settings({"max_open_positions": 5}, user_id=test_user.id)
        await service.update_settings({"max_open_positions": 6}, user_id=test_user.id)
        await service.update_settings({"max_open_positions": 7}, user_id=test_user.id)
        
        audits = await service.get_audit_trail(limit=10)
        
        assert len(audits) >= 3
        # Check ordering (newest first)
        for i in range(len(audits) - 1):
            assert audits[i].changed_at >= audits[i + 1].changed_at

    @pytest.mark.asyncio
    async def test_audit_captures_old_and_new_values(self, service, test_user):
        """Audit should capture both old and new values."""
        # Get initial settings
        initial = await service.get_settings()
        old_positions = initial.max_open_positions
        
        # Make change
        await service.update_settings(
            {"max_open_positions": old_positions - 1},
            user_id=test_user.id
        )
        
        audits = await service.get_audit_trail(limit=1)
        latest = audits[0]
        
        assert "max_open_positions" in latest.old_value
        assert "max_open_positions" in latest.new_value
        assert latest.new_value["max_open_positions"] == old_positions - 1

    @pytest.mark.asyncio
    async def test_audit_filter_by_change_type(self, service, test_user):
        """get_audit_trail should filter by change_type."""
        # Make a risk update
        await service.update_settings(
            {"max_risk_per_trade_percent": 1.5},
            user_id=test_user.id
        )
        
        # Make a mode change
        await service.set_mode(SystemMode.AUTONOMOUS, user_id=test_user.id)
        
        # Filter to mode changes only
        mode_audits = await service.get_audit_trail(limit=10, change_type="mode_change")
        
        for audit in mode_audits:
            assert audit.change_type == "mode_change"
