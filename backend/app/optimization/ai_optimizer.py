"""
AI-driven optimizer using Bayesian-style optimization.

Combines exploration (random search) with exploitation (mutation of best configs).
"""

from typing import Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
import random
import logging

from app.optimization.parameter_space import ParameterSpace
from app.optimization.base_optimizer import BaseOptimizer
from app.models.optimization import OptimizationJob, OptimizationResult

logger = logging.getLogger(__name__)


class AIOptimizer(BaseOptimizer):
    """
    AI-driven Bayesian-style optimization.

    Uses historical results to suggest promising parameter combinations.
    Balances exploration (untested regions) with exploitation (near-optimal regions).
    
    Strategy:
    1. Start with random exploration (20% of iterations)
    2. Analyze top performers from previous iterations
    3. Generate mutations around best configs
    """

    async def optimize(self, job: OptimizationJob, db: AsyncSession) -> List[Dict[str, Any]]:
        """
        Generate AI-suggested configurations.

        Args:
            job: Optimization job with parameter ranges
            db: Database session

        Returns:
            List of AI-suggested configurations
        """
        param_space = ParameterSpace(job.parameter_ranges)
        n_iterations = job.max_iterations or 50

        # Phase 1: Random exploration (first 20%)
        n_random = max(10, int(n_iterations * 0.2))
        configs = param_space.generate_random(n_random)

        # Phase 2: Check for existing results to exploit
        stmt = select(OptimizationResult).where(
            OptimizationResult.job_id == job.id
        ).order_by(desc(OptimizationResult.score)).limit(10)

        result = await db.execute(stmt)
        top_results = result.scalars().all()

        if top_results:
            # Generate variations around top performers
            n_exploit = n_iterations - n_random
            for _ in range(n_exploit):
                # Pick a random top performer
                base_config = random.choice(top_results).config

                # Mutate parameters slightly
                mutated_config = self._mutate_config(
                    base_config, 
                    param_space, 
                    mutation_rate=0.3
                )
                configs.append(mutated_config)
        else:
            # No history yet - generate more random configs
            additional = param_space.generate_random(n_iterations - n_random)
            configs.extend(additional)

        job.total_combinations = len(configs)
        await db.commit()

        logger.info(
            f"AI optimizer will test {len(configs)} configurations "
            f"({n_random} random, {len(configs) - n_random} exploited/random)"
        )

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
        mutated = base_config.copy()

        for param_name, param_def in param_space.parameter_ranges.items():
            if random.random() < mutation_rate:
                if isinstance(param_def, list):
                    # Pick a different discrete value
                    mutated[param_name] = random.choice(param_def)
                elif isinstance(param_def, dict) and "min" in param_def:
                    # Adjust continuous value with random walk
                    current_val = base_config.get(param_name, param_def["min"])
                    min_val = param_def["min"]
                    max_val = param_def["max"]
                    step = param_def.get("step", (max_val - min_val) / 10.0)

                    # Random walk: -step, 0, or +step
                    delta = random.choice([-step, 0, step])
                    new_val = current_val + delta
                    new_val = max(min_val, min(max_val, new_val))

                    mutated[param_name] = round(new_val, 10)

        return mutated
