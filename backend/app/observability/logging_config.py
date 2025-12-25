"""
Structured logging configuration for Flowrex.

Prompt 17 - Deployment Prep.

Provides:
- JSON formatted logs for production
- Text formatted logs for development
- Configurable log levels
- Rotating file handler for non-development environments
"""

import logging
import sys
from datetime import datetime, timezone
from typing import Optional
import os

try:
    from pythonjsonlogger import jsonlogger
    HAS_JSON_LOGGER = True
except ImportError:
    HAS_JSON_LOGGER = False


class CustomJsonFormatter(jsonlogger.JsonFormatter if HAS_JSON_LOGGER else logging.Formatter):
    """Custom JSON formatter with additional fields."""

    def add_fields(self, log_record: dict, record: logging.LogRecord, message_dict: dict) -> None:
        """Add custom fields to log record."""
        super().add_fields(log_record, record, message_dict)

        # Add timestamp in ISO format
        log_record['timestamp'] = datetime.now(timezone.utc).isoformat()

        # Add environment
        log_record['environment'] = os.getenv("ENVIRONMENT", os.getenv("APP_ENV", "development"))

        # Add service name
        log_record['service'] = 'flowrex-backend'

        # Add level as string
        log_record['level'] = record.levelname

        # Add source location
        log_record['logger'] = record.name
        log_record['module'] = record.module
        log_record['function'] = record.funcName
        log_record['line'] = record.lineno

        # Add request context if available
        if hasattr(record, 'request_id'):
            log_record['request_id'] = record.request_id
        if hasattr(record, 'user_id'):
            log_record['user_id'] = record.user_id


class ColoredFormatter(logging.Formatter):
    """Colored formatter for development console output."""

    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
    }
    RESET = '\033[0m'

    def format(self, record: logging.LogRecord) -> str:
        """Format with colors."""
        color = self.COLORS.get(record.levelname, self.RESET)
        record.levelname = f"{color}{record.levelname}{self.RESET}"
        return super().format(record)


def setup_logging(
    log_level: Optional[str] = None,
    log_format: Optional[str] = None,
    log_file_enabled: Optional[bool] = None,
    log_file_path: Optional[str] = None,
) -> None:
    """Configure application logging.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: Log format ('json' or 'text')
        log_file_enabled: Whether to enable file logging
        log_file_path: Path to log file
    """
    # Get settings from environment if not provided
    log_level = log_level or os.getenv("LOG_LEVEL", "INFO")
    log_format = log_format or os.getenv("LOG_FORMAT", "json")
    environment = os.getenv("ENVIRONMENT", os.getenv("APP_ENV", "development"))
    
    if log_file_enabled is None:
        log_file_enabled = os.getenv("LOG_FILE_ENABLED", "false").lower() == "true"
    if log_file_path is None:
        log_file_path = os.getenv("LOG_FILE_PATH", "/var/log/flowrex/app.log")

    # Root logger
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Remove existing handlers
    logger.handlers = []

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    if log_format == "json" and HAS_JSON_LOGGER:
        formatter = CustomJsonFormatter(
            '%(timestamp)s %(level)s %(name)s %(message)s'
        )
    elif environment in ("development", "dev"):
        formatter = ColoredFormatter(
            '%(asctime)s - %(levelname)s - %(name)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    else:
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(name)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler (if enabled and not in development)
    if log_file_enabled and environment not in ("development", "dev"):
        try:
            from logging.handlers import RotatingFileHandler
            
            # Ensure directory exists
            log_dir = os.path.dirname(log_file_path)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir, exist_ok=True)

            file_handler = RotatingFileHandler(
                log_file_path,
                maxBytes=int(os.getenv("LOG_FILE_MAX_BYTES", 10485760)),  # 10MB
                backupCount=int(os.getenv("LOG_FILE_BACKUP_COUNT", 5)),
            )
            file_handler.setLevel(getattr(logging, log_level.upper(), logging.INFO))
            
            # Always use JSON for file logs
            if HAS_JSON_LOGGER:
                file_handler.setFormatter(CustomJsonFormatter(
                    '%(timestamp)s %(level)s %(name)s %(message)s'
                ))
            else:
                file_handler.setFormatter(formatter)
            
            logger.addHandler(file_handler)
        except Exception as e:
            logger.warning(f"Could not setup file logging: {e}")

    # Silence noisy libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)

    logger.info("Logging configured", extra={
        "log_level": log_level,
        "log_format": log_format,
        "environment": environment,
    })


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the given name.
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


class RequestContextFilter(logging.Filter):
    """Filter that adds request context to log records."""

    def __init__(self, request_id: Optional[str] = None, user_id: Optional[int] = None):
        super().__init__()
        self.request_id = request_id
        self.user_id = user_id

    def filter(self, record: logging.LogRecord) -> bool:
        """Add context to record."""
        record.request_id = self.request_id
        record.user_id = self.user_id
        return True
