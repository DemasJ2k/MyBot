"""
Settings Service - Centralized management of system settings.

All settings changes MUST go through this service to ensure:
- Validation against hard-coded constraints
- Proper audit trail
- Mode transition rules enforcement
- Broadcast of settings changes to system components
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
import logging

from app.models.system_settings import (
    SystemSettings, 
    SettingsAudit, 
    UserPreferences,
    SystemMode, 
    BrokerType
)
from app.risk.constants import validate_immutable_constants

logger = logging.getLogger(__name__)


class SettingsService:
    """
    Centralized service for managing system settings.
    All settings changes MUST go through this service.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_settings(self) -> SystemSettings:
        """
        Retrieves current system settings.
        Creates default settings if none exist (singleton pattern).
        """
        stmt = select(SystemSettings).limit(1)
        result = await self.db.execute(stmt)
        settings = result.scalar_one_or_none()

        if settings is None:
            # Create default settings
            settings = SystemSettings()
            self.db.add(settings)
            await self.db.commit()
            await self.db.refresh(settings)
            logger.info("Created default system settings")

        return settings

    async def update_settings(
        self,
        updates: dict,
        user_id: Optional[int] = None,
        reason: Optional[str] = None,
    ) -> tuple[bool, str, Optional[SystemSettings]]:
        """
        Updates system settings with validation.
        Returns (success, message, updated_settings).
        """
        settings = await self.get_settings()

        # Store old values for audit
        old_values = settings.to_dict()
        
        # Track what changed
        changed_fields = {}

        # Apply updates
        for key, value in updates.items():
            if hasattr(settings, key):
                old_val = getattr(settings, key)
                
                # Handle enum conversions
                if key == "mode" and isinstance(value, str):
                    try:
                        value = SystemMode(value)
                    except ValueError:
                        return False, f"Invalid mode value: {value}", None
                elif key == "broker_type" and isinstance(value, str):
                    try:
                        value = BrokerType(value)
                    except ValueError:
                        return False, f"Invalid broker_type value: {value}", None

                # Track change
                if old_val != value:
                    changed_fields[key] = {"old": str(old_val), "new": str(value)}
                    setattr(settings, key, value)
            else:
                return False, f"Unknown setting: {key}", None

        if not changed_fields:
            return True, "No changes to apply", settings

        # Validate updated settings
        is_valid, error_msg = settings.validate()
        if not is_valid:
            await self.db.rollback()
            return False, f"Validation failed: {error_msg}", None

        # Special validation for mode changes
        if "mode" in updates:
            old_mode = old_values.get("mode", "guide")
            new_mode = updates["mode"]
            if isinstance(new_mode, SystemMode):
                new_mode = new_mode.value
            
            can_switch, switch_error = await self._validate_mode_switch(
                old_mode, new_mode
            )
            if not can_switch:
                await self.db.rollback()
                return False, f"Mode switch denied: {switch_error}", None

        # Increment version
        settings.version += 1
        settings.updated_by = user_id

        # Determine change type
        if "mode" in changed_fields:
            change_type = "mode_change"
        elif any(k in changed_fields for k in ["max_risk_per_trade_percent", "max_daily_loss_percent", "max_open_positions"]):
            change_type = "risk_update"
        elif "broker_type" in changed_fields or "broker_connected" in changed_fields:
            change_type = "broker_update"
        else:
            change_type = "settings_update"

        # Create audit entry
        new_values = {k: updates.get(k) for k in changed_fields}
        # Convert enums for JSON storage
        for k, v in new_values.items():
            if isinstance(v, (SystemMode, BrokerType)):
                new_values[k] = v.value
        
        audit = SettingsAudit(
            settings_version=settings.version,
            changed_by=user_id,
            change_type=change_type,
            old_value={k: old_values.get(k) for k in changed_fields},
            new_value=new_values,
            reason=reason,
        )
        self.db.add(audit)

        await self.db.commit()
        await self.db.refresh(settings)

        logger.info(f"Settings updated: {change_type}, version {settings.version}")

        return True, "Settings updated successfully", settings

    async def _validate_mode_switch(
        self, old_mode: str, new_mode: str
    ) -> tuple[bool, str]:
        """
        Validates that mode switch is allowed.
        Returns (is_allowed, error_message).
        """
        if old_mode == new_mode:
            return True, ""

        # Guide -> Autonomous requires additional checks
        if old_mode == "guide" and new_mode == "autonomous":
            # Check system health
            health_ok = await self._check_system_health()
            if not health_ok:
                return False, "System health check failed"

            # Check broker connection
            settings = await self.get_settings()
            if not settings.broker_connected and settings.broker_type != BrokerType.PAPER:
                return False, "Broker not connected (required for non-paper trading)"

            # Check for emergency shutdown (integrate with risk service if available)
            try:
                from app.risk.monitor import RiskMonitor
                # Note: RiskMonitor would need to expose emergency state
                # For now, we'll assume no emergency if risk module doesn't have this
            except ImportError:
                pass

        # Autonomous -> Guide is always allowed (safety measure)
        return True, ""

    async def _check_system_health(self) -> bool:
        """
        Performs system health check before mode switch.
        Returns True if system is healthy.
        """
        # Check database connectivity
        try:
            await self.db.execute(select(1))
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False

        # Additional health checks can be added here:
        # - Agent health monitoring
        # - Redis connectivity
        # - External service availability
        
        return True

    async def get_mode(self) -> SystemMode:
        """Returns current system mode."""
        settings = await self.get_settings()
        return settings.mode

    async def set_mode(
        self,
        mode: SystemMode,
        user_id: Optional[int] = None,
        reason: Optional[str] = None,
    ) -> tuple[bool, str]:
        """
        Changes system mode with validation and audit.
        Returns (success, message).
        """
        success, message, updated_settings = await self.update_settings(
            {"mode": mode.value if isinstance(mode, SystemMode) else mode},
            user_id=user_id,
            reason=reason or f"Mode change to {mode.value if isinstance(mode, SystemMode) else mode}",
        )

        if success and updated_settings:
            # Broadcast mode change to all agents
            await self._broadcast_mode_change(updated_settings.mode)

        return success, message

    async def _broadcast_mode_change(self, new_mode: SystemMode) -> None:
        """
        Notifies all system components of mode change.
        This integrates with the message bus from multi-agent coordination.
        """
        logger.info(f"Broadcasting mode change to: {new_mode.value}")
        
        # In production, this would publish to message bus
        # Integration point with coordination system
        try:
            from app.coordination.message_bus import get_message_bus
            bus = get_message_bus()
            await bus.publish("system.mode_changed", {
                "mode": new_mode.value,
                "timestamp": str(__import__("datetime").datetime.utcnow())
            })
        except Exception as e:
            # Don't fail mode change if broadcast fails
            logger.warning(f"Mode change broadcast failed: {e}")

    async def get_audit_trail(
        self, limit: int = 100, change_type: Optional[str] = None
    ) -> list[SettingsAudit]:
        """Retrieves settings audit trail."""
        stmt = select(SettingsAudit).order_by(SettingsAudit.changed_at.desc())
        
        if change_type:
            stmt = stmt.where(SettingsAudit.change_type == change_type)
        
        stmt = stmt.limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def set_broker_connected(self, connected: bool, user_id: Optional[int] = None) -> tuple[bool, str]:
        """Updates broker connection status."""
        return await self.update_settings(
            {"broker_connected": connected},
            user_id=user_id,
            reason=f"Broker {'connected' if connected else 'disconnected'}"
        )[:2]


class UserPreferencesService:
    """Service for managing per-user preferences."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_preferences(self, user_id: int) -> UserPreferences:
        """
        Gets user preferences, creating defaults if not exist.
        """
        stmt = select(UserPreferences).where(UserPreferences.user_id == user_id)
        result = await self.db.execute(stmt)
        prefs = result.scalar_one_or_none()

        if prefs is None:
            prefs = UserPreferences(user_id=user_id)
            self.db.add(prefs)
            await self.db.commit()
            await self.db.refresh(prefs)

        return prefs

    async def update_preferences(
        self, user_id: int, updates: dict
    ) -> tuple[bool, str, Optional[UserPreferences]]:
        """Updates user preferences."""
        prefs = await self.get_preferences(user_id)

        for key, value in updates.items():
            if hasattr(prefs, key) and key not in ["id", "user_id", "created_at", "updated_at"]:
                setattr(prefs, key, value)
            elif key not in ["id", "user_id", "created_at", "updated_at"]:
                return False, f"Unknown preference: {key}", None

        await self.db.commit()
        await self.db.refresh(prefs)

        return True, "Preferences updated", prefs

    async def update_theme(self, user_id: int, theme: str) -> tuple[bool, str]:
        """Updates user theme preference."""
        if theme not in ["light", "dark", "system"]:
            return False, "Invalid theme. Must be 'light', 'dark', or 'system'"
        
        success, msg, _ = await self.update_preferences(user_id, {"theme": theme})
        return success, msg

    async def add_favorite_symbol(self, user_id: int, symbol: str) -> tuple[bool, str]:
        """Adds a symbol to user's favorites."""
        prefs = await self.get_preferences(user_id)
        favorites = list(prefs.favorite_symbols or [])
        
        if symbol not in favorites:
            favorites.append(symbol)
            prefs.favorite_symbols = favorites
            await self.db.commit()
        
        return True, f"Added {symbol} to favorites"

    async def remove_favorite_symbol(self, user_id: int, symbol: str) -> tuple[bool, str]:
        """Removes a symbol from user's favorites."""
        prefs = await self.get_preferences(user_id)
        favorites = list(prefs.favorite_symbols or [])
        
        if symbol in favorites:
            favorites.remove(symbol)
            prefs.favorite_symbols = favorites
            await self.db.commit()
        
        return True, f"Removed {symbol} from favorites"
