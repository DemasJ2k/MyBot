import pytest
from app.ai_agents.risk_agent import RiskAgent, HARD_CAPS
from app.models.ai_agent import SystemMode
from app.models.signal import Signal, SignalType, SignalStatus
from app.models.position import Position, PositionStatus, PositionSide
from datetime import datetime, timedelta


@pytest.mark.asyncio
class TestRiskAgent:
    """Test suite for RiskAgent."""

    async def test_hard_caps_defined(self):
        """Test that all hard caps are properly defined."""
        assert HARD_CAPS["max_risk_per_trade"] == 2.0
        assert HARD_CAPS["max_daily_loss"] == 5.0
        assert HARD_CAPS["max_trades_per_day"] == 20
        assert HARD_CAPS["max_open_positions"] == 10
        assert HARD_CAPS["max_order_size"] == 1.0
        assert HARD_CAPS["emergency_drawdown_stop"] == 15.0

    async def test_position_size_calculation(self, test_db):
        """Test position size calculation logic."""
        agent = RiskAgent(db=test_db, system_mode=SystemMode.GUIDE)

        # Test case 1: Normal calculation
        position_size = agent._calculate_position_size(
            account_balance=10000.0,
            risk_percent=2.0,
            entry_price=1.1000,
            stop_loss=1.0950
        )

        # Risk amount = 10000 * 0.02 = 200
        # Risk per unit = 1.1000 - 1.0950 = 0.005
        # Position size = 200 / 0.005 = 40000
        assert position_size > 0
        assert position_size == 40000.0

        # Test case 2: Zero risk per unit
        position_size_zero = agent._calculate_position_size(
            account_balance=10000.0,
            risk_percent=2.0,
            entry_price=1.1000,
            stop_loss=1.1000
        )
        assert position_size_zero == 0.0

    async def test_validate_signal_approved(self, test_db):
        """Test signal validation when all checks pass."""
        agent = RiskAgent(db=test_db, system_mode=SystemMode.AUTONOMOUS)

        signal = Signal(
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

        validation = await agent.validate_signal(signal, account_balance=10000.0)

        assert validation["approved"] is True
        assert validation["position_size"] > 0
        assert validation["reason"] == "All risk checks passed"

    async def test_validate_signal_max_open_positions(self, test_db):
        """Test signal rejection when max open positions reached."""
        agent = RiskAgent(db=test_db, system_mode=SystemMode.AUTONOMOUS)

        # Create 10 open positions (at limit)
        for i in range(10):
            position = Position(
                strategy_name=f"Strategy{i}",
                symbol="EURUSD",
                side=PositionSide.LONG,
                status=PositionStatus.OPEN,
                entry_price=1.1000,
                position_size=0.1,
                entry_time=datetime.utcnow(),
                stop_loss=1.0950,
                take_profit=1.1150,
                unrealized_pnl=0.0
            )
            test_db.add(position)

        await test_db.commit()

        signal = Signal(
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

        validation = await agent.validate_signal(signal, account_balance=10000.0)

        assert validation["approved"] is False
        assert "Max open positions reached" in validation["reason"]

    async def test_validate_signal_daily_trade_limit(self, test_db):
        """Test signal rejection when daily trade limit reached."""
        agent = RiskAgent(db=test_db, system_mode=SystemMode.AUTONOMOUS)

        # Create 20 positions today (at limit)
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

        for i in range(20):
            position = Position(
                strategy_name=f"Strategy{i}",
                symbol="EURUSD",
                side=PositionSide.LONG,
                status=PositionStatus.CLOSED,
                entry_price=1.1000,
                position_size=0.1,
                entry_time=today_start + timedelta(minutes=i*10),
                stop_loss=1.0950,
                take_profit=1.1150,
                exit_price=1.1050,
                exit_time=today_start + timedelta(minutes=i*10+5),
                unrealized_pnl=0.0,
                realized_pnl=5.0
            )
            test_db.add(position)

        await test_db.commit()

        signal = Signal(
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

        validation = await agent.validate_signal(signal, account_balance=10000.0)

        assert validation["approved"] is False
        assert "Daily trade limit reached" in validation["reason"]

    async def test_validate_signal_low_risk_reward(self, test_db):
        """Test signal rejection when R:R ratio is too low."""
        agent = RiskAgent(db=test_db, system_mode=SystemMode.AUTONOMOUS)

        signal = Signal(
            strategy_name="NBB",
            symbol="EURUSD",
            signal_type=SignalType.LONG,
            status=SignalStatus.PENDING,
            entry_price=1.1000,
            stop_loss=1.0950,  # Risk: 50 pips
            take_profit=1.1040,  # Reward: 40 pips (R:R = 0.8)
            risk_percent=2.0,
            timeframe="1h",
            confidence=75.0,
            signal_time=datetime.utcnow()
        )

        validation = await agent.validate_signal(signal, account_balance=10000.0)

        assert validation["approved"] is False
        assert "R:R ratio too low" in validation["reason"]

    async def test_check_emergency_conditions_normal(self, test_db):
        """Test emergency check under normal conditions."""
        agent = RiskAgent(db=test_db, system_mode=SystemMode.AUTONOMOUS)

        emergency = await agent.check_emergency_conditions(
            account_balance=9500.0,
            peak_balance=10000.0
        )

        # 5% drawdown - within acceptable range
        assert emergency is False

    async def test_check_emergency_conditions_triggered(self, test_db):
        """Test emergency shutdown when drawdown exceeds limit."""
        agent = RiskAgent(db=test_db, system_mode=SystemMode.AUTONOMOUS)

        emergency = await agent.check_emergency_conditions(
            account_balance=8400.0,  # 16% drawdown
            peak_balance=10000.0
        )

        # 16% drawdown - exceeds 15% emergency threshold
        assert emergency is True
