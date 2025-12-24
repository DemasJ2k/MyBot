"""
Performance metrics calculator for backtesting.

Calculates Sharpe ratio, Sortino ratio, drawdown, and other statistics.
Prompt 05 - Backtest Engine.
"""

from dataclasses import dataclass
from typing import Optional
import math

from app.backtest.portfolio import Portfolio, EquityPoint, Trade


@dataclass
class PerformanceMetrics:
    """
    Calculates and stores comprehensive backtest performance metrics.
    
    Metrics include:
    - Total return and P&L
    - Risk-adjusted returns (Sharpe, Sortino)
    - Drawdown statistics
    - Trade statistics (win rate, profit factor, expectancy)
    - Recovery factor
    
    All ratios are annualized assuming 252 trading days.
    """
    # Return metrics
    total_return: float
    total_pnl: float
    
    # Risk metrics
    sharpe_ratio: Optional[float]
    sortino_ratio: Optional[float]
    max_drawdown: float
    avg_drawdown: float
    
    # Trade statistics
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    profit_factor: Optional[float]
    expectancy: float
    
    # Additional metrics
    avg_win: float
    avg_loss: float
    largest_win: float
    largest_loss: float
    avg_trade_duration_hours: float
    recovery_factor: Optional[float]
    
    # Annualization factor (trading days per year)
    TRADING_DAYS_PER_YEAR: int = 252
    
    @classmethod
    def from_portfolio(
        cls,
        portfolio: Portfolio,
        risk_free_rate: float = 0.02
    ) -> "PerformanceMetrics":
        """
        Calculate all performance metrics from a portfolio.
        
        Args:
            portfolio: The portfolio after backtesting
            risk_free_rate: Annual risk-free rate (default 2%)
            
        Returns:
            PerformanceMetrics instance with all calculated values
        """
        # Basic return metrics
        total_return = portfolio.total_return
        total_pnl = portfolio.total_pnl
        
        # Drawdown metrics
        max_drawdown = portfolio.max_drawdown
        avg_drawdown = cls._calculate_avg_drawdown(portfolio.equity_curve)
        
        # Calculate returns series for Sharpe/Sortino
        returns = cls._calculate_returns_series(portfolio.equity_curve)
        
        # Risk-adjusted returns
        sharpe_ratio = cls._calculate_sharpe_ratio(returns, risk_free_rate)
        sortino_ratio = cls._calculate_sortino_ratio(returns, risk_free_rate)
        
        # Trade statistics
        total_trades = len(portfolio.trades)
        winning_trades = len(portfolio.winning_trades)
        losing_trades = len(portfolio.losing_trades)
        win_rate = portfolio.win_rate
        
        # Profit factor
        profit_factor = cls._calculate_profit_factor(portfolio.trades)
        
        # Average win/loss
        avg_win, avg_loss = cls._calculate_avg_win_loss(portfolio.trades)
        
        # Largest win/loss
        largest_win, largest_loss = cls._calculate_largest_win_loss(portfolio.trades)
        
        # Expectancy
        expectancy = cls._calculate_expectancy(win_rate, avg_win, avg_loss)
        
        # Average trade duration
        avg_trade_duration = cls._calculate_avg_trade_duration(portfolio.trades)
        
        # Recovery factor
        recovery_factor = cls._calculate_recovery_factor(total_pnl, max_drawdown, portfolio.initial_balance)
        
        return cls(
            total_return=total_return,
            total_pnl=total_pnl,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            max_drawdown=max_drawdown,
            avg_drawdown=avg_drawdown,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=win_rate,
            profit_factor=profit_factor,
            expectancy=expectancy,
            avg_win=avg_win,
            avg_loss=avg_loss,
            largest_win=largest_win,
            largest_loss=largest_loss,
            avg_trade_duration_hours=avg_trade_duration,
            recovery_factor=recovery_factor,
        )
    
    @staticmethod
    def _calculate_returns_series(equity_curve: list[EquityPoint]) -> list[float]:
        """
        Calculate period-over-period returns from equity curve.
        
        Args:
            equity_curve: List of equity points
            
        Returns:
            List of percentage returns
        """
        if len(equity_curve) < 2:
            return []
        
        returns = []
        for i in range(1, len(equity_curve)):
            prev_equity = equity_curve[i - 1].equity
            curr_equity = equity_curve[i].equity
            
            if prev_equity > 0:
                ret = (curr_equity - prev_equity) / prev_equity
                returns.append(ret)
        
        return returns
    
    @classmethod
    def _calculate_sharpe_ratio(
        cls,
        returns: list[float],
        risk_free_rate: float
    ) -> Optional[float]:
        """
        Calculate annualized Sharpe ratio.
        
        Sharpe = (mean_return - risk_free_rate) / std_dev * sqrt(252)
        
        Args:
            returns: List of period returns
            risk_free_rate: Annual risk-free rate
            
        Returns:
            Sharpe ratio or None if insufficient data
        """
        if len(returns) < 2:
            return None
        
        mean_return = sum(returns) / len(returns)
        
        # Calculate standard deviation
        variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
        std_dev = math.sqrt(variance)
        
        if std_dev == 0:
            return None
        
        # Daily risk-free rate
        daily_rf = risk_free_rate / cls.TRADING_DAYS_PER_YEAR
        
        # Annualized Sharpe ratio
        sharpe = (mean_return - daily_rf) / std_dev * math.sqrt(cls.TRADING_DAYS_PER_YEAR)
        
        return sharpe
    
    @classmethod
    def _calculate_sortino_ratio(
        cls,
        returns: list[float],
        risk_free_rate: float
    ) -> Optional[float]:
        """
        Calculate annualized Sortino ratio.
        
        Sortino uses downside deviation instead of standard deviation,
        penalizing only negative volatility.
        
        Args:
            returns: List of period returns
            risk_free_rate: Annual risk-free rate
            
        Returns:
            Sortino ratio or None if insufficient data
        """
        if len(returns) < 2:
            return None
        
        mean_return = sum(returns) / len(returns)
        
        # Calculate downside deviation (only negative returns)
        negative_returns = [r for r in returns if r < 0]
        
        if not negative_returns:
            # No negative returns - excellent performance, but can't calculate
            return None
        
        downside_variance = sum(r ** 2 for r in negative_returns) / len(returns)
        downside_dev = math.sqrt(downside_variance)
        
        if downside_dev == 0:
            return None
        
        # Daily risk-free rate
        daily_rf = risk_free_rate / cls.TRADING_DAYS_PER_YEAR
        
        # Annualized Sortino ratio
        sortino = (mean_return - daily_rf) / downside_dev * math.sqrt(cls.TRADING_DAYS_PER_YEAR)
        
        return sortino
    
    @staticmethod
    def _calculate_avg_drawdown(equity_curve: list[EquityPoint]) -> float:
        """
        Calculate average drawdown from equity curve.
        
        Args:
            equity_curve: List of equity points
            
        Returns:
            Average drawdown as a decimal
        """
        if not equity_curve:
            return 0.0
        
        drawdowns = [ep.drawdown for ep in equity_curve if ep.drawdown > 0]
        
        if not drawdowns:
            return 0.0
        
        return sum(drawdowns) / len(drawdowns)
    
    @staticmethod
    def _calculate_profit_factor(trades: list[Trade]) -> Optional[float]:
        """
        Calculate profit factor (gross profits / gross losses).
        
        Args:
            trades: List of completed trades
            
        Returns:
            Profit factor or None if no losing trades
        """
        gross_profit = sum(t.pnl for t in trades if t.pnl > 0)
        gross_loss = abs(sum(t.pnl for t in trades if t.pnl < 0))
        
        if gross_loss == 0:
            return None  # Infinite profit factor
        
        return gross_profit / gross_loss
    
    @staticmethod
    def _calculate_avg_win_loss(trades: list[Trade]) -> tuple[float, float]:
        """
        Calculate average winning and losing trade P&L.
        
        Args:
            trades: List of completed trades
            
        Returns:
            Tuple of (avg_win, avg_loss)
        """
        winners = [t.pnl for t in trades if t.pnl > 0]
        losers = [t.pnl for t in trades if t.pnl < 0]
        
        avg_win = sum(winners) / len(winners) if winners else 0.0
        avg_loss = abs(sum(losers) / len(losers)) if losers else 0.0
        
        return avg_win, avg_loss
    
    @staticmethod
    def _calculate_largest_win_loss(trades: list[Trade]) -> tuple[float, float]:
        """
        Find largest winning and losing trades.
        
        Args:
            trades: List of completed trades
            
        Returns:
            Tuple of (largest_win, largest_loss)
        """
        if not trades:
            return 0.0, 0.0
        
        pnls = [t.pnl for t in trades]
        largest_win = max(pnls) if pnls else 0.0
        largest_loss = abs(min(pnls)) if pnls else 0.0
        
        return max(0.0, largest_win), largest_loss
    
    @staticmethod
    def _calculate_expectancy(win_rate: float, avg_win: float, avg_loss: float) -> float:
        """
        Calculate trade expectancy (expected value per trade).
        
        Expectancy = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)
        
        Args:
            win_rate: Winning percentage as decimal
            avg_win: Average winning trade amount
            avg_loss: Average losing trade amount (positive number)
            
        Returns:
            Expected value per trade
        """
        return (win_rate * avg_win) - ((1 - win_rate) * avg_loss)
    
    @staticmethod
    def _calculate_avg_trade_duration(trades: list[Trade]) -> float:
        """
        Calculate average trade duration in hours.
        
        Args:
            trades: List of completed trades
            
        Returns:
            Average duration in hours
        """
        if not trades:
            return 0.0
        
        durations = []
        for trade in trades:
            duration = trade.exit_time - trade.entry_time
            durations.append(duration.total_seconds() / 3600)  # Convert to hours
        
        return sum(durations) / len(durations)
    
    @staticmethod
    def _calculate_recovery_factor(
        total_pnl: float,
        max_drawdown: float,
        initial_balance: float
    ) -> Optional[float]:
        """
        Calculate recovery factor (total P&L / max drawdown in currency).
        
        Recovery factor measures how well the strategy recovers from drawdowns.
        
        Args:
            total_pnl: Total profit/loss
            max_drawdown: Maximum drawdown as decimal
            initial_balance: Starting capital
            
        Returns:
            Recovery factor or None if no drawdown
        """
        if max_drawdown == 0:
            return None
        
        # Convert max drawdown to currency amount
        max_dd_amount = max_drawdown * initial_balance
        
        if max_dd_amount == 0:
            return None
        
        return total_pnl / max_dd_amount
    
    def to_dict(self) -> dict:
        """Convert metrics to dictionary for JSON serialization."""
        return {
            "total_return": self.total_return,
            "total_pnl": self.total_pnl,
            "sharpe_ratio": self.sharpe_ratio,
            "sortino_ratio": self.sortino_ratio,
            "max_drawdown": self.max_drawdown,
            "avg_drawdown": self.avg_drawdown,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": self.win_rate,
            "profit_factor": self.profit_factor,
            "expectancy": self.expectancy,
            "avg_win": self.avg_win,
            "avg_loss": self.avg_loss,
            "largest_win": self.largest_win,
            "largest_loss": self.largest_loss,
            "avg_trade_duration_hours": self.avg_trade_duration_hours,
            "recovery_factor": self.recovery_factor,
        }
    
    def summary(self) -> str:
        """Generate a human-readable summary of performance."""
        lines = [
            "=" * 50,
            "BACKTEST PERFORMANCE SUMMARY",
            "=" * 50,
            f"Total Return: {self.total_return:.2%}",
            f"Total P&L: ${self.total_pnl:,.2f}",
            "",
            "Risk Metrics:",
            f"  Sharpe Ratio: {self.sharpe_ratio:.2f}" if self.sharpe_ratio else "  Sharpe Ratio: N/A",
            f"  Sortino Ratio: {self.sortino_ratio:.2f}" if self.sortino_ratio else "  Sortino Ratio: N/A",
            f"  Max Drawdown: {self.max_drawdown:.2%}",
            f"  Avg Drawdown: {self.avg_drawdown:.2%}",
            "",
            "Trade Statistics:",
            f"  Total Trades: {self.total_trades}",
            f"  Winners: {self.winning_trades} | Losers: {self.losing_trades}",
            f"  Win Rate: {self.win_rate:.2%}",
            f"  Profit Factor: {self.profit_factor:.2f}" if self.profit_factor else "  Profit Factor: N/A",
            f"  Expectancy: ${self.expectancy:.2f}",
            "",
            "Trade Details:",
            f"  Avg Win: ${self.avg_win:.2f}",
            f"  Avg Loss: ${self.avg_loss:.2f}",
            f"  Largest Win: ${self.largest_win:.2f}",
            f"  Largest Loss: ${self.largest_loss:.2f}",
            f"  Avg Duration: {self.avg_trade_duration_hours:.1f} hours",
            "",
            f"Recovery Factor: {self.recovery_factor:.2f}" if self.recovery_factor else "Recovery Factor: N/A",
            "=" * 50,
        ]
        return "\n".join(lines)
