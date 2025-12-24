from typing import Dict, List, Type
from sqlalchemy.ext.asyncio import AsyncSession
from app.strategies.base_strategy import BaseStrategy
from app.strategies.nbb_strategy import NBBStrategy
from app.strategies.jadecap_strategy import JadeCapStrategy
from app.strategies.fabio_strategy import FabioStrategy
from app.strategies.tori_strategy import ToriStrategy
from app.models.signal import Signal
from app.models.market_data import Candle
import logging

logger = logging.getLogger(__name__)


class StrategyManager:
    """Manages all trading strategies and signal generation."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.strategies: Dict[str, BaseStrategy] = {}
        self._register_strategies()

    def _register_strategies(self):
        """Register all available strategies."""
        strategy_classes: List[Type[BaseStrategy]] = [
            NBBStrategy,
            JadeCapStrategy,
            FabioStrategy,
            ToriStrategy,
        ]

        for strategy_class in strategy_classes:
            strategy = strategy_class(
                config=strategy_class.get_default_config(strategy_class),
                db=self.db
            )
            self.strategies[strategy.get_name()] = strategy
            logger.info(f"Registered strategy: {strategy.get_name()}")

    def get_strategy(self, name: str) -> BaseStrategy:
        """Get strategy by name."""
        if name not in self.strategies:
            raise ValueError(f"Strategy '{name}' not found")
        return self.strategies[name]

    def list_strategies(self) -> List[str]:
        """List all registered strategy names."""
        return list(self.strategies.keys())

    async def run_strategy(
        self,
        strategy_name: str,
        symbol: str,
        candles: List[Candle],
        current_price: float
    ) -> List[Signal]:
        """Run a specific strategy and return signals."""
        strategy = self.get_strategy(strategy_name)

        logger.info(f"Running strategy '{strategy_name}' for {symbol}")
        signals = await strategy.analyze(
            symbol=symbol,
            candles=candles,
            current_price=current_price
        )

        logger.info(f"Strategy '{strategy_name}' generated {len(signals)} signals for {symbol}")
        return signals

    async def run_all_strategies(
        self,
        symbol: str,
        candles: List[Candle],
        current_price: float
    ) -> Dict[str, List[Signal]]:
        """Run all strategies and return signals grouped by strategy."""
        all_signals = {}

        for strategy_name in self.strategies.keys():
            signals = await self.run_strategy(
                strategy_name=strategy_name,
                symbol=symbol,
                candles=candles,
                current_price=current_price
            )
            all_signals[strategy_name] = signals

        return all_signals
