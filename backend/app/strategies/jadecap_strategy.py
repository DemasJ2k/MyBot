from typing import List, Dict, Any
from datetime import datetime, timedelta, timezone
from app.strategies.base_strategy import BaseStrategy
from app.models.market_data import Candle
from app.models.signal import Signal, SignalType, SignalStatus
import logging

logger = logging.getLogger(__name__)


class JadeCapStrategy(BaseStrategy):
    """
    JadeCap Multi-Timeframe Trend Following Strategy

    Logic:
    - Identify trend on higher timeframe (4h/1day)
    - Wait for pullback to key moving average
    - Enter when lower timeframe (1h) confirms continuation
    - Ride trend with trailing stop
    """

    def get_name(self) -> str:
        return "JadeCap"

    def get_default_config(self) -> Dict[str, Any]:
        return {
            "htf": "4h",  # Higher timeframe
            "ltf": "1h",  # Lower timeframe
            "ema_fast": 20,
            "ema_slow": 50,
            "pullback_ema": 20,
            "min_risk_reward": 2.0,
            "risk_percent": 1.5,
            "trailing_stop_percent": 1.5,
        }

    async def analyze(
        self,
        symbol: str,
        candles: List[Candle],
        current_price: float
    ) -> List[Signal]:
        """Generate JadeCap signals based on multi-timeframe trend."""
        if len(candles) < self.config["ema_slow"] + 10:
            logger.warning(f"JadeCap: Insufficient data for {symbol}")
            return []

        signals = []

        # Calculate EMAs
        ema_fast = self._calculate_ema(candles, self.config["ema_fast"])
        ema_slow = self._calculate_ema(candles, self.config["ema_slow"])

        # Determine trend
        trend = self._determine_trend(ema_fast, ema_slow, candles)

        if trend == "bullish":
            # Look for pullback to EMA and continuation
            if self._is_bullish_pullback(candles, ema_fast, current_price):
                entry_price = current_price
                stop_loss = ema_slow[-1] * 0.995
                take_profit = entry_price + (entry_price - stop_loss) * 3.0

                signals.append(Signal(
                    strategy_name=self.get_name(),
                    symbol=symbol,
                    signal_type=SignalType.LONG,
                    status=SignalStatus.PENDING,
                    entry_price=entry_price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    risk_percent=self.config["risk_percent"],
                    timeframe=self.config["htf"],
                    confidence=75.0,
                    reason=f"JadeCap: Bullish trend + pullback to EMA{self.config['ema_fast']}",
                    signal_time=datetime.now(timezone.utc),
                    expiry_time=datetime.now(timezone.utc) + timedelta(hours=48)
                ))

        elif trend == "bearish":
            if self._is_bearish_pullback(candles, ema_fast, current_price):
                entry_price = current_price
                stop_loss = ema_slow[-1] * 1.005
                take_profit = entry_price - (stop_loss - entry_price) * 3.0

                signals.append(Signal(
                    strategy_name=self.get_name(),
                    symbol=symbol,
                    signal_type=SignalType.SHORT,
                    status=SignalStatus.PENDING,
                    entry_price=entry_price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    risk_percent=self.config["risk_percent"],
                    timeframe=self.config["htf"],
                    confidence=75.0,
                    reason=f"JadeCap: Bearish trend + pullback to EMA{self.config['ema_fast']}",
                    signal_time=datetime.now(timezone.utc),
                    expiry_time=datetime.now(timezone.utc) + timedelta(hours=48)
                ))

        return signals

    def _calculate_ema(self, candles: List[Candle], period: int) -> List[float]:
        """Calculate Exponential Moving Average."""
        prices = [c.close for c in candles]
        ema = []
        multiplier = 2 / (period + 1)

        # First EMA is SMA
        sma = sum(prices[:period]) / period
        ema.append(sma)

        # Calculate EMA for remaining prices
        for price in prices[period:]:
            ema_value = (price - ema[-1]) * multiplier + ema[-1]
            ema.append(ema_value)

        return ema

    def _determine_trend(
        self,
        ema_fast: List[float],
        ema_slow: List[float],
        candles: List[Candle]
    ) -> str:
        """Determine trend direction."""
        if len(ema_fast) < 5 or len(ema_slow) < 5:
            return "neutral"

        # Bullish: fast EMA above slow EMA and rising
        if ema_fast[-1] > ema_slow[-1] and ema_fast[-1] > ema_fast[-5]:
            return "bullish"

        # Bearish: fast EMA below slow EMA and falling
        if ema_fast[-1] < ema_slow[-1] and ema_fast[-1] < ema_fast[-5]:
            return "bearish"

        return "neutral"

    def _is_bullish_pullback(
        self,
        candles: List[Candle],
        ema_fast: List[float],
        current_price: float
    ) -> bool:
        """Check if price has pulled back to EMA in bullish trend."""
        if len(ema_fast) < 3:
            return False

        # Price should be near EMA (within 0.5%)
        ema_current = ema_fast[-1]
        if abs(current_price - ema_current) / ema_current > 0.005:
            return False

        # Recent candles should show bounce from EMA
        if candles[-1].close > candles[-2].close:
            return True

        return False

    def _is_bearish_pullback(
        self,
        candles: List[Candle],
        ema_fast: List[float],
        current_price: float
    ) -> bool:
        """Check if price has pulled back to EMA in bearish trend."""
        if len(ema_fast) < 3:
            return False

        ema_current = ema_fast[-1]
        if abs(current_price - ema_current) / ema_current > 0.005:
            return False

        if candles[-1].close < candles[-2].close:
            return True

        return False
