import aiohttp
import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta, timezone
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
        self.last_refill = datetime.now(timezone.utc)
        self._lock = asyncio.Lock()

    async def acquire(self):
        """Wait until a token is available."""
        async with self._lock:
            now = datetime.now(timezone.utc)
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
                    self.last_refill = datetime.now(timezone.utc)

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

    async def _get_cached(self, cache_key: str) -> Optional[Any]:
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

    async def _set_cached(self, cache_key: str, data: Any, ttl: int):
        """Store data in Redis cache with TTL."""
        if not self.redis_client:
            return

        try:
            await self.redis_client.setex(cache_key, ttl, json.dumps(data, default=str))
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
            # Convert string datetimes back to datetime objects
            for candle in cached:
                if isinstance(candle.get("datetime"), str):
                    candle["datetime"] = datetime.fromisoformat(candle["datetime"])
            return cached

        params: Dict[str, Any] = {
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
                dt_str = item["datetime"]
                if "Z" in dt_str:
                    dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                elif "+" in dt_str or dt_str.endswith("-00:00"):
                    dt = datetime.fromisoformat(dt_str)
                else:
                    dt = datetime.fromisoformat(dt_str).replace(tzinfo=timezone.utc)

                candles.append({
                    "datetime": dt,
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
            if isinstance(cached.get("timestamp"), str):
                cached["timestamp"] = datetime.fromisoformat(cached["timestamp"])
            return cached

        params = {"symbol": symbol, "format": "JSON"}
        data = await self._request("quote", params)

        dt_str = data["datetime"]
        if "Z" in dt_str:
            dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        elif "+" in dt_str or dt_str.endswith("-00:00"):
            dt = datetime.fromisoformat(dt_str)
        else:
            dt = datetime.fromisoformat(dt_str).replace(tzinfo=timezone.utc)

        quote = {
            "symbol": data["symbol"],
            "price": float(data["close"]),
            "bid": float(data.get("bid", data["close"])),
            "ask": float(data.get("ask", data["close"])),
            "volume": int(data.get("volume", 0)),
            "timestamp": dt
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
                dt_str = data["datetime"]
                if "Z" in dt_str:
                    return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                return datetime.fromisoformat(dt_str).replace(tzinfo=timezone.utc)
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
            for event in cached:
                if isinstance(event.get("event_date"), str):
                    event["event_date"] = datetime.fromisoformat(event["event_date"])
            return cached

        params: Dict[str, Any] = {
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
            time_str = item.get("time", "00:00:00")
            dt_str = f"{item['date']} {time_str}"
            try:
                dt = datetime.fromisoformat(dt_str).replace(tzinfo=timezone.utc)
            except ValueError:
                dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)

            events.append({
                "event_date": dt,
                "country": item["country"],
                "event": item["event"],
                "impact": item.get("impact"),
                "actual": item.get("actual"),
                "forecast": item.get("forecast"),
                "previous": item.get("previous")
            })

        await self._set_cached(cache_key, events, ttl=3600)  # 1 hour
        return events
