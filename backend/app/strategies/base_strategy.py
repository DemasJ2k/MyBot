from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime
from app.models.market_data import Candle
from app.models.signal import Signal, SignalType, SignalStatus
from sqlalchemy.ext.asyncio import AsyncSession
import logging

logger = logging.getLogger(__name__)


class BaseStrategy(ABC):
    """
    Abstract base class for all trading strategies.

    All strategies must implement:
    - analyze(): Generate signals from market data
    - get_name(): Return strategy name
    - get_default_config(): Return default configuration
    """

    def __init__(self, config: Dict[str, Any], db: AsyncSession):
        self.config = config
        self.db = db
        self.name = self.get_name()
        logger.info(f"Initialized strategy: {self.name}")

    @abstractmethod
    async def analyze(
        self,
        symbol: str,
        candles: List[Candle],
        current_price: float
    ) -> List[Signal]:
        """
        Analyze market data and generate trading signals.

        Args:
            symbol: Trading symbol
            candles: Historical OHLCV data (sorted oldest to newest)
            current_price: Current market price

        Returns:
            List of Signal objects (not yet committed to database)
        """
        pass

    @abstractmethod
    def get_name(self) -> str:
        """Return strategy name."""
        pass

    @abstractmethod
    def get_default_config(self) -> Dict[str, Any]:
        """Return default configuration parameters."""
        pass

    def validate_signal(self, signal: Signal) -> bool:
        """
        Validate signal meets minimum requirements.

        Override in subclass for custom validation.
        """
        # Minimum R:R ratio
        min_rr = self.config.get("min_risk_reward", 1.5)
        if signal.risk_reward_ratio < min_rr:
            logger.warning(f"Signal rejected: R:R {signal.risk_reward_ratio:.2f} < {min_rr}")
            return False

        # Stop loss must be set
        if signal.stop_loss <= 0:
            logger.warning("Signal rejected: Invalid stop loss")
            return False

        # Take profit must be set
        if signal.take_profit <= 0:
            logger.warning("Signal rejected: Invalid take profit")
            return False

        # Entry price must be between SL and TP
        if signal.signal_type == SignalType.LONG:
            if not (signal.stop_loss < signal.entry_price < signal.take_profit):
                logger.warning("Signal rejected: Invalid LONG price levels")
                return False
        else:
            if not (signal.take_profit < signal.entry_price < signal.stop_loss):
                logger.warning("Signal rejected: Invalid SHORT price levels")
                return False

        return True

    def calculate_position_size(
        self,
        account_balance: float,
        risk_percent: float,
        entry_price: float,
        stop_loss: float
    ) -> float:
        """
        Calculate position size based on risk parameters.

        Args:
            account_balance: Total account balance
            risk_percent: Risk percentage (e.g., 2.0 for 2%)
            entry_price: Entry price
            stop_loss: Stop loss price

        Returns:
            Position size in lots/shares
        """
        risk_amount = account_balance * (risk_percent / 100.0)
        risk_per_unit = abs(entry_price - stop_loss)

        if risk_per_unit == 0:
            return 0.0

        position_size = risk_amount / risk_per_unit
        return round(position_size, 2)

    async def save_signal(self, signal: Signal) -> Signal:
        """Save signal to database."""
        if self.validate_signal(signal):
            self.db.add(signal)
            await self.db.commit()
            await self.db.refresh(signal)
            logger.info(f"Signal saved: {signal}")
            return signal
        else:
            logger.warning(f"Signal validation failed: {signal}")
            raise ValueError("Signal validation failed")
