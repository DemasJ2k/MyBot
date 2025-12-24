"""
Journal API routes.

Prompt 11 - Journaling and Feedback Loop.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
from app.database import get_db
from app.journal.analyzer import PerformanceAnalyzer
from app.journal.feedback_loop import FeedbackLoop
from app.models.journal import JournalEntry, FeedbackDecision, PerformanceSnapshot, TradeSource
from sqlalchemy import select, desc, and_
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/journal", tags=["journal"])


class JournalEntryResponse(BaseModel):
    """Response model for journal entry."""
    id: int
    entry_id: str
    source: str
    strategy_name: str
    symbol: str
    timeframe: str
    side: str
    entry_price: float
    exit_price: float
    position_size: float
    stop_loss: float
    take_profit: float
    risk_percent: float
    risk_reward_ratio: float
    pnl: float
    pnl_percent: float
    is_winner: bool
    exit_reason: str
    entry_slippage: float
    exit_slippage: float
    commission: float
    entry_time: datetime
    exit_time: datetime
    duration_minutes: int
    backtest_id: Optional[str] = None
    execution_order_id: Optional[int] = None
    signal_id: Optional[int] = None
    notes: Optional[str] = None

    class Config:
        from_attributes = True


class JournalEntryDetailResponse(BaseModel):
    """Detailed response model for journal entry."""
    entry: JournalEntryResponse
    strategy_config: dict
    market_context: dict


class PerformanceMetricsResponse(BaseModel):
    """Response model for performance metrics."""
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_pnl: float
    avg_pnl: float
    gross_profit: float
    gross_loss: float
    profit_factor: float
    avg_win: float
    avg_loss: float
    max_consecutive_wins: int
    max_consecutive_losses: int
    avg_duration_minutes: int


class AnalysisResponse(BaseModel):
    """Response model for strategy analysis."""
    strategy_name: str
    symbol: str
    lookback_days: int
    live_performance: PerformanceMetricsResponse
    backtest_performance: PerformanceMetricsResponse
    paper_performance: PerformanceMetricsResponse
    deviation: dict
    analysis_time: str


class UnderperformanceResponse(BaseModel):
    """Response model for underperformance detection."""
    underperforming: bool
    issues: List[str]
    recommendation: str
    consecutive_losses: int
    live_metrics: PerformanceMetricsResponse
    deviation: dict


class FeedbackCycleResponse(BaseModel):
    """Response model for feedback cycle result."""
    action: str
    decision_id: Optional[int] = None
    execution_result: Optional[str] = None
    reason: Optional[str] = None
    underperformance: Optional[dict] = None


class FeedbackDecisionResponse(BaseModel):
    """Response model for feedback decision."""
    id: int
    decision_type: str
    strategy_name: str
    symbol: str
    analysis: dict
    action_taken: str
    action_params: Optional[dict] = None
    executed: bool
    execution_result: Optional[str] = None
    decision_time: str
    executed_at: Optional[str] = None


class BatchFeedbackRequest(BaseModel):
    """Request model for batch feedback."""
    strategies: List[tuple[str, str]]  # List of (strategy_name, symbol) tuples


@router.get("/entries", response_model=List[JournalEntryResponse])
async def get_journal_entries(
    strategy_name: Optional[str] = None,
    symbol: Optional[str] = None,
    source: Optional[str] = None,
    is_winner: Optional[bool] = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    """Get journal entries with optional filters."""
    stmt = select(JournalEntry)

    filters = []
    if strategy_name:
        filters.append(JournalEntry.strategy_name == strategy_name)
    if symbol:
        filters.append(JournalEntry.symbol == symbol)
    if source:
        filters.append(JournalEntry.source == source)
    if is_winner is not None:
        filters.append(JournalEntry.is_winner == is_winner)

    if filters:
        stmt = stmt.where(and_(*filters))

    stmt = stmt.order_by(desc(JournalEntry.exit_time)).offset(offset).limit(limit)

    result = await db.execute(stmt)
    entries = result.scalars().all()

    return [
        JournalEntryResponse(
            id=e.id,
            entry_id=e.entry_id,
            source=e.source.value if hasattr(e.source, 'value') else str(e.source),
            strategy_name=e.strategy_name,
            symbol=e.symbol,
            timeframe=e.timeframe,
            side=e.side,
            entry_price=e.entry_price,
            exit_price=e.exit_price,
            position_size=e.position_size,
            stop_loss=e.stop_loss,
            take_profit=e.take_profit,
            risk_percent=e.risk_percent,
            risk_reward_ratio=e.risk_reward_ratio,
            pnl=e.pnl,
            pnl_percent=e.pnl_percent,
            is_winner=e.is_winner,
            exit_reason=e.exit_reason,
            entry_slippage=e.entry_slippage,
            exit_slippage=e.exit_slippage,
            commission=e.commission,
            entry_time=e.entry_time,
            exit_time=e.exit_time,
            duration_minutes=e.duration_minutes,
            backtest_id=e.backtest_id,
            execution_order_id=e.execution_order_id,
            signal_id=e.signal_id,
            notes=e.notes
        )
        for e in entries
    ]


@router.get("/entries/{entry_id}", response_model=JournalEntryDetailResponse)
async def get_journal_entry(entry_id: str, db: AsyncSession = Depends(get_db)):
    """Get detailed journal entry."""
    stmt = select(JournalEntry).where(JournalEntry.entry_id == entry_id)
    result = await db.execute(stmt)
    entry = result.scalar_one_or_none()

    if not entry:
        raise HTTPException(status_code=404, detail="Journal entry not found")

    return JournalEntryDetailResponse(
        entry=JournalEntryResponse(
            id=entry.id,
            entry_id=entry.entry_id,
            source=entry.source.value if hasattr(entry.source, 'value') else str(entry.source),
            strategy_name=entry.strategy_name,
            symbol=entry.symbol,
            timeframe=entry.timeframe,
            side=entry.side,
            entry_price=entry.entry_price,
            exit_price=entry.exit_price,
            position_size=entry.position_size,
            stop_loss=entry.stop_loss,
            take_profit=entry.take_profit,
            risk_percent=entry.risk_percent,
            risk_reward_ratio=entry.risk_reward_ratio,
            pnl=entry.pnl,
            pnl_percent=entry.pnl_percent,
            is_winner=entry.is_winner,
            exit_reason=entry.exit_reason,
            entry_slippage=entry.entry_slippage,
            exit_slippage=entry.exit_slippage,
            commission=entry.commission,
            entry_time=entry.entry_time,
            exit_time=entry.exit_time,
            duration_minutes=entry.duration_minutes,
            backtest_id=entry.backtest_id,
            execution_order_id=entry.execution_order_id,
            signal_id=entry.signal_id,
            notes=entry.notes
        ),
        strategy_config=entry.strategy_config,
        market_context=entry.market_context
    )


@router.get("/stats")
async def get_journal_stats(
    strategy_name: Optional[str] = None,
    symbol: Optional[str] = None,
    source: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Get aggregated journal statistics."""
    stmt = select(JournalEntry)

    filters = []
    if strategy_name:
        filters.append(JournalEntry.strategy_name == strategy_name)
    if symbol:
        filters.append(JournalEntry.symbol == symbol)
    if source:
        filters.append(JournalEntry.source == source)

    if filters:
        stmt = stmt.where(and_(*filters))

    result = await db.execute(stmt)
    entries = result.scalars().all()

    if not entries:
        return {
            "total_entries": 0,
            "total_trades": 0,
            "winners": 0,
            "losers": 0,
            "win_rate": 0.0,
            "total_pnl": 0.0,
            "avg_pnl": 0.0,
            "strategies": [],
            "symbols": [],
            "sources": []
        }

    total = len(entries)
    winners = sum(1 for e in entries if e.is_winner)
    losers = total - winners
    total_pnl = sum(e.pnl for e in entries)
    
    strategies = list(set(e.strategy_name for e in entries))
    symbols = list(set(e.symbol for e in entries))
    sources = list(set(e.source.value if hasattr(e.source, 'value') else str(e.source) for e in entries))

    return {
        "total_entries": total,
        "total_trades": total,
        "winners": winners,
        "losers": losers,
        "win_rate": (winners / total * 100.0) if total > 0 else 0.0,
        "total_pnl": total_pnl,
        "avg_pnl": total_pnl / total if total > 0 else 0.0,
        "strategies": strategies,
        "symbols": symbols,
        "sources": sources
    }


@router.get("/analyze/{strategy_name}/{symbol}")
async def analyze_strategy(
    strategy_name: str,
    symbol: str,
    lookback_days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db)
):
    """Analyze strategy performance from journal."""
    analyzer = PerformanceAnalyzer(db=db)

    analysis = await analyzer.analyze_strategy(
        strategy_name=strategy_name,
        symbol=symbol,
        lookback_days=lookback_days
    )

    return analysis


@router.get("/underperformance/{strategy_name}/{symbol}")
async def detect_underperformance(
    strategy_name: str,
    symbol: str,
    db: AsyncSession = Depends(get_db)
):
    """Detect if strategy is underperforming."""
    analyzer = PerformanceAnalyzer(db=db)

    result = await analyzer.detect_underperformance(
        strategy_name=strategy_name,
        symbol=symbol
    )

    return result


@router.post("/feedback/{strategy_name}/{symbol}")
async def run_feedback_cycle(
    strategy_name: str,
    symbol: str,
    db: AsyncSession = Depends(get_db)
):
    """Run AI feedback cycle for strategy."""
    feedback_loop = FeedbackLoop(db=db)

    result = await feedback_loop.run_feedback_cycle(
        strategy_name=strategy_name,
        symbol=symbol
    )

    return result


@router.post("/feedback/batch")
async def run_batch_feedback(
    request: BatchFeedbackRequest,
    db: AsyncSession = Depends(get_db)
):
    """Run AI feedback cycle for multiple strategies."""
    feedback_loop = FeedbackLoop(db=db)

    result = await feedback_loop.run_batch_feedback(
        strategies=request.strategies
    )

    return result


@router.get("/feedback/decisions", response_model=List[FeedbackDecisionResponse])
async def get_feedback_decisions(
    strategy_name: Optional[str] = None,
    symbol: Optional[str] = None,
    decision_type: Optional[str] = None,
    executed: Optional[bool] = None,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db)
):
    """Get feedback decision log."""
    stmt = select(FeedbackDecision)

    filters = []
    if strategy_name:
        filters.append(FeedbackDecision.strategy_name == strategy_name)
    if symbol:
        filters.append(FeedbackDecision.symbol == symbol)
    if decision_type:
        filters.append(FeedbackDecision.decision_type == decision_type)
    if executed is not None:
        filters.append(FeedbackDecision.executed == executed)

    if filters:
        stmt = stmt.where(and_(*filters))

    stmt = stmt.order_by(desc(FeedbackDecision.decision_time)).limit(limit)

    result = await db.execute(stmt)
    decisions = result.scalars().all()

    return [
        FeedbackDecisionResponse(
            id=d.id,
            decision_type=d.decision_type,
            strategy_name=d.strategy_name,
            symbol=d.symbol,
            analysis=d.analysis,
            action_taken=d.action_taken,
            action_params=d.action_params,
            executed=d.executed,
            execution_result=d.execution_result,
            decision_time=d.decision_time.isoformat() if d.decision_time else None,
            executed_at=d.executed_at.isoformat() if d.executed_at else None
        )
        for d in decisions
    ]


@router.get("/snapshots")
async def get_performance_snapshots(
    strategy_name: Optional[str] = None,
    symbol: Optional[str] = None,
    source: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db)
):
    """Get performance snapshots."""
    stmt = select(PerformanceSnapshot)

    filters = []
    if strategy_name:
        filters.append(PerformanceSnapshot.strategy_name == strategy_name)
    if symbol:
        filters.append(PerformanceSnapshot.symbol == symbol)
    if source:
        filters.append(PerformanceSnapshot.source == source)

    if filters:
        stmt = stmt.where(and_(*filters))

    stmt = stmt.order_by(desc(PerformanceSnapshot.snapshot_time)).limit(limit)

    result = await db.execute(stmt)
    snapshots = result.scalars().all()

    return [
        {
            "id": s.id,
            "strategy_name": s.strategy_name,
            "symbol": s.symbol,
            "source": s.source.value if hasattr(s.source, 'value') else str(s.source),
            "period_start": s.period_start.isoformat(),
            "period_end": s.period_end.isoformat(),
            "total_trades": s.total_trades,
            "winning_trades": s.winning_trades,
            "losing_trades": s.losing_trades,
            "win_rate_percent": s.win_rate_percent,
            "total_pnl": s.total_pnl,
            "avg_win": s.avg_win,
            "avg_loss": s.avg_loss,
            "profit_factor": s.profit_factor,
            "max_consecutive_wins": s.max_consecutive_wins,
            "max_consecutive_losses": s.max_consecutive_losses,
            "avg_duration_minutes": s.avg_duration_minutes,
            "snapshot_time": s.snapshot_time.isoformat()
        }
        for s in snapshots
    ]


@router.post("/snapshots/{strategy_name}/{symbol}")
async def create_performance_snapshot(
    strategy_name: str,
    symbol: str,
    source: str = Query("live", description="Trade source: live, backtest, paper"),
    lookback_days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db)
):
    """Create a performance snapshot for the specified period."""
    analyzer = PerformanceAnalyzer(db=db)

    from datetime import timedelta
    period_end = datetime.utcnow()
    period_start = period_end - timedelta(days=lookback_days)

    # Map source string to enum
    source_map = {
        "live": TradeSource.LIVE,
        "backtest": TradeSource.BACKTEST,
        "paper": TradeSource.PAPER
    }
    trade_source = source_map.get(source.lower(), TradeSource.LIVE)

    snapshot = await analyzer.create_performance_snapshot(
        strategy_name=strategy_name,
        symbol=symbol,
        source=trade_source,
        period_start=period_start,
        period_end=period_end
    )

    return {
        "id": snapshot.id,
        "strategy_name": snapshot.strategy_name,
        "symbol": snapshot.symbol,
        "source": snapshot.source.value if hasattr(snapshot.source, 'value') else str(snapshot.source),
        "period_start": snapshot.period_start.isoformat(),
        "period_end": snapshot.period_end.isoformat(),
        "total_trades": snapshot.total_trades,
        "win_rate_percent": snapshot.win_rate_percent,
        "total_pnl": snapshot.total_pnl,
        "profit_factor": snapshot.profit_factor,
        "snapshot_time": snapshot.snapshot_time.isoformat()
    }


@router.get("/health")
async def journal_health():
    """Health check for journal module."""
    return {
        "status": "healthy",
        "module": "journal",
        "features": [
            "journal_entries",
            "performance_analyzer",
            "feedback_loop",
            "performance_snapshots"
        ]
    }
