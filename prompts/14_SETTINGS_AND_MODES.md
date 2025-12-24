# 14_SETTINGS_AND_MODES.md

## Context for Claude Opus 4.5

You are implementing the centralized settings and mode management system for Flowrex. This system controls ALL configurable behavior, enforces hard risk limits, manages GUIDE vs AUTONOMOUS mode switching, and maintains an audit trail of all settings changes.

**Prerequisites:**
- `09_RISK_ENGINE.md` has been completed (hard caps defined)
- `12_FRONTEND_CORE.md` and `13_UI_DASHBOARDS.md` completed (UI components available)
- Database models and migrations exist

**Critical Requirements:**
- Settings are THE SINGLE SOURCE OF TRUTH for system configuration
- Hard risk limits CANNOT be modified (immutable in code)
- Mode switching has explicit validation rules
- All settings changes are audited and versioned
- Unsafe settings combinations are rejected at validation layer
- Settings changes propagate deterministically to all components
- No race conditions in mode transitions

---

## System Architecture

### Settings Hierarchy

**Level 1: Hard-Coded Immutable Constants (HIGHEST AUTHORITY)**
- Defined in `backend/app/risk_engine/constants.py`
- Cannot be modified by any user or system component
- Violation = immediate system halt

**Level 2: System Settings (Database-Persisted)**
- Defined in `backend/app/models/system_settings.py`
- Can be modified within constraints defined by Level 1
- Requires validation before persistence
- All changes audited

**Level 3: User Preferences (Per-User)**
- Defined in `backend/app/models/user_preferences.py`
- UI customization, notifications, display settings
- Cannot override system settings

**Level 4: Strategy Configurations (Per-Strategy)**
- Defined in strategy.configuration JSON field
- Must respect risk limits from Level 1 and 2
- Validated before strategy activation

---

## Mode System Design

### Mode Definitions

**GUIDE Mode:**
- AI generates signals and recommendations
- NO automatic trade execution
- User must manually approve every action
- AI can run backtests and optimizations
- AI can disable strategies (safety measure)
- Risk engine still enforces all limits

**AUTONOMOUS Mode:**
- AI can execute trades automatically
- AI can enable/disable strategies
- AI can modify strategy parameters (within limits)
- All actions still respect hard caps
- Emergency shutdown overrides everything

### Mode Transition Rules

**Guide → Autonomous:**
- Requires: System health check pass
- Requires: No emergency shutdown active
- Requires: All strategies validated
- Requires: Broker connection verified
- Requires: User confirmation (cannot be bypassed)
- Action: Audit log entry created
- Action: All agents notified of mode change

**Autonomous → Guide:**
- Can happen: On user request
- Can happen: On emergency shutdown trigger
- Can happen: On system health degradation
- Action: All pending orders cancelled (optional, user-configurable)
- Action: All agents notified immediately
- Action: Audit log entry created

---

## Implementation

### 1. Hard-Coded Risk Constants

**File:** `backend/app/risk_engine/constants.py`

```python
"""
Immutable risk constants.
These values CANNOT be changed at runtime.
Any attempt to modify these values should be treated as a CRITICAL ERROR.
"""

# Maximum risk per single trade as percentage of account balance
MAX_RISK_PER_TRADE_PERCENT = 2.0

# Maximum daily loss as percentage of account balance
MAX_DAILY_LOSS_PERCENT = 5.0

# Emergency shutdown threshold (account drawdown)
EMERGENCY_DRAWDOWN_PERCENT = 15.0

# Maximum number of simultaneously open positions
MAX_OPEN_POSITIONS = 10

# Maximum trades per day
MAX_TRADES_PER_DAY = 20

# Maximum trades per hour (rate limiting)
MAX_TRADES_PER_HOUR = 10

# Minimum risk/reward ratio for any trade
MIN_RISK_REWARD_RATIO = 1.5

# Maximum position size as percentage of account balance
MAX_POSITION_SIZE_PERCENT = 10.0

# Strategy auto-disable threshold (consecutive losses)
STRATEGY_AUTO_DISABLE_THRESHOLD = 5


def validate_immutable_constants() -> None:
    """
    Validates that hard-coded constants are within acceptable ranges.
    Called on system startup.
    """
    assert 0 < MAX_RISK_PER_TRADE_PERCENT <= 5.0, "MAX_RISK_PER_TRADE_PERCENT out of acceptable range"
    assert 0 < MAX_DAILY_LOSS_PERCENT <= 10.0, "MAX_DAILY_LOSS_PERCENT out of acceptable range"
    assert 0 < EMERGENCY_DRAWDOWN_PERCENT <= 25.0, "EMERGENCY_DRAWDOWN_PERCENT out of acceptable range"
    assert 1 <= MAX_OPEN_POSITIONS <= 50, "MAX_OPEN_POSITIONS out of acceptable range"
    assert 1 <= MAX_TRADES_PER_DAY <= 100, "MAX_TRADES_PER_DAY out of acceptable range"
    assert 1.0 <= MIN_RISK_REWARD_RATIO <= 5.0, "MIN_RISK_REWARD_RATIO out of acceptable range"
    assert 0 < MAX_POSITION_SIZE_PERCENT <= 20.0, "MAX_POSITION_SIZE_PERCENT out of acceptable range"
    assert 1 <= STRATEGY_AUTO_DISABLE_THRESHOLD <= 10, "STRATEGY_AUTO_DISABLE_THRESHOLD out of acceptable range"
```

### 2. System Settings Model

**File:** `backend/app/models/system_settings.py`

```python
from sqlalchemy import String, Float, Integer, Boolean, JSON, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
import enum

from app.database import Base


class SystemMode(str, enum.Enum):
    GUIDE = "guide"
    AUTONOMOUS = "autonomous"


class BrokerType(str, enum.Enum):
    MT5 = "mt5"
    OANDA = "oanda"
    BINANCE = "binance"
    PAPER = "paper"


class SystemSettings(Base):
    __tablename__ = "system_settings"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Mode Configuration
    mode: Mapped[SystemMode] = mapped_column(SQLEnum(SystemMode), default=SystemMode.GUIDE, nullable=False)

    # Broker Configuration
    broker_type: Mapped[BrokerType] = mapped_column(SQLEnum(BrokerType), default=BrokerType.PAPER, nullable=False)
    broker_connected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Data Provider Configuration
    data_provider: Mapped[str] = mapped_column(String, default="twelvedata", nullable=False)

    # Risk Configuration (Soft Limits - must be <= hard limits)
    # These can be configured but cannot exceed hard-coded constants
    max_risk_per_trade_percent: Mapped[float] = mapped_column(Float, default=2.0, nullable=False)
    max_daily_loss_percent: Mapped[float] = mapped_column(Float, default=5.0, nullable=False)
    emergency_drawdown_percent: Mapped[float] = mapped_column(Float, default=15.0, nullable=False)
    max_open_positions: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    max_trades_per_day: Mapped[int] = mapped_column(Integer, default=20, nullable=False)

    # Strategy Management
    auto_disable_strategies: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    strategy_disable_threshold: Mapped[int] = mapped_column(Integer, default=5, nullable=False)

    # Mode Transition Behavior
    cancel_orders_on_mode_switch: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    require_confirmation_for_autonomous: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # System Health Monitoring
    health_check_interval_seconds: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    agent_timeout_seconds: Mapped[int] = mapped_column(Integer, default=60, nullable=False)

    # Notification Settings
    email_notifications_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notification_email: Mapped[str | None] = mapped_column(String, nullable=True)

    # Advanced Settings
    advanced_settings: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    # Audit Fields
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    updated_by: Mapped[int | None] = mapped_column(Integer, nullable=True)  # user_id

    def validate(self) -> tuple[bool, str]:
        """
        Validates settings against hard-coded constraints.
        Returns (is_valid, error_message).
        """
        from app.risk_engine.constants import (
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

        return True, ""


class SettingsAudit(Base):
    __tablename__ = "settings_audit"

    id: Mapped[int] = mapped_column(primary_key=True)
    settings_version: Mapped[int] = mapped_column(Integer, nullable=False)
    changed_by: Mapped[int | None] = mapped_column(Integer, nullable=True)  # user_id, None = system
    changed_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, nullable=False)
    change_type: Mapped[str] = mapped_column(String, nullable=False)  # mode_change, risk_update, etc.
    old_value: Mapped[dict] = mapped_column(JSON, nullable=False)
    new_value: Mapped[dict] = mapped_column(JSON, nullable=False)
    reason: Mapped[str | None] = mapped_column(String, nullable=True)
```

### 3. Settings Service

**File:** `backend/app/services/settings_service.py`

```python
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional

from app.models.system_settings import SystemSettings, SettingsAudit, SystemMode, BrokerType
from app.risk_engine.constants import validate_immutable_constants


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
        Creates default settings if none exist.
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
        old_values = {
            "mode": settings.mode.value,
            "max_risk_per_trade_percent": settings.max_risk_per_trade_percent,
            "max_daily_loss_percent": settings.max_daily_loss_percent,
            "emergency_drawdown_percent": settings.emergency_drawdown_percent,
            "max_open_positions": settings.max_open_positions,
            "max_trades_per_day": settings.max_trades_per_day,
        }

        # Apply updates
        for key, value in updates.items():
            if hasattr(settings, key):
                # Handle enum conversions
                if key == "mode" and isinstance(value, str):
                    value = SystemMode(value)
                elif key == "broker_type" and isinstance(value, str):
                    value = BrokerType(value)

                setattr(settings, key, value)
            else:
                return False, f"Unknown setting: {key}", None

        # Validate updated settings
        is_valid, error_msg = settings.validate()
        if not is_valid:
            await self.db.rollback()
            return False, f"Validation failed: {error_msg}", None

        # Special validation for mode changes
        if "mode" in updates:
            can_switch, switch_error = await self._validate_mode_switch(
                old_values["mode"], updates["mode"]
            )
            if not can_switch:
                await self.db.rollback()
                return False, f"Mode switch denied: {switch_error}", None

        # Increment version
        settings.version += 1
        settings.updated_by = user_id

        # Create audit entry
        audit = SettingsAudit(
            settings_version=settings.version,
            changed_by=user_id,
            change_type="settings_update",
            old_value=old_values,
            new_value={k: updates[k] for k in updates if k in old_values},
            reason=reason,
        )
        self.db.add(audit)

        await self.db.commit()
        await self.db.refresh(settings)

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
            if not settings.broker_connected:
                return False, "Broker not connected"

            # Check for emergency shutdown
            from app.services.risk_service import RiskService
            risk_service = RiskService(self.db)
            risk_state = await risk_service.get_current_state()
            if risk_state.emergency_shutdown:
                return False, "Emergency shutdown is active"

        return True, ""

    async def _check_system_health(self) -> bool:
        """
        Performs system health check before mode switch.
        Returns True if system is healthy.
        """
        # Check database connectivity
        try:
            await self.db.execute(select(1))
        except Exception:
            return False

        # Check agent health (if multi-agent system is running)
        # This would integrate with the agent health monitoring system
        # For now, return True
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
        success, message, _ = await self.update_settings(
            {"mode": mode.value},
            user_id=user_id,
            reason=reason or f"Mode change to {mode.value}",
        )

        if success:
            # Broadcast mode change to all agents
            await self._broadcast_mode_change(mode)

        return success, message

    async def _broadcast_mode_change(self, new_mode: SystemMode) -> None:
        """
        Notifies all system components of mode change.
        This integrates with the message bus from multi-agent coordination.
        """
        # In production, this would publish to message bus
        # For now, we'll add a log entry
        import logging
        logging.info(f"System mode changed to: {new_mode.value}")

    async def get_audit_trail(
        self, limit: int = 100
    ) -> list[SettingsAudit]:
        """Retrieves settings audit trail."""
        stmt = (
            select(SettingsAudit)
            .order_by(SettingsAudit.changed_at.desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
```

### 4. Settings API Routes

**File:** `backend/app/api/v1/settings_routes.py`

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from typing import Optional

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.models.user import User
from app.models.system_settings import SystemMode, BrokerType
from app.services.settings_service import SettingsService


router = APIRouter(prefix="/api/v1/settings", tags=["settings"])


class SettingsResponse(BaseModel):
    mode: str
    broker_type: str
    broker_connected: bool
    max_risk_per_trade_percent: float
    max_daily_loss_percent: float
    emergency_drawdown_percent: float
    max_open_positions: int
    max_trades_per_day: int
    auto_disable_strategies: bool
    strategy_disable_threshold: int
    cancel_orders_on_mode_switch: bool
    version: int

    class Config:
        from_attributes = True


class SettingsUpdateRequest(BaseModel):
    mode: Optional[str] = None
    broker_type: Optional[str] = None
    max_risk_per_trade_percent: Optional[float] = Field(None, gt=0, le=5.0)
    max_daily_loss_percent: Optional[float] = Field(None, gt=0, le=10.0)
    emergency_drawdown_percent: Optional[float] = Field(None, gt=0, le=25.0)
    max_open_positions: Optional[int] = Field(None, ge=1, le=50)
    max_trades_per_day: Optional[int] = Field(None, ge=1, le=100)
    auto_disable_strategies: Optional[bool] = None
    strategy_disable_threshold: Optional[int] = Field(None, ge=1, le=10)
    cancel_orders_on_mode_switch: Optional[bool] = None
    reason: Optional[str] = None


class ModeChangeRequest(BaseModel):
    mode: str
    reason: Optional[str] = None


class ModeResponse(BaseModel):
    mode: str


class AuditEntryResponse(BaseModel):
    id: int
    settings_version: int
    changed_by: Optional[int]
    changed_at: str
    change_type: str
    old_value: dict
    new_value: dict
    reason: Optional[str]


@router.get("", response_model=SettingsResponse)
async def get_settings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get current system settings."""
    service = SettingsService(db)
    settings = await service.get_settings()
    return SettingsResponse(
        mode=settings.mode.value,
        broker_type=settings.broker_type.value,
        broker_connected=settings.broker_connected,
        max_risk_per_trade_percent=settings.max_risk_per_trade_percent,
        max_daily_loss_percent=settings.max_daily_loss_percent,
        emergency_drawdown_percent=settings.emergency_drawdown_percent,
        max_open_positions=settings.max_open_positions,
        max_trades_per_day=settings.max_trades_per_day,
        auto_disable_strategies=settings.auto_disable_strategies,
        strategy_disable_threshold=settings.strategy_disable_threshold,
        cancel_orders_on_mode_switch=settings.cancel_orders_on_mode_switch,
        version=settings.version,
    )


@router.put("", response_model=SettingsResponse)
async def update_settings(
    request: SettingsUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update system settings."""
    service = SettingsService(db)

    # Build updates dict (only include provided fields)
    updates = request.model_dump(exclude_unset=True, exclude={"reason"})

    success, message, updated_settings = await service.update_settings(
        updates=updates,
        user_id=current_user.id,
        reason=request.reason,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message,
        )

    return SettingsResponse(
        mode=updated_settings.mode.value,
        broker_type=updated_settings.broker_type.value,
        broker_connected=updated_settings.broker_connected,
        max_risk_per_trade_percent=updated_settings.max_risk_per_trade_percent,
        max_daily_loss_percent=updated_settings.max_daily_loss_percent,
        emergency_drawdown_percent=updated_settings.emergency_drawdown_percent,
        max_open_positions=updated_settings.max_open_positions,
        max_trades_per_day=updated_settings.max_trades_per_day,
        auto_disable_strategies=updated_settings.auto_disable_strategies,
        strategy_disable_threshold=updated_settings.strategy_disable_threshold,
        cancel_orders_on_mode_switch=updated_settings.cancel_orders_on_mode_switch,
        version=updated_settings.version,
    )


@router.get("/mode", response_model=ModeResponse)
async def get_mode(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get current system mode."""
    service = SettingsService(db)
    mode = await service.get_mode()
    return ModeResponse(mode=mode.value)


@router.post("/mode", response_model=ModeResponse)
async def set_mode(
    request: ModeChangeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Change system mode."""
    service = SettingsService(db)

    try:
        mode = SystemMode(request.mode)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid mode: {request.mode}. Must be 'guide' or 'autonomous'",
        )

    success, message = await service.set_mode(
        mode=mode,
        user_id=current_user.id,
        reason=request.reason,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message,
        )

    return ModeResponse(mode=mode.value)


@router.get("/audit", response_model=list[AuditEntryResponse])
async def get_audit_trail(
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get settings audit trail."""
    service = SettingsService(db)
    audits = await service.get_audit_trail(limit=limit)

    return [
        AuditEntryResponse(
            id=audit.id,
            settings_version=audit.settings_version,
            changed_by=audit.changed_by,
            changed_at=audit.changed_at.isoformat(),
            change_type=audit.change_type,
            old_value=audit.old_value,
            new_value=audit.new_value,
            reason=audit.reason,
        )
        for audit in audits
    ]


@router.get("/constants")
async def get_hard_constants(
    current_user: User = Depends(get_current_user),
):
    """Get immutable hard-coded constants."""
    from app.risk_engine.constants import (
        MAX_RISK_PER_TRADE_PERCENT,
        MAX_DAILY_LOSS_PERCENT,
        EMERGENCY_DRAWDOWN_PERCENT,
        MAX_OPEN_POSITIONS,
        MAX_TRADES_PER_DAY,
        MIN_RISK_REWARD_RATIO,
        MAX_POSITION_SIZE_PERCENT,
        STRATEGY_AUTO_DISABLE_THRESHOLD,
    )

    return {
        "max_risk_per_trade_percent": MAX_RISK_PER_TRADE_PERCENT,
        "max_daily_loss_percent": MAX_DAILY_LOSS_PERCENT,
        "emergency_drawdown_percent": EMERGENCY_DRAWDOWN_PERCENT,
        "max_open_positions": MAX_OPEN_POSITIONS,
        "max_trades_per_day": MAX_TRADES_PER_DAY,
        "min_risk_reward_ratio": MIN_RISK_REWARD_RATIO,
        "max_position_size_percent": MAX_POSITION_SIZE_PERCENT,
        "strategy_auto_disable_threshold": STRATEGY_AUTO_DISABLE_THRESHOLD,
    }
```

### 5. Frontend Mode Provider Enhancement

**File:** `frontend/providers/ModeProvider.tsx` (Enhancement)

```typescript
'use client';

import { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { apiClient } from '@/services/api';

export type SystemMode = 'guide' | 'autonomous';

interface ModeContextType {
  mode: SystemMode;
  isLoading: boolean;
  setMode: (newMode: SystemMode, reason?: string) => Promise<void>;
  canSwitch: boolean;
  switchError: string | null;
}

const ModeContext = createContext<ModeContextType | undefined>(undefined);

export function ModeProvider({ children }: { children: ReactNode }) {
  const [mode, setModeState] = useState<SystemMode>('guide');
  const [isLoading, setIsLoading] = useState(true);
  const [canSwitch, setCanSwitch] = useState(true);
  const [switchError, setSwitchError] = useState<string | null>(null);

  // Load initial mode
  useEffect(() => {
    loadMode();
  }, []);

  const loadMode = async () => {
    try {
      const response = await apiClient.getSystemMode();
      setModeState(response.mode as SystemMode);
    } catch (error) {
      console.error('Failed to load system mode:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const setMode = async (newMode: SystemMode, reason?: string) => {
    setSwitchError(null);
    setIsLoading(true);

    try {
      await apiClient.setSystemMode(newMode, reason);
      setModeState(newMode);
      setCanSwitch(true);

      // Broadcast mode change event
      window.dispatchEvent(new CustomEvent('modeChanged', { detail: { mode: newMode } }));
    } catch (error: any) {
      const errorMessage = error.response?.data?.detail || 'Failed to change mode';
      setSwitchError(errorMessage);
      setCanSwitch(false);
      throw error;
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <ModeContext.Provider value={{ mode, isLoading, setMode, canSwitch, switchError }}>
      {children}
    </ModeContext.Provider>
  );
}

export function useMode() {
  const context = useContext(ModeContext);
  if (context === undefined) {
    throw new Error('useMode must be used within a ModeProvider');
  }
  return context;
}
```

### 6. Settings Management UI Component

**File:** `frontend/components/settings/SettingsManager.tsx`

```typescript
'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { apiClient } from '@/services/api';
import { useMode } from '@/providers/ModeProvider';
import { AlertTriangle, CheckCircle, Info } from 'lucide-react';

interface SystemSettings {
  mode: string;
  broker_type: string;
  broker_connected: boolean;
  max_risk_per_trade_percent: number;
  max_daily_loss_percent: number;
  emergency_drawdown_percent: number;
  max_open_positions: number;
  max_trades_per_day: number;
  auto_disable_strategies: boolean;
  strategy_disable_threshold: number;
  cancel_orders_on_mode_switch: boolean;
  version: number;
}

interface HardConstants {
  max_risk_per_trade_percent: number;
  max_daily_loss_percent: number;
  emergency_drawdown_percent: number;
  max_open_positions: number;
  max_trades_per_day: number;
  min_risk_reward_ratio: number;
  max_position_size_percent: number;
  strategy_auto_disable_threshold: number;
}

export default function SettingsManager() {
  const { mode, setMode } = useMode();
  const queryClient = useQueryClient();
  const [editedSettings, setEditedSettings] = useState<Partial<SystemSettings>>({});
  const [showConfirmation, setShowConfirmation] = useState(false);
  const [pendingMode, setPendingMode] = useState<'guide' | 'autonomous' | null>(null);

  const { data: settings } = useQuery({
    queryKey: ['systemSettings'],
    queryFn: () => apiClient.getSystemSettings(),
  });

  const { data: constants } = useQuery({
    queryKey: ['hardConstants'],
    queryFn: () => apiClient.getHardConstants(),
  });

  const updateSettingsMutation = useMutation({
    mutationFn: (updates: Partial<SystemSettings>) => apiClient.updateSystemSettings(updates),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['systemSettings'] });
      setEditedSettings({});
    },
  });

  const handleModeChange = async (newMode: 'guide' | 'autonomous') => {
    if (newMode === 'autonomous' && settings?.cancel_orders_on_mode_switch) {
      setPendingMode(newMode);
      setShowConfirmation(true);
    } else {
      await setMode(newMode);
    }
  };

  const confirmModeChange = async () => {
    if (pendingMode) {
      await setMode(pendingMode, 'User confirmed mode change');
      setPendingMode(null);
      setShowConfirmation(false);
    }
  };

  const cancelModeChange = () => {
    setPendingMode(null);
    setShowConfirmation(false);
  };

  const handleSettingChange = (key: keyof SystemSettings, value: any) => {
    setEditedSettings(prev => ({ ...prev, [key]: value }));
  };

  const saveSettings = async () => {
    await updateSettingsMutation.mutateAsync(editedSettings);
  };

  const resetSettings = () => {
    setEditedSettings({});
  };

  const getValue = (key: keyof SystemSettings) => {
    return editedSettings[key] !== undefined ? editedSettings[key] : settings?.[key];
  };

  const getMaxValue = (key: string): number => {
    const constantsMap: Record<string, keyof HardConstants> = {
      max_risk_per_trade_percent: 'max_risk_per_trade_percent',
      max_daily_loss_percent: 'max_daily_loss_percent',
      emergency_drawdown_percent: 'emergency_drawdown_percent',
      max_open_positions: 'max_open_positions',
      max_trades_per_day: 'max_trades_per_day',
      strategy_disable_threshold: 'strategy_auto_disable_threshold',
    };

    const constantKey = constantsMap[key];
    return constantKey && constants ? constants[constantKey] : 999;
  };

  return (
    <div className="space-y-6">
      {/* Mode Selection */}
      <Card>
        <h2 className="text-xl font-semibold mb-4 text-gray-900 dark:text-white">System Mode</h2>
        <div className="flex space-x-4">
          <Button
            variant={mode === 'guide' ? 'primary' : 'secondary'}
            onClick={() => handleModeChange('guide')}
            disabled={mode === 'guide'}
            className="flex-1"
          >
            GUIDE Mode
          </Button>
          <Button
            variant={mode === 'autonomous' ? 'primary' : 'secondary'}
            onClick={() => handleModeChange('autonomous')}
            disabled={mode === 'autonomous'}
            className="flex-1"
          >
            AUTONOMOUS Mode
          </Button>
        </div>
        <div className="mt-3 p-3 bg-blue-50 dark:bg-blue-900/20 rounded">
          <div className="flex items-start">
            <Info className="h-5 w-5 text-blue-600 dark:text-blue-400 mr-2 mt-0.5" />
            <div className="text-sm text-blue-800 dark:text-blue-300">
              <p className="font-semibold mb-1">Current Mode: {mode.toUpperCase()}</p>
              <p>
                {mode === 'guide'
                  ? 'AI provides recommendations only. Manual approval required for all trades.'
                  : 'AI can execute trades automatically within defined risk limits.'}
              </p>
            </div>
          </div>
        </div>
      </Card>

      {/* Risk Limits */}
      <Card>
        <h2 className="text-xl font-semibold mb-4 text-gray-900 dark:text-white">Risk Limits</h2>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Max Risk Per Trade (%)
            </label>
            <input
              type="number"
              step="0.1"
              min="0.1"
              max={getMaxValue('max_risk_per_trade_percent')}
              value={getValue('max_risk_per_trade_percent')}
              onChange={(e) => handleSettingChange('max_risk_per_trade_percent', parseFloat(e.target.value))}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
            />
            <p className="text-xs text-gray-500 mt-1">
              Hard limit: {constants?.max_risk_per_trade_percent}%
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Max Daily Loss (%)
            </label>
            <input
              type="number"
              step="0.1"
              min="0.1"
              max={getMaxValue('max_daily_loss_percent')}
              value={getValue('max_daily_loss_percent')}
              onChange={(e) => handleSettingChange('max_daily_loss_percent', parseFloat(e.target.value))}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
            />
            <p className="text-xs text-gray-500 mt-1">
              Hard limit: {constants?.max_daily_loss_percent}%
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Emergency Drawdown (%)
            </label>
            <input
              type="number"
              step="0.1"
              min="0.1"
              max={getMaxValue('emergency_drawdown_percent')}
              value={getValue('emergency_drawdown_percent')}
              onChange={(e) => handleSettingChange('emergency_drawdown_percent', parseFloat(e.target.value))}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
            />
            <p className="text-xs text-gray-500 mt-1">
              Triggers emergency shutdown. Hard limit: {constants?.emergency_drawdown_percent}%
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Max Open Positions
            </label>
            <input
              type="number"
              min="1"
              max={getMaxValue('max_open_positions')}
              value={getValue('max_open_positions')}
              onChange={(e) => handleSettingChange('max_open_positions', parseInt(e.target.value))}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
            />
            <p className="text-xs text-gray-500 mt-1">
              Hard limit: {constants?.max_open_positions}
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Max Trades Per Day
            </label>
            <input
              type="number"
              min="1"
              max={getMaxValue('max_trades_per_day')}
              value={getValue('max_trades_per_day')}
              onChange={(e) => handleSettingChange('max_trades_per_day', parseInt(e.target.value))}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
            />
            <p className="text-xs text-gray-500 mt-1">
              Hard limit: {constants?.max_trades_per_day}
            </p>
          </div>
        </div>
      </Card>

      {/* Strategy Management */}
      <Card>
        <h2 className="text-xl font-semibold mb-4 text-gray-900 dark:text-white">Strategy Management</h2>
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-700 dark:text-gray-300">Auto-Disable Strategies</p>
              <p className="text-xs text-gray-500">Automatically disable strategies after consecutive losses</p>
            </div>
            <label className="relative inline-flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={getValue('auto_disable_strategies') as boolean}
                onChange={(e) => handleSettingChange('auto_disable_strategies', e.target.checked)}
                className="sr-only peer"
              />
              <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 dark:peer-focus:ring-blue-800 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-blue-600"></div>
            </label>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Disable After Consecutive Losses
            </label>
            <input
              type="number"
              min="1"
              max={getMaxValue('strategy_disable_threshold')}
              value={getValue('strategy_disable_threshold')}
              onChange={(e) => handleSettingChange('strategy_disable_threshold', parseInt(e.target.value))}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
              disabled={!getValue('auto_disable_strategies')}
            />
          </div>
        </div>
      </Card>

      {/* Action Buttons */}
      {Object.keys(editedSettings).length > 0 && (
        <div className="flex space-x-3">
          <Button variant="primary" onClick={saveSettings} className="flex-1">
            <CheckCircle className="h-4 w-4 mr-2" />
            Save Changes
          </Button>
          <Button variant="secondary" onClick={resetSettings} className="flex-1">
            Reset
          </Button>
        </div>
      )}

      {/* Mode Change Confirmation Modal */}
      {showConfirmation && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <Card className="max-w-md w-full">
            <div className="flex items-start mb-4">
              <AlertTriangle className="h-6 w-6 text-amber-500 mr-3 mt-1" />
              <div>
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white">Confirm Mode Change</h3>
                <p className="text-sm text-gray-600 dark:text-gray-400 mt-2">
                  You are about to switch to AUTONOMOUS mode. All pending orders will be cancelled.
                  The AI will be able to execute trades automatically.
                </p>
                <p className="text-sm font-semibold text-amber-700 dark:text-amber-500 mt-3">
                  Are you sure you want to continue?
                </p>
              </div>
            </div>
            <div className="flex space-x-3">
              <Button variant="danger" onClick={confirmModeChange} className="flex-1">
                Yes, Switch to Autonomous
              </Button>
              <Button variant="secondary" onClick={cancelModeChange} className="flex-1">
                Cancel
              </Button>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}
```

---

## Database Migration

**File:** `backend/alembic/versions/YYYYMMDD_HHMMSS_add_system_settings.py`

```python
"""Add system settings and audit tables

Revision ID: add_system_settings
Revises: previous_revision
Create Date: YYYY-MM-DD HH:MM:SS
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = 'add_system_settings'
down_revision = 'previous_revision'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create system_settings table
    op.create_table(
        'system_settings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('mode', sa.Enum('guide', 'autonomous', name='systemmode'), nullable=False, server_default='guide'),
        sa.Column('broker_type', sa.Enum('mt5', 'oanda', 'binance', 'paper', name='brokertype'), nullable=False, server_default='paper'),
        sa.Column('broker_connected', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('data_provider', sa.String(), nullable=False, server_default='twelvedata'),
        sa.Column('max_risk_per_trade_percent', sa.Float(), nullable=False, server_default='2.0'),
        sa.Column('max_daily_loss_percent', sa.Float(), nullable=False, server_default='5.0'),
        sa.Column('emergency_drawdown_percent', sa.Float(), nullable=False, server_default='15.0'),
        sa.Column('max_open_positions', sa.Integer(), nullable=False, server_default='10'),
        sa.Column('max_trades_per_day', sa.Integer(), nullable=False, server_default='20'),
        sa.Column('auto_disable_strategies', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('strategy_disable_threshold', sa.Integer(), nullable=False, server_default='5'),
        sa.Column('cancel_orders_on_mode_switch', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('require_confirmation_for_autonomous', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('health_check_interval_seconds', sa.Integer(), nullable=False, server_default='30'),
        sa.Column('agent_timeout_seconds', sa.Integer(), nullable=False, server_default='60'),
        sa.Column('email_notifications_enabled', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('notification_email', sa.String(), nullable=True),
        sa.Column('advanced_settings', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_by', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Create settings_audit table
    op.create_table(
        'settings_audit',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('settings_version', sa.Integer(), nullable=False),
        sa.Column('changed_by', sa.Integer(), nullable=True),
        sa.Column('changed_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('change_type', sa.String(), nullable=False),
        sa.Column('old_value', sa.JSON(), nullable=False),
        sa.Column('new_value', sa.JSON(), nullable=False),
        sa.Column('reason', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes
    op.create_index('ix_settings_audit_changed_at', 'settings_audit', ['changed_at'])
    op.create_index('ix_settings_audit_changed_by', 'settings_audit', ['changed_by'])

    # Insert default settings row
    op.execute("""
        INSERT INTO system_settings (id) VALUES (1)
        ON CONFLICT (id) DO NOTHING
    """)


def downgrade() -> None:
    op.drop_table('settings_audit')
    op.drop_table('system_settings')
    op.execute('DROP TYPE IF EXISTS systemmode')
    op.execute('DROP TYPE IF EXISTS brokertype')
```

---

## Required Tests

### Unit Tests

**File:** `backend/tests/unit/test_settings_validation.py`

```python
import pytest
from app.models.system_settings import SystemSettings


def test_settings_validation_within_limits():
    """Test that valid settings pass validation."""
    settings = SystemSettings(
        max_risk_per_trade_percent=1.5,
        max_daily_loss_percent=4.0,
        emergency_drawdown_percent=12.0,
        max_open_positions=8,
        max_trades_per_day=15,
    )

    is_valid, error = settings.validate()
    assert is_valid
    assert error == ""


def test_settings_validation_exceeds_hard_cap():
    """Test that settings exceeding hard caps fail validation."""
    settings = SystemSettings(
        max_risk_per_trade_percent=5.0,  # Exceeds 2.0% hard cap
    )

    is_valid, error = settings.validate()
    assert not is_valid
    assert "cannot exceed" in error


def test_settings_validation_negative_values():
    """Test that negative values fail validation."""
    settings = SystemSettings(
        max_risk_per_trade_percent=-1.0,
    )

    is_valid, error = settings.validate()
    assert not is_valid
    assert "must be positive" in error


def test_settings_validation_logical_consistency():
    """Test that illogical settings combinations fail."""
    settings = SystemSettings(
        max_risk_per_trade_percent=3.0,
        max_daily_loss_percent=2.0,  # Less than per-trade risk
    )

    is_valid, error = settings.validate()
    assert not is_valid
    assert "should be >=" in error
```

**File:** `backend/tests/integration/test_mode_switching.py`

```python
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.settings_service import SettingsService
from app.models.system_settings import SystemMode


@pytest.mark.asyncio
async def test_mode_switch_guide_to_autonomous(db: AsyncSession):
    """Test successful mode switch from GUIDE to AUTONOMOUS."""
    service = SettingsService(db)

    # Start in GUIDE mode
    settings = await service.get_settings()
    assert settings.mode == SystemMode.GUIDE

    # Switch to AUTONOMOUS
    success, message = await service.set_mode(SystemMode.AUTONOMOUS)
    assert success

    # Verify mode changed
    updated_settings = await service.get_settings()
    assert updated_settings.mode == SystemMode.AUTONOMOUS


@pytest.mark.asyncio
async def test_mode_switch_creates_audit_entry(db: AsyncSession):
    """Test that mode switch creates audit entry."""
    service = SettingsService(db)

    # Switch mode
    await service.set_mode(SystemMode.AUTONOMOUS, reason="Test mode switch")

    # Check audit trail
    audits = await service.get_audit_trail(limit=1)
    assert len(audits) > 0
    assert audits[0].change_type == "settings_update"
    assert audits[0].reason == "Test mode switch"
```

---

## Validation Checklist

Before proceeding to the next prompt, verify ALL of the following:

### Settings System
- [ ] SystemSettings model created with all fields
- [ ] SettingsAudit model created
- [ ] Hard-coded constants defined in constants.py
- [ ] validate_immutable_constants() function implemented
- [ ] Settings validation method implemented
- [ ] Validation rejects values exceeding hard caps
- [ ] Validation rejects illogical combinations

### Settings Service
- [ ] SettingsService class implemented
- [ ] get_settings() method works
- [ ] update_settings() validates before persisting
- [ ] Mode switching validation implemented
- [ ] Audit trail creation on all changes
- [ ] Mode change broadcasts to system components

### API Routes
- [ ] GET /api/v1/settings endpoint implemented
- [ ] PUT /api/v1/settings endpoint implemented
- [ ] GET /api/v1/settings/mode endpoint implemented
- [ ] POST /api/v1/settings/mode endpoint implemented
- [ ] GET /api/v1/settings/audit endpoint implemented
- [ ] GET /api/v1/settings/constants endpoint implemented
- [ ] All endpoints require authentication

### Frontend Integration
- [ ] ModeProvider enhanced with error handling
- [ ] SettingsManager component implemented
- [ ] Mode confirmation dialog implemented
- [ ] Settings form validates against hard caps
- [ ] Real-time mode indicator updates
- [ ] Audit trail viewer implemented

### Database
- [ ] Migration created for system_settings table
- [ ] Migration created for settings_audit table
- [ ] Enums created for SystemMode and BrokerType
- [ ] Default settings row inserted
- [ ] Indexes created on audit table

### Testing
- [ ] Unit tests for settings validation
- [ ] Unit tests for hard cap enforcement
- [ ] Integration tests for mode switching
- [ ] Integration tests for audit trail
- [ ] Tests for concurrent settings updates
- [ ] Tests verify mode broadcast

---

## Hard Stop Criteria

DO NOT proceed to the next prompt if ANY of the following are true:

1. **Hard Caps Not Enforced:** Settings can exceed hard-coded constants
2. **No Validation:** Settings can be saved without validation
3. **No Audit Trail:** Settings changes are not logged
4. **Mode Switch Bypass:** Can switch to AUTONOMOUS without checks
5. **Race Conditions:** Concurrent updates cause data corruption
6. **No Broadcasting:** Mode changes don't propagate to components
7. **Frontend Mismatch:** UI allows values exceeding backend limits
8. **Database Migration Fails:** Migration does not run successfully
9. **Test Failures:** Any test in test suite fails
10. **API Authentication Bypass:** Settings endpoints accessible without auth

---

## Next Prompt

After completing this prompt and passing ALL validation checks, proceed to:

**15_TESTING_AND_VALIDATION.md** - Comprehensive testing strategy, test pyramid, coverage requirements, and CI/CD integration.
