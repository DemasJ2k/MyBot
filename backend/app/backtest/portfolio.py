"""
Portfolio simulator for backtesting.

Tracks positions, balance, equity curve, and P&L calculations.
Prompt 05 - Backtest Engine.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class TradeSide(str, Enum):
    """Trade direction."""
    LONG = "LONG"
    SHORT = "SHORT"


@dataclass
class Trade:
    """
    Represents a completed (closed) trade.
    
    Captures entry/exit details and resulting P&L for trade logging.
    """
    symbol: str
    side: TradeSide
    entry_price: float
    exit_price: float
    quantity: float
    entry_time: datetime
    exit_time: datetime
    pnl: float
    pnl_percent: float
    commission: float = 0.0
    
    def to_dict(self) -> dict:
        """Convert trade to dictionary for JSON serialization."""
        return {
            "symbol": self.symbol,
            "side": self.side.value,
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "quantity": self.quantity,
            "entry_time": self.entry_time.isoformat(),
            "exit_time": self.exit_time.isoformat(),
            "pnl": self.pnl,
            "pnl_percent": self.pnl_percent,
            "commission": self.commission,
        }


@dataclass
class OpenPosition:
    """
    Represents an open (active) position.
    
    Tracks entry details and optional stop-loss/take-profit levels.
    """
    symbol: str
    side: TradeSide
    entry_price: float
    quantity: float
    entry_time: datetime
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    
    def unrealized_pnl(self, current_price: float) -> float:
        """Calculate unrealized P&L at current price."""
        if self.side == TradeSide.LONG:
            return (current_price - self.entry_price) * self.quantity
        else:  # SHORT
            return (self.entry_price - current_price) * self.quantity
    
    def unrealized_pnl_percent(self, current_price: float) -> float:
        """Calculate unrealized P&L percentage."""
        position_value = self.entry_price * self.quantity
        if position_value == 0:
            return 0.0
        return self.unrealized_pnl(current_price) / position_value


@dataclass
class EquityPoint:
    """
    A single point on the equity curve.
    
    Records portfolio value at a specific timestamp.
    """
    timestamp: datetime
    equity: float
    drawdown: float = 0.0
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "equity": self.equity,
            "drawdown": self.drawdown,
        }


@dataclass
class Portfolio:
    """
    Simulates a trading portfolio during backtesting.
    
    Handles:
    - Position opening/closing
    - Balance and equity tracking
    - Stop-loss and take-profit checking
    - Trade logging
    - Equity curve recording
    
    Attributes:
        initial_balance: Starting capital
        balance: Current cash balance (excluding open positions)
        equity: Total portfolio value (balance + unrealized P&L)
        positions: List of currently open positions
        trades: List of completed trades
        equity_curve: Time series of equity values
        commission_rate: Trading commission as a percentage (default 0.1%)
    """
    initial_balance: float
    balance: float = field(init=False)
    equity: float = field(init=False)
    positions: list[OpenPosition] = field(default_factory=list)
    trades: list[Trade] = field(default_factory=list)
    equity_curve: list[EquityPoint] = field(default_factory=list)
    commission_rate: float = 0.001  # 0.1% default commission
    
    # Track peak equity for drawdown calculation
    _peak_equity: float = field(init=False, repr=False)
    
    def __post_init__(self):
        """Initialize balance and equity from initial_balance."""
        self.balance = self.initial_balance
        self.equity = self.initial_balance
        self._peak_equity = self.initial_balance
    
    def open_position(
        self,
        symbol: str,
        side: TradeSide,
        entry_price: float,
        quantity: float,
        entry_time: datetime,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None
    ) -> Optional[OpenPosition]:
        """
        Open a new position.
        
        Args:
            symbol: Trading symbol
            side: LONG or SHORT
            entry_price: Price at entry
            quantity: Position size
            entry_time: Timestamp of entry
            stop_loss: Optional stop-loss price
            take_profit: Optional take-profit price
            
        Returns:
            The opened position, or None if insufficient balance
        """
        # Calculate required margin (full position value for now)
        position_value = entry_price * quantity
        commission = position_value * self.commission_rate
        
        required_capital = position_value + commission
        
        if required_capital > self.balance:
            logger.warning(
                f"Insufficient balance to open position. "
                f"Required: {required_capital:.2f}, Available: {self.balance:.2f}"
            )
            return None
        
        # Deduct from balance
        self.balance -= required_capital
        
        position = OpenPosition(
            symbol=symbol,
            side=side,
            entry_price=entry_price,
            quantity=quantity,
            entry_time=entry_time,
            stop_loss=stop_loss,
            take_profit=take_profit,
        )
        
        self.positions.append(position)
        
        logger.info(
            f"Opened {side.value} position: {symbol} @ {entry_price:.4f}, "
            f"qty={quantity}, SL={stop_loss}, TP={take_profit}"
        )
        
        return position
    
    def close_position(
        self,
        position: OpenPosition,
        exit_price: float,
        exit_time: datetime
    ) -> Trade:
        """
        Close an existing position.
        
        Args:
            position: The position to close
            exit_price: Price at exit
            exit_time: Timestamp of exit
            
        Returns:
            The completed Trade record
        """
        if position not in self.positions:
            raise ValueError("Position not found in portfolio")
        
        # Calculate P&L
        pnl = self._calculate_pnl(position, exit_price)
        
        # Calculate commission for exit
        position_value = exit_price * position.quantity
        commission = position_value * self.commission_rate
        
        # Net P&L after exit commission
        net_pnl = pnl - commission
        
        # Calculate percentage return
        entry_value = position.entry_price * position.quantity
        pnl_percent = net_pnl / entry_value if entry_value > 0 else 0.0
        
        # Create trade record
        trade = Trade(
            symbol=position.symbol,
            side=position.side,
            entry_price=position.entry_price,
            exit_price=exit_price,
            quantity=position.quantity,
            entry_time=position.entry_time,
            exit_time=exit_time,
            pnl=net_pnl,
            pnl_percent=pnl_percent,
            commission=commission + (entry_value * self.commission_rate),
        )
        
        # Return position value + P&L to balance
        self.balance += entry_value + net_pnl
        
        # Remove from open positions
        self.positions.remove(position)
        
        # Add to trade history
        self.trades.append(trade)
        
        logger.info(
            f"Closed {trade.side.value} position: {trade.symbol} @ {exit_price:.4f}, "
            f"P&L={net_pnl:.2f} ({pnl_percent:.2%})"
        )
        
        return trade
    
    def _calculate_pnl(self, position: OpenPosition, exit_price: float) -> float:
        """
        Calculate raw P&L for a position (before commission).
        
        Args:
            position: The position to calculate P&L for
            exit_price: The exit price
            
        Returns:
            Raw P&L amount
        """
        if position.side == TradeSide.LONG:
            return (exit_price - position.entry_price) * position.quantity
        else:  # SHORT
            return (position.entry_price - exit_price) * position.quantity
    
    def check_stop_loss_take_profit(
        self,
        current_price: float,
        current_time: datetime
    ) -> list[Trade]:
        """
        Check all open positions for stop-loss or take-profit triggers.
        
        Args:
            current_price: Current market price
            current_time: Current timestamp
            
        Returns:
            List of trades that were closed due to SL/TP
        """
        closed_trades = []
        
        # Create a copy of positions list to iterate
        # (since we'll be modifying it)
        positions_to_check = self.positions.copy()
        
        for position in positions_to_check:
            should_close = False
            exit_price = current_price
            
            if position.side == TradeSide.LONG:
                # Long position: SL hit when price drops below SL
                if position.stop_loss and current_price <= position.stop_loss:
                    should_close = True
                    exit_price = position.stop_loss
                    logger.info(f"Stop-loss triggered for LONG {position.symbol}")
                # Long position: TP hit when price rises above TP
                elif position.take_profit and current_price >= position.take_profit:
                    should_close = True
                    exit_price = position.take_profit
                    logger.info(f"Take-profit triggered for LONG {position.symbol}")
            
            else:  # SHORT
                # Short position: SL hit when price rises above SL
                if position.stop_loss and current_price >= position.stop_loss:
                    should_close = True
                    exit_price = position.stop_loss
                    logger.info(f"Stop-loss triggered for SHORT {position.symbol}")
                # Short position: TP hit when price drops below TP
                elif position.take_profit and current_price <= position.take_profit:
                    should_close = True
                    exit_price = position.take_profit
                    logger.info(f"Take-profit triggered for SHORT {position.symbol}")
            
            if should_close:
                trade = self.close_position(position, exit_price, current_time)
                closed_trades.append(trade)
        
        return closed_trades
    
    def update_equity(self, current_prices: dict[str, float], timestamp: datetime):
        """
        Update portfolio equity based on current prices.
        
        Args:
            current_prices: Dict mapping symbol to current price
            timestamp: Current timestamp for equity curve
        """
        # Start with cash balance
        total_equity = self.balance
        
        # Add unrealized P&L from open positions
        for position in self.positions:
            if position.symbol in current_prices:
                price = current_prices[position.symbol]
                # Position value at current price
                current_value = price * position.quantity
                # Original position value (already deducted from balance)
                # So we just add current value
                total_equity += current_value
        
        self.equity = total_equity
        
        # Update peak equity for drawdown calculation
        if total_equity > self._peak_equity:
            self._peak_equity = total_equity
        
        # Calculate drawdown
        drawdown = 0.0
        if self._peak_equity > 0:
            drawdown = (self._peak_equity - total_equity) / self._peak_equity
        
        # Record equity point
        equity_point = EquityPoint(
            timestamp=timestamp,
            equity=total_equity,
            drawdown=drawdown,
        )
        self.equity_curve.append(equity_point)
    
    def get_equity_curve_dict(self) -> list[dict]:
        """Get equity curve as list of dictionaries for JSON serialization."""
        return [ep.to_dict() for ep in self.equity_curve]
    
    def get_trade_log_dict(self) -> list[dict]:
        """Get trade log as list of dictionaries for JSON serialization."""
        return [t.to_dict() for t in self.trades]
    
    @property
    def total_return(self) -> float:
        """Calculate total return as a decimal (e.g., 0.15 = 15%)."""
        if self.initial_balance == 0:
            return 0.0
        return (self.equity - self.initial_balance) / self.initial_balance
    
    @property
    def total_pnl(self) -> float:
        """Calculate total P&L in currency."""
        return self.equity - self.initial_balance
    
    @property
    def winning_trades(self) -> list[Trade]:
        """Get list of winning trades."""
        return [t for t in self.trades if t.pnl > 0]
    
    @property
    def losing_trades(self) -> list[Trade]:
        """Get list of losing trades."""
        return [t for t in self.trades if t.pnl <= 0]
    
    @property
    def win_rate(self) -> float:
        """Calculate win rate as a decimal."""
        if not self.trades:
            return 0.0
        return len(self.winning_trades) / len(self.trades)
    
    @property
    def max_drawdown(self) -> float:
        """Get maximum drawdown from equity curve."""
        if not self.equity_curve:
            return 0.0
        return max(ep.drawdown for ep in self.equity_curve)
    
    def has_open_position(self, symbol: str) -> bool:
        """Check if there's an open position for a symbol."""
        return any(p.symbol == symbol for p in self.positions)
    
    def get_position(self, symbol: str) -> Optional[OpenPosition]:
        """Get open position for a symbol, if any."""
        for position in self.positions:
            if position.symbol == symbol:
                return position
        return None
