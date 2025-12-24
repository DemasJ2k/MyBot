from typing import List, Dict, Any
from datetime import datetime, timedelta, timezone
from app.strategies.base_strategy import BaseStrategy
from app.models.market_data import Candle
from app.models.signal import Signal, SignalType, SignalStatus
import logging

logger = logging.getLogger(__name__)


class FabioStrategy(BaseStrategy):
    """
    Fabio Auction Market Theory (AMT) Strategy

    Logic:
    - Calculate Value Area (POC, VAH, VAL) from volume profile
    - Trade breakouts from value area
    - Enter when price returns to POC after breakout
    - Target previous high/low
    """

    def get_name(self) -> str:
        return "Fabio"

    def get_default_config(self) -> Dict[str, Any]:
        return {
            "timeframe": "1h",
            "value_area_percent": 70,  # 70% of volume
            "lookback_candles": 50,
            "min_risk_reward": 2.0,
            "risk_percent": 2.0,
        }

    async def analyze(
        self,
        symbol: str,
        candles: List[Candle],
        current_price: float
    ) -> List[Signal]:
        """Generate Fabio AMT signals."""
        lookback = self.config["lookback_candles"]

        if len(candles) < lookback:
            logger.warning(f"Fabio: Insufficient data for {symbol}")
            return []

        signals = []

        # Calculate value area
        value_area = self._calculate_value_area(candles[-lookback:])

        poc = value_area["poc"]
        vah = value_area["vah"]
        val = value_area["val"]

        # Check for breakout and retest
        if current_price > vah * 1.002:  # Above value area
            # Look for retest of POC from above
            if self._is_retest_from_above(candles[-10:], poc, current_price):
                entry_price = current_price
                stop_loss = val * 0.998
                take_profit = vah * 1.01

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
                    confidence=80.0,
                    reason=f"Fabio AMT: Breakout above VA, retest POC {poc:.5f}",
                    signal_time=datetime.now(timezone.utc),
                    expiry_time=datetime.now(timezone.utc) + timedelta(hours=24)
                ))

        elif current_price < val * 0.998:  # Below value area
            if self._is_retest_from_below(candles[-10:], poc, current_price):
                entry_price = current_price
                stop_loss = vah * 1.002
                take_profit = val * 0.99

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
                    confidence=80.0,
                    reason=f"Fabio AMT: Breakout below VA, retest POC {poc:.5f}",
                    signal_time=datetime.now(timezone.utc),
                    expiry_time=datetime.now(timezone.utc) + timedelta(hours=24)
                ))

        return signals

    def _calculate_value_area(self, candles: List[Candle]) -> Dict[str, float]:
        """
        Calculate Point of Control (POC), Value Area High (VAH), Value Area Low (VAL).

        Simplified volume profile calculation.
        """
        # Create price levels with volume
        price_levels = {}

        for candle in candles:
            # Discretize prices into levels (round to 4 decimals)
            high_level = round(candle.high, 4)
            low_level = round(candle.low, 4)

            # Distribute volume across range
            num_levels = max(1, int((high_level - low_level) / 0.0001))
            volume_per_level = candle.volume / num_levels if num_levels > 0 else candle.volume

            price = low_level
            while price <= high_level:
                price_key = round(price, 4)
                if price_key not in price_levels:
                    price_levels[price_key] = 0
                price_levels[price_key] += volume_per_level
                price += 0.0001

        if not price_levels:
            # Fallback if no volume data
            avg_price = sum(c.close for c in candles) / len(candles)
            return {"poc": avg_price, "vah": avg_price * 1.005, "val": avg_price * 0.995}

        # Find POC (price level with highest volume)
        poc = max(price_levels.items(), key=lambda x: x[1])[0]

        # Calculate value area (70% of volume around POC)
        total_volume = sum(price_levels.values())
        target_volume = total_volume * (self.config["value_area_percent"] / 100.0)

        sorted_prices = sorted(price_levels.items(), key=lambda x: x[1], reverse=True)

        value_area_volume = 0
        value_area_prices = []

        for price, volume in sorted_prices:
            value_area_prices.append(price)
            value_area_volume += volume
            if value_area_volume >= target_volume:
                break

        vah = max(value_area_prices)
        val = min(value_area_prices)

        return {"poc": poc, "vah": vah, "val": val}

    def _is_retest_from_above(
        self,
        recent_candles: List[Candle],
        poc: float,
        current_price: float
    ) -> bool:
        """Check if price is retesting POC from above."""
        if len(recent_candles) < 2:
            return False

        # Price should be near POC (within 0.3%)
        if abs(current_price - poc) / poc > 0.003:
            return False

        # Recent candles should show move toward POC
        if recent_candles[-2].close > poc and current_price <= poc * 1.002:
            return True

        return False

    def _is_retest_from_below(
        self,
        recent_candles: List[Candle],
        poc: float,
        current_price: float
    ) -> bool:
        """Check if price is retesting POC from below."""
        if len(recent_candles) < 2:
            return False

        if abs(current_price - poc) / poc > 0.003:
            return False

        if recent_candles[-2].close < poc and current_price >= poc * 0.998:
            return True

        return False
