import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone

from app.data.twelvedata_client import TwelveDataClient, RateLimiter


class TestRateLimiter:
    @pytest.mark.asyncio
    async def test_acquire_token_available(self):
        limiter = RateLimiter(max_requests=10, time_window=60)
        assert limiter.tokens == 10

        await limiter.acquire()
        assert limiter.tokens == 9

    @pytest.mark.asyncio
    async def test_acquire_multiple_tokens(self):
        limiter = RateLimiter(max_requests=5, time_window=60)

        for i in range(5):
            await limiter.acquire()

        assert limiter.tokens == 0


class TestTwelveDataClient:
    @pytest_asyncio.fixture
    async def mock_client(self):
        """Create client with mocked dependencies."""
        with patch('app.data.twelvedata_client.aioredis') as mock_redis:
            mock_redis_instance = AsyncMock()
            mock_redis_instance.get = AsyncMock(return_value=None)
            mock_redis_instance.setex = AsyncMock()
            mock_redis_instance.close = AsyncMock()
            mock_redis.from_url = AsyncMock(return_value=mock_redis_instance)

            client = TwelveDataClient()
            client.redis_client = mock_redis_instance
            yield client

    @pytest.mark.asyncio
    async def test_client_initialization(self):
        client = TwelveDataClient()
        assert client.base_url == "https://api.twelvedata.com"
        assert client._session is None
        assert client.redis_client is None

    @pytest.mark.asyncio
    async def test_get_time_series_response_parsing(self, mock_client):
        """Test that time series data is correctly parsed."""
        mock_response = {
            "meta": {"symbol": "EURUSD"},
            "values": [
                {
                    "datetime": "2024-01-15 12:00:00",
                    "open": "1.0950",
                    "high": "1.0980",
                    "low": "1.0930",
                    "close": "1.0960",
                    "volume": "1000"
                },
                {
                    "datetime": "2024-01-15 11:00:00",
                    "open": "1.0940",
                    "high": "1.0970",
                    "low": "1.0920",
                    "close": "1.0950",
                    "volume": "800"
                }
            ]
        }

        with patch.object(mock_client, '_request', new_callable=AsyncMock) as mock_req:
            mock_req.return_value = mock_response

            candles = await mock_client.get_time_series("EURUSD", "1h")

            assert len(candles) == 2
            assert candles[0]["open"] == 1.0950
            assert candles[0]["close"] == 1.0960
            assert candles[1]["volume"] == 800

    @pytest.mark.asyncio
    async def test_get_quote_response_parsing(self, mock_client):
        """Test that quote data is correctly parsed."""
        mock_response = {
            "symbol": "AAPL",
            "datetime": "2024-01-15 15:00:00",
            "close": "185.50",
            "volume": "50000000"
        }

        with patch.object(mock_client, '_request', new_callable=AsyncMock) as mock_req:
            mock_req.return_value = mock_response

            quote = await mock_client.get_quote("AAPL")

            assert quote["symbol"] == "AAPL"
            assert quote["price"] == 185.50
            assert quote["volume"] == 50000000

    @pytest.mark.asyncio
    async def test_search_symbol_response_parsing(self, mock_client):
        """Test that symbol search results are correctly parsed."""
        mock_response = {
            "data": [
                {
                    "symbol": "AAPL",
                    "instrument_name": "Apple Inc",
                    "exchange": "NASDAQ",
                    "currency": "USD",
                    "country": "United States",
                    "instrument_type": "Common Stock"
                }
            ]
        }

        with patch.object(mock_client, '_request', new_callable=AsyncMock) as mock_req:
            mock_req.return_value = mock_response

            results = await mock_client.search_symbol("AAPL")

            assert len(results) == 1
            assert results[0]["symbol"] == "AAPL"
            assert results[0]["type"] == "Common Stock"

    @pytest.mark.asyncio
    async def test_get_time_series_empty_response(self, mock_client):
        """Test handling of empty API response."""
        mock_response = {"meta": {"symbol": "INVALID"}}

        with patch.object(mock_client, '_request', new_callable=AsyncMock) as mock_req:
            mock_req.return_value = mock_response

            candles = await mock_client.get_time_series("INVALID", "1h")
            assert candles == []
