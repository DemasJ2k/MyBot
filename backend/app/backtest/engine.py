"""
Backtest engine for running strategy simulations.

Orchestrates the backtesting process using historical data.
Prompt 05 - Backtest Engine.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Type
import logging

from app.backtest.portfolio import Portfolio, TradeSide
from app.backtest.performance import PerformanceMetrics
from app.strategies.base_strategy import BaseStrategy
from app.models.market_data import Candle

logger = logging.getLogger(__name__)


@dataclass
class BacktestConfig:
    """Configuration for a backtest run."""
    strategy_class: Type[BaseStrategy]
    strategy_params: dict
    symbol: str
    timeframe: str
    start_date: datetime
    end_date: datetime
    initial_capital: float = 10000.0
    commission_rate: float = 0.001  # 0.1%
    position_size_pct: float = 0.02  # 2% of capital per trade
    risk_free_rate: float = 0.02  # 2% annual
    
    def __post_init__(self):
        """Validate configuration."""
        if self.initial_capital <= 0:
            raise ValueError("Initial capital must be positive")
        if self.position_size_pct <= 0 or self.position_size_pct > 1:
            raise ValueError("Position size percentage must be between 0 and 1")
        if self.start_date >= self.end_date:
            raise ValueError("Start date must be before end date")


@dataclass
class BacktestResult:
    """Container for backtest results."""
    config: BacktestConfig
    portfolio: Portfolio
    metrics: PerformanceMetrics
    
    def to_dict(self) -> dict:
        """Convert result to dictionary for API response."""
        return {
            "config": {
                "strategy_name": self.config.strategy_class.__name__,
                "strategy_params": self.config.strategy_params,
                "symbol": self.config.symbol,
                "timeframe": self.config.timeframe,
                "start_date": self.config.start_date.isoformat(),
                "end_date": self.config.end_date.isoformat(),
                "initial_capital": self.config.initial_capital,
                "commission_rate": self.config.commission_rate,
                "position_size_pct": self.config.position_size_pct,
            },
            "metrics": self.metrics.to_dict(),
            "equity_curve": self.portfolio.get_equity_curve_dict(),
            "trade_log": self.portfolio.get_trade_log_dict(),
        }


class BacktestEngine:
    """
    Engine for running backtests on historical data.
    
    The engine:
    1. Takes a strategy and historical candle data
    2. Iterates through candles chronologically
    3. Generates signals from the strategy
    4. Executes simulated trades through Portfolio
    5. Tracks equity curve and calculates performance metrics
    
    Example:
        engine = BacktestEngine(config)
        result = engine.run(candles)
        print(result.metrics.summary())
    """
    
    def __init__(self, config: BacktestConfig):
        """
        Initialize the backtest engine.
        
        Args:
            config: BacktestConfig with strategy and parameters
        """
        self.config = config
        self.portfolio: Optional[Portfolio] = None
        self.strategy: Optional[BaseStrategy] = None
        
    def run(self, candles: list[Candle]) -> BacktestResult:
        """
        Run the backtest on historical candle data.
        
        Args:
            candles: List of Candle objects sorted by timestamp ascending
            
        Returns:
            BacktestResult containing portfolio, metrics, and config
        """
        if not candles:
            raise ValueError("No candle data provided for backtest")
        
        logger.info(
            f"Starting backtest: {self.config.strategy_class.__name__} "
            f"on {self.config.symbol} from {self.config.start_date} to {self.config.end_date}"
        )
        
        # Initialize portfolio
        self.portfolio = Portfolio(
            initial_balance=self.config.initial_capital,
            commission_rate=self.config.commission_rate,
        )
        
        # Initialize strategy
        self.strategy = self.config.strategy_class(**self.config.strategy_params)
        
        # Filter candles to date range
        filtered_candles = self._filter_candles(candles)
        
        if not filtered_candles:
            raise ValueError("No candles within specified date range")
        
        logger.info(f"Processing {len(filtered_candles)} candles")
        
        # Build candle history for strategy lookback
        candle_history: list[Candle] = []
        
        # Process each candle
        for candle in filtered_candles:
            # Add candle to history
            candle_history.append(candle)
            
            # Update current prices for equity calculation
            current_prices = {self.config.symbol: candle.close}
            
            # Check stop-loss/take-profit on existing positions
            self.portfolio.check_stop_loss_take_profit(
                candle.close,
                candle.timestamp
            )
            
            # Generate signal from strategy
            signal = self.strategy.generate_signal(
                candle_history,
                self.config.symbol
            )
            
            # Process signal
            if signal:
                self._process_signal(signal, candle)
            
            # Update portfolio equity
            self.portfolio.update_equity(current_prices, candle.timestamp)
        
        # Close any remaining open positions at the end
        self._close_remaining_positions(filtered_candles[-1])
        
        # Calculate final metrics
        metrics = PerformanceMetrics.from_portfolio(
            self.portfolio,
            risk_free_rate=self.config.risk_free_rate
        )
        
        logger.info(f"Backtest completed. Total return: {metrics.total_return:.2%}")
        
        return BacktestResult(
            config=self.config,
            portfolio=self.portfolio,
            metrics=metrics,
        )
    
    def _filter_candles(self, candles: list[Candle]) -> list[Candle]:
        """
        Filter candles to the configured date range.
        
        Args:
            candles: All available candles
            
        Returns:
            Candles within start_date and end_date
        """
        filtered = []
        
        for candle in candles:
            # Handle both timezone-aware and naive datetimes
            candle_time = candle.timestamp
            start = self.config.start_date
            end = self.config.end_date
            
            # Make comparison work regardless of timezone awareness
            if candle_time.tzinfo is not None and start.tzinfo is None:
                candle_time = candle_time.replace(tzinfo=None)
            
            if start <= candle_time <= end:
                filtered.append(candle)
        
        return sorted(filtered, key=lambda c: c.timestamp)
    
    def _process_signal(self, signal: dict, candle: Candle):
        """
        Process a strategy signal and execute trade if appropriate.
        
        Args:
            signal: Signal dictionary from strategy
            candle: Current candle for timing
        """
        signal_type = signal.get("type", "").upper()
        
        if signal_type == "BUY":
            self._handle_buy_signal(signal, candle)
        elif signal_type == "SELL":
            self._handle_sell_signal(signal, candle)
        elif signal_type == "CLOSE":
            self._handle_close_signal(candle)
    
    def _handle_buy_signal(self, signal: dict, candle: Candle):
        """
        Handle a BUY signal - open a long position.
        
        Args:
            signal: Signal dictionary with optional SL/TP
            candle: Current candle
        """
        # Don't open if we already have a position
        if self.portfolio.has_open_position(self.config.symbol):
            logger.debug(f"Already have position in {self.config.symbol}, skipping BUY")
            return
        
        # Calculate position size
        quantity = self._calculate_position_size(candle.close)
        
        if quantity <= 0:
            logger.debug("Position size too small, skipping trade")
            return
        
        # Extract stop-loss and take-profit from signal
        stop_loss = signal.get("stop_loss")
        take_profit = signal.get("take_profit")
        
        self.portfolio.open_position(
            symbol=self.config.symbol,
            side=TradeSide.LONG,
            entry_price=candle.close,
            quantity=quantity,
            entry_time=candle.timestamp,
            stop_loss=stop_loss,
            take_profit=take_profit,
        )
    
    def _handle_sell_signal(self, signal: dict, candle: Candle):
        """
        Handle a SELL signal - close long or open short.
        
        For simplicity in this version, SELL closes existing long positions.
        Short selling can be added as an enhancement.
        
        Args:
            signal: Signal dictionary
            candle: Current candle
        """
        # If we have an open position, close it
        position = self.portfolio.get_position(self.config.symbol)
        
        if position and position.side == TradeSide.LONG:
            self.portfolio.close_position(
                position,
                exit_price=candle.close,
                exit_time=candle.timestamp,
            )
    
    def _handle_close_signal(self, candle: Candle):
        """
        Handle a CLOSE signal - close any open position.
        
        Args:
            candle: Current candle
        """
        position = self.portfolio.get_position(self.config.symbol)
        
        if position:
            self.portfolio.close_position(
                position,
                exit_price=candle.close,
                exit_time=candle.timestamp,
            )
    
    def _calculate_position_size(self, price: float) -> float:
        """
        Calculate position size based on config and available capital.
        
        Uses a percentage of current equity for position sizing.
        
        Args:
            price: Entry price
            
        Returns:
            Quantity to trade
        """
        # Use percentage of current equity
        position_value = self.portfolio.equity * self.config.position_size_pct
        
        if price <= 0:
            return 0.0
        
        quantity = position_value / price
        
        return quantity
    
    def _close_remaining_positions(self, last_candle: Candle):
        """
        Close any remaining open positions at the end of backtest.
        
        Args:
            last_candle: The final candle in the backtest
        """
        # Create a copy since we'll be modifying the list
        positions_to_close = self.portfolio.positions.copy()
        
        for position in positions_to_close:
            self.portfolio.close_position(
                position,
                exit_price=last_candle.close,
                exit_time=last_candle.timestamp,
            )
            logger.info(f"Closed remaining position in {position.symbol} at end of backtest")


def run_backtest(
    strategy_class: Type[BaseStrategy],
    strategy_params: dict,
    candles: list[Candle],
    symbol: str,
    timeframe: str,
    start_date: datetime,
    end_date: datetime,
    initial_capital: float = 10000.0,
    commission_rate: float = 0.001,
    position_size_pct: float = 0.02,
) -> BacktestResult:
    """
    Convenience function to run a backtest.
    
    Args:
        strategy_class: The strategy class to use
        strategy_params: Parameters to pass to strategy constructor
        candles: Historical candle data
        symbol: Trading symbol
        timeframe: Candle timeframe
        start_date: Backtest start date
        end_date: Backtest end date
        initial_capital: Starting capital
        commission_rate: Trading commission rate
        position_size_pct: Position size as percentage of equity
        
    Returns:
        BacktestResult with portfolio, metrics, and configuration
    """
    config = BacktestConfig(
        strategy_class=strategy_class,
        strategy_params=strategy_params,
        symbol=symbol,
        timeframe=timeframe,
        start_date=start_date,
        end_date=end_date,
        initial_capital=initial_capital,
        commission_rate=commission_rate,
        position_size_pct=position_size_pct,
    )
    
    engine = BacktestEngine(config)
    return engine.run(candles)
