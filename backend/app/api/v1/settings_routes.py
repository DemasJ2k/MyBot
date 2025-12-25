"""
Settings API Routes.

Provides endpoints for:
- System settings management
- Mode switching (GUIDE / AUTONOMOUS)
- User preferences
- Settings audit trail
- Hard-coded constants reference
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.models.user import User
from app.models.system_settings import SystemMode, BrokerType
from app.services.settings_service import SettingsService, UserPreferencesService


router = APIRouter(prefix="/settings", tags=["Settings"])


# ============= Request/Response Models =============

class SettingsResponse(BaseModel):
    """Current system settings response."""
    mode: str
    broker_type: str
    broker_connected: bool
    data_provider: str
    max_risk_per_trade_percent: float
    max_daily_loss_percent: float
    emergency_drawdown_percent: float
    max_open_positions: int
    max_trades_per_day: int
    auto_disable_strategies: bool
    strategy_disable_threshold: int
    cancel_orders_on_mode_switch: bool
    require_confirmation_for_autonomous: bool
    health_check_interval_seconds: int
    agent_timeout_seconds: int
    email_notifications_enabled: bool
    notification_email: Optional[str]
    version: int

    class Config:
        from_attributes = True


class SettingsUpdateRequest(BaseModel):
    """Request to update system settings."""
    mode: Optional[str] = Field(None, description="System mode: 'guide' or 'autonomous'")
    broker_type: Optional[str] = Field(None, description="Broker type: 'paper', 'mt5', 'oanda', 'binance'")
    max_risk_per_trade_percent: Optional[float] = Field(None, gt=0, le=5.0)
    max_daily_loss_percent: Optional[float] = Field(None, gt=0, le=10.0)
    emergency_drawdown_percent: Optional[float] = Field(None, gt=0, le=25.0)
    max_open_positions: Optional[int] = Field(None, ge=1, le=50)
    max_trades_per_day: Optional[int] = Field(None, ge=1, le=100)
    auto_disable_strategies: Optional[bool] = None
    strategy_disable_threshold: Optional[int] = Field(None, ge=1, le=10)
    cancel_orders_on_mode_switch: Optional[bool] = None
    require_confirmation_for_autonomous: Optional[bool] = None
    health_check_interval_seconds: Optional[int] = Field(None, ge=10, le=300)
    agent_timeout_seconds: Optional[int] = Field(None, ge=10, le=300)
    email_notifications_enabled: Optional[bool] = None
    notification_email: Optional[str] = Field(None, max_length=255)
    reason: Optional[str] = Field(None, max_length=500, description="Reason for the change (for audit)")


class ModeChangeRequest(BaseModel):
    """Request to change system mode."""
    mode: str = Field(..., description="New mode: 'guide' or 'autonomous'")
    reason: Optional[str] = Field(None, max_length=500)


class ModeResponse(BaseModel):
    """Current mode response."""
    mode: str


class AuditEntryResponse(BaseModel):
    """Settings audit entry."""
    id: int
    settings_version: int
    changed_by: Optional[int]
    changed_at: str
    change_type: str
    old_value: dict
    new_value: dict
    reason: Optional[str]


class HardConstantsResponse(BaseModel):
    """Immutable hard-coded constants."""
    max_risk_per_trade_percent: float
    max_daily_loss_percent: float
    emergency_drawdown_percent: float
    max_open_positions: int
    max_trades_per_day: int
    max_trades_per_hour: int
    min_risk_reward_ratio: float
    max_position_size_percent: float
    strategy_auto_disable_threshold: int


class UserPreferencesResponse(BaseModel):
    """User preferences response."""
    theme: str
    sidebar_collapsed: bool
    default_chart_timeframe: str
    email_on_trade_execution: bool
    email_on_signal_generated: bool
    email_on_risk_alert: bool
    email_on_emergency_shutdown: bool
    dashboard_widgets: dict
    favorite_symbols: list
    favorite_strategies: list
    decimal_places: int
    date_format: str
    timezone: str


class UserPreferencesUpdateRequest(BaseModel):
    """Request to update user preferences."""
    theme: Optional[str] = Field(None, pattern="^(light|dark|system)$")
    sidebar_collapsed: Optional[bool] = None
    default_chart_timeframe: Optional[str] = Field(None, pattern="^(1m|5m|15m|30m|1h|4h|1d|1w)$")
    email_on_trade_execution: Optional[bool] = None
    email_on_signal_generated: Optional[bool] = None
    email_on_risk_alert: Optional[bool] = None
    email_on_emergency_shutdown: Optional[bool] = None
    dashboard_widgets: Optional[dict] = None
    favorite_symbols: Optional[list] = None
    favorite_strategies: Optional[list] = None
    decimal_places: Optional[int] = Field(None, ge=0, le=8)
    date_format: Optional[str] = Field(None, max_length=20)
    timezone: Optional[str] = Field(None, max_length=50)


# ============= System Settings Endpoints =============

@router.get("", response_model=SettingsResponse)
async def get_settings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get current system settings.
    
    Returns the complete system configuration including:
    - Operating mode (GUIDE/AUTONOMOUS)
    - Broker configuration
    - Risk limits (soft limits within hard caps)
    - Strategy management settings
    - Notification settings
    """
    service = SettingsService(db)
    settings = await service.get_settings()
    
    return SettingsResponse(
        mode=settings.mode.value,
        broker_type=settings.broker_type.value,
        broker_connected=settings.broker_connected,
        data_provider=settings.data_provider,
        max_risk_per_trade_percent=settings.max_risk_per_trade_percent,
        max_daily_loss_percent=settings.max_daily_loss_percent,
        emergency_drawdown_percent=settings.emergency_drawdown_percent,
        max_open_positions=settings.max_open_positions,
        max_trades_per_day=settings.max_trades_per_day,
        auto_disable_strategies=settings.auto_disable_strategies,
        strategy_disable_threshold=settings.strategy_disable_threshold,
        cancel_orders_on_mode_switch=settings.cancel_orders_on_mode_switch,
        require_confirmation_for_autonomous=settings.require_confirmation_for_autonomous,
        health_check_interval_seconds=settings.health_check_interval_seconds,
        agent_timeout_seconds=settings.agent_timeout_seconds,
        email_notifications_enabled=settings.email_notifications_enabled,
        notification_email=settings.notification_email,
        version=settings.version,
    )


@router.put("", response_model=SettingsResponse)
async def update_settings(
    request: SettingsUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update system settings.
    
    All updates are validated against hard-coded constraints.
    Invalid values will be rejected.
    All changes are recorded in the audit trail.
    """
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
        data_provider=updated_settings.data_provider,
        max_risk_per_trade_percent=updated_settings.max_risk_per_trade_percent,
        max_daily_loss_percent=updated_settings.max_daily_loss_percent,
        emergency_drawdown_percent=updated_settings.emergency_drawdown_percent,
        max_open_positions=updated_settings.max_open_positions,
        max_trades_per_day=updated_settings.max_trades_per_day,
        auto_disable_strategies=updated_settings.auto_disable_strategies,
        strategy_disable_threshold=updated_settings.strategy_disable_threshold,
        cancel_orders_on_mode_switch=updated_settings.cancel_orders_on_mode_switch,
        require_confirmation_for_autonomous=updated_settings.require_confirmation_for_autonomous,
        health_check_interval_seconds=updated_settings.health_check_interval_seconds,
        agent_timeout_seconds=updated_settings.agent_timeout_seconds,
        email_notifications_enabled=updated_settings.email_notifications_enabled,
        notification_email=updated_settings.notification_email,
        version=updated_settings.version,
    )


# ============= Mode Endpoints =============

@router.get("/mode", response_model=ModeResponse)
async def get_mode(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get current system mode.
    
    Returns either 'guide' or 'autonomous'.
    """
    service = SettingsService(db)
    mode = await service.get_mode()
    return ModeResponse(mode=mode.value)


@router.post("/mode", response_model=ModeResponse)
async def set_mode(
    request: ModeChangeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Change system mode.
    
    GUIDE mode:
    - AI generates signals and recommendations only
    - User must manually approve every action
    
    AUTONOMOUS mode:
    - AI can execute trades automatically
    - Requires: system health check, broker connection, no emergency shutdown
    
    Mode changes are always audited.
    """
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


# ============= Audit Endpoints =============

@router.get("/audit", response_model=list[AuditEntryResponse])
async def get_audit_trail(
    limit: int = 100,
    change_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get settings audit trail.
    
    Optional filters:
    - limit: Maximum entries to return (default 100)
    - change_type: Filter by type ('mode_change', 'risk_update', 'broker_update', 'settings_update')
    """
    service = SettingsService(db)
    audits = await service.get_audit_trail(limit=limit, change_type=change_type)

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


# ============= Constants Endpoint =============

@router.get("/constants", response_model=HardConstantsResponse)
async def get_hard_constants(
    current_user: User = Depends(get_current_user),
):
    """
    Get immutable hard-coded constants.
    
    These values CANNOT be modified by any user or system component.
    They represent the absolute maximum risk tolerance.
    Soft limits in settings must always be <= these values.
    """
    from app.risk.constants import (
        MAX_RISK_PER_TRADE_PERCENT,
        MAX_DAILY_LOSS_PERCENT,
        EMERGENCY_DRAWDOWN_PERCENT,
        MAX_OPEN_POSITIONS,
        MAX_TRADES_PER_DAY,
        MAX_TRADES_PER_HOUR,
        MIN_RISK_REWARD_RATIO,
        MAX_POSITION_SIZE_PERCENT,
        STRATEGY_AUTO_DISABLE_THRESHOLD,
    )

    return HardConstantsResponse(
        max_risk_per_trade_percent=MAX_RISK_PER_TRADE_PERCENT,
        max_daily_loss_percent=MAX_DAILY_LOSS_PERCENT,
        emergency_drawdown_percent=EMERGENCY_DRAWDOWN_PERCENT,
        max_open_positions=MAX_OPEN_POSITIONS,
        max_trades_per_day=MAX_TRADES_PER_DAY,
        max_trades_per_hour=MAX_TRADES_PER_HOUR,
        min_risk_reward_ratio=MIN_RISK_REWARD_RATIO,
        max_position_size_percent=MAX_POSITION_SIZE_PERCENT,
        strategy_auto_disable_threshold=STRATEGY_AUTO_DISABLE_THRESHOLD,
    )


# ============= User Preferences Endpoints =============

@router.get("/preferences", response_model=UserPreferencesResponse)
async def get_user_preferences(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get current user's preferences.
    
    Returns UI customization, notification settings, and display preferences.
    """
    service = UserPreferencesService(db)
    prefs = await service.get_preferences(current_user.id)
    
    return UserPreferencesResponse(
        theme=prefs.theme,
        sidebar_collapsed=prefs.sidebar_collapsed,
        default_chart_timeframe=prefs.default_chart_timeframe,
        email_on_trade_execution=prefs.email_on_trade_execution,
        email_on_signal_generated=prefs.email_on_signal_generated,
        email_on_risk_alert=prefs.email_on_risk_alert,
        email_on_emergency_shutdown=prefs.email_on_emergency_shutdown,
        dashboard_widgets=prefs.dashboard_widgets,
        favorite_symbols=prefs.favorite_symbols,
        favorite_strategies=prefs.favorite_strategies,
        decimal_places=prefs.decimal_places,
        date_format=prefs.date_format,
        timezone=prefs.timezone,
    )


@router.put("/preferences", response_model=UserPreferencesResponse)
async def update_user_preferences(
    request: UserPreferencesUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update current user's preferences.
    """
    service = UserPreferencesService(db)
    
    updates = request.model_dump(exclude_unset=True)
    
    success, message, prefs = await service.update_preferences(current_user.id, updates)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message,
        )

    return UserPreferencesResponse(
        theme=prefs.theme,
        sidebar_collapsed=prefs.sidebar_collapsed,
        default_chart_timeframe=prefs.default_chart_timeframe,
        email_on_trade_execution=prefs.email_on_trade_execution,
        email_on_signal_generated=prefs.email_on_signal_generated,
        email_on_risk_alert=prefs.email_on_risk_alert,
        email_on_emergency_shutdown=prefs.email_on_emergency_shutdown,
        dashboard_widgets=prefs.dashboard_widgets,
        favorite_symbols=prefs.favorite_symbols,
        favorite_strategies=prefs.favorite_strategies,
        decimal_places=prefs.decimal_places,
        date_format=prefs.date_format,
        timezone=prefs.timezone,
    )


@router.post("/preferences/favorites/symbols/{symbol}")
async def add_favorite_symbol(
    symbol: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add a symbol to user's favorites."""
    service = UserPreferencesService(db)
    success, message = await service.add_favorite_symbol(current_user.id, symbol.upper())
    
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)
    
    return {"message": message}


@router.delete("/preferences/favorites/symbols/{symbol}")
async def remove_favorite_symbol(
    symbol: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove a symbol from user's favorites."""
    service = UserPreferencesService(db)
    success, message = await service.remove_favorite_symbol(current_user.id, symbol.upper())
    
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)
    
    return {"message": message}
