"""
Grid search optimizer - exhaustive search over parameter combinations.
"""

from typing import Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from app.optimization.parameter_space import ParameterSpace
from app.optimization.base_optimizer import BaseOptimizer
from app.models.optimization import OptimizationJob

logger = logging.getLogger(__name__)


class GridSearchOptimizer(BaseOptimizer):
    """
    Exhaustive grid search optimizer.
    
    Tests all possible combinations of parameters within the defined
    parameter space. Best for small parameter spaces.
    """

    async def optimize(self, job: OptimizationJob, db: AsyncSession) -> List[Dict[str, Any]]:
        """
        Generate all grid search configurations.

        Args:
            job: Optimization job with parameter ranges
            db: Database session

        Returns:
            List of all parameter combinations to test
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
            logger.warning(
                f"Grid has {len(configs)} configs, limiting to {job.max_iterations}"
            )
            configs = configs[:job.max_iterations]

        return configs
