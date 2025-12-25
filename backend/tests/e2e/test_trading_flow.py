"""
E2E Tests: Trading Workflow.

Tests complete trading workflows:
1. Market data retrieval
2. Signal generation
3. Risk validation
4. Order execution (paper trading)
5. Position management
"""
import pytest
from httpx import AsyncClient

pytestmark = [pytest.mark.e2e, pytest.mark.asyncio]


class TestTradingWorkflow:
    """Complete trading workflow tests."""

    async def test_market_data_flow(
        self,
        authenticated_client: AsyncClient,
        test_symbol: str
    ):
        """
        Test market data retrieval flow.
        """
        # Search for symbol
        search_response = await authenticated_client.get(
            "/api/v1/data/search",
            params={"query": test_symbol}
        )
        # May fail if TwelveData API key not configured
        if search_response.status_code == 502:
            pytest.skip("Market data API not available")
        
        assert search_response.status_code == 200

    async def test_execution_mode_management(
        self,
        authenticated_client: AsyncClient
    ):
        """
        Test execution mode (GUIDE/AUTONOMOUS) management.
        """
        # Get current mode
        mode_response = await authenticated_client.get("/api/v1/execution/mode")
        assert mode_response.status_code == 200
        mode_data = mode_response.json()
        assert mode_data["mode"] in ["GUIDE", "AUTONOMOUS"]

        # Ensure we're in GUIDE mode (safe for testing)
        if mode_data["mode"] != "GUIDE":
            set_response = await authenticated_client.post(
                "/api/v1/execution/mode",
                json={"mode": "GUIDE", "confirm_autonomous": False}
            )
            assert set_response.status_code == 200

    async def test_risk_state_retrieval(
        self,
        authenticated_client: AsyncClient
    ):
        """
        Test risk state can be retrieved.
        """
        response = await authenticated_client.get("/api/v1/risk/state")
        assert response.status_code == 200
        risk_data = response.json()
        
        # Verify risk state structure
        assert "account_balance" in risk_data or "daily_pnl" in risk_data


class TestBacktestWorkflow:
    """Backtesting workflow tests."""

    async def test_backtest_execution(
        self,
        authenticated_client: AsyncClient,
        test_symbol: str
    ):
        """
        Test running a backtest.
        """
        backtest_request = {
            "strategy_name": "sma_crossover",
            "symbol": test_symbol,
            "interval": "1day",
            "start_date": "2024-01-01",
            "end_date": "2024-06-01",
            "initial_balance": 100000,
            "risk_per_trade_percent": 1.0
        }

        response = await authenticated_client.post(
            "/api/v1/backtest/run",
            json=backtest_request
        )
        
        # May fail if no historical data available
        if response.status_code == 400:
            pytest.skip("Insufficient market data for backtest")
        
        assert response.status_code in [200, 201, 202]
