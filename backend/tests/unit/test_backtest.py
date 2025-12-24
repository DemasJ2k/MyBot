"""
Unit tests for backtest engine.

Prompt 05 - Backtest Engine.
"""

import pytest
from datetime import datetime, timedelta

from app.backtest.portfolio import (
    Portfolio,
    Trade,
    OpenPosition,
    EquityPoint,
    TradeSide,
)
from app.backtest.performance import PerformanceMetrics


# ============================================================================
# Portfolio Tests
# ============================================================================

class TestPortfolio:
    """Tests for the Portfolio class."""

    def test_portfolio_initialization(self):
        """Test portfolio initializes correctly."""
        portfolio = Portfolio(initial_balance=10000.0)
        
        assert portfolio.initial_balance == 10000.0
        assert portfolio.balance == 10000.0
        assert portfolio.equity == 10000.0
        assert len(portfolio.positions) == 0
        assert len(portfolio.trades) == 0
        assert len(portfolio.equity_curve) == 0

    def test_open_position_long(self):
        """Test opening a long position."""
        portfolio = Portfolio(initial_balance=10000.0)
        entry_time = datetime(2024, 1, 1, 10, 0, 0)
        
        position = portfolio.open_position(
            symbol="EUR/USD",
            side=TradeSide.LONG,
            entry_price=1.1000,
            quantity=1000,
            entry_time=entry_time,
            stop_loss=1.0900,
            take_profit=1.1200,
        )
        
        assert position is not None
        assert position.symbol == "EUR/USD"
        assert position.side == TradeSide.LONG
        assert position.entry_price == 1.1000
        assert position.quantity == 1000
        assert position.stop_loss == 1.0900
        assert position.take_profit == 1.1200
        assert len(portfolio.positions) == 1

    def test_open_position_insufficient_balance(self):
        """Test opening position fails with insufficient balance."""
        portfolio = Portfolio(initial_balance=100.0)  # Small balance
        entry_time = datetime(2024, 1, 1, 10, 0, 0)
        
        position = portfolio.open_position(
            symbol="EUR/USD",
            side=TradeSide.LONG,
            entry_price=1.1000,
            quantity=10000,  # Way too large
            entry_time=entry_time,
        )
        
        assert position is None
        assert len(portfolio.positions) == 0

    def test_close_position_profit(self):
        """Test closing position with profit."""
        portfolio = Portfolio(initial_balance=10000.0, commission_rate=0.0)
        entry_time = datetime(2024, 1, 1, 10, 0, 0)
        exit_time = datetime(2024, 1, 1, 14, 0, 0)
        
        position = portfolio.open_position(
            symbol="EUR/USD",
            side=TradeSide.LONG,
            entry_price=1.1000,
            quantity=1000,
            entry_time=entry_time,
        )
        
        trade = portfolio.close_position(
            position=position,
            exit_price=1.1100,  # 100 pip profit
            exit_time=exit_time,
        )
        
        assert trade.pnl == pytest.approx(10.0, rel=0.001)  # (1.1100 - 1.1000) * 1000
        assert trade.pnl_percent == pytest.approx(0.009090909, rel=0.001)
        assert len(portfolio.positions) == 0
        assert len(portfolio.trades) == 1

    def test_close_position_loss(self):
        """Test closing position with loss."""
        portfolio = Portfolio(initial_balance=10000.0, commission_rate=0.0)
        entry_time = datetime(2024, 1, 1, 10, 0, 0)
        exit_time = datetime(2024, 1, 1, 14, 0, 0)
        
        position = portfolio.open_position(
            symbol="EUR/USD",
            side=TradeSide.LONG,
            entry_price=1.1000,
            quantity=1000,
            entry_time=entry_time,
        )
        
        trade = portfolio.close_position(
            position=position,
            exit_price=1.0900,  # 100 pip loss
            exit_time=exit_time,
        )
        
        assert trade.pnl == pytest.approx(-10.0, rel=0.001)  # (1.0900 - 1.1000) * 1000
        assert len(portfolio.trades) == 1

    def test_stop_loss_trigger_long(self):
        """Test stop-loss triggers for long position."""
        portfolio = Portfolio(initial_balance=10000.0, commission_rate=0.0)
        entry_time = datetime(2024, 1, 1, 10, 0, 0)
        check_time = datetime(2024, 1, 1, 12, 0, 0)
        
        portfolio.open_position(
            symbol="EUR/USD",
            side=TradeSide.LONG,
            entry_price=1.1000,
            quantity=1000,
            entry_time=entry_time,
            stop_loss=1.0950,  # 50 pip stop
        )
        
        # Price drops to stop-loss
        closed = portfolio.check_stop_loss_take_profit(
            current_price=1.0940,  # Below stop-loss
            current_time=check_time,
        )
        
        assert len(closed) == 1
        assert closed[0].exit_price == 1.0950  # Closed at SL price
        assert len(portfolio.positions) == 0

    def test_take_profit_trigger_long(self):
        """Test take-profit triggers for long position."""
        portfolio = Portfolio(initial_balance=10000.0, commission_rate=0.0)
        entry_time = datetime(2024, 1, 1, 10, 0, 0)
        check_time = datetime(2024, 1, 1, 12, 0, 0)
        
        portfolio.open_position(
            symbol="EUR/USD",
            side=TradeSide.LONG,
            entry_price=1.1000,
            quantity=1000,
            entry_time=entry_time,
            take_profit=1.1100,  # 100 pip target
        )
        
        # Price rises to take-profit
        closed = portfolio.check_stop_loss_take_profit(
            current_price=1.1150,  # Above take-profit
            current_time=check_time,
        )
        
        assert len(closed) == 1
        assert closed[0].exit_price == 1.1100  # Closed at TP price
        assert closed[0].pnl == pytest.approx(10.0, rel=0.001)  # 100 pips profit

    def test_short_position_pnl(self):
        """Test P&L calculation for short positions."""
        portfolio = Portfolio(initial_balance=10000.0, commission_rate=0.0)
        entry_time = datetime(2024, 1, 1, 10, 0, 0)
        exit_time = datetime(2024, 1, 1, 14, 0, 0)
        
        position = portfolio.open_position(
            symbol="EUR/USD",
            side=TradeSide.SHORT,
            entry_price=1.1000,
            quantity=1000,
            entry_time=entry_time,
        )
        
        # Price drops = profit for short
        trade = portfolio.close_position(
            position=position,
            exit_price=1.0900,
            exit_time=exit_time,
        )
        
        assert trade.pnl == pytest.approx(10.0, rel=0.001)  # (1.1000 - 1.0900) * 1000

    def test_equity_curve_update(self):
        """Test equity curve updates correctly."""
        portfolio = Portfolio(initial_balance=10000.0, commission_rate=0.0)
        entry_time = datetime(2024, 1, 1, 10, 0, 0)
        
        portfolio.open_position(
            symbol="EUR/USD",
            side=TradeSide.LONG,
            entry_price=1.1000,
            quantity=1000,
            entry_time=entry_time,
        )
        
        # Update equity with higher price
        portfolio.update_equity(
            current_prices={"EUR/USD": 1.1050},
            timestamp=datetime(2024, 1, 1, 11, 0, 0),
        )
        
        assert len(portfolio.equity_curve) == 1
        # Balance is reduced by position cost, then position value at current price added
        # Balance: 10000 - 1100 (entry value + commission) = 8900
        # Position value at 1.1050: 1050 * 1000 = 1105
        # Total equity: 8900 + 1105 = 10005 (approx)

    def test_win_rate_calculation(self):
        """Test win rate property."""
        portfolio = Portfolio(initial_balance=10000.0, commission_rate=0.0)
        
        # Add 3 winning and 2 losing trades
        for i in range(3):
            portfolio.trades.append(
                Trade(
                    symbol="EUR/USD",
                    side=TradeSide.LONG,
                    entry_price=1.1,
                    exit_price=1.11,
                    quantity=100,
                    entry_time=datetime.now(),
                    exit_time=datetime.now(),
                    pnl=10.0,
                    pnl_percent=0.01,
                )
            )
        
        for i in range(2):
            portfolio.trades.append(
                Trade(
                    symbol="EUR/USD",
                    side=TradeSide.LONG,
                    entry_price=1.1,
                    exit_price=1.09,
                    quantity=100,
                    entry_time=datetime.now(),
                    exit_time=datetime.now(),
                    pnl=-10.0,
                    pnl_percent=-0.01,
                )
            )
        
        assert portfolio.win_rate == pytest.approx(0.6, rel=0.001)  # 3/5

    def test_max_drawdown_calculation(self):
        """Test max drawdown from equity curve."""
        portfolio = Portfolio(initial_balance=10000.0)
        
        # Simulate equity curve with drawdown
        portfolio.equity_curve = [
            EquityPoint(datetime(2024, 1, 1), equity=10000.0, drawdown=0.0),
            EquityPoint(datetime(2024, 1, 2), equity=10500.0, drawdown=0.0),
            EquityPoint(datetime(2024, 1, 3), equity=9500.0, drawdown=0.095238),  # ~9.5% DD
            EquityPoint(datetime(2024, 1, 4), equity=9800.0, drawdown=0.066667),
            EquityPoint(datetime(2024, 1, 5), equity=10200.0, drawdown=0.0285),
        ]
        
        assert portfolio.max_drawdown == pytest.approx(0.095238, rel=0.001)


# ============================================================================
# PerformanceMetrics Tests
# ============================================================================

class TestPerformanceMetrics:
    """Tests for PerformanceMetrics class."""

    def test_calculate_from_portfolio(self):
        """Test calculating metrics from portfolio."""
        portfolio = Portfolio(initial_balance=10000.0)
        portfolio.equity = 11000.0  # 10% return
        
        # Add some trades
        portfolio.trades = [
            Trade("EUR/USD", TradeSide.LONG, 1.1, 1.12, 100,
                  datetime(2024, 1, 1), datetime(2024, 1, 2), 200.0, 0.02),
            Trade("EUR/USD", TradeSide.LONG, 1.12, 1.10, 100,
                  datetime(2024, 1, 2), datetime(2024, 1, 3), -200.0, -0.02),
            Trade("EUR/USD", TradeSide.LONG, 1.1, 1.15, 100,
                  datetime(2024, 1, 3), datetime(2024, 1, 4), 500.0, 0.05),
        ]
        
        # Add equity curve
        portfolio.equity_curve = [
            EquityPoint(datetime(2024, 1, 1), 10000.0, 0.0),
            EquityPoint(datetime(2024, 1, 2), 10200.0, 0.0),
            EquityPoint(datetime(2024, 1, 3), 10000.0, 0.0196),
            EquityPoint(datetime(2024, 1, 4), 11000.0, 0.0),
        ]
        
        metrics = PerformanceMetrics.from_portfolio(portfolio)
        
        assert metrics.total_return == pytest.approx(0.10, rel=0.01)
        assert metrics.total_trades == 3
        assert metrics.winning_trades == 2
        assert metrics.losing_trades == 1
        assert metrics.win_rate == pytest.approx(0.6667, rel=0.01)

    def test_sharpe_ratio_calculation(self):
        """Test Sharpe ratio calculation."""
        # Create a returns series with known mean and std
        returns = [0.01, 0.02, -0.01, 0.015, 0.005]  # Daily returns
        
        sharpe = PerformanceMetrics._calculate_sharpe_ratio(returns, risk_free_rate=0.02)
        
        # With these returns, should be positive
        assert sharpe is not None
        assert sharpe > 0

    def test_sharpe_ratio_insufficient_data(self):
        """Test Sharpe ratio with insufficient data returns None."""
        returns = [0.01]  # Only one return
        
        sharpe = PerformanceMetrics._calculate_sharpe_ratio(returns, risk_free_rate=0.02)
        
        assert sharpe is None

    def test_sortino_ratio_calculation(self):
        """Test Sortino ratio calculation."""
        returns = [0.01, 0.02, -0.01, -0.005, 0.015]  # Mix of positive and negative
        
        sortino = PerformanceMetrics._calculate_sortino_ratio(returns, risk_free_rate=0.02)
        
        assert sortino is not None

    def test_sortino_ratio_no_negative_returns(self):
        """Test Sortino ratio with no negative returns returns None."""
        returns = [0.01, 0.02, 0.015]  # All positive
        
        sortino = PerformanceMetrics._calculate_sortino_ratio(returns, risk_free_rate=0.02)
        
        assert sortino is None

    def test_profit_factor_calculation(self):
        """Test profit factor calculation."""
        trades = [
            Trade("X", TradeSide.LONG, 1.0, 1.1, 100, datetime.now(), datetime.now(), 100.0, 0.1),
            Trade("X", TradeSide.LONG, 1.0, 1.1, 100, datetime.now(), datetime.now(), 200.0, 0.2),
            Trade("X", TradeSide.LONG, 1.0, 0.9, 100, datetime.now(), datetime.now(), -50.0, -0.05),
        ]
        
        pf = PerformanceMetrics._calculate_profit_factor(trades)
        
        # Gross profit = 300, Gross loss = 50
        assert pf == pytest.approx(6.0, rel=0.01)

    def test_profit_factor_no_losses(self):
        """Test profit factor with no losing trades returns None."""
        trades = [
            Trade("X", TradeSide.LONG, 1.0, 1.1, 100, datetime.now(), datetime.now(), 100.0, 0.1),
            Trade("X", TradeSide.LONG, 1.0, 1.1, 100, datetime.now(), datetime.now(), 200.0, 0.2),
        ]
        
        pf = PerformanceMetrics._calculate_profit_factor(trades)
        
        assert pf is None

    def test_expectancy_calculation(self):
        """Test expectancy calculation."""
        # 60% win rate, avg win $200, avg loss $100
        expectancy = PerformanceMetrics._calculate_expectancy(
            win_rate=0.6,
            avg_win=200.0,
            avg_loss=100.0,
        )
        
        # (0.6 * 200) - (0.4 * 100) = 120 - 40 = 80
        assert expectancy == pytest.approx(80.0, rel=0.01)

    def test_avg_trade_duration(self):
        """Test average trade duration calculation."""
        trades = [
            Trade("X", TradeSide.LONG, 1.0, 1.1, 100,
                  datetime(2024, 1, 1, 10, 0), datetime(2024, 1, 1, 14, 0), 10.0, 0.1),  # 4 hours
            Trade("X", TradeSide.LONG, 1.0, 1.1, 100,
                  datetime(2024, 1, 2, 10, 0), datetime(2024, 1, 2, 12, 0), 10.0, 0.1),  # 2 hours
        ]
        
        avg_duration = PerformanceMetrics._calculate_avg_trade_duration(trades)
        
        assert avg_duration == pytest.approx(3.0, rel=0.01)  # 3 hours average

    def test_recovery_factor(self):
        """Test recovery factor calculation."""
        recovery = PerformanceMetrics._calculate_recovery_factor(
            total_pnl=1000.0,
            max_drawdown=0.10,  # 10%
            initial_balance=10000.0,
        )
        
        # max_dd_amount = 0.10 * 10000 = 1000
        # recovery = 1000 / 1000 = 1.0
        assert recovery == pytest.approx(1.0, rel=0.01)

    def test_recovery_factor_no_drawdown(self):
        """Test recovery factor with no drawdown returns None."""
        recovery = PerformanceMetrics._calculate_recovery_factor(
            total_pnl=1000.0,
            max_drawdown=0.0,
            initial_balance=10000.0,
        )
        
        assert recovery is None

    def test_metrics_summary(self):
        """Test metrics summary string generation."""
        portfolio = Portfolio(initial_balance=10000.0)
        portfolio.equity = 11000.0
        portfolio.trades = [
            Trade("X", TradeSide.LONG, 1.0, 1.1, 100, datetime.now(), datetime.now(), 100.0, 0.1),
        ]
        portfolio.equity_curve = [
            EquityPoint(datetime.now(), 10000.0, 0.0),
            EquityPoint(datetime.now(), 11000.0, 0.0),
        ]
        
        metrics = PerformanceMetrics.from_portfolio(portfolio)
        summary = metrics.summary()
        
        assert "BACKTEST PERFORMANCE SUMMARY" in summary
        assert "Total Return:" in summary
        assert "Max Drawdown:" in summary

    def test_metrics_to_dict(self):
        """Test metrics to_dict conversion."""
        portfolio = Portfolio(initial_balance=10000.0)
        portfolio.equity = 11000.0
        portfolio.equity_curve = [
            EquityPoint(datetime.now(), 10000.0, 0.0),
            EquityPoint(datetime.now(), 11000.0, 0.0),
        ]
        
        metrics = PerformanceMetrics.from_portfolio(portfolio)
        d = metrics.to_dict()
        
        assert "total_return" in d
        assert "sharpe_ratio" in d
        assert "max_drawdown" in d
        assert "win_rate" in d


# ============================================================================
# OpenPosition Tests
# ============================================================================

class TestOpenPosition:
    """Tests for OpenPosition dataclass."""

    def test_unrealized_pnl_long_profit(self):
        """Test unrealized P&L for long position in profit."""
        position = OpenPosition(
            symbol="EUR/USD",
            side=TradeSide.LONG,
            entry_price=1.1000,
            quantity=1000,
            entry_time=datetime.now(),
        )
        
        pnl = position.unrealized_pnl(current_price=1.1050)
        
        assert pnl == pytest.approx(5.0, rel=0.01)  # (1.1050 - 1.1000) * 1000

    def test_unrealized_pnl_short_profit(self):
        """Test unrealized P&L for short position in profit."""
        position = OpenPosition(
            symbol="EUR/USD",
            side=TradeSide.SHORT,
            entry_price=1.1000,
            quantity=1000,
            entry_time=datetime.now(),
        )
        
        pnl = position.unrealized_pnl(current_price=1.0950)
        
        assert pnl == pytest.approx(5.0, rel=0.01)  # (1.1000 - 1.0950) * 1000

    def test_unrealized_pnl_percent(self):
        """Test unrealized P&L percentage calculation."""
        position = OpenPosition(
            symbol="EUR/USD",
            side=TradeSide.LONG,
            entry_price=1.1000,
            quantity=1000,
            entry_time=datetime.now(),
        )
        
        pnl_pct = position.unrealized_pnl_percent(current_price=1.1100)
        
        # 10 / 1100 = 0.00909...
        assert pnl_pct == pytest.approx(0.00909, rel=0.01)


# ============================================================================
# Trade Tests
# ============================================================================

class TestTrade:
    """Tests for Trade dataclass."""

    def test_trade_to_dict(self):
        """Test trade to_dict conversion."""
        trade = Trade(
            symbol="EUR/USD",
            side=TradeSide.LONG,
            entry_price=1.1000,
            exit_price=1.1100,
            quantity=1000,
            entry_time=datetime(2024, 1, 1, 10, 0, 0),
            exit_time=datetime(2024, 1, 1, 14, 0, 0),
            pnl=100.0,
            pnl_percent=0.0909,
            commission=2.2,
        )
        
        d = trade.to_dict()
        
        assert d["symbol"] == "EUR/USD"
        assert d["side"] == "LONG"
        assert d["entry_price"] == 1.1000
        assert d["exit_price"] == 1.1100
        assert d["pnl"] == 100.0


# ============================================================================
# EquityPoint Tests
# ============================================================================

class TestEquityPoint:
    """Tests for EquityPoint dataclass."""

    def test_equity_point_to_dict(self):
        """Test equity point to_dict conversion."""
        ep = EquityPoint(
            timestamp=datetime(2024, 1, 1, 10, 0, 0),
            equity=10500.0,
            drawdown=0.05,
        )
        
        d = ep.to_dict()
        
        assert d["equity"] == 10500.0
        assert d["drawdown"] == 0.05
        assert "2024-01-01" in d["timestamp"]
