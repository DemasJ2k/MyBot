# Prompt 06: Optimization Engine

## Purpose

Build a comprehensive parameter optimization system that discovers optimal strategy configurations through grid search, random search, and AI-driven optimization. The engine runs thousands of backtests, ranks results by performance metrics, and saves winning configurations as playbooks for deployment.

## Scope

- Parameter space definition and validation
- Grid search optimizer (exhaustive)
- Random search optimizer (Monte Carlo)
- AI-driven optimizer (Bayesian optimization with GPT suggestions)
- Parallel backtest execution
- Multi-objective optimization (maximize return, minimize drawdown)
- Result ranking and filtering
- Playbook generation from optimal configs
- Optimization job management and progress tracking
- Walk-forward analysis preparation
- Complete test suite

## Optimization Architecture

```
Strategy Config + Parameter Ranges
    ↓
Optimization Engine → [Grid / Random / AI Optimizer]
    ↓
Parallel Backtest Executor → Backtest Engine (Prompt 05)
    ↓
Results Aggregator → Performance Ranker
    ↓
Top Configs → Playbook Generator
    ↓
Database (optimizations, playbooks)
```

## Implementation

### Step 1: Database Models

Create `backend/app/models/optimization.py`:

```python
from sqlalchemy import String, Float, Integer, JSON, Enum as SQLEnum, ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from typing import Optional, Dict, Any, List
import enum
from app.models.base import Base, TimestampMixin


class OptimizationMethod(str, enum.Enum):
    GRID_SEARCH = "grid_search"
    RANDOM_SEARCH = "random_search"
    AI_DRIVEN = "ai_driven"
    GENETIC = "genetic"


class OptimizationStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class OptimizationJob(Base, TimestampMixin):
    """Optimization job configuration and status."""
    __tablename__ = "optimization_jobs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    strategy_name: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    interval: Mapped[str] = mapped_column(String(10), nullable=False)

    # Optimization parameters
    method: Mapped[OptimizationMethod] = mapped_column(SQLEnum(OptimizationMethod), nullable=False)
    status: Mapped[OptimizationStatus] = mapped_column(
        SQLEnum(OptimizationStatus),
        default=OptimizationStatus.PENDING,
        nullable=False,
        index=True
    )

    # Parameter space (JSON)
    parameter_ranges: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)

    # Backtest configuration
    start_date: Mapped[datetime] = mapped_column(nullable=False)
    end_date: Mapped[datetime] = mapped_column(nullable=False)
    initial_balance: Mapped[float] = mapped_column(Float, nullable=False, default=10000.0)
    commission_percent: Mapped[float] = mapped_column(Float, nullable=False, default=0.1)
    slippage_percent: Mapped[float] = mapped_column(Float, nullable=False, default=0.05)

    # Optimization settings
    max_iterations: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    objective_metric: Mapped[str] = mapped_column(String(50), nullable=False, default="sharpe_ratio")
    minimize: Mapped[bool] = mapped_column(default=False, nullable=False)  # False = maximize

    # Progress tracking
    total_combinations: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    completed_iterations: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    progress_percent: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # Results
    best_config: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    best_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    best_backtest_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Execution metadata
    started_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    results: Mapped[List["OptimizationResult"]] = relationship(
        "OptimizationResult",
        back_populates="job",
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_optimization_strategy_status", "strategy_name", "status"),
    )

    def __repr__(self) -> str:
        return f"<OptimizationJob {self.id} {self.strategy_name} {self.method.value} {self.status.value}>"


class OptimizationResult(Base, TimestampMixin):
    """Individual optimization iteration result."""
    __tablename__ = "optimization_results"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("optimization_jobs.id"), nullable=False, index=True)
    iteration: Mapped[int] = mapped_column(Integer, nullable=False)

    # Configuration tested
    config: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)

    # Performance metrics
    score: Mapped[float] = mapped_column(Float, nullable=False)  # Objective metric value
    total_return_percent: Mapped[float] = mapped_column(Float, nullable=False)
    sharpe_ratio: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_drawdown_percent: Mapped[float] = mapped_column(Float, nullable=False)
    win_rate_percent: Mapped[float] = mapped_column(Float, nullable=False)
    profit_factor: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    total_trades: Mapped[int] = mapped_column(Integer, nullable=False)

    # Reference to backtest
    backtest_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Relationships
    job: Mapped["OptimizationJob"] = relationship("OptimizationJob", back_populates="results")

    __table_args__ = (
        Index("ix_optimization_result_job_score", "job_id", "score"),
    )

    def __repr__(self) -> str:
        return f"<OptimizationResult {self.id} job={self.job_id} iter={self.iteration} score={self.score:.4f}>"


class Playbook(Base, TimestampMixin):
    """Saved strategy configuration for deployment."""
    __tablename__ = "playbooks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    strategy_name: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)

    # Strategy configuration (JSON)
    config: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)

    # Performance metrics from optimization
    expected_return_percent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    expected_sharpe_ratio: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    expected_max_drawdown_percent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Metadata
    optimization_job_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_playbook_strategy_active", "strategy_name", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<Playbook {self.id} '{self.name}' {self.strategy_name} {self.symbol}>"
```

Update `backend/app/models/__init__.py`:

```python
from app.models.base import Base, TimestampMixin
from app.models.user import User
from app.models.market_data import Candle, Symbol, EconomicEvent
from app.models.signal import Signal, SignalType, SignalStatus
from app.models.position import Position, PositionStatus, PositionSide
from app.models.backtest import BacktestResult
from app.models.optimization import (
    OptimizationJob,
    OptimizationResult,
    OptimizationMethod,
    OptimizationStatus,
    Playbook,
)

__all__ = [
    "Base",
    "TimestampMixin",
    "User",
    "Candle",
    "Symbol",
    "EconomicEvent",
    "Signal",
    "SignalType",
    "SignalStatus",
    "Position",
    "PositionStatus",
    "PositionSide",
    "BacktestResult",
    "OptimizationJob",
    "OptimizationResult",
    "OptimizationMethod",
    "OptimizationStatus",
    "Playbook",
]
```

### Step 2: Parameter Space Definition

Create `backend/app/optimization/parameter_space.py`:

```python
from typing import Dict, Any, List, Tuple
import itertools
import random
import logging

logger = logging.getLogger(__name__)


class ParameterSpace:
    """Defines and generates parameter combinations for optimization."""

    def __init__(self, parameter_ranges: Dict[str, Any]):
        """
        Args:
            parameter_ranges: Dict mapping parameter names to ranges
                Examples:
                    {"ema_fast": [10, 20, 30, 50]}  # Discrete values
                    {"risk_percent": {"min": 1.0, "max": 3.0, "step": 0.5}}  # Range
        """
        self.parameter_ranges = parameter_ranges
        self.parameters = list(parameter_ranges.keys())

    def generate_grid(self) -> List[Dict[str, Any]]:
        """
        Generate all possible combinations (grid search).

        Returns:
            List of config dictionaries
        """
        param_lists = []

        for param_name, param_def in self.parameter_ranges.items():
            if isinstance(param_def, list):
                # Discrete values
                param_lists.append(param_def)
            elif isinstance(param_def, dict) and "min" in param_def and "max" in param_def:
                # Range with step
                min_val = param_def["min"]
                max_val = param_def["max"]
                step = param_def.get("step", 1.0)

                values = []
                current = min_val
                while current <= max_val:
                    values.append(current)
                    current += step

                param_lists.append(values)
            else:
                raise ValueError(f"Invalid parameter definition for '{param_name}': {param_def}")

        # Generate all combinations
        combinations = list(itertools.product(*param_lists))

        configs = []
        for combo in combinations:
            config = {param_name: value for param_name, value in zip(self.parameters, combo)}
            configs.append(config)

        logger.info(f"Generated {len(configs)} configurations for grid search")
        return configs

    def generate_random(self, n_samples: int) -> List[Dict[str, Any]]:
        """
        Generate random parameter combinations (random search).

        Args:
            n_samples: Number of random samples to generate

        Returns:
            List of config dictionaries
        """
        configs = []

        for _ in range(n_samples):
            config = {}

            for param_name, param_def in self.parameter_ranges.items():
                if isinstance(param_def, list):
                    # Random choice from discrete values
                    config[param_name] = random.choice(param_def)
                elif isinstance(param_def, dict) and "min" in param_def and "max" in param_def:
                    # Random value in range
                    min_val = param_def["min"]
                    max_val = param_def["max"]
                    step = param_def.get("step", None)

                    if step:
                        # Discrete steps
                        num_steps = int((max_val - min_val) / step) + 1
                        random_step = random.randint(0, num_steps - 1)
                        config[param_name] = min_val + random_step * step
                    else:
                        # Continuous
                        config[param_name] = random.uniform(min_val, max_val)
                else:
                    raise ValueError(f"Invalid parameter definition for '{param_name}': {param_def}")

            configs.append(config)

        logger.info(f"Generated {len(configs)} random configurations")
        return configs

    def count_combinations(self) -> int:
        """Count total number of grid combinations."""
        count = 1

        for param_def in self.parameter_ranges.values():
            if isinstance(param_def, list):
                count *= len(param_def)
            elif isinstance(param_def, dict) and "min" in param_def and "max" in param_def:
                min_val = param_def["min"]
                max_val = param_def["max"]
                step = param_def.get("step", 1.0)
                num_values = int((max_val - min_val) / step) + 1
                count *= num_values

        return count
```

### Step 3: Grid Search Optimizer

Create `backend/app/optimization/grid_optimizer.py`:

```python
from typing import Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from app.optimization.parameter_space import ParameterSpace
from app.optimization.base_optimizer import BaseOptimizer
from app.models.optimization import OptimizationJob, OptimizationResult
import logging

logger = logging.getLogger(__name__)


class GridSearchOptimizer(BaseOptimizer):
    """Exhaustive grid search optimizer."""

    async def optimize(self, job: OptimizationJob, db: AsyncSession) -> List[Dict[str, Any]]:
        """
        Run grid search optimization.

        Returns:
            List of configurations to test
        """
        param_space = ParameterSpace(job.parameter_ranges)

        # Generate all combinations
        configs = param_space.generate_grid()

        # Update job with total combinations
        job.total_combinations = len(configs)
        await db.commit()

        logger.info(f"Grid search will test {len(configs)} configurations")

        # Limit to max_iterations if specified
        if job.max_iterations and len(configs) > job.max_iterations:
            logger.warning(f"Grid has {len(configs)} configs, limiting to {job.max_iterations}")
            configs = configs[:job.max_iterations]

        return configs
```

### Step 4: Random Search Optimizer

Create `backend/app/optimization/random_optimizer.py`:

```python
from typing import Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from app.optimization.parameter_space import ParameterSpace
from app.optimization.base_optimizer import BaseOptimizer
from app.models.optimization import OptimizationJob
import logging

logger = logging.getLogger(__name__)


class RandomSearchOptimizer(BaseOptimizer):
    """Monte Carlo random search optimizer."""

    async def optimize(self, job: OptimizationJob, db: AsyncSession) -> List[Dict[str, Any]]:
        """
        Run random search optimization.

        Returns:
            List of random configurations to test
        """
        param_space = ParameterSpace(job.parameter_ranges)

        # Generate random samples
        n_samples = job.max_iterations or 100
        configs = param_space.generate_random(n_samples)

        job.total_combinations = len(configs)
        await db.commit()

        logger.info(f"Random search will test {len(configs)} configurations")

        return configs
```

### Step 5: AI-Driven Optimizer

Create `backend/app/optimization/ai_optimizer.py`:

```python
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.optimization.parameter_space import ParameterSpace
from app.optimization.base_optimizer import BaseOptimizer
from app.models.optimization import OptimizationJob, OptimizationResult
from sqlalchemy import select, desc
import logging
import json

logger = logging.getLogger(__name__)


class AIOptimizer(BaseOptimizer):
    """
    AI-driven Bayesian optimization.

    Uses historical results to suggest promising parameter combinations.
    Balances exploration (untested regions) with exploitation (near-optimal regions).
    """

    async def optimize(self, job: OptimizationJob, db: AsyncSession) -> List[Dict[str, Any]]:
        """
        Run AI-driven optimization.

        Strategy:
        1. Start with random exploration (20% of iterations)
        2. Analyze top performers
        3. Generate variations around best configs
        4. Suggest unexplored parameter regions

        Returns:
            List of AI-suggested configurations
        """
        param_space = ParameterSpace(job.parameter_ranges)
        n_iterations = job.max_iterations or 50

        # Phase 1: Random exploration (first 20%)
        n_random = max(10, int(n_iterations * 0.2))
        configs = param_space.generate_random(n_random)

        # Phase 2: Exploitation based on historical results
        stmt = select(OptimizationResult).where(
            OptimizationResult.job_id == job.id
        ).order_by(desc(OptimizationResult.score)).limit(10)

        result = await db.execute(stmt)
        top_results = result.scalars().all()

        if top_results:
            # Generate variations around top performers
            n_exploit = n_iterations - n_random
            for i in range(n_exploit):
                # Pick a random top performer
                import random
                base_config = random.choice(top_results).config

                # Mutate parameters slightly
                mutated_config = self._mutate_config(base_config, param_space, mutation_rate=0.3)
                configs.append(mutated_config)

        job.total_combinations = len(configs)
        await db.commit()

        logger.info(f"AI optimizer will test {len(configs)} configurations ({n_random} random, {len(configs)-n_random} exploited)")

        return configs

    def _mutate_config(
        self,
        base_config: Dict[str, Any],
        param_space: ParameterSpace,
        mutation_rate: float = 0.3
    ) -> Dict[str, Any]:
        """
        Mutate a configuration by adjusting parameters slightly.

        Args:
            base_config: Base configuration to mutate
            param_space: Parameter space definition
            mutation_rate: Probability of mutating each parameter

        Returns:
            Mutated configuration
        """
        import random

        mutated = base_config.copy()

        for param_name, param_def in param_space.parameter_ranges.items():
            if random.random() < mutation_rate:
                if isinstance(param_def, list):
                    # Pick a different discrete value
                    mutated[param_name] = random.choice(param_def)
                elif isinstance(param_def, dict) and "min" in param_def:
                    # Adjust continuous value
                    current_val = base_config.get(param_name, param_def["min"])
                    min_val = param_def["min"]
                    max_val = param_def["max"]
                    step = param_def.get("step", (max_val - min_val) / 10.0)

                    # Random walk
                    delta = random.choice([-step, 0, step])
                    new_val = current_val + delta
                    new_val = max(min_val, min(max_val, new_val))

                    mutated[param_name] = new_val

        return mutated
```

### Step 6: Base Optimizer Class

Create `backend/app/optimization/base_optimizer.py`:

```python
from abc import ABC, abstractmethod
from typing import Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.optimization import OptimizationJob


class BaseOptimizer(ABC):
    """Base class for optimization algorithms."""

    @abstractmethod
    async def optimize(self, job: OptimizationJob, db: AsyncSession) -> List[Dict[str, Any]]:
        """
        Generate configurations to test.

        Args:
            job: Optimization job
            db: Database session

        Returns:
            List of parameter configurations to test
        """
        pass
```

### Step 7: Optimization Engine

Create `backend/app/optimization/engine.py`:

```python
from typing import Dict, Any, List, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.optimization import (
    OptimizationJob,
    OptimizationResult,
    OptimizationMethod,
    OptimizationStatus,
    Playbook,
)
from app.models.backtest import BacktestResult
from app.models.market_data import Candle
from app.strategies.strategy_manager import StrategyManager
from app.backtest.engine import BacktestEngine
from app.optimization.grid_optimizer import GridSearchOptimizer
from app.optimization.random_optimizer import RandomSearchOptimizer
from app.optimization.ai_optimizer import AIOptimizer
import logging
import asyncio

logger = logging.getLogger(__name__)


class OptimizationEngine:
    """Manages parameter optimization jobs."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def run_optimization(self, job_id: int) -> OptimizationJob:
        """
        Execute an optimization job.

        Args:
            job_id: Optimization job ID

        Returns:
            Updated job with results
        """
        # Load job
        stmt = select(OptimizationJob).where(OptimizationJob.id == job_id)
        result = await self.db.execute(stmt)
        job = result.scalar_one_or_none()

        if not job:
            raise ValueError(f"Optimization job {job_id} not found")

        if job.status != OptimizationStatus.PENDING:
            raise ValueError(f"Job {job_id} is not pending (status={job.status})")

        # Update status
        job.status = OptimizationStatus.RUNNING
        job.started_at = datetime.utcnow()
        await self.db.commit()

        try:
            # Select optimizer
            optimizer = self._get_optimizer(job.method)

            # Generate configurations
            configs = await optimizer.optimize(job, self.db)

            # Get historical candles for backtesting
            candles = await self._load_candles(job)

            if not candles:
                raise ValueError(f"No historical data for {job.symbol}")

            # Run backtests for each configuration
            for i, config in enumerate(configs):
                logger.info(f"Testing config {i+1}/{len(configs)}: {config}")

                # Run backtest with this config
                backtest_result = await self._run_backtest(job, config, candles)

                # Extract objective metric
                score = self._extract_metric(backtest_result, job.objective_metric)

                # Save result
                opt_result = OptimizationResult(
                    job_id=job.id,
                    iteration=i + 1,
                    config=config,
                    score=score,
                    total_return_percent=backtest_result["total_return_percent"],
                    sharpe_ratio=backtest_result["sharpe_ratio"],
                    max_drawdown_percent=backtest_result["max_drawdown_percent"],
                    win_rate_percent=backtest_result["win_rate_percent"],
                    profit_factor=backtest_result["profit_factor"],
                    total_trades=backtest_result["total_trades"],
                    backtest_id=None  # Could save backtest to DB
                )

                self.db.add(opt_result)

                # Update job progress
                job.completed_iterations = i + 1
                job.progress_percent = (i + 1) / len(configs) * 100.0

                # Update best if better
                if job.best_score is None:
                    job.best_score = score
                    job.best_config = config
                else:
                    if (not job.minimize and score > job.best_score) or (job.minimize and score < job.best_score):
                        job.best_score = score
                        job.best_config = config
                        logger.info(f"New best score: {score:.4f} with config {config}")

                await self.db.commit()

            # Mark as completed
            job.status = OptimizationStatus.COMPLETED
            job.completed_at = datetime.utcnow()
            await self.db.commit()

            logger.info(f"Optimization job {job_id} completed. Best score: {job.best_score:.4f}")

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
        """Get optimizer instance by method."""
        if method == OptimizationMethod.GRID_SEARCH:
            return GridSearchOptimizer()
        elif method == OptimizationMethod.RANDOM_SEARCH:
            return RandomSearchOptimizer()
        elif method == OptimizationMethod.AI_DRIVEN:
            return AIOptimizer()
        else:
            raise ValueError(f"Unknown optimization method: {method}")

    async def _load_candles(self, job: OptimizationJob) -> List[Candle]:
        """Load historical candles for backtesting."""
        from sqlalchemy import and_

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

        return candles

    async def _run_backtest(
        self,
        job: OptimizationJob,
        config: Dict[str, Any],
        candles: List[Candle]
    ) -> Dict[str, Any]:
        """Run a single backtest with given config."""
        # Get strategy with custom config
        manager = StrategyManager(db=self.db)
        strategy = manager.get_strategy(job.strategy_name)
        strategy.config = config  # Override with optimization config

        # Run backtest
        engine = BacktestEngine(
            strategy=strategy,
            candles=candles,
            initial_balance=job.initial_balance,
            commission_percent=job.commission_percent,
            slippage_percent=job.slippage_percent
        )

        results = await engine.run()
        return results

    def _extract_metric(self, backtest_result: Dict[str, Any], metric_name: str) -> float:
        """Extract optimization metric from backtest result."""
        value = backtest_result.get(metric_name)

        if value is None:
            logger.warning(f"Metric '{metric_name}' not found in backtest results, using 0.0")
            return 0.0

        return float(value)
```

### Step 8: Database Migration

```bash
cd backend
DATABASE_URL="sqlite+aiosqlite:///./flowrex_dev.db" python -m alembic revision --autogenerate -m "add_optimization_tables"
```

Run migration:
```bash
DATABASE_URL="sqlite+aiosqlite:///./flowrex_dev.db" python -m alembic upgrade head
```

### Step 9: API Routes

Create `backend/app/api/v1/optimization_routes.py`:

```python
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from app.database import get_db
from app.models.optimization import (
    OptimizationJob,
    OptimizationResult,
    OptimizationMethod,
    OptimizationStatus,
    Playbook,
)
from app.optimization.engine import OptimizationEngine
from sqlalchemy import select, desc
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/optimization", tags=["optimization"])


class OptimizationJobCreate(BaseModel):
    strategy_name: str
    symbol: str
    interval: str = "1h"
    method: OptimizationMethod
    parameter_ranges: Dict[str, Any]
    start_date: datetime
    end_date: datetime
    initial_balance: float = 10000.0
    commission_percent: float = 0.1
    slippage_percent: float = 0.05
    max_iterations: int = 100
    objective_metric: str = "sharpe_ratio"
    minimize: bool = False


class OptimizationJobResponse(BaseModel):
    id: int
    strategy_name: str
    symbol: str
    method: str
    status: str
    progress_percent: float
    best_score: float | None
    best_config: Dict[str, Any] | None
    created_at: datetime

    class Config:
        from_attributes = True


class PlaybookCreate(BaseModel):
    name: str
    notes: Optional[str] = None


class PlaybookResponse(BaseModel):
    id: int
    name: str
    strategy_name: str
    symbol: str
    config: Dict[str, Any]
    expected_return_percent: float | None
    expected_sharpe_ratio: float | None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


@router.post("/jobs", response_model=OptimizationJobResponse)
async def create_optimization_job(
    request: OptimizationJobCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """
    Create and start an optimization job.

    The job runs in the background and can be polled for progress.
    """
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

    logger.info(f"Created optimization job {job.id}")

    return job


async def run_optimization_task(job_id: int):
    """Background task to run optimization."""
    from app.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        try:
            engine = OptimizationEngine(db=db)
            await engine.run_optimization(job_id)
        except Exception as e:
            logger.error(f"Optimization task failed: {e}")


@router.get("/jobs", response_model=List[OptimizationJobResponse])
async def list_optimization_jobs(
    strategy_name: Optional[str] = None,
    status: Optional[OptimizationStatus] = None,
    limit: int = Query(20, ge=1, le=100),
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


@router.get("/jobs/{job_id}")
async def get_optimization_job(job_id: int, db: AsyncSession = Depends(get_db)):
    """Get detailed optimization job information."""
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
                "max_drawdown_percent": r.max_drawdown_percent
            }
            for r in top_results
        ]
    }


@router.post("/jobs/{job_id}/playbook", response_model=PlaybookResponse)
async def create_playbook(
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
    strategy_name: Optional[str] = None,
    symbol: Optional[str] = None,
    is_active: Optional[bool] = None,
    limit: int = Query(50, ge=1, le=200),
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


@router.patch("/playbooks/{playbook_id}")
async def update_playbook(
    playbook_id: int,
    is_active: Optional[bool] = None,
    notes: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Update playbook status or notes."""
    stmt = select(Playbook).where(Playbook.id == playbook_id)
    result = await db.execute(stmt)
    playbook = result.scalar_one_or_none()

    if not playbook:
        raise HTTPException(status_code=404, detail="Playbook not found")

    if is_active is not None:
        playbook.is_active = is_active
    if notes is not None:
        playbook.notes = notes

    await db.commit()

    return {"message": "Playbook updated"}
```

Register routes in `backend/app/main.py`:

```python
from app.api.v1 import auth_routes, data_routes, strategy_routes, backtest_routes, optimization_routes

app.include_router(optimization_routes.router, prefix="/api/v1")
```

### Step 10: Tests

Create `backend/tests/unit/test_optimization.py`:

```python
import pytest
from app.optimization.parameter_space import ParameterSpace


class TestParameterSpace:
    def test_grid_generation_discrete(self):
        param_ranges = {
            "ema_fast": [10, 20, 30],
            "ema_slow": [50, 100]
        }

        space = ParameterSpace(param_ranges)
        configs = space.generate_grid()

        assert len(configs) == 6  # 3 x 2
        assert {"ema_fast": 10, "ema_slow": 50} in configs
        assert {"ema_fast": 30, "ema_slow": 100} in configs

    def test_grid_generation_range(self):
        param_ranges = {
            "risk_percent": {"min": 1.0, "max": 3.0, "step": 1.0}
        }

        space = ParameterSpace(param_ranges)
        configs = space.generate_grid()

        assert len(configs) == 3  # 1.0, 2.0, 3.0
        assert {"risk_percent": 1.0} in configs
        assert {"risk_percent": 3.0} in configs

    def test_random_generation(self):
        param_ranges = {
            "ema_fast": [10, 20, 30, 50],
            "risk_percent": {"min": 1.0, "max": 3.0}
        }

        space = ParameterSpace(param_ranges)
        configs = space.generate_random(n_samples=10)

        assert len(configs) == 10

        for config in configs:
            assert config["ema_fast"] in [10, 20, 30, 50]
            assert 1.0 <= config["risk_percent"] <= 3.0

    def test_count_combinations(self):
        param_ranges = {
            "ema_fast": [10, 20, 30],
            "ema_slow": [50, 100],
            "risk_percent": {"min": 1.0, "max": 2.0, "step": 0.5}
        }

        space = ParameterSpace(param_ranges)
        count = space.count_combinations()

        assert count == 3 * 2 * 3  # 18 combinations
```

Run tests:
```bash
cd backend
DATABASE_URL="sqlite+aiosqlite:///./flowrex_dev.db" python -m pytest tests/unit/test_optimization.py -v
```

### Step 11: Manual Testing

Start server:
```bash
cd backend
DATABASE_URL="sqlite+aiosqlite:///./flowrex_dev.db" python -m uvicorn app.main:app --reload
```

Create optimization job:

```bash
curl -X POST "http://localhost:8000/api/v1/optimization/jobs" \
  -H "Content-Type: application/json" \
  -d '{
    "strategy_name": "NBB",
    "symbol": "EURUSD",
    "interval": "1h",
    "method": "grid_search",
    "parameter_ranges": {
      "zone_lookback": [10, 20, 30],
      "risk_percent": {"min": 1.0, "max": 2.0, "step": 0.5}
    },
    "start_date": "2024-01-01T00:00:00Z",
    "end_date": "2024-06-01T00:00:00Z",
    "max_iterations": 20,
    "objective_metric": "sharpe_ratio"
  }'
```

Check job status:
```bash
curl "http://localhost:8000/api/v1/optimization/jobs/1"
```

Create playbook from results:
```bash
curl -X POST "http://localhost:8000/api/v1/optimization/jobs/1/playbook" \
  -H "Content-Type: application/json" \
  -d '{"name": "NBB_EURUSD_Optimized_v1", "notes": "Optimized for Sharpe ratio"}'
```

## Validation Checklist

Before proceeding to Prompt 07, verify:

- [ ] OptimizationJob, OptimizationResult, Playbook models created
- [ ] Database migration applied successfully
- [ ] ParameterSpace generates grid configurations correctly
- [ ] ParameterSpace generates random configurations correctly
- [ ] Grid search optimizer implemented
- [ ] Random search optimizer implemented
- [ ] AI-driven optimizer implemented with mutation logic
- [ ] OptimizationEngine runs backtests for each config
- [ ] OptimizationEngine tracks best config and score
- [ ] OptimizationEngine updates progress during execution
- [ ] API route `/optimization/jobs` creates jobs
- [ ] API route `/optimization/jobs/{id}` returns job status and top results
- [ ] API route `/optimization/jobs/{id}/playbook` creates playbooks
- [ ] API route `/optimization/playbooks` lists playbooks
- [ ] All unit tests pass
- [ ] Can create grid search optimization job via API
- [ ] Can monitor optimization progress
- [ ] Can create playbook from completed optimization
- [ ] Playbooks contain optimized strategy configs
- [ ] Background task execution works for long-running optimizations
- [ ] CROSSCHECK.md validation for Prompt 06 completed

## Hard Stop Criteria

**DO NOT PROCEED to Prompt 07 unless:**

1. ✅ Database migration runs without errors
2. ✅ All pytest tests pass (0 failures, 0 errors)
3. ✅ Grid search generates correct number of combinations
4. ✅ Random search generates valid random configs within ranges
5. ✅ AI optimizer mutates configs intelligently
6. ✅ Optimization engine completes full job successfully
7. ✅ Best config is identified and saved
8. ✅ Can create playbook from optimization results
9. ✅ Playbook contains all expected fields (config, metrics)
10. ✅ CROSSCHECK.md section for Prompt 06 fully validated

If any criterion fails, **HALT** and fix before continuing.

---

**Completion Criteria:**
- Optimization engine fully operational with 3 methods (grid, random, AI)
- Parameter space handling for discrete and continuous ranges
- Backtest-driven optimization with progress tracking
- Playbook generation from optimal configs
- System ready for AI Agent System (Prompt 07)
