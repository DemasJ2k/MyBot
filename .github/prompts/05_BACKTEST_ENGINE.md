# Prompt 05: Backtest Engine

## Purpose

Build a comprehensive backtesting system that validates trading strategies using historical data. This engine simulates order execution, tracks performance metrics, generates equity curves, and enables strategy comparison and optimization.

## Scope

- Historical data replay with tick-by-tick simulation
- Simulated order execution with slippage and commission
- Portfolio tracking (balance, equity, margin, positions)
- Performance metrics calculation:
  - Total return, annualized return
  - Sharpe ratio, Sortino ratio
  - Maximum drawdown, average drawdown
  - Win rate, profit factor
  - Average win/loss, largest win/loss
  - Expectancy, recovery factor
- Equity curve and drawdown curve generation
- Trade-by-trade logging
- Multi-strategy comparison
- Parameter optimization preparation
- Backtest results storage and retrieval
- Complete test suite

## Backtest Architecture

```
Historical Candles (from Data Engine)
    ↓
Backtest Engine → Strategy (generate signals)
    ↓
Order Simulator → Fill Logic (slippage, commission)
    ↓
Portfolio Tracker → Position Management
    ↓
Performance Calculator → Metrics & Equity Curve
    ↓
Results Storage → Database
```

## Implementation

### Step 1: Database Models

Create `backend/app/models/backtest.py`:

```python
from sqlalchemy import String, Float, Integer, JSON, DateTime, Index, Text
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from typing import Optional, Dict, Any, List
from app.models.base import Base, TimestampMixin


class BacktestResult(Base, TimestampMixin):
    """Backtest execution results and performance metrics."""
    __tablename__ = "backtest_results"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    strategy_name: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    interval: Mapped[str] = mapped_column(String(10), nullable=False)

    # Backtest parameters
    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    initial_balance: Mapped[float] = mapped_column(Float, nullable=False)
    commission_percent: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    slippage_percent: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # Strategy configuration (JSON)
    strategy_config: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # Performance metrics
    final_balance: Mapped[float] = mapped_column(Float, nullable=False)
    total_return_percent: Mapped[float] = mapped_column(Float, nullable=False)
    annualized_return_percent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    total_trades: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    winning_trades: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    losing_trades: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    win_rate_percent: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    gross_profit: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    gross_loss: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    net_profit: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    profit_factor: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    avg_win: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    avg_loss: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    largest_win: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    largest_loss: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    max_drawdown_percent: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    avg_drawdown_percent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    sharpe_ratio: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sortino_ratio: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    expectancy: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    recovery_factor: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Equity curve and trade log (JSON)
    equity_curve: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSON, nullable=True)
    trade_log: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSON, nullable=True)

    # Execution metadata
    execution_time_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_backtest_strategy_symbol", "strategy_name", "symbol"),
    )

    def __repr__(self) -> str:
        return f"<BacktestResult {self.id} {self.strategy_name} {self.symbol} {self.total_return_percent:.2f}%>"
```

Update `backend/app/models/__init__.py`:

```python
from app.models.base import Base, TimestampMixin
from app.models.user import User
from app.models.market_data import Candle, Symbol, EconomicEvent
from app.models.signal import Signal, SignalType, SignalStatus
from app.models.position import Position, PositionStatus, PositionSide
from app.models.backtest import BacktestResult

__all__ = [
    "Base",
    "TimestampMixin",
    "User",
    "Candle",
    "Symbol",
    "EconomicEvent",
    "Signal",
    "SignalType",
    "SignalStatus",
    "Position",
    "PositionStatus",
    "PositionSide",
    "BacktestResult",
]
```

### Step 2: Portfolio Simulator

Create `backend/app/backtest/portfolio.py`:

```python
from typing import Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class Trade:
    """Represents a completed trade."""
    entry_time: datetime
    exit_time: datetime
    symbol: str
    side: str  # "long" or "short"
    entry_price: float
    exit_price: float
    position_size: float
    pnl: float
    commission: float
    net_pnl: float
    reason: str = ""


@dataclass
class OpenPosition:
    """Represents an open position."""
    symbol: str
    side: str  # "long" or "short"
    entry_price: float
    position_size: float
    stop_loss: float
    take_profit: float
    entry_time: datetime
    unrealized_pnl: float = 0.0


@dataclass
class EquityPoint:
    """Equity curve data point."""
    timestamp: datetime
    balance: float
    equity: float
    drawdown_percent: float


class Portfolio:
    """Simulates portfolio state during backtesting."""

    def __init__(
        self,
        initial_balance: float,
        commission_percent: float = 0.0,
        slippage_percent: float = 0.0
    ):
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.commission_percent = commission_percent
        self.slippage_percent = slippage_percent

        self.positions: Dict[str, OpenPosition] = {}
        self.trade_history: List[Trade] = []
        self.equity_curve: List[EquityPoint] = []

        self.peak_equity = initial_balance
        self.max_drawdown_percent = 0.0

    def calculate_equity(self, current_prices: Dict[str, float]) -> float:
        """Calculate current equity (balance + unrealized P&L)."""
        unrealized_pnl = 0.0

        for symbol, position in self.positions.items():
            current_price = current_prices.get(symbol, position.entry_price)
            position.unrealized_pnl = self._calculate_pnl(
                side=position.side,
                entry_price=position.entry_price,
                exit_price=current_price,
                position_size=position.position_size
            )
            unrealized_pnl += position.unrealized_pnl

        equity = self.balance + unrealized_pnl
        return equity

    def update_equity_curve(self, timestamp: datetime, current_prices: Dict[str, float]):
        """Update equity curve with current state."""
        equity = self.calculate_equity(current_prices)

        # Update peak and drawdown
        if equity > self.peak_equity:
            self.peak_equity = equity

        drawdown_percent = 0.0
        if self.peak_equity > 0:
            drawdown_percent = ((self.peak_equity - equity) / self.peak_equity) * 100.0

        if drawdown_percent > self.max_drawdown_percent:
            self.max_drawdown_percent = drawdown_percent

        self.equity_curve.append(EquityPoint(
            timestamp=timestamp,
            balance=self.balance,
            equity=equity,
            drawdown_percent=drawdown_percent
        ))

    def open_position(
        self,
        symbol: str,
        side: str,
        entry_price: float,
        position_size: float,
        stop_loss: float,
        take_profit: float,
        entry_time: datetime
    ) -> bool:
        """
        Open a new position.

        Returns:
            True if position opened successfully, False otherwise
        """
        if symbol in self.positions:
            logger.warning(f"Position already open for {symbol}")
            return False

        # Apply slippage
        if side == "long":
            actual_entry = entry_price * (1 + self.slippage_percent / 100.0)
        else:
            actual_entry = entry_price * (1 - self.slippage_percent / 100.0)

        # Calculate commission
        commission = (actual_entry * position_size) * (self.commission_percent / 100.0)

        # Check if sufficient balance
        required_margin = actual_entry * position_size + commission
        if required_margin > self.balance:
            logger.warning(f"Insufficient balance to open position: {required_margin} > {self.balance}")
            return False

        # Deduct commission from balance
        self.balance -= commission

        position = OpenPosition(
            symbol=symbol,
            side=side,
            entry_price=actual_entry,
            position_size=position_size,
            stop_loss=stop_loss,
            take_profit=take_profit,
            entry_time=entry_time
        )

        self.positions[symbol] = position
        logger.info(f"Opened {side} position: {symbol} @ {actual_entry:.5f}, size={position_size}")
        return True

    def close_position(
        self,
        symbol: str,
        exit_price: float,
        exit_time: datetime,
        reason: str = ""
    ) -> Optional[Trade]:
        """
        Close an open position.

        Returns:
            Trade object if successful, None otherwise
        """
        if symbol not in self.positions:
            logger.warning(f"No open position for {symbol}")
            return None

        position = self.positions[symbol]

        # Apply slippage
        if position.side == "long":
            actual_exit = exit_price * (1 - self.slippage_percent / 100.0)
        else:
            actual_exit = exit_price * (1 + self.slippage_percent / 100.0)

        # Calculate P&L
        pnl = self._calculate_pnl(
            side=position.side,
            entry_price=position.entry_price,
            exit_price=actual_exit,
            position_size=position.position_size
        )

        # Calculate commission
        commission = (actual_exit * position.position_size) * (self.commission_percent / 100.0)

        net_pnl = pnl - commission

        # Update balance
        self.balance += (position.entry_price * position.position_size) + net_pnl

        # Create trade record
        trade = Trade(
            entry_time=position.entry_time,
            exit_time=exit_time,
            symbol=symbol,
            side=position.side,
            entry_price=position.entry_price,
            exit_price=actual_exit,
            position_size=position.position_size,
            pnl=pnl,
            commission=commission,
            net_pnl=net_pnl,
            reason=reason
        )

        self.trade_history.append(trade)
        del self.positions[symbol]

        logger.info(f"Closed {position.side} position: {symbol} @ {actual_exit:.5f}, P&L={net_pnl:.2f}")
        return trade

    def check_stop_loss_take_profit(
        self,
        symbol: str,
        current_high: float,
        current_low: float,
        current_time: datetime
    ) -> Optional[Trade]:
        """
        Check if position hit stop loss or take profit.

        Returns:
            Trade object if position closed, None otherwise
        """
        if symbol not in self.positions:
            return None

        position = self.positions[symbol]

        if position.side == "long":
            # Check stop loss
            if current_low <= position.stop_loss:
                return self.close_position(symbol, position.stop_loss, current_time, "Stop Loss")

            # Check take profit
            if current_high >= position.take_profit:
                return self.close_position(symbol, position.take_profit, current_time, "Take Profit")

        else:  # short
            # Check stop loss
            if current_high >= position.stop_loss:
                return self.close_position(symbol, position.stop_loss, current_time, "Stop Loss")

            # Check take profit
            if current_low <= position.take_profit:
                return self.close_position(symbol, position.take_profit, current_time, "Take Profit")

        return None

    def _calculate_pnl(
        self,
        side: str,
        entry_price: float,
        exit_price: float,
        position_size: float
    ) -> float:
        """Calculate P&L for a position."""
        if side == "long":
            pnl = (exit_price - entry_price) * position_size
        else:
            pnl = (entry_price - exit_price) * position_size

        return pnl

    def get_open_position(self, symbol: str) -> Optional[OpenPosition]:
        """Get open position for symbol."""
        return self.positions.get(symbol)

    def has_open_position(self, symbol: str) -> bool:
        """Check if there's an open position for symbol."""
        return symbol in self.positions
```

### Step 3: Performance Calculator

Create `backend/app/backtest/performance.py`:

```python
from typing import List
import math
from app.backtest.portfolio import Trade, EquityPoint
import logging

logger = logging.getLogger(__name__)


class PerformanceMetrics:
    """Calculate performance metrics from backtest results."""

    def __init__(
        self,
        initial_balance: float,
        final_balance: float,
        trades: List[Trade],
        equity_curve: List[EquityPoint],
        days: int
    ):
        self.initial_balance = initial_balance
        self.final_balance = final_balance
        self.trades = trades
        self.equity_curve = equity_curve
        self.days = days

    def calculate_all(self) -> dict:
        """Calculate all performance metrics."""
        return {
            "total_return_percent": self.total_return_percent(),
            "annualized_return_percent": self.annualized_return_percent(),
            "total_trades": len(self.trades),
            "winning_trades": self.winning_trades(),
            "losing_trades": self.losing_trades(),
            "win_rate_percent": self.win_rate_percent(),
            "gross_profit": self.gross_profit(),
            "gross_loss": self.gross_loss(),
            "net_profit": self.net_profit(),
            "profit_factor": self.profit_factor(),
            "avg_win": self.avg_win(),
            "avg_loss": self.avg_loss(),
            "largest_win": self.largest_win(),
            "largest_loss": self.largest_loss(),
            "max_drawdown_percent": self.max_drawdown_percent(),
            "avg_drawdown_percent": self.avg_drawdown_percent(),
            "sharpe_ratio": self.sharpe_ratio(),
            "sortino_ratio": self.sortino_ratio(),
            "expectancy": self.expectancy(),
            "recovery_factor": self.recovery_factor(),
        }

    def total_return_percent(self) -> float:
        """Total return percentage."""
        if self.initial_balance == 0:
            return 0.0
        return ((self.final_balance - self.initial_balance) / self.initial_balance) * 100.0

    def annualized_return_percent(self) -> float:
        """Annualized return percentage."""
        if self.days == 0 or self.initial_balance == 0:
            return 0.0

        years = self.days / 365.0
        if years == 0:
            return 0.0

        total_return = self.final_balance / self.initial_balance
        annualized = (total_return ** (1 / years) - 1) * 100.0
        return annualized

    def winning_trades(self) -> int:
        """Count of winning trades."""
        return sum(1 for t in self.trades if t.net_pnl > 0)

    def losing_trades(self) -> int:
        """Count of losing trades."""
        return sum(1 for t in self.trades if t.net_pnl <= 0)

    def win_rate_percent(self) -> float:
        """Win rate percentage."""
        if len(self.trades) == 0:
            return 0.0
        return (self.winning_trades() / len(self.trades)) * 100.0

    def gross_profit(self) -> float:
        """Total profit from winning trades."""
        return sum(t.net_pnl for t in self.trades if t.net_pnl > 0)

    def gross_loss(self) -> float:
        """Total loss from losing trades (absolute value)."""
        return abs(sum(t.net_pnl for t in self.trades if t.net_pnl <= 0))

    def net_profit(self) -> float:
        """Net profit (gross profit - gross loss)."""
        return self.gross_profit() - self.gross_loss()

    def profit_factor(self) -> float:
        """Profit factor (gross profit / gross loss)."""
        gross_loss = self.gross_loss()
        if gross_loss == 0:
            return 0.0 if self.gross_profit() == 0 else float('inf')
        return self.gross_profit() / gross_loss

    def avg_win(self) -> float:
        """Average winning trade."""
        wins = [t.net_pnl for t in self.trades if t.net_pnl > 0]
        return sum(wins) / len(wins) if wins else 0.0

    def avg_loss(self) -> float:
        """Average losing trade (absolute value)."""
        losses = [abs(t.net_pnl) for t in self.trades if t.net_pnl <= 0]
        return sum(losses) / len(losses) if losses else 0.0

    def largest_win(self) -> float:
        """Largest winning trade."""
        wins = [t.net_pnl for t in self.trades if t.net_pnl > 0]
        return max(wins) if wins else 0.0

    def largest_loss(self) -> float:
        """Largest losing trade (absolute value)."""
        losses = [abs(t.net_pnl) for t in self.trades if t.net_pnl <= 0]
        return max(losses) if losses else 0.0

    def max_drawdown_percent(self) -> float:
        """Maximum drawdown percentage."""
        if not self.equity_curve:
            return 0.0
        return max(ep.drawdown_percent for ep in self.equity_curve)

    def avg_drawdown_percent(self) -> float:
        """Average drawdown percentage."""
        if not self.equity_curve:
            return 0.0
        drawdowns = [ep.drawdown_percent for ep in self.equity_curve if ep.drawdown_percent > 0]
        return sum(drawdowns) / len(drawdowns) if drawdowns else 0.0

    def sharpe_ratio(self, risk_free_rate: float = 0.0) -> float:
        """
        Sharpe ratio (risk-adjusted return).

        Assumes risk_free_rate is annualized percentage.
        """
        if len(self.trades) < 2:
            return 0.0

        returns = [t.net_pnl / self.initial_balance for t in self.trades]
        avg_return = sum(returns) / len(returns)

        variance = sum((r - avg_return) ** 2 for r in returns) / (len(returns) - 1)
        std_dev = math.sqrt(variance)

        if std_dev == 0:
            return 0.0

        # Annualize
        periods_per_year = 365.0 / self.days * len(self.trades) if self.days > 0 else 1
        annualized_return = avg_return * periods_per_year * 100.0
        annualized_std = std_dev * math.sqrt(periods_per_year) * 100.0

        sharpe = (annualized_return - risk_free_rate) / annualized_std if annualized_std > 0 else 0.0
        return sharpe

    def sortino_ratio(self, risk_free_rate: float = 0.0) -> float:
        """
        Sortino ratio (downside risk-adjusted return).

        Only considers downside volatility.
        """
        if len(self.trades) < 2:
            return 0.0

        returns = [t.net_pnl / self.initial_balance for t in self.trades]
        avg_return = sum(returns) / len(returns)

        # Downside deviation (only negative returns)
        downside_returns = [r for r in returns if r < 0]
        if not downside_returns:
            return 0.0

        downside_variance = sum(r ** 2 for r in downside_returns) / len(downside_returns)
        downside_std = math.sqrt(downside_variance)

        if downside_std == 0:
            return 0.0

        # Annualize
        periods_per_year = 365.0 / self.days * len(self.trades) if self.days > 0 else 1
        annualized_return = avg_return * periods_per_year * 100.0
        annualized_downside_std = downside_std * math.sqrt(periods_per_year) * 100.0

        sortino = (annualized_return - risk_free_rate) / annualized_downside_std if annualized_downside_std > 0 else 0.0
        return sortino

    def expectancy(self) -> float:
        """
        Expectancy (average expected profit per trade).

        Formula: (Win% * AvgWin) - (Loss% * AvgLoss)
        """
        if len(self.trades) == 0:
            return 0.0

        win_rate = self.win_rate_percent() / 100.0
        loss_rate = 1 - win_rate

        expectancy = (win_rate * self.avg_win()) - (loss_rate * self.avg_loss())
        return expectancy

    def recovery_factor(self) -> float:
        """
        Recovery factor (net profit / max drawdown).

        Higher is better. Measures how much profit is made per unit of risk.
        """
        max_dd = self.max_drawdown_percent()
        if max_dd == 0:
            return 0.0

        # Convert to dollar drawdown
        max_dd_dollars = (max_dd / 100.0) * self.initial_balance
        if max_dd_dollars == 0:
            return 0.0

        return self.net_profit() / max_dd_dollars
```

### Step 4: Backtest Engine

Create `backend/app/backtest/engine.py`:

```python
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.market_data import Candle
from app.models.signal import Signal, SignalType
from app.strategies.base_strategy import BaseStrategy
from app.backtest.portfolio import Portfolio, Trade
from app.backtest.performance import PerformanceMetrics
import logging
import time

logger = logging.getLogger(__name__)


class BacktestEngine:
    """
    Backtesting engine that simulates strategy execution on historical data.
    """

    def __init__(
        self,
        strategy: BaseStrategy,
        candles: List[Candle],
        initial_balance: float = 10000.0,
        commission_percent: float = 0.1,
        slippage_percent: float = 0.05,
        risk_per_trade_percent: float = 2.0
    ):
        self.strategy = strategy
        self.candles = sorted(candles, key=lambda c: c.timestamp)  # Ensure chronological order
        self.initial_balance = initial_balance
        self.commission_percent = commission_percent
        self.slippage_percent = slippage_percent
        self.risk_per_trade_percent = risk_per_trade_percent

        self.portfolio = Portfolio(
            initial_balance=initial_balance,
            commission_percent=commission_percent,
            slippage_percent=slippage_percent
        )

    async def run(self) -> Dict[str, Any]:
        """
        Run backtest simulation.

        Returns:
            Dictionary with performance metrics and results
        """
        start_time = time.time()

        logger.info(f"Starting backtest for {self.strategy.get_name()} on {len(self.candles)} candles")

        # Replay historical data candle by candle
        for i in range(len(self.candles)):
            current_candle = self.candles[i]
            historical_candles = self.candles[:i+1]  # All candles up to current

            # Check stop loss / take profit for open positions
            if self.portfolio.has_open_position(current_candle.symbol):
                self.portfolio.check_stop_loss_take_profit(
                    symbol=current_candle.symbol,
                    current_high=current_candle.high,
                    current_low=current_candle.low,
                    current_time=current_candle.timestamp
                )

            # Update equity curve
            current_prices = {current_candle.symbol: current_candle.close}
            self.portfolio.update_equity_curve(current_candle.timestamp, current_prices)

            # Run strategy analysis if we have enough data
            min_candles = 50  # Minimum candles needed
            if len(historical_candles) >= min_candles:
                signals = await self.strategy.analyze(
                    symbol=current_candle.symbol,
                    candles=historical_candles,
                    current_price=current_candle.close
                )

                # Execute signals (only if no open position)
                for signal in signals:
                    if not self.portfolio.has_open_position(signal.symbol):
                        self._execute_signal(signal, current_candle.timestamp)

        # Close any remaining open positions at final price
        if self.candles:
            final_candle = self.candles[-1]
            for symbol in list(self.portfolio.positions.keys()):
                self.portfolio.close_position(
                    symbol=symbol,
                    exit_price=final_candle.close,
                    exit_time=final_candle.timestamp,
                    reason="Backtest end"
                )

        # Calculate performance metrics
        days = (self.candles[-1].timestamp - self.candles[0].timestamp).days if self.candles else 1

        metrics_calc = PerformanceMetrics(
            initial_balance=self.initial_balance,
            final_balance=self.portfolio.balance,
            trades=self.portfolio.trade_history,
            equity_curve=self.portfolio.equity_curve,
            days=max(days, 1)
        )

        metrics = metrics_calc.calculate_all()

        execution_time = time.time() - start_time

        # Prepare results
        results = {
            "strategy_name": self.strategy.get_name(),
            "symbol": self.candles[0].symbol if self.candles else "",
            "interval": self.candles[0].interval if self.candles else "",
            "start_date": self.candles[0].timestamp if self.candles else datetime.utcnow(),
            "end_date": self.candles[-1].timestamp if self.candles else datetime.utcnow(),
            "initial_balance": self.initial_balance,
            "final_balance": self.portfolio.balance,
            "commission_percent": self.commission_percent,
            "slippage_percent": self.slippage_percent,
            "execution_time_seconds": execution_time,
            **metrics,
            "equity_curve": [
                {
                    "timestamp": ep.timestamp.isoformat(),
                    "balance": ep.balance,
                    "equity": ep.equity,
                    "drawdown_percent": ep.drawdown_percent
                }
                for ep in self.portfolio.equity_curve
            ],
            "trade_log": [
                {
                    "entry_time": t.entry_time.isoformat(),
                    "exit_time": t.exit_time.isoformat(),
                    "symbol": t.symbol,
                    "side": t.side,
                    "entry_price": t.entry_price,
                    "exit_price": t.exit_price,
                    "position_size": t.position_size,
                    "pnl": t.pnl,
                    "commission": t.commission,
                    "net_pnl": t.net_pnl,
                    "reason": t.reason
                }
                for t in self.portfolio.trade_history
            ]
        }

        logger.info(f"Backtest completed in {execution_time:.2f}s: {metrics['total_trades']} trades, "
                    f"{metrics['total_return_percent']:.2f}% return, {metrics['max_drawdown_percent']:.2f}% max DD")

        return results

    def _execute_signal(self, signal: Signal, current_time: datetime):
        """Execute a trading signal."""
        # Calculate position size based on risk
        position_size = self.strategy.calculate_position_size(
            account_balance=self.portfolio.balance,
            risk_percent=self.risk_per_trade_percent,
            entry_price=signal.entry_price,
            stop_loss=signal.stop_loss
        )

        if position_size <= 0:
            logger.warning(f"Invalid position size: {position_size}")
            return

        side = "long" if signal.signal_type == SignalType.LONG else "short"

        success = self.portfolio.open_position(
            symbol=signal.symbol,
            side=side,
            entry_price=signal.entry_price,
            position_size=position_size,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            entry_time=current_time
        )

        if success:
            logger.debug(f"Executed {side} signal for {signal.symbol} @ {signal.entry_price:.5f}")
        else:
            logger.warning(f"Failed to execute signal for {signal.symbol}")
```

### Step 5: Database Migration

```bash
cd backend
DATABASE_URL="sqlite+aiosqlite:///./flowrex_dev.db" python -m alembic revision --autogenerate -m "add_backtest_results"
```

Run migration:
```bash
DATABASE_URL="sqlite+aiosqlite:///./flowrex_dev.db" python -m alembic upgrade head
```

### Step 6: API Routes

Create `backend/app/api/v1/backtest_routes.py`:

```python
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
from typing import List, Optional
from pydantic import BaseModel
from app.database import get_db
from app.data.data_service import DataService
from app.data.twelvedata_client import TwelveDataClient
from app.strategies.strategy_manager import StrategyManager
from app.backtest.engine import BacktestEngine
from app.models.backtest import BacktestResult
from sqlalchemy import select, desc
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/backtest", tags=["backtest"])


class BacktestRequest(BaseModel):
    strategy_name: str
    symbol: str
    interval: str = "1h"
    start_date: datetime
    end_date: datetime
    initial_balance: float = 10000.0
    commission_percent: float = 0.1
    slippage_percent: float = 0.05
    risk_per_trade_percent: float = 2.0


class BacktestResultResponse(BaseModel):
    id: int
    strategy_name: str
    symbol: str
    interval: str
    start_date: datetime
    end_date: datetime
    initial_balance: float
    final_balance: float
    total_return_percent: float
    total_trades: int
    win_rate_percent: float
    profit_factor: float | None
    max_drawdown_percent: float
    sharpe_ratio: float | None
    created_at: datetime

    class Config:
        from_attributes = True


@router.post("/run")
async def run_backtest(
    request: BacktestRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Run a backtest for a strategy on historical data.

    Returns detailed performance metrics and equity curve.
    """
    async with TwelveDataClient() as client:
        # Get historical candles
        data_service = DataService(db=db, client=client)

        candles = await data_service.get_candles(
            symbol=request.symbol,
            interval=request.interval,
            start_date=request.start_date,
            end_date=request.end_date
        )

        if not candles:
            # Fetch if missing
            logger.info(f"Fetching historical data for {request.symbol}")
            await data_service.fetch_and_store_candles(
                symbol=request.symbol,
                interval=request.interval,
                start_date=request.start_date,
                end_date=request.end_date
            )
            candles = await data_service.get_candles(
                symbol=request.symbol,
                interval=request.interval,
                start_date=request.start_date,
                end_date=request.end_date
            )

        if not candles:
            raise HTTPException(
                status_code=404,
                detail=f"No historical data available for {request.symbol}"
            )

        # Get strategy
        manager = StrategyManager(db=db)
        strategy = manager.get_strategy(request.strategy_name)

        # Run backtest
        engine = BacktestEngine(
            strategy=strategy,
            candles=candles,
            initial_balance=request.initial_balance,
            commission_percent=request.commission_percent,
            slippage_percent=request.slippage_percent,
            risk_per_trade_percent=request.risk_per_trade_percent
        )

        results = await engine.run()

        # Save results to database
        backtest_result = BacktestResult(
            strategy_name=results["strategy_name"],
            symbol=results["symbol"],
            interval=results["interval"],
            start_date=results["start_date"],
            end_date=results["end_date"],
            initial_balance=results["initial_balance"],
            final_balance=results["final_balance"],
            commission_percent=results["commission_percent"],
            slippage_percent=results["slippage_percent"],
            strategy_config=strategy.config,
            total_return_percent=results["total_return_percent"],
            annualized_return_percent=results["annualized_return_percent"],
            total_trades=results["total_trades"],
            winning_trades=results["winning_trades"],
            losing_trades=results["losing_trades"],
            win_rate_percent=results["win_rate_percent"],
            gross_profit=results["gross_profit"],
            gross_loss=results["gross_loss"],
            net_profit=results["net_profit"],
            profit_factor=results["profit_factor"],
            avg_win=results["avg_win"],
            avg_loss=results["avg_loss"],
            largest_win=results["largest_win"],
            largest_loss=results["largest_loss"],
            max_drawdown_percent=results["max_drawdown_percent"],
            avg_drawdown_percent=results["avg_drawdown_percent"],
            sharpe_ratio=results["sharpe_ratio"],
            sortino_ratio=results["sortino_ratio"],
            expectancy=results["expectancy"],
            recovery_factor=results["recovery_factor"],
            equity_curve=results["equity_curve"],
            trade_log=results["trade_log"],
            execution_time_seconds=results["execution_time_seconds"]
        )

        db.add(backtest_result)
        await db.commit()
        await db.refresh(backtest_result)

        logger.info(f"Backtest saved with ID {backtest_result.id}")

        return results


@router.get("/results", response_model=List[BacktestResultResponse])
async def get_backtest_results(
    strategy_name: Optional[str] = None,
    symbol: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """Get backtest results with optional filters."""
    stmt = select(BacktestResult)

    if strategy_name:
        stmt = stmt.where(BacktestResult.strategy_name == strategy_name)
    if symbol:
        stmt = stmt.where(BacktestResult.symbol == symbol)

    stmt = stmt.order_by(desc(BacktestResult.created_at)).limit(limit)

    result = await db.execute(stmt)
    backtests = result.scalars().all()

    return backtests


@router.get("/results/{backtest_id}")
async def get_backtest_detail(backtest_id: int, db: AsyncSession = Depends(get_db)):
    """Get detailed backtest results including equity curve and trade log."""
    stmt = select(BacktestResult).where(BacktestResult.id == backtest_id)
    result = await db.execute(stmt)
    backtest = result.scalar_one_or_none()

    if not backtest:
        raise HTTPException(status_code=404, detail="Backtest not found")

    return {
        "id": backtest.id,
        "strategy_name": backtest.strategy_name,
        "symbol": backtest.symbol,
        "interval": backtest.interval,
        "start_date": backtest.start_date,
        "end_date": backtest.end_date,
        "initial_balance": backtest.initial_balance,
        "final_balance": backtest.final_balance,
        "total_return_percent": backtest.total_return_percent,
        "annualized_return_percent": backtest.annualized_return_percent,
        "total_trades": backtest.total_trades,
        "winning_trades": backtest.winning_trades,
        "losing_trades": backtest.losing_trades,
        "win_rate_percent": backtest.win_rate_percent,
        "profit_factor": backtest.profit_factor,
        "max_drawdown_percent": backtest.max_drawdown_percent,
        "sharpe_ratio": backtest.sharpe_ratio,
        "sortino_ratio": backtest.sortino_ratio,
        "equity_curve": backtest.equity_curve,
        "trade_log": backtest.trade_log,
        "strategy_config": backtest.strategy_config
    }
```

Register routes in `backend/app/main.py`:

```python
from app.api.v1 import auth_routes, data_routes, strategy_routes, backtest_routes

app.include_router(backtest_routes.router, prefix="/api/v1")
```

### Step 7: Tests

Create `backend/tests/unit/test_backtest.py`:

```python
import pytest
from datetime import datetime, timedelta
from app.backtest.portfolio import Portfolio
from app.backtest.performance import PerformanceMetrics
from app.backtest.portfolio import Trade, EquityPoint


class TestPortfolio:
    def test_portfolio_initialization(self):
        portfolio = Portfolio(initial_balance=10000.0, commission_percent=0.1)
        assert portfolio.balance == 10000.0
        assert portfolio.initial_balance == 10000.0
        assert len(portfolio.positions) == 0

    def test_open_long_position(self):
        portfolio = Portfolio(initial_balance=10000.0, commission_percent=0.1, slippage_percent=0.05)

        success = portfolio.open_position(
            symbol="EURUSD",
            side="long",
            entry_price=1.1000,
            position_size=100,
            stop_loss=1.0950,
            take_profit=1.1100,
            entry_time=datetime.utcnow()
        )

        assert success is True
        assert "EURUSD" in portfolio.positions
        assert portfolio.balance < 10000.0  # Commission deducted

    def test_close_position_profit(self):
        portfolio = Portfolio(initial_balance=10000.0, commission_percent=0.0, slippage_percent=0.0)

        portfolio.open_position(
            symbol="EURUSD",
            side="long",
            entry_price=1.1000,
            position_size=100,
            stop_loss=1.0950,
            take_profit=1.1100,
            entry_time=datetime.utcnow()
        )

        trade = portfolio.close_position(
            symbol="EURUSD",
            exit_price=1.1050,
            exit_time=datetime.utcnow(),
            reason="Take Profit"
        )

        assert trade is not None
        assert trade.net_pnl > 0  # Profitable trade
        assert portfolio.balance > 10000.0

    def test_stop_loss_hit(self):
        portfolio = Portfolio(initial_balance=10000.0, commission_percent=0.0, slippage_percent=0.0)

        portfolio.open_position(
            symbol="EURUSD",
            side="long",
            entry_price=1.1000,
            position_size=100,
            stop_loss=1.0950,
            take_profit=1.1100,
            entry_time=datetime.utcnow()
        )

        trade = portfolio.check_stop_loss_take_profit(
            symbol="EURUSD",
            current_high=1.1010,
            current_low=1.0945,  # Hits stop loss
            current_time=datetime.utcnow()
        )

        assert trade is not None
        assert trade.reason == "Stop Loss"
        assert trade.net_pnl < 0


class TestPerformanceMetrics:
    def test_total_return_calculation(self):
        trades = []
        equity_curve = []

        metrics = PerformanceMetrics(
            initial_balance=10000.0,
            final_balance=12000.0,
            trades=trades,
            equity_curve=equity_curve,
            days=365
        )

        assert metrics.total_return_percent() == 20.0

    def test_win_rate_calculation(self):
        trades = [
            Trade(
                entry_time=datetime.utcnow(),
                exit_time=datetime.utcnow(),
                symbol="EURUSD",
                side="long",
                entry_price=1.1000,
                exit_price=1.1050,
                position_size=100,
                pnl=5.0,
                commission=0.1,
                net_pnl=4.9,
                reason="TP"
            ),
            Trade(
                entry_time=datetime.utcnow(),
                exit_time=datetime.utcnow(),
                symbol="EURUSD",
                side="long",
                entry_price=1.1000,
                exit_price=1.0950,
                position_size=100,
                pnl=-5.0,
                commission=0.1,
                net_pnl=-5.1,
                reason="SL"
            ),
        ]

        metrics = PerformanceMetrics(
            initial_balance=10000.0,
            final_balance=10000.0,
            trades=trades,
            equity_curve=[],
            days=30
        )

        assert metrics.win_rate_percent() == 50.0
        assert metrics.winning_trades() == 1
        assert metrics.losing_trades() == 1
```

Run tests:
```bash
cd backend
DATABASE_URL="sqlite+aiosqlite:///./flowrex_dev.db" python -m pytest tests/unit/test_backtest.py -v
```

### Step 8: Manual Testing

Start server:
```bash
cd backend
DATABASE_URL="sqlite+aiosqlite:///./flowrex_dev.db" python -m uvicorn app.main:app --reload
```

Run backtest via API:

```bash
curl -X POST "http://localhost:8000/api/v1/backtest/run" \
  -H "Content-Type: application/json" \
  -d '{
    "strategy_name": "NBB",
    "symbol": "EURUSD",
    "interval": "1h",
    "start_date": "2024-01-01T00:00:00Z",
    "end_date": "2024-12-01T00:00:00Z",
    "initial_balance": 10000.0,
    "commission_percent": 0.1,
    "slippage_percent": 0.05,
    "risk_per_trade_percent": 2.0
  }'
```

Get backtest results:
```bash
curl "http://localhost:8000/api/v1/backtest/results?strategy_name=NBB&limit=10"
```

Get detailed backtest:
```bash
curl "http://localhost:8000/api/v1/backtest/results/1"
```

## Validation Checklist

Before proceeding to Prompt 06, verify:

- [ ] BacktestResult model created
- [ ] Database migration applied successfully
- [ ] `backtest_results` table exists with JSON columns for equity_curve and trade_log
- [ ] Portfolio class tracks balance, positions, trades
- [ ] Portfolio correctly calculates P&L for long and short positions
- [ ] Portfolio applies commission and slippage
- [ ] Portfolio checks stop loss and take profit
- [ ] PerformanceMetrics calculates all metrics (return, Sharpe, drawdown, etc.)
- [ ] BacktestEngine replays historical data chronologically
- [ ] BacktestEngine executes strategy signals
- [ ] BacktestEngine generates equity curve
- [ ] API route `/backtest/run` executes backtests
- [ ] API route `/backtest/results` retrieves results
- [ ] All unit tests pass
- [ ] Can run backtest for NBB strategy via API
- [ ] Backtest returns metrics: return, win rate, profit factor, Sharpe, max DD
- [ ] Trade log includes all executed trades with P&L
- [ ] Equity curve shows balance progression over time
- [ ] CROSSCHECK.md validation for Prompt 05 completed

## Hard Stop Criteria

**DO NOT PROCEED to Prompt 06 unless:**

1. ✅ Database migration runs without errors
2. ✅ All pytest tests pass (0 failures, 0 errors)
3. ✅ Portfolio simulator correctly handles long and short positions
4. ✅ Portfolio applies commission and slippage to all trades
5. ✅ Stop loss and take profit execution works correctly
6. ✅ Performance metrics calculate accurately (verified manually)
7. ✅ Can run complete backtest via API and receive results
8. ✅ Backtest results saved to database with all metrics
9. ✅ Equity curve and trade log are properly formatted
10. ✅ CROSSCHECK.md section for Prompt 05 fully validated

If any criterion fails, **HALT** and fix before continuing.

---

**Completion Criteria:**
- Backtest engine fully operational
- Can simulate strategy execution on historical data
- Performance metrics accurately calculated
- Results stored in database with equity curves
- System ready for Optimization Engine (Prompt 06)
