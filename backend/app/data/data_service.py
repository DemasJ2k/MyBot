from typing import List, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from app.models.market_data import Candle, Symbol, EconomicEvent
from app.data.twelvedata_client import TwelveDataClient
import logging

logger = logging.getLogger(__name__)


class DataService:
    """Service for fetching and storing market data."""

    def __init__(self, db: AsyncSession, client: TwelveDataClient):
        self.db = db
        self.client = client

    async def fetch_and_store_candles(
        self,
        symbol: str,
        interval: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        outputsize: int = 5000
    ) -> int:
        """
        Fetch candles from TwelveData and store in database.

        Returns:
            Number of candles inserted
        """
        candles_data = await self.client.get_time_series(
            symbol=symbol,
            interval=interval,
            start_date=start_date,
            end_date=end_date,
            outputsize=outputsize
        )

        if not candles_data:
            logger.warning(f"No candles fetched for {symbol} {interval}")
            return 0

        inserted_count = 0
        for candle_dict in candles_data:
            # Check if candle already exists
            stmt = select(Candle).where(
                and_(
                    Candle.symbol == symbol,
                    Candle.interval == interval,
                    Candle.timestamp == candle_dict["datetime"]
                )
            )
            result = await self.db.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                continue

            candle = Candle(
                symbol=symbol,
                interval=interval,
                timestamp=candle_dict["datetime"],
                open=candle_dict["open"],
                high=candle_dict["high"],
                low=candle_dict["low"],
                close=candle_dict["close"],
                volume=candle_dict["volume"],
                source="twelvedata"
            )
            self.db.add(candle)
            inserted_count += 1

        await self.db.commit()
        logger.info(f"Inserted {inserted_count} candles for {symbol} {interval}")
        return inserted_count

    async def get_candles(
        self,
        symbol: str,
        interval: str,
        start_date: datetime,
        end_date: datetime
    ) -> List[Candle]:
        """Retrieve candles from database."""
        stmt = select(Candle).where(
            and_(
                Candle.symbol == symbol,
                Candle.interval == interval,
                Candle.timestamp >= start_date,
                Candle.timestamp <= end_date
            )
        ).order_by(Candle.timestamp.asc())

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def upsert_symbol(self, symbol_data: dict) -> Symbol:
        """Insert or update symbol metadata."""
        stmt = select(Symbol).where(Symbol.symbol == symbol_data["symbol"])
        result = await self.db.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            for key, value in symbol_data.items():
                setattr(existing, key, value)
            await self.db.commit()
            await self.db.refresh(existing)
            return existing

        symbol = Symbol(**symbol_data)
        self.db.add(symbol)
        await self.db.commit()
        await self.db.refresh(symbol)
        return symbol

    async def fetch_and_store_economic_events(
        self,
        start_date: datetime,
        end_date: datetime,
        country: Optional[str] = None
    ) -> int:
        """Fetch economic calendar and store events."""
        events_data = await self.client.get_economic_calendar(
            start_date=start_date,
            end_date=end_date,
            country=country
        )

        inserted_count = 0
        for event_dict in events_data:
            event = EconomicEvent(**event_dict)
            self.db.add(event)
            inserted_count += 1

        await self.db.commit()
        logger.info(f"Inserted {inserted_count} economic events")
        return inserted_count
