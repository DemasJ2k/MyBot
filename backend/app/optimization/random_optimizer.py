"""
Random search optimizer - Monte Carlo sampling of parameter space.
"""

from typing import Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from app.optimization.parameter_space import ParameterSpace
from app.optimization.base_optimizer import BaseOptimizer
from app.models.optimization import OptimizationJob

logger = logging.getLogger(__name__)


class RandomSearchOptimizer(BaseOptimizer):
    """
    Monte Carlo random search optimizer.
    
    Randomly samples parameter combinations. Often more efficient than
    grid search for high-dimensional parameter spaces.
    """

    async def optimize(self, job: OptimizationJob, db: AsyncSession) -> List[Dict[str, Any]]:
        """
        Generate random parameter configurations.

        Args:
            job: Optimization job with parameter ranges
            db: Database session

        Returns:
            List of randomly sampled configurations
        """
        param_space = ParameterSpace(job.parameter_ranges)

        # Generate random samples
        n_samples = job.max_iterations or 100
        configs = param_space.generate_random(n_samples)

        job.total_combinations = len(configs)
        await db.commit()

        logger.info(f"Random search will test {len(configs)} configurations")

        return configs
