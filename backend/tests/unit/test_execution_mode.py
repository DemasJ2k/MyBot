"""
Tests for Execution Mode Module - Prompt 16.

Tests cover:
- ExecutionMode enum validation
- SimulationAccount model operations
- SimulatedBrokerAdapter functionality
- ExecutionModeService operations
- Mode transitions (SIMULATION <-> PAPER <-> LIVE)
- Safety checks for live trading
- Audit trail functionality
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from decimal import Decimal
from datetime import datetime

from app.models.execution_mode import (
    ExecutionMode,
    SimulationAccount,
    ExecutionModeAudit,
    SimulationPosition,
)
from app.services.execution_mode_service import (
    ExecutionModeService,
    ExecutionModeError,
    LiveModeConfirmationRequired,
    PasswordVerificationRequired,
)
from app.execution.simulated_adapter import SimulatedBrokerAdapter
from app.execution.base_broker import OrderRequest, BrokerOrderResult


# ============= ExecutionMode Enum Tests =============

class TestExecutionModeEnum:
    """Tests for ExecutionMode enumeration."""

    def test_simulation_is_default(self):
        """SIMULATION should be the safest and default mode."""
        assert ExecutionMode.SIMULATION.value == "simulation"

    def test_all_modes_defined(self):
        """All three execution modes should be defined."""
        modes = [m.value for m in ExecutionMode]
        assert "simulation" in modes
        assert "paper" in modes
        assert "live" in modes
        assert len(modes) == 3

    def test_mode_string_conversion(self):
        """Modes should convert to/from strings correctly."""
        assert ExecutionMode("simulation") == ExecutionMode.SIMULATION
        assert ExecutionMode("paper") == ExecutionMode.PAPER
        assert ExecutionMode("live") == ExecutionMode.LIVE

    def test_invalid_mode_raises_error(self):
        """Invalid mode string should raise ValueError."""
        with pytest.raises(ValueError):
            ExecutionMode("invalid")


# ============= SimulationAccount Model Tests =============

class TestSimulationAccountModel:
    """Tests for SimulationAccount model."""

    def _create_account(self, **kwargs) -> SimulationAccount:
        """Helper to create simulation account with defaults."""
        defaults = {
            "user_id": 1,
            "balance": 10000.0,
            "equity": 10000.0,
            "margin_used": 0.0,
            "margin_available": 10000.0,
            "initial_balance": 10000.0,
            "currency": "USD",
            "slippage_pips": 0.5,
            "commission_per_lot": 7.0,
            "latency_ms": 100,
            "fill_probability": 0.98,
            "total_trades": 0,
            "winning_trades": 0,
            "total_pnl": 0.0,
        }
        defaults.update(kwargs)
        return SimulationAccount(**defaults)

    def test_default_balance(self):
        """Default balance should be $10,000."""
        account = self._create_account()
        assert account.balance == 10000.0
        assert account.initial_balance == 10000.0

    def test_reset_restores_initial_balance(self):
        """Reset should restore account to initial state."""
        account = self._create_account(
            balance=5000.0,
            equity=5200.0,
            margin_used=500.0,
            total_trades=10,
            winning_trades=6,
            total_pnl=200.0,
        )
        
        account.reset()
        
        assert account.balance == account.initial_balance
        assert account.equity == account.initial_balance
        assert account.margin_used == 0.0
        assert account.total_trades == 0
        assert account.winning_trades == 0
        assert account.total_pnl == 0.0
        assert account.last_reset_at is not None

    def test_record_trade_winning(self):
        """Recording a winning trade should update statistics."""
        account = self._create_account()
        
        account.record_trade(pnl=100.0, is_winner=True)
        
        assert account.balance == 10100.0
        assert account.total_pnl == 100.0
        assert account.total_trades == 1
        assert account.winning_trades == 1

    def test_record_trade_losing(self):
        """Recording a losing trade should update statistics."""
        account = self._create_account()
        
        account.record_trade(pnl=-50.0, is_winner=False)
        
        assert account.balance == 9950.0
        assert account.total_pnl == -50.0
        assert account.total_trades == 1
        assert account.winning_trades == 0

    def test_win_rate_calculation(self):
        """Win rate should be calculated correctly."""
        account = self._create_account(
            total_trades=10,
            winning_trades=7,
        )
        
        assert account.win_rate == 70.0

    def test_win_rate_zero_trades(self):
        """Win rate with zero trades should be 0."""
        account = self._create_account()
        assert account.win_rate == 0.0

    def test_update_equity(self):
        """Update equity should calculate from unrealized P&L."""
        account = self._create_account(balance=10000.0, margin_used=500.0)
        
        account.update_equity(unrealized_pnl=200.0)
        
        assert account.equity == 10200.0
        assert account.margin_available == 9700.0  # equity - margin_used


# ============= SimulationPosition Model Tests =============

class TestSimulationPositionModel:
    """Tests for SimulationPosition model."""

    def _create_position(self, **kwargs) -> SimulationPosition:
        """Helper to create simulation position."""
        defaults = {
            "user_id": 1,
            "simulation_account_id": 1,
            "symbol": "EURUSD",
            "side": "long",
            "quantity": 1.0,
            "entry_price": 1.1000,
            "current_price": 1.1000,
            "stop_loss": 1.0950,
            "take_profit": 1.1100,
            "margin_required": 1100.0,
            "order_id": "SIM-TEST001",
        }
        defaults.update(kwargs)
        return SimulationPosition(**defaults)

    def test_update_price_long_profit(self):
        """Long position should show profit when price increases."""
        position = self._create_position(
            side="long",
            entry_price=1.1000,
            current_price=1.1000,
        )
        
        position.update_price(1.1050)  # 50 pips up
        
        assert position.current_price == 1.1050
        assert position.unrealized_pnl > 0

    def test_update_price_long_loss(self):
        """Long position should show loss when price decreases."""
        position = self._create_position(
            side="long",
            entry_price=1.1000,
            current_price=1.1000,
        )
        
        position.update_price(1.0950)  # 50 pips down
        
        assert position.current_price == 1.0950
        assert position.unrealized_pnl < 0

    def test_update_price_short_profit(self):
        """Short position should show profit when price decreases."""
        position = self._create_position(
            side="short",
            entry_price=1.1000,
            current_price=1.1000,
        )
        
        position.update_price(1.0950)  # 50 pips down
        
        assert position.unrealized_pnl > 0

    def test_check_stop_loss_long(self):
        """Stop loss should trigger for long position."""
        position = self._create_position(
            side="long",
            stop_loss=1.0950,
            current_price=1.0940,  # Below stop loss
        )
        
        assert position.check_stop_loss() is True

    def test_check_stop_loss_not_triggered(self):
        """Stop loss should not trigger when price is favorable."""
        position = self._create_position(
            side="long",
            stop_loss=1.0950,
            current_price=1.1050,  # Above stop loss
        )
        
        assert position.check_stop_loss() is False

    def test_check_take_profit_long(self):
        """Take profit should trigger for long position."""
        position = self._create_position(
            side="long",
            take_profit=1.1100,
            current_price=1.1110,  # Above take profit
        )
        
        assert position.check_take_profit() is True

    def test_no_stop_loss_returns_false(self):
        """No stop loss set should return False."""
        position = self._create_position(stop_loss=None)
        assert position.check_stop_loss() is False


# ============= SimulatedBrokerAdapter Tests =============

class TestSimulatedBrokerAdapter:
    """Tests for SimulatedBrokerAdapter."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        return AsyncMock()

    @pytest.fixture
    def mock_account(self):
        """Create mock simulation account."""
        account = MagicMock(spec=SimulationAccount)
        account.id = 1
        account.user_id = 1
        account.balance = 10000.0
        account.equity = 10000.0
        account.margin_used = 0.0
        account.margin_available = 10000.0
        account.slippage_pips = 0.5
        account.commission_per_lot = 7.0
        account.latency_ms = 0  # No latency for tests
        account.fill_probability = 1.0  # Always fill for tests
        account.currency = "USD"  # Add currency for BrokerAccountInfo
        return account

    @pytest.fixture
    def adapter(self, mock_db, mock_account):
        """Create simulated broker adapter."""
        return SimulatedBrokerAdapter(
            db_session=mock_db,
            user_id=1,
            simulation_account=mock_account,
        )

    @pytest.mark.asyncio
    async def test_connect_success(self, adapter):
        """Connect should succeed for simulation."""
        result = await adapter.connect()
        assert result is True
        assert adapter.is_connected is True

    @pytest.mark.asyncio
    async def test_disconnect(self, adapter):
        """Disconnect should update connection state."""
        await adapter.connect()
        await adapter.disconnect()
        assert adapter.is_connected is False

    def test_set_price(self, adapter):
        """Setting price should store bid/ask."""
        adapter.set_price("EURUSD", Decimal("1.0995"), Decimal("1.1005"))
        
        bid, ask = adapter._prices["EURUSD"]
        assert bid == Decimal("1.0995")
        assert ask == Decimal("1.1005")

    def test_set_mid_price(self, adapter):
        """Setting mid price should calculate bid/ask with spread."""
        adapter.set_mid_price("EURUSD", Decimal("1.1000"), spread_pips=Decimal("2"))
        
        bid, ask = adapter._prices["EURUSD"]
        # Spread of 2 pips = 0.0002, so half spread = 0.0001
        assert bid < Decimal("1.1000")
        assert ask > Decimal("1.1000")

    @pytest.mark.asyncio
    async def test_get_account_info(self, adapter, mock_account):
        """Get account info should return current state."""
        await adapter.connect()
        info = await adapter.get_account_info()
        
        assert info.balance == Decimal("10000.0")
        assert info.equity == Decimal("10000.0")
        assert info.currency == "USD"


# ============= ExecutionModeService Tests =============

class TestExecutionModeService:
    """Tests for ExecutionModeService."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        db = AsyncMock()
        db.execute = AsyncMock()
        db.flush = AsyncMock()
        db.add = MagicMock()
        return db

    @pytest.fixture
    def service(self, mock_db):
        """Create execution mode service."""
        return ExecutionModeService(mock_db)

    @pytest.mark.asyncio
    async def test_get_current_mode_default(self, service, mock_db):
        """Default mode should be SIMULATION."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result
        
        mode = await service.get_current_mode()
        
        assert mode == ExecutionMode.SIMULATION

    @pytest.mark.asyncio
    async def test_get_current_mode_from_settings(self, service, mock_db):
        """Mode should be read from settings."""
        mock_settings = MagicMock()
        mock_settings.execution_mode = "paper"
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_settings
        mock_db.execute.return_value = mock_result
        
        mode = await service.get_current_mode()
        
        assert mode == ExecutionMode.PAPER

    @pytest.mark.asyncio
    async def test_change_mode_to_simulation(self, service, mock_db):
        """Changing to SIMULATION should not require confirmation."""
        mock_settings = MagicMock()
        mock_settings.execution_mode = "paper"
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_settings
        mock_db.execute.return_value = mock_result
        
        new_mode = await service.change_mode(
            user_id=1,
            new_mode=ExecutionMode.SIMULATION,
        )
        
        assert new_mode == ExecutionMode.SIMULATION

    @pytest.mark.asyncio
    async def test_change_mode_to_live_requires_password(self, service, mock_db):
        """Changing to LIVE should require password verification."""
        mock_settings = MagicMock()
        mock_settings.execution_mode = "simulation"
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_settings
        mock_db.execute.return_value = mock_result
        
        with pytest.raises(PasswordVerificationRequired):
            await service.change_mode(
                user_id=1,
                new_mode=ExecutionMode.LIVE,
                password_verified=False,
            )

    @pytest.mark.asyncio
    async def test_change_mode_to_live_requires_confirmation(self, service, mock_db):
        """Changing to LIVE should require explicit confirmation."""
        mock_settings = MagicMock()
        mock_settings.execution_mode = "simulation"
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_settings
        mock_db.execute.return_value = mock_result
        
        with pytest.raises(LiveModeConfirmationRequired):
            await service.change_mode(
                user_id=1,
                new_mode=ExecutionMode.LIVE,
                password_verified=True,
                confirmed=False,
            )

    @pytest.mark.asyncio
    async def test_change_mode_to_live_requires_reason(self, service, mock_db):
        """Changing to LIVE should require a reason."""
        mock_settings = MagicMock()
        mock_settings.execution_mode = "simulation"
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_settings
        mock_db.execute.return_value = mock_result
        
        with pytest.raises(ExecutionModeError) as exc_info:
            await service.change_mode(
                user_id=1,
                new_mode=ExecutionMode.LIVE,
                password_verified=True,
                confirmed=True,
                reason=None,
            )
        
        assert "reason is required" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_change_mode_to_live_success(self, service, mock_db):
        """Changing to LIVE with all requirements should succeed."""
        mock_settings = MagicMock()
        mock_settings.execution_mode = "simulation"
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_settings
        mock_db.execute.return_value = mock_result
        
        new_mode = await service.change_mode(
            user_id=1,
            new_mode=ExecutionMode.LIVE,
            password_verified=True,
            confirmed=True,
            reason="Starting live trading after testing",
            ip_address="127.0.0.1",
        )
        
        assert new_mode == ExecutionMode.LIVE
        # Verify audit was created
        mock_db.add.assert_called()

    @pytest.mark.asyncio
    async def test_same_mode_no_change(self, service, mock_db):
        """Changing to same mode should return current mode."""
        mock_settings = MagicMock()
        mock_settings.execution_mode = "simulation"
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_settings
        mock_db.execute.return_value = mock_result
        
        result = await service.change_mode(
            user_id=1,
            new_mode=ExecutionMode.SIMULATION,
        )
        
        assert result == ExecutionMode.SIMULATION

    @pytest.mark.asyncio
    async def test_is_live_trading_enabled(self, service, mock_db):
        """is_live_trading_enabled should return correct status."""
        mock_settings = MagicMock()
        mock_settings.execution_mode = "live"
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_settings
        mock_db.execute.return_value = mock_result
        
        result = await service.is_live_trading_enabled()
        
        assert result is True

    @pytest.mark.asyncio
    async def test_is_simulation_mode(self, service, mock_db):
        """is_simulation_mode should return correct status."""
        mock_settings = MagicMock()
        mock_settings.execution_mode = "simulation"
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_settings
        mock_db.execute.return_value = mock_result
        
        result = await service.is_simulation_mode()
        
        assert result is True


# ============= Safety Checks Tests =============

class TestSafetyChecks:
    """Tests for execution mode safety mechanisms."""

    def test_simulation_is_safest_mode(self):
        """SIMULATION should be the safest mode (no real money)."""
        # Verify SIMULATION is first in enum (default)
        modes = list(ExecutionMode)
        assert modes[0] == ExecutionMode.SIMULATION

    def test_live_mode_value_is_explicit(self):
        """LIVE mode value should be explicit and clear."""
        assert ExecutionMode.LIVE.value == "live"

    @pytest.mark.asyncio
    async def test_validate_mode_for_action(self):
        """validate_mode_for_action should restrict actions by mode."""
        mock_db = AsyncMock()
        mock_settings = MagicMock()
        mock_settings.execution_mode = "simulation"
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_settings
        mock_db.execute.return_value = mock_result
        
        service = ExecutionModeService(mock_db)
        
        # Should pass for simulation
        await service.validate_mode_for_action(
            required_modes=[ExecutionMode.SIMULATION, ExecutionMode.PAPER],
            action_description="Test action",
        )
        
        # Should fail for live-only action
        with pytest.raises(ExecutionModeError):
            await service.validate_mode_for_action(
                required_modes=[ExecutionMode.LIVE],
                action_description="Live-only action",
            )


# ============= Audit Trail Tests =============

class TestAuditTrail:
    """Tests for execution mode audit functionality."""

    def test_audit_model_captures_context(self):
        """ExecutionModeAudit should capture full context."""
        audit = ExecutionModeAudit(
            user_id=1,
            old_mode="simulation",
            new_mode="live",
            reason="Starting live trading",
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
            confirmation_required=True,
            password_verified=True,
            had_open_positions=False,
            positions_cancelled=0,
        )
        
        assert audit.user_id == 1
        assert audit.old_mode == "simulation"
        assert audit.new_mode == "live"
        assert audit.reason == "Starting live trading"
        assert audit.ip_address == "192.168.1.1"
        assert audit.confirmation_required is True
        assert audit.password_verified is True


# ============= Integration with System Settings Tests =============

class TestSystemSettingsIntegration:
    """Tests for execution mode integration with system settings."""

    def test_execution_mode_field_exists(self):
        """SystemSettings should have execution_mode field."""
        from app.models.system_settings import SystemSettings
        
        # Verify the field is mapped
        assert hasattr(SystemSettings, 'execution_mode')
