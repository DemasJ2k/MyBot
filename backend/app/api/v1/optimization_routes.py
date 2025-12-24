"""
API routes for optimization jobs and playbooks.

Prompt 06 - Optimization Engine.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
import logging

from app.database import get_db, AsyncSessionLocal
from app.models.optimization import (
    OptimizationJob,
    OptimizationResult,
    OptimizationMethod,
    OptimizationStatus,
    Playbook,
)
from app.optimization.engine import OptimizationEngine

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/optimization", tags=["optimization"])


# ============================================================================
# Pydantic Schemas
# ============================================================================


class OptimizationJobCreate(BaseModel):
    """Schema for creating an optimization job."""
    strategy_name: str = Field(..., description="Name of strategy to optimize")
    symbol: str = Field(..., description="Trading symbol (e.g., EURUSD)")
    interval: str = Field("1h", description="Candle interval")
    method: OptimizationMethod = Field(..., description="Optimization method")
    parameter_ranges: Dict[str, Any] = Field(
        ...,
        description="Parameter ranges to optimize",
        examples=[{
            "ema_fast": [10, 20, 30],
            "risk_percent": {"min": 1.0, "max": 3.0, "step": 0.5}
        }]
    )
    start_date: datetime = Field(..., description="Backtest start date")
    end_date: datetime = Field(..., description="Backtest end date")
    initial_balance: float = Field(10000.0, description="Initial balance for backtests")
    commission_percent: float = Field(0.1, description="Commission percentage")
    slippage_percent: float = Field(0.05, description="Slippage percentage")
    max_iterations: int = Field(100, ge=1, le=10000, description="Max iterations")
    objective_metric: str = Field("sharpe_ratio", description="Metric to optimize")
    minimize: bool = Field(False, description="If True, minimize metric; else maximize")


class OptimizationJobResponse(BaseModel):
    """Response schema for optimization job."""
    id: int
    strategy_name: str
    symbol: str
    interval: str
    method: str
    status: str
    progress_percent: float
    completed_iterations: int
    total_combinations: Optional[int]
    best_score: Optional[float]
    best_config: Optional[Dict[str, Any]]
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    error_message: Optional[str]

    class Config:
        from_attributes = True


class OptimizationResultResponse(BaseModel):
    """Response schema for optimization result."""
    iteration: int
    config: Dict[str, Any]
    score: float
    total_return_percent: float
    sharpe_ratio: Optional[float]
    max_drawdown_percent: float
    win_rate_percent: float
    profit_factor: Optional[float]
    total_trades: int


class OptimizationJobDetailResponse(BaseModel):
    """Detailed response with top results."""
    job: OptimizationJobResponse
    top_results: List[OptimizationResultResponse]


class PlaybookCreate(BaseModel):
    """Schema for creating a playbook."""
    name: str = Field(..., min_length=1, max_length=100, description="Playbook name")
    notes: Optional[str] = Field(None, description="Optional notes")


class PlaybookResponse(BaseModel):
    """Response schema for playbook."""
    id: int
    name: str
    strategy_name: str
    symbol: str
    config: Dict[str, Any]
    expected_return_percent: Optional[float]
    expected_sharpe_ratio: Optional[float]
    expected_max_drawdown_percent: Optional[float]
    optimization_job_id: Optional[int]
    is_active: bool
    notes: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class PlaybookUpdate(BaseModel):
    """Schema for updating a playbook."""
    is_active: Optional[bool] = None
    notes: Optional[str] = None


# ============================================================================
# Background Task
# ============================================================================


async def run_optimization_task(job_id: int):
    """
    Background task to run optimization.
    
    Creates its own database session for the background task.
    """
    async with AsyncSessionLocal() as db:
        try:
            engine = OptimizationEngine(db=db)
            await engine.run_optimization(job_id)
            logger.info(f"Optimization task {job_id} completed successfully")
        except Exception as e:
            logger.error(f"Optimization task {job_id} failed: {e}")


# ============================================================================
# Optimization Job Routes
# ============================================================================


@router.post("/jobs", response_model=OptimizationJobResponse, status_code=201)
async def create_optimization_job(
    request: OptimizationJobCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """
    Create and start an optimization job.

    The job runs in the background and can be polled for progress.
    """
    # Validate date range
    if request.start_date >= request.end_date:
        raise HTTPException(
            status_code=400,
            detail="start_date must be before end_date"
        )

    job = OptimizationJob(
        strategy_name=request.strategy_name,
        symbol=request.symbol,
        interval=request.interval,
        method=request.method,
        status=OptimizationStatus.PENDING,
        parameter_ranges=request.parameter_ranges,
        start_date=request.start_date,
        end_date=request.end_date,
        initial_balance=request.initial_balance,
        commission_percent=request.commission_percent,
        slippage_percent=request.slippage_percent,
        max_iterations=request.max_iterations,
        objective_metric=request.objective_metric,
        minimize=request.minimize
    )

    db.add(job)
    await db.commit()
    await db.refresh(job)

    # Run optimization in background
    background_tasks.add_task(run_optimization_task, job.id)

    logger.info(f"Created optimization job {job.id} for {job.strategy_name}")

    return job


@router.get("/jobs", response_model=List[OptimizationJobResponse])
async def list_optimization_jobs(
    strategy_name: Optional[str] = Query(None, description="Filter by strategy"),
    status: Optional[OptimizationStatus] = Query(None, description="Filter by status"),
    limit: int = Query(20, ge=1, le=100, description="Max results"),
    db: AsyncSession = Depends(get_db)
):
    """List optimization jobs with optional filters."""
    stmt = select(OptimizationJob)

    if strategy_name:
        stmt = stmt.where(OptimizationJob.strategy_name == strategy_name)
    if status:
        stmt = stmt.where(OptimizationJob.status == status)

    stmt = stmt.order_by(desc(OptimizationJob.created_at)).limit(limit)

    result = await db.execute(stmt)
    jobs = result.scalars().all()

    return jobs


@router.get("/jobs/{job_id}", response_model=OptimizationJobDetailResponse)
async def get_optimization_job(
    job_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get detailed optimization job information including top results."""
    stmt = select(OptimizationJob).where(OptimizationJob.id == job_id)
    result = await db.execute(stmt)
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Get top results
    stmt = select(OptimizationResult).where(
        OptimizationResult.job_id == job_id
    ).order_by(desc(OptimizationResult.score)).limit(10)

    result = await db.execute(stmt)
    top_results = result.scalars().all()

    return {
        "job": job,
        "top_results": [
            {
                "iteration": r.iteration,
                "config": r.config,
                "score": r.score,
                "total_return_percent": r.total_return_percent,
                "sharpe_ratio": r.sharpe_ratio,
                "max_drawdown_percent": r.max_drawdown_percent,
                "win_rate_percent": r.win_rate_percent,
                "profit_factor": r.profit_factor,
                "total_trades": r.total_trades,
            }
            for r in top_results
        ]
    }


@router.delete("/jobs/{job_id}")
async def delete_optimization_job(
    job_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Delete an optimization job and its results."""
    stmt = select(OptimizationJob).where(OptimizationJob.id == job_id)
    result = await db.execute(stmt)
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status == OptimizationStatus.RUNNING:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete running job. Cancel it first."
        )

    await db.delete(job)
    await db.commit()

    return {"message": f"Job {job_id} deleted"}


@router.post("/jobs/{job_id}/cancel")
async def cancel_optimization_job(
    job_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Cancel a running optimization job."""
    stmt = select(OptimizationJob).where(OptimizationJob.id == job_id)
    result = await db.execute(stmt)
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status not in [OptimizationStatus.PENDING, OptimizationStatus.RUNNING]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel job with status {job.status}"
        )

    job.status = OptimizationStatus.CANCELLED
    job.completed_at = datetime.utcnow()
    await db.commit()

    return {"message": f"Job {job_id} cancelled"}


# ============================================================================
# Playbook Routes
# ============================================================================


@router.post("/jobs/{job_id}/playbook", response_model=PlaybookResponse, status_code=201)
async def create_playbook_from_job(
    job_id: int,
    request: PlaybookCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a playbook from optimization results."""
    engine = OptimizationEngine(db=db)

    try:
        playbook = await engine.create_playbook_from_optimization(
            job_id=job_id,
            playbook_name=request.name,
            notes=request.notes
        )
        return playbook
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/playbooks", response_model=List[PlaybookResponse])
async def list_playbooks(
    strategy_name: Optional[str] = Query(None, description="Filter by strategy"),
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    limit: int = Query(50, ge=1, le=200, description="Max results"),
    db: AsyncSession = Depends(get_db)
):
    """List playbooks with optional filters."""
    stmt = select(Playbook)

    if strategy_name:
        stmt = stmt.where(Playbook.strategy_name == strategy_name)
    if symbol:
        stmt = stmt.where(Playbook.symbol == symbol)
    if is_active is not None:
        stmt = stmt.where(Playbook.is_active == is_active)

    stmt = stmt.order_by(desc(Playbook.created_at)).limit(limit)

    result = await db.execute(stmt)
    playbooks = result.scalars().all()

    return playbooks


@router.get("/playbooks/{playbook_id}", response_model=PlaybookResponse)
async def get_playbook(
    playbook_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get a playbook by ID."""
    stmt = select(Playbook).where(Playbook.id == playbook_id)
    result = await db.execute(stmt)
    playbook = result.scalar_one_or_none()

    if not playbook:
        raise HTTPException(status_code=404, detail="Playbook not found")

    return playbook


@router.patch("/playbooks/{playbook_id}", response_model=PlaybookResponse)
async def update_playbook(
    playbook_id: int,
    request: PlaybookUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update playbook status or notes."""
    stmt = select(Playbook).where(Playbook.id == playbook_id)
    result = await db.execute(stmt)
    playbook = result.scalar_one_or_none()

    if not playbook:
        raise HTTPException(status_code=404, detail="Playbook not found")

    if request.is_active is not None:
        playbook.is_active = request.is_active
    if request.notes is not None:
        playbook.notes = request.notes

    await db.commit()
    await db.refresh(playbook)

    return playbook


@router.delete("/playbooks/{playbook_id}")
async def delete_playbook(
    playbook_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Delete a playbook."""
    stmt = select(Playbook).where(Playbook.id == playbook_id)
    result = await db.execute(stmt)
    playbook = result.scalar_one_or_none()

    if not playbook:
        raise HTTPException(status_code=404, detail="Playbook not found")

    await db.delete(playbook)
    await db.commit()

    return {"message": f"Playbook {playbook_id} deleted"}


# ============================================================================
# Utility Routes
# ============================================================================


@router.get("/methods")
async def list_optimization_methods():
    """List available optimization methods."""
    return {
        "methods": [
            {
                "value": method.value,
                "description": {
                    OptimizationMethod.GRID_SEARCH: "Exhaustive search over all parameter combinations",
                    OptimizationMethod.RANDOM_SEARCH: "Monte Carlo random sampling of parameter space",
                    OptimizationMethod.AI_DRIVEN: "AI-guided exploration with mutation of best configs",
                    OptimizationMethod.GENETIC: "Genetic algorithm optimization (coming soon)",
                }.get(method, "")
            }
            for method in OptimizationMethod
        ]
    }


@router.get("/metrics")
async def list_optimization_metrics():
    """List available optimization metrics."""
    return {
        "metrics": [
            {"name": "sharpe_ratio", "description": "Risk-adjusted return (Sharpe ratio)", "minimize": False},
            {"name": "sortino_ratio", "description": "Downside risk-adjusted return", "minimize": False},
            {"name": "total_return", "description": "Total return percentage", "minimize": False},
            {"name": "max_drawdown", "description": "Maximum drawdown", "minimize": True},
            {"name": "win_rate", "description": "Percentage of winning trades", "minimize": False},
            {"name": "profit_factor", "description": "Gross profit / gross loss", "minimize": False},
            {"name": "expectancy", "description": "Expected value per trade", "minimize": False},
            {"name": "total_trades", "description": "Number of trades", "minimize": False},
            {"name": "recovery_factor", "description": "Net profit / max drawdown", "minimize": False},
        ]
    }
