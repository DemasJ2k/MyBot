"""
Secrets Management for Flowrex.

Prompt 17 - Deployment Prep.

Provides:
- Centralized secrets access
- Environment variable validation  
- Secret masking for logs
- AWS Secrets Manager integration (optional)
"""

import os
import logging
from typing import Optional, Dict, Any
from functools import lru_cache

logger = logging.getLogger(__name__)


class SecretsManager:
    """Centralized secrets management with validation and caching."""

    # Secrets required for each environment
    REQUIRED_SECRETS: Dict[str, list] = {
        "development": [],  # Allow everything optional in dev
        "staging": [
            "JWT_SECRET_KEY",
            "DATABASE_URL",
        ],
        "production": [
            "JWT_SECRET_KEY",
            "APP_SECRET_KEY",
            "DATABASE_URL",
        ],
    }

    # Secrets that should never be logged
    SENSITIVE_KEYS = {
        "JWT_SECRET_KEY",
        "APP_SECRET_KEY",
        "SECRET_KEY",
        "DATABASE_URL",
        "REDIS_URL",
        "API_KEY",
        "PASSWORD",
        "TOKEN",
    }

    def __init__(self):
        """Initialize secrets manager."""
        self._cache: Dict[str, str] = {}
        self._aws_client = None

    def get_secret(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get a secret value with caching.
        
        Args:
            key: The secret key name
            default: Default value if not found
            
        Returns:
            The secret value or default
        """
        # Check cache first
        if key in self._cache:
            return self._cache[key]

        # Try environment variable
        value = os.getenv(key)
        if value:
            self._cache[key] = value
            return value

        # Could add AWS Secrets Manager lookup here
        # value = self._get_from_aws(key)
        # if value:
        #     self._cache[key] = value
        #     return value

        return default

    def validate_required_secrets(self, environment: str) -> tuple[bool, list[str]]:
        """Validate all required secrets are present.
        
        Args:
            environment: Current environment (development, staging, production)
            
        Returns:
            Tuple of (is_valid, missing_secrets)
        """
        required = self.REQUIRED_SECRETS.get(environment, self.REQUIRED_SECRETS["production"])
        missing = []

        for key in required:
            value = self.get_secret(key)
            if not value:
                missing.append(key)
            elif self._is_weak_secret(key, value):
                logger.warning(f"Secret {key} appears to be a weak/default value")

        return len(missing) == 0, missing

    def _is_weak_secret(self, key: str, value: str) -> bool:
        """Check if a secret appears to be weak/default."""
        if key not in self.SENSITIVE_KEYS:
            return False

        weak_values = {"secret", "changeme", "password", "development", "test", "12345"}
        return len(value) < 32 or value.lower() in weak_values

    @staticmethod
    def mask_secret(value: str, visible_chars: int = 4) -> str:
        """Mask a secret value for safe logging.
        
        Args:
            value: The secret value to mask
            visible_chars: Number of characters to show at end
            
        Returns:
            Masked string like '****xyz'
        """
        if not value or len(value) <= visible_chars:
            return "****"
        return "*" * (len(value) - visible_chars) + value[-visible_chars:]

    def clear_cache(self) -> None:
        """Clear the secrets cache."""
        self._cache.clear()

    # AWS Secrets Manager integration (stub for future use)
    # def _get_from_aws(self, key: str) -> Optional[str]:
    #     """Retrieve secret from AWS Secrets Manager."""
    #     try:
    #         if self._aws_client is None:
    #             import boto3
    #             self._aws_client = boto3.client('secretsmanager')
    #         
    #         response = self._aws_client.get_secret_value(SecretId=key)
    #         return response['SecretString']
    #     except Exception as e:
    #         logger.debug(f"Could not retrieve {key} from AWS: {e}")
    #         return None


@lru_cache()
def get_secrets_manager() -> SecretsManager:
    """Get cached SecretsManager instance."""
    return SecretsManager()


# Convenience function
def get_secret(key: str, default: Optional[str] = None) -> Optional[str]:
    """Get a secret value.
    
    Args:
        key: The secret key name
        default: Default value if not found
        
    Returns:
        The secret value or default
    """
    return get_secrets_manager().get_secret(key, default)
