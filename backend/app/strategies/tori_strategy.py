from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta, timezone
from app.strategies.base_strategy import BaseStrategy
from app.models.market_data import Candle
from app.models.signal import Signal, SignalType, SignalStatus
import logging

logger = logging.getLogger(__name__)


class ToriStrategy(BaseStrategy):
    """
    Tori Trendline + Fibonacci Confluence Strategy

    Logic:
    - Draw trendlines from swing highs/lows
    - Calculate Fibonacci retracement levels (38.2%, 50%, 61.8%)
    - Enter when price bounces off trendline + Fib level
    - Target next Fib extension
    """

    def get_name(self) -> str:
        return "Tori"

    def get_default_config(self) -> Dict[str, Any]:
        return {
            "timeframe": "4h",
            "swing_lookback": 30,
            "fib_levels": [0.382, 0.5, 0.618],
            "confluence_tolerance": 0.002,  # 0.2% tolerance
            "min_risk_reward": 2.5,
            "risk_percent": 1.5,
        }

    async def analyze(
        self,
        symbol: str,
        candles: List[Candle],
        current_price: float
    ) -> List[Signal]:
        """Generate Tori signals based on trendline + Fib confluence."""
        lookback = self.config["swing_lookback"]

        if len(candles) < lookback + 10:
            logger.warning(f"Tori: Insufficient data for {symbol}")
            return []

        signals = []

        # Identify swing points
        swing_highs = self._find_swing_highs(candles, lookback)
        swing_lows = self._find_swing_lows(candles, lookback)

        # Calculate trendlines
        uptrend_line = self._calculate_trendline(swing_lows, candles)
        downtrend_line = self._calculate_trendline(swing_highs, candles)

        # Calculate Fibonacci levels
        fib_levels = self._calculate_fibonacci_levels(candles)

        # Check for confluence (trendline + Fib level)
        if uptrend_line and fib_levels:
            if self._is_confluence(current_price, uptrend_line, fib_levels["support"]):
                entry_price = current_price
                stop_loss = min(fib_levels["support"]) * 0.995
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
                    timeframe=self.config["timeframe"],
                    confidence=85.0,
                    reason=f"Tori: Uptrend + Fib confluence at {current_price:.5f}",
                    signal_time=datetime.now(timezone.utc),
                    expiry_time=datetime.now(timezone.utc) + timedelta(hours=48)
                ))

        if downtrend_line and fib_levels:
            if self._is_confluence(current_price, downtrend_line, fib_levels["resistance"]):
                entry_price = current_price
                stop_loss = max(fib_levels["resistance"]) * 1.005
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
                    timeframe=self.config["timeframe"],
                    confidence=85.0,
                    reason=f"Tori: Downtrend + Fib confluence at {current_price:.5f}",
                    signal_time=datetime.now(timezone.utc),
                    expiry_time=datetime.now(timezone.utc) + timedelta(hours=48)
                ))

        return signals

    def _find_swing_highs(self, candles: List[Candle], lookback: int) -> List[Tuple[int, float]]:
        """Find swing high points (index, price)."""
        swing_highs = []

        for i in range(lookback, len(candles) - lookback):
            is_swing_high = True
            for j in range(i - lookback, i + lookback + 1):
                if j != i and candles[j].high >= candles[i].high:
                    is_swing_high = False
                    break

            if is_swing_high:
                swing_highs.append((i, candles[i].high))

        return swing_highs[-5:]  # Last 5 swing highs

    def _find_swing_lows(self, candles: List[Candle], lookback: int) -> List[Tuple[int, float]]:
        """Find swing low points (index, price)."""
        swing_lows = []

        for i in range(lookback, len(candles) - lookback):
            is_swing_low = True
            for j in range(i - lookback, i + lookback + 1):
                if j != i and candles[j].low <= candles[i].low:
                    is_swing_low = False
                    break

            if is_swing_low:
                swing_lows.append((i, candles[i].low))

        return swing_lows[-5:]  # Last 5 swing lows

    def _calculate_trendline(
        self,
        swing_points: List[Tuple[int, float]],
        candles: List[Candle]
    ) -> Optional[float]:
        """Calculate current trendline price (simplified linear regression)."""
        if len(swing_points) < 2:
            return None

        # Use last two swing points
        p1_idx, p1_price = swing_points[-2]
        p2_idx, p2_price = swing_points[-1]

        # Calculate slope
        slope = (p2_price - p1_price) / (p2_idx - p1_idx)

        # Project to current price
        current_idx = len(candles) - 1
        trendline_price = p2_price + slope * (current_idx - p2_idx)

        return trendline_price

    def _calculate_fibonacci_levels(self, candles: List[Candle]) -> Optional[Dict[str, List[float]]]:
        """Calculate Fibonacci retracement levels."""
        if len(candles) < 20:
            return None

        # Find recent high and low
        recent_high = max(c.high for c in candles[-50:])
        recent_low = min(c.low for c in candles[-50:])

        fib_range = recent_high - recent_low

        support_levels = []
        resistance_levels = []

        for level in self.config["fib_levels"]:
            fib_price = recent_low + fib_range * level
            support_levels.append(fib_price)

            fib_price_res = recent_high - fib_range * level
            resistance_levels.append(fib_price_res)

        return {
            "support": support_levels,
            "resistance": resistance_levels
        }

    def _is_confluence(
        self,
        current_price: float,
        trendline_price: float,
        fib_levels: List[float]
    ) -> bool:
        """Check if current price is at confluence of trendline and Fib level."""
        tolerance = self.config["confluence_tolerance"]

        # Check if price is near trendline
        if abs(current_price - trendline_price) / trendline_price > tolerance:
            return False

        # Check if price is near any Fib level
        for fib_level in fib_levels:
            if abs(current_price - fib_level) / fib_level < tolerance:
                return True

        return False
