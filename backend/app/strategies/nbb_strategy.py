from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta, timezone
from app.strategies.base_strategy import BaseStrategy
from app.models.market_data import Candle
from app.models.signal import Signal, SignalType, SignalStatus
import logging

logger = logging.getLogger(__name__)


class NBBStrategy(BaseStrategy):
    """
    No Bullshit Breaker (NBB) Strategy

    Logic:
    - Identify supply/demand zones (swing highs/lows)
    - Wait for price to break zone with strong momentum
    - Enter on retest of broken zone
    - Stop loss beyond zone, TP at next zone
    """

    def get_name(self) -> str:
        return "NBB"

    def get_default_config(self) -> Dict[str, Any]:
        return {
            "timeframe": "1h",
            "zone_lookback": 20,  # candles to identify zones
            "breakout_threshold": 0.0015,  # 0.15% minimum breakout
            "retest_tolerance": 0.0005,  # 0.05% retest tolerance
            "min_risk_reward": 2.0,
            "risk_percent": 1.5,
            "confidence_threshold": 60.0,
        }

    async def analyze(
        self,
        symbol: str,
        candles: List[Candle],
        current_price: float
    ) -> List[Signal]:
        """Generate NBB signals based on zone breakouts."""
        if len(candles) < self.config["zone_lookback"] + 10:
            logger.warning(f"NBB: Insufficient data for {symbol}")
            return []

        signals = []

        # Identify supply/demand zones
        zones = self._identify_zones(candles)

        # Check for breakout and retest
        for zone in zones:
            signal = self._check_breakout_and_retest(
                symbol=symbol,
                candles=candles,
                current_price=current_price,
                zone=zone
            )
            if signal:
                signals.append(signal)

        return signals

    def _identify_zones(self, candles: List[Candle]) -> List[Dict[str, Any]]:
        """Identify supply and demand zones from swing points."""
        zones = []
        lookback = self.config["zone_lookback"]

        for i in range(lookback, len(candles) - lookback):
            # Demand zone (swing low)
            if self._is_swing_low(candles, i, lookback):
                zones.append({
                    "type": "demand",
                    "price": candles[i].low,
                    "index": i,
                    "high": candles[i].high,
                    "low": candles[i].low,
                })

            # Supply zone (swing high)
            if self._is_swing_high(candles, i, lookback):
                zones.append({
                    "type": "supply",
                    "price": candles[i].high,
                    "index": i,
                    "high": candles[i].high,
                    "low": candles[i].low,
                })

        return zones

    def _is_swing_low(self, candles: List[Candle], index: int, lookback: int) -> bool:
        """Check if candle at index is a swing low."""
        current_low = candles[index].low

        for i in range(index - lookback, index + lookback + 1):
            if i == index:
                continue
            if candles[i].low < current_low:
                return False

        return True

    def _is_swing_high(self, candles: List[Candle], index: int, lookback: int) -> bool:
        """Check if candle at index is a swing high."""
        current_high = candles[index].high

        for i in range(index - lookback, index + lookback + 1):
            if i == index:
                continue
            if candles[i].high > current_high:
                return False

        return True

    def _check_breakout_and_retest(
        self,
        symbol: str,
        candles: List[Candle],
        current_price: float,
        zone: Dict[str, Any]
    ) -> Optional[Signal]:
        """Check if zone has been broken and retested."""
        breakout_threshold = self.config["breakout_threshold"]
        retest_tolerance = self.config["retest_tolerance"]

        zone_index = zone["index"]
        zone_price = zone["price"]

        # Check candles after zone for breakout
        for i in range(zone_index + 1, len(candles)):
            if zone["type"] == "demand":
                # Bullish breakout: price breaks above zone
                if candles[i].close > zone_price * (1 + breakout_threshold):
                    # Look for retest (price comes back to zone)
                    if abs(current_price - zone_price) / zone_price < retest_tolerance:
                        # Generate LONG signal
                        entry_price = current_price
                        stop_loss = zone["low"] * 0.999  # Just below zone
                        take_profit = entry_price + (entry_price - stop_loss) * 2.5

                        return Signal(
                            strategy_name=self.get_name(),
                            symbol=symbol,
                            signal_type=SignalType.LONG,
                            status=SignalStatus.PENDING,
                            entry_price=entry_price,
                            stop_loss=stop_loss,
                            take_profit=take_profit,
                            risk_percent=self.config["risk_percent"],
                            timeframe=self.config["timeframe"],
                            confidence=70.0,
                            reason=f"NBB: Demand zone breakout + retest at {zone_price:.5f}",
                            signal_time=datetime.now(timezone.utc),
                            expiry_time=datetime.now(timezone.utc) + timedelta(hours=24)
                        )

            elif zone["type"] == "supply":
                # Bearish breakout: price breaks below zone
                if candles[i].close < zone_price * (1 - breakout_threshold):
                    # Look for retest
                    if abs(current_price - zone_price) / zone_price < retest_tolerance:
                        # Generate SHORT signal
                        entry_price = current_price
                        stop_loss = zone["high"] * 1.001  # Just above zone
                        take_profit = entry_price - (stop_loss - entry_price) * 2.5

                        return Signal(
                            strategy_name=self.get_name(),
                            symbol=symbol,
                            signal_type=SignalType.SHORT,
                            status=SignalStatus.PENDING,
                            entry_price=entry_price,
                            stop_loss=stop_loss,
                            take_profit=take_profit,
                            risk_percent=self.config["risk_percent"],
                            timeframe=self.config["timeframe"],
                            confidence=70.0,
                            reason=f"NBB: Supply zone breakout + retest at {zone_price:.5f}",
                            signal_time=datetime.now(timezone.utc),
                            expiry_time=datetime.now(timezone.utc) + timedelta(hours=24)
                        )

        return None
