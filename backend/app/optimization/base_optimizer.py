"""
Base optimizer abstract class.

All optimization algorithms inherit from this base class.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.optimization import OptimizationJob


class BaseOptimizer(ABC):
    """
    Base class for optimization algorithms.
    
    Subclasses must implement the optimize() method to generate
    configurations to test.
    """

    @abstractmethod
    async def optimize(self, job: OptimizationJob, db: AsyncSession) -> List[Dict[str, Any]]:
        """
        Generate configurations to test.

        Args:
            job: Optimization job with parameters and settings
            db: Database session for persistence

        Returns:
            List of parameter configurations to test
        """
        pass
