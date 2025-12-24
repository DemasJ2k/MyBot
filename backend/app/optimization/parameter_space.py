"""
Parameter space definition and generation for optimization.

Handles discrete value lists and continuous ranges with step sizes.
"""

from typing import Dict, Any, List
import itertools
import random
import logging

logger = logging.getLogger(__name__)


class ParameterSpace:
    """
    Defines and generates parameter combinations for optimization.
    
    Supports two types of parameter definitions:
    1. Discrete values: {"param": [1, 2, 3, 4]}
    2. Range with step: {"param": {"min": 1.0, "max": 3.0, "step": 0.5}}
    """

    def __init__(self, parameter_ranges: Dict[str, Any]):
        """
        Initialize parameter space.

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
            List of config dictionaries containing all combinations
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
                # Use a small epsilon for floating point comparison
                while current <= max_val + 1e-9:
                    values.append(round(current, 10))  # Round to avoid floating point artifacts
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
            List of config dictionaries with random values
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
                        # Discrete steps within range
                        num_steps = int((max_val - min_val) / step) + 1
                        random_step = random.randint(0, num_steps - 1)
                        config[param_name] = round(min_val + random_step * step, 10)
                    else:
                        # Continuous random value
                        config[param_name] = random.uniform(min_val, max_val)
                else:
                    raise ValueError(f"Invalid parameter definition for '{param_name}': {param_def}")

            configs.append(config)

        logger.info(f"Generated {len(configs)} random configurations")
        return configs

    def count_combinations(self) -> int:
        """
        Count total number of grid combinations.
        
        Returns:
            Total number of possible combinations
        """
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

    def validate(self) -> bool:
        """
        Validate parameter space definition.
        
        Returns:
            True if valid, raises ValueError otherwise
        """
        if not self.parameter_ranges:
            raise ValueError("Parameter ranges cannot be empty")
            
        for param_name, param_def in self.parameter_ranges.items():
            if isinstance(param_def, list):
                if len(param_def) == 0:
                    raise ValueError(f"Parameter '{param_name}' has empty list")
            elif isinstance(param_def, dict):
                if "min" not in param_def or "max" not in param_def:
                    raise ValueError(f"Parameter '{param_name}' range missing 'min' or 'max'")
                if param_def["min"] > param_def["max"]:
                    raise ValueError(f"Parameter '{param_name}' has min > max")
            else:
                raise ValueError(f"Invalid parameter definition for '{param_name}'")
                
        return True
