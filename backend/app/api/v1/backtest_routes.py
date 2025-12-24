"""
API routes for backtesting.

Prompt 05 - Backtest Engine.
"""

from datetime import datetime
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.user import User
from app.models.market_data import Candle
from app.models.backtest import BacktestResult as BacktestResultModel
from app.backtest.engine import BacktestEngine, BacktestConfig
from app.backtest.performance import PerformanceMetrics
from app.strategies.strategy_manager import StrategyManager

router = APIRouter(prefix="/backtest", tags=["backtest"])


# ============================================================================
# Pydantic Schemas
# ============================================================================

class BacktestRequest(BaseModel):
    """Request schema for running a backtest."""
    strategy_name: str = Field(..., description="Name of the strategy to use")
    strategy_params: dict = Field(default_factory=dict, description="Strategy parameters")
    symbol: str = Field(..., description="Trading symbol (e.g., EUR/USD)")
    timeframe: str = Field(..., description="Candle timeframe (e.g., 1h, 4h, 1day)")
    start_date: datetime = Field(..., description="Backtest start date")
    end_date: datetime = Field(..., description="Backtest end date")
    initial_capital: float = Field(default=10000.0, gt=0, description="Starting capital")
    commission_rate: float = Field(default=0.001, ge=0, le=0.1, description="Commission rate (0.001 = 0.1%)")
    position_size_pct: float = Field(default=0.02, gt=0, le=1.0, description="Position size as % of equity")
    
    @field_validator("strategy_name")
    @classmethod
    def validate_strategy_name(cls, v: str) -> str:
        """Validate that the strategy exists."""
        valid_strategies = StrategyManager.get_available_strategies()
        if v not in valid_strategies:
            raise ValueError(f"Unknown strategy: {v}. Available: {list(valid_strategies.keys())}")
        return v
    
    @field_validator("timeframe")
    @classmethod
    def validate_timeframe(cls, v: str) -> str:
        """Validate timeframe format."""
        valid_timeframes = ["1min", "5min", "15min", "30min", "1h", "4h", "1day", "1week"]
        if v not in valid_timeframes:
            raise ValueError(f"Invalid timeframe: {v}. Valid: {valid_timeframes}")
        return v


class MetricsResponse(BaseModel):
    """Performance metrics in API response."""
    total_return: float
    total_pnl: float
    sharpe_ratio: Optional[float]
    sortino_ratio: Optional[float]
    max_drawdown: float
    avg_drawdown: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    profit_factor: Optional[float]
    expectancy: float
    avg_win: float
    avg_loss: float
    largest_win: float
    largest_loss: float
    avg_trade_duration_hours: float
    recovery_factor: Optional[float]


class EquityPointResponse(BaseModel):
    """Single equity curve point."""
    timestamp: str
    equity: float
    drawdown: float


class TradeLogResponse(BaseModel):
    """Single trade record."""
    symbol: str
    side: str
    entry_price: float
    exit_price: float
    quantity: float
    entry_time: str
    exit_time: str
    pnl: float
    pnl_percent: float
    commission: float


class BacktestResponse(BaseModel):
    """Response schema for backtest results."""
    id: str
    strategy_name: str
    symbol: str
    timeframe: str
    start_date: str
    end_date: str
    initial_capital: float
    metrics: MetricsResponse
    equity_curve: list[EquityPointResponse]
    trade_log: list[TradeLogResponse]
    created_at: str


class BacktestSummary(BaseModel):
    """Summary of a backtest result for listing."""
    id: str
    strategy_name: str
    symbol: str
    timeframe: str
    start_date: str
    end_date: str
    initial_capital: float
    total_return: float
    max_drawdown: float
    total_trades: int
    win_rate: float
    sharpe_ratio: Optional[float]
    created_at: str


class BacktestListResponse(BaseModel):
    """Response for listing backtest results."""
    results: list[BacktestSummary]
    total: int
    page: int
    page_size: int


# ============================================================================
# API Endpoints
# ============================================================================

@router.post("/run", response_model=BacktestResponse, status_code=status.HTTP_201_CREATED)
async def run_backtest(
    request: BacktestRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> BacktestResponse:
    """
    Run a backtest on historical data.
    
    This endpoint:
    1. Validates the request parameters
    2. Fetches historical candle data from the database
    3. Runs the backtest simulation
    4. Saves the results to the database
    5. Returns comprehensive performance metrics
    
    **Required permissions:** Authenticated user
    
    **Rate limit:** 10 requests per minute (backtests are compute-intensive)
    """
    # Get strategy class
    strategies = StrategyManager.get_available_strategies()
    strategy_class = strategies.get(request.strategy_name)
    
    if not strategy_class:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Strategy not found: {request.strategy_name}"
        )
    
    # Fetch historical candles from database
    stmt = (
        select(Candle)
        .where(Candle.symbol == request.symbol)
        .where(Candle.timeframe == request.timeframe)
        .where(Candle.timestamp >= request.start_date)
        .where(Candle.timestamp <= request.end_date)
        .order_by(Candle.timestamp.asc())
    )
    
    result = await session.execute(stmt)
    candles = list(result.scalars().all())
    
    if not candles:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No candle data found for {request.symbol} ({request.timeframe}) "
                   f"between {request.start_date} and {request.end_date}"
        )
    
    # Create backtest config
    try:
        config = BacktestConfig(
            strategy_class=strategy_class,
            strategy_params=request.strategy_params,
            symbol=request.symbol,
            timeframe=request.timeframe,
            start_date=request.start_date,
            end_date=request.end_date,
            initial_capital=request.initial_capital,
            commission_rate=request.commission_rate,
            position_size_pct=request.position_size_pct,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    
    # Run backtest
    try:
        engine = BacktestEngine(config)
        backtest_result = engine.run(candles)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Backtest failed: {str(e)}"
        )
    
    # Save results to database
    metrics = backtest_result.metrics
    portfolio = backtest_result.portfolio
    
    db_result = BacktestResultModel(
        id=str(uuid4()),
        user_id=current_user.id,
        strategy_name=request.strategy_name,
        symbol=request.symbol,
        timeframe=request.timeframe,
        start_date=request.start_date,
        end_date=request.end_date,
        initial_capital=request.initial_capital,
        total_return=metrics.total_return,
        sharpe_ratio=metrics.sharpe_ratio,
        sortino_ratio=metrics.sortino_ratio,
        max_drawdown=metrics.max_drawdown,
        win_rate=metrics.win_rate,
        profit_factor=metrics.profit_factor,
        total_trades=metrics.total_trades,
        winning_trades=metrics.winning_trades,
        losing_trades=metrics.losing_trades,
        equity_curve=portfolio.get_equity_curve_dict(),
        trade_log=portfolio.get_trade_log_dict(),
        strategy_params=request.strategy_params,
    )
    
    session.add(db_result)
    await session.commit()
    await session.refresh(db_result)
    
    # Build response
    return BacktestResponse(
        id=db_result.id,
        strategy_name=db_result.strategy_name,
        symbol=db_result.symbol,
        timeframe=db_result.timeframe,
        start_date=db_result.start_date.isoformat(),
        end_date=db_result.end_date.isoformat(),
        initial_capital=db_result.initial_capital,
        metrics=MetricsResponse(**metrics.to_dict()),
        equity_curve=[EquityPointResponse(**ep) for ep in db_result.equity_curve],
        trade_log=[TradeLogResponse(**t) for t in db_result.trade_log],
        created_at=db_result.created_at.isoformat(),
    )


@router.get("/results", response_model=BacktestListResponse)
async def list_backtest_results(
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Results per page"),
    strategy_name: Optional[str] = Query(default=None, description="Filter by strategy"),
    symbol: Optional[str] = Query(default=None, description="Filter by symbol"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> BacktestListResponse:
    """
    List backtest results for the current user.
    
    Supports pagination and filtering by strategy name and symbol.
    Results are sorted by creation date (newest first).
    
    **Required permissions:** Authenticated user
    """
    # Build query
    stmt = select(BacktestResultModel).where(
        BacktestResultModel.user_id == current_user.id
    )
    
    # Apply filters
    if strategy_name:
        stmt = stmt.where(BacktestResultModel.strategy_name == strategy_name)
    if symbol:
        stmt = stmt.where(BacktestResultModel.symbol == symbol)
    
    # Get total count
    count_stmt = select(BacktestResultModel).where(
        BacktestResultModel.user_id == current_user.id
    )
    if strategy_name:
        count_stmt = count_stmt.where(BacktestResultModel.strategy_name == strategy_name)
    if symbol:
        count_stmt = count_stmt.where(BacktestResultModel.symbol == symbol)
    
    count_result = await session.execute(count_stmt)
    total = len(list(count_result.scalars().all()))
    
    # Apply pagination and ordering
    stmt = stmt.order_by(BacktestResultModel.created_at.desc())
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    
    result = await session.execute(stmt)
    results = list(result.scalars().all())
    
    summaries = [
        BacktestSummary(
            id=r.id,
            strategy_name=r.strategy_name,
            symbol=r.symbol,
            timeframe=r.timeframe,
            start_date=r.start_date.isoformat(),
            end_date=r.end_date.isoformat(),
            initial_capital=r.initial_capital,
            total_return=r.total_return,
            max_drawdown=r.max_drawdown,
            total_trades=r.total_trades,
            win_rate=r.win_rate,
            sharpe_ratio=r.sharpe_ratio,
            created_at=r.created_at.isoformat(),
        )
        for r in results
    ]
    
    return BacktestListResponse(
        results=summaries,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/results/{result_id}", response_model=BacktestResponse)
async def get_backtest_result(
    result_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> BacktestResponse:
    """
    Get detailed backtest result by ID.
    
    Returns the full backtest result including equity curve and trade log.
    
    **Required permissions:** Authenticated user (can only access own results)
    """
    stmt = select(BacktestResultModel).where(
        BacktestResultModel.id == result_id,
        BacktestResultModel.user_id == current_user.id,
    )
    
    result = await session.execute(stmt)
    db_result = result.scalar_one_or_none()
    
    if not db_result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Backtest result not found: {result_id}"
        )
    
    # Reconstruct metrics from stored values
    metrics = MetricsResponse(
        total_return=db_result.total_return,
        total_pnl=db_result.initial_capital * db_result.total_return,
        sharpe_ratio=db_result.sharpe_ratio,
        sortino_ratio=db_result.sortino_ratio,
        max_drawdown=db_result.max_drawdown,
        avg_drawdown=0.0,  # Not stored, compute from equity_curve if needed
        total_trades=db_result.total_trades,
        winning_trades=db_result.winning_trades,
        losing_trades=db_result.losing_trades,
        win_rate=db_result.win_rate,
        profit_factor=db_result.profit_factor,
        expectancy=0.0,  # Recompute if needed
        avg_win=0.0,
        avg_loss=0.0,
        largest_win=0.0,
        largest_loss=0.0,
        avg_trade_duration_hours=0.0,
        recovery_factor=None,
    )
    
    return BacktestResponse(
        id=db_result.id,
        strategy_name=db_result.strategy_name,
        symbol=db_result.symbol,
        timeframe=db_result.timeframe,
        start_date=db_result.start_date.isoformat(),
        end_date=db_result.end_date.isoformat(),
        initial_capital=db_result.initial_capital,
        metrics=metrics,
        equity_curve=[EquityPointResponse(**ep) for ep in db_result.equity_curve],
        trade_log=[TradeLogResponse(**t) for t in db_result.trade_log],
        created_at=db_result.created_at.isoformat(),
    )


@router.delete("/results/{result_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_backtest_result(
    result_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Delete a backtest result.
    
    **Required permissions:** Authenticated user (can only delete own results)
    """
    stmt = select(BacktestResultModel).where(
        BacktestResultModel.id == result_id,
        BacktestResultModel.user_id == current_user.id,
    )
    
    result = await session.execute(stmt)
    db_result = result.scalar_one_or_none()
    
    if not db_result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Backtest result not found: {result_id}"
        )
    
    await session.delete(db_result)
    await session.commit()


@router.get("/strategies", response_model=list[str])
async def list_available_strategies(
    current_user: User = Depends(get_current_user),
) -> list[str]:
    """
    List available strategies for backtesting.
    
    Returns a list of strategy names that can be used in the /run endpoint.
    
    **Required permissions:** Authenticated user
    """
    strategies = StrategyManager.get_available_strategies()
    return list(strategies.keys())
