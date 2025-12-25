"""Risk Engine unit tests."""

import pytest
from datetime import datetime
from app.risk.validator import RiskValidator
from app.risk.monitor import RiskMonitor
from app.risk.constants import (
    MAX_RISK_PER_TRADE_PERCENT,
    MAX_DAILY_LOSS_PERCENT,
    EMERGENCY_DRAWDOWN_PERCENT,
    MAX_OPEN_POSITIONS,
    MAX_TRADES_PER_DAY,
    MAX_TRADES_PER_HOUR,
    MAX_POSITION_SIZE_LOTS,
    MIN_RISK_REWARD_RATIO,
)
from app.models.signal import Signal, SignalType, SignalStatus
from app.models.position import Position, PositionStatus, PositionSide
from app.models.risk import AccountRiskState, StrategyRiskBudget


@pytest.mark.asyncio
class TestRiskConstants:
    """Test that hard risk constants are defined correctly."""

    async def test_hard_limits_immutable(self):
        """Verify hard limits are defined correctly."""
        assert MAX_RISK_PER_TRADE_PERCENT == 2.0
        assert MAX_DAILY_LOSS_PERCENT == 5.0
        assert EMERGENCY_DRAWDOWN_PERCENT == 15.0
        assert MAX_OPEN_POSITIONS == 10
        assert MAX_TRADES_PER_DAY == 20
        assert MAX_TRADES_PER_HOUR == 5
        assert MAX_POSITION_SIZE_LOTS == 1.0
        assert MIN_RISK_REWARD_RATIO == 1.5


@pytest.mark.asyncio
class TestRiskValidator:
    """Test risk validator functionality."""

    async def test_validate_trade_approved(self, test_db, test_user):
        """Test that a valid trade is approved."""
        validator = RiskValidator(db=test_db)

        signal = Signal(
            user_id=test_user.id,
            strategy_name="NBB",
            symbol="EURUSD",
            signal_type=SignalType.LONG,
            status=SignalStatus.PENDING,
            entry_price=1.1000,
            stop_loss=1.0950,
            take_profit=1.1150,  # 3:1 R:R
            risk_percent=2.0,
            timeframe="1h",
            confidence=75.0,
            signal_time=datetime.utcnow()
        )

        test_db.add(signal)
        await test_db.commit()
        await test_db.refresh(signal)

        approved, reason, metrics = await validator.validate_trade(
            signal=signal,
            account_balance=10000.0,
            peak_balance=10000.0
        )

        assert approved is True
        assert reason is None
        assert "checks_performed" in metrics

    async def test_validate_trade_emergency_drawdown(self, test_db, test_user):
        """Test that emergency drawdown triggers rejection."""
        validator = RiskValidator(db=test_db)

        signal = Signal(
            user_id=test_user.id,
            strategy_name="NBB",
            symbol="EURUSD",
            signal_type=SignalType.LONG,
            status=SignalStatus.PENDING,
            entry_price=1.1000,
            stop_loss=1.0950,
            take_profit=1.1150,
            risk_percent=2.0,
            timeframe="1h",
            confidence=75.0,
            signal_time=datetime.utcnow()
        )

        test_db.add(signal)
        await test_db.commit()
        await test_db.refresh(signal)

        # Account balance is 8500, peak is 10000 = 15% drawdown
        approved, reason, metrics = await validator.validate_trade(
            signal=signal,
            account_balance=8500.0,
            peak_balance=10000.0
        )

        assert approved is False
        assert "Emergency drawdown" in reason

    async def test_risk_reward_ratio_check(self, test_db, test_user):
        """Test that low R:R ratio is rejected."""
        validator = RiskValidator(db=test_db)

        # Low R:R ratio (< 1.5)
        signal = Signal(
            user_id=test_user.id,
            strategy_name="NBB",
            symbol="EURUSD",
            signal_type=SignalType.LONG,
            status=SignalStatus.PENDING,
            entry_price=1.1000,
            stop_loss=1.0950,
            take_profit=1.1020,  # 0.4:1 R:R
            risk_percent=2.0,
            timeframe="1h",
            confidence=75.0,
            signal_time=datetime.utcnow()
        )

        test_db.add(signal)
        await test_db.commit()
        await test_db.refresh(signal)

        approved, reason, metrics = await validator.validate_trade(
            signal=signal,
            account_balance=10000.0,
            peak_balance=10000.0
        )

        assert approved is False
        assert "Risk/reward ratio" in reason

    async def test_max_positions_check(self, test_db, test_user):
        """Test that max positions limit is enforced."""
        # Create 10 open positions
        for i in range(10):
            position = Position(
                user_id=test_user.id,
                strategy_name="NBB",
                symbol=f"SYMBOL{i}",
                side=PositionSide.LONG,
                status=PositionStatus.OPEN,
                entry_price=100.0,
                position_size=0.1,
                entry_time=datetime.utcnow(),
                stop_loss=95.0,
                take_profit=110.0,
            )
            test_db.add(position)
        await test_db.commit()

        validator = RiskValidator(db=test_db)

        signal = Signal(
            user_id=test_user.id,
            strategy_name="NBB",
            symbol="EURUSD",
            signal_type=SignalType.LONG,
            status=SignalStatus.PENDING,
            entry_price=1.1000,
            stop_loss=1.0950,
            take_profit=1.1150,
            risk_percent=2.0,
            timeframe="1h",
            confidence=75.0,
            signal_time=datetime.utcnow()
        )

        test_db.add(signal)
        await test_db.commit()
        await test_db.refresh(signal)

        approved, reason, metrics = await validator.validate_trade(
            signal=signal,
            account_balance=10000.0,
            peak_balance=10000.0
        )

        assert approved is False
        assert "Maximum open positions" in reason

    async def test_emergency_shutdown_blocks_trades(self, test_db, test_user):
        """Test that emergency shutdown blocks all trades."""
        # Create state with emergency shutdown active
        state = AccountRiskState(
            account_balance=10000.0,
            peak_balance=10000.0,
            current_drawdown_percent=0.0,
            daily_pnl=0.0,
            daily_loss_percent=0.0,
            trades_today=0,
            trades_this_hour=0,
            open_positions_count=0,
            total_exposure=0.0,
            total_exposure_percent=0.0,
            emergency_shutdown_active=True,
            throttling_active=False,
            last_updated=datetime.utcnow()
        )
        test_db.add(state)
        await test_db.commit()

        validator = RiskValidator(db=test_db)

        signal = Signal(
            user_id=test_user.id,
            strategy_name="NBB",
            symbol="EURUSD",
            signal_type=SignalType.LONG,
            status=SignalStatus.PENDING,
            entry_price=1.1000,
            stop_loss=1.0950,
            take_profit=1.1150,
            risk_percent=2.0,
            timeframe="1h",
            confidence=75.0,
            signal_time=datetime.utcnow()
        )

        test_db.add(signal)
        await test_db.commit()
        await test_db.refresh(signal)

        approved, reason, metrics = await validator.validate_trade(
            signal=signal,
            account_balance=10000.0,
            peak_balance=10000.0
        )

        assert approved is False
        assert "Emergency shutdown is active" in reason

    async def test_position_size_calculation(self, test_db):
        """Test position size calculation."""
        validator = RiskValidator(db=test_db)

        # 2% risk on $10,000 = $200 risk
        # Entry 1.1000, SL 1.0950 = $0.0050 risk per unit
        # $200 / $0.0050 = 40,000 units, but capped at 1.0 lots
        position_size = validator._calculate_position_size(
            account_balance=10000.0,
            risk_percent=2.0,
            entry_price=1.1000,
            stop_loss=1.0950
        )

        assert position_size == 1.0  # Capped at MAX_POSITION_SIZE_LOTS

    async def test_check_drawdown_passes(self, test_db):
        """Test drawdown check passes below threshold."""
        validator = RiskValidator(db=test_db)

        result = validator._check_drawdown(10.0)  # 10% drawdown

        assert result["passed"] is True
        assert result["current"] == 10.0
        assert result["limit"] == EMERGENCY_DRAWDOWN_PERCENT

    async def test_check_drawdown_fails(self, test_db):
        """Test drawdown check fails at threshold."""
        validator = RiskValidator(db=test_db)

        result = validator._check_drawdown(15.0)  # Exactly at threshold

        assert result["passed"] is False
        assert "Emergency drawdown limit breached" in result["reason"]


@pytest.mark.asyncio
class TestRiskMonitor:
    """Test risk monitor functionality."""

    async def test_update_account_state_creates_new(self, test_db):
        """Test creating new account state."""
        monitor = RiskMonitor(db=test_db)

        state = await monitor.update_account_state(
            account_balance=10000.0,
            peak_balance=10000.0
        )

        assert state.account_balance == 10000.0
        assert state.peak_balance == 10000.0
        assert state.current_drawdown_percent == 0.0
        assert state.emergency_shutdown_active is False

    async def test_update_account_state_calculates_drawdown(self, test_db):
        """Test drawdown calculation."""
        monitor = RiskMonitor(db=test_db)

        state = await monitor.update_account_state(
            account_balance=9000.0,
            peak_balance=10000.0
        )

        assert state.current_drawdown_percent == 10.0  # 10% drawdown

    async def test_reset_emergency_shutdown(self, test_db):
        """Test resetting emergency shutdown."""
        # Create state with shutdown active
        state = AccountRiskState(
            account_balance=10000.0,
            peak_balance=10000.0,
            current_drawdown_percent=0.0,
            daily_pnl=0.0,
            daily_loss_percent=0.0,
            trades_today=0,
            trades_this_hour=0,
            open_positions_count=0,
            total_exposure=0.0,
            total_exposure_percent=0.0,
            emergency_shutdown_active=True,
            throttling_active=False,
            last_updated=datetime.utcnow()
        )
        test_db.add(state)
        await test_db.commit()

        monitor = RiskMonitor(db=test_db)
        result = await monitor.reset_emergency_shutdown()

        assert result is True

        # Verify shutdown is reset
        updated_state = await monitor.get_account_state()
        assert updated_state.emergency_shutdown_active is False

    async def test_strategy_auto_disable(self, test_db, test_user):
        """Test strategy auto-disable after consecutive losses."""
        monitor = RiskMonitor(db=test_db)

        # Create a position with loss
        position = Position(
            user_id=test_user.id,
            strategy_name="NBB",
            symbol="EURUSD",
            side=PositionSide.LONG,
            status=PositionStatus.CLOSED,
            entry_price=1.1000,
            position_size=0.1,
            entry_time=datetime.utcnow(),
            exit_price=1.0950,
            exit_time=datetime.utcnow(),
            stop_loss=1.0950,
            take_profit=1.1150,
            realized_pnl=-50.0
        )
        test_db.add(position)
        await test_db.commit()

        # Simulate 5 consecutive losses
        for i in range(5):
            await monitor.update_strategy_budget(
                strategy_name="NBB",
                symbol="EURUSD",
                position=position,
                trade_closed=True
            )

        # Check if strategy is disabled
        from sqlalchemy import select, and_
        stmt = select(StrategyRiskBudget).where(
            and_(
                StrategyRiskBudget.strategy_name == "NBB",
                StrategyRiskBudget.symbol == "EURUSD"
            )
        )
        result = await test_db.execute(stmt)
        budget = result.scalar_one_or_none()

        assert budget is not None
        assert budget.is_enabled is False
        assert "consecutive losses" in budget.disabled_reason

    async def test_enable_strategy(self, test_db):
        """Test re-enabling a disabled strategy."""
        # Create disabled budget
        budget = StrategyRiskBudget(
            strategy_name="NBB",
            symbol="EURUSD",
            max_exposure_percent=5.0,
            max_daily_loss_percent=2.0,
            current_exposure=0.0,
            current_exposure_percent=0.0,
            daily_pnl=0.0,
            is_enabled=False,
            disabled_reason="5 consecutive losses",
            consecutive_losses=5,
            last_updated=datetime.utcnow()
        )
        test_db.add(budget)
        await test_db.commit()

        monitor = RiskMonitor(db=test_db)
        result = await monitor.enable_strategy("NBB", "EURUSD")

        assert result is True

        # Verify enabled
        from sqlalchemy import select, and_
        stmt = select(StrategyRiskBudget).where(
            and_(
                StrategyRiskBudget.strategy_name == "NBB",
                StrategyRiskBudget.symbol == "EURUSD"
            )
        )
        result = await test_db.execute(stmt)
        updated_budget = result.scalar_one_or_none()

        assert updated_budget.is_enabled is True
        assert updated_budget.consecutive_losses == 0
        assert updated_budget.disabled_reason is None


@pytest.mark.asyncio
class TestRiskAPI:
    """Test risk API endpoints."""

    async def test_get_risk_limits(self, client):
        """Test getting risk limits endpoint."""
        response = await client.get("/api/v1/risk/limits")

        assert response.status_code == 200
        data = response.json()

        assert "position_limits" in data
        assert "account_limits" in data
        assert "daily_limits" in data
        assert data["position_limits"]["max_risk_per_trade_percent"] == 2.0
        assert data["account_limits"]["emergency_drawdown_percent"] == 15.0

    async def test_get_risk_state_empty(self, client):
        """Test getting risk state when none exists."""
        response = await client.get("/api/v1/risk/state")

        assert response.status_code == 200
        data = response.json()
        assert data.get("message") == "No risk state available"

    async def test_update_risk_state(self, client):
        """Test updating risk state."""
        response = await client.post(
            "/api/v1/risk/state/update",
            json={
                "account_balance": 10000.0,
                "peak_balance": 10000.0
            }
        )

        assert response.status_code == 200
        data = response.json()

        assert data["account_balance"] == 10000.0
        assert data["current_drawdown_percent"] == 0.0
        assert data["emergency_shutdown_active"] is False

    async def test_get_risk_decisions_empty(self, client):
        """Test getting risk decisions when none exist."""
        response = await client.get("/api/v1/risk/decisions")

        assert response.status_code == 200
        data = response.json()
        assert data == []

    async def test_get_strategy_budgets_empty(self, client):
        """Test getting strategy budgets when none exist."""
        response = await client.get("/api/v1/risk/budgets")

        assert response.status_code == 200
        data = response.json()
        assert data == []
