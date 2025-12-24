import pytest
from app.ai_agents.supervisor_agent import SupervisorAgent, HARD_CAPS
from app.ai_agents.strategy_agent import StrategyAgent
from app.ai_agents.execution_agent import ExecutionAgent
from app.models.ai_agent import SystemMode, SystemConfig
from app.models.signal import Signal, SignalType, SignalStatus
from app.models.position import Position, PositionStatus, PositionSide
from app.models.optimization import Playbook
from app.models.backtest import BacktestResult
from datetime import datetime


@pytest.mark.asyncio
class TestSupervisorAgent:
    """Test suite for SupervisorAgent."""

    async def test_enforce_mode_guide(self, test_db):
        """Test mode enforcement in GUIDE mode."""
        # Set up config for GUIDE mode
        config = SystemConfig(
            key="system_mode",
            value={"mode": "guide"},
            description="Test mode config"
        )
        test_db.add(config)
        await test_db.commit()

        agent = SupervisorAgent(db=test_db, system_mode=SystemMode.GUIDE)
        result = await agent.enforce_mode()

        assert result is True
        assert agent.system_mode == SystemMode.GUIDE

    async def test_enforce_mode_autonomous(self, test_db):
        """Test mode enforcement in AUTONOMOUS mode."""
        # Set up config for AUTONOMOUS mode
        config = SystemConfig(
            key="system_mode",
            value={"mode": "autonomous"},
            description="Test mode config"
        )
        test_db.add(config)
        await test_db.commit()

        agent = SupervisorAgent(db=test_db, system_mode=SystemMode.AUTONOMOUS)
        result = await agent.enforce_mode()

        assert result is True
        assert agent.system_mode == SystemMode.AUTONOMOUS

    async def test_verify_hard_caps(self, test_db):
        """Test hard caps verification."""
        agent = SupervisorAgent(db=test_db, system_mode=SystemMode.GUIDE)
        verification = await agent.verify_hard_caps()

        assert verification["verified"] is True
        assert verification["immutable"] is True
        assert len(verification["violations"]) == 0
        assert verification["hard_caps"] == HARD_CAPS

    async def test_can_proceed_with_trading_allowed(self, test_db):
        """Test trading permission when all checks pass."""
        agent = SupervisorAgent(db=test_db, system_mode=SystemMode.AUTONOMOUS)

        permission = await agent.can_proceed_with_trading(
            account_balance=9500.0,
            peak_balance=10000.0,
            open_positions=5,
            trades_today=10
        )

        assert permission["can_proceed"] is True
        assert len(permission["reasons"]) == 0

    async def test_can_proceed_with_trading_blocked_positions(self, test_db):
        """Test trading blocked when max positions reached."""
        agent = SupervisorAgent(db=test_db, system_mode=SystemMode.AUTONOMOUS)

        permission = await agent.can_proceed_with_trading(
            account_balance=9500.0,
            peak_balance=10000.0,
            open_positions=10,  # At limit
            trades_today=5
        )

        assert permission["can_proceed"] is False
        assert any("Max open positions" in reason for reason in permission["reasons"])

    async def test_can_proceed_with_trading_blocked_daily_limit(self, test_db):
        """Test trading blocked when daily limit reached."""
        agent = SupervisorAgent(db=test_db, system_mode=SystemMode.AUTONOMOUS)

        permission = await agent.can_proceed_with_trading(
            account_balance=9500.0,
            peak_balance=10000.0,
            open_positions=5,
            trades_today=20  # At limit
        )

        assert permission["can_proceed"] is False
        assert any("Daily trade limit" in reason for reason in permission["reasons"])

    async def test_can_proceed_with_trading_blocked_drawdown(self, test_db):
        """Test trading blocked when emergency drawdown reached."""
        agent = SupervisorAgent(db=test_db, system_mode=SystemMode.AUTONOMOUS)

        permission = await agent.can_proceed_with_trading(
            account_balance=8400.0,  # 16% drawdown
            peak_balance=10000.0,
            open_positions=5,
            trades_today=10
        )

        assert permission["can_proceed"] is False
        assert any("Emergency drawdown" in reason for reason in permission["reasons"])


@pytest.mark.asyncio
class TestStrategyAgent:
    """Test suite for StrategyAgent."""

    async def test_evaluate_strategy_performance_pass(self, test_db):
        """Test strategy evaluation when performance meets criteria."""
        # Create a good backtest result
        backtest = BacktestResult(
            strategy_name="NBB",
            symbol="EURUSD",
            timeframe="1h",
            user_id=1,
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 3, 1),
            initial_capital=10000.0,
            total_trades=50,
            winning_trades=30,
            losing_trades=20,
            win_rate=60.0,
            total_return=0.15,
            sharpe_ratio=1.2,
            max_drawdown=8.0,
            equity_curve=[],
            trade_log=[],
            strategy_params={"threshold": 0.8}
        )
        test_db.add(backtest)
        await test_db.commit()

        agent = StrategyAgent(db=test_db, system_mode=SystemMode.GUIDE)
        result = await agent._evaluate_strategy_performance("NBB", "EURUSD")

        assert result is True

    async def test_evaluate_strategy_performance_fail_low_sharpe(self, test_db):
        """Test strategy evaluation fails with low Sharpe ratio."""
        # Create a backtest with low Sharpe ratio
        backtest = BacktestResult(
            strategy_name="NBB",
            symbol="EURUSD",
            timeframe="1h",
            user_id=1,
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 3, 1),
            initial_capital=10000.0,
            total_trades=50,
            winning_trades=22,
            losing_trades=28,
            win_rate=44.0,
            total_return=0.02,
            sharpe_ratio=0.3,  # Too low
            max_drawdown=12.0,
            equity_curve=[],
            trade_log=[],
            strategy_params={"threshold": 0.8}
        )
        test_db.add(backtest)
        await test_db.commit()

        agent = StrategyAgent(db=test_db, system_mode=SystemMode.GUIDE)
        result = await agent._evaluate_strategy_performance("NBB", "EURUSD")

        assert result is False

    async def test_evaluate_strategy_performance_fail_high_drawdown(self, test_db):
        """Test strategy evaluation fails with high drawdown."""
        # Create a backtest with high drawdown
        backtest = BacktestResult(
            strategy_name="NBB",
            symbol="EURUSD",
            timeframe="1h",
            user_id=1,
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 3, 1),
            initial_capital=10000.0,
            total_trades=50,
            winning_trades=28,
            losing_trades=22,
            win_rate=56.0,
            total_return=0.10,
            sharpe_ratio=0.8,
            max_drawdown=25.0,  # Too high
            equity_curve=[],
            trade_log=[],
            strategy_params={"threshold": 0.8}
        )
        test_db.add(backtest)
        await test_db.commit()

        agent = StrategyAgent(db=test_db, system_mode=SystemMode.GUIDE)
        result = await agent._evaluate_strategy_performance("NBB", "EURUSD")

        assert result is False


@pytest.mark.asyncio
class TestExecutionAgent:
    """Test suite for ExecutionAgent."""

    async def test_execute_signal_guide_mode(self, test_db):
        """Test signal execution in GUIDE mode (should simulate only)."""
        agent = ExecutionAgent(db=test_db, system_mode=SystemMode.GUIDE)

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
        test_db.add(signal)
        await test_db.commit()

        position = await agent.execute_signal(
            signal=signal,
            position_size=0.5,
            account_balance=10000.0
        )

        # In GUIDE mode, no position should be created
        assert position is None

    async def test_execute_signal_autonomous_mode(self, test_db):
        """Test signal execution in AUTONOMOUS mode (should create position)."""
        agent = ExecutionAgent(db=test_db, system_mode=SystemMode.AUTONOMOUS)

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
        test_db.add(signal)
        await test_db.commit()

        position = await agent.execute_signal(
            signal=signal,
            position_size=0.5,
            account_balance=10000.0
        )

        # In AUTONOMOUS mode, position should be created
        assert position is not None
        assert position.strategy_name == "NBB"
        assert position.symbol == "EURUSD"
        assert position.side == PositionSide.LONG
        assert position.status == PositionStatus.OPEN
        assert position.position_size == 0.5

    async def test_close_position_long(self, test_db):
        """Test closing a long position."""
        agent = ExecutionAgent(db=test_db, system_mode=SystemMode.AUTONOMOUS)

        position = Position(
            strategy_name="NBB",
            symbol="EURUSD",
            side=PositionSide.LONG,
            status=PositionStatus.OPEN,
            entry_price=1.1000,
            position_size=1.0,
            entry_time=datetime.utcnow(),
            stop_loss=1.0950,
            take_profit=1.1150,
            unrealized_pnl=0.0
        )
        test_db.add(position)
        await test_db.commit()

        closed_position = await agent.close_position(
            position=position,
            exit_price=1.1100,
            reason="Take profit hit"
        )

        assert closed_position.status == PositionStatus.CLOSED
        assert closed_position.exit_price == 1.1100
        # PnL = (1.1100 - 1.1000) * 1.0 = 0.01 * 1.0 = 100 pips
        assert closed_position.realized_pnl == pytest.approx(0.01, rel=1e-6)

    async def test_close_position_short(self, test_db):
        """Test closing a short position."""
        agent = ExecutionAgent(db=test_db, system_mode=SystemMode.AUTONOMOUS)

        position = Position(
            strategy_name="NBB",
            symbol="EURUSD",
            side=PositionSide.SHORT,
            status=PositionStatus.OPEN,
            entry_price=1.1000,
            position_size=1.0,
            entry_time=datetime.utcnow(),
            stop_loss=1.1050,
            take_profit=1.0850,
            unrealized_pnl=0.0
        )
        test_db.add(position)
        await test_db.commit()

        closed_position = await agent.close_position(
            position=position,
            exit_price=1.0900,
            reason="Take profit hit"
        )

        assert closed_position.status == PositionStatus.CLOSED
        assert closed_position.exit_price == 1.0900
        # PnL = (1.1000 - 1.0900) * 1.0 = 0.01 * 1.0 = 100 pips
        assert closed_position.realized_pnl == pytest.approx(0.01, rel=1e-6)
