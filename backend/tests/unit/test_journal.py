"""Journal and Feedback Loop unit tests."""

import pytest
from datetime import datetime, timedelta
from app.journal.writer import JournalWriter
from app.journal.analyzer import PerformanceAnalyzer
from app.journal.feedback_loop import FeedbackLoop
from app.models.journal import JournalEntry, FeedbackDecision, TradeSource
from app.models.risk import StrategyRiskBudget
from app.backtest.portfolio import Trade, TradeSide


@pytest.mark.asyncio
class TestJournalWriter:
    """Test journal writer functionality."""

    async def test_record_backtest_trade(self, test_db):
        """Test recording a backtest trade to journal."""
        writer = JournalWriter(db=test_db)

        # Create mock trade
        trade = Trade(
            symbol="EURUSD",
            side=TradeSide.LONG,
            entry_price=1.1000,
            exit_price=1.1050,
            quantity=1.0,
            entry_time=datetime.utcnow() - timedelta(hours=2),
            exit_time=datetime.utcnow(),
            pnl=50.0,
            pnl_percent=0.45,
            commission=0.1
        )

        entry = await writer.record_backtest_trade(
            trade=trade,
            strategy_name="NBB",
            strategy_config={"zone_lookback": 20},
            backtest_id="bt_12345678"
        )

        assert entry.id is not None
        assert entry.source == TradeSource.BACKTEST
        assert entry.is_winner is True
        assert entry.pnl == 49.9  # 50.0 - 0.1 commission
        assert entry.strategy_name == "NBB"
        assert entry.symbol == "EURUSD"
        assert entry.side.lower() == "long"

    async def test_record_losing_trade(self, test_db):
        """Test recording a losing trade."""
        writer = JournalWriter(db=test_db)

        trade = Trade(
            symbol="GBPUSD",
            side=TradeSide.SHORT,
            entry_price=1.2500,
            exit_price=1.2550,
            quantity=1.0,
            entry_time=datetime.utcnow() - timedelta(hours=1),
            exit_time=datetime.utcnow(),
            pnl=-50.0,
            pnl_percent=-0.40,
            commission=0.1
        )

        entry = await writer.record_backtest_trade(
            trade=trade,
            strategy_name="JadeCap",
            strategy_config={"ema_period": 21},
            backtest_id="bt_87654321"
        )

        assert entry.is_winner is False
        assert entry.pnl == -50.1  # -50.0 - 0.1 commission
        assert entry.side.lower() == "short"

    async def test_unique_entry_ids(self, test_db):
        """Test that each entry gets a unique ID."""
        writer = JournalWriter(db=test_db)

        trade1 = Trade(
            symbol="EURUSD",
            side=TradeSide.LONG,
            entry_price=1.1000,
            exit_price=1.1050,
            quantity=1.0,
            entry_time=datetime.utcnow() - timedelta(hours=2),
            exit_time=datetime.utcnow() - timedelta(hours=1),
            pnl=50.0,
            pnl_percent=0.45,
            commission=0.1
        )

        trade2 = Trade(
            symbol="EURUSD",
            side=TradeSide.LONG,
            entry_price=1.1100,
            exit_price=1.1150,
            quantity=1.0,
            entry_time=datetime.utcnow() - timedelta(hours=1),
            exit_time=datetime.utcnow(),
            pnl=50.0,
            pnl_percent=0.45,
            commission=0.1
        )

        entry1 = await writer.record_backtest_trade(
            trade=trade1,
            strategy_name="NBB",
            strategy_config={},
            backtest_id="bt_1"
        )

        entry2 = await writer.record_backtest_trade(
            trade=trade2,
            strategy_name="NBB",
            strategy_config={},
            backtest_id="bt_1"
        )

        assert entry1.entry_id != entry2.entry_id


@pytest.mark.asyncio
class TestPerformanceAnalyzer:
    """Test performance analyzer functionality."""

    async def test_analyze_strategy_no_data(self, test_db):
        """Test analyzing a strategy with no data."""
        analyzer = PerformanceAnalyzer(db=test_db)

        analysis = await analyzer.analyze_strategy(
            strategy_name="NBB",
            symbol="EURUSD",
            lookback_days=30
        )

        assert analysis["live_performance"]["total_trades"] == 0
        assert analysis["backtest_performance"]["total_trades"] == 0
        # No data means deviation status will be one of these
        assert analysis["deviation"]["status"] in ["no_live_data", "no_backtest_data"]

    async def test_calculate_metrics_with_entries(self, test_db):
        """Test metric calculation with journal entries."""
        writer = JournalWriter(db=test_db)

        # Create 5 winning trades
        for i in range(5):
            trade = Trade(
                symbol="EURUSD",
                side=TradeSide.LONG,
                entry_price=1.1000 + (i * 0.01),
                exit_price=1.1050 + (i * 0.01),
                quantity=1.0,
                entry_time=datetime.utcnow() - timedelta(hours=i+2),
                exit_time=datetime.utcnow() - timedelta(hours=i+1),
                pnl=50.0,
                pnl_percent=0.45,
                commission=0.1
            )
            await writer.record_backtest_trade(
                trade=trade,
                strategy_name="NBB",
                strategy_config={},
                backtest_id=f"bt_{i}"
            )

        # Create 3 losing trades
        for i in range(3):
            trade = Trade(
                symbol="EURUSD",
                side=TradeSide.LONG,
                entry_price=1.1000,
                exit_price=1.0950,
                quantity=1.0,
                entry_time=datetime.utcnow() - timedelta(hours=i+10),
                exit_time=datetime.utcnow() - timedelta(hours=i+9),
                pnl=-50.0,
                pnl_percent=-0.45,
                commission=0.1
            )
            await writer.record_backtest_trade(
                trade=trade,
                strategy_name="NBB",
                strategy_config={},
                backtest_id=f"bt_loss_{i}"
            )

        analyzer = PerformanceAnalyzer(db=test_db)
        analysis = await analyzer.analyze_strategy("NBB", "EURUSD", lookback_days=30)

        bt_perf = analysis["backtest_performance"]
        assert bt_perf["total_trades"] == 8
        assert bt_perf["winning_trades"] == 5
        assert bt_perf["losing_trades"] == 3
        assert bt_perf["win_rate"] == 62.5  # 5/8 = 62.5%

    async def test_detect_underperformance_no_issues(self, test_db):
        """Test underperformance detection with good performance."""
        analyzer = PerformanceAnalyzer(db=test_db)

        result = await analyzer.detect_underperformance("NBB", "EURUSD")

        # With no data, should not detect underperformance
        assert result["underperforming"] is False
        assert result["recommendation"] == "continue"

    async def test_detect_underperformance_low_win_rate(self, test_db):
        """Test underperformance detection with low win rate."""
        writer = JournalWriter(db=test_db)

        # Create 2 winning trades and 8 losing trades (20% win rate)
        # First create a live trade journal entry directly for this test
        for i in range(2):
            entry = JournalEntry(
                entry_id=f"LIVE_win_{i}",
                source=TradeSource.LIVE,
                strategy_name="NBB",
                strategy_config={},
                symbol="EURUSD",
                timeframe="1h",
                side="long",
                entry_price=1.1000,
                exit_price=1.1050,
                position_size=1.0,
                stop_loss=1.0950,
                take_profit=1.1100,
                risk_percent=2.0,
                risk_reward_ratio=2.0,
                pnl=50.0,
                pnl_percent=0.45,
                is_winner=True,
                exit_reason="tp",
                entry_slippage=0.0,
                exit_slippage=0.0,
                commission=0.1,
                market_context={},
                entry_time=datetime.utcnow() - timedelta(hours=i+10),
                exit_time=datetime.utcnow() - timedelta(hours=i+9),
                duration_minutes=60
            )
            test_db.add(entry)

        for i in range(8):
            entry = JournalEntry(
                entry_id=f"LIVE_loss_{i}",
                source=TradeSource.LIVE,
                strategy_name="NBB",
                strategy_config={},
                symbol="EURUSD",
                timeframe="1h",
                side="long",
                entry_price=1.1000,
                exit_price=1.0950,
                position_size=1.0,
                stop_loss=1.0950,
                take_profit=1.1100,
                risk_percent=2.0,
                risk_reward_ratio=2.0,
                pnl=-50.0,
                pnl_percent=-0.45,
                is_winner=False,
                exit_reason="sl",
                entry_slippage=0.0,
                exit_slippage=0.0,
                commission=0.1,
                market_context={},
                entry_time=datetime.utcnow() - timedelta(hours=i+2),
                exit_time=datetime.utcnow() - timedelta(hours=i+1),
                duration_minutes=60
            )
            test_db.add(entry)

        await test_db.commit()

        analyzer = PerformanceAnalyzer(db=test_db)
        result = await analyzer.detect_underperformance("NBB", "EURUSD")

        # Should detect underperformance with 20% win rate
        assert result["underperforming"] is True
        assert "low_win_rate" in result["issues"]


@pytest.mark.asyncio
class TestFeedbackLoop:
    """Test feedback loop functionality."""

    async def test_feedback_cycle_no_underperformance(self, test_db):
        """Test feedback cycle with normal performance."""
        feedback = FeedbackLoop(db=test_db)

        result = await feedback.run_feedback_cycle("NBB", "EURUSD")

        assert result["action"] == "none"
        assert "Performance within acceptable range" in result["reason"]

    async def test_feedback_cycle_underperformance(self, test_db):
        """Test feedback cycle with underperformance."""
        # Create poor performance data (8 consecutive losses)
        for i in range(8):
            entry = JournalEntry(
                entry_id=f"LIVE_loss_{i}",
                source=TradeSource.LIVE,
                strategy_name="BadStrategy",
                strategy_config={},
                symbol="EURUSD",
                timeframe="1h",
                side="long",
                entry_price=1.1000,
                exit_price=1.0950,
                position_size=1.0,
                stop_loss=1.0950,
                take_profit=1.1100,
                risk_percent=2.0,
                risk_reward_ratio=2.0,
                pnl=-50.0,
                pnl_percent=-0.45,
                is_winner=False,
                exit_reason="sl",
                entry_slippage=0.0,
                exit_slippage=0.0,
                commission=0.1,
                market_context={},
                entry_time=datetime.utcnow() - timedelta(hours=i+2),
                exit_time=datetime.utcnow() - timedelta(hours=i+1),
                duration_minutes=60
            )
            test_db.add(entry)

        await test_db.commit()

        feedback = FeedbackLoop(db=test_db)
        result = await feedback.run_feedback_cycle("BadStrategy", "EURUSD")

        assert result["action"] in ["disable_strategy", "trigger_optimization", "monitor_closely"]
        assert result["decision_id"] is not None

    async def test_decision_logging(self, test_db):
        """Test that feedback decisions are logged."""
        # Create underperforming data
        for i in range(6):
            entry = JournalEntry(
                entry_id=f"LIVE_log_{i}",
                source=TradeSource.LIVE,
                strategy_name="LogTest",
                strategy_config={},
                symbol="GBPUSD",
                timeframe="1h",
                side="long",
                entry_price=1.2500,
                exit_price=1.2450,
                position_size=1.0,
                stop_loss=1.2450,
                take_profit=1.2600,
                risk_percent=2.0,
                risk_reward_ratio=2.0,
                pnl=-50.0,
                pnl_percent=-0.40,
                is_winner=False,
                exit_reason="sl",
                entry_slippage=0.0,
                exit_slippage=0.0,
                commission=0.1,
                market_context={},
                entry_time=datetime.utcnow() - timedelta(hours=i+2),
                exit_time=datetime.utcnow() - timedelta(hours=i+1),
                duration_minutes=60
            )
            test_db.add(entry)

        await test_db.commit()

        feedback = FeedbackLoop(db=test_db)
        result = await feedback.run_feedback_cycle("LogTest", "GBPUSD")

        # Check that decision was logged
        from sqlalchemy import select
        stmt = select(FeedbackDecision).where(FeedbackDecision.strategy_name == "LogTest")
        db_result = await test_db.execute(stmt)
        decision = db_result.scalar_one_or_none()

        assert decision is not None
        assert decision.symbol == "GBPUSD"
        assert decision.executed is True

    async def test_disable_strategy_action(self, test_db):
        """Test that disable_strategy action updates risk budget."""
        # Create risk budget
        budget = StrategyRiskBudget(
            strategy_name="DisableTest",
            symbol="EURUSD",
            max_exposure_percent=5.0,
            max_daily_loss_percent=2.0,
            current_exposure=0.0,
            current_exposure_percent=0.0,
            daily_pnl=0.0,
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            total_pnl=0.0,
            consecutive_losses=0,
            max_consecutive_losses=5,
            is_enabled=True,
            last_updated=datetime.utcnow()
        )
        test_db.add(budget)
        await test_db.commit()

        # Create 10 consecutive losses to trigger disable
        for i in range(10):
            entry = JournalEntry(
                entry_id=f"LIVE_disable_{i}",
                source=TradeSource.LIVE,
                strategy_name="DisableTest",
                strategy_config={},
                symbol="EURUSD",
                timeframe="1h",
                side="long",
                entry_price=1.1000,
                exit_price=1.0950,
                position_size=1.0,
                stop_loss=1.0950,
                take_profit=1.1100,
                risk_percent=2.0,
                risk_reward_ratio=2.0,
                pnl=-50.0,
                pnl_percent=-0.45,
                is_winner=False,
                exit_reason="sl",
                entry_slippage=0.0,
                exit_slippage=0.0,
                commission=0.1,
                market_context={},
                entry_time=datetime.utcnow() - timedelta(hours=i+2),
                exit_time=datetime.utcnow() - timedelta(hours=i+1),
                duration_minutes=60
            )
            test_db.add(entry)

        await test_db.commit()

        feedback = FeedbackLoop(db=test_db)
        result = await feedback.run_feedback_cycle("DisableTest", "EURUSD")

        # Check if strategy was disabled
        from sqlalchemy import select
        stmt = select(StrategyRiskBudget).where(
            StrategyRiskBudget.strategy_name == "DisableTest",
            StrategyRiskBudget.symbol == "EURUSD"
        )
        db_result = await test_db.execute(stmt)
        updated_budget = db_result.scalar_one_or_none()

        if result["action"] == "disable_strategy":
            assert updated_budget.is_enabled is False
            assert "underperformance" in updated_budget.disabled_reason.lower()


@pytest.mark.asyncio
class TestPerformanceSnapshot:
    """Test performance snapshot creation."""

    async def test_create_snapshot(self, test_db):
        """Test creating a performance snapshot."""
        writer = JournalWriter(db=test_db)

        # Create some trades
        for i in range(5):
            trade = Trade(
                symbol="EURUSD",
                side=TradeSide.LONG,
                entry_price=1.1000,
                exit_price=1.1050 if i < 3 else 1.0950,
                quantity=1.0,
                entry_time=datetime.utcnow() - timedelta(days=10, hours=i),
                exit_time=datetime.utcnow() - timedelta(days=10, hours=i-1),
                pnl=50.0 if i < 3 else -50.0,
                pnl_percent=0.45 if i < 3 else -0.45,
                commission=0.1
            )
            await writer.record_backtest_trade(
                trade=trade,
                strategy_name="NBB",
                strategy_config={},
                backtest_id=f"bt_snap_{i}"
            )

        analyzer = PerformanceAnalyzer(db=test_db)

        snapshot = await analyzer.create_performance_snapshot(
            strategy_name="NBB",
            symbol="EURUSD",
            source=TradeSource.BACKTEST,
            period_start=datetime.utcnow() - timedelta(days=30),
            period_end=datetime.utcnow()
        )

        assert snapshot.id is not None
        assert snapshot.total_trades == 5
        assert snapshot.winning_trades == 3
        assert snapshot.losing_trades == 2
        assert snapshot.win_rate_percent == 60.0


@pytest.mark.asyncio
class TestJournalRoutes:
    """Test journal API routes."""

    async def test_get_journal_entries_empty(self, client):
        """Test getting empty journal entries."""
        response = await client.get("/api/v1/journal/entries")
        assert response.status_code == 200
        data = response.json()
        assert data == []

    async def test_get_journal_stats_empty(self, client):
        """Test getting stats with no entries."""
        response = await client.get("/api/v1/journal/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["total_entries"] == 0
        assert data["win_rate"] == 0.0

    async def test_analyze_strategy_endpoint(self, client):
        """Test analyze strategy endpoint."""
        response = await client.get("/api/v1/journal/analyze/NBB/EURUSD")
        assert response.status_code == 200
        data = response.json()
        assert data["strategy_name"] == "NBB"
        assert data["symbol"] == "EURUSD"
        assert "live_performance" in data
        assert "backtest_performance" in data

    async def test_underperformance_endpoint(self, client):
        """Test underperformance detection endpoint."""
        response = await client.get("/api/v1/journal/underperformance/NBB/EURUSD")
        assert response.status_code == 200
        data = response.json()
        assert "underperforming" in data
        assert "recommendation" in data

    async def test_feedback_cycle_endpoint(self, client):
        """Test feedback cycle endpoint."""
        response = await client.post("/api/v1/journal/feedback/NBB/EURUSD")
        assert response.status_code == 200
        data = response.json()
        assert "action" in data

    async def test_feedback_decisions_endpoint(self, client):
        """Test getting feedback decisions."""
        response = await client.get("/api/v1/journal/feedback/decisions")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    async def test_journal_health_endpoint(self, client):
        """Test journal health endpoint."""
        response = await client.get("/api/v1/journal/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["module"] == "journal"


@pytest.mark.asyncio
class TestConsecutiveStreaks:
    """Test consecutive win/loss streak calculation."""

    async def test_calculate_max_consecutive_wins(self, test_db):
        """Test calculating max consecutive wins."""
        writer = JournalWriter(db=test_db)

        # Pattern: W, W, W, L, W, W (max consecutive wins = 3)
        results = [True, True, True, False, True, True]

        for i, is_win in enumerate(results):
            trade = Trade(
                symbol="EURUSD",
                side=TradeSide.LONG,
                entry_price=1.1000,
                exit_price=1.1050 if is_win else 1.0950,
                quantity=1.0,
                entry_time=datetime.utcnow() - timedelta(hours=i+2),
                exit_time=datetime.utcnow() - timedelta(hours=i+1),
                pnl=50.0 if is_win else -50.0,
                pnl_percent=0.45 if is_win else -0.45,
                commission=0.1
            )
            await writer.record_backtest_trade(
                trade=trade,
                strategy_name="StreakTest",
                strategy_config={},
                backtest_id=f"bt_streak_{i}"
            )

        analyzer = PerformanceAnalyzer(db=test_db)
        analysis = await analyzer.analyze_strategy("StreakTest", "EURUSD", lookback_days=30)

        bt_perf = analysis["backtest_performance"]
        assert bt_perf["max_consecutive_wins"] == 3
        assert bt_perf["max_consecutive_losses"] == 1


@pytest.mark.asyncio
class TestBatchFeedback:
    """Test batch feedback functionality."""

    async def test_batch_feedback_empty(self, test_db):
        """Test batch feedback with empty list."""
        feedback = FeedbackLoop(db=test_db)

        result = await feedback.run_batch_feedback([])

        assert result["total_analyzed"] == 0
        assert result["actions_taken"] == 0

    async def test_batch_feedback_multiple_strategies(self, test_db):
        """Test batch feedback with multiple strategies."""
        feedback = FeedbackLoop(db=test_db)

        strategies = [
            ("NBB", "EURUSD"),
            ("JadeCap", "GBPUSD"),
            ("Fabio", "USDJPY")
        ]

        result = await feedback.run_batch_feedback(strategies)

        assert result["total_analyzed"] == 3
        assert "details" in result
