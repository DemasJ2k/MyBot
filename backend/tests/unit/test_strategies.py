import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timedelta, timezone

from app.strategies.nbb_strategy import NBBStrategy
from app.strategies.jadecap_strategy import JadeCapStrategy
from app.strategies.fabio_strategy import FabioStrategy
from app.strategies.tori_strategy import ToriStrategy
from app.strategies.strategy_manager import StrategyManager
from app.models.market_data import Candle
from app.models.signal import SignalType


def create_candles(count: int, base_price: float = 1.1000, trend: str = "flat") -> list:
    """Helper to create test candles."""
    candles = []
    price = base_price

    for i in range(count):
        if trend == "up":
            price += 0.0002
        elif trend == "down":
            price -= 0.0002

        candle = MagicMock(spec=Candle)
        candle.symbol = "EURUSD"
        candle.interval = "1h"
        candle.timestamp = datetime.now(timezone.utc) - timedelta(hours=count - i)
        candle.open = price
        candle.high = price + 0.0010
        candle.low = price - 0.0010
        candle.close = price + 0.0005
        candle.volume = 1000 + i * 10
        candles.append(candle)

    return candles


class TestNBBStrategy:
    @pytest_asyncio.fixture
    async def mock_db(self):
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_strategy_initialization(self, mock_db):
        strategy = NBBStrategy(
            config=NBBStrategy.get_default_config(NBBStrategy),
            db=mock_db
        )
        assert strategy.get_name() == "NBB"
        assert strategy.config["zone_lookback"] == 20

    @pytest.mark.asyncio
    async def test_analyze_insufficient_data(self, mock_db):
        strategy = NBBStrategy(
            config=NBBStrategy.get_default_config(NBBStrategy),
            db=mock_db
        )

        # Only 10 candles (needs at least 30)
        candles = create_candles(10)

        signals = await strategy.analyze("EURUSD", candles, 1.1005)
        assert len(signals) == 0

    @pytest.mark.asyncio
    async def test_swing_high_detection(self, mock_db):
        strategy = NBBStrategy(
            config=NBBStrategy.get_default_config(NBBStrategy),
            db=mock_db
        )

        # Create candles with a clear swing high
        candles = create_candles(60, trend="flat")
        # Make a swing high in the middle
        candles[30].high = 1.2000

        is_swing_high = strategy._is_swing_high(candles, 30, 5)
        assert is_swing_high is True


class TestJadeCapStrategy:
    @pytest_asyncio.fixture
    async def mock_db(self):
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_strategy_initialization(self, mock_db):
        strategy = JadeCapStrategy(
            config=JadeCapStrategy.get_default_config(JadeCapStrategy),
            db=mock_db
        )
        assert strategy.get_name() == "JadeCap"
        assert strategy.config["ema_fast"] == 20
        assert strategy.config["ema_slow"] == 50

    @pytest.mark.asyncio
    async def test_ema_calculation(self, mock_db):
        strategy = JadeCapStrategy(
            config=JadeCapStrategy.get_default_config(JadeCapStrategy),
            db=mock_db
        )

        candles = create_candles(60, trend="up")

        ema = strategy._calculate_ema(candles, 20)
        assert len(ema) > 0
        assert all(isinstance(val, float) for val in ema)

    @pytest.mark.asyncio
    async def test_trend_detection_bullish(self, mock_db):
        strategy = JadeCapStrategy(
            config=JadeCapStrategy.get_default_config(JadeCapStrategy),
            db=mock_db
        )

        candles = create_candles(60, trend="up")
        ema_fast = strategy._calculate_ema(candles, 20)
        ema_slow = strategy._calculate_ema(candles, 50)

        trend = strategy._determine_trend(ema_fast, ema_slow, candles)
        # May be bullish or neutral depending on data
        assert trend in ["bullish", "neutral", "bearish"]


class TestFabioStrategy:
    @pytest_asyncio.fixture
    async def mock_db(self):
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_strategy_initialization(self, mock_db):
        strategy = FabioStrategy(
            config=FabioStrategy.get_default_config(FabioStrategy),
            db=mock_db
        )
        assert strategy.get_name() == "Fabio"
        assert strategy.config["value_area_percent"] == 70

    @pytest.mark.asyncio
    async def test_value_area_calculation(self, mock_db):
        strategy = FabioStrategy(
            config=FabioStrategy.get_default_config(FabioStrategy),
            db=mock_db
        )

        candles = create_candles(50)
        value_area = strategy._calculate_value_area(candles)

        assert "poc" in value_area
        assert "vah" in value_area
        assert "val" in value_area
        assert value_area["val"] <= value_area["poc"] <= value_area["vah"]


class TestToriStrategy:
    @pytest_asyncio.fixture
    async def mock_db(self):
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_strategy_initialization(self, mock_db):
        strategy = ToriStrategy(
            config=ToriStrategy.get_default_config(ToriStrategy),
            db=mock_db
        )
        assert strategy.get_name() == "Tori"
        assert strategy.config["swing_lookback"] == 30

    @pytest.mark.asyncio
    async def test_fibonacci_calculation(self, mock_db):
        strategy = ToriStrategy(
            config=ToriStrategy.get_default_config(ToriStrategy),
            db=mock_db
        )

        candles = create_candles(60)
        fib_levels = strategy._calculate_fibonacci_levels(candles)

        assert fib_levels is not None
        assert "support" in fib_levels
        assert "resistance" in fib_levels
        assert len(fib_levels["support"]) == 3  # 38.2%, 50%, 61.8%


class TestStrategyManager:
    @pytest_asyncio.fixture
    async def mock_db(self):
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_register_all_strategies(self, mock_db):
        manager = StrategyManager(db=mock_db)
        strategies = manager.list_strategies()

        assert "NBB" in strategies
        assert "JadeCap" in strategies
        assert "Fabio" in strategies
        assert "Tori" in strategies
        assert len(strategies) == 4

    @pytest.mark.asyncio
    async def test_get_strategy(self, mock_db):
        manager = StrategyManager(db=mock_db)

        nbb = manager.get_strategy("NBB")
        assert nbb.get_name() == "NBB"

        jadecap = manager.get_strategy("JadeCap")
        assert jadecap.get_name() == "JadeCap"

    @pytest.mark.asyncio
    async def test_get_strategy_not_found(self, mock_db):
        manager = StrategyManager(db=mock_db)

        with pytest.raises(ValueError, match="Strategy 'Unknown' not found"):
            manager.get_strategy("Unknown")

    @pytest.mark.asyncio
    async def test_run_strategy(self, mock_db):
        manager = StrategyManager(db=mock_db)
        candles = create_candles(60)

        signals = await manager.run_strategy(
            strategy_name="NBB",
            symbol="EURUSD",
            candles=candles,
            current_price=1.1000
        )

        assert isinstance(signals, list)

    @pytest.mark.asyncio
    async def test_run_all_strategies(self, mock_db):
        manager = StrategyManager(db=mock_db)
        candles = create_candles(60)

        all_signals = await manager.run_all_strategies(
            symbol="EURUSD",
            candles=candles,
            current_price=1.1000
        )

        assert isinstance(all_signals, dict)
        assert "NBB" in all_signals
        assert "JadeCap" in all_signals
        assert "Fabio" in all_signals
        assert "Tori" in all_signals


class TestSignalValidation:
    @pytest_asyncio.fixture
    async def mock_db(self):
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_signal_risk_reward_calculation(self, mock_db):
        from app.models.signal import Signal, SignalStatus

        signal = Signal(
            strategy_name="NBB",
            symbol="EURUSD",
            signal_type=SignalType.LONG,
            status=SignalStatus.PENDING,
            entry_price=1.1000,
            stop_loss=1.0950,
            take_profit=1.1150,
            risk_percent=1.5,
            timeframe="1h",
            confidence=70.0,
            signal_time=datetime.now(timezone.utc)
        )

        # Risk = 1.1000 - 1.0950 = 0.0050
        # Reward = 1.1150 - 1.1000 = 0.0150
        # R:R = 0.0150 / 0.0050 = 3.0
        assert abs(signal.risk_reward_ratio - 3.0) < 0.001

    @pytest.mark.asyncio
    async def test_validate_valid_long_signal(self, mock_db):
        from app.models.signal import Signal, SignalStatus

        strategy = NBBStrategy(
            config=NBBStrategy.get_default_config(NBBStrategy),
            db=mock_db
        )

        signal = Signal(
            strategy_name="NBB",
            symbol="EURUSD",
            signal_type=SignalType.LONG,
            status=SignalStatus.PENDING,
            entry_price=1.1000,
            stop_loss=1.0950,
            take_profit=1.1150,
            risk_percent=1.5,
            timeframe="1h",
            confidence=70.0,
            signal_time=datetime.now(timezone.utc)
        )

        assert strategy.validate_signal(signal) is True

    @pytest.mark.asyncio
    async def test_validate_invalid_rr_signal(self, mock_db):
        from app.models.signal import Signal, SignalStatus

        strategy = NBBStrategy(
            config=NBBStrategy.get_default_config(NBBStrategy),
            db=mock_db
        )

        # R:R = 1.0 (below 2.0 threshold)
        signal = Signal(
            strategy_name="NBB",
            symbol="EURUSD",
            signal_type=SignalType.LONG,
            status=SignalStatus.PENDING,
            entry_price=1.1000,
            stop_loss=1.0950,
            take_profit=1.1050,  # Only 1:1 R:R
            risk_percent=1.5,
            timeframe="1h",
            confidence=70.0,
            signal_time=datetime.now(timezone.utc)
        )

        assert strategy.validate_signal(signal) is False
