"""
Optimization engine for running parameter optimization jobs.

Orchestrates the optimization process: generates configurations,
runs backtests, tracks results, and identifies optimal parameters.
"""

from typing import Dict, Any, List, Optional, Type
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
import logging

from app.models.optimization import (
    OptimizationJob,
    OptimizationResult,
    OptimizationMethod,
    OptimizationStatus,
    Playbook,
)
from app.models.market_data import Candle
from app.backtest.engine import BacktestEngine, BacktestConfig
from app.backtest.performance import PerformanceMetrics
from app.strategies.base_strategy import BaseStrategy
from app.strategies.nbb_strategy import NBBStrategy
from app.strategies.jadecap_strategy import JadeCapStrategy
from app.strategies.fabio_strategy import FabioStrategy
from app.strategies.tori_strategy import ToriStrategy
from app.optimization.grid_optimizer import GridSearchOptimizer
from app.optimization.random_optimizer import RandomSearchOptimizer
from app.optimization.ai_optimizer import AIOptimizer

logger = logging.getLogger(__name__)

# Strategy class registry
STRATEGY_CLASSES: Dict[str, Type[BaseStrategy]] = {
    "NBB": NBBStrategy,
    "JadeCap": JadeCapStrategy,
    "Fabio": FabioStrategy,
    "Tori": ToriStrategy,
}


class OptimizationEngine:
    """
    Manages parameter optimization jobs.
    
    The engine:
    1. Loads optimization job configuration
    2. Selects appropriate optimizer (grid, random, AI)
    3. Generates parameter configurations to test
    4. Runs backtests for each configuration
    5. Tracks best results and updates progress
    6. Supports playbook generation from optimal configs
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize optimization engine.
        
        Args:
            db: Async database session
        """
        self.db = db

    async def run_optimization(self, job_id: int) -> OptimizationJob:
        """
        Execute an optimization job.

        Args:
            job_id: Optimization job ID

        Returns:
            Updated job with results

        Raises:
            ValueError: If job not found or not in PENDING status
        """
        # Load job
        stmt = select(OptimizationJob).where(OptimizationJob.id == job_id)
        result = await self.db.execute(stmt)
        job = result.scalar_one_or_none()

        if not job:
            raise ValueError(f"Optimization job {job_id} not found")

        if job.status != OptimizationStatus.PENDING:
            raise ValueError(f"Job {job_id} is not pending (status={job.status})")

        # Update status to running
        job.status = OptimizationStatus.RUNNING
        job.started_at = datetime.utcnow()
        await self.db.commit()

        try:
            # Select optimizer based on method
            optimizer = self._get_optimizer(job.method)

            # Generate configurations to test
            configs = await optimizer.optimize(job, self.db)

            if not configs:
                raise ValueError("No configurations generated")

            # Get historical candles for backtesting
            candles = await self._load_candles(job)

            if not candles:
                raise ValueError(f"No historical data for {job.symbol} {job.interval}")

            logger.info(f"Running optimization with {len(configs)} configs on {len(candles)} candles")

            # Get strategy class
            strategy_class = self._get_strategy_class(job.strategy_name)

            # Run backtests for each configuration
            for i, config in enumerate(configs):
                logger.debug(f"Testing config {i+1}/{len(configs)}: {config}")

                try:
                    # Run backtest with this config
                    metrics = self._run_single_backtest(
                        strategy_class=strategy_class,
                        strategy_params=config,
                        candles=candles,
                        job=job,
                    )

                    # Extract objective metric
                    score = self._extract_metric(metrics, job.objective_metric)

                    # Save result
                    opt_result = OptimizationResult(
                        job_id=job.id,
                        iteration=i + 1,
                        config=config,
                        score=score,
                        total_return_percent=metrics.total_return * 100,
                        sharpe_ratio=metrics.sharpe_ratio,
                        max_drawdown_percent=metrics.max_drawdown * 100,
                        win_rate_percent=metrics.win_rate * 100,
                        profit_factor=metrics.profit_factor,
                        total_trades=metrics.total_trades,
                        backtest_id=None,
                    )

                    self.db.add(opt_result)

                    # Update job progress
                    job.completed_iterations = i + 1
                    job.progress_percent = (i + 1) / len(configs) * 100.0

                    # Update best if this is better
                    if job.best_score is None:
                        job.best_score = score
                        job.best_config = config
                    else:
                        is_better = (
                            (not job.minimize and score > job.best_score) or
                            (job.minimize and score < job.best_score)
                        )
                        if is_better:
                            job.best_score = score
                            job.best_config = config
                            logger.info(f"New best score: {score:.4f} with config {config}")

                    await self.db.commit()

                except Exception as e:
                    logger.warning(f"Backtest failed for config {config}: {e}")
                    # Continue with next config
                    continue

            # Mark as completed
            job.status = OptimizationStatus.COMPLETED
            job.completed_at = datetime.utcnow()
            await self.db.commit()

            if job.best_score is not None:
                logger.info(f"Optimization job {job_id} completed. Best score: {job.best_score:.4f}")
            else:
                logger.warning(f"Optimization job {job_id} completed but no valid results")

            return job

        except Exception as e:
            logger.error(f"Optimization job {job_id} failed: {e}")
            job.status = OptimizationStatus.FAILED
            job.error_message = str(e)
            job.completed_at = datetime.utcnow()
            await self.db.commit()
            raise

    async def create_playbook_from_optimization(
        self,
        job_id: int,
        playbook_name: str,
        notes: Optional[str] = None
    ) -> Playbook:
        """
        Create a playbook from optimization results.

        Args:
            job_id: Optimization job ID
            playbook_name: Name for the playbook
            notes: Optional notes

        Returns:
            Created playbook

        Raises:
            ValueError: If job not found, not completed, or has no best config
        """
        # Load job
        stmt = select(OptimizationJob).where(OptimizationJob.id == job_id)
        result = await self.db.execute(stmt)
        job = result.scalar_one_or_none()

        if not job:
            raise ValueError(f"Optimization job {job_id} not found")

        if job.status != OptimizationStatus.COMPLETED:
            raise ValueError(f"Job {job_id} is not completed")

        if not job.best_config:
            raise ValueError(f"Job {job_id} has no best config")

        # Get best result for metrics
        stmt = select(OptimizationResult).where(
            OptimizationResult.job_id == job_id,
            OptimizationResult.score == job.best_score
        ).limit(1)

        result = await self.db.execute(stmt)
        best_result = result.scalar_one_or_none()

        # Create playbook
        playbook = Playbook(
            name=playbook_name,
            strategy_name=job.strategy_name,
            symbol=job.symbol,
            config=job.best_config,
            expected_return_percent=best_result.total_return_percent if best_result else None,
            expected_sharpe_ratio=best_result.sharpe_ratio if best_result else None,
            expected_max_drawdown_percent=best_result.max_drawdown_percent if best_result else None,
            optimization_job_id=job_id,
            is_active=True,
            notes=notes
        )

        self.db.add(playbook)
        await self.db.commit()
        await self.db.refresh(playbook)

        logger.info(f"Created playbook '{playbook_name}' from optimization job {job_id}")

        return playbook

    def _get_optimizer(self, method: OptimizationMethod):
        """
        Get optimizer instance by method.
        
        Args:
            method: Optimization method enum
            
        Returns:
            Optimizer instance
            
        Raises:
            ValueError: If method is unsupported
        """
        if method == OptimizationMethod.GRID_SEARCH:
            return GridSearchOptimizer()
        elif method == OptimizationMethod.RANDOM_SEARCH:
            return RandomSearchOptimizer()
        elif method == OptimizationMethod.AI_DRIVEN:
            return AIOptimizer()
        else:
            raise ValueError(f"Unsupported optimization method: {method}")

    def _get_strategy_class(self, strategy_name: str) -> Type[BaseStrategy]:
        """
        Get strategy class by name.
        
        Args:
            strategy_name: Strategy name
            
        Returns:
            Strategy class
            
        Raises:
            ValueError: If strategy not found
        """
        if strategy_name not in STRATEGY_CLASSES:
            raise ValueError(
                f"Unknown strategy '{strategy_name}'. "
                f"Available: {list(STRATEGY_CLASSES.keys())}"
            )
        return STRATEGY_CLASSES[strategy_name]

    async def _load_candles(self, job: OptimizationJob) -> List[Candle]:
        """
        Load historical candles for backtesting.
        
        Args:
            job: Optimization job with symbol/interval/date range
            
        Returns:
            List of candles sorted by timestamp
        """
        stmt = select(Candle).where(
            and_(
                Candle.symbol == job.symbol,
                Candle.interval == job.interval,
                Candle.timestamp >= job.start_date,
                Candle.timestamp <= job.end_date
            )
        ).order_by(Candle.timestamp.asc())

        result = await self.db.execute(stmt)
        candles = list(result.scalars().all())

        logger.info(f"Loaded {len(candles)} candles for {job.symbol} {job.interval}")

        return candles

    def _run_single_backtest(
        self,
        strategy_class: Type[BaseStrategy],
        strategy_params: Dict[str, Any],
        candles: List[Candle],
        job: OptimizationJob,
    ) -> PerformanceMetrics:
        """
        Run a single backtest with given configuration.
        
        Args:
            strategy_class: Strategy class to instantiate
            strategy_params: Parameters for strategy
            candles: Historical candle data
            job: Optimization job with backtest settings
            
        Returns:
            Performance metrics from backtest
        """
        # Create backtest config
        config = BacktestConfig(
            strategy_class=strategy_class,
            strategy_params=strategy_params,
            symbol=job.symbol,
            timeframe=job.interval,
            start_date=job.start_date,
            end_date=job.end_date,
            initial_capital=job.initial_balance,
            commission_rate=job.commission_percent / 100.0,
            position_size_pct=0.02,  # Default 2% position size
        )

        # Run backtest (synchronous)
        engine = BacktestEngine(config)
        result = engine.run(candles)

        return result.metrics

    def _extract_metric(self, metrics: PerformanceMetrics, metric_name: str) -> float:
        """
        Extract optimization metric from backtest results.
        
        Args:
            metrics: Performance metrics from backtest
            metric_name: Name of metric to extract
            
        Returns:
            Metric value, or 0.0 if not found
        """
        # Map metric names to attributes
        metric_map = {
            "sharpe_ratio": metrics.sharpe_ratio,
            "sortino_ratio": metrics.sortino_ratio,
            "total_return": metrics.total_return,
            "total_return_percent": metrics.total_return * 100,
            "max_drawdown": metrics.max_drawdown,
            "max_drawdown_percent": metrics.max_drawdown * 100,
            "win_rate": metrics.win_rate,
            "win_rate_percent": metrics.win_rate * 100,
            "profit_factor": metrics.profit_factor,
            "expectancy": metrics.expectancy,
            "total_trades": metrics.total_trades,
            "recovery_factor": metrics.recovery_factor,
        }

        value = metric_map.get(metric_name)

        if value is None:
            logger.warning(f"Metric '{metric_name}' not found or is None, using 0.0")
            return 0.0

        return float(value)
