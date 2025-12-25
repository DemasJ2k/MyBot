"""Observability module for Flowrex - logging, metrics, and tracing."""

from app.observability.logging_config import setup_logging, get_logger
from app.observability.metrics import (
    setup_metrics,
    http_requests_total,
    http_request_duration_seconds,
    trades_executed_total,
    signals_generated_total,
    active_strategies,
    websocket_connections,
    database_connections,
)

__all__ = [
    "setup_logging",
    "get_logger",
    "setup_metrics",
    "http_requests_total",
    "http_request_duration_seconds",
    "trades_executed_total",
    "signals_generated_total",
    "active_strategies",
    "websocket_connections",
    "database_connections",
]
