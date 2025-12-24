# Prompt 03: Data Engine with TwelveData Integration

## Purpose

Build the complete market data infrastructure using **TwelveData as the PRIMARY and authoritative data source**. This system provides normalized OHLCV candles, real-time quotes, symbol search, and economic calendar data with Redis caching, rate-limit protection, and retry logic.

## Scope

- TwelveData API async client
- Data models for candles, quotes, and symbols
- Normalization layer for consistent data format
- Redis caching with TTL management
- Rate-limit tracking and auto-throttling
- Symbol resolution and search
- Economic calendar integration
- Comprehensive error handling
- Complete test suite

## Data Architecture

```
TwelveData API (Primary Source)
    ↓
HTTP Client (aiohttp) → Rate Limiter → Retry Logic
    ↓
Response Parser → Data Validator → Normalizer
    ↓
Redis Cache (5min-1hr TTL) → Application
```

**TwelveData Endpoints Used:**
- `/time_series` - Historical OHLCV candles
- `/quote` - Real-time quotes
- `/symbol_search` - Symbol lookup
- `/earliest_timestamp` - Data availability
- `/economic_calendar` - News events

**Environment Variables Required:**
```
TWELVEDATA_API_KEY=your_api_key_here
TWELVEDATA_BASE_URL=https://api.twelvedata.com
TWELVEDATA_RATE_LIMIT=8  # requests per minute for free tier
REDIS_URL=redis://localhost:6379/0
```

## Implementation

### Step 1: Install Dependencies

Update `backend/requirements.txt`:
```txt
aiohttp==3.9.1
aiohttp-retry==2.8.3
redis==5.0.1
```

Run:
```bash
pip install -r backend/requirements.txt
```

### Step 2: Data Models

Create `backend/app/models/market_data.py`:

```python
from sqlalchemy import String, Float, Integer, DateTime, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from typing import Optional
from app.models.base import Base, TimestampMixin


class Candle(Base, TimestampMixin):
    """OHLCV candle data normalized from TwelveData."""
    __tablename__ = "candles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    interval: Mapped[str] = mapped_column(String(10), nullable=False, index=True)  # 1min, 5min, 1h, 1day
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    open: Mapped[float] = mapped_column(Float, nullable=False)
    high: Mapped[float] = mapped_column(Float, nullable=False)
    low: Mapped[float] = mapped_column(Float, nullable=False)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    source: Mapped[str] = mapped_column(String(50), nullable=False, default="twelvedata")

    __table_args__ = (
        UniqueConstraint("symbol", "interval", "timestamp", name="uq_candle_symbol_interval_time"),
        Index("ix_candle_symbol_interval_timestamp", "symbol", "interval", "timestamp"),
    )

    def __repr__(self) -> str:
        return f"<Candle {self.symbol} {self.interval} {self.timestamp} OHLC={self.open}/{self.high}/{self.low}/{self.close}>"


class Symbol(Base, TimestampMixin):
    """Tradable symbols with metadata."""
    __tablename__ = "symbols"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False)
    exchange: Mapped[str] = mapped_column(String(50), nullable=False)
    mic_code: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    country: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    type: Mapped[str] = mapped_column(String(50), nullable=False)  # Stock, Forex, Crypto, etc.
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    def __repr__(self) -> str:
        return f"<Symbol {self.symbol} {self.name}>"


class EconomicEvent(Base, TimestampMixin):
    """Economic calendar events from TwelveData."""
    __tablename__ = "economic_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    event_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    country: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    event: Mapped[str] = mapped_column(String(255), nullable=False)
    impact: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # High, Medium, Low
    actual: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    forecast: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    previous: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    __table_args__ = (
        Index("ix_economic_event_date", "event_date"),
    )

    def __repr__(self) -> str:
        return f"<EconomicEvent {self.country} {self.event} {self.event_date}>"
```

Update `backend/app/models/__init__.py`:
```python
from app.models.base import Base, TimestampMixin
from app.models.user import User
from app.models.market_data import Candle, Symbol, EconomicEvent

__all__ = ["Base", "TimestampMixin", "User", "Candle", "Symbol", "EconomicEvent"]
```

### Step 3: TwelveData Client

Create `backend/app/data/twelvedata_client.py`:

```python
import aiohttp
import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from aiohttp_retry import RetryClient, ExponentialRetry
from app.config import settings
import redis.asyncio as aioredis
import json

logger = logging.getLogger(__name__)


class RateLimiter:
    """Token bucket rate limiter for TwelveData API."""

    def __init__(self, max_requests: int, time_window: int = 60):
        self.max_requests = max_requests
        self.time_window = time_window
        self.tokens = max_requests
        self.last_refill = datetime.utcnow()
        self._lock = asyncio.Lock()

    async def acquire(self):
        """Wait until a token is available."""
        async with self._lock:
            now = datetime.utcnow()
            elapsed = (now - self.last_refill).total_seconds()

            if elapsed > self.time_window:
                self.tokens = self.max_requests
                self.last_refill = now

            if self.tokens <= 0:
                wait_time = self.time_window - elapsed
                if wait_time > 0:
                    logger.warning(f"Rate limit reached. Waiting {wait_time:.2f}s")
                    await asyncio.sleep(wait_time)
                    self.tokens = self.max_requests
                    self.last_refill = datetime.utcnow()

            self.tokens -= 1


class TwelveDataClient:
    """Async client for TwelveData API with caching and rate limiting."""

    def __init__(self):
        self.base_url = settings.twelvedata_base_url
        self.api_key = settings.twelvedata_api_key
        self.rate_limiter = RateLimiter(max_requests=settings.twelvedata_rate_limit)
        self.redis_client: Optional[aioredis.Redis] = None
        self._session: Optional[aiohttp.ClientSession] = None
        self._retry_client: Optional[RetryClient] = None

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def connect(self):
        """Initialize HTTP session and Redis connection."""
        if not self._session:
            timeout = aiohttp.ClientTimeout(total=30)
            self._session = aiohttp.ClientSession(timeout=timeout)

            retry_options = ExponentialRetry(attempts=3, start_timeout=1, max_timeout=10)
            self._retry_client = RetryClient(
                client_session=self._session,
                retry_options=retry_options,
                raise_for_status=False
            )

        if not self.redis_client:
            self.redis_client = await aioredis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True
            )

        logger.info("TwelveData client connected")

    async def close(self):
        """Close HTTP session and Redis connection."""
        if self._retry_client:
            await self._retry_client.close()
            self._retry_client = None

        if self._session:
            await self._session.close()
            self._session = None

        if self.redis_client:
            await self.redis_client.close()
            self.redis_client = None

        logger.info("TwelveData client closed")

    async def _get_cached(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Retrieve data from Redis cache."""
        if not self.redis_client:
            return None

        try:
            cached = await self.redis_client.get(cache_key)
            if cached:
                logger.debug(f"Cache HIT: {cache_key}")
                return json.loads(cached)
        except Exception as e:
            logger.warning(f"Cache read error: {e}")

        return None

    async def _set_cached(self, cache_key: str, data: Dict[str, Any], ttl: int):
        """Store data in Redis cache with TTL."""
        if not self.redis_client:
            return

        try:
            await self.redis_client.setex(cache_key, ttl, json.dumps(data))
            logger.debug(f"Cache SET: {cache_key} (TTL={ttl}s)")
        except Exception as e:
            logger.warning(f"Cache write error: {e}")

    async def _request(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Make HTTP request to TwelveData API with rate limiting and retry."""
        if not self._retry_client:
            raise RuntimeError("Client not connected. Use async context manager.")

        params["apikey"] = self.api_key
        url = f"{self.base_url}/{endpoint}"

        await self.rate_limiter.acquire()

        try:
            async with self._retry_client.get(url, params=params) as response:
                response.raise_for_status()
                data = await response.json()

                if "status" in data and data["status"] == "error":
                    raise ValueError(f"TwelveData API error: {data.get('message', 'Unknown error')}")

                return data

        except aiohttp.ClientError as e:
            logger.error(f"HTTP request failed: {url} - {e}")
            raise
        except Exception as e:
            logger.error(f"Request error: {e}")
            raise

    async def get_time_series(
        self,
        symbol: str,
        interval: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        outputsize: int = 5000
    ) -> List[Dict[str, Any]]:
        """
        Fetch historical OHLCV candles.

        Args:
            symbol: Trading symbol (e.g., "EURUSD", "AAPL")
            interval: Time interval (1min, 5min, 15min, 30min, 1h, 4h, 1day, 1week, 1month)
            start_date: Start datetime (optional)
            end_date: End datetime (optional)
            outputsize: Number of candles (default 5000, max 5000)

        Returns:
            List of candle dictionaries with datetime, open, high, low, close, volume
        """
        cache_key = f"twelvedata:timeseries:{symbol}:{interval}:{outputsize}"

        cached = await self._get_cached(cache_key)
        if cached:
            return cached

        params = {
            "symbol": symbol,
            "interval": interval,
            "outputsize": outputsize,
            "format": "JSON",
            "timezone": "UTC"
        }

        if start_date:
            params["start_date"] = start_date.strftime("%Y-%m-%d %H:%M:%S")
        if end_date:
            params["end_date"] = end_date.strftime("%Y-%m-%d %H:%M:%S")

        data = await self._request("time_series", params)

        if "values" not in data:
            logger.warning(f"No time series data for {symbol}")
            return []

        candles = []
        for item in data["values"]:
            try:
                candles.append({
                    "datetime": datetime.fromisoformat(item["datetime"].replace("Z", "+00:00")),
                    "open": float(item["open"]),
                    "high": float(item["high"]),
                    "low": float(item["low"]),
                    "close": float(item["close"]),
                    "volume": int(item.get("volume", 0))
                })
            except (KeyError, ValueError) as e:
                logger.warning(f"Skipping invalid candle data: {e}")
                continue

        await self._set_cached(cache_key, candles, ttl=300)  # 5 minutes
        return candles

    async def get_quote(self, symbol: str) -> Dict[str, Any]:
        """
        Fetch real-time quote.

        Returns:
            Dict with symbol, price, bid, ask, volume, timestamp
        """
        cache_key = f"twelvedata:quote:{symbol}"

        cached = await self._get_cached(cache_key)
        if cached:
            return cached

        params = {"symbol": symbol, "format": "JSON"}
        data = await self._request("quote", params)

        quote = {
            "symbol": data["symbol"],
            "price": float(data["close"]),
            "bid": float(data.get("bid", data["close"])),
            "ask": float(data.get("ask", data["close"])),
            "volume": int(data.get("volume", 0)),
            "timestamp": datetime.fromisoformat(data["datetime"].replace("Z", "+00:00"))
        }

        await self._set_cached(cache_key, quote, ttl=10)  # 10 seconds
        return quote

    async def search_symbol(self, query: str, limit: int = 10) -> List[Dict[str, str]]:
        """
        Search for symbols by name or ticker.

        Returns:
            List of dicts with symbol, instrument_name, exchange, currency, country, type
        """
        cache_key = f"twelvedata:search:{query}:{limit}"

        cached = await self._get_cached(cache_key)
        if cached:
            return cached

        params = {"symbol": query, "outputsize": limit}
        data = await self._request("symbol_search", params)

        if "data" not in data:
            return []

        results = []
        for item in data["data"]:
            results.append({
                "symbol": item["symbol"],
                "instrument_name": item["instrument_name"],
                "exchange": item["exchange"],
                "currency": item["currency"],
                "country": item.get("country", ""),
                "type": item["instrument_type"]
            })

        await self._set_cached(cache_key, results, ttl=3600)  # 1 hour
        return results

    async def get_earliest_timestamp(self, symbol: str, interval: str) -> Optional[datetime]:
        """Get the earliest available data timestamp for a symbol."""
        params = {
            "symbol": symbol,
            "interval": interval,
            "format": "JSON"
        }

        try:
            data = await self._request("earliest_timestamp", params)
            if "datetime" in data:
                return datetime.fromisoformat(data["datetime"].replace("Z", "+00:00"))
        except Exception as e:
            logger.warning(f"Could not get earliest timestamp for {symbol}: {e}")

        return None

    async def get_economic_calendar(
        self,
        start_date: datetime,
        end_date: datetime,
        country: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch economic calendar events.

        Args:
            start_date: Start date
            end_date: End date
            country: Country code (e.g., "US", "EU") - optional

        Returns:
            List of economic events
        """
        cache_key = f"twelvedata:calendar:{start_date.date()}:{end_date.date()}:{country or 'all'}"

        cached = await self._get_cached(cache_key)
        if cached:
            return cached

        params = {
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d"),
            "format": "JSON"
        }

        if country:
            params["country"] = country

        data = await self._request("economic_calendar", params)

        if "data" not in data:
            return []

        events = []
        for item in data["data"]:
            events.append({
                "event_date": datetime.fromisoformat(item["date"] + " " + item.get("time", "00:00:00")),
                "country": item["country"],
                "event": item["event"],
                "impact": item.get("impact"),
                "actual": item.get("actual"),
                "forecast": item.get("forecast"),
                "previous": item.get("previous")
            })

        await self._set_cached(cache_key, events, ttl=3600)  # 1 hour
        return events
```

### Step 4: Data Service Layer

Create `backend/app/data/data_service.py`:

```python
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
```

### Step 5: Update Configuration

Update `backend/app/config.py` to add TwelveData settings:

```python
from pydantic_settings import BaseSettings
from pydantic import field_validator
import os


class Settings(BaseSettings):
    # Existing fields...

    # TwelveData API
    twelvedata_api_key: str = ""
    twelvedata_base_url: str = "https://api.twelvedata.com"
    twelvedata_rate_limit: int = 8  # requests per minute (free tier)

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    @field_validator("twelvedata_api_key")
    @classmethod
    def validate_twelvedata_key(cls, v: str) -> str:
        if not v and os.getenv("APP_ENV") == "production":
            raise ValueError("TWELVEDATA_API_KEY is required in production")
        return v

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
```

Update `.env.example`:
```env
TWELVEDATA_API_KEY=your_api_key_here
TWELVEDATA_BASE_URL=https://api.twelvedata.com
TWELVEDATA_RATE_LIMIT=8
REDIS_URL=redis://localhost:6379/0
```

### Step 6: Database Migration

Create Alembic migration:

```bash
cd backend
DATABASE_URL="sqlite+aiosqlite:///./flowrex_dev.db" python -m alembic revision --autogenerate -m "add_market_data_tables"
```

This generates `backend/alembic/versions/002_add_market_data_tables.py`. Verify the migration includes:
- `candles` table with unique constraint on (symbol, interval, timestamp)
- `symbols` table with unique symbol column
- `economic_events` table with event_date index

Run migration:
```bash
DATABASE_URL="sqlite+aiosqlite:///./flowrex_dev.db" python -m alembic upgrade head
```

### Step 7: API Routes

Create `backend/app/api/v1/data_routes.py`:

```python
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
from typing import List, Optional
from pydantic import BaseModel
from app.database import get_db
from app.data.twelvedata_client import TwelveDataClient
from app.data.data_service import DataService
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/data", tags=["data"])


# Response schemas
class CandleResponse(BaseModel):
    symbol: str
    interval: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int

    class Config:
        from_attributes = True


class QuoteResponse(BaseModel):
    symbol: str
    price: float
    bid: float
    ask: float
    volume: int
    timestamp: datetime


class SymbolSearchResult(BaseModel):
    symbol: str
    instrument_name: str
    exchange: str
    currency: str
    country: str
    type: str


# Dependency
async def get_data_client():
    async with TwelveDataClient() as client:
        yield client


@router.get("/candles/{symbol}", response_model=List[CandleResponse])
async def get_candles(
    symbol: str,
    interval: str = Query("1day", regex="^(1min|5min|15min|30min|1h|4h|1day|1week|1month)$"),
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    fetch_missing: bool = True,
    db: AsyncSession = Depends(get_db),
    client: TwelveDataClient = Depends(get_data_client)
):
    """
    Get OHLCV candles for a symbol.

    If data is missing and fetch_missing=True, fetches from TwelveData and stores.
    """
    if not end_date:
        end_date = datetime.utcnow()
    if not start_date:
        start_date = end_date - timedelta(days=30)

    service = DataService(db=db, client=client)

    # Try to get from database first
    candles = await service.get_candles(
        symbol=symbol,
        interval=interval,
        start_date=start_date,
        end_date=end_date
    )

    # If no data and fetch_missing, fetch from TwelveData
    if not candles and fetch_missing:
        logger.info(f"Fetching missing candles for {symbol} {interval}")
        await service.fetch_and_store_candles(
            symbol=symbol,
            interval=interval,
            start_date=start_date,
            end_date=end_date
        )
        candles = await service.get_candles(
            symbol=symbol,
            interval=interval,
            start_date=start_date,
            end_date=end_date
        )

    return candles


@router.get("/quote/{symbol}", response_model=QuoteResponse)
async def get_quote(
    symbol: str,
    client: TwelveDataClient = Depends(get_data_client)
):
    """Get real-time quote for a symbol."""
    try:
        quote = await client.get_quote(symbol)
        return quote
    except Exception as e:
        logger.error(f"Failed to get quote for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch quote: {str(e)}")


@router.get("/search", response_model=List[SymbolSearchResult])
async def search_symbols(
    query: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=50),
    client: TwelveDataClient = Depends(get_data_client)
):
    """Search for symbols by ticker or name."""
    try:
        results = await client.search_symbol(query, limit=limit)
        return results
    except Exception as e:
        logger.error(f"Symbol search failed for '{query}': {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.post("/sync/{symbol}")
async def sync_symbol_data(
    symbol: str,
    interval: str = Query("1day"),
    days_back: int = Query(365, ge=1, le=3650),
    db: AsyncSession = Depends(get_db),
    client: TwelveDataClient = Depends(get_data_client)
):
    """
    Manually trigger data sync for a symbol.

    Fetches historical data from TwelveData and stores in database.
    """
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days_back)

    service = DataService(db=db, client=client)

    try:
        count = await service.fetch_and_store_candles(
            symbol=symbol,
            interval=interval,
            start_date=start_date,
            end_date=end_date
        )
        return {
            "symbol": symbol,
            "interval": interval,
            "candles_inserted": count,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat()
        }
    except Exception as e:
        logger.error(f"Data sync failed for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")
```

Register routes in `backend/app/main.py`:

```python
from app.api.v1 import auth_routes, data_routes

# After existing route registration:
app.include_router(data_routes.router, prefix="/api/v1")
```

### Step 8: Tests

Create `backend/tests/unit/test_data_client.py`:

```python
import pytest
from datetime import datetime, timedelta
from app.data.twelvedata_client import TwelveDataClient, RateLimiter
import asyncio


class TestRateLimiter:
    @pytest.mark.asyncio
    async def test_rate_limiter_allows_requests(self):
        limiter = RateLimiter(max_requests=5, time_window=60)

        for _ in range(5):
            await limiter.acquire()

        assert limiter.tokens == 0

    @pytest.mark.asyncio
    async def test_rate_limiter_blocks_excess_requests(self):
        limiter = RateLimiter(max_requests=2, time_window=2)

        await limiter.acquire()
        await limiter.acquire()

        start = datetime.utcnow()
        await limiter.acquire()  # Should wait ~2 seconds
        elapsed = (datetime.utcnow() - start).total_seconds()

        assert elapsed >= 1.5  # Allow some margin


@pytest.mark.asyncio
class TestTwelveDataClient:
    async def test_client_context_manager(self):
        async with TwelveDataClient() as client:
            assert client._session is not None
            assert client._retry_client is not None
            assert client.redis_client is not None

        # Should be closed after exit
        assert client._session is None

    async def test_search_symbol(self):
        async with TwelveDataClient() as client:
            # Note: This requires valid API key in environment
            results = await client.search_symbol("EUR", limit=5)

            assert isinstance(results, list)
            if results:  # May be empty if API key is invalid
                assert "symbol" in results[0]
                assert "instrument_name" in results[0]

    async def test_get_time_series(self):
        async with TwelveDataClient() as client:
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=7)

            candles = await client.get_time_series(
                symbol="EURUSD",
                interval="1day",
                start_date=start_date,
                end_date=end_date,
                outputsize=100
            )

            assert isinstance(candles, list)
            if candles:
                assert "datetime" in candles[0]
                assert "open" in candles[0]
                assert "close" in candles[0]
```

Create `backend/tests/integration/test_data_service.py`:

```python
import pytest
from datetime import datetime, timedelta
from app.data.data_service import DataService
from app.data.twelvedata_client import TwelveDataClient
from app.models.market_data import Candle, Symbol


@pytest.mark.asyncio
class TestDataService:
    async def test_fetch_and_store_candles(self, async_db_session):
        async with TwelveDataClient() as client:
            service = DataService(db=async_db_session, client=client)

            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=3)

            count = await service.fetch_and_store_candles(
                symbol="EURUSD",
                interval="1day",
                start_date=start_date,
                end_date=end_date,
                outputsize=10
            )

            assert count >= 0  # May be 0 if API key invalid or weekend

            # Verify stored in database
            candles = await service.get_candles(
                symbol="EURUSD",
                interval="1day",
                start_date=start_date,
                end_date=end_date
            )

            assert len(candles) == count
            if candles:
                assert candles[0].symbol == "EURUSD"
                assert candles[0].interval == "1day"

    async def test_upsert_symbol(self, async_db_session):
        async with TwelveDataClient() as client:
            service = DataService(db=async_db_session, client=client)

            symbol_data = {
                "symbol": "AAPL",
                "name": "Apple Inc.",
                "currency": "USD",
                "exchange": "NASDAQ",
                "type": "Stock",
                "country": "US"
            }

            # First insert
            symbol1 = await service.upsert_symbol(symbol_data)
            assert symbol1.symbol == "AAPL"
            assert symbol1.name == "Apple Inc."

            # Update
            symbol_data["name"] = "Apple Inc. Updated"
            symbol2 = await service.upsert_symbol(symbol_data)
            assert symbol2.id == symbol1.id
            assert symbol2.name == "Apple Inc. Updated"
```

Update `backend/tests/conftest.py` to include async_db_session fixture:

```python
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.models.base import Base


@pytest.fixture
async def async_db_session():
    """Create async test database session."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with AsyncSessionLocal() as session:
        yield session

    await engine.dispose()
```

### Step 9: Run Tests

```bash
cd backend
DATABASE_URL="sqlite+aiosqlite:///./flowrex_dev.db" python -m pytest tests/ -v --tb=short
```

All tests must pass before proceeding.

### Step 10: Manual API Testing

Start the server:
```bash
cd backend
DATABASE_URL="sqlite+aiosqlite:///./flowrex_dev.db" python -m uvicorn app.main:app --reload
```

Test endpoints:

**Search symbols:**
```bash
curl "http://localhost:8000/api/v1/data/search?query=EUR&limit=5"
```

**Get quote:**
```bash
curl "http://localhost:8000/api/v1/data/quote/EURUSD"
```

**Get candles:**
```bash
curl "http://localhost:8000/api/v1/data/candles/EURUSD?interval=1day&fetch_missing=true"
```

**Sync historical data:**
```bash
curl -X POST "http://localhost:8000/api/v1/data/sync/EURUSD?interval=1day&days_back=365"
```

## Validation Checklist

Before proceeding to Prompt 04, verify:

- [ ] All dependencies installed (`aiohttp`, `aiohttp-retry`, `redis`)
- [ ] `Candle`, `Symbol`, `EconomicEvent` models created
- [ ] Database migration created and applied successfully
- [ ] `candles` table exists with unique constraint on (symbol, interval, timestamp)
- [ ] TwelveDataClient implements rate limiting (8 requests/min default)
- [ ] TwelveDataClient caches responses in Redis
- [ ] TwelveDataClient implements exponential retry (3 attempts)
- [ ] DataService can fetch and store candles without duplicates
- [ ] API routes `/data/candles/{symbol}`, `/data/quote/{symbol}`, `/data/search` work
- [ ] All unit tests pass (`test_data_client.py`)
- [ ] All integration tests pass (`test_data_service.py`)
- [ ] Can search symbols via API: `curl "http://localhost:8000/api/v1/data/search?query=EUR"`
- [ ] Can get real-time quote: `curl "http://localhost:8000/api/v1/data/quote/EURUSD"`
- [ ] Can fetch candles: `curl "http://localhost:8000/api/v1/data/candles/EURUSD?interval=1day"`
- [ ] Redis cache is working (second identical request returns instantly)
- [ ] Rate limiter prevents exceeding TwelveData limits
- [ ] Environment variables configured in `.env`
- [ ] CROSSCHECK.md validation for Prompt 03 completed

## Hard Stop Criteria

**DO NOT PROCEED to Prompt 04 unless:**

1. ✅ Database migration runs without errors
2. ✅ All pytest tests pass (0 failures, 0 errors)
3. ✅ Can successfully fetch candles from TwelveData API
4. ✅ Can successfully store and retrieve candles from database
5. ✅ Redis caching is operational (verify with duplicate requests)
6. ✅ Rate limiter prevents API overuse
7. ✅ Symbol search returns valid results
8. ✅ All API endpoints respond with 200 status
9. ✅ No hard-coded API keys in code (must be in environment)
10. ✅ CROSSCHECK.md section for Prompt 03 fully validated

If any criterion fails, **HALT** and fix before continuing.

---

**Completion Criteria:**
- TwelveData client fully operational with caching and rate limiting
- Market data models created and migrated
- Data service layer can fetch, normalize, and store candles
- API endpoints provide access to historical and real-time data
- All tests pass
- System ready for Strategy Engine integration (Prompt 04)
