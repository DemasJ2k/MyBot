import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone

from app.data.data_service import DataService
from app.models.market_data import Candle


class TestDataService:
    @pytest_asyncio.fixture
    async def mock_db(self):
        """Create mock database session."""
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        return db

    @pytest_asyncio.fixture
    async def mock_client(self):
        """Create mock TwelveData client."""
        client = AsyncMock()
        return client

    @pytest.mark.asyncio
    async def test_fetch_and_store_candles_inserts_new(self, mock_db, mock_client):
        """Test that new candles are inserted."""
        mock_client.get_time_series = AsyncMock(return_value=[
            {
                "datetime": datetime(2024, 1, 15, 12, 0, tzinfo=timezone.utc),
                "open": 1.0950,
                "high": 1.0980,
                "low": 1.0930,
                "close": 1.0960,
                "volume": 1000
            }
        ])

        # Mock execute to return no existing candle
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        mock_db.execute = AsyncMock(return_value=mock_result)

        service = DataService(mock_db, mock_client)
        inserted = await service.fetch_and_store_candles("EURUSD", "1h")

        assert inserted == 1
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_and_store_candles_skips_existing(self, mock_db, mock_client):
        """Test that existing candles are skipped."""
        mock_client.get_time_series = AsyncMock(return_value=[
            {
                "datetime": datetime(2024, 1, 15, 12, 0, tzinfo=timezone.utc),
                "open": 1.0950,
                "high": 1.0980,
                "low": 1.0930,
                "close": 1.0960,
                "volume": 1000
            }
        ])

        # Mock execute to return existing candle
        existing_candle = MagicMock(spec=Candle)
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=existing_candle)
        mock_db.execute = AsyncMock(return_value=mock_result)

        service = DataService(mock_db, mock_client)
        inserted = await service.fetch_and_store_candles("EURUSD", "1h")

        assert inserted == 0
        mock_db.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_fetch_and_store_candles_empty_response(self, mock_db, mock_client):
        """Test handling of empty API response."""
        mock_client.get_time_series = AsyncMock(return_value=[])

        service = DataService(mock_db, mock_client)
        inserted = await service.fetch_and_store_candles("INVALID", "1h")

        assert inserted == 0

    @pytest.mark.asyncio
    async def test_get_candles_returns_data(self, mock_db, mock_client):
        """Test that get_candles queries database correctly."""
        mock_candles = [
            MagicMock(spec=Candle),
            MagicMock(spec=Candle)
        ]

        mock_scalars = MagicMock()
        mock_scalars.all = MagicMock(return_value=mock_candles)
        mock_result = AsyncMock()
        mock_result.scalars = MagicMock(return_value=mock_scalars)
        mock_db.execute = AsyncMock(return_value=mock_result)

        service = DataService(mock_db, mock_client)
        candles = await service.get_candles(
            symbol="EURUSD",
            interval="1h",
            start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2024, 1, 31, tzinfo=timezone.utc)
        )

        assert len(candles) == 2
        mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_upsert_symbol_creates_new(self, mock_db, mock_client):
        """Test that new symbols are created."""
        # Mock execute to return no existing symbol
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        mock_db.execute = AsyncMock(return_value=mock_result)

        service = DataService(mock_db, mock_client)
        symbol_data = {
            "symbol": "EURUSD",
            "name": "Euro / US Dollar",
            "exchange": "FOREX",
            "currency": "USD",
            "type": "forex"
        }

        await service.upsert_symbol(symbol_data)

        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
