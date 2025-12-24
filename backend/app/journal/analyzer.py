"""
Performance Analyzer for journal entries.

Analyzes journal entries to detect patterns and performance deviations.
Prompt 11 - Journaling and Feedback Loop.
"""

from typing import Dict, Any, List
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from app.models.journal import JournalEntry, PerformanceSnapshot, TradeSource
import logging

logger = logging.getLogger(__name__)


class PerformanceAnalyzer:
    """Analyzes journal entries to detect patterns and performance deviations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def analyze_strategy(
        self,
        strategy_name: str,
        symbol: str,
        lookback_days: int = 30
    ) -> Dict[str, Any]:
        """
        Analyze strategy performance from journal.

        Compares live vs backtest performance.

        Args:
            strategy_name: Strategy name
            symbol: Symbol
            lookback_days: Days to look back

        Returns:
            Analysis dict with performance metrics and deviation
        """
        cutoff_date = datetime.utcnow() - timedelta(days=lookback_days)

        # Get live trades
        live_metrics = await self._calculate_metrics(
            strategy_name, symbol, TradeSource.LIVE, cutoff_date
        )

        # Get backtest trades
        backtest_metrics = await self._calculate_metrics(
            strategy_name, symbol, TradeSource.BACKTEST, cutoff_date
        )

        # Get paper trades for additional context
        paper_metrics = await self._calculate_metrics(
            strategy_name, symbol, TradeSource.PAPER, cutoff_date
        )

        # Calculate deviations
        deviation = self._calculate_deviation(live_metrics, backtest_metrics)

        analysis = {
            "strategy_name": strategy_name,
            "symbol": symbol,
            "lookback_days": lookback_days,
            "live_performance": live_metrics,
            "backtest_performance": backtest_metrics,
            "paper_performance": paper_metrics,
            "deviation": deviation,
            "analysis_time": datetime.utcnow().isoformat()
        }

        logger.info(
            f"Analyzed {strategy_name} on {symbol}: "
            f"Live WR={live_metrics.get('win_rate', 0):.1f}% vs "
            f"BT WR={backtest_metrics.get('win_rate', 0):.1f}%"
        )

        return analysis

    async def _calculate_metrics(
        self,
        strategy_name: str,
        symbol: str,
        source: TradeSource,
        cutoff_date: datetime
    ) -> Dict[str, Any]:
        """Calculate performance metrics from journal entries."""
        stmt = select(JournalEntry).where(
            and_(
                JournalEntry.strategy_name == strategy_name,
                JournalEntry.symbol == symbol,
                JournalEntry.source == source,
                JournalEntry.entry_time >= cutoff_date
            )
        )

        result = await self.db.execute(stmt)
        entries = result.scalars().all()

        if not entries:
            return {
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "win_rate": 0.0,
                "total_pnl": 0.0,
                "avg_pnl": 0.0,
                "gross_profit": 0.0,
                "gross_loss": 0.0,
                "profit_factor": 0.0,
                "avg_win": 0.0,
                "avg_loss": 0.0,
                "max_consecutive_wins": 0,
                "max_consecutive_losses": 0,
                "avg_duration_minutes": 0
            }

        total_trades = len(entries)
        winning_trades = sum(1 for e in entries if e.is_winner)
        losing_trades = total_trades - winning_trades

        win_rate = (winning_trades / total_trades * 100.0) if total_trades > 0 else 0.0

        total_pnl = sum(e.pnl for e in entries)
        avg_pnl = total_pnl / total_trades if total_trades > 0 else 0.0

        gross_profit = sum(e.pnl for e in entries if e.is_winner)
        gross_loss = abs(sum(e.pnl for e in entries if not e.is_winner))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf") if gross_profit > 0 else 0.0

        avg_win = gross_profit / winning_trades if winning_trades > 0 else 0.0
        avg_loss = gross_loss / losing_trades if losing_trades > 0 else 0.0

        # Calculate consecutive wins/losses
        max_consecutive_wins, max_consecutive_losses = self._calculate_consecutive_streaks(entries)

        # Average trade duration
        total_duration = sum(e.duration_minutes for e in entries)
        avg_duration = total_duration // total_trades if total_trades > 0 else 0

        return {
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "win_rate": win_rate,
            "total_pnl": total_pnl,
            "avg_pnl": avg_pnl,
            "gross_profit": gross_profit,
            "gross_loss": gross_loss,
            "profit_factor": profit_factor,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "max_consecutive_wins": max_consecutive_wins,
            "max_consecutive_losses": max_consecutive_losses,
            "avg_duration_minutes": avg_duration
        }

    def _calculate_consecutive_streaks(self, entries: List[JournalEntry]) -> tuple[int, int]:
        """Calculate max consecutive wins and losses."""
        if not entries:
            return 0, 0

        # Sort by exit time
        sorted_entries = sorted(entries, key=lambda e: e.exit_time)

        max_wins = 0
        max_losses = 0
        current_wins = 0
        current_losses = 0

        for entry in sorted_entries:
            if entry.is_winner:
                current_wins += 1
                current_losses = 0
                max_wins = max(max_wins, current_wins)
            else:
                current_losses += 1
                current_wins = 0
                max_losses = max(max_losses, current_losses)

        return max_wins, max_losses

    def _calculate_deviation(
        self,
        live_metrics: Dict[str, Any],
        backtest_metrics: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate deviation between live and backtest performance."""
        if backtest_metrics["total_trades"] == 0:
            return {"status": "no_backtest_data"}

        if live_metrics["total_trades"] == 0:
            return {"status": "no_live_data"}

        win_rate_deviation = live_metrics["win_rate"] - backtest_metrics["win_rate"]
        
        # Handle infinite profit factors
        live_pf = live_metrics["profit_factor"] if live_metrics["profit_factor"] != float("inf") else 99.0
        bt_pf = backtest_metrics["profit_factor"] if backtest_metrics["profit_factor"] != float("inf") else 99.0
        profit_factor_deviation = live_pf - bt_pf

        pnl_deviation = live_metrics["avg_pnl"] - backtest_metrics["avg_pnl"]

        # Determine severity
        severity = "normal"
        if abs(win_rate_deviation) > 20.0:  # >20% deviation in win rate
            severity = "critical"
        elif abs(win_rate_deviation) > 10.0:
            severity = "warning"

        # Also check profit factor deviation
        if live_pf < 1.0 and bt_pf > 1.0:
            severity = "critical"

        return {
            "status": "analyzed",
            "win_rate_deviation_percent": win_rate_deviation,
            "profit_factor_deviation": profit_factor_deviation,
            "avg_pnl_deviation": pnl_deviation,
            "severity": severity
        }

    async def detect_underperformance(
        self,
        strategy_name: str,
        symbol: str
    ) -> Dict[str, Any]:
        """
        Detect if strategy is underperforming.

        Criteria:
        - Win rate < 40%
        - Profit factor < 1.0
        - 5+ consecutive losses
        - Live performance significantly worse than backtest

        Returns:
            Detection result with recommendations
        """
        analysis = await self.analyze_strategy(strategy_name, symbol, lookback_days=30)

        live_metrics = analysis["live_performance"]
        deviation = analysis["deviation"]

        issues = []

        # Check win rate (only if we have enough trades)
        if live_metrics["total_trades"] >= 5 and live_metrics["win_rate"] < 40.0:
            issues.append("low_win_rate")

        # Check profit factor (only if we have enough trades)
        if live_metrics["total_trades"] >= 5 and live_metrics["profit_factor"] < 1.0:
            issues.append("unprofitable")

        # Check deviation severity
        if deviation.get("severity") == "critical":
            issues.append("critical_deviation_from_backtest")

        # Check consecutive losses
        consecutive_losses = await self._count_consecutive_losses(strategy_name, symbol)
        if consecutive_losses >= 5:
            issues.append("excessive_consecutive_losses")

        if issues:
            recommendation = self._generate_recommendation(issues)

            return {
                "underperforming": True,
                "issues": issues,
                "recommendation": recommendation,
                "consecutive_losses": consecutive_losses,
                "live_metrics": live_metrics,
                "deviation": deviation
            }

        return {
            "underperforming": False,
            "issues": [],
            "recommendation": "continue",
            "consecutive_losses": consecutive_losses,
            "live_metrics": live_metrics,
            "deviation": deviation
        }

    async def _count_consecutive_losses(self, strategy_name: str, symbol: str) -> int:
        """Count current consecutive losses."""
        stmt = select(JournalEntry).where(
            and_(
                JournalEntry.strategy_name == strategy_name,
                JournalEntry.symbol == symbol,
                JournalEntry.source == TradeSource.LIVE
            )
        ).order_by(JournalEntry.exit_time.desc()).limit(20)

        result = await self.db.execute(stmt)
        entries = result.scalars().all()

        consecutive = 0
        for entry in entries:
            if not entry.is_winner:
                consecutive += 1
            else:
                break

        return consecutive

    def _generate_recommendation(self, issues: List[str]) -> str:
        """Generate recommendation based on issues."""
        if "critical_deviation_from_backtest" in issues:
            return "trigger_optimization"

        if "excessive_consecutive_losses" in issues:
            return "disable_strategy"

        if "unprofitable" in issues and "low_win_rate" in issues:
            return "disable_strategy"

        if "unprofitable" in issues:
            return "trigger_optimization"

        if "low_win_rate" in issues:
            return "monitor_closely"

        return "monitor_closely"

    async def create_performance_snapshot(
        self,
        strategy_name: str,
        symbol: str,
        source: TradeSource,
        period_start: datetime,
        period_end: datetime
    ) -> PerformanceSnapshot:
        """
        Create a performance snapshot for the specified period.

        Args:
            strategy_name: Strategy name
            symbol: Symbol
            source: Trade source
            period_start: Period start time
            period_end: Period end time

        Returns:
            Created performance snapshot
        """
        # Get entries in period
        stmt = select(JournalEntry).where(
            and_(
                JournalEntry.strategy_name == strategy_name,
                JournalEntry.symbol == symbol,
                JournalEntry.source == source,
                JournalEntry.entry_time >= period_start,
                JournalEntry.entry_time <= period_end
            )
        )

        result = await self.db.execute(stmt)
        entries = result.scalars().all()

        # Calculate metrics
        total_trades = len(entries)
        winning_trades = sum(1 for e in entries if e.is_winner)
        losing_trades = total_trades - winning_trades
        win_rate = (winning_trades / total_trades * 100.0) if total_trades > 0 else 0.0

        total_pnl = sum(e.pnl for e in entries)
        
        gross_profit = sum(e.pnl for e in entries if e.is_winner)
        gross_loss = abs(sum(e.pnl for e in entries if not e.is_winner))
        
        avg_win = gross_profit / winning_trades if winning_trades > 0 else 0.0
        avg_loss = gross_loss / losing_trades if losing_trades > 0 else 0.0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else None

        max_wins, max_losses = self._calculate_consecutive_streaks(entries)
        
        total_duration = sum(e.duration_minutes for e in entries)
        avg_duration = total_duration // total_trades if total_trades > 0 else 0

        snapshot = PerformanceSnapshot(
            strategy_name=strategy_name,
            symbol=symbol,
            source=source,
            period_start=period_start,
            period_end=period_end,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate_percent=win_rate,
            total_pnl=total_pnl,
            avg_win=avg_win,
            avg_loss=avg_loss,
            profit_factor=profit_factor,
            max_consecutive_wins=max_wins,
            max_consecutive_losses=max_losses,
            avg_duration_minutes=avg_duration,
            snapshot_time=datetime.utcnow()
        )

        self.db.add(snapshot)
        await self.db.commit()
        await self.db.refresh(snapshot)

        logger.info(
            f"Created performance snapshot for {strategy_name} on {symbol}: "
            f"WR={win_rate:.1f}%, P&L={total_pnl:.2f}"
        )

        return snapshot
