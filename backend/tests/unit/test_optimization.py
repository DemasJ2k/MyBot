"""
Unit tests for Optimization Engine (Prompt 06).

Tests cover:
- ParameterSpace grid/random generation
- Grid, Random, AI optimizers
- OptimizationJob/Result/Playbook models
- API routes
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import random

from app.optimization.parameter_space import ParameterSpace
from app.optimization.grid_optimizer import GridSearchOptimizer
from app.optimization.random_optimizer import RandomSearchOptimizer
from app.optimization.ai_optimizer import AIOptimizer
from app.models.optimization import (
    OptimizationJob,
    OptimizationResult,
    OptimizationMethod,
    OptimizationStatus,
    Playbook,
)


# ============================================================================
# ParameterSpace Tests
# ============================================================================


class TestParameterSpace:
    """Tests for ParameterSpace class."""

    def test_grid_generation_discrete(self):
        """Grid search with discrete values generates all combinations."""
        param_ranges = {
            "ema_fast": [10, 20, 30],
            "ema_slow": [50, 100]
        }

        space = ParameterSpace(param_ranges)
        configs = space.generate_grid()

        assert len(configs) == 6  # 3 x 2
        assert {"ema_fast": 10, "ema_slow": 50} in configs
        assert {"ema_fast": 10, "ema_slow": 100} in configs
        assert {"ema_fast": 20, "ema_slow": 50} in configs
        assert {"ema_fast": 20, "ema_slow": 100} in configs
        assert {"ema_fast": 30, "ema_slow": 50} in configs
        assert {"ema_fast": 30, "ema_slow": 100} in configs

    def test_grid_generation_range(self):
        """Grid search with range + step generates correct values."""
        param_ranges = {
            "risk_percent": {"min": 1.0, "max": 3.0, "step": 1.0}
        }

        space = ParameterSpace(param_ranges)
        configs = space.generate_grid()

        assert len(configs) == 3  # 1.0, 2.0, 3.0
        
        values = [c["risk_percent"] for c in configs]
        assert pytest.approx(1.0, rel=0.001) in values
        assert pytest.approx(2.0, rel=0.001) in values
        assert pytest.approx(3.0, rel=0.001) in values

    def test_grid_generation_mixed(self):
        """Grid search with mixed discrete and range parameters."""
        param_ranges = {
            "ema_fast": [10, 20],
            "risk_percent": {"min": 1.0, "max": 2.0, "step": 0.5}
        }

        space = ParameterSpace(param_ranges)
        configs = space.generate_grid()

        # 2 discrete x 3 range values (1.0, 1.5, 2.0)
        assert len(configs) == 6

    def test_random_generation(self):
        """Random search generates valid configs within bounds."""
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

    def test_random_generation_with_step(self):
        """Random search with step respects discrete increments."""
        param_ranges = {
            "risk_percent": {"min": 1.0, "max": 2.0, "step": 0.5}
        }

        space = ParameterSpace(param_ranges)
        configs = space.generate_random(n_samples=20)

        valid_values = [1.0, 1.5, 2.0]
        for config in configs:
            assert any(
                pytest.approx(config["risk_percent"], rel=0.001) == v 
                for v in valid_values
            ), f"Invalid value: {config['risk_percent']}"

    def test_count_combinations(self):
        """Combination counting is accurate."""
        param_ranges = {
            "ema_fast": [10, 20, 30],
            "ema_slow": [50, 100],
            "risk_percent": {"min": 1.0, "max": 2.0, "step": 0.5}
        }

        space = ParameterSpace(param_ranges)
        count = space.count_combinations()

        # 3 x 2 x 3 = 18 combinations
        assert count == 18

    def test_count_combinations_single_param(self):
        """Combination counting works for single parameter."""
        param_ranges = {
            "lookback": [10, 20, 30, 40, 50]
        }

        space = ParameterSpace(param_ranges)
        count = space.count_combinations()

        assert count == 5

    def test_invalid_param_raises_error(self):
        """Invalid parameter definition raises ValueError."""
        param_ranges = {
            "invalid": "not_a_list_or_dict"
        }

        space = ParameterSpace(param_ranges)
        
        with pytest.raises(ValueError, match="Invalid parameter definition"):
            space.generate_grid()

    def test_invalid_range_missing_min(self):
        """Range missing 'min' raises ValueError."""
        param_ranges = {
            "risk": {"max": 3.0}
        }

        space = ParameterSpace(param_ranges)
        
        with pytest.raises(ValueError, match="Invalid parameter definition"):
            space.generate_grid()

    def test_validate_success(self):
        """Valid parameter space passes validation."""
        param_ranges = {
            "ema": [10, 20],
            "risk": {"min": 1.0, "max": 2.0}
        }

        space = ParameterSpace(param_ranges)
        assert space.validate() is True

    def test_validate_empty_list(self):
        """Empty list fails validation."""
        param_ranges = {
            "ema": []
        }

        space = ParameterSpace(param_ranges)
        
        with pytest.raises(ValueError, match="empty list"):
            space.validate()

    def test_validate_min_greater_than_max(self):
        """Min > max fails validation."""
        param_ranges = {
            "risk": {"min": 3.0, "max": 1.0}
        }

        space = ParameterSpace(param_ranges)
        
        with pytest.raises(ValueError, match="min > max"):
            space.validate()


# ============================================================================
# Optimizer Tests
# ============================================================================


class TestGridSearchOptimizer:
    """Tests for GridSearchOptimizer."""

    @pytest.mark.asyncio
    async def test_optimize_generates_grid(self):
        """Grid optimizer generates all combinations."""
        # Mock job and db
        job = MagicMock()
        job.parameter_ranges = {
            "ema": [10, 20],
            "risk": [1.0, 2.0]
        }
        job.max_iterations = None

        db = AsyncMock()

        optimizer = GridSearchOptimizer()
        configs = await optimizer.optimize(job, db)

        assert len(configs) == 4
        assert job.total_combinations == 4
        db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_optimize_respects_max_iterations(self):
        """Grid optimizer limits to max_iterations."""
        job = MagicMock()
        job.parameter_ranges = {
            "ema": [10, 20, 30, 40, 50]
        }
        job.max_iterations = 3

        db = AsyncMock()

        optimizer = GridSearchOptimizer()
        configs = await optimizer.optimize(job, db)

        assert len(configs) == 3  # Limited by max_iterations


class TestRandomSearchOptimizer:
    """Tests for RandomSearchOptimizer."""

    @pytest.mark.asyncio
    async def test_optimize_generates_random_samples(self):
        """Random optimizer generates requested number of samples."""
        job = MagicMock()
        job.parameter_ranges = {
            "ema": [10, 20, 30],
            "risk": {"min": 1.0, "max": 3.0}
        }
        job.max_iterations = 15

        db = AsyncMock()

        optimizer = RandomSearchOptimizer()
        configs = await optimizer.optimize(job, db)

        assert len(configs) == 15
        assert job.total_combinations == 15

    @pytest.mark.asyncio
    async def test_optimize_default_iterations(self):
        """Random optimizer uses default 100 if max_iterations is None."""
        job = MagicMock()
        job.parameter_ranges = {
            "ema": [10, 20]
        }
        job.max_iterations = None

        db = AsyncMock()

        optimizer = RandomSearchOptimizer()
        configs = await optimizer.optimize(job, db)

        assert len(configs) == 100


class TestAIOptimizer:
    """Tests for AIOptimizer."""

    @pytest.mark.asyncio
    async def test_optimize_with_no_history(self):
        """AI optimizer generates random configs when no history."""
        job = MagicMock()
        job.id = 1
        job.parameter_ranges = {
            "ema": [10, 20, 30],
            "risk": {"min": 1.0, "max": 2.0}
        }
        job.max_iterations = 20

        # Mock empty history
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        db.execute.return_value = mock_result

        optimizer = AIOptimizer()
        configs = await optimizer.optimize(job, db)

        assert len(configs) == 20

    @pytest.mark.asyncio
    async def test_optimize_with_history(self):
        """AI optimizer exploits top configs when history exists."""
        job = MagicMock()
        job.id = 1
        job.parameter_ranges = {
            "ema": [10, 20, 30],
            "risk": {"min": 1.0, "max": 2.0, "step": 0.5}
        }
        job.max_iterations = 20

        # Mock history with top configs
        mock_result1 = MagicMock()
        mock_result1.config = {"ema": 20, "risk": 1.5}
        mock_result2 = MagicMock()
        mock_result2.config = {"ema": 30, "risk": 2.0}

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_result1, mock_result2]
        db.execute.return_value = mock_result

        optimizer = AIOptimizer()
        configs = await optimizer.optimize(job, db)

        assert len(configs) == 20
        # First ~20% should be random, rest exploited
        assert job.total_combinations == 20

    def test_mutate_config(self):
        """Mutation produces valid configs."""
        param_ranges = {
            "ema": [10, 20, 30],
            "risk": {"min": 1.0, "max": 2.0, "step": 0.5}
        }
        param_space = ParameterSpace(param_ranges)
        base_config = {"ema": 20, "risk": 1.5}

        optimizer = AIOptimizer()
        
        # Run multiple mutations to test randomness
        for _ in range(10):
            mutated = optimizer._mutate_config(base_config, param_space, mutation_rate=1.0)
            
            # Check values are valid
            assert mutated["ema"] in [10, 20, 30]
            assert 1.0 <= mutated["risk"] <= 2.0


# ============================================================================
# Model Tests
# ============================================================================


class TestOptimizationJobModel:
    """Tests for OptimizationJob model."""

    def test_model_creation(self):
        """OptimizationJob can be created with required fields."""
        job = OptimizationJob(
            strategy_name="NBB",
            symbol="EURUSD",
            interval="1h",
            method=OptimizationMethod.GRID_SEARCH,
            status=OptimizationStatus.PENDING,
            parameter_ranges={"ema": [10, 20]},
            start_date=datetime.now(),
            end_date=datetime.now() + timedelta(days=30),
            initial_balance=10000.0,
            commission_percent=0.1,
            slippage_percent=0.05,
            max_iterations=100,
            objective_metric="sharpe_ratio",
            minimize=False,
        )

        assert job.strategy_name == "NBB"
        assert job.method == OptimizationMethod.GRID_SEARCH
        assert job.status == OptimizationStatus.PENDING

    def test_model_repr(self):
        """OptimizationJob has readable repr."""
        job = OptimizationJob(
            id=1,
            strategy_name="NBB",
            symbol="EURUSD",
            interval="1h",
            method=OptimizationMethod.GRID_SEARCH,
            status=OptimizationStatus.RUNNING,
            parameter_ranges={},
            start_date=datetime.now(),
            end_date=datetime.now(),
        )

        repr_str = repr(job)
        assert "OptimizationJob" in repr_str
        assert "NBB" in repr_str
        assert "grid_search" in repr_str
        assert "running" in repr_str


class TestOptimizationResultModel:
    """Tests for OptimizationResult model."""

    def test_model_creation(self):
        """OptimizationResult can be created with required fields."""
        result = OptimizationResult(
            job_id=1,
            iteration=5,
            config={"ema": 20, "risk": 1.5},
            score=1.25,
            total_return_percent=15.5,
            sharpe_ratio=1.25,
            max_drawdown_percent=8.2,
            win_rate_percent=55.0,
            profit_factor=1.8,
            total_trades=42,
        )

        assert result.iteration == 5
        assert result.score == 1.25
        assert result.config == {"ema": 20, "risk": 1.5}


class TestPlaybookModel:
    """Tests for Playbook model."""

    def test_model_creation(self):
        """Playbook can be created with required fields."""
        playbook = Playbook(
            name="NBB_Optimized_v1",
            strategy_name="NBB",
            symbol="EURUSD",
            config={"ema": 20, "risk": 1.5},
            expected_return_percent=15.5,
            expected_sharpe_ratio=1.25,
            is_active=True,
        )

        assert playbook.name == "NBB_Optimized_v1"
        assert playbook.is_active is True

    def test_model_repr(self):
        """Playbook has readable repr."""
        playbook = Playbook(
            id=1,
            name="Test_Playbook",
            strategy_name="NBB",
            symbol="EURUSD",
            config={},
        )

        repr_str = repr(playbook)
        assert "Playbook" in repr_str
        assert "Test_Playbook" in repr_str


# ============================================================================
# Enum Tests
# ============================================================================


class TestOptimizationEnums:
    """Tests for optimization enums."""

    def test_optimization_method_values(self):
        """OptimizationMethod has expected values."""
        assert OptimizationMethod.GRID_SEARCH.value == "grid_search"
        assert OptimizationMethod.RANDOM_SEARCH.value == "random_search"
        assert OptimizationMethod.AI_DRIVEN.value == "ai_driven"
        assert OptimizationMethod.GENETIC.value == "genetic"

    def test_optimization_status_values(self):
        """OptimizationStatus has expected values."""
        assert OptimizationStatus.PENDING.value == "pending"
        assert OptimizationStatus.RUNNING.value == "running"
        assert OptimizationStatus.COMPLETED.value == "completed"
        assert OptimizationStatus.FAILED.value == "failed"
        assert OptimizationStatus.CANCELLED.value == "cancelled"


# ============================================================================
# Integration-style Tests
# ============================================================================


class TestParameterSpaceEdgeCases:
    """Edge case tests for ParameterSpace."""

    def test_single_value_list(self):
        """Single value list generates single config."""
        param_ranges = {"ema": [20]}
        space = ParameterSpace(param_ranges)
        configs = space.generate_grid()
        
        assert len(configs) == 1
        assert configs[0]["ema"] == 20

    def test_zero_step_range(self):
        """Range with min=max generates single value."""
        param_ranges = {"risk": {"min": 1.5, "max": 1.5, "step": 0.1}}
        space = ParameterSpace(param_ranges)
        configs = space.generate_grid()
        
        assert len(configs) == 1
        assert pytest.approx(configs[0]["risk"], rel=0.001) == 1.5

    def test_many_parameters(self):
        """Many parameters generate combinatorial explosion correctly."""
        param_ranges = {
            "p1": [1, 2],
            "p2": [1, 2],
            "p3": [1, 2],
            "p4": [1, 2],
        }
        space = ParameterSpace(param_ranges)
        
        assert space.count_combinations() == 16  # 2^4
        
        configs = space.generate_grid()
        assert len(configs) == 16

    def test_floating_point_precision(self):
        """Floating point ranges handle precision correctly."""
        param_ranges = {
            "risk": {"min": 0.1, "max": 0.3, "step": 0.1}
        }
        space = ParameterSpace(param_ranges)
        configs = space.generate_grid()
        
        # Should have 3 values: 0.1, 0.2, 0.3
        assert len(configs) == 3
        
        values = sorted([c["risk"] for c in configs])
        assert pytest.approx(values[0], rel=0.01) == 0.1
        assert pytest.approx(values[1], rel=0.01) == 0.2
        assert pytest.approx(values[2], rel=0.01) == 0.3


class TestOptimizerEdgeCases:
    """Edge case tests for optimizers."""

    @pytest.mark.asyncio
    async def test_grid_max_iterations_none_means_no_limit(self):
        """Grid with max_iterations=None returns all configs."""
        job = MagicMock()
        job.parameter_ranges = {"ema": [10, 20, 30]}
        job.max_iterations = None

        db = AsyncMock()

        optimizer = GridSearchOptimizer()
        configs = await optimizer.optimize(job, db)

        # None means no limit, all configs returned
        assert len(configs) == 3

    @pytest.mark.asyncio
    async def test_random_seeded_reproducibility(self):
        """Random optimizer can be made reproducible with seed."""
        job = MagicMock()
        job.parameter_ranges = {"ema": [10, 20, 30, 40, 50]}
        job.max_iterations = 5

        db = AsyncMock()

        # Seed random for reproducibility
        random.seed(42)
        optimizer1 = RandomSearchOptimizer()
        configs1 = await optimizer1.optimize(job, db)

        random.seed(42)
        optimizer2 = RandomSearchOptimizer()
        configs2 = await optimizer2.optimize(job, db)

        assert configs1 == configs2
